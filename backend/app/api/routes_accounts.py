"""Account management, import triggers, and synthetic mailbox generation endpoints."""

import json
from fastapi import APIRouter, Depends, HTTPException
import sqlite3
from typing import List, Dict, Any, Optional

from backend.app.db.database import Database, get_db, get_database
from backend.app.models.schemas import (
    AccountCreate,
    AccountResponse,
    AccountStatusUpdate,
    SyntheticGenerateRequest,
    ImapConnectRequest,
    CategorySyncExecuteRequest,
    CategorySyncUndoRequest,
)
from backend.app.classification import CategoryLabelSyncService
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.providers.synthetic import SyntheticMailboxGenerator
from backend.app.providers.mbox import MboxProvider
from backend.app.providers.imap import ImapProvider

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

@router.get("", response_model=List[AccountResponse])
def list_accounts(conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, provider, display_name, email_address, created_at, last_sync_at, status
        FROM accounts
        ORDER BY id ASC;
    """)
    rows = cursor.fetchall()
    return [
        AccountResponse(
            id=r["id"],
            provider=r["provider"],
            display_name=r["display_name"],
            email_address=r["email_address"],
            created_at=r["created_at"],
            last_sync_at=r["last_sync_at"],
            status=r["status"]
        )
        for r in rows
    ]

@router.post("", response_model=AccountResponse)
def create_account(req: AccountCreate, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO accounts (provider, display_name, email_address, settings_json)
        VALUES (?, ?, ?, ?);
    """, (req.provider, req.display_name, req.email_address, req.settings_json or "{}"))
    account_id = cursor.lastrowid
    
    cursor.execute("SELECT id, provider, display_name, email_address, created_at, last_sync_at, status FROM accounts WHERE id = ?;", (account_id,))
    r = cursor.fetchone()
    return AccountResponse(
        id=r["id"],
        provider=r["provider"],
        display_name=r["display_name"],
        email_address=r["email_address"],
        created_at=r["created_at"],
        last_sync_at=r["last_sync_at"],
        status=r["status"]
    )

@router.patch("/{account_id}/status", response_model=AccountResponse)
def update_account_status(account_id: int, req: AccountStatusUpdate, conn: sqlite3.Connection = Depends(get_db)):
    if req.status not in ("active", "paused"):
        raise HTTPException(status_code=400, detail="Status must be 'active' or 'paused'")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM accounts WHERE id = ?;", (account_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Account not found")
    cursor.execute("UPDATE accounts SET status = ? WHERE id = ?;", (req.status, account_id))
    conn.commit()
    cursor.execute("SELECT id, provider, display_name, email_address, created_at, last_sync_at, status FROM accounts WHERE id = ?;", (account_id,))
    r = cursor.fetchone()
    return AccountResponse(
        id=r["id"],
        provider=r["provider"],
        display_name=r["display_name"],
        email_address=r["email_address"],
        created_at=r["created_at"],
        last_sync_at=r["last_sync_at"],
        status=r["status"]
    )

@router.delete("/{account_id}")
def delete_account(account_id: int, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT id, email_address FROM accounts WHERE id = ?;", (account_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")

    email_address = row["email_address"]
    cursor.execute("DELETE FROM accounts WHERE id = ?;", (account_id,))

    # Only delete credentials if no remaining account uses this email address
    cursor.execute("SELECT 1 FROM accounts WHERE email_address = ? LIMIT 1;", (email_address,))
    if not cursor.fetchone():
        from backend.app.security.credential_store import CredentialStore
        CredentialStore().delete_credentials(email_address)

    # Clean up orphan senders with no remaining messages
    cursor.execute("""
        DELETE FROM senders
        WHERE id NOT IN (SELECT DISTINCT sender_id FROM messages WHERE sender_id IS NOT NULL);
    """)
    return {"status": "success", "deleted_account_id": account_id}

@router.post("/synthetic")
@router.post("/synthetic/generate")
def generate_synthetic(req: SyntheticGenerateRequest):
    """Generate and index realistic synthetic mailbox emails for testing and demo."""
    db = get_database()
    with db.connect() as conn:
        cursor = conn.cursor()
        # Check if demo account already exists or create one
        cursor.execute("SELECT id FROM accounts WHERE provider = 'synthetic' AND email_address = ?;", (req.email_address,))
        row = cursor.fetchone()
        if row:
            account_id = row[0]
        else:
            cursor.execute("""
                INSERT INTO accounts (provider, display_name, email_address)
                VALUES ('synthetic', ?, ?);
            """, (req.display_name, req.email_address))
            account_id = cursor.lastrowid
        
    generator = SyntheticMailboxGenerator(seed=req.seed)
    pipeline = IngestionPipeline(db)
    result = pipeline.ingest_messages(account_id, generator.generate(count=req.message_count))
    
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET last_sync_at = datetime('now') WHERE id = ?;", (account_id,))
    
    return {
        "status": "success",
        "account_id": account_id,
        "scanned_count": result.scanned_count,
        "inserted_count": result.inserted_count,
        "skipped_count": result.skipped_count,
        "failed_count": result.failed_count
    }

