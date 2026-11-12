"""Main FastAPI application entrypoint for MailGraph."""

import sqlite3
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

from backend.app.config import settings
from backend.app.db.database import get_database, get_db
from backend.app.api.routes_accounts import router as accounts_router
from backend.app.api.routes_senders import router as senders_router
from backend.app.api.routes_messages import router as messages_router
from backend.app.api.routes_graph import router as graph_router
from backend.app.api.routes_cleanup import router as cleanup_router
from backend.app.api.routes_attachments import router as attachments_router
from backend.app.api.routes_timeline import router as timeline_router
from backend.app.api.routes_insights import router as insights_router
from backend.app.api.routes_settings import router as settings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database and run migrations on startup
    db = get_database()
    db.initialize()
    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan
)

# Enable CORS for local desktop UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(accounts_router)
app.include_router(senders_router)
app.include_router(messages_router)
app.include_router(graph_router)
app.include_router(cleanup_router)
app.include_router(attachments_router)
app.include_router(timeline_router)
app.include_router(insights_router)
app.include_router(settings_router)

@app.get("/api/health")
def health_check():
    """Health check endpoint for desktop process heartbeat."""
    return {"status": "ok", "version": settings.app_version, "app": settings.app_name}

@app.get("/api/overview")
def get_overview(conn: sqlite3.Connection = Depends(get_db)):
    """Mailbox overview statistics: counts, date coverage, storage, and top senders."""
    cursor = conn.cursor()
    
    # Message count, unread, storage for active mailbox (excluding trash/spam)
    cursor.execute("""
        SELECT 
            COUNT(id) as total_messages,
            COALESCE(SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END), 0) as unread_messages,
            COALESCE(SUM(size_bytes), 0) as total_bytes,
            MIN(received_at) as earliest_date,
            MAX(received_at) as latest_date
        FROM messages
        WHERE folder_id IS NULL OR folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam'));
    """)
    m_stats = cursor.fetchone()
    
    # Active Senders & domains count
    cursor.execute("""
        SELECT COUNT(DISTINCT s.id) as total_senders, COUNT(DISTINCT s.domain) as total_domains 
        FROM senders s
        JOIN messages m ON s.id = m.sender_id
        WHERE m.folder_id IS NULL OR m.folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam'));
    """)
    s_stats = cursor.fetchone()
    
    # Accounts count
    cursor.execute("SELECT COUNT(id) FROM accounts;")
    acc_count = cursor.fetchone()[0]
    
    # Top 5 senders by active message count
    cursor.execute("""
        SELECT s.id, s.normalized_address, s.display_name, s.domain,
               COUNT(m.id) as count, COALESCE(SUM(m.size_bytes), 0) as bytes
        FROM senders s
        JOIN messages m ON s.id = m.sender_id
        WHERE m.folder_id IS NULL OR m.folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam'))
        GROUP BY s.id
        HAVING count > 0
        ORDER BY count DESC
        LIMIT 5;
    """)
    top_senders_count = [
        {"id": r[0], "address": r[1], "name": r[2] or r[1].split("@")[0], "domain": r[3], "message_count": r[4], "total_bytes": r[5]}
        for r in cursor.fetchall()
    ]
    
    # Category counts for active messages
    cursor.execute("""
        SELECT c.name, c.color, COUNT(mc.message_id) as count
        FROM categories c
        JOIN message_categories mc ON c.id = mc.category_id
        JOIN messages m ON mc.message_id = m.id
        WHERE m.folder_id IS NULL OR m.folder_id NOT IN (SELECT id FROM folders WHERE folder_type IN ('trash', 'spam'))
        GROUP BY c.id
        HAVING count > 0
        ORDER BY count DESC;
    """)
    category_distribution = [
        {"name": r[0], "color": r[1], "count": r[2]}
        for r in cursor.fetchall()
    ]
    
    # Recent scan status
    cursor.execute("""
        SELECT id, account_id, status, started_at, completed_at, inserted_count, failed_count
        FROM sync_runs
        ORDER BY id DESC LIMIT 1;
    """)
    last_sync = cursor.fetchone()
    sync_status = {
        "status": last_sync[2] if last_sync else "idle",
        "started_at": last_sync[3] if last_sync else None,
        "completed_at": last_sync[4] if last_sync else None,
        "inserted_count": last_sync[5] if last_sync else 0
    } if last_sync else None
    
    return {
        "total_messages": m_stats[0],
        "unread_messages": m_stats[1],
        "total_bytes": m_stats[2],
        "earliest_date": m_stats[3],
        "latest_date": m_stats[4],
        "total_senders": s_stats[0],
        "total_domains": s_stats[1],
        "total_accounts": acc_count,
        "top_senders_by_count": top_senders_count,
        "categories": category_distribution,
        "recent_sync": sync_status
    }
