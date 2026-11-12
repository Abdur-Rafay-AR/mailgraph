"""Dedicated sender management endpoints: browsing, searching, volume ranking, protection, and bulk cleanup."""

from fastapi import APIRouter, Depends, HTTPException, Query
import sqlite3
from typing import List, Optional, Dict, Any

from backend.app.db.database import get_db, get_database
from backend.app.models.schemas import SenderProtectRequest, BulkSenderCleanupRequest
from backend.app.search.query_compiler import QueryAST, QueryCondition
from backend.app.actions.engine import ActionEngine

router = APIRouter(prefix="/api/senders", tags=["senders"])

@router.get("")
def list_senders(
    search: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    is_protected: Optional[bool] = None,
    sort_by: str = Query("message_count", pattern="^(message_count|total_bytes|unread_count|last_seen_at|normalized_address)$"),
    sort_dir: str = Query("DESC", pattern="^(ASC|DESC|asc|desc)$"),
    page: int = 1,
    page_size: int = 50,
    conn: sqlite3.Connection = Depends(get_db)
):
    """List and rank senders by volume, storage contribution, unread count, and activity."""
    cursor = conn.cursor()
    offset = max(0, (page - 1) * page_size)
    order_dir = sort_dir.upper()
    
    where_clauses = ["1=1"]
    params: List[Any] = []
    
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        where_clauses.append("(s.normalized_address LIKE ? OR s.display_name LIKE ? OR s.domain LIKE ?)")
        params.extend([term, term, term])
        
    if domain:
        where_clauses.append("s.domain = ?")
        params.append(domain.lower())
        
    if is_protected is not None:
        where_clauses.append("s.is_protected = ?")
        params.append(1 if is_protected else 0)
        
    if category:
        where_clauses.append("EXISTS (SELECT 1 FROM messages m2 JOIN message_categories mc ON m2.id = mc.message_id JOIN categories c ON mc.category_id = c.id WHERE m2.sender_id = s.id AND c.name = ?)")
        params.append(category)
        
    where_sql = " AND ".join(where_clauses)
    active_folder_filter = "(m.folder_id IS NULL OR m.folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')))"
    
    # Total active senders count (only senders with active non-trash messages)
    count_sql = f"""
        SELECT COUNT(DISTINCT s.id) 
        FROM senders s 
        JOIN messages m ON s.id = m.sender_id AND {active_folder_filter}
        WHERE {where_sql};
    """
    cursor.execute(count_sql, params)
    total_count = cursor.fetchone()[0]
    
    # Query aggregated active sender metrics
    data_sql = f"""
        SELECT 
            s.id,
            s.normalized_address,
            s.display_name,
            s.domain,
            s.first_seen_at,
            s.last_seen_at,
            s.is_protected,
            COUNT(m.id) as message_count,
            COALESCE(SUM(m.size_bytes), 0) as total_bytes,
            COALESCE(SUM(CASE WHEN m.is_read = 0 THEN 1 ELSE 0 END), 0) as unread_count,
            (
                SELECT c.name FROM message_categories mc2
                JOIN categories c ON mc2.category_id = c.id
                JOIN messages m3 ON mc2.message_id = m3.id
                WHERE m3.sender_id = s.id AND (m3.folder_id IS NULL OR m3.folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')))
                GROUP BY c.id
                ORDER BY COUNT(*) DESC
                LIMIT 1
            ) as dominant_category
        FROM senders s
        JOIN messages m ON s.id = m.sender_id AND {active_folder_filter}
        WHERE {where_sql}
        GROUP BY s.id
        HAVING message_count > 0
        ORDER BY {sort_by} {order_dir}
        LIMIT ? OFFSET ?;
    """
    data_params = list(params) + [page_size, offset]
    cursor.execute(data_sql, data_params)
    rows = cursor.fetchall()
    
    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "normalized_address": r["normalized_address"],
            "display_name": r["display_name"] or r["normalized_address"].split("@")[0],
            "domain": r["domain"],
            "first_seen_at": r["first_seen_at"],
            "last_seen_at": r["last_seen_at"],
            "is_protected": bool(r["is_protected"]),
            "message_count": r["message_count"],
            "total_bytes": r["total_bytes"],
            "unread_count": r["unread_count"],
            "category": r["dominant_category"] or "unknown"
        })
        
    return {
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "items": items
    }

