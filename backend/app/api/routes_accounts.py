"""Account management, import triggers, and synthetic mailbox generation endpoints."""

import json
from fastapi import APIRouter, Depends, HTTPException
import sqlite3
from typing import List, Dict, Any, Optional

from backend.app.db.database import get_db, get_database
from backend.app.models.schemas import AccountCreate, AccountResponse, SyntheticGenerateRequest, ImapConnectRequest
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

@router.delete("/{account_id}")
def delete_account(account_id: int, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM accounts WHERE id = ?;", (account_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Account not found")
        
    cursor.execute("DELETE FROM accounts WHERE id = ?;", (account_id,))
    # Clean up orphan senders with no remaining messages
    cursor.execute("""
        DELETE FROM senders
        WHERE id NOT IN (SELECT DISTINCT sender_id FROM messages WHERE sender_id IS NOT NULL);
    """)
    return {"status": "success", "deleted_account_id": account_id}

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
    provider = MboxProvider(file_path=file_path)
    provider.connect()
    pipeline = IngestionPipeline(db)
    
    result = pipeline.ingest_messages(account_id, provider.stream_messages(limit=limit))
    return {
        "status": "success",
        "account_id": account_id,
        "inserted_count": result.inserted_count,
        "skipped_count": result.skipped_count,
        "failed_count": result.failed_count
    }
