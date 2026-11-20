"""Official Gmail API provider with OAuth loopback flow and least privilege scopes."""

import base64
import json
import logging
import random
import time
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import quote

import requests

from backend.app.ingestion.mime_parser import MimeParser, ParsedEmail
from backend.app.providers.base import AbstractMailProvider, ProviderCapabilities, ProviderFolder
from backend.app.security.credential_store import CredentialStore

logger = logging.getLogger(__name__)

READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"


class GmailProvider(AbstractMailProvider):
    """Google Gmail API adapter using OAuth 2.0 with loopback consent."""

    def __init__(
        self,
        account_email: str = "",
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token_dict: Optional[Dict[str, Any]] = None,
    ):
        self.account_email = account_email
        self.client_id = client_id
        self.client_secret = client_secret
        self.credential_store = CredentialStore()
        self.parser = MimeParser()
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._label_cache: Dict[str, str] = {}

        if token_dict:
            self._access_token = token_dict.get("access_token")
            self._refresh_token = token_dict.get("refresh_token")
            self.client_id = self.client_id or token_dict.get("client_id")
            self.client_secret = self.client_secret or token_dict.get("client_secret")

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_archive=True,
            supports_trash=True,
            supports_undo=True,
            supports_labels=True,
            is_read_only=False,
            provider_name="gmail"
        )

    def is_authenticated(self) -> bool:
        """Check if active tokens exist in secure storage."""
        if self._access_token:
            return True
        creds_json = self.credential_store.get_credentials(self.account_email)
        return bool(creds_json)

    def get_oauth_url(self, redirect_uri: str = "http://127.0.0.1:28491/api/accounts/gmail/callback") -> str:
        """Generate Google OAuth consent URL."""
        if not self.client_id:
            raise ValueError("Gmail client_id must be provided to initiate OAuth.")

        params = [
            f"client_id={quote(self.client_id, safe='')}",
            f"redirect_uri={quote(redirect_uri, safe=':/')}",
            "response_type=code",
            f"scope={MODIFY_SCOPE}",
            "access_type=offline",
            "prompt=consent",
            f"state={quote(self.account_email, safe='@.')}"
        ]
        return f"https://accounts.google.com/o/oauth2/v2/auth?{'&'.join(params)}"

    def connect(self) -> bool:
        if self._access_token:
            return True
        if not self.account_email:
            return False
        creds_str = self.credential_store.get_credentials(self.account_email)
        if not creds_str:
            return False
        try:
            creds = json.loads(creds_str)
            self._access_token = creds.get("access_token")
            self._refresh_token = creds.get("refresh_token") or self._refresh_token
            self.client_id = self.client_id or creds.get("client_id")
            self.client_secret = self.client_secret or creds.get("client_secret")
            if not self._access_token and self._refresh_token:
                return self._refresh_access_token()
            return bool(self._access_token)
        except Exception as ex:
            logger.warning("Failed to load Gmail OAuth credentials: %s", ex)
            return False

    def disconnect(self) -> None:
        """No persistent socket to close for REST API provider."""
        return None

    def _refresh_access_token(self) -> bool:
        """Attempt to refresh an expired OAuth2 access token using stored refresh_token."""
        if not (self._refresh_token and self.client_id and self.client_secret):
            return False
        try:
            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=15.0,
            )
            if resp.status_code != 200:
                logger.warning("Gmail token refresh failed: %s %s", resp.status_code, resp.text)
                return False
            token_data = resp.json()
            new_access = token_data.get("access_token")
            if not new_access:
                return False
            self._access_token = new_access
            if self.account_email:
                existing = {}
                raw = self.credential_store.get_credentials(self.account_email)
                if raw:
                    try:
                        existing = json.loads(raw)
                    except Exception:
                        existing = {}
                existing.update({
                    "provider": "gmail",
                    "access_token": new_access,
                    "refresh_token": self._refresh_token,
                })
                self.credential_store.save_credentials(self.account_email, json.dumps(existing))
            return True
        except Exception as ex:
            logger.warning("Error refreshing Gmail access token: %s", ex)
            return False

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }

    def refresh_labels(self) -> Dict[str, str]:
        """Query Gmail API for existing labels, updating local name->id cache."""
        if not self.connect():
            raise ConnectionError(f"Account {self.account_email} is not authenticated with Gmail OAuth.")
        headers = self._get_headers()
        url = "https://gmail.googleapis.com/gmail/v1/users/me/labels"
        resp = requests.get(url, headers=headers, timeout=30.0)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch Gmail labels: {resp.status_code} {resp.text}")
        data = resp.json()
        labels = data.get("labels", [])
        self._label_cache = {lbl["name"]: lbl["id"] for lbl in labels if "name" in lbl and "id" in lbl}
        return self._label_cache

    def list_labels(self) -> List[str]:
        """List existing custom and system label names from Gmail."""
        return list(self.refresh_labels().keys())

    def resolve_or_create_label_id(self, display_name: str, create: bool = True) -> Optional[str]:
        """Resolve a human-readable label name to a Gmail label ID, optionally creating it if missing."""
        if display_name in self._label_cache:
            return self._label_cache[display_name]
        if display_name in self._label_cache.values():
            return display_name

        self.refresh_labels()
        if display_name in self._label_cache:
            return self._label_cache[display_name]
        if display_name in self._label_cache.values():
            return display_name

        if not create:
            return None

        url = "https://gmail.googleapis.com/gmail/v1/users/me/labels"
        headers = self._get_headers()
        payload = {
            "name": display_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show"
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30.0)
        if resp.status_code in (200, 201):
            created_label = resp.json()
            label_id = created_label["id"]
            self._label_cache[display_name] = label_id
            return label_id
        elif resp.status_code == 409:
            # 409 Conflict: label already created on server
            self.refresh_labels()
            if display_name in self._label_cache:
                return self._label_cache[display_name]
            raise RuntimeError(f"Label '{display_name}' reported 409 Conflict, but could not be resolved after refresh.")
        else:
            raise RuntimeError(f"Failed to create Gmail label '{display_name}': {resp.status_code} {resp.text}")

    def apply_labels(
        self,
        provider_message_ids: List[str],
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Apply or remove labels on target messages on Gmail via batchModify REST API."""
        if not provider_message_ids:
            return {"status": "success", "count": 0}

        if not add_labels and not remove_labels:
            return {"status": "success", "count": len(provider_message_ids)}

        if not self.connect():
            raise ConnectionError(f"Account {self.account_email} is not authenticated with Gmail OAuth.")

        add_ids = [
            lbl_id
            for lbl in (add_labels or [])
            if (lbl_id := self.resolve_or_create_label_id(lbl, create=True)) is not None
        ]
        remove_ids = [
            lbl_id
            for lbl in (remove_labels or [])
            if (lbl_id := self.resolve_or_create_label_id(lbl, create=False)) is not None
        ]

        batch_size = 1000
        headers = self._get_headers()
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/batchModify"

        for i in range(0, len(provider_message_ids), batch_size):
            chunk = provider_message_ids[i:i + batch_size]
            payload = {
                "ids": chunk,
                "addLabelIds": add_ids,
                "removeLabelIds": remove_ids
            }
            max_retries = 3
            backoff_base = 0.5
            cache_busted = False
            success = False
            for attempt in range(max_retries + 1):
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=30.0)
                except (requests.ConnectionError, requests.Timeout) as ex:
                    if attempt < max_retries:
                        sleep_time = backoff_base * (2 ** attempt) + random.uniform(0.0, 0.25)
                        time.sleep(sleep_time)
                        continue
                    else:
                        raise RuntimeError(f"Gmail batchModify network error after {max_retries} retries: {ex}") from ex

                if resp.status_code in (200, 204):
                    success = True
                    break
                elif resp.status_code == 404 and not cache_busted:
                    # Cache busting: refresh labels and re-resolve in case of stale label ID
                    cache_busted = True
                    self.refresh_labels()
                    add_ids = [
                        lbl_id
                        for lbl in (add_labels or [])
                        if (lbl_id := self.resolve_or_create_label_id(lbl, create=True)) is not None
                    ]
                    remove_ids = [
                        lbl_id
                        for lbl in (remove_labels or [])
                        if (lbl_id := self.resolve_or_create_label_id(lbl, create=False)) is not None
                    ]
                    payload["addLabelIds"] = add_ids
                    payload["removeLabelIds"] = remove_ids
                    continue
                elif resp.status_code in (429, 503):
                    if attempt < max_retries:
                        sleep_time = backoff_base * (2 ** attempt) + random.uniform(0.0, 0.25)
                        time.sleep(sleep_time)
                        continue
                    else:
                        raise RuntimeError(f"Gmail batchModify failed due to rate limiting/overload: {resp.status_code} {resp.text}")
                else:
                    raise RuntimeError(f"Gmail batchModify failed: {resp.status_code} {resp.text}")

            if not success:
                raise RuntimeError("Gmail batchModify failed after all retry attempts.")

        return {"status": "success", "count": len(provider_message_ids)}



    def list_folders(self) -> List[ProviderFolder]:
        return [
            ProviderFolder(id="INBOX", name="Inbox", folder_type="inbox", is_special=True),
            ProviderFolder(id="TRASH", name="Trash", folder_type="trash", is_special=True),
            ProviderFolder(id="SPAM", name="Spam", folder_type="spam", is_special=True),
            ProviderFolder(id="SENT", name="Sent", folder_type="sent", is_special=True),
            ProviderFolder(id="STARRED", name="Starred", folder_type="generic", is_special=True),
            ProviderFolder(id="IMPORTANT", name="Important", folder_type="generic", is_special=True)
        ]

    def stream_messages(self, folder_id: Optional[str] = None, limit: Optional[int] = None) -> Generator[ParsedEmail, None, None]:
        """Stream messages via Gmail REST API."""
        if not self.connect():
            raise ConnectionError(f"Account {self.account_email} is not authenticated with Gmail OAuth.")

        headers = self._get_headers()
        list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        page_token: Optional[str] = None
        fetched = 0

        while True:
            params: Dict[str, Any] = {"maxResults": min(100, (limit - fetched) if limit else 100)}
            if folder_id:
                params["labelIds"] = folder_id
            if page_token:
                params["pageToken"] = page_token

            resp = requests.get(list_url, headers=headers, params=params, timeout=30.0)
            if resp.status_code == 401 and self._refresh_access_token():
                headers = self._get_headers()
                resp = requests.get(list_url, headers=headers, params=params, timeout=30.0)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to list Gmail messages: {resp.status_code} {resp.text}")

            data = resp.json()
            msg_refs = data.get("messages", [])
            if not msg_refs:
                break

            for ref in msg_refs:
                if limit and fetched >= limit:
                    return
                msg_id = ref.get("id")
                if not msg_id:
                    continue
                msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}"
                m_resp = requests.get(msg_url, headers=headers, params={"format": "raw"}, timeout=30.0)
                if m_resp.status_code != 200:
                    logger.warning("Skipping Gmail message %s: %s", msg_id, m_resp.status_code)
                    continue
                m_data = m_resp.json()
                raw_b64 = m_data.get("raw")
                if not raw_b64:
                    continue
                # Pad base64url safely
                padded = raw_b64 + "=" * (-len(raw_b64) % 4)
                raw_bytes = base64.urlsafe_b64decode(padded)
                parsed = self.parser.parse_bytes(raw_bytes, provider_message_id=msg_id)
                parsed.provider_thread_id = m_data.get("threadId") or parsed.provider_thread_id
                label_ids = set(m_data.get("labelIds", []))
                parsed.is_read = "UNREAD" not in label_ids
                parsed.is_starred = "STARRED" in label_ids
                parsed.is_important = "IMPORTANT" in label_ids
                yield parsed
                fetched += 1

            page_token = data.get("nextPageToken")
            if not page_token or (limit and fetched >= limit):
                break

    def _batch_modify_system_labels(
        self,
        provider_message_ids: List[str],
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Batch-modify built-in Gmail system label IDs (TRASH, INBOX, etc.)."""
        if not provider_message_ids:
            return {"status": "success", "count": 0}
        if not self.connect():
            raise ConnectionError(f"Account {self.account_email} is not authenticated with Gmail OAuth.")

        headers = self._get_headers()
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/batchModify"
        for i in range(0, len(provider_message_ids), 1000):
            chunk = provider_message_ids[i:i + 1000]
            payload = {
                "ids": chunk,
                "addLabelIds": add_label_ids or [],
                "removeLabelIds": remove_label_ids or [],
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30.0)
            if resp.status_code == 401 and self._refresh_access_token():
                headers = self._get_headers()
                resp = requests.post(url, headers=headers, json=payload, timeout=30.0)
            if resp.status_code not in (200, 204):
                raise RuntimeError(f"Gmail batchModify failed: {resp.status_code} {resp.text}")
        return {"status": "success", "count": len(provider_message_ids)}

    def move_to_trash(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Move Gmail messages to TRASH via batchModify."""
        return self._batch_modify_system_labels(
            provider_message_ids,
            add_label_ids=["TRASH"],
            remove_label_ids=["INBOX"],
        )

    def archive_messages(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Archive Gmail messages by removing the INBOX label."""
        return self._batch_modify_system_labels(
            provider_message_ids,
            remove_label_ids=["INBOX"],
        )

    def restore_messages(self, provider_message_ids: List[str], dest_folder: str = "INBOX") -> Dict[str, Any]:
        """Restore Gmail messages from TRASH back to destination label (default INBOX)."""
        add_ids = [dest_folder] if dest_folder else ["INBOX"]
        return self._batch_modify_system_labels(
            provider_message_ids,
            add_label_ids=add_ids,
            remove_label_ids=["TRASH"],
        )