@router.get("/{sender_id}")
def get_sender_detail(sender_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Retrieve detailed sender profile, category distribution, and recent messages."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, normalized_address, display_name, domain, first_seen_at, last_seen_at, is_protected, notes
        FROM senders WHERE id = ?;
    """, (sender_id,))
    sender = cursor.fetchone()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
        
    cursor.execute("""
        SELECT COUNT(id) as count, COALESCE(SUM(size_bytes), 0) as total_size,
               COALESCE(SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END), 0) as unread
        FROM messages 
        WHERE sender_id = ? AND (folder_id IS NULL OR folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')));
    """, (sender_id,))
    stats = cursor.fetchone()
    
    cursor.execute("""
        SELECT id, subject, received_at, size_bytes, is_read, is_starred
        FROM messages 
        WHERE sender_id = ? AND (folder_id IS NULL OR folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')))
        ORDER BY received_at DESC LIMIT 20;
    """, (sender_id,))
    recent_messages = [
        {
            "id": r["id"],
            "subject": r["subject"],
            "received_at": r["received_at"],
            "size_bytes": r["size_bytes"],
            "is_read": bool(r["is_read"]),
            "is_starred": bool(r["is_starred"])
        }
        for r in cursor.fetchall()
    ]
    
    return {
        "id": sender["id"],
        "normalized_address": sender["normalized_address"],
        "display_name": sender["display_name"],
        "domain": sender["domain"],
        "is_protected": bool(sender["is_protected"]),
        "notes": sender["notes"],
        "message_count": stats["count"],
        "total_bytes": stats["total_size"],
        "unread_count": stats["unread"],
        "recent_messages": recent_messages
    }

@router.post("/{sender_id}/protect")
def set_sender_protection(sender_id: int, req: SenderProtectRequest, conn: sqlite3.Connection = Depends(get_db)):
    """Protect or unprotect a sender from bulk cleanup operations."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, normalized_address FROM senders WHERE id = ?;", (sender_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sender not found")
        
    cursor.execute("UPDATE senders SET is_protected = ? WHERE id = ?;", (1 if req.is_protected else 0, sender_id))
    
    # Also synchronize with protection_rules table
    addr = row["normalized_address"]
    if req.is_protected:
        cursor.execute("""
            INSERT OR IGNORE INTO protection_rules (account_id, rule_type, rule_value, reason, enabled)
            SELECT NULL, 'sender', ?, 'User protected sender', 1
            WHERE NOT EXISTS (SELECT 1 FROM protection_rules WHERE rule_type = 'sender' AND rule_value = ?);
        """, (addr, addr))
    else:
        cursor.execute("DELETE FROM protection_rules WHERE rule_type = 'sender' AND rule_value = ?;", (addr,))
        
    return {"id": sender_id, "is_protected": req.is_protected}

@router.post("/bulk-cleanup-preview")
def bulk_cleanup_senders_preview(req: BulkSenderCleanupRequest):
    """Generate exact simulation preview for one or multiple selected senders."""
    if not req.sender_ids:
        raise HTTPException(status_code=400, detail="At least one sender ID must be specified.")
        
    db = get_database()
    with db.connect() as conn:
        cursor = conn.cursor()
        placeholders = ", ".join("?" for _ in req.sender_ids)
        cursor.execute(f"SELECT normalized_address FROM senders WHERE id IN ({placeholders});", req.sender_ids)
        addresses = [r[0] for r in cursor.fetchall()]
        
        cursor.execute(f"""
            SELECT DISTINCT account_id FROM messages 
            WHERE sender_id IN ({placeholders}) 
              AND (folder_id IS NULL OR folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')));
        """, req.sender_ids)
        acc_rows = cursor.fetchall()
        target_account_ids = [r[0] for r in acc_rows if r[0] is not None]
        if not target_account_ids:
            cursor.execute("SELECT id FROM accounts ORDER BY id DESC LIMIT 1;")
            acc_row = cursor.fetchone()
            target_account_ids = [acc_row[0]] if acc_row else [1]
    
    if not addresses:
        raise HTTPException(status_code=404, detail="None of the specified senders were found.")
        
    engine = ActionEngine(db)
    
    ast = QueryAST(
        version=1,
        all=[QueryCondition(field="sender_address", op="in", value=addresses)],
        exclude_protected=req.exclude_protected
    )
    
    target_count = 0
    affected_threads_count = 0
    total_size_bytes = 0
    protected_excluded_count = 0
    all_top_senders = []
    all_samples = []
    reversible = True
    reversibility_note = ""

    for acc_id in target_account_ids:
        preview = engine.calculate_preview(acc_id, req.operation_type, ast)
        target_count += preview.target_count
        affected_threads_count += preview.affected_threads_count
        total_size_bytes += preview.total_size_bytes
        protected_excluded_count += preview.protected_excluded_count
        all_top_senders.extend(preview.top_senders)
        all_samples.extend(preview.samples)
        reversible = preview.reversible
        reversibility_note = preview.reversibility_note

    return {
        "operation_type": req.operation_type,
        "selected_sender_count": len(addresses),
        "target_count": target_count,
        "affected_threads_count": affected_threads_count,
        "total_size_bytes": total_size_bytes,
        "protected_excluded_count": protected_excluded_count,
        "top_senders": all_top_senders[:5],
        "samples": all_samples[:10],
        "reversible": reversible,
        "reversibility_note": reversibility_note,
        "compiled_ast": {
            "all": [{"field": "sender_address", "op": "in", "value": addresses}],
            "exclude_protected": req.exclude_protected
        }
    }

@router.post("/bulk-cleanup-execute")
def bulk_cleanup_senders_execute(req: BulkSenderCleanupRequest):
    """Execute confirmed cleanup on one or multiple selected senders."""
    db = get_database()
    with db.connect() as conn:
        cursor = conn.cursor()
        placeholders = ", ".join("?" for _ in req.sender_ids)
        cursor.execute(f"SELECT normalized_address FROM senders WHERE id IN ({placeholders});", req.sender_ids)
        addresses = [r[0] for r in cursor.fetchall()]
        
        cursor.execute(f"""
            SELECT DISTINCT account_id FROM messages 
            WHERE sender_id IN ({placeholders}) 
              AND (folder_id IS NULL OR folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')));
        """, req.sender_ids)
        acc_rows = cursor.fetchall()
        target_account_ids = [r[0] for r in acc_rows if r[0] is not None]
        if not target_account_ids:
            cursor.execute("SELECT id FROM accounts ORDER BY id DESC LIMIT 1;")
            acc_row = cursor.fetchone()
            target_account_ids = [acc_row[0]] if acc_row else [1]
    
    if not addresses:
        raise HTTPException(status_code=404, detail="No matching senders.")
        
    engine = ActionEngine(db)
    
    ast = QueryAST(
        version=1,
        all=[QueryCondition(field="sender_address", op="in", value=addresses)],
        exclude_protected=req.exclude_protected
    )
    
    last_op_id = None
    for acc_id in target_account_ids:
        last_op_id = engine.execute_action(acc_id, req.operation_type, ast)
        
    return {"status": "completed", "operation_id": last_op_id}
