"""Attachment intelligence, filtering, duplicate content detection, and local export."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.db.database import get_db

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.get("")
def list_attachments(
    account_id: Optional[int] = None,
    mime_type: Optional[str] = None,
    min_size: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    conn: sqlite3.Connection = Depends(get_db)
):
    """List and filter attachments independently of messages."""
    cursor = conn.cursor()
    safe_page = max(1, page)
    safe_page_size = max(1, min(500, page_size))
    offset = (safe_page - 1) * safe_page_size

    where_clauses = ["(m.folder_id IS NULL OR m.folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')))"]
    params: List[Any] = []

    if account_id is not None:
        where_clauses.append("m.account_id = ?")
        params.append(account_id)
    else:
        where_clauses.append("m.account_id IN (SELECT id FROM accounts WHERE status != 'paused')")

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

    cursor.execute(f"SELECT COUNT(*) FROM attachments a JOIN messages m ON a.message_id = m.id WHERE {where_sql};", params)
    total_count = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT a.id, a.message_id, a.filename, a.mime_type, a.size_bytes, a.content_hash,
               a.is_inline, a.content_available, a.local_path,
               m.subject as message_subject, m.received_at, m.sender_address
        FROM attachments a
        JOIN messages m ON a.message_id = m.id
        WHERE {where_sql}
        ORDER BY a.size_bytes DESC
        LIMIT ? OFFSET ?;
    """, params + [safe_page_size, offset])

    items = [
        {
            "id": r["id"],
            "message_id": r["message_id"],
            "filename": r["filename"],
            "mime_type": r["mime_type"],
            "size_bytes": r["size_bytes"],
            "content_hash": r["content_hash"],
            "is_inline": bool(r["is_inline"]),
            "content_available": bool(r["content_available"]) and bool(r["local_path"]),
            "message_subject": r["message_subject"],
            "received_at": r["received_at"],
            "sender_address": r["sender_address"]
        }
        for r in cursor.fetchall()
    ]

    return {
        "total_count": total_count,
        "page": safe_page,
        "page_size": safe_page_size,
        "items": items
    }


@router.get("/duplicates")
def get_duplicate_attachments(
    account_id: Optional[int] = None,
    conn: sqlite3.Connection = Depends(get_db)
):
    """Identify duplicate attachment groups based on cryptographic content hash in two queries."""
    cursor = conn.cursor()

    params: List[Any] = []
    acc_filter = "AND (m.folder_id IS NULL OR m.folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam')))"
    if account_id is not None:
        acc_filter += " AND m.account_id = ?"
        params.append(account_id)
    else:
        acc_filter += " AND m.account_id IN (SELECT id FROM accounts WHERE status != 'paused')"

    cursor.execute(f"""
        SELECT a.content_hash, COUNT(*) as file_count, SUM(a.size_bytes) as total_wasted_bytes,
               MIN(a.filename) as sample_filename, MIN(a.size_bytes) as single_size
        FROM attachments a
        JOIN messages m ON a.message_id = m.id
        WHERE a.content_hash IS NOT NULL AND a.is_inline = 0 {acc_filter}
        GROUP BY a.content_hash
        HAVING file_count > 1
        ORDER BY total_wasted_bytes DESC;
    """, params)
    group_rows = cursor.fetchall()
    if not group_rows:
        return {"duplicate_groups": []}

    hashes = [r[0] for r in group_rows]
    hash_placeholders = ", ".join("?" for _ in hashes)
    cursor.execute(f"""
        SELECT a.content_hash, a.id, a.message_id, a.filename, m.subject, m.received_at, m.sender_address
        FROM attachments a
        JOIN messages m ON a.message_id = m.id
        WHERE a.content_hash IN ({hash_placeholders}) AND a.is_inline = 0 {acc_filter}
        ORDER BY m.received_at DESC;
    """, hashes + params)

    refs_by_hash: Dict[str, List[Dict[str, Any]]] = {}
    for ref in cursor.fetchall():
        refs_by_hash.setdefault(ref[0], []).append({
            "attachment_id": ref[1],
            "message_id": ref[2],
            "filename": ref[3],
            "message_subject": ref[4],
            "received_at": ref[5],
            "sender_address": ref[6]
        })

    groups = [
        {
            "content_hash": r[0],
            "filename": r[3],
            "file_size": r[4],
            "duplicate_count": r[1],
            "total_bytes_occupied": r[2],
            "references": refs_by_hash.get(r[0], [])
        }
        for r in group_rows
    ]

    return {"duplicate_groups": groups}


@router.get("/{attachment_id}/download")
def download_attachment(attachment_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Download a locally cached attachment file if available within the MailGraph data directory."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT filename, mime_type, local_path FROM attachments WHERE id = ?;",
        (attachment_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")

    local_path = row["local_path"]
    if not local_path:
        raise HTTPException(status_code=404, detail="Attachment content is not stored locally")

    resolved_file = Path(local_path).resolve()
    resolved_data_dir = Path(settings.data_dir).resolve()
    if resolved_data_dir not in resolved_file.parents or not resolved_file.is_file():
        raise HTTPException(status_code=404, detail="Attachment file missing or inaccessible")

    return FileResponse(
        path=str(resolved_file),
        media_type=row["mime_type"] or "application/octet-stream",
        filename=row["filename"] or "attachment.bin",
    )
