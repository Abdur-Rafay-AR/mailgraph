"""OS Keyring credential storage abstraction with fallback."""

import os
import json
import logging
from typing import Optional
from pathlib import Path
from backend.app.config import settings

logger = logging.getLogger(__name__)

class CredentialStore:
    """Safely manages tokens and credentials in OS Credential Manager (Keyring)."""

    def __init__(self, service_name: str = "MailGraph"):
        self.service_name = service_name
        self._fallback_file = Path(settings.data_dir) / ".credentials_fallback.json"
        
    def save_credentials(self, account_identifier: str, secret_json: str) -> bool:
        """Store credentials for an account."""
        try:
            import keyring
            keyring.set_password(self.service_name, account_identifier, secret_json)
            return True
        except Exception as ex:
            logger.warning(f"OS keyring unavailable, using local secure file: {ex}")
            return self._save_fallback(account_identifier, secret_json)

    def get_credentials(self, account_identifier: str) -> Optional[str]:
        """Retrieve credentials for an account."""
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

    def _save_fallback(self, account_identifier: str, secret: str) -> bool:
        try:
            data = {}
            if self._fallback_file.exists():
                with open(self._fallback_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
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
