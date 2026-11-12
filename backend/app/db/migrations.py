"""Database migrations and initial seed data for MailGraph."""

import sqlite3
from typing import List, Tuple
from backend.app.db.schema import ALL_TABLES, INDEXES, FTS_TABLES

DEFAULT_CATEGORIES: List[Tuple[str, str, str]] = [
    ("important", "High priority messages and starred contacts", "#ef4444"),
    ("personal", "Direct human conversations and personal correspondence", "#10b981"),
    ("work", "Professional communications, projects, colleagues", "#3b82f6"),
    ("university", "Academic, educational, course updates", "#8b5cf6"),
    ("transactional", "Order confirmations, tracking, flight itineraries", "#06b6d4"),
    ("receipt_invoice", "Financial receipts, invoices, billing statements", "#f59e0b"),
    ("security", "Password resets, 2FA alerts, login notifications", "#dc2626"),
    ("calendar", "Calendar invitations, RSVPs, meeting updates", "#6366f1"),
    ("notification", "Automated system alerts and status updates", "#64748b"),
    ("newsletter", "Editorial subscriptions, digests, blogs", "#14b8a6"),
    ("promotional", "Marketing campaigns, discounts, sales pitches", "#ec4899"),
    ("social", "Social media network alerts, invites, mentions", "#f97316"),
    ("automated_report", "Metrics digests, cron outputs, build results", "#475569"),
    ("cold_outreach", "Unsolicited sales pitches and recruiting", "#78716c"),
    ("unknown", "Unclassified correspondence", "#94a3b8")
]

DEFAULT_PROTECTION_RULES = [
    ("sender", "no-reply@accounts.google.com", "Essential Google Account security notifications"),
    ("domain", "apple.com", "Apple ID and iCloud receipts and alerts"),
    ("domain", "github.com", "Version control and account security notifications")
]

def run_migrations(conn: sqlite3.Connection) -> None:
    """Execute all schema migrations and initial seed data."""
    cursor = conn.cursor()
    
    # 1. Create all standard tables
    for ddl in ALL_TABLES:
        cursor.execute(ddl)
        
    # 2. Create performance indexes
    for idx in INDEXES:
        cursor.execute(idx)
        
    # 3. Create FTS5 virtual tables
    for fts in FTS_TABLES:
        cursor.execute(fts)
        
    # 4. Seed default categories if not already present
    for name, desc, color in DEFAULT_CATEGORIES:
        cursor.execute("""
            INSERT OR IGNORE INTO categories (name, description, is_system, color)
            VALUES (?, ?, 1, ?);
        """, (name, desc, color))
        
    # 5. Seed baseline protection rules
    for rule_type, val, reason in DEFAULT_PROTECTION_RULES:
        cursor.execute("""
            INSERT OR IGNORE INTO protection_rules (account_id, rule_type, rule_value, reason, enabled)
            SELECT NULL, ?, ?, ?, 1
            WHERE NOT EXISTS (
                SELECT 1 FROM protection_rules WHERE rule_type = ? AND rule_value = ?
            );
        """, (rule_type, val, reason, rule_type, val))
        
    # 6. Record migration version 1
    cursor.execute("""
        INSERT OR IGNORE INTO schema_migrations (version) VALUES (1);
    """)
    conn.commit()
