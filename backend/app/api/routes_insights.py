"""Explainable 'What am I missing?' insights endpoints."""

from fastapi import APIRouter, Depends, HTTPException
import sqlite3
import json
from typing import Optional

from backend.app.db.database import get_db, get_database
from backend.app.insights.insight_service import InsightService

router = APIRouter(prefix="/api/insights", tags=["insights"])

@router.get("")
def list_insights(account_id: Optional[int] = None, conn: sqlite3.Connection = Depends(get_db)):
    """Retrieve actionable, explainable insights with evidence links."""
    db = get_database()
    service = InsightService(db)
    service.generate_insights(account_id=account_id)

    cursor = conn.cursor()
    if account_id is not None:
        cursor.execute(
            """
            SELECT id, account_id, insight_type, title, description, evidence_json, confidence, created_at
            FROM insights
            WHERE dismissed_at IS NULL AND account_id = ?
            ORDER BY id DESC;
            """,
            (account_id,),
        )
    else:
        cursor.execute(
            """
            SELECT id, account_id, insight_type, title, description, evidence_json, confidence, created_at
            FROM insights
            WHERE dismissed_at IS NULL AND account_id IS NULL
            ORDER BY id DESC;
            """
        )
    rows = cursor.fetchall()

    return [
        {
            "id": r["id"],
            "account_id": r["account_id"],
            "insight_type": r["insight_type"],
            "title": r["title"],
            "description": r["description"],
            "evidence": json.loads(r["evidence_json"] or "{}"),
            "confidence": r["confidence"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.post("/{insight_id}/dismiss")
def dismiss_insight(insight_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Dismiss a recommendation."""
    cursor = conn.cursor()
    cursor.execute("UPDATE insights SET dismissed_at = datetime('now') WHERE id = ?;", (insight_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Insight not found")
    return {"status": "dismissed", "insight_id": insight_id}
