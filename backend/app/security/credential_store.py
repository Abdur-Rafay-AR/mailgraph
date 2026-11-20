"""OS Keyring credential storage abstraction with encrypted local fallback."""

import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken

from backend.app.config import settings

logger = logging.getLogger(__name__)


class CredentialStore:
    """Safely manages tokens and credentials in OS Credential Manager (Keyring) and encrypted local fallback."""

    _ENC_PREFIX = "enc:v1:"

    def __init__(self, service_name: Optional[str] = None):
        self.service_name = service_name or settings.credential_service_name
        data_dir = Path(settings.data_dir)
        self._fallback_file = data_dir / ".credentials_fallback.json"
        self._key_file = data_dir / ".credentials.key"

    def _get_cipher(self) -> Fernet:
        """Load or generate a local symmetric key for fallback credential encryption."""
        self._key_file.parent.mkdir(parents=True, exist_ok=True)
        if self._key_file.exists():
            raw_key = self._key_file.read_bytes().strip()
            try:
                return Fernet(raw_key)
            except Exception:
                pass
        key = Fernet.generate_key()
        self._key_file.write_bytes(key)
        if sys.platform != "win32":
            try:
                os.chmod(self._key_file, 0o600)
            except OSError:
                pass
        return Fernet(key)

    def _encrypt_secret(self, secret: str) -> str:
        try:
            token = self._get_cipher().encrypt(secret.encode("utf-8")).decode("ascii")
            return f"{self._ENC_PREFIX}{token}"
        except Exception as ex:
            logger.warning("Failed to encrypt fallback credential: %s", ex)
            return secret

    def _decrypt_secret(self, stored: str) -> Optional[str]:
        if not stored.startswith(self._ENC_PREFIX):
            # Support reading legacy plaintext fallback entries seamlessly
            return stored
        token = stored[len(self._ENC_PREFIX):].encode("ascii")
        try:
            return self._get_cipher().decrypt(token).decode("utf-8")
        except (InvalidToken, Exception) as ex:
            logger.warning("Failed to decrypt fallback credential: %s", ex)
            return None

    def save_credentials(self, account_identifier: str, secret_json: str) -> bool:
        """Store credentials for an account in OS Keyring and encrypted local fallback store."""
        keyring_ok = False
        try:
            import keyring
            keyring.set_password(self.service_name, account_identifier, secret_json)
            keyring_ok = True
        except Exception as ex:
            logger.warning("OS keyring unavailable, using encrypted local fallback: %s", ex)

        # Persist encrypted fallback for resilience across restarts / headless environments
        fallback_ok = self._save_fallback(account_identifier, secret_json)
        return keyring_ok or fallback_ok

    def get_credentials(self, account_identifier: str) -> Optional[str]:
        """Retrieve credentials for an account from Keyring or encrypted fallback file."""
        try:
            import keyring
            secret = keyring.get_password(self.service_name, account_identifier)
            if secret:
                return secret
        except Exception as ex:
            logger.debug("Keyring lookup failed for %s: %s", account_identifier, ex)
        return self._get_fallback(account_identifier)

    def delete_credentials(self, account_identifier: str) -> bool:
        """Remove credentials for an account from both Keyring and local fallback."""
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

        if self._fallback_file.exists():
            try:
                with open(self._fallback_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                identifiers.update(data.keys())
            except Exception as ex:
                logger.debug("Failed to read fallback identifiers: %s", ex)

        if sys.platform == "win32" and self.service_name:
            try:
                out = subprocess.check_output(["cmdkey", "/list"], text=True, timeout=2.0)
                pattern = rf"target=([^\r\n]+)@{re.escape(self.service_name)}"
                found = re.findall(pattern, out)
                for ident in found:
                    ident = ident.strip()
                    if ident and "@" in ident and not ident.startswith("test") and not ident.endswith(".local"):
                        identifiers.add(ident)
                        if not self._get_fallback(ident):
                            secret = self.get_credentials(ident)
                            if secret:
                                self._save_fallback(ident, secret)
            except Exception as ex:
                logger.debug("cmdkey lookup skipped or failed: %s", ex)

        return [i for i in identifiers if "@" in i and not i.startswith("test") and not i.endswith(".local")]

    def _save_fallback(self, account_identifier: str, secret: str) -> bool:
        try:
            self._fallback_file.parent.mkdir(parents=True, exist_ok=True)
            data: Dict[str, str] = {}
            if self._fallback_file.exists():
                try:
                    with open(self._fallback_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data[account_identifier] = self._encrypt_secret(secret)
            with open(self._fallback_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
            if sys.platform != "win32":
                try:
                    os.chmod(self._fallback_file, 0o600)
                except OSError:
                    pass
            return True
        except Exception as ex:
            logger.warning("Failed to save fallback credentials: %s", ex)
            return False

    def _get_fallback(self, account_identifier: str) -> Optional[str]:
        if not self._fallback_file.exists():
            return None
        try:
            with open(self._fallback_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get(account_identifier)
            if not raw:
                return None
            return self._decrypt_secret(raw)
        except Exception as ex:
            logger.debug("Failed to read fallback credential: %s", ex)
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
        except Exception as ex:
            logger.debug("Failed to delete fallback credential: %s", ex)


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
