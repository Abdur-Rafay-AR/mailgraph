"""Attachment intelligence, filtering, duplicate content detection, and local export."""

from fastapi import APIRouter, Depends, HTTPException, Query
import sqlite3
from typing import Optional, List, Dict, Any

from backend.app.db.database import get_db

router = APIRouter(prefix="/api/attachments", tags=["attachments"])

@router.get("")
def list_attachments(
    mime_type: Optional[str] = None,
    min_size: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    conn: sqlite3.Connection = Depends(get_db)
):
    """List and filter attachments independently of messages."""
    cursor = conn.cursor()
    offset = max(0, (page - 1) * page_size)
    
    where_clauses = ["1=1"]
    params: List[Any] = []
    
    if search:
        where_clauses.append("a.filename LIKE ?")
        params.append(f"%{search}%")
    if mime_type:
        where_clauses.append("a.mime_type LIKE ?")
        params.append(f"%{mime_type}%")
    if min_size:
        where_clauses.append("a.size_bytes >= ?")
        params.append(min_size)
        
    where_sql = " AND ".join(where_clauses)
    
    cursor.execute(f"SELECT COUNT(*) FROM attachments a WHERE {where_sql};", params)
    total_count = cursor.fetchone()[0]
    
    cursor.execute(f"""
        SELECT a.id, a.message_id, a.filename, a.mime_type, a.size_bytes, a.content_hash,
               a.is_inline, a.content_available,
               m.subject as message_subject, m.received_at, m.sender_address
        FROM attachments a
        JOIN messages m ON a.message_id = m.id
        WHERE {where_sql}
        ORDER BY a.size_bytes DESC
        LIMIT ? OFFSET ?;
    """, params + [page_size, offset])
    
    items = [
        {
            "id": r["id"],
            "message_id": r["message_id"],
            "filename": r["filename"],
            "mime_type": r["mime_type"],
            "size_bytes": r["size_bytes"],
            "content_hash": r["content_hash"],
            "is_inline": bool(r["is_inline"]),
            "content_available": bool(r["content_available"]),
            "message_subject": r["message_subject"],
            "received_at": r["received_at"],
            "sender_address": r["sender_address"]
        }
        for r in cursor.fetchall()
    ]
    
    return {
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "items": items
    }

@router.get("/duplicates")
def get_duplicate_attachments(conn: sqlite3.Connection = Depends(get_db)):
    """Identify duplicate attachment groups based on cryptographic content hash."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT content_hash, COUNT(*) as file_count, SUM(size_bytes) as total_wasted_bytes,
               MIN(filename) as sample_filename, MIN(size_bytes) as single_size
        FROM attachments
        WHERE content_hash IS NOT NULL AND is_inline = 0
        GROUP BY content_hash
        HAVING file_count > 1
        ORDER BY total_wasted_bytes DESC;
    """)
    groups = []
    for r in cursor.fetchall():
        h = r[0]
        count = r[1]
        total_wasted = r[2]
        sample_name = r[3]
        single_size = r[4]
        
        # Fetch matching references
        cursor.execute("""
            SELECT a.id, a.message_id, a.filename, m.subject, m.received_at, m.sender_address
            FROM attachments a
            JOIN messages m ON a.message_id = m.id
            WHERE a.content_hash = ?;
        """, (h,))
        refs = [
            {
                "attachment_id": ref[0],
                "message_id": ref[1],
                "filename": ref[2],
                "message_subject": ref[3],
                "received_at": ref[4],
                "sender_address": ref[5]
            }
            for ref in cursor.fetchall()
        ]
        
        groups.append({
            "content_hash": h,
            "filename": sample_name,
            "file_size": single_size,
            "duplicate_count": count,
            "total_bytes_occupied": total_wasted,
            "references": refs
        })
        
    return {"duplicate_groups": groups}
