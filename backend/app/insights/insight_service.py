"""Deterministic insights generator for mailbox intelligence and cleanup opportunities."""

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.app.db.database import Database


@dataclass
class GeneratedInsight:
    insight_type: str
    title: str
    description: str
    evidence: Dict[str, Any]
    confidence: float


class InsightService:
    """Analyzes the local mailbox model to produce explainable, actionable insights."""

    _ACTIVE_FOLDER_SQL = (
        "(m.folder_id IS NULL OR m.folder_id NOT IN "
        "(SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')))"
    )

    def __init__(self, db: Database):
        self.db = db

    def generate_insights(self, account_id: Optional[int] = None) -> List[GeneratedInsight]:
        """Compute all insights deterministically from the database without creating duplicates."""
        insights: List[GeneratedInsight] = []

        with self.db.connect() as conn:
            cursor = conn.cursor()

            self._detect_storage_dominators(cursor, account_id, insights)
            self._detect_zombie_subscriptions(cursor, account_id, insights)
            self._detect_large_attachments(cursor, account_id, insights)
            self._detect_unreplied_threads(cursor, account_id, insights)

            for ins in insights:
                ev_json = json.dumps(ins.evidence)
                # Insert if not already present (unique index covers COALESCE(account_id, -1), insight_type, title)
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO insights (
                        account_id, insight_type, title, description, evidence_json, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (account_id, ins.insight_type, ins.title, ins.description, ev_json, ins.confidence),
                )
                # Refresh active (non-dismissed) insight metrics if it already existed
                cursor.execute(
                    """
                    UPDATE insights
                    SET description = ?, evidence_json = ?, confidence = ?
                    WHERE COALESCE(account_id, -1) = COALESCE(?, -1)
                      AND insight_type = ?
                      AND title = ?
                      AND dismissed_at IS NULL;
                    """,
                    (ins.description, ev_json, ins.confidence, account_id, ins.insight_type, ins.title),
                )

        return insights

    def _scope_clause(self, account_id: Optional[int], alias: str = "m") -> tuple[str, tuple]:
        clauses = [self._ACTIVE_FOLDER_SQL.replace("m.", f"{alias}.")]
        params: tuple = ()
        if account_id is not None:
            clauses.append(f"{alias}.account_id = ?")
            params = (account_id,)
        else:
            clauses.append(f"{alias}.account_id IN (SELECT id FROM accounts WHERE status != 'paused')")
        return " AND ".join(clauses), params

    def _detect_storage_dominators(self, cursor: sqlite3.Cursor, account_id: Optional[int], insights: List[GeneratedInsight]) -> None:
        scope_sql, params = self._scope_clause(account_id, "m")
        cursor.execute(f"""
            SELECT m.sender_address, m.sender_name, SUM(m.size_bytes) as total_bytes, COUNT(*) as msg_count
            FROM messages m
            WHERE {scope_sql}
            GROUP BY m.sender_address
            HAVING total_bytes > 500000
            ORDER BY total_bytes DESC
            LIMIT 5;
        """, params)

        for row in cursor.fetchall():
            addr, name, total_bytes, count = row[0], row[1], row[2], row[3]
            mb = total_bytes / (1024 * 1024)
            name_display = name or addr
            insights.append(GeneratedInsight(
                insight_type="storage_dominator",
                title=f"Storage dominator: {name_display}",
                description=f"{count} messages from {addr} occupy {mb:.2f} MB of local storage.",
                evidence={"sender_address": addr, "total_bytes": total_bytes, "message_count": count},
                confidence=0.95
            ))

    def _detect_zombie_subscriptions(self, cursor: sqlite3.Cursor, account_id: Optional[int], insights: List[GeneratedInsight]) -> None:
        scope_sql, params = self._scope_clause(account_id, "m")
        cursor.execute(f"""
            SELECT s.normalized_address, s.display_name, COUNT(m.id) as msg_count,
                   SUM(CASE WHEN m.is_starred = 1 THEN 1 ELSE 0 END) as starred_count
            FROM senders s
            JOIN messages m ON s.id = m.sender_id
            JOIN message_categories mc ON m.id = mc.message_id
            JOIN categories c ON mc.category_id = c.id
            WHERE c.name IN ('newsletter', 'promotional', 'notification')
              AND {scope_sql}
            GROUP BY s.id
            HAVING msg_count >= 3 AND starred_count = 0
            ORDER BY msg_count DESC
            LIMIT 5;
        """, params)

        for row in cursor.fetchall():
            addr, name, count, starred = row[0], row[1], row[2], row[3]
            name_display = name or addr
            insights.append(GeneratedInsight(
                insight_type="zombie_subscription",
                title=f"Inactive subscription: {name_display}",
                description=f"Received {count} messages from {addr} without stars or favorites. Good candidate for review.",
                evidence={"sender_address": addr, "message_count": count, "starred_count": starred},
                confidence=0.88
            ))

    def _detect_large_attachments(self, cursor: sqlite3.Cursor, account_id: Optional[int], insights: List[GeneratedInsight]) -> None:
        scope_sql, params = self._scope_clause(account_id, "m")
        cursor.execute(f"""
            SELECT COUNT(a.id) as count, COALESCE(SUM(a.size_bytes), 0) as total_bytes
            FROM attachments a
            JOIN messages m ON a.message_id = m.id
            WHERE {scope_sql}
              AND a.size_bytes > 500000;
        """, params)

        row = cursor.fetchone()
        if row and row[0] and row[0] > 0:
            count, total_bytes = row[0], row[1]
            mb = total_bytes / (1024 * 1024)
            insights.append(GeneratedInsight(
                insight_type="large_attachments",
                title="Large attachments archive",
                description=f"{count} files larger than 500 KB consume {mb:.2f} MB in total.",
                evidence={"attachment_count": count, "total_bytes": total_bytes},
                confidence=0.90
            ))

    def _detect_unreplied_threads(self, cursor: sqlite3.Cursor, account_id: Optional[int], insights: List[GeneratedInsight]) -> None:
        scope_sql, params = self._scope_clause(account_id, "m")
        cursor.execute(f"""
            SELECT m.id, m.subject, m.sender_name, m.sender_address, m.received_at
            FROM messages m
            JOIN message_categories mc ON m.id = mc.message_id
            JOIN categories c ON mc.category_id = c.id
            LEFT JOIN threads t ON m.thread_id = t.id
            WHERE {scope_sql}
              AND c.name IN ('work', 'personal', 'important')
              AND m.in_reply_to IS NULL
              AND (t.id IS NULL OR t.message_count = 1)
            ORDER BY m.received_at DESC
            LIMIT 3;
        """, params)

        for row in cursor.fetchall():
            mid, subj, name, addr, rec_at = row[0], row[1], row[2], row[3], row[4]
            name_display = name or addr
            insights.append(GeneratedInsight(
                insight_type="unreplied_thread",
                title=f"Awaiting reply: {name_display}",
                description=f"Initial message '{subj}' from {name_display} has no recorded reply.",
                evidence={"message_id": mid, "subject": subj, "sender_address": addr, "received_at": rec_at},
                confidence=0.82
            ))
