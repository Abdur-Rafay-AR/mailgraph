"""Message querying, details inspection, and CSV export endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response
import sqlite3
from typing import Optional

from backend.app.db.database import get_db, get_database
from backend.app.models.schemas import MessageSearchRequest
from backend.app.search.search_service import SearchService
from backend.app.search.query_compiler import QueryAST, QueryCondition
from backend.app.security.sanitizer import HtmlSanitizer

router = APIRouter(prefix="/api/messages", tags=["messages"])

@router.post("/search")
def search_messages(req: MessageSearchRequest):
    """Execute paginated search with full-text indexing, facets, and filter conditions."""
    db = get_database()
    search_service = SearchService(db)
    
    ast = QueryAST(
        version=req.query.version,
        account_ids=req.query.account_ids,
        all=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.all],
        any=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.any],
        none=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.none],
        search_term=req.query.search_term,
        exclude_protected=req.query.exclude_protected
    )
    
    res = search_service.search(
        ast=ast,
        page=req.page,
        page_size=req.page_size,
        sort_by=req.sort_by,
        sort_dir=req.sort_dir
    )
    
    return {
        "total_count": res.total_count,
        "page": res.page,
        "page_size": res.page_size,
        "items": res.items,
        "facets": res.facets
    }

@router.get("/{message_id}")
def get_message_detail(message_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Retrieve complete message details, sanitized preview HTML, and attachments."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.id, m.account_id, m.provider_message_id, m.provider_thread_id,
               m.folder_id, m.thread_id, m.message_id_header, m.in_reply_to,
               m.references_header, m.subject, m.sender_name, m.sender_address,
               m.sent_at, m.received_at, m.is_read, m.is_starred, m.is_important,
               m.has_attachments, m.size_bytes, m.snippet, m.body_text,
               s.domain as sender_domain,
               c.name as category_name, c.color as category_color,
               mc.confidence as category_confidence, mc.reason as category_reason
        FROM messages m
        LEFT JOIN senders s ON m.sender_id = s.id
        LEFT JOIN message_categories mc ON m.id = mc.message_id
        LEFT JOIN categories c ON mc.category_id = c.id
        WHERE m.id = ?;
    """, (message_id,))
    msg = cursor.fetchone()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    # Get recipients
    cursor.execute("""
        SELECT address, display_name, role FROM message_addresses WHERE message_id = ?;
    """, (message_id,))
    addresses = [
        {"address": r[0], "display_name": r[1], "role": r[2]}
        for r in cursor.fetchall()
    ]
    
    # Get attachments
    cursor.execute("""
        SELECT id, filename, mime_type, size_bytes, content_hash, is_inline, content_available
        FROM attachments WHERE message_id = ?;
    """, (message_id,))
    attachments = [
        {
            "id": r[0],
            "filename": r[1],
            "mime_type": r[2],
            "size_bytes": r[3],
            "content_hash": r[4],
            "is_inline": bool(r[5]),
            "content_available": bool(r[6])
        }
        for r in cursor.fetchall()
    ]
    
    # Generate sanitized HTML preview
    body_text = msg["body_text"] or ""
    # Render basic paragraph formatting for preview if only plaintext exists
    simulated_html = f"<div style='font-family: system-ui, sans-serif; white-space: pre-wrap; line-height: 1.6;'>{body_text}</div>"
    sanitized_preview = HtmlSanitizer.sanitize(simulated_html, allow_remote_images=False)
    
    return {
        "id": msg["id"],
        "account_id": msg["account_id"],
        "provider_message_id": msg["provider_message_id"],
        "folder_id": msg["folder_id"],
        "thread_id": msg["thread_id"],
        "subject": msg["subject"] or "(No Subject)",
        "sender_name": msg["sender_name"],
        "sender_address": msg["sender_address"],
        "sender_domain": msg["sender_domain"],
        "sent_at": msg["sent_at"],
        "received_at": msg["received_at"],
        "is_read": bool(msg["is_read"]),
        "is_starred": bool(msg["is_starred"]),
        "is_important": bool(msg["is_important"]),
        "has_attachments": bool(msg["has_attachments"]),
        "size_bytes": msg["size_bytes"],
        "snippet": msg["snippet"],
        "category": msg["category_name"] or "unknown",
        "category_color": msg["category_color"] or "#64748b",
        "category_reason": msg["category_reason"],
        "addresses": addresses,
        "attachments": attachments,
        "sanitized_html": sanitized_preview,
        "body_text": body_text
    }

@router.post("/export/csv")
def export_messages_csv(req: MessageSearchRequest):
    """Download search results as CSV file."""
    db = get_database()
    search_service = SearchService(db)
    
    ast = QueryAST(
        version=req.query.version,
        account_ids=req.query.account_ids,
        all=[QueryCondition(field=c.field, op=c.op, value=c.value) for c in req.query.all],
        search_term=req.query.search_term,
        exclude_protected=req.query.exclude_protected
    )
    csv_data = search_service.export_csv(ast)
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mailgraph_export.csv"}
    )
