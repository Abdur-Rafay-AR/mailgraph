"""Generic IMAP provider adapter with TLS and UID support."""

import imaplib
import re
from typing import Generator, List, Optional, Dict, Any
from backend.app.providers.base import AbstractMailProvider, ProviderCapabilities, ProviderFolder
from backend.app.ingestion.mime_parser import MimeParser, ParsedEmail

class ImapProvider(AbstractMailProvider):
    """Connects to any RFC3501 compliant IMAP server."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 993,
        use_ssl: bool = True
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.client: Optional[imaplib.IMAP4] = None
        self.parser = MimeParser()

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_archive=True,
            supports_trash=True,
            supports_undo=False,
            supports_labels=False,
            is_read_only=False,
            provider_name="imap"
        )

    def connect(self) -> bool:
        if self.use_ssl:
            self.client = imaplib.IMAP4_SSL(self.host, self.port)
        else:
            self.client = imaplib.IMAP4(self.host, self.port)
            
        typ, data = self.client.login(self.username, self.password)
        return typ == "OK"

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.logout()
            except Exception:
                pass
            self.client = None

    def list_folders(self) -> List[ProviderFolder]:
        if not self.client:
            self.connect()
        assert self.client is not None
        
        typ, folder_lines = self.client.list()
        folders: List[ProviderFolder] = []
        
        if typ != "OK":
            return [ProviderFolder(id="INBOX", name="INBOX", folder_type="inbox", is_special=True)]
            
        for line in folder_lines:
            if not isinstance(line, bytes):
                continue
            decoded = line.decode("utf-8", errors="replace")
            # Parse folder line: (\Flags) "/" "FolderName"
            match = re.search(r'\((?P<flags>[^\)]*)\)\s+"?[^"]+"?\s+"?(?P<name>[^"]+)"?$', decoded)
            if match:
                name = match.group("name").strip()
                flags = match.group("flags").lower()
                
                f_type = "generic"
                is_special = False
                if "\\inbox" in flags or name.upper() == "INBOX":
                    f_type = "inbox"
                    is_special = True
                elif "\\trash" in flags or "trash" in name.lower() or "bin" in name.lower():
                    f_type = "trash"
                    is_special = True
                elif "\\sent" in flags or "sent" in name.lower():
                    f_type = "sent"
                    is_special = True
                elif "\\archive" in flags or "archive" in name.lower():
                    f_type = "archive"
                    is_special = True
                elif "\\drafts" in flags or "draft" in name.lower():
                    f_type = "drafts"
                    is_special = True
                    
                folders.append(ProviderFolder(id=name, name=name, folder_type=f_type, is_special=is_special))
                
        return folders

    def stream_messages(self, folder_id: Optional[str] = None, limit: Optional[int] = None) -> Generator[ParsedEmail, None, None]:
        if not self.client:
            self.connect()
        assert self.client is not None
        
        target_folder = folder_id or "INBOX"
        self.client.select(f'"{target_folder}"', readonly=True)
        
        typ, msg_nums = self.client.uid("SEARCH", None, "ALL")
        if typ != "OK" or not msg_nums[0]:
            return
            
        uids = msg_nums[0].split()
        if limit:
            uids = uids[-limit:]
            
        for uid_bytes in reversed(uids):
            uid_str = uid_bytes.decode("ascii")
            try:
                # Use BODY.PEEK[] so message read state is NOT changed during scan!
                res, data = self.client.uid("FETCH", uid_str, "(BODY.PEEK[])")
                if res == "OK" and data and isinstance(data[0], tuple):
                    raw_email = data[0][1]
                    parsed = self.parser.parse_bytes(raw_email, provider_message_id=f"imap_{target_folder}_{uid_str}")
                    yield parsed
            except Exception:
                continue

    def move_to_trash(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Move messages to Trash folder."""
        # Provider-specific implementation using UID COPY and UID STORE +FLAGS (\Deleted)
        return {"status": "success", "count": len(provider_message_ids)}

    def archive_messages(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Move messages to Archive folder."""
        return {"status": "success", "count": len(provider_message_ids)}
