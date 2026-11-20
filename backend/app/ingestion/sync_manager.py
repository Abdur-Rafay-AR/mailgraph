"""Background synchronization manager for long-running email ingestion jobs."""

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.app.db.database import get_database
from backend.app.ingestion.pipeline import IngestionPipeline, IngestionResult
from backend.app.providers.gmail import GmailProvider
from backend.app.providers.imap import ImapProvider
from backend.app.providers.synthetic import SyntheticMailboxGenerator
from backend.app.security.credential_store import CredentialStore

logger = logging.getLogger(__name__)

class SyncManager:
    """Singleton manager coordinating asynchronous mailbox ingestion and cancellation."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._active_job: Optional[Dict[str, Any]] = None

    def get_active_job(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._active_job:
                return dict(self._active_job)
            return None

    def stop_active_sync(self) -> bool:
        with self._lock:
            if self._active_job and self._active_job.get("status") in ("running", "starting"):
                self._stop_event.set()
                self._active_job["status"] = "stopping"
                return True
            return False

    def start_sync(self, account_id: int, limit: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            if self._active_job and self._active_job.get("status") in ("running", "starting", "stopping"):
                if self._thread and self._thread.is_alive():
                    return {"status": "already_running", "job": dict(self._active_job)}

            self._stop_event.clear()
            self._active_job = {
                "account_id": account_id,
                "status": "starting",
                "folder": "INBOX",
                "total_count": 0,
                "scanned_count": 0,
                "inserted_count": 0,
                "updated_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "pct": 0.0,
                "speed": 0.0,
                "started_at": time.time(),
                "error_message": None,
                "email_address": "",
                "is_all": (limit is None or limit <= 0)
            }

            self._thread = threading.Thread(
                target=self._run_sync,
                args=(account_id, limit),
                daemon=True
            )
            self._thread.start()
            return {"status": "started", "job": dict(self._active_job)}

    def _run_sync(self, account_id: int, limit: Optional[int] = None):
        db = get_database()
        remote_provider = None
        try:
            with db.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, provider, display_name, email_address, settings_json, status FROM accounts WHERE id = ?;",
                    (account_id,)
                )
                row = cursor.fetchone()
                if not row:
                    with self._lock:
                        self._active_job["status"] = "failed"
                        self._active_job["error_message"] = "Account not found"
                    return

                if row["status"] == "paused":
                    with self._lock:
                        self._active_job["status"] = "failed"
                        self._active_job["error_message"] = "Cannot sync disabled/paused account"
                    return

                provider_name = row[1]
                email_address = row[3]

            with self._lock:
                self._active_job["email_address"] = email_address
                self._active_job["status"] = "running"

            pipeline = IngestionPipeline(db)
            start_time = time.time()
            pre_scanned = 0
            pre_updated = 0
            pre_skipped = 0

            def record_flag_updates(updates: List[Tuple[str, bool, bool]], chunk_checked: int) -> None:
                nonlocal pre_scanned, pre_updated, pre_skipped
                if updates:
                    with db.connect() as conn:
                        conn.executemany(
                            """
                            UPDATE messages
                            SET is_read = ?, is_starred = ?, updated_at = datetime('now')
                            WHERE account_id = ? AND provider_message_id = ?;
                            """,
                            [(1 if r else 0, 1 if s else 0, account_id, pmid) for pmid, r, s in updates],
                        )
                pre_scanned += chunk_checked
                pre_updated += len(updates)
                pre_skipped += max(0, chunk_checked - len(updates))
                elapsed = max(0.1, time.time() - start_time)
                with self._lock:
                    tot = self._active_job.get("total_count", 0)
                    pct = min(100.0, (pre_scanned / tot * 100.0)) if tot > 0 else 0.0
                    self._active_job["scanned_count"] = pre_scanned
                    self._active_job["updated_count"] = pre_updated
                    self._active_job["skipped_count"] = pre_skipped
                    self._active_job["pct"] = round(pct, 1)
                    self._active_job["speed"] = round(pre_scanned / elapsed, 1)

            # Determine provider & total count
            if provider_name == "synthetic":
                total = limit if (limit and limit > 0) else 100
                with self._lock:
                    self._active_job["total_count"] = total
                generator = SyntheticMailboxGenerator()
                messages = generator.generate(count=total)

            elif provider_name in ("imap", "gmail"):
                cred_store = CredentialStore()
                secret = cred_store.get_credentials(email_address)
                if not secret:
                    with self._lock:
                        self._active_job["status"] = "failed"
                        self._active_job["error_message"] = f"No credentials stored in OS Keyring for {email_address}."
                    return
                try:
                    creds = json.loads(secret)
                except Exception:
                    with self._lock:
                        self._active_job["status"] = "failed"
                        self._active_job["error_message"] = "Invalid credential payload in OS Keyring."
                    return

                if creds.get("provider") == "imap" or "password" in creds:
                    remote_provider = ImapProvider(
                        host=creds.get("host", "imap.gmail.com"),
                        username=creds.get("username", email_address),
                        password=creds["password"],
                        port=creds.get("port", 993),
                        use_ssl=creds.get("use_ssl", True)
                    )
                    remote_provider.connect()
                    # For full mailbox syncs, prefer Gmail/IMAP "All Mail" so archived/sent/labeled mail is included
                    is_full_sync = limit is None or limit <= 0
                    target_folder = "INBOX"
                    if hasattr(remote_provider, "get_all_mail_folder_name"):
                        all_mail_folder = remote_provider.get_all_mail_folder_name()
                        if all_mail_folder and is_full_sync:
                            target_folder = all_mail_folder

                    folder_total = remote_provider.get_message_count(target_folder)
                    target_limit = limit if (limit and limit > 0) else folder_total
                    if folder_total > 0 and target_limit > folder_total:
                        target_limit = folder_total

                    with db.connect() as conn:
                        rows = conn.execute(
                            "SELECT provider_message_id, is_read, is_starred FROM messages WHERE account_id = ?;",
                            (account_id,),
                        ).fetchall()
                        known_state = {r[0]: (bool(r[1]), bool(r[2])) for r in rows}

                    with self._lock:
                        self._active_job["folder"] = target_folder
                        self._active_job["total_count"] = target_limit if target_limit > 0 else folder_total

                    messages = remote_provider.stream_messages(
                        folder_id=target_folder,
                        limit=target_limit if target_limit > 0 else None,
                        batch_size=50,
                        known_state=known_state,
                        on_flag_updates=record_flag_updates,
                    )

                elif creds.get("provider") == "gmail" or "access_token" in creds:
                    remote_provider = GmailProvider(account_email=email_address, token_dict=creds)
                    remote_provider.connect()
                    target_limit = limit if (limit and limit > 0) else 1000
                    with self._lock:
                        self._active_job["total_count"] = target_limit
                    messages = remote_provider.stream_messages(limit=target_limit)
                else:
                    with self._lock:
                        self._active_job["status"] = "failed"
                        self._active_job["error_message"] = "Invalid credentials format in OS Keyring."
                    return
            else:
                with self._lock:
                    self._active_job["status"] = "failed"
                    self._active_job["error_message"] = f"Sync not supported for provider '{provider_name}'."
                return

            def on_progress(res: IngestionResult):
                elapsed = max(0.1, time.time() - start_time)
                total_scanned = pre_scanned + res.scanned_count
                total_updated = pre_updated + res.updated_count
                total_skipped = pre_skipped + res.skipped_count
                with self._lock:
                    tot = self._active_job.get("total_count", 0)
                    pct = min(100.0, (total_scanned / tot * 100.0)) if tot > 0 else 0.0
                    speed = total_scanned / elapsed
                    self._active_job["scanned_count"] = total_scanned
                    self._active_job["inserted_count"] = res.inserted_count
                    self._active_job["updated_count"] = total_updated
                    self._active_job["skipped_count"] = total_skipped
                    self._active_job["failed_count"] = res.failed_count
                    self._active_job["pct"] = round(pct, 1)
                    self._active_job["speed"] = round(speed, 1)

            result = pipeline.ingest_messages(
                account_id=account_id,
                messages=messages,
                progress_callback=on_progress,
                is_cancelled=lambda: self._stop_event.is_set()
            )

            with self._lock:
                if self._stop_event.is_set():
                    self._active_job["status"] = "stopped"
                elif result.error_message and not self._stop_event.is_set():
                    self._active_job["status"] = "failed"
                    self._active_job["error_message"] = result.error_message
                else:
                    self._active_job["status"] = "completed"
                    self._active_job["pct"] = 100.0
                self._active_job["scanned_count"] = pre_scanned + result.scanned_count
                self._active_job["inserted_count"] = result.inserted_count
                self._active_job["updated_count"] = pre_updated + result.updated_count
                self._active_job["skipped_count"] = pre_skipped + result.skipped_count

            with db.connect() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE accounts SET last_sync_at = datetime('now'), status = 'active' WHERE id = ?;", (account_id,))

        except Exception as ex:
            logger.exception("Error in background sync thread: %s", ex)
            with self._lock:
                self._active_job["status"] = "failed"
                self._active_job["error_message"] = str(ex)
        finally:
            if remote_provider is not None and hasattr(remote_provider, "disconnect"):
                try:
                    remote_provider.disconnect()
                except Exception:
                    pass

sync_manager = SyncManager()
