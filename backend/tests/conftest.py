"""Pytest test suite configuration and database isolation."""

import os
import tempfile
from pathlib import Path

# Create an isolated temporary test directory
test_dir = Path(tempfile.gettempdir()) / "mailgraph_test_suite"
test_dir.mkdir(parents=True, exist_ok=True)
test_db = test_dir / "test_mailgraph.db"

# Force environment overrides BEFORE backend modules load
os.environ["MAILGRAPH_DATA_DIR"] = str(test_dir)
os.environ["MAILGRAPH_DB_PATH"] = str(test_db)
os.environ["MAILGRAPH_CREDENTIAL_SERVICE_NAME"] = "MailGraphTest"
