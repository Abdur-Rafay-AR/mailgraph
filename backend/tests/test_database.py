import os
import sqlite3
import pytest
from backend.app.db.database import Database
from backend.app.db.schema import ALL_TABLES, FTS_TABLES
from backend.app.db.migrations import run_migrations

def test_database_initialization_in_memory():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys;")
        fk = cursor.fetchone()[0]
        assert fk == 1

def test_migrations_create_all_tables():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        
        # Verify core tables
        expected_tables = {
            "accounts", "folders", "messages", "message_addresses",
            "senders", "threads", "attachments", "categories",
            "message_categories", "protection_rules", "saved_queries",
            "operations", "operation_items", "sync_runs", "insights",
            "messages_fts", "schema_migrations"
        }
        for table in expected_tables:
            assert table in tables, f"Expected table '{table}' to be created"

def test_default_categories_seeded():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories;")
        categories = {row[0] for row in cursor.fetchall()}
        
        expected_categories = {
            "important", "personal", "work", "university",
            "transactional", "receipt_invoice", "security", "calendar",
            "notification", "newsletter", "promotional", "social",
            "automated_report", "cold_outreach", "unknown"
        }
        assert expected_categories.issubset(categories)

def test_fts5_indexing_and_search():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages_fts (message_id, subject, snippet, body_text)
            VALUES (1, 'Weekly Newsletter from TechRadar', 'Top headlines in open source software', 'Full email text content goes here.');
        """)
        cursor.execute("SELECT message_id FROM messages_fts WHERE messages_fts MATCH 'TechRadar';")
        res = cursor.fetchall()
        assert len(res) == 1
        assert res[0][0] == 1
