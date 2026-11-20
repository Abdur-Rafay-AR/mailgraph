import json
import pytest
from unittest.mock import MagicMock
from backend.app.db.database import Database
from backend.app.classification.category_sync import CategoryLabelSyncService, CATEGORY_GMAIL_LABEL_MAP


def test_category_label_sync_service(tmp_path):
    db = Database(str(tmp_path / "sync.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'User', 'u@test.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain) VALUES (1, 'bank@nayapay.com', 'nayapay.com');")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'msg_fin_1', 1, 1, 'bank@nayapay.com', '2026-01-01');")
        
        # Add to finance category
        fin_id = conn.execute("SELECT id FROM categories WHERE name = 'finance';").fetchone()[0]
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (1, ?, 'rule');", (fin_id,))

    service = CategoryLabelSyncService(db)
    
    # 1. Preview
    preview = service.preview_sync(account_id=1)
    assert preview["total_messages"] == 1
    assert len(preview["categories"]) == 1
    assert preview["categories"][0]["category"] == "finance"
    assert preview["categories"][0]["label"] == "MailGraph/Finance"
    assert preview["categories"][0]["count"] == 1

    # 2. Execute
    res = service.execute_sync(account_id=1, sync_remote=False)
    assert res["labeled_count"] == 1
    assert len(res["operation_ids"]) == 1
    assert res["batch_id"] is not None

    # Verify operations table has distinct entry with batch_id
    with db.connect() as conn:
        op = conn.execute("SELECT operation_type, target_count, status FROM operations WHERE id = ?;", (res["operation_ids"][0],)).fetchone()
        assert op["operation_type"] == "label"
        assert op["status"] == "completed"

    # 3. Undo Batch
    undo_res = service.undo_batch(res["batch_id"])
    assert undo_res["undone_count"] == 1


def test_preview_and_execute_excludes_protected_messages(tmp_path):
    db = Database(str(tmp_path / "sync_prot.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'User', 'u@test.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        # Sender 1 is unprotected, Sender 2 is protected
        conn.execute("INSERT INTO senders (id, normalized_address, domain, is_protected) VALUES (1, 'work1@company.com', 'company.com', 0);")
        conn.execute("INSERT INTO senders (id, normalized_address, domain, is_protected) VALUES (2, 'work2@company.com', 'company.com', 1);")
        # Sender 3 belongs to protected domain apple.com
        conn.execute("INSERT INTO senders (id, normalized_address, domain, is_protected) VALUES (3, 'billing@apple.com', 'apple.com', 0);")

        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'msg_work_1', 1, 1, 'work1@company.com', '2026-01-01');")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (2, 1, 'msg_work_2', 1, 2, 'work2@company.com', '2026-01-01');")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (3, 1, 'msg_work_3', 1, 3, 'billing@apple.com', '2026-01-01');")

        work_id = conn.execute("SELECT id FROM categories WHERE name = 'work';").fetchone()[0]
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (1, ?, 'rule');", (work_id,))
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (2, ?, 'rule');", (work_id,))
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (3, ?, 'rule');", (work_id,))

    service = CategoryLabelSyncService(db)

    # Preview should only count unprotected message 1
    preview = service.preview_sync(account_id=1)
    assert preview["total_messages"] == 1
    assert preview["categories"][0]["category"] == "work"
    assert preview["categories"][0]["label"] == "MailGraph/Work"
    assert preview["categories"][0]["count"] == 1

    # Execute should only label unprotected message 1
    res = service.execute_sync(account_id=1, sync_remote=False)
    assert res["labeled_count"] == 1

    with db.connect() as conn:
        items = conn.execute("SELECT message_id FROM operation_items WHERE operation_id = ?;", (res["operation_ids"][0],)).fetchall()
        assert len(items) == 1
        assert items[0]["message_id"] == 1


def test_selective_categories_and_custom_batch_id(tmp_path):
    db = Database(str(tmp_path / "sync_sel.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'User', 'u@test.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain) VALUES (1, 'news@digest.com', 'digest.com');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain) VALUES (2, 'friend@social.com', 'social.com');")

        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'msg_news', 1, 1, 'news@digest.com', '2026-01-01');")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (2, 1, 'msg_soc', 1, 2, 'friend@social.com', '2026-01-01');")

        news_id = conn.execute("SELECT id FROM categories WHERE name = 'newsletter';").fetchone()[0]
        soc_id = conn.execute("SELECT id FROM categories WHERE name = 'social';").fetchone()[0]
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (1, ?, 'rule');", (news_id,))
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (2, ?, 'rule');", (soc_id,))

    service = CategoryLabelSyncService(db)

    # 1. Sync only newsletter category with custom batch_id
    custom_batch = "custom-batch-12345"
    res = service.execute_sync(account_id=1, categories=["newsletter"], batch_id=custom_batch, sync_remote=False)
    assert res["batch_id"] == custom_batch
    assert res["labeled_count"] == 1
    assert len(res["operation_ids"]) == 1

    # 2. Undo that specific batch
    undo_res = service.undo_batch(custom_batch)
    assert undo_res["undone_count"] == 1

    # 3. Full sync without category filter: both newsletter and social
    full_res = service.execute_sync(account_id=1, sync_remote=False)
    assert full_res["labeled_count"] == 2
    assert len(full_res["operation_ids"]) == 2

    # Undo full sync batch undos both operations
    full_undo = service.undo_batch(full_res["batch_id"])
    assert full_undo["undone_count"] == 2


