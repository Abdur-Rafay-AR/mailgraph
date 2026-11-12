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

    def _parse_provider_id(self, pmid: str) -> Optional[tuple[str, str]]:
        """Extract folder and UID from imap_{folder}_{uid} string."""
        if not pmid.startswith("imap_"):
            return None
        rest = pmid[5:]
        last_underscore = rest.rfind("_")
        if last_underscore == -1:
            return None
        folder = rest[:last_underscore]
        uid = rest[last_underscore + 1:]
        return folder, uid

    def _get_trash_folder_name(self) -> str:
        """Find the IMAP Trash folder name dynamically, or default appropriately."""
        try:
            folders = self.list_folders()
            for f in folders:
                if f.folder_type == "trash":
                    return f.name
            for f in folders:
                if f.name in ("[Gmail]/Trash", "[Gmail]/Bin", "[Google Mail]/Trash", "[Google Mail]/Bin", "Trash", "Deleted Items"):
                    return f.name
        except Exception:
            pass
        return "[Gmail]/Trash" if "gmail" in self.host.lower() else "Trash"

    def _get_archive_folder_name(self) -> str:
        """Find the IMAP Archive folder name dynamically."""
        try:
            folders = self.list_folders()
            for f in folders:
                if f.folder_type == "archive":
                    return f.name
            for f in folders:
                if f.name in ("[Gmail]/All Mail", "[Google Mail]/All Mail", "Archive", "Archives"):
                    return f.name
        except Exception:
            pass
        return "[Gmail]/All Mail" if "gmail" in self.host.lower() else "Archive"

    def move_to_trash(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Move messages to Trash folder on live IMAP server."""
        if not provider_message_ids:
            return {"status": "success", "count": 0}

        if not self.client:
            self.connect()
        assert self.client is not None

        trash_folder = self._get_trash_folder_name()
        by_folder: Dict[str, List[str]] = {}
        for pmid in provider_message_ids:
            parsed = self._parse_provider_id(pmid)
            if parsed:
                f, u = parsed
                by_folder.setdefault(f, []).append(u)

        moved_count = 0
        failed_count = 0

        for folder, uids in by_folder.items():
            try:
                self.client.select(f'"{folder}"', readonly=False)
                for i in range(0, len(uids), 100):
                    chunk = uids[i:i + 100]
                    uid_set = ",".join(chunk)
                    
                    # Try UID MOVE first (RFC 6855)
                    typ, _ = self.client.uid("MOVE", uid_set, f'"{trash_folder}"')
                    if typ == "OK":
                        moved_count += len(chunk)
                    else:
                        # Fallback to standard RFC 3501 COPY + STORE + EXPUNGE
                        cp_typ, _ = self.client.uid("COPY", uid_set, f'"{trash_folder}"')
                        if cp_typ == "OK":
                            self.client.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")
                            self.client.expunge()
                            moved_count += len(chunk)
                        else:
                            failed_count += len(chunk)
            except Exception:
                failed_count += len(uids)

        return {
            "status": "success" if failed_count == 0 else "partial",
            "count": moved_count,
            "failed": failed_count,
            "trash_folder": trash_folder
        }

    def archive_messages(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Archive messages by removing from INBOX or copying to Archive folder."""
        if not provider_message_ids:
            return {"status": "success", "count": 0}

        if not self.client:
            self.connect()
        assert self.client is not None

        archive_folder = self._get_archive_folder_name()
        by_folder: Dict[str, List[str]] = {}
        for pmid in provider_message_ids:
            parsed = self._parse_provider_id(pmid)
            if parsed:
                f, u = parsed
                by_folder.setdefault(f, []).append(u)

        archived_count = 0
        failed_count = 0
        is_gmail = "gmail" in self.host.lower()

        for folder, uids in by_folder.items():
            try:
                self.client.select(f'"{folder}"', readonly=False)
                for i in range(0, len(uids), 100):
                    chunk = uids[i:i + 100]
                    uid_set = ",".join(chunk)
                    
                    if is_gmail and folder.upper() == "INBOX":
                        # In Gmail IMAP, marking \\Deleted in INBOX and expunging archives the message
                        self.client.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")
                        self.client.expunge()
                        archived_count += len(chunk)
                    else:
                        typ, _ = self.client.uid("MOVE", uid_set, f'"{archive_folder}"')
                        if typ == "OK":
                            archived_count += len(chunk)
                        else:
                            self.client.uid("COPY", uid_set, f'"{archive_folder}"')
                            self.client.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")
                            self.client.expunge()
                            archived_count += len(chunk)
            except Exception:
                failed_count += len(uids)

        return {"status": "success" if failed_count == 0 else "partial", "count": archived_count, "failed": failed_count}

    def restore_messages(self, provider_message_ids: List[str], dest_folder: str = "INBOX") -> Dict[str, Any]:
        """Restore messages from Trash back to Inbox."""
        if not provider_message_ids:
            return {"status": "success", "count": 0}

        if not self.client:
            self.connect()
        assert self.client is not None

        trash_folder = self._get_trash_folder_name()
        by_folder: Dict[str, List[str]] = {}
        for pmid in provider_message_ids:
            parsed = self._parse_provider_id(pmid)
            if parsed:
                f, u = parsed
                by_folder.setdefault(f, []).append(u)

        restored_count = 0
        try:
            self.client.select(f'"{trash_folder}"', readonly=False)
            all_uids = []
            for uids in by_folder.values():
                all_uids.extend(uids)

            for i in range(0, len(all_uids), 100):
                chunk = all_uids[i:i + 100]
                uid_set = ",".join(chunk)
                typ, _ = self.client.uid("MOVE", uid_set, f'"{dest_folder}"')
                if typ == "OK":
                    restored_count += len(chunk)
                else:
                    self.client.uid("COPY", uid_set, f'"{dest_folder}"')
                    self.client.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")
                    self.client.expunge()
                    restored_count += len(chunk)
        except Exception:
            pass

        return {"status": "success", "count": restored_count}

    def permanently_delete(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Permanently delete messages from IMAP server."""
        if not provider_message_ids:
            return {"status": "success", "count": 0}

        if not self.client:
            self.connect()
        assert self.client is not None

        by_folder: Dict[str, List[str]] = {}
        for pmid in provider_message_ids:
            parsed = self._parse_provider_id(pmid)
            if parsed:
                f, u = parsed
                by_folder.setdefault(f, []).append(u)

        deleted_count = 0
        for folder, uids in by_folder.items():
            try:
                self.client.select(f'"{folder}"', readonly=False)
                for i in range(0, len(uids), 100):
                    chunk = uids[i:i + 100]
                    uid_set = ",".join(chunk)
                    self.client.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")
                    self.client.expunge()
                    deleted_count += len(chunk)
            except Exception:
                pass

        return {"status": "success", "count": deleted_count}
