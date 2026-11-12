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
