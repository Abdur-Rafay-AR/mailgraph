"""Category label synchronization service for mapping local email classifications to provider labels."""

import json
import uuid
from typing import Dict, Any, List, Optional
from backend.app.db.database import Database
from backend.app.search.query_compiler import QueryAST, QueryCondition
from backend.app.actions.engine import ActionEngine

CATEGORY_GMAIL_LABEL_MAP: Dict[str, str] = {
    "finance": "MailGraph/Finance",
    "security": "MailGraph/Security",
    "receipt_invoice": "MailGraph/Receipts",
    "newsletter": "MailGraph/Newsletters",
    "promotional": "MailGraph/Promotional",
    "work": "MailGraph/Work",
    "personal": "MailGraph/Personal",
    "university": "MailGraph/University",
    "social": "MailGraph/Social",
    "calendar": "MailGraph/Calendar",
    "notification": "MailGraph/Notifications",
    "automated_report": "MailGraph/Reports",
    "cold_outreach": "MailGraph/Cold Outreach",
}


def get_label_for_category(category: str) -> str:
    """Return the designated Gmail/provider label name for a given category."""
    if category in CATEGORY_GMAIL_LABEL_MAP:
        return CATEGORY_GMAIL_LABEL_MAP[category]
    return f"MailGraph/{category.capitalize()}"


class CategoryLabelSyncService:
    """Manages preview, execution, and granular rollback of category-to-label synchronization."""

    def __init__(self, db: Database, action_engine: Optional[ActionEngine] = None):
        self.db = db
        self.action_engine = action_engine or ActionEngine(db)

    def preview_sync(self, account_id: int) -> Dict[str, Any]:
        """
        Calculate preview counts of messages grouped by category for an account.
        Enforces protection rules and excludes trash/spam folders.
        """
        query = """
            SELECT c.name, COUNT(DISTINCT m.id) as cnt
            FROM message_categories mc
            JOIN categories c ON mc.category_id = c.id
            JOIN messages m ON mc.message_id = m.id
            LEFT JOIN senders s ON m.sender_id = s.id
            WHERE m.account_id = ?
              AND (m.folder_id IS NULL OR m.folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')))
              AND (
                  (m.sender_id IS NULL OR m.sender_id NOT IN (SELECT id FROM senders WHERE is_protected = 1))
                  AND m.sender_address NOT IN (SELECT rule_value FROM protection_rules WHERE rule_type = 'sender' AND enabled = 1)
                  AND NOT EXISTS (
                      SELECT 1 FROM protection_rules pr
                      WHERE pr.rule_type = 'domain' AND pr.enabled = 1
                      AND (m.sender_address LIKE '%@' || pr.rule_value OR m.sender_address LIKE '%.' || pr.rule_value)
                  )
                  AND m.is_starred = 0
                  AND m.is_important = 0
              )
            GROUP BY c.name
            ORDER BY cnt DESC, c.name ASC;
        """
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (account_id,))
            rows = cursor.fetchall()

        categories_breakdown = []
        total_messages = 0

        for r in rows:
            cat_name = r["name"]
            cnt = r["cnt"]
            if cnt > 0:
                categories_breakdown.append({
                    "category": cat_name,
                    "label": get_label_for_category(cat_name),
                    "count": cnt
                })
                total_messages += cnt

        return {
            "account_id": account_id,
            "total_messages": total_messages,
            "categories": categories_breakdown
        }

    def execute_sync(
        self,
        account_id: int,
        categories: Optional[List[str]] = None,
        batch_id: Optional[str] = None,
        sync_remote: bool = True
    ) -> Dict[str, Any]:
        """
        Execute label sync for specified categories (or all eligible categories if None).
        Creates distinct operations linked by batch_id.
        """
        batch_id = batch_id or str(uuid.uuid4())

        if categories is None:
            preview = self.preview_sync(account_id)
            target_categories = [c["category"] for c in preview["categories"] if c["count"] > 0]
        else:
            target_categories = categories

        op_ids: List[int] = []
        total_labeled = 0

        for cat in target_categories:
            target_label = get_label_for_category(cat)
            ast = QueryAST(
                version=1,
                account_ids=[account_id],
                all=[QueryCondition(field="category", op="eq", value=cat)],
                exclude_protected=True
            )

            # Check candidate messages and exclude those already successfully labeled with target_label
            sql, params = self.action_engine.compiler.compile_sql(ast, count_only=False)
            with self.db.connect() as conn:
                candidate_rows = conn.execute(sql, params).fetchall()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT oi.message_id
                    FROM operation_items oi
                    JOIN operations o ON oi.operation_id = o.id
                    WHERE o.account_id = ?
                      AND o.operation_type = 'label'
                      AND o.status != 'undone'
                      AND oi.status = 'success'
                      AND json_extract(oi.result_state_json, '$.added_label') = ?;
                """, (account_id, target_label))
                already_labeled_ids = {row[0] for row in cursor.fetchall()}

            unlabeled_ids = [r["id"] for r in candidate_rows if r["id"] not in already_labeled_ids]
            if not unlabeled_ids:
                # All messages in this category are already labeled with target_label; skip operation creation
                continue

            op_id = self.action_engine.execute_action(
                account_id=account_id,
                operation_type="label",
                ast=ast,
                label_name=target_label,
                batch_id=batch_id,
                sync_remote=sync_remote,
                target_message_ids=unlabeled_ids
            )

            with self.db.connect() as conn:
                row = conn.execute("SELECT completed_count FROM operations WHERE id = ?;", (op_id,)).fetchone()
                completed = row["completed_count"] if row else 0

            if completed > 0:
                op_ids.append(op_id)
                total_labeled += completed

        return {
            "batch_id": batch_id,
            "operation_ids": op_ids,
            "labeled_count": total_labeled
        }

    def undo_batch(self, batch_id: str, sync_remote: bool = True) -> Dict[str, Any]:
        """
        Undo all operations linked to a specific batch_id by removing applied labels.
        """
        with self.db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, query_snapshot_json, status
                FROM operations
                WHERE query_snapshot_json LIKE '%' || ? || '%'
                ORDER BY id ASC;
            """, (batch_id,))
            rows = cursor.fetchall()

        matching_op_ids: List[int] = []
        for r in rows:
            try:
                snapshot = json.loads(r["query_snapshot_json"] or "{}")
                if snapshot.get("batch_id") == batch_id and r["status"] != "undone":
                    matching_op_ids.append(r["id"])
            except Exception:
                continue

        undone_ops: List[int] = []
        for op_id in matching_op_ids:
            self.action_engine.undo_operation(op_id, sync_remote=sync_remote)
            undone_ops.append(op_id)

        return {
            "batch_id": batch_id,
            "undone_count": len(undone_ops),
            "operation_ids": undone_ops
        }