@router.post("/mbox/import")
def import_mbox(account_id: int, file_path: str, limit: Optional[int] = None):
    """Import an offline MBOX archive file into the specified account."""
    db = get_database()
    _verify_account_active(account_id, db)

    provider = MboxProvider(file_path=file_path)
    try:
        provider.connect()
    except FileNotFoundError as ex:
        raise HTTPException(status_code=400, detail=str(ex))

    pipeline = IngestionPipeline(db)
    result = pipeline.ingest_messages(account_id, provider.stream_messages(limit=limit))

    with db.connect() as conn:
        conn.execute("UPDATE accounts SET last_sync_at = datetime('now') WHERE id = ?;", (account_id,))

    return {
        "status": "success",
        "account_id": account_id,
        "scanned_count": result.scanned_count,
        "inserted_count": result.inserted_count,
        "skipped_count": result.skipped_count,
        "failed_count": result.failed_count
    }

@router.post("/imap/connect")
def connect_imap(req: ImapConnectRequest, initial_scan_limit: Optional[int] = 100):
    """Authenticate and link a Gmail or IMAP account using an App Password."""
    from backend.app.security.credential_store import CredentialStore

    # 1. Test IMAP connection
    provider = ImapProvider(
        host=req.host,
        username=req.username,
        password=req.password,
        port=req.port,
        use_ssl=req.use_ssl
    )
    try:
        provider.connect()
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Failed to connect to {req.host}: {str(ex)}")

    try:
        # 2. Store credentials in OS Keyring
        cred_store = CredentialStore()
        cred_json = json.dumps({
            "provider": "imap",
            "host": req.host,
            "port": req.port,
            "username": req.username,
            "password": req.password
        })
        cred_store.save_credentials(req.email_address, cred_json)

        # 3. Register in SQLite
        db = get_database()
        with db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM accounts WHERE email_address = ?;", (req.email_address,))
            row = cursor.fetchone()
            if row:
                account_id = row[0]
                cursor.execute("UPDATE accounts SET status = 'active', last_sync_at = datetime('now') WHERE id = ?;", (account_id,))
            else:
                cursor.execute("""
                    INSERT INTO accounts (provider, display_name, email_address, settings_json)
                    VALUES ('imap', ?, ?, ?);
                """, (req.display_name, req.email_address, json.dumps({"host": req.host, "port": req.port})))
                account_id = cursor.lastrowid

        # 4. Run initial scan if requested
        inserted = 0
        if initial_scan_limit is not None and initial_scan_limit <= 0:
            pipeline = IngestionPipeline(db)
            res = pipeline.ingest_messages(account_id, provider.stream_messages(folder_id="INBOX", limit=None))
            inserted = res.inserted_count
        elif initial_scan_limit and initial_scan_limit > 0:
            pipeline = IngestionPipeline(db)
            res = pipeline.ingest_messages(account_id, provider.stream_messages(folder_id="INBOX", limit=initial_scan_limit))
            inserted = res.inserted_count

        return {
            "status": "success",
            "account_id": account_id,
            "email_address": req.email_address,
            "inserted_count": inserted
        }
    finally:
        provider.disconnect()

