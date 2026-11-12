"""Ingestion pipeline coordinating streaming parsing, deduplication, and database insertion."""

import re
import json
import sqlite3
from dataclasses import dataclass
from typing import Generator, Iterable, Optional, Callable, Dict, Any
from backend.app.db.database import Database
from backend.app.ingestion.mime_parser import ParsedEmail
from backend.app.classification.rules_engine import RulesEngine

@dataclass
class IngestionResult:
    scanned_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    error_message: Optional[str] = None

class IngestionPipeline:
    """Manages transactional ingestion of emails into the local SQLite store."""

    def __init__(self, db: Database):
        self.db = db
        self.rules_engine = RulesEngine()

    def ingest_messages(
        self,
        account_id: int,
        messages: Iterable[ParsedEmail],
        folder_id: Optional[int] = None,
        progress_callback: Optional[Callable[[IngestionResult], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> IngestionResult:
        """Streamingly ingest parsed messages with deduplication and indexing."""
        res = IngestionResult()
        
        # Start a sync run record
        sync_run_id = self._start_sync_run(account_id)
        
        try:
            with self.db.connect() as conn:
                cursor = conn.cursor()
                
                # Cache known sender IDs to minimize queries
                cursor.execute("SELECT normalized_address, id FROM senders;")
                sender_cache: Dict[str, int] = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Cache categories
                cursor.execute("SELECT name, id FROM categories;")
                category_cache: Dict[str, int] = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Cache existing provider message IDs for this account for fast deduplication
                cursor.execute("SELECT provider_message_id FROM messages WHERE account_id = ?;", (account_id,))
                existing_pids = {row[0] for row in cursor.fetchall()}
                
                cursor.execute("SELECT content_hash FROM messages WHERE account_id = ? AND content_hash IS NOT NULL;", (account_id,))
                existing_hashes = {row[0] for row in cursor.fetchall()}
                
                batch_count = 0
                
                for email_msg in messages:
                    if is_cancelled and is_cancelled():
                        res.error_message = "Ingestion cancelled by user."
                        break
                        
                    res.scanned_count += 1
                    
                    # Deduplication check
                    if email_msg.provider_message_id in existing_pids:
                        res.skipped_count += 1
                        continue
                    if email_msg.content_hash and email_msg.content_hash in existing_hashes:
                        res.skipped_count += 1
                        continue
                        
                    try:
                        # 1. Resolve or create sender
                        sender_id = self._resolve_sender(cursor, email_msg, sender_cache)
                        
                        # 2. Resolve or create thread
                        thread_id = self._resolve_thread(cursor, account_id, email_msg)
                        
                        # 3. Insert message
                        cursor.execute("""
                            INSERT INTO messages (
                                account_id, provider_message_id, provider_thread_id,
                                folder_id, thread_id, message_id_header, in_reply_to,
                                references_header, subject, sender_name, sender_address,
                                sender_id, sent_at, received_at, is_read, is_starred,
                                is_important, has_attachments, size_bytes, snippet,
                                body_text, body_indexed, content_hash
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, (
                            account_id, email_msg.provider_message_id, email_msg.provider_thread_id,
                            folder_id, thread_id, email_msg.message_id_header, email_msg.in_reply_to,
                            email_msg.references_header, email_msg.subject, email_msg.sender_name,
                            email_msg.sender_address, sender_id, email_msg.sent_at, email_msg.received_at,
                            1 if email_msg.is_read else 0,
                            1 if email_msg.is_starred else 0,
                            1 if email_msg.is_important else 0,
                            1 if email_msg.has_attachments else 0,
                            email_msg.size_bytes, email_msg.snippet,
                            email_msg.body_text, 0, email_msg.content_hash
                        ))
                        message_id = cursor.lastrowid
                        
                        # 4. Insert addresses
                        for addr in email_msg.addresses:
                            cursor.execute("""
                                INSERT INTO message_addresses (message_id, address, display_name, role)
                                VALUES (?, ?, ?, ?);
                            """, (message_id, addr.address, addr.display_name, addr.role))
                            
                        # 5. Insert attachments
                        for att in email_msg.attachments:
                            cursor.execute("""
                                INSERT INTO attachments (
                                    message_id, provider_attachment_id, filename,
                                    mime_type, size_bytes, content_hash, is_inline, content_available
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                            """, (
                                message_id, None, att.filename,
                                att.mime_type, att.size_bytes, att.content_hash,
                                1 if att.is_inline else 0,
                                1 if att.content_available else 0
                            ))
                            
                        # 6. Insert FTS index
                        cursor.execute("""
                            INSERT INTO messages_fts (message_id, subject, snippet, body_text)
                            VALUES (?, ?, ?, ?);
                        """, (message_id, email_msg.subject, email_msg.snippet, email_msg.body_text or ""))
                        
                        # 7. Apply deterministic classification rule
                        cat_name, conf, reason = self.rules_engine.classify(email_msg)
                        cat_id = category_cache.get(cat_name) or category_cache.get("unknown")
                        if cat_id:
                            cursor.execute("""
                                INSERT OR IGNORE INTO message_categories (message_id, category_id, source, confidence, reason)
                                VALUES (?, ?, 'rule', ?, ?);
                            """, (message_id, cat_id, conf, reason))
                        
                        # Update local caches
                        existing_pids.add(email_msg.provider_message_id)
                        if email_msg.content_hash:
                            existing_hashes.add(email_msg.content_hash)
                        res.inserted_count += 1
                        batch_count += 1
                        
                        # Report smooth progress every 15 items
                        if progress_callback and res.scanned_count % 15 == 0:
                            progress_callback(res)

                        # Commit periodic transaction batches (every 100 messages) for fast disk writes
                        if batch_count >= 100:
                            conn.commit()
                            batch_count = 0
                                
                    except Exception as ex:
                        res.failed_count += 1
                        continue
                        
                conn.commit()
                
            self._complete_sync_run(sync_run_id, res)
            if progress_callback:
                progress_callback(res)
                
        except Exception as ex:
            res.error_message = str(ex)
            self._fail_sync_run(sync_run_id, str(ex))
            
        return res

    def _resolve_sender(self, cursor: sqlite3.Cursor, email_msg: ParsedEmail, sender_cache: Dict[str, int]) -> int:
        addr = email_msg.sender_address.lower().strip()
        if addr in sender_cache:
            sender_id = sender_cache[addr]
            cursor.execute("""
                UPDATE senders
                SET last_seen_at = CASE 
                    WHEN last_seen_at IS NULL OR ? > last_seen_at THEN ? 
                    ELSE last_seen_at 
                END,
                first_seen_at = CASE 
                    WHEN first_seen_at IS NULL OR ? < first_seen_at THEN ? 
                    ELSE first_seen_at 
                END
                WHERE id = ?;
            """, (email_msg.received_at, email_msg.received_at, email_msg.received_at, email_msg.received_at, sender_id))
            return sender_id
            
        # Create new sender
        cursor.execute("""
            INSERT INTO senders (normalized_address, display_name, domain, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(normalized_address) DO UPDATE SET
                last_seen_at = excluded.last_seen_at
            RETURNING id;
        """, (addr, email_msg.sender_name, email_msg.sender_domain, email_msg.received_at, email_msg.received_at))
        row = cursor.fetchone()
        sender_id = row[0]
        sender_cache[addr] = sender_id
        return sender_id

    def _resolve_thread(self, cursor: sqlite3.Cursor, account_id: int, email_msg: ParsedEmail) -> int:
        norm_subj = re.sub(r'^(re|fwd|fw):\s*', '', email_msg.subject, flags=re.I).strip()
        provider_tid = email_msg.provider_thread_id
        
        # 1. Match by provider thread ID if available
        if provider_tid:
            cursor.execute("""
                SELECT id, message_count FROM threads 
                WHERE account_id = ? AND provider_thread_id = ?;
            """, (account_id, provider_tid))
            row = cursor.fetchone()
            if row:
                tid, count = row[0], row[1]
                cursor.execute("""
                    UPDATE threads 
                    SET message_count = message_count + 1,
                        last_message_at = CASE WHEN ? > last_message_at THEN ? ELSE last_message_at END
                    WHERE id = ?;
                """, (email_msg.received_at, email_msg.received_at, tid))
                return tid
                
        # 2. Match by normalized subject within the last 30 days
        if norm_subj and norm_subj != "(No Subject)":
            cursor.execute("""
                SELECT id, message_count FROM threads 
                WHERE account_id = ? AND subject_normalized = ?;
            """, (account_id, norm_subj))
            row = cursor.fetchone()
            if row:
                tid, count = row[0], row[1]
                cursor.execute("""
                    UPDATE threads 
                    SET message_count = message_count + 1,
                        last_message_at = CASE WHEN ? > last_message_at THEN ? ELSE last_message_at END
                    WHERE id = ?;
                """, (email_msg.received_at, email_msg.received_at, tid))
                return tid

        # 3. Create new thread
        cursor.execute("""
            INSERT INTO threads (
                account_id, provider_thread_id, subject_normalized,
                first_message_at, last_message_at, message_count
            ) VALUES (?, ?, ?, ?, ?, 1);
        """, (account_id, provider_tid, norm_subj, email_msg.received_at, email_msg.received_at))
        return cursor.lastrowid

    def _start_sync_run(self, account_id: int) -> int:
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_runs (account_id, status) VALUES (?, 'running');
            """, (account_id,))
            return cursor.lastrowid

    def _complete_sync_run(self, sync_run_id: int, res: IngestionResult) -> None:
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sync_runs
                SET status = 'completed',
                    completed_at = datetime('now'),
                    scanned_count = ?,
                    inserted_count = ?,
                    failed_count = ?
                WHERE id = ?;
            """, (res.scanned_count, res.inserted_count, res.failed_count, sync_run_id))

    def _fail_sync_run(self, sync_run_id: int, error_msg: str) -> None:
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sync_runs
                SET status = 'failed',
                    completed_at = datetime('now'),
                    checkpoint_json = ?
                WHERE id = ?;
            """, (json.dumps({"error": error_msg}), sync_run_id))
