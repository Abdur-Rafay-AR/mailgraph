"""Database connection and connection pool management."""

import sqlite3
from pathlib import Path
from typing import Generator, Optional
from contextlib import contextmanager

from backend.app.config import settings
from backend.app.db.migrations import run_migrations

class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.db_path
        self._ensure_dir()
        
    def _ensure_dir(self):
        if self.db_path != ":memory:":
            p = Path(self.db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            
    def get_connection(self) -> sqlite3.Connection:
        """Create a configured SQLite connection."""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0
        )
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        if self.db_path != ":memory:":
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
            cursor.execute("PRAGMA temp_store = MEMORY;")
        return conn

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections with transaction commit/rollback."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Run schema migrations on the database."""
        with self.connect() as conn:
            run_migrations(conn)

# Global database instance
_default_db: Optional[Database] = None

def get_database() -> Database:
    global _default_db
    if _default_db is None:
        _default_db = Database()
        _default_db.initialize()
    return _default_db

def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency for obtaining a db connection."""
    db = get_database()
    with db.connect() as conn:
        yield conn
