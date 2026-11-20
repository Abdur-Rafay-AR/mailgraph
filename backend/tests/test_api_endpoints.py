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

def test_imap_connect_endpoint(monkeypatch):
    from unittest.mock import MagicMock
    from backend.app.providers.imap import ImapProvider

    mock_connect = MagicMock()
    monkeypatch.setattr(ImapProvider, "connect", mock_connect)
    monkeypatch.setattr(ImapProvider, "stream_messages", lambda self, folder_id, limit: [])

    res = client.post("/api/accounts/imap/connect", json={
        "display_name": "My Gmail",
        "email_address": "testuser@gmail.com",
        "host": "imap.gmail.com",
        "username": "testuser@gmail.com",
        "password": "abcdefghijklmnop",
        "port": 993,
        "use_ssl": True
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["email_address"] == "testuser@gmail.com"
    assert data["account_id"] > 0


def test_senders_cleaned_disappear_from_list_and_overview():
    # 1. Generate synthetic mailbox
    seed = random.randint(10000, 99999)
    res = client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Disappearing Sender Test",
        "email_address": f"disappear_{seed}@local.box",
        "message_count": 15,
        "seed": seed
    })
    assert res.status_code == 200

    # 2. Get list of senders
    senders_res = client.get("/api/senders")
    assert senders_res.status_code == 200
    senders_list = senders_res.json()["items"]
    assert len(senders_list) > 0
    target_sender = senders_list[0]
    target_sender_id = target_sender["id"]
    target_address = target_sender["normalized_address"]

    # 3. Clean up all messages from target sender
    clean_res = client.post("/api/senders/bulk-cleanup-execute", json={
        "sender_ids": [target_sender_id],
        "operation_type": "trash",
        "exclude_protected": False
    })
    assert clean_res.status_code == 200

    # 4. Senders list must immediately exclude target sender
    refreshed_senders = client.get("/api/senders").json()["items"]
    refreshed_ids = [s["id"] for s in refreshed_senders]
    assert target_sender_id not in refreshed_ids

def test_cors_security_origin_restriction():
    """Verify that localhost and null origins are allowed, while external origins are blocked."""
    # 1. Allowed localhost origin (Vite dev server)
    res_local = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert res_local.status_code == 200
    assert res_local.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # 2. Allowed null origin (Electron local file bundle)
    res_null = client.get("/api/health", headers={"Origin": "null"})
    assert res_null.status_code == 200
    assert res_null.headers.get("access-control-allow-origin") == "null"

    # 3. Blocked external / malicious origin
    res_external = client.get("/api/health", headers={"Origin": "https://malicious-website.com"})
    assert res_external.status_code == 200
    assert res_external.headers.get("access-control-allow-origin") is None

def test_account_sync_endpoint_synthetic():
    """Verify that an existing account can be synced without re-entering credentials."""
    # 1. Create synthetic account
    res = client.post("/api/accounts", json={
        "provider": "synthetic",
        "display_name": "Sync Test Mailbox",
        "email_address": "sync_test@mailgraph.local"
    })
    assert res.status_code == 200
    account_id = res.json()["id"]

    # 2. Trigger sync
    sync_res = client.post(f"/api/accounts/{account_id}/sync?limit=15")
    assert sync_res.status_code == 200
    data = sync_res.json()
    assert data["status"] == "success"
    assert data["account_id"] == account_id
    assert data["inserted_count"] > 0

    # 3. Verify last_sync_at is updated
    accounts = client.get("/api/accounts").json()
    target = next(a for a in accounts if a["id"] == account_id)
    assert target["last_sync_at"] is not None

def test_account_sync_missing_account():
    """Verify 404 for non-existent account sync."""
    res = client.post("/api/accounts/999999/sync")
    assert res.status_code == 404

def test_account_sync_missing_keyring_credentials():
    """Verify error when OS keyring does not contain credentials for an IMAP account."""
    res = client.post("/api/accounts", json={
        "provider": "imap",
        "display_name": "No Creds Account",
        "email_address": "nocreds@example.com"
    })
    acc_id = res.json()["id"]
    sync_res = client.post(f"/api/accounts/{acc_id}/sync")
    assert sync_res.status_code == 400
    assert "credentials" in sync_res.json()["detail"].lower()

