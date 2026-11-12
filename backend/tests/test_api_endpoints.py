import pytest
import random
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_clean_db():
    client.post("/api/settings/wipe-data")
    yield

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data

def test_create_and_list_account():
    # 1. Create synthetic account
    res = client.post("/api/accounts", json={
        "provider": "synthetic",
        "display_name": "Demo Mailbox",
        "email_address": "demo@mailgraph.local"
    })
    assert res.status_code == 200
    acc = res.json()
    account_id = acc["id"]
    assert account_id > 0
    
    # 2. List accounts
    list_res = client.get("/api/accounts")
    assert list_res.status_code == 200
    accounts = list_res.json()
    assert any(a["id"] == account_id for a in accounts)

def test_generate_synthetic_mailbox_and_overview():
    # Create account and generate 25 synthetic messages
    seed = random.randint(10000, 99999)
    res = client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Test Synthetic Box",
        "email_address": f"synthetic_{seed}@local.box",
        "message_count": 25,
        "seed": seed
    })
    assert res.status_code == 200
    data = res.json()
    assert data["inserted_count"] == 25
    
    # Check overview stats
    ov = client.get("/api/overview")
    assert ov.status_code == 200
    stats = ov.json()
    assert stats["total_messages"] >= 25
    assert stats["total_senders"] > 0
    assert len(stats["top_senders_by_count"]) > 0

def test_senders_endpoint_and_protection():
    # Generate some senders first
    client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Test Send Box",
        "email_address": "senders_test@local.box",
        "message_count": 15,
        "seed": 881
    })
    
    res = client.get("/api/senders")
    assert res.status_code == 200
    senders = res.json()["items"]
    assert len(senders) > 0
    
    first_sender = senders[0]
    sid = first_sender["id"]
    
    # Toggle protection
    prot_res = client.post(f"/api/senders/{sid}/protect", json={"is_protected": True})
    assert prot_res.status_code == 200
    assert prot_res.json()["is_protected"] is True

def test_messages_search_endpoint():
    client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Search Box",
        "email_address": "search_test@local.box",
        "message_count": 20,
        "seed": 992
    })
    
    res = client.post("/api/messages/search", json={
        "query": {
            "search_term": "Sprint",
            "exclude_protected": False
        },
        "page": 1,
        "page_size": 10
    })
    assert res.status_code == 200
    data = res.json()
    assert "total_count" in data
    assert "items" in data

def test_graph_endpoint():
    client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Graph Box",
        "email_address": "graph_test@local.box",
        "message_count": 20,
        "seed": 331
    })
    
    res = client.get("/api/graph?level=domain")
    assert res.status_code == 200
    data = res.json()
    assert "elements" in data
    assert len(data["elements"]["nodes"]) > 0

def test_cleanup_preview_and_execute_endpoint():
    client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Cleanup Box",
        "email_address": "cleanup_test@local.box",
        "message_count": 25,
        "seed": 441
    })
    
    # 1. Preview
    prev_res = client.post("/api/cleanup/preview", json={
        "operation_type": "trash",
        "query": {
            "all": [{"field": "is_read", "op": "eq", "value": True}],
            "exclude_protected": True
        }
    })
    assert prev_res.status_code == 200
    preview = prev_res.json()
    assert "target_count" in preview
    assert preview["operation_type"] == "trash"
    
    # 2. Execute
    exec_res = client.post("/api/cleanup/execute", json={
        "operation_type": "trash",
        "query": {
            "all": [{"field": "is_read", "op": "eq", "value": True}],
            "exclude_protected": True
        }
    })
    assert exec_res.status_code == 200
    op = exec_res.json()
    assert "operation_id" in op
    assert op["status"] == "completed"

def test_insights_endpoint():
    client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Insight Box",
        "email_address": "insight_test@local.box",
        "message_count": 30,
        "seed": 551
    })
    res = client.get("/api/insights")
    assert res.status_code == 200
    insights = res.json()
    assert isinstance(insights, list)
