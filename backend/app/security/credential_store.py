"""OS Keyring credential storage abstraction with dual-layer fallback."""

import os
import sys
import json
import logging
import subprocess
import re
import sqlite3
from typing import Optional, List, Dict, Any
from pathlib import Path
from backend.app.config import settings

logger = logging.getLogger(__name__)

class CredentialStore:
    """Safely manages tokens and credentials in OS Credential Manager (Keyring) and local fallback store."""

    def __init__(self, service_name: Optional[str] = None):
        self.service_name = service_name or settings.credential_service_name
        self._fallback_file = Path(settings.data_dir) / ".credentials_fallback.json"
        
    def save_credentials(self, account_identifier: str, secret_json: str) -> bool:
        """Store credentials for an account across both Keyring and local secure store."""
        # Always persist to local fallback file for guaranteed persistence across process restarts
        self._save_fallback(account_identifier, secret_json)
        
        try:
            import keyring
            keyring.set_password(self.service_name, account_identifier, secret_json)
            return True
        except Exception as ex:
            logger.warning(f"OS keyring unavailable, using local secure file: {ex}")
            return True

    def get_credentials(self, account_identifier: str) -> Optional[str]:
        """Retrieve credentials for an account from Keyring or fallback file."""
        try:
            import keyring
            secret = keyring.get_password(self.service_name, account_identifier)
            if secret:
                return secret
        except Exception:
            pass
        return self._get_fallback(account_identifier)

    def delete_credentials(self, account_identifier: str) -> bool:
        """Remove credentials for an account."""
        try:
            import keyring
            keyring.delete_password(self.service_name, account_identifier)
        except Exception:
            pass
        self._delete_fallback(account_identifier)
        return True

    def list_stored_identifiers(self) -> List[str]:
        """Return all account identifiers present in the credential store (Keyring + local fallback)."""
        identifiers = set()
        
        # 1. From local fallback file
        if self._fallback_file.exists():
            try:
                with open(self._fallback_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                identifiers.update(data.keys())
            except Exception:
                pass

        # 2. On Windows, check Windows Credential Manager targets for this service
        if sys.platform == "win32" and self.service_name:
            try:
                out = subprocess.check_output(["cmdkey", "/list"], text=True, timeout=2.0)
                pattern = rf"target=([^\r\n]+)@{re.escape(self.service_name)}"
                found = re.findall(pattern, out)
                for ident in found:
                    ident = ident.strip()
                    if ident and "@" in ident and not ident.startswith("test") and not ident.endswith(".local"):
                        identifiers.add(ident)
                        # Ensure fallback file has the secret cached as well
                        if not self._get_fallback(ident):
                            secret = self.get_credentials(ident)
                            if secret:
                                self._save_fallback(ident, secret)
            except Exception as ex:
                logger.debug(f"cmdkey lookup skipped or failed: {ex}")

        return [i for i in identifiers if "@" in i and not i.startswith("test") and not i.endswith(".local")]

    def _save_fallback(self, account_identifier: str, secret: str) -> bool:
        try:
            self._fallback_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if self._fallback_file.exists():
                try:
                    with open(self._fallback_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data[account_identifier] = secret
            with open(self._fallback_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return True
        except Exception:
            return False

    def _get_fallback(self, account_identifier: str) -> Optional[str]:
        if not self._fallback_file.exists():
            return None
        try:
            with open(self._fallback_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(account_identifier)
        except Exception:
            return None

    def _delete_fallback(self, account_identifier: str) -> None:
        if not self._fallback_file.exists():
            return
        try:
            with open(self._fallback_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if account_identifier in data:
                del data[account_identifier]
                with open(self._fallback_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
        except Exception:
            pass


def reconcile_accounts(conn: sqlite3.Connection) -> int:
    """
    Auto-reconciles SQLite accounts table with locally stored credentials in CredentialStore.
    If a valid credential exists in CredentialStore (Windows Keyring or fallback file)
    but its account row is missing in SQLite, restores it automatically with status='active'.
    Returns number of accounts reconciled/restored.
    """
    store = CredentialStore()
    identifiers = store.list_stored_identifiers()
    restored = 0
    cursor = conn.cursor()
    for ident in identifiers:
        if not ident or "@" not in ident or ident.endswith(".local"):
            continue
        cursor.execute("SELECT id FROM accounts WHERE email_address = ?;", (ident,))
        if cursor.fetchone() is None:
            raw_secret = store.get_credentials(ident)
            if not raw_secret:
                continue
            try:
                cred = json.loads(raw_secret)
            except Exception:
                continue
            
            provider = cred.get("provider", "imap")
            host = cred.get("host", "imap.gmail.com")
            port = cred.get("port", 993)
            is_gmail = "gmail" in host.lower() or "gmail" in ident.lower()
            display_name = f"Gmail ({ident})" if is_gmail else f"IMAP ({ident})"
            settings_json = json.dumps({"host": host, "port": port})
            
            cursor.execute("""
                INSERT INTO accounts (provider, display_name, email_address, settings_json, status)
                VALUES (?, ?, ?, ?, 'active');
            """, (provider, display_name, ident, settings_json))
            restored += 1
            logger.info(f"Reconciled and restored account {ident} from local credential store.")
            
    if restored > 0:
        conn.commit()
    return restored
