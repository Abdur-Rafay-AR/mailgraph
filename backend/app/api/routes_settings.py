"""Privacy configuration, protection rules, local AI settings, and local data wipe."""

from fastapi import APIRouter, Depends, HTTPException
import sqlite3
from typing import List, Dict, Any

from backend.app.config import settings
from backend.app.db.database import get_db, get_database
from backend.app.models.schemas import SettingsUpdate, ProtectionRuleCreate, NlQueryRequest
from backend.app.ai.local_llm import LocalAiService

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("")
def get_settings():
    """Retrieve application settings, storage locations, and privacy status."""
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "data_dir": str(settings.data_dir),
        "db_path": settings.db_path,
        "telemetry": settings.telemetry,
        "index_message_bodies": settings.index_message_bodies,
        "download_attachments_automatically": settings.download_attachments_automatically,
        "local_ai_enabled": settings.local_ai_enabled,
        "local_ai_endpoint": settings.local_ai_endpoint,
        "local_ai_model": settings.local_ai_model,
        "default_delete_mode": settings.default_delete_mode
    }

@router.put("")
def update_settings(req: SettingsUpdate):
    """Update runtime settings."""
    if req.index_message_bodies is not None:
        settings.index_message_bodies = req.index_message_bodies
    if req.local_ai_enabled is not None:
        settings.local_ai_enabled = req.local_ai_enabled
    if req.local_ai_endpoint is not None:
        settings.local_ai_endpoint = req.local_ai_endpoint
    if req.local_ai_model is not None:
        settings.local_ai_model = req.local_ai_model
    if req.default_delete_mode is not None:
        settings.default_delete_mode = req.default_delete_mode
        
    return get_settings()

@router.get("/protection-rules")
def list_protection_rules(conn: sqlite3.Connection = Depends(get_db)):
    """List all sender, domain, and message protection rules."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, account_id, rule_type, rule_value, reason, created_at, enabled
        FROM protection_rules
        ORDER BY id DESC;
    """)
    rows = cursor.fetchall()
    return [
        {
            "id": r[0],
            "account_id": r[1],
            "rule_type": r[2],
            "rule_value": r[3],
            "reason": r[4],
            "created_at": r[5],
            "enabled": bool(r[6])
        }
        for r in rows
    ]

@router.post("/protection-rules")
def create_protection_rule(req: ProtectionRuleCreate, conn: sqlite3.Connection = Depends(get_db)):
    """Add a new protected sender or domain."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO protection_rules (account_id, rule_type, rule_value, reason, enabled)
        VALUES (?, ?, ?, ?, 1);
    """, (req.account_id, req.rule_type, req.rule_value.strip().lower(), req.reason or "User protected"))
    rule_id = cursor.lastrowid
    
    # If protecting a sender, mark the senders table too
    if req.rule_type == "sender":
        cursor.execute("UPDATE senders SET is_protected = 1 WHERE normalized_address = ?;", (req.rule_value.strip().lower(),))
        
    return {"id": rule_id, "status": "created"}

@router.delete("/protection-rules/{rule_id}")
def delete_protection_rule(rule_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Remove a protection rule."""
    cursor = conn.cursor()
    cursor.execute("SELECT rule_type, rule_value FROM protection_rules WHERE id = ?;", (rule_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    cursor.execute("DELETE FROM protection_rules WHERE id = ?;", (rule_id,))
    if row[0] == "sender":
        cursor.execute("UPDATE senders SET is_protected = 0 WHERE normalized_address = ?;", (row[1],))
        
    return {"status": "deleted", "rule_id": rule_id}

@router.get("/ai/status")
def get_ai_status():
    """Check connectivity to optional local Ollama model daemon."""
    service = LocalAiService()
    return service.check_status()

@router.post("/ai/query")
def translate_nl_query(req: NlQueryRequest):
    """Translate natural language request into a validated, inspectable QueryAST."""
    service = LocalAiService()
    ast = service.translate_nl_query(req.prompt)
    if not ast:
        raise HTTPException(status_code=503, detail="Local AI model is not reachable or failed to parse query.")
    return {
        "version": ast.version,
        "search_term": ast.search_term,
        "all": [{"field": c.field, "op": c.op, "value": c.value} for c in ast.all],
        "exclude_protected": ast.exclude_protected
    }

@router.post("/wipe-data")
def wipe_all_local_data(conn: sqlite3.Connection = Depends(get_db)):
    """Securely purge all local email tables, indexes, and accounts."""
    cursor = conn.cursor()
    tables = [
        "operation_items", "operations", "insights", "sync_runs",
        "attachments", "message_addresses", "message_categories",
        "messages", "messages_fts", "threads", "senders", "folders",
        "accounts", "saved_queries"
    ]
    for t in tables:
        cursor.execute(f"DELETE FROM {t};")
    conn.commit()
    cursor.execute("VACUUM;")
    return {"status": "success", "message": "All local data has been securely wiped."}
