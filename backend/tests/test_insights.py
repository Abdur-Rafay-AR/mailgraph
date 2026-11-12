import pytest
from backend.app.db.database import Database
from backend.app.db.migrations import run_migrations
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.providers.synthetic import SyntheticMailboxGenerator
from backend.app.insights.insight_service import InsightService

def test_generate_insights_for_synthetic_mailbox():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (provider, display_name, email_address) VALUES ('synthetic', 'Demo', 'u@l');")
        account_id = cursor.lastrowid

    generator = SyntheticMailboxGenerator(seed=555)
    pipeline = IngestionPipeline(db)
    pipeline.ingest_messages(account_id, generator.generate(count=80))

    insight_service = InsightService(db)
    insights = insight_service.generate_insights(account_id)
    
    assert len(insights) > 0
    insight_types = {ins.insight_type for ins in insights}
    # Verify that at least one actionable category was recognized
    assert any(t in insight_types for t in ["storage_dominator", "zombie_subscription", "large_attachments", "unreplied_thread"])
    
    # Verify evidence and description are populated
    for ins in insights:
        assert ins.title
        assert ins.description
        assert ins.confidence > 0.0
