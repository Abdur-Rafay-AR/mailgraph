import os
import tempfile
import pytest
from backend.app.db.database import Database
from backend.app.db.migrations import run_migrations
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.providers.synthetic import SyntheticMailboxGenerator
from backend.app.providers.mbox import MboxProvider

def test_ingestion_pipeline_stores_messages_and_senders():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO accounts (provider, display_name, email_address)
            VALUES ('synthetic', 'Demo Account', 'user@local');
        """)
        account_id = cursor.lastrowid

    generator = SyntheticMailboxGenerator(seed=999)
    pipeline = IngestionPipeline(db)
    
    result = pipeline.ingest_messages(account_id, generator.generate(count=30))
    assert result.inserted_count == 30
    assert result.failed_count == 0
    
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages WHERE account_id = ?;", (account_id,))
        count = cursor.fetchone()[0]
        assert count == 30
        
        cursor.execute("SELECT COUNT(*) FROM senders;")
        sender_count = cursor.fetchone()[0]
        assert sender_count > 0
        
        cursor.execute("SELECT COUNT(*) FROM threads WHERE account_id = ?;", (account_id,))
        thread_count = cursor.fetchone()[0]
        assert thread_count > 0

def test_ingestion_pipeline_deduplication():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (provider, display_name, email_address) VALUES ('synthetic', 'Demo', 'u@l');")
        account_id = cursor.lastrowid
        
    generator = SyntheticMailboxGenerator(seed=777)
    messages = list(generator.generate(count=20))
    
    pipeline = IngestionPipeline(db)
    res1 = pipeline.ingest_messages(account_id, messages)
    assert res1.inserted_count == 20
    
    # Re-ingesting the exact same messages must not duplicate
    res2 = pipeline.ingest_messages(account_id, messages)
    assert res2.inserted_count == 0
    assert res2.skipped_count == 20
    
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages WHERE account_id = ?;", (account_id,))
        assert cursor.fetchone()[0] == 20


def test_ingestion_pipeline_updates_read_and_star_flags_on_resync():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (provider, display_name, email_address) VALUES ('imap', 'Gmail', 'u@gmail.com');")
        account_id = cursor.lastrowid

    generator = SyntheticMailboxGenerator(seed=321)
    messages = list(generator.generate(count=5))
    for m in messages:
        m.is_read = False
        m.is_starred = False

    pipeline = IngestionPipeline(db)
    res1 = pipeline.ingest_messages(account_id, messages)
    assert res1.inserted_count == 5

    # Re-sync with updated read/starred flags
    for m in messages:
        m.is_read = True
    messages[0].is_starred = True

    res2 = pipeline.ingest_messages(account_id, messages)
    assert res2.inserted_count == 0
    assert res2.updated_count == 5

    with db.connect() as conn:
        unread = conn.execute("SELECT COUNT(*) FROM messages WHERE account_id = ? AND is_read = 0;", (account_id,)).fetchone()[0]
        starred = conn.execute("SELECT COUNT(*) FROM messages WHERE account_id = ? AND is_starred = 1;", (account_id,)).fetchone()[0]
        assert unread == 0
        assert starred == 1
