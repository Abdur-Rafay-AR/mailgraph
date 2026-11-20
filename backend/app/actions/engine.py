"""Safe cleanup preview and execution engine with protection safeguards and undo tracking."""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from backend.app.db.database import Database
from backend.app.search.query_compiler import QueryCompiler, QueryAST

@dataclass
class ActionPreview:
    account_id: int
    operation_type: str
    target_count: int
    affected_threads_count: int
    total_size_bytes: int
    protected_excluded_count: int
    date_range_start: Optional[str]
    date_range_end: Optional[str]
    top_senders: List[Dict[str, Any]]
    samples: List[Dict[str, Any]]
    reversible: bool
    reversibility_note: str

class ActionEngine:
    """Manages preview simulation, confirmed execution, audit logs, and undo operations."""

    def __init__(self, db: Database):
        self.db = db
        self.compiler = QueryCompiler()

    def calculate_preview(
        self,
        account_id: int,
        operation_type: str,
        ast: QueryAST,
        label_name: Optional[str] = None
    ) -> ActionPreview:
        """
        Calculate preview of targets, storage impact, exclusions, and samples.
        Uses identical query logic as the execution path.
        """
        if operation_type not in ("trash", "archive", "label", "delete"):
            raise ValueError(f"Unsupported operation type '{operation_type}'.")
            
        ast.account_ids = [account_id]
        if operation_type == "label":
            ast.exclude_protected = True
        elif ast.exclude_protected is None:
            ast.exclude_protected = True
        
        with self.db.connect() as conn:
            cursor = conn.cursor()
            
            # 1. Target count and aggregated stats
            base_sql, params = self.compiler.compile_sql(ast, count_only=False)
            stats_sql = f"""
                WITH targets AS ({base_sql})
                SELECT 
                    COUNT(*) as count,
                    COUNT(DISTINCT thread_id) as thread_count,
                    COALESCE(SUM(size_bytes), 0) as total_bytes,
                    MIN(received_at) as earliest,
                    MAX(received_at) as latest
                FROM targets;
            """
            cursor.execute(stats_sql, params)
            stats = cursor.fetchone()
            target_count = stats[0]
            thread_count = stats[1]
            total_bytes = stats[2]
            earliest = stats[3]
            latest = stats[4]
            
            # 2. Protected count excluded (calculate difference if exclude_protected was False)
            unprotected_ast = QueryAST(
                version=ast.version,
                account_ids=ast.account_ids,
                all=ast.all,
                any=ast.any,
                none=ast.none,
                search_term=ast.search_term,
                exclude_protected=False
            )
            raw_sql, raw_params = self.compiler.compile_sql(unprotected_ast, count_only=True)
            cursor.execute(raw_sql, raw_params)
            total_unprotected = cursor.fetchone()[0]
            protected_excluded = max(0, total_unprotected - target_count)
            
            # 3. Top Senders breakdown
            sender_sql = f"""
                WITH targets AS ({base_sql})
                SELECT sender_address, sender_name, COUNT(*) as count, SUM(size_bytes) as total_size
                FROM targets
                GROUP BY sender_address
                ORDER BY count DESC
                LIMIT 5;
            """
            cursor.execute(sender_sql, params)
            top_senders = [
                {"address": r[0], "name": r[1] or r[0], "count": r[2], "total_bytes": r[3]}
                for r in cursor.fetchall()
            ]
            
            # 4. Representative samples (up to 10)
            sample_sql = f"""
                WITH targets AS ({base_sql})
                SELECT id, provider_message_id, subject, sender_name, sender_address,
                       received_at, size_bytes, category_name
                FROM targets
                ORDER BY received_at DESC
                LIMIT 10;
            """
            cursor.execute(sample_sql, params)
            samples = [
                {
                    "id": r[0],
                    "provider_message_id": r[1],
                    "subject": r[2],
                    "sender_name": r[3],
                    "sender_address": r[4],
                    "received_at": r[5],
                    "size_bytes": r[6],
                    "category": r[7]
                }
                for r in cursor.fetchall()
            ]
            
            reversibility_notes = {
                "trash": "Reversible: Messages will be moved to the Trash folder and can be restored using the Undo button.",
                "archive": "Reversible: Messages will be archived and can be restored back to Inbox.",
                "label": "Reversible: Labels can be completely removed using the Undo button.",
                "delete": "Warning: Permanent deletion cannot be automatically undone."
            }
            
            return ActionPreview(
                account_id=account_id,
                operation_type=operation_type,
                target_count=target_count,
                affected_threads_count=thread_count,
                total_size_bytes=total_bytes,
                protected_excluded_count=protected_excluded,
                date_range_start=earliest,
                date_range_end=latest,
                top_senders=top_senders,
                samples=samples,
                reversible=operation_type in ("trash", "archive", "label"),
                reversibility_note=reversibility_notes.get(operation_type, "Standard provider operation.")
            )

    def _get_remote_provider(self, account_id: int):
        """Retrieve and initialize live provider for an account if live credentials exist."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, provider, email_address, settings_json FROM accounts WHERE id = ?;", (account_id,))
            acc_row = cursor.fetchone()
            if not acc_row:
                return None
            
            provider_type = acc_row["provider"]
            email_addr = acc_row["email_address"]
            
            if provider_type in ("imap", "gmail"):
                from backend.app.security.credential_store import CredentialStore
                cred_json_str = CredentialStore().get_credentials(email_addr)
                if not cred_json_str:
                    return None
                try:
                    cred = json.loads(cred_json_str)
                    if cred.get("provider") == "imap" or "password" in cred:
                        from backend.app.providers.imap import ImapProvider
                        return ImapProvider(
                            host=cred.get("host", "imap.gmail.com"),
                            username=cred.get("username", email_addr),
                            password=cred.get("password"),
                            port=cred.get("port", 993),
                            use_ssl=cred.get("use_ssl", True)
                        )
                    elif cred.get("provider") == "gmail" or provider_type == "gmail" or "access_token" in cred:
                        from backend.app.providers.gmail import GmailProvider
                        return GmailProvider(account_email=email_addr)
                except Exception as ex:
                    print(f"Failed to initialize remote provider for {email_addr}: {ex}")
            return None

    def execute_action(
        self,
        account_id: int,
        operation_type: str,
        ast: QueryAST,
        label_name: Optional[str] = None,
        batch_id: Optional[str] = None,
        sync_remote: bool = True,
        target_message_ids: Optional[List[int]] = None
    ) -> int:
        """
        Execute the confirmed operation on target messages.
        Returns operation_id.
        """
        if operation_type not in ("trash", "archive", "label"):
            raise ValueError(f"Unsupported operation type '{operation_type}'. Only 'trash', 'archive', and 'label' allowed.")

        if operation_type == "label" and not label_name:
            raise ValueError("label_name is required for 'label' operation.")
            
        ast.account_ids = [account_id]
        # For 'label' operations, protection rules are strictly enforced at execute time
        if operation_type == "label":
            ast.exclude_protected = True
        elif ast.exclude_protected is None:
            ast.exclude_protected = True
        snapshot_dict = {
            "version": ast.version,
            "all": [{"field": c.field, "op": c.op, "value": c.value} for c in ast.all],
            "search_term": ast.search_term,
            "exclude_protected": ast.exclude_protected
        }
        if label_name:
            snapshot_dict["label_name"] = label_name
        if batch_id:
            snapshot_dict["batch_id"] = batch_id
        query_snapshot = json.dumps(snapshot_dict)
        
        with self.db.connect() as conn:
            cursor = conn.cursor()
            
            # Resolve destination folder if trash or archive
            dest_folder_id = None
            if operation_type in ("trash", "archive"):
                dest_folder_type = "trash" if operation_type == "trash" else "archive"
                cursor.execute("""
                    SELECT id FROM folders WHERE account_id = ? AND folder_type = ? LIMIT 1;
                """, (account_id, dest_folder_type))
                dest_row = cursor.fetchone()
                if dest_row:
                    dest_folder_id = dest_row[0]
                else:
                    cursor.execute("""
                        INSERT INTO folders (account_id, provider_folder_id, name, folder_type, is_special)
                        VALUES (?, ?, ?, ?, 1);
                    """, (account_id, dest_folder_type, dest_folder_type.capitalize(), dest_folder_type))
                    dest_folder_id = cursor.lastrowid
                
            # Compile target query to get fresh target IDs
            sql, params = self.compiler.compile_sql(ast, count_only=False)
            cursor.execute(sql, params)
            target_rows = cursor.fetchall()
            if target_message_ids is not None:
                target_ids_set = set(target_message_ids)
                target_rows = [r for r in target_rows if r["id"] in target_ids_set]
            target_count = len(target_rows)
            
            # Record operation
            cursor.execute("""
                INSERT INTO operations (
                    account_id, operation_type, query_snapshot_json,
                    target_count, status, undo_status
                ) VALUES (?, ?, ?, ?, 'running', 'available');
            """, (account_id, operation_type, query_snapshot, target_count))
            operation_id = cursor.lastrowid
            
            completed_count = 0
            failed_count = 0
            
            for r in target_rows:
                msg_id = r["id"]
                orig_folder_id = r["folder_id"]
                pid = r["provider_message_id"] or ""
                
                try:
                    if operation_type == "label":
                        orig_state = "{}"
                        result_state = json.dumps({"added_label": label_name})
                    else:
                        orig_state = json.dumps({"folder_id": orig_folder_id, "is_read": r["is_read"]})
                        result_state = json.dumps({"folder_id": dest_folder_id})
                    
                    # Record item snapshot
                    cursor.execute("""
                        INSERT INTO operation_items (
                            operation_id, message_id, provider_message_id,
                            original_state_json, result_state_json, status
                        ) VALUES (?, ?, ?, ?, ?, 'success');
                    """, (operation_id, msg_id, pid, orig_state, result_state))
                    
                    if operation_type in ("trash", "archive"):
                        # Update message record
                        cursor.execute("""
                            UPDATE messages
                            SET folder_id = ?, updated_at = datetime('now')
                            WHERE id = ?;
                        """, (dest_folder_id, msg_id))
                    
                    completed_count += 1
                except Exception as ex:
                    failed_count += 1
                    cursor.execute("""
                        INSERT INTO operation_items (
                            operation_id, message_id, provider_message_id,
                            original_state_json, status, error_message
                        ) VALUES (?, ?, ?, '{}', 'failed', ?);
                    """, (operation_id, msg_id, pid, str(ex)))
                    
            status = "completed" if failed_count == 0 else "completed_with_errors"
            cursor.execute("""
                UPDATE operations
                SET status = ?,
                    completed_count = ?,
                    failed_count = ?,
                    completed_at = datetime('now')
                WHERE id = ?;
            """, (status, completed_count, failed_count, operation_id))

            # If account is connected to live IMAP/Gmail, execute remote action on mailbox
            if sync_remote:
                remote_provider = self._get_remote_provider(account_id)
                if remote_provider:
                    target_pids = [r["provider_message_id"] for r in target_rows if r["provider_message_id"]]
                    try:
                        if operation_type == "trash":
                            remote_provider.move_to_trash(target_pids)
                        elif operation_type == "archive":
                            remote_provider.archive_messages(target_pids)
                        elif operation_type == "label":
                            remote_provider.apply_labels(target_pids, add_labels=[label_name])
                    except Exception as ex:
                        print(f"Warning: remote mailbox operation failed: {ex}")
                    finally:
                        if hasattr(remote_provider, "disconnect"):
                            remote_provider.disconnect()
            
            return operation_id

    def undo_operation(self, operation_id: int, sync_remote: bool = True) -> Dict[str, Any]:
        """Undo a previously executed operation by restoring original message folder state or removing labels."""
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, account_id, operation_type, status, undo_status FROM operations WHERE id = ?;", (operation_id,))
            op_row = cursor.fetchone()
            if not op_row:
                raise ValueError(f"Operation #{operation_id} not found.")

            account_id = op_row["account_id"]
            op_type = op_row["operation_type"]
                
            cursor.execute("""
                SELECT id, message_id, provider_message_id, original_state_json, result_state_json, status 
                FROM operation_items 
                WHERE operation_id = ? AND status = 'success';
            """, (operation_id,))
            items = cursor.fetchall()
            
            restored_count = 0
            if op_type == "label":
                labels_to_pids: Dict[str, List[str]] = {}
                for item in items:
                    item_id = item["id"]
                    try:
                        res_state = json.loads(item["result_state_json"] or "{}")
                    except Exception:
                        res_state = {}
                    added_label = res_state.get("added_label")
                    pid = item["provider_message_id"]
                    if added_label and pid:
                        labels_to_pids.setdefault(added_label, []).append(pid)

                    cursor.execute("UPDATE operation_items SET status = 'undone' WHERE id = ?;", (item_id,))
                    restored_count += 1

                cursor.execute("""
                    UPDATE operations
                    SET status = 'undone', undo_status = 'restored'
                    WHERE id = ?;
                """, (operation_id,))

                if sync_remote:
                    # Attempt remote label removal on live server if supported
                    remote_provider = self._get_remote_provider(account_id)
                    if remote_provider:
                        try:
                            for added_lbl, pids in labels_to_pids.items():
                                remote_provider.apply_labels(pids, remove_labels=[added_lbl])
                        except Exception as ex:
                            print(f"Warning: remote label removal failed: {ex}")
                        finally:
                            if hasattr(remote_provider, "disconnect"):
                                remote_provider.disconnect()
            else:
                for item in items:
                    item_id = item["id"]
                    message_id = item["message_id"]
                    orig_state = json.loads(item["original_state_json"])
                    orig_folder_id = orig_state.get("folder_id")
                    
                    cursor.execute("""
                        UPDATE messages
                        SET folder_id = ?, updated_at = datetime('now')
                        WHERE id = ?;
                    """, (orig_folder_id, message_id))
                    
                    cursor.execute("UPDATE operation_items SET status = 'undone' WHERE id = ?;", (item_id,))
                    restored_count += 1
                    
                cursor.execute("""
                    UPDATE operations
                    SET status = 'undone', undo_status = 'restored'
                    WHERE id = ?;
                """, (operation_id,))

                if sync_remote:
                    # Attempt remote undo on live server if supported
                    remote_provider = self._get_remote_provider(account_id)
                    if remote_provider and op_type == "trash":
                        try:
                            pids = [r["provider_message_id"] for r in items if r["provider_message_id"]]
                            remote_provider.restore_messages(pids, dest_folder="INBOX")
                        except Exception as ex:
                            print(f"Warning: remote restore failed: {ex}")
                        finally:
                            if hasattr(remote_provider, "disconnect"):
                                remote_provider.disconnect()
            
            return {
                "operation_id": operation_id,
                "status": "undone",
                "restored_count": restored_count
            }
