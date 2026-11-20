import json
from unittest.mock import MagicMock
import pytest
from backend.app.db.database import Database
from backend.app.db.migrations import run_migrations
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.providers.synthetic import SyntheticMailboxGenerator
from backend.app.search.query_compiler import QueryAST, QueryCondition
from backend.app.actions.engine import ActionEngine

def setup_test_mailbox():
    db = Database(db_path=":memory:")
    with db.connect() as conn:
        run_migrations(conn)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (provider, display_name, email_address) VALUES ('synthetic', 'Test Acc', 'user@test');")
        account_id = cursor.lastrowid
        
        # Set up a trash folder and archive folder
        cursor.execute("INSERT INTO folders (account_id, provider_folder_id, name, folder_type) VALUES (?, 'trash', 'Trash', 'trash');", (account_id,))
        cursor.execute("INSERT INTO folders (account_id, provider_folder_id, name, folder_type) VALUES (?, 'archive', 'Archive', 'archive');", (account_id,))
        
    generator = SyntheticMailboxGenerator(seed=101)
    pipeline = IngestionPipeline(db)
    pipeline.ingest_messages(account_id, generator.generate(count=40))
    return db, account_id

def test_preview_and_execute_trash_operation():
    db, account_id = setup_test_mailbox()
    engine = ActionEngine(db)
    
    # Query targets from a specific sender
    ast = QueryAST(
        account_ids=[account_id],
        all=[QueryCondition(field="sender_domain", op="eq", value="substack.com")]
    )
    
    # 1. Preview
    preview = engine.calculate_preview(account_id, "trash", ast)
    assert preview.target_count > 0
    assert len(preview.samples) > 0
    assert preview.operation_type == "trash"
    
    # 2. Execute
    operation_id = engine.execute_action(account_id, "trash", ast)
    assert operation_id > 0
    
    # Verify messages moved to trash
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT status, completed_count, failed_count FROM operations WHERE id = ?;
        """, (operation_id,))
        row = cursor.fetchone()
        assert row[0] == "completed"
        assert row[1] == preview.target_count
        assert row[2] == 0
        
    # 3. Undo
    undo_res = engine.undo_operation(operation_id)
    assert undo_res["status"] == "undone"
    assert undo_res["restored_count"] == preview.target_count


def test_label_preview_execution_and_undo(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.initialize()
    
    # Seed account and messages
    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'Test', 't@e.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain, is_protected) VALUES (1, 'news@digest.com', 'digest.com', 0);")
        conn.execute("INSERT INTO senders (id, normalized_address, domain, is_protected) VALUES (2, 'safe@google.com', 'google.com', 1);")
        
        # Message 1: unprotected
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'p_1', 1, 1, 'news@digest.com', '2026-01-01');")
        # Message 2: protected
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (2, 1, 'p_2', 1, 2, 'safe@google.com', '2026-01-01');")

    engine = ActionEngine(db)
    ast = QueryAST(version=1, exclude_protected=True)

    # 1. Preview
    preview = engine.calculate_preview(account_id=1, operation_type="label", ast=ast, label_name="MailGraph/Newsletters")
    assert preview.operation_type == "label"
    assert preview.target_count == 1
    assert preview.protected_excluded_count == 1
    assert preview.reversible is True

    # Also test preview with exclude_protected=False: normalization must enforce exclude_protected=True for label
    ast_unsafe = QueryAST(version=1, exclude_protected=False)
    preview_unsafe = engine.calculate_preview(account_id=1, operation_type="label", ast=ast_unsafe, label_name="MailGraph/Newsletters")
    assert preview_unsafe.target_count == 1
    assert preview_unsafe.protected_excluded_count == 1

    # 2. Execute
    op_id = engine.execute_action(account_id=1, operation_type="label", ast=ast, label_name="MailGraph/Newsletters", sync_remote=False)
    assert op_id > 0
    
    with db.connect() as conn:
        row = conn.execute("SELECT status, target_count, completed_count FROM operations WHERE id = ?;", (op_id,)).fetchone()
        assert row["status"] == "completed"
        assert row["completed_count"] == 1
        item = conn.execute("SELECT result_state_json FROM operation_items WHERE operation_id = ?;", (op_id,)).fetchone()
        assert json.loads(item["result_state_json"]).get("added_label") == "MailGraph/Newsletters"

    # 3. Undo
    undo_res = engine.undo_operation(op_id)
    assert undo_res["status"] == "undone"
    assert undo_res["restored_count"] == 1


def test_label_realtime_protection_revalidation(tmp_path):
    """Verify that protection added after preview is enforced at execution time."""
    db = Database(str(tmp_path / "test_revalidation.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'Test', 't@e.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain, is_protected) VALUES (1, 'a@test.com', 'test.com', 0);")
        conn.execute("INSERT INTO senders (id, normalized_address, domain, is_protected) VALUES (2, 'b@test.com', 'test.com', 0);")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'p_1', 1, 1, 'a@test.com', '2026-01-01');")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (2, 1, 'p_2', 1, 2, 'b@test.com', '2026-01-01');")

    engine = ActionEngine(db)
    ast = QueryAST(version=1, exclude_protected=True)

    # 1. Preview shows 2 targets
    preview = engine.calculate_preview(account_id=1, operation_type="label", ast=ast, label_name="MailGraph/Work")
    assert preview.target_count == 2
    assert preview.protected_excluded_count == 0

    # 2. User marks sender 2 as protected before execution
    with db.connect() as conn:
        conn.execute("UPDATE senders SET is_protected = 1 WHERE id = 2;")

    # 3. Execution should re-validate and exclude sender 2
    op_id = engine.execute_action(account_id=1, operation_type="label", ast=ast, label_name="MailGraph/Work", sync_remote=False)
    assert op_id > 0

    with db.connect() as conn:
        row = conn.execute("SELECT target_count, completed_count FROM operations WHERE id = ?;", (op_id,)).fetchone()
        assert row["target_count"] == 1
        assert row["completed_count"] == 1
        items = conn.execute("SELECT message_id FROM operation_items WHERE operation_id = ?;", (op_id,)).fetchall()
        assert len(items) == 1
        assert items[0]["message_id"] == 1

    # 4. Even if caller attempts exclude_protected=False for label, protection is strictly enforced
    ast_unsafe = QueryAST(version=1, exclude_protected=False)
    op_id_2 = engine.execute_action(account_id=1, operation_type="label", ast=ast_unsafe, label_name="MailGraph/Work", sync_remote=False)
    with db.connect() as conn:
        row2 = conn.execute("SELECT target_count FROM operations WHERE id = ?;", (op_id_2,)).fetchone()
        # Message 2 from protected sender 2 must still be excluded
        assert row2["target_count"] == 1


def test_label_remote_sync_and_undo(tmp_path, monkeypatch):
    """Verify that remote provider apply_labels is invoked on execute and undo."""
    db = Database(str(tmp_path / "test_remote.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'Test', 't@e.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain, is_protected) VALUES (1, 'promo@site.com', 'site.com', 0);")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'p_remote_1', 1, 1, 'promo@site.com', '2026-01-01');")

    mock_provider = MagicMock()
    mock_provider.apply_labels.return_value = {"status": "success", "count": 1}
    engine = ActionEngine(db)
    monkeypatch.setattr(engine, "_get_remote_provider", lambda acc_id: mock_provider)

    ast = QueryAST(version=1, exclude_protected=True)

    # Execute with remote sync enabled
    op_id = engine.execute_action(account_id=1, operation_type="label", ast=ast, label_name="MailGraph/Promotional", sync_remote=True)
    assert mock_provider.apply_labels.called
    mock_provider.apply_labels.assert_called_with(["p_remote_1"], add_labels=["MailGraph/Promotional"])

    # Undo with remote sync enabled
    mock_provider.reset_mock()
    undo_res = engine.undo_operation(op_id, sync_remote=True)
    assert undo_res["status"] == "undone"
    assert mock_provider.apply_labels.called
    mock_provider.apply_labels.assert_called_with(["p_remote_1"], remove_labels=["MailGraph/Promotional"])

    # Undo with sync_remote=False should NOT invoke remote provider
    mock_provider.reset_mock()
    undo_res_no_sync = engine.undo_operation(op_id, sync_remote=False)
    assert undo_res_no_sync["status"] == "undone"
    assert not mock_provider.apply_labels.called


def test_label_batch_id_and_snapshot(tmp_path):
    """Verify that batch_id is captured in query_snapshot_json when provided."""
    db = Database(str(tmp_path / "test_batch.db"))
    db.initialize()

    with db.connect() as conn:
        conn.execute("INSERT INTO accounts (id, provider, display_name, email_address) VALUES (1, 'synthetic', 'Test', 't@e.com');")
        conn.execute("INSERT INTO folders (id, account_id, provider_folder_id, name) VALUES (1, 1, 'INBOX', 'INBOX');")
        conn.execute("INSERT INTO senders (id, normalized_address, domain, is_protected) VALUES (1, 'test@box.com', 'box.com', 0);")
        conn.execute("INSERT INTO messages (id, account_id, provider_message_id, folder_id, sender_id, sender_address, received_at) VALUES (1, 1, 'p_b1', 1, 1, 'test@box.com', '2026-01-01');")

    engine = ActionEngine(db)
    ast = QueryAST(version=1)

    op_id = engine.execute_action(
        account_id=1,
        operation_type="label",
        ast=ast,
        label_name="MailGraph/Finance",
        batch_id="batch-uuid-123",
        sync_remote=False
    )
    assert op_id > 0

    with db.connect() as conn:
        row = conn.execute("SELECT query_snapshot_json FROM operations WHERE id = ?;", (op_id,)).fetchone()
        snapshot = json.loads(row["query_snapshot_json"])
        assert snapshot.get("batch_id") == "batch-uuid-123"
        assert snapshot.get("label_name") == "MailGraph/Finance"


def test_label_validation_errors(tmp_path):
    """Verify validation errors for missing label_name and invalid operation_type."""
    db = Database(str(tmp_path / "test_err.db"))
    db.initialize()
    engine = ActionEngine(db)
    ast = QueryAST(version=1)

    # Missing label_name
    with pytest.raises(ValueError, match="label_name is required"):
        engine.execute_action(account_id=1, operation_type="label", ast=ast, label_name="")

    with pytest.raises(ValueError, match="label_name is required"):
        engine.execute_action(account_id=1, operation_type="label", ast=ast, label_name=None)

    # Unsupported operation_type in preview
    with pytest.raises(ValueError, match="Unsupported operation type"):
        engine.calculate_preview(account_id=1, operation_type="unknown_op", ast=ast)

    # Unsupported operation_type in execute
    with pytest.raises(ValueError, match="Unsupported operation type"):
        engine.execute_action(account_id=1, operation_type="unknown_op", ast=ast)