def test_empty_account_preview_and_execute(tmp_path):
    db = Database(str(tmp_path / "sync_empty.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'User', 'u@test.com');")

    service = CategoryLabelSyncService(db)

    preview = service.preview_sync(account_id=1)
    assert preview["account_id"] == 1
    assert preview["total_messages"] == 0
    assert preview["categories"] == []

    res = service.execute_sync(account_id=1, sync_remote=False)
    assert res["labeled_count"] == 0
    assert res["operation_ids"] == []
    assert res["batch_id"] is not None

    undo_res = service.undo_batch(res["batch_id"])
    assert undo_res["undone_count"] == 0


def test_category_sync_remote_provider_calls(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "sync_remote.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'User', 'u@test.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain) VALUES (1, 'sales@shop.com', 'shop.com');")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'msg_promo_1', 1, 1, 'sales@shop.com', '2026-01-01');")

        promo_id = conn.execute("SELECT id FROM categories WHERE name = 'promotional';").fetchone()[0]
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (1, ?, 'rule');", (promo_id,))

    service = CategoryLabelSyncService(db)

    mock_provider = MagicMock()
    mock_provider.apply_labels.return_value = {"status": "success", "count": 1}
    monkeypatch.setattr(service.action_engine, "_get_remote_provider", lambda acc_id: mock_provider)

    # 1. Execute sync with remote sync enabled
    res = service.execute_sync(account_id=1, sync_remote=True)
    assert res["labeled_count"] == 1
    assert mock_provider.apply_labels.called
    mock_provider.apply_labels.assert_called_with(["msg_promo_1"], add_labels=["MailGraph/Promotional"])

    # 2. Undo with remote sync enabled
    mock_provider.reset_mock()
    undo_res = service.undo_batch(res["batch_id"], sync_remote=True)
    assert undo_res["undone_count"] == 1
    assert mock_provider.apply_labels.called
    mock_provider.apply_labels.assert_called_with(["msg_promo_1"], remove_labels=["MailGraph/Promotional"])

    # 3. Double undo: second call undos nothing
    mock_provider.reset_mock()
    undo_res_2 = service.undo_batch(res["batch_id"], sync_remote=True)
    assert undo_res_2["undone_count"] == 0
    assert not mock_provider.apply_labels.called


def test_category_sync_unmapped_custom_category(tmp_path):
    db = Database(str(tmp_path / "sync_custom.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'User', 'u@test.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain) VALUES (1, 'consultant@firm.com', 'firm.com');")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'msg_cust_1', 1, 1, 'consultant@firm.com', '2026-01-01');")

        # Custom category not in default map
        conn.execute("INSERT INTO categories (name, description) VALUES ('consulting', 'Consulting work');")
        cust_id = conn.execute("SELECT id FROM categories WHERE name = 'consulting';").fetchone()[0]
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (1, ?, 'rule');", (cust_id,))

    service = CategoryLabelSyncService(db)

    preview = service.preview_sync(account_id=1)
    assert preview["total_messages"] == 1
    assert preview["categories"][0]["category"] == "consulting"
    assert preview["categories"][0]["label"] == "MailGraph/Consulting"

    res = service.execute_sync(account_id=1, sync_remote=False)
    assert res["labeled_count"] == 1

    with db.connect() as conn:
        item = conn.execute("SELECT result_state_json FROM operation_items WHERE operation_id = ?;", (res["operation_ids"][0],)).fetchone()
        assert json.loads(item["result_state_json"]).get("added_label") == "MailGraph/Consulting"


def test_category_sync_idempotency_and_resume(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "sync_idempotent.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'User', 'u@test.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain) VALUES (1, 'bank@nayapay.com', 'nayapay.com');")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'msg_fin_1', 1, 1, 'bank@nayapay.com', '2026-01-01');")

        fin_id = conn.execute("SELECT id FROM categories WHERE name = 'finance';").fetchone()[0]
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (1, ?, 'rule');", (fin_id,))

    service = CategoryLabelSyncService(db)
    mock_provider = MagicMock()
    mock_provider.apply_labels.return_value = {"status": "success", "count": 1}
    monkeypatch.setattr(service.action_engine, "_get_remote_provider", lambda acc_id: mock_provider)

    # 1. First sync labels msg_fin_1
    res1 = service.execute_sync(account_id=1, sync_remote=True)
    assert res1["labeled_count"] == 1
    assert len(res1["operation_ids"]) == 1
    assert mock_provider.apply_labels.call_count == 1
    mock_provider.apply_labels.assert_called_with(["msg_fin_1"], add_labels=["MailGraph/Finance"])

    # 2. Second sync on same account: all messages already labeled, zero duplicate operations/provider calls
    mock_provider.reset_mock()
    res2 = service.execute_sync(account_id=1, sync_remote=True)
    assert res2["labeled_count"] == 0
    assert res2["operation_ids"] == []
    assert not mock_provider.apply_labels.called

    # 3. Add a new message to the finance category
    with db.connect() as conn:
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (2, 1, 'msg_fin_2', 1, 1, 'bank@nayapay.com', '2026-01-02');")
        conn.execute("INSERT INTO message_categories (message_id, category_id, source) VALUES (2, ?, 'rule');", (fin_id,))

    # 4. Third sync: only the 1 new message is labeled (resumes delta)
    mock_provider.reset_mock()
    res3 = service.execute_sync(account_id=1, sync_remote=True)
    assert res3["labeled_count"] == 1
    assert len(res3["operation_ids"]) == 1
    assert mock_provider.apply_labels.call_count == 1
    mock_provider.apply_labels.assert_called_with(["msg_fin_2"], add_labels=["MailGraph/Finance"])


