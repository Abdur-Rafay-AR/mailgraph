"""Safe cleanup operations, simulation previews, audit logging, and undo endpoints."""

import json
from fastapi import APIRouter, Depends, HTTPException
import sqlite3
from typing import List, Dict, Any

from backend.app.db.database import get_db, get_database
from backend.app.models.schemas import CleanupPreviewRequest, CleanupExecuteRequest, CleanupUndoRequest
from backend.app.search.query_compiler import QueryAST, QueryCondition
from backend.app.actions.engine import ActionEngine

router = APIRouter(prefix="/api/cleanup", tags=["cleanup"])

@router.post("/preview")
def calculate_cleanup_preview(req: CleanupPreviewRequest):
    """Calculate exact simulation preview for a prospective bulk operation."""
    db = get_database()
    account_id = req.account_id
    if not account_id:
        with db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM accounts LIMIT 1;")
            acc = cursor.fetchone()
            account_id = acc[0] if acc else 1
        
    engine = ActionEngine(db)
    
    ast = QueryAST(
        version=req.query.version,
        all=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.all],
        any=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.any],
        none=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.none],
        search_term=req.query.search_term,
        exclude_protected=req.query.exclude_protected
    )
    
    preview = engine.calculate_preview(account_id, req.operation_type, ast)
    return {
        "operation_type": preview.operation_type,
        "account_id": preview.account_id,
        "target_count": preview.target_count,
        "affected_threads_count": preview.affected_threads_count,
        "total_size_bytes": preview.total_size_bytes,
        "protected_excluded_count": preview.protected_excluded_count,
        "date_range_start": preview.date_range_start,
        "date_range_end": preview.date_range_end,
        "top_senders": preview.top_senders,
        "samples": preview.samples,
        "reversible": preview.reversible,
        "reversibility_note": preview.reversibility_note
    }

@router.post("/execute")
def execute_cleanup(req: CleanupExecuteRequest):
    """Execute confirmed cleanup operation with full audit snapshotting."""
    db = get_database()
    account_id = req.account_id
    if not account_id:
        with db.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM accounts LIMIT 1;")
            acc = cursor.fetchone()
            account_id = acc[0] if acc else 1
        
    engine = ActionEngine(db)
    
    ast = QueryAST(
        version=req.query.version,
        all=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.all],
        any=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.any],
        none=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.none],
        search_term=req.query.search_term,
        exclude_protected=req.query.exclude_protected
    )
    
    op_id = engine.execute_action(account_id, req.operation_type, ast)
    
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, operation_type, target_count, completed_count, failed_count, status, created_at, undo_status
            FROM operations WHERE id = ?;
        """, (op_id,))
        row = cursor.fetchone()
    
    return {
        "operation_id": row["id"],
        "operation_type": row["operation_type"],
        "target_count": row["target_count"],
        "completed_count": row["completed_count"],
        "failed_count": row["failed_count"],
        "status": row["status"],
        "created_at": row["created_at"],
        "undo_status": row["undo_status"]
    }

@router.post("/undo")
def undo_cleanup(req: CleanupUndoRequest):
    """Restore messages from a previous bulk operation."""
    db = get_database()
    engine = ActionEngine(db)
    return engine.undo_operation(req.operation_id)

@router.get("/operations")
def list_operations(conn: sqlite3.Connection = Depends(get_db)):
    """Retrieve audit history of all past cleanup operations."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, account_id, operation_type, query_snapshot_json, target_count,
               completed_count, failed_count, status, created_at, completed_at, undo_status
        FROM operations
        ORDER BY id DESC
        LIMIT 50;
    """)
    rows = cursor.fetchall()
    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "account_id": r["account_id"],
            "operation_type": r["operation_type"],
            "target_count": r["target_count"],
            "completed_count": r["completed_count"],
            "failed_count": r["failed_count"],
            "status": r["status"],
            "created_at": r["created_at"],
            "completed_at": r["completed_at"],
            "undo_status": r["undo_status"]
        })
    return items