@router.post("/{account_id}/sync")
def sync_account(account_id: int, limit: Optional[int] = 100):
    """
    Sync new emails for an existing account using stored credentials from OS Keyring.
    Eliminates needing to re-enter email & password.
    """
    db = get_database()
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, provider, display_name, email_address, settings_json, status FROM accounts WHERE id = ?;", (account_id,))
        acc = cursor.fetchone()
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found.")
        if acc["status"] == "paused":
            raise HTTPException(status_code=400, detail="Cannot sync a disabled/paused account. Please re-enable it first.")
        provider_name = acc[1]
        email_address = acc[3]

    pipeline = IngestionPipeline(db)
    remote_provider = None

    try:
        if provider_name == "synthetic":
            generator = SyntheticMailboxGenerator()
            res = pipeline.ingest_messages(account_id, generator.generate(count=limit or 25))
        elif provider_name in ("imap", "gmail"):
            from backend.app.security.credential_store import CredentialStore
            cred_store = CredentialStore()
            secret = cred_store.get_credentials(email_address)
            if not secret:
                raise HTTPException(
                    status_code=400,
                    detail=f"No stored credentials found in OS Keyring for {email_address}. Please reconnect your account."
                )
            try:
                creds = json.loads(secret)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid credential payload stored in OS Keyring.")

            if creds.get("provider") == "imap" or "password" in creds:
                remote_provider = ImapProvider(
                    host=creds.get("host", "imap.gmail.com"),
                    username=creds.get("username", email_address),
                    password=creds["password"],
                    port=creds.get("port", 993),
                    use_ssl=creds.get("use_ssl", True)
                )
                remote_provider.connect()
                res = pipeline.ingest_messages(account_id, remote_provider.stream_messages(folder_id="INBOX", limit=limit))
            elif creds.get("provider") == "gmail" or "access_token" in creds:
                from backend.app.providers.gmail import GmailProvider
                remote_provider = GmailProvider(account_email=email_address, token_dict=creds)
                remote_provider.connect()
                res = pipeline.ingest_messages(account_id, remote_provider.stream_messages(limit=limit))
            else:
                raise HTTPException(status_code=400, detail="Unrecognized credential structure in OS Keyring.")
        else:
            raise HTTPException(status_code=400, detail=f"Sync not supported for provider '{provider_name}'.")
    finally:
        if remote_provider is not None and hasattr(remote_provider, "disconnect"):
            try:
                remote_provider.disconnect()
            except Exception:
                pass

    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET last_sync_at = datetime('now'), status = 'active' WHERE id = ?;", (account_id,))

    return {
        "status": "success",
        "account_id": account_id,
        "scanned_count": res.scanned_count,
        "inserted_count": res.inserted_count,
        "updated_count": res.updated_count,
        "skipped_count": res.skipped_count,
        "failed_count": res.failed_count
    }

@router.post("/{account_id}/sync-start")
def start_background_sync(account_id: int, limit: Optional[int] = None):
    """
    Launch asynchronous ingestion job in a background worker thread.
    Allows fetching ALL emails without blocking the HTTP server or UI navigation.
    """
    db = get_database()
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM accounts WHERE id = ?;", (account_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found.")
        if row["status"] == "paused":
            raise HTTPException(status_code=400, detail="Cannot sync a disabled/paused account. Please re-enable it first.")

    from backend.app.ingestion.sync_manager import sync_manager
    res = sync_manager.start_sync(account_id, limit=limit)
    return res

@router.get("/sync/active")
def get_active_sync_status():
    """Poll active background ingestion job telemetry (scanned, inserted, total, pct, speed)."""
    from backend.app.ingestion.sync_manager import sync_manager
    job = sync_manager.get_active_job()
    return {
        "active": bool(job and job.get("status") in ("starting", "running", "stopping")),
        "job": job
    }

@router.post("/sync/stop")
def stop_active_sync():
    """Gracefully cancel and stop any active background ingestion job."""
    from backend.app.ingestion.sync_manager import sync_manager
    stopped = sync_manager.stop_active_sync()
    return {"status": "stopping" if stopped else "no_active_job"}


def _verify_account_active(account_id: int, db: Database) -> Dict[str, Any]:
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM accounts WHERE id = ?;", (account_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found.")
        if row["status"] == "paused":
            raise HTTPException(status_code=400, detail="Cannot sync a disabled/paused account. Please re-enable it first.")
        return dict(row)


@router.post("/{account_id}/sync-labels/preview")
def preview_category_label_sync(account_id: int):
    """Calculate preview counts of messages grouped by category for label synchronization."""
    db = get_database()
    _verify_account_active(account_id, db)
    service = CategoryLabelSyncService(db)
    return service.preview_sync(account_id)


@router.post("/{account_id}/sync-labels/execute")
def execute_category_label_sync(account_id: int, req: Optional[CategorySyncExecuteRequest] = None):
    """Execute label synchronization for specified categories (or all eligible categories)."""
    db = get_database()
    _verify_account_active(account_id, db)
    service = CategoryLabelSyncService(db)
    categories = req.categories if req else None
    batch_id = req.batch_id if req else None
    return service.execute_sync(account_id, categories=categories, batch_id=batch_id)


@router.post("/{account_id}/sync-labels/undo")
def undo_category_label_sync(account_id: int, req: CategorySyncUndoRequest):
    """Roll back applied labels for a specific category sync batch."""
    db = get_database()
    _verify_account_active(account_id, db)
    service = CategoryLabelSyncService(db)
    return service.undo_batch(req.batch_id, account_id=account_id)