def test_background_sync_lifecycle_and_stop():
    """Verify background sync starts, reports progress, and can be stopped."""
    import time
    # 1. Create synthetic account
    res = client.post("/api/accounts", json={
        "provider": "synthetic",
        "display_name": "BG Sync Test",
        "email_address": "bgsync@mailgraph.local"
    })
    acc_id = res.json()["id"]

    # 2. Start background sync with 100 messages
    start_res = client.post(f"/api/accounts/{acc_id}/sync-start?limit=100")
    assert start_res.status_code == 200
    assert start_res.json()["status"] in ("started", "already_running")

    # 3. Check active sync status endpoint
    poll_res = client.get("/api/accounts/sync/active")
    assert poll_res.status_code == 200
    poll_data = poll_res.json()
    assert "job" in poll_data
    assert poll_data["job"]["account_id"] == acc_id

    # 4. Stop sync
    stop_res = client.post("/api/accounts/sync/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "stopping"

    # Wait briefly for thread to settle
    time.sleep(0.5)
    final_res = client.get("/api/accounts/sync/active").json()
    assert final_res["job"]["status"] in ("stopped", "completed")

def test_account_status_toggle_and_sync_restriction():
    """Verify accounts can be paused/disabled and resumed, and paused accounts reject sync."""
    res = client.post("/api/accounts", json={
        "provider": "synthetic",
        "display_name": "Toggle Account",
        "email_address": "toggle@mailgraph.local"
    })
    acc_id = res.json()["id"]
    assert res.json()["status"] == "active"

    # Pause account
    patch_res = client.patch(f"/api/accounts/{acc_id}/status", json={"status": "paused"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "paused"

    # Verify listing reflects paused status
    accs = client.get("/api/accounts").json()
    acc = next(a for a in accs if a["id"] == acc_id)
    assert acc["status"] == "paused"

    # Attempting to sync paused account must be rejected with 400
    sync_res = client.post(f"/api/accounts/{acc_id}/sync")
    assert sync_res.status_code == 400
    assert "disabled/paused" in sync_res.json()["detail"]

    start_sync_res = client.post(f"/api/accounts/{acc_id}/sync-start")
    assert start_sync_res.status_code == 400
    assert "disabled/paused" in start_sync_res.json()["detail"]

    # Re-enable account
    resume_res = client.patch(f"/api/accounts/{acc_id}/status", json={"status": "active"})
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "active"

def test_account_scoping_and_pause_exclusion():
    """Verify overview and message search filter by account_id and exclude paused accounts by default."""
    # 1. Generate 10 messages for Account 1
    res1 = client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Account 1",
        "email_address": "box1@mailgraph.local",
        "message_count": 10,
        "seed": 101
    })
    acc1_id = res1.json()["account_id"]

    # 2. Generate 10 messages for Account 2
    res2 = client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Account 2",
        "email_address": "box2@mailgraph.local",
        "message_count": 10,
        "seed": 202
    })
    acc2_id = res2.json()["account_id"]

    # Global overview should see both (20 messages)
    ov_all = client.get("/api/overview").json()
    assert ov_all["total_messages"] == 20

    # Scoped overview for Account 1
    ov_acc1 = client.get(f"/api/overview?account_id={acc1_id}").json()
    assert ov_acc1["total_messages"] == 10

    # Search scoped to Account 2
    search_acc2 = client.post("/api/messages/search", json={
        "query": {"account_ids": [acc2_id], "exclude_protected": False}
    }).json()
    assert search_acc2["total_count"] == 10
    assert all(item["account_id"] == acc2_id for item in search_acc2["items"])

    # Now pause Account 2
    client.patch(f"/api/accounts/{acc2_id}/status", json={"status": "paused"})

    # Default overview should now only count active Account 1 (10 messages)
    ov_after_pause = client.get("/api/overview").json()
    assert ov_after_pause["total_messages"] == 10

    # Default search should now only return active Account 1 messages
    search_default = client.post("/api/messages/search", json={
        "query": {"exclude_protected": False}
    }).json()
    assert search_default["total_count"] == 10
    assert all(item["account_id"] == acc1_id for item in search_default["items"])


def test_sync_labels_endpoints(client):
    # Setup account and synthetic data
    acc_res = client.post("/api/accounts/synthetic", json={"message_count": 10})
    acc_id = acc_res.json()["account_id"]

    # 1. Sync labels preview
    prev_res = client.post(f"/api/accounts/{acc_id}/sync-labels/preview")
    assert prev_res.status_code == 200
    prev_data = prev_res.json()
    assert "categories" in prev_data
    assert "total_messages" in prev_data

    # 2. Sync labels execute
    exec_res = client.post(f"/api/accounts/{acc_id}/sync-labels/execute", json={})
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert "batch_id" in exec_data
    assert exec_data["labeled_count"] >= 0

    # 3. Sync labels undo
    undo_res = client.post(f"/api/accounts/{acc_id}/sync-labels/undo", json={"batch_id": exec_data["batch_id"]})
    assert undo_res.status_code == 200
    assert "undone_count" in undo_res.json()

    # 4. Cleanup label preview and execute
    clean_prev = client.post("/api/cleanup/preview", json={
        "account_id": acc_id,
        "operation_type": "label",
        "label_name": "MailGraph/CustomTag",
        "query": {"version": 1, "all": [], "any": [], "none": []}
    })
    assert clean_prev.status_code == 200
    assert clean_prev.json()["operation_type"] == "label"

    clean_exec = client.post("/api/cleanup/execute", json={
        "account_id": acc_id,
        "operation_type": "label",
        "label_name": "MailGraph/CustomTag",
        "query": {"version": 1, "all": [], "any": [], "none": []}
    })
    assert clean_exec.status_code == 200
    assert clean_exec.json()["operation_type"] == "label"


def test_sync_labels_paused_and_not_found(client):
    # Missing account
    missing_id = 999999
    assert client.post(f"/api/accounts/{missing_id}/sync-labels/preview").status_code == 404
    assert client.post(f"/api/accounts/{missing_id}/sync-labels/execute", json={}).status_code == 404
    assert client.post(f"/api/accounts/{missing_id}/sync-labels/undo", json={"batch_id": "dummy"}).status_code == 404

    # Create account and pause it
    acc_res = client.post("/api/accounts/synthetic/generate", json={
        "display_name": "Paused Box",
        "email_address": "paused@mailgraph.local",
        "message_count": 5
    })
    acc_id = acc_res.json()["account_id"]
    client.patch(f"/api/accounts/{acc_id}/status", json={"status": "paused"})

    # Check paused account
    assert client.post(f"/api/accounts/{acc_id}/sync-labels/preview").status_code == 400
    assert client.post(f"/api/accounts/{acc_id}/sync-labels/execute", json={}).status_code == 400
    assert client.post(f"/api/accounts/{acc_id}/sync-labels/undo", json={"batch_id": "dummy"}).status_code == 400





