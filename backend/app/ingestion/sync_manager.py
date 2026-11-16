"""Background synchronization manager for long-running email ingestion jobs."""

import time
import json
import logging
import threading
from typing import Optional, Dict, Any
from backend.app.db.database import get_database
from backend.app.ingestion.pipeline import IngestionPipeline, IngestionResult
from backend.app.providers.imap import ImapProvider
from backend.app.providers.gmail import GmailProvider
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
                display_name = row[2]
                email_address = row[3]

            with self._lock:
                self._active_job["email_address"] = email_address
                self._active_job["status"] = "running"

            pipeline = IngestionPipeline(db)

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
                creds = json.loads(secret)

                if creds.get("provider") == "imap" or "password" in creds:
                    provider = ImapProvider(
                        host=creds.get("host", "imap.gmail.com"),
                        username=creds.get("username", email_address),
                        password=creds["password"],
                        port=creds.get("port", 993),
                        use_ssl=creds.get("use_ssl", True)
                    )
                    provider.connect()
                    inbox_total = provider.get_message_count("INBOX")
                    target_limit = limit if (limit and limit > 0) else inbox_total
                    if inbox_total > 0 and target_limit > inbox_total:
                        target_limit = inbox_total

                    with self._lock:
                        self._active_job["total_count"] = target_limit if target_limit > 0 else inbox_total

                    messages = provider.stream_messages(folder_id="INBOX", limit=target_limit if target_limit > 0 else None, batch_size=50)

                elif creds.get("provider") == "gmail" or "access_token" in creds:
                    provider = GmailProvider(token_dict=creds)
                    provider.connect()
                    target_limit = limit if (limit and limit > 0) else 1000
                    with self._lock:
                        self._active_job["total_count"] = target_limit
                    messages = provider.stream_messages(limit=target_limit)
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

            start_time = time.time()

            def on_progress(res: IngestionResult):
                elapsed = max(0.1, time.time() - start_time)
                tot = self._active_job.get("total_count", 0)
                pct = min(100.0, (res.scanned_count / tot * 100.0)) if tot > 0 else 0.0
                speed = res.scanned_count / elapsed
                with self._lock:
                    self._active_job["scanned_count"] = res.scanned_count
                    self._active_job["inserted_count"] = res.inserted_count
                    self._active_job["skipped_count"] = res.skipped_count
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
                self._active_job["scanned_count"] = result.scanned_count
                self._active_job["inserted_count"] = result.inserted_count
                self._active_job["skipped_count"] = result.skipped_count

            with db.connect() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE accounts SET last_sync_at = datetime('now'), status = 'active' WHERE id = ?;", (account_id,))

        except Exception as ex:
            logger.exception("Error in background sync thread: %s", ex)
            with self._lock:
                self._active_job["status"] = "failed"
                self._active_job["error_message"] = str(ex)

sync_manager = SyncManager()
