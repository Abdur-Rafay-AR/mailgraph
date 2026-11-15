"""Mailbox Time Machine analytics: volume histograms, sender trends, and subscription lifecycles."""

from fastapi import APIRouter, Depends, Query
import sqlite3
from typing import Optional, List, Dict, Any

from backend.app.db.database import get_db

router = APIRouter(prefix="/api/timeline", tags=["timeline"])

@router.get("/volume")
def get_volume_timeline(
    group_by: str = Query("month", pattern="^(year|month|day)$"),
    limit: Optional[int] = None,
    conn: sqlite3.Connection = Depends(get_db)
):
    """Calculate message volume and storage trend grouped by time interval."""
    cursor = conn.cursor()
    
    fmt = "%Y-%m"
    if group_by == "year":
        fmt = "%Y"
    elif group_by == "day":
        fmt = "%Y-%m-%d"
        
    order_clause = "DESC" if limit else "ASC"
    query = f"""
        SELECT 
            strftime('{fmt}', received_at) as period,
            COUNT(*) as message_count,
            COALESCE(SUM(size_bytes), 0) as total_bytes,
            COALESCE(SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END), 0) as unread_count
        FROM messages
        WHERE received_at IS NOT NULL
        GROUP BY period
        ORDER BY period {order_clause}
    """
    if limit and limit > 0:
        query += f" LIMIT {int(limit)}"
        
    cursor.execute(query)
    rows = cursor.fetchall()
    
    if limit and limit > 0:
        rows = list(reversed(rows))
        
    return [
        {
            "period": r[0],
            "message_count": r[1],
            "total_bytes": r[2],
            "unread_count": r[3]
        }
        for r in rows if r[0]
    ]

@router.get("/senders")
def get_sender_timeline(limit: int = 15, conn: sqlite3.Connection = Depends(get_db)):
    """Analyze high-volume sender lifecycles: first observed, peak, and most recent."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            s.id,
            s.normalized_address,
            s.display_name,
            s.domain,
            MIN(m.received_at) as first_seen,
            MAX(m.received_at) as last_seen,
            COUNT(m.id) as message_count,
            COALESCE(SUM(m.size_bytes), 0) as total_bytes
        FROM senders s
        JOIN messages m ON s.id = m.sender_id
        GROUP BY s.id
        ORDER BY message_count DESC
        LIMIT ?;
    """, (limit,))
    rows = cursor.fetchall()
    
    return [
        {
            "id": r[0],
            "address": r[1],
            "display_name": r[2] or r[1].split("@")[0],
            "domain": r[3],
            "first_seen": r[4],
            "last_seen": r[5],
            "message_count": r[6],
            "total_bytes": r[7]
        }
        for r in rows
    ]

@router.get("/cadence")
def get_timeline_cadence(conn: sqlite3.Connection = Depends(get_db)):
    """Calculate day-of-week volume distribution (Monday to Sunday)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            strftime('%w', received_at) as dow,
            COUNT(*) as message_count,
            COALESCE(SUM(size_bytes), 0) as total_bytes
        FROM messages
        WHERE received_at IS NOT NULL
        GROUP BY dow
        ORDER BY dow ASC;
    """)
    rows = cursor.fetchall()
    dow_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    dow_map = {str(i): {"day": dow_names[i], "day_index": i, "count": 0, "bytes": 0} for i in range(7)}
    for r in rows:
        if str(r[0]) in dow_map:
            dow_map[str(r[0])]["count"] = r[1]
            dow_map[str(r[0])]["bytes"] = r[2]

    # Reorder starting Monday (Mon-Sun standard ISO)
    ordered = [dow_map[str(i)] for i in [1, 2, 3, 4, 5, 6, 0]]
    return ordered
