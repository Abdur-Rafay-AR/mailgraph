"""Database schema definitions for MailGraph."""

ALL_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT NOT NULL, -- 'gmail', 'imap', 'mbox', 'synthetic'
        display_name TEXT NOT NULL,
        email_address TEXT NOT NULL,
        provider_account_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_sync_at TEXT,
        sync_cursor TEXT,
        status TEXT NOT NULL DEFAULT 'active', -- 'active', 'paused', 'error', 'disconnected'
        settings_json TEXT NOT NULL DEFAULT '{}'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        provider_folder_id TEXT NOT NULL,
        name TEXT NOT NULL,
        folder_type TEXT NOT NULL DEFAULT 'generic', -- 'inbox', 'sent', 'trash', 'archive', 'drafts', 'spam', 'generic'
        parent_id INTEGER,
        is_special INTEGER NOT NULL DEFAULT 0,
        last_scanned_at TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
        FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE SET NULL,
        UNIQUE(account_id, provider_folder_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS senders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        normalized_address TEXT NOT NULL UNIQUE,
        display_name TEXT,
        domain TEXT NOT NULL,
        first_seen_at TEXT,
        last_seen_at TEXT,
        user_category TEXT,
        is_protected INTEGER NOT NULL DEFAULT 0,
        notes TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS threads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        provider_thread_id TEXT,
        subject_normalized TEXT,
        first_message_at TEXT,
        last_message_at TEXT,
        message_count INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        provider_message_id TEXT NOT NULL,
        provider_thread_id TEXT,
        folder_id INTEGER,
        thread_id INTEGER,
        message_id_header TEXT,
        in_reply_to TEXT,
        references_header TEXT,
        subject TEXT,
        sender_name TEXT,
        sender_address TEXT NOT NULL,
        sender_id INTEGER,
        sent_at TEXT,
        received_at TEXT NOT NULL,
        is_read INTEGER NOT NULL DEFAULT 0,
        is_starred INTEGER NOT NULL DEFAULT 0,
        is_important INTEGER NOT NULL DEFAULT 0,
        has_attachments INTEGER NOT NULL DEFAULT 0,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        snippet TEXT,
        body_text TEXT,
        body_indexed INTEGER NOT NULL DEFAULT 0,
        content_hash TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
        FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL,
        FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE SET NULL,
        FOREIGN KEY (sender_id) REFERENCES senders(id) ON DELETE SET NULL,
        UNIQUE(account_id, provider_message_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS message_addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        address TEXT NOT NULL,
        display_name TEXT,
        role TEXT NOT NULL, -- 'from', 'to', 'cc', 'bcc', 'reply_to'
        FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        provider_attachment_id TEXT,
        filename TEXT NOT NULL,
        mime_type TEXT,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        content_hash TEXT,
        local_path TEXT,
        is_inline INTEGER NOT NULL DEFAULT 0,
        content_available INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        is_system INTEGER NOT NULL DEFAULT 1,
        color TEXT NOT NULL DEFAULT '#64748b'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS message_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        category_id INTEGER NOT NULL,
        source TEXT NOT NULL DEFAULT 'rule', -- 'rule', 'model', 'user'
        confidence REAL NOT NULL DEFAULT 1.0,
        reason TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
        UNIQUE(message_id, category_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS protection_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER,
        rule_type TEXT NOT NULL, -- 'sender', 'domain', 'message', 'thread', 'query'
        rule_value TEXT NOT NULL,
        reason TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        enabled INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS saved_queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        query_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        operation_type TEXT NOT NULL, -- 'trash', 'archive', 'label', 'delete'
        query_snapshot_json TEXT NOT NULL,
        target_count INTEGER NOT NULL DEFAULT 0,
        completed_count INTEGER NOT NULL DEFAULT 0,
        failed_count INTEGER NOT NULL DEFAULT 0,
        skipped_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'previewed', 'running', 'completed', 'completed_with_errors', 'undone', 'cancelled'
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        completed_at TEXT,
        backup_manifest_path TEXT,
        undo_status TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS operation_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        provider_message_id TEXT NOT NULL,
        original_state_json TEXT NOT NULL DEFAULT '{}',
        result_state_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'success', 'failed', 'skipped', 'undone'
        error_code TEXT,
        error_message TEXT,
        FOREIGN KEY (operation_id) REFERENCES operations(id) ON DELETE CASCADE,
        FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        completed_at TEXT,
        status TEXT NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed', 'cancelled'
        scanned_count INTEGER NOT NULL DEFAULT 0,
        inserted_count INTEGER NOT NULL DEFAULT 0,
        updated_count INTEGER NOT NULL DEFAULT 0,
        failed_count INTEGER NOT NULL DEFAULT 0,
        checkpoint_json TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER,
        insight_type TEXT NOT NULL, -- 'unreplied_thread', 'zombie_subscription', 'volume_spike', 'large_attachments', 'storage_dominator'
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        evidence_json TEXT NOT NULL DEFAULT '{}',
        confidence REAL NOT NULL DEFAULT 1.0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        dismissed_at TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    );
    """
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_messages_account ON messages(account_id);",
    "CREATE INDEX IF NOT EXISTS idx_messages_folder ON messages(folder_id);",
    "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);",
    "CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_address);",
    "CREATE INDEX IF NOT EXISTS idx_messages_received ON messages(received_at);",
    "CREATE INDEX IF NOT EXISTS idx_messages_read ON messages(is_read);",
    "CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);",
    "CREATE INDEX IF NOT EXISTS idx_messages_sender_folder ON messages(sender_id, folder_id);",
    "CREATE INDEX IF NOT EXISTS idx_folders_type ON folders(folder_type);",
    "CREATE INDEX IF NOT EXISTS idx_senders_domain ON senders(domain);",
    "CREATE INDEX IF NOT EXISTS idx_attachments_msg ON attachments(message_id);",
    "CREATE INDEX IF NOT EXISTS idx_attachments_hash ON attachments(content_hash);",
    "CREATE INDEX IF NOT EXISTS idx_addr_msg ON message_addresses(message_id);",
    "CREATE INDEX IF NOT EXISTS idx_msg_cat_msg ON message_categories(message_id);",
    "CREATE INDEX IF NOT EXISTS idx_msg_cat_composite ON message_categories(message_id, category_id);"
]

FTS_TABLES = [
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        message_id UNINDEXED,
        subject,
        snippet,
        body_text,
        tokenize='unicode61'
    );
    """
]
