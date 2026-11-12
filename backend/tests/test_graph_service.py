import pytest
from backend.app.db.database import Database
from backend.app.db.migrations import run_migrations
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.providers.synthetic import SyntheticMailboxGenerator
from backend.app.graph.graph_service import GraphService

def test_generate_domain_graph():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (provider, display_name, email_address) VALUES ('synthetic', 'Demo', 'u@l');")
        account_id = cursor.lastrowid

    generator = SyntheticMailboxGenerator(seed=404)
    pipeline = IngestionPipeline(db)
    pipeline.ingest_messages(account_id, generator.generate(count=60))

    graph_service = GraphService(db)
    graph_data = graph_service.get_graph(account_id=account_id, level="domain")
    
    nodes = graph_data["elements"]["nodes"]
    edges = graph_data["elements"]["edges"]
    
    assert len(nodes) > 0
    # Check domain node attributes
    domain_nodes = [n for n in nodes if n["data"]["node_type"] == "domain"]
    assert len(domain_nodes) >= 5
    
    sample = domain_nodes[0]["data"]
    assert "message_count" in sample
    assert "total_bytes" in sample
    assert "unread_count" in sample
    assert "label" in sample

def test_generate_sender_drilldown_graph():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (provider, display_name, email_address) VALUES ('synthetic', 'Demo', 'u@l');")
        account_id = cursor.lastrowid

    generator = SyntheticMailboxGenerator(seed=404)
    pipeline = IngestionPipeline(db)
    pipeline.ingest_messages(account_id, generator.generate(count=60))

    graph_service = GraphService(db)
    # Drilldown for a specific domain
    graph_data = graph_service.get_graph(account_id=account_id, level="sender", selected_domain="acme-corp.com")
    
    nodes = graph_data["elements"]["nodes"]
    edges = graph_data["elements"]["edges"]
    
    sender_nodes = [n for n in nodes if n["data"]["node_type"] == "sender"]
    assert len(sender_nodes) > 0
    # There should be edges connecting senders to domain
    assert len(edges) > 0
