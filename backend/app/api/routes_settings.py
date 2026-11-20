"""Privacy configuration, protection rules, local AI settings, and local data wipe."""

import json
import sqlite3
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from backend.app.ai.local_llm import LocalAiService, is_loopback_endpoint
from backend.app.config import settings
from backend.app.db.database import get_db
from backend.app.models.schemas import NlQueryRequest, ProtectionRuleCreate, SettingsUpdate
from backend.app.security.credential_store import CredentialStore

router = APIRouter(prefix="/api/settings", tags=["settings"])

_PERSISTED_SETTING_KEYS = (
    "index_message_bodies",
    "local_ai_enabled",
    "local_ai_endpoint",
    "local_ai_model",
    "default_delete_mode",
)


def load_persisted_settings(conn: sqlite3.Connection) -> None:
    """Hydrate runtime Settings singleton from SQLite app_settings table."""
    cursor = conn.cursor()
    cursor.execute("SELECT key, value_json FROM app_settings;")
    for row in cursor.fetchall():
        key = row["key"]
        if key not in _PERSISTED_SETTING_KEYS:
            continue
        try:
            val = json.loads(row["value_json"])
            setattr(settings, key, val)
        except Exception:
            continue


def _persist_setting(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        INSERT INTO app_settings (key, value_json, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = datetime('now');
        """,
        (key, json.dumps(value)),
    )


def _sync_fts_body_index(conn: sqlite3.Connection, enabled: bool) -> None:
    """Rebuild FTS5 body_text column according to privacy index_message_bodies setting."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages_fts;")
    if enabled:
        cursor.execute("""
            INSERT INTO messages_fts (message_id, subject, snippet, body_text)
            SELECT id, COALESCE(subject, ''), COALESCE(snippet, ''), COALESCE(body_text, '')
            FROM messages;
        """)
        cursor.execute("UPDATE messages SET body_indexed = 1;")
    else:
        cursor.execute("""
            INSERT INTO messages_fts (message_id, subject, snippet, body_text)
            SELECT id, COALESCE(subject, ''), COALESCE(snippet, ''), ''
            FROM messages;
        """)
        cursor.execute("UPDATE messages SET body_indexed = 0;")


@router.get("")
def get_settings() -> Dict[str, Any]:
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
def update_settings(req: SettingsUpdate, conn: sqlite3.Connection = Depends(get_db)):
    """Update and persist runtime settings."""
    if req.local_ai_endpoint is not None and not is_loopback_endpoint(req.local_ai_endpoint):
        raise HTTPException(
            status_code=400,
            detail="Local AI endpoint must target localhost or loopback (127.0.0.1 / localhost) for privacy."
        )
    if req.default_delete_mode is not None and req.default_delete_mode not in ("trash", "archive"):
        raise HTTPException(status_code=400, detail="default_delete_mode must be 'trash' or 'archive'")

    if req.index_message_bodies is not None:
        prev = settings.index_message_bodies
        settings.index_message_bodies = req.index_message_bodies
        _persist_setting(conn, "index_message_bodies", settings.index_message_bodies)
        if prev != req.index_message_bodies:
            _sync_fts_body_index(conn, req.index_message_bodies)
    if req.local_ai_enabled is not None:
        settings.local_ai_enabled = req.local_ai_enabled
        _persist_setting(conn, "local_ai_enabled", settings.local_ai_enabled)
    if req.local_ai_endpoint is not None:
        settings.local_ai_endpoint = req.local_ai_endpoint
        _persist_setting(conn, "local_ai_endpoint", settings.local_ai_endpoint)
    if req.local_ai_model is not None:
        settings.local_ai_model = req.local_ai_model
        _persist_setting(conn, "local_ai_model", settings.local_ai_model)
    if req.default_delete_mode is not None:
        settings.default_delete_mode = req.default_delete_mode
        _persist_setting(conn, "default_delete_mode", settings.default_delete_mode)

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
    valid_types = ("sender", "domain", "message", "thread", "query")
    if req.rule_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"rule_type must be one of: {', '.join(valid_types)}")

    cleaned_val = req.rule_value.strip().lower()
    if not cleaned_val:
        raise HTTPException(status_code=400, detail="rule_value cannot be empty")
    if req.rule_type == "sender" and "@" not in cleaned_val:
        raise HTTPException(status_code=400, detail="Sender rule must be a valid email address")

    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM protection_rules WHERE rule_type = ? AND rule_value = ? AND COALESCE(account_id, -1) = COALESCE(?, -1);",
        (req.rule_type, cleaned_val, req.account_id),
    )
    existing = cursor.fetchone()
    if existing:
        return {"id": existing[0], "status": "already_exists"}

    cursor.execute("""
        INSERT INTO protection_rules (account_id, rule_type, rule_value, reason, enabled)
        VALUES (?, ?, ?, ?, 1);
    """, (req.account_id, req.rule_type, cleaned_val, (req.reason or "User protected").strip()))
    rule_id = cursor.lastrowid

    if req.rule_type == "sender":
        cursor.execute("UPDATE senders SET is_protected = 1 WHERE normalized_address = ?;", (cleaned_val,))

    return {"id": rule_id, "status": "created"}


@router.delete("/protection-rules/{rule_id}")
def delete_protection_rule(rule_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Remove a protection rule."""
    cursor = conn.cursor()
    cursor.execute("SELECT rule_type, rule_value FROM protection_rules WHERE id = ?;", (rule_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule_type, rule_value = row[0], row[1]
    cursor.execute("DELETE FROM protection_rules WHERE id = ?;", (rule_id,))
    if rule_type == "sender":
        cursor.execute(
            "SELECT 1 FROM protection_rules WHERE rule_type = 'sender' AND rule_value = ? AND enabled = 1 LIMIT 1;",
            (rule_value,),
        )
        if not cursor.fetchone():
            cursor.execute("UPDATE senders SET is_protected = 0 WHERE normalized_address = ?;", (rule_value,))

    return {"status": "deleted", "rule_id": rule_id}


@router.get("/ai/status")
def get_ai_status():
    """Check connectivity to optional local Ollama model daemon."""
    service = LocalAiService()
    return service.check_status()


@router.post("/ai/query")
def translate_nl_query(req: NlQueryRequest):
    """Translate natural language request into a validated, inspectable QueryAST."""
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
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
    """Securely purge all local email tables, indexes, accounts, and stored credentials."""
    cursor = conn.cursor()

    # Clear stored credentials for all accounts so startup reconciliation doesn't resurrect them
    cursor.execute("SELECT DISTINCT email_address FROM accounts;")
    emails = [r[0] for r in cursor.fetchall() if r[0]]
    cred_store = CredentialStore()
    for email_addr in emails:
        cred_store.delete_credentials(email_addr)

    tables = [
        "operation_items", "operations", "insights", "sync_runs",
        "attachments", "message_addresses", "message_categories",
        "messages", "messages_fts", "threads", "senders", "folders",
        "accounts", "saved_queries"
    ]
    for t in tables:
        cursor.execute(f"DELETE FROM {t};")
    conn.commit()
    try:
        cursor.execute("VACUUM;")
    except sqlite3.OperationalError:
        pass
    return {"status": "success", "message": "All local data has been securely wiped."}
