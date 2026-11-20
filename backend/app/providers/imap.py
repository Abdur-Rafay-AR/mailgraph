"""Generic IMAP provider adapter with TLS and UID support."""

import imaplib
import re
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from backend.app.ingestion.mime_parser import MimeParser, ParsedEmail
from backend.app.providers.base import AbstractMailProvider, ProviderCapabilities, ProviderFolder
from backend.app.providers.exceptions import UIDValidityChangedError

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
            supports_labels=True,
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
                elif "\\archive" in flags or "\\all" in flags or "archive" in name.lower() or "all mail" in name.lower():
                    f_type = "archive"
                    is_special = True
                elif "\\drafts" in flags or "draft" in name.lower():
                    f_type = "drafts"
                    is_special = True
                    
                folders.append(ProviderFolder(id=name, name=name, folder_type=f_type, is_special=is_special))
                
        return folders

    def get_message_count(self, folder_id: str = "INBOX") -> int:
        """Return total message count in a folder with zero body overhead."""
        if not self.client:
            self.connect()
        assert self.client is not None
        try:
            typ, data = self.client.select(f'"{folder_id}"', readonly=True)
            if typ == "OK" and data and data[0]:
                return int(data[0])
        except Exception:
            pass
        return 0

    def get_all_mail_folder_name(self) -> Optional[str]:
        """Return the server's All Mail folder name (e.g. [Gmail]/All Mail) if available."""
        try:
            if not self.client:
                self.connect()
            assert self.client is not None
            typ, folder_lines = self.client.list()
            if typ == "OK" and folder_lines:
                for line in folder_lines:
                    if not isinstance(line, bytes):
                        continue
                    decoded = line.decode("utf-8", errors="replace")
                    match = re.search(r'\((?P<flags>[^\)]*)\)\s+"?[^"]+"?\s+"?(?P<name>[^"]+)"?$', decoded)
                    if not match:
                        continue
                    flags = match.group("flags").lower()
                    name = match.group("name").strip()
                    if "\\all" in flags or name in ("[Gmail]/All Mail", "[Google Mail]/All Mail"):
                        return name
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_uid_and_flags(data: list, idx: int, meta_bytes: bytes, fallback_uid: str = "unknown") -> tuple[str, bool, bool]:
        """Extract UID and \\Seen / \\Flagged flags from both pre-literal and post-literal IMAP FETCH responses."""
        meta_str = meta_bytes.decode("ascii", errors="ignore")
        if idx + 1 < len(data) and isinstance(data[idx + 1], bytes):
            meta_str += " " + data[idx + 1].decode("ascii", errors="ignore")

        m = re.search(r"UID\s+(\d+)", meta_str)
        uid_str = m.group(1) if m else fallback_uid

        flags_match = re.search(r"FLAGS\s*\(([^)]*)\)", meta_str, re.IGNORECASE)
        flags_str = flags_match.group(1).lower() if flags_match else ""
        is_read = "\\seen" in flags_str
        is_starred = "\\flagged" in flags_str
        return uid_str, is_read, is_starred

    def stream_messages(
        self,
        folder_id: Optional[str] = None,
        limit: Optional[int] = None,
        batch_size: int = 50,
        known_state: Optional[Dict[str, Tuple[bool, bool]]] = None,
        on_flag_updates: Optional[Callable[[List[Tuple[str, bool, bool]], int], None]] = None,
    ) -> Generator[ParsedEmail, None, None]:
        """Stream parsed emails using high-throughput multi-UID batch fetching.

        When known_state is provided (mapping provider_message_id -> (is_read, is_starred)),
        already-indexed UIDs perform a lightweight FLAGS-only check instead of re-downloading
        full message bodies, dramatically accelerating incremental and full-mailbox syncs.
        """
        if not self.client:
            self.connect()
        assert self.client is not None

        target_folder = folder_id or "INBOX"
        sel_typ, _ = self.client.select(f'"{target_folder}"', readonly=True)
        if sel_typ != "OK":
            return

        typ, msg_nums = self.client.uid("SEARCH", None, "ALL")
        if typ != "OK" or not msg_nums or not msg_nums[0]:
            return

        all_uids = msg_nums[0].split()
        if not all_uids:
            return

        if limit and limit < len(all_uids):
            # Take the most recent 'limit' messages
            selected_uids = all_uids[-limit:]
        else:
            selected_uids = all_uids

        # Reverse so most recent messages arrive first
        uids_list = [u.decode("ascii") for u in reversed(selected_uids)]

        # Partition into already-indexed UIDs (flags-only check) vs new UIDs (full fetch)
        if known_state is not None:
            existing_uids = [u for u in uids_list if f"imap_{target_folder}_{u}" in known_state]
            new_uids = [u for u in uids_list if f"imap_{target_folder}_{u}" not in known_state]

            for i in range(0, len(existing_uids), 500):
                chunk = existing_uids[i:i + 500]
                uid_set = ",".join(chunk)
                updates: List[Tuple[str, bool, bool]] = []
                try:
                    f_res, f_data = self.client.uid("FETCH", uid_set, "(UID FLAGS)")
                    if f_res == "OK" and f_data:
                        for idx, item in enumerate(f_data):
                            raw_bytes = item[0] if isinstance(item, tuple) else item
                            if not isinstance(raw_bytes, bytes):
                                continue
                            uid_str, is_read, is_starred = self._extract_uid_and_flags(f_data, idx, raw_bytes)
                            if uid_str == "unknown":
                                continue
                            pmid = f"imap_{target_folder}_{uid_str}"
                            prev = known_state.get(pmid)
                            if prev is not None and prev != (is_read, is_starred):
                                updates.append((pmid, is_read, is_starred))
                                known_state[pmid] = (is_read, is_starred)
                except Exception:
                    pass
                if on_flag_updates:
                    on_flag_updates(updates, len(chunk))
        else:
            new_uids = uids_list

        # Fetch new messages in multi-UID batches (50 messages per round-trip)
        for i in range(0, len(new_uids), batch_size):
            chunk = new_uids[i:i + batch_size]
            uid_set = ",".join(chunk)

            try:
                # Use BODY.PEEK[] + FLAGS so message read state is NOT changed during scan!
                res, data = self.client.uid("FETCH", uid_set, "(BODY.PEEK[] FLAGS)")
                if res != "OK" or not data:
                    continue

                for idx, item in enumerate(data):
                    if isinstance(item, tuple) and len(item) == 2:
                        meta_bytes, raw_email = item
                        uid_str, is_read, is_starred = self._extract_uid_and_flags(data, idx, meta_bytes)

                        try:
                            parsed = self.parser.parse_bytes(raw_email, provider_message_id=f"imap_{target_folder}_{uid_str}")
                            parsed.is_read = is_read
                            parsed.is_starred = is_starred
                            yield parsed
                        except Exception:
                            continue
            except Exception:
                # Resilient fallback: fetch individually if a large batch fails (e.g. huge attachment timeout)
                for single_uid in chunk:
                    try:
                        s_res, s_data = self.client.uid("FETCH", single_uid, "(BODY.PEEK[] FLAGS)")
                        if s_res == "OK" and s_data and isinstance(s_data[0], tuple):
                            meta_bytes, raw_email = s_data[0][0], s_data[0][1]
                            _, is_read, is_starred = self._extract_uid_and_flags(s_data, 0, meta_bytes, single_uid)
                            parsed = self.parser.parse_bytes(raw_email, provider_message_id=f"imap_{target_folder}_{single_uid}")
                            parsed.is_read = is_read
                            parsed.is_starred = is_starred
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

    def _extract_uidvalidity(self, select_data: Any = None) -> Optional[str]:
        """Extract UIDVALIDITY string from IMAP client response or select data."""
        if not self.client:
            return None
        try:
            typ, resp_data = self.client.response("UIDVALIDITY")
            if typ == "OK" and resp_data and resp_data[0] is not None:
                raw = resp_data[0]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                m = re.search(r"(\d+)", str(raw))
                if m:
                    return m.group(1)
                return str(raw).strip()
        except Exception:
            pass

        if select_data:
            for item in select_data:
                if isinstance(item, (bytes, str)):
                    text = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
                    m = re.search(r"UIDVALIDITY\s+(\d+)", text, re.IGNORECASE)
                    if m:
                        return m.group(1)

        untagged = getattr(self.client, "untagged_responses", {})
        if "UIDVALIDITY" in untagged and untagged["UIDVALIDITY"] and untagged["UIDVALIDITY"][0] is not None:
            raw = untagged["UIDVALIDITY"][0]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            m = re.search(r"(\d+)", str(raw))
            if m:
                return m.group(1)
            return str(raw).strip()

        return None

    def get_folder_uidvalidity(self, folder: str) -> Optional[str]:
        """Inspect and return the UIDVALIDITY string for a folder."""
        if not self.client:
            self.connect()
        assert self.client is not None

        try:
            typ, data = self.client.select(f'"{folder}"', readonly=True)
            if typ != "OK":
                return None
            return self._extract_uidvalidity(data)
        except Exception:
            return None

    def apply_labels(
        self,
        provider_message_ids: List[str],
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
        expected_uidvalidity: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Apply or remove Gmail labels (+X-GM-LABELS / -X-GM-LABELS) with UIDVALIDITY verification."""
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

        if not by_folder:
            return {"status": "success", "count": 0}

        # Step 2: For each folder, select read-write and verify UIDVALIDITY
        for folder in by_folder.keys():
            typ, data = self.client.select(f'"{folder}"', readonly=False)
            if typ != "OK":
                raise RuntimeError(f"Failed to select folder '{folder}' in read-write mode")
            actual_uidval = self._extract_uidvalidity(data)
            if expected_uidvalidity and folder in expected_uidvalidity:
                expected = str(expected_uidvalidity[folder])
                if actual_uidval != expected:
                    raise UIDValidityChangedError(folder=folder, expected=expected, actual=str(actual_uidval or ""))

        # Step 3: Ensure label mailboxes exist
        if add_labels:
            for lbl in add_labels:
                typ, existing = self.client.list(pattern=f'"{lbl}"')
                exists = False
                if typ == "OK" and existing:
                    for item in existing:
                        if item:
                            exists = True
                            break
                if not exists:
                    self.client.create(f'"{lbl}"')

        # Step 4: In chunks of 100 UIDs, apply / remove labels
        total_uids = 0
        currently_selected = next(iter(by_folder)) if len(by_folder) == 1 else None

        for folder, uids in by_folder.items():
            if currently_selected != folder:
                typ, _ = self.client.select(f'"{folder}"', readonly=False)
                if typ != "OK":
                    raise RuntimeError(f"Failed to select folder '{folder}' in read-write mode")
                currently_selected = folder

            total_uids += len(uids)
            for i in range(0, len(uids), 100):
                chunk = uids[i:i + 100]
                uid_set = ",".join(chunk)

                if add_labels:
                    for lbl in add_labels:
                        typ, resp = self.client.uid("STORE", uid_set, "+X-GM-LABELS", f'("{lbl}")')
                        if typ != "OK":
                            raise RuntimeError(f"IMAP STORE +X-GM-LABELS failed for '{lbl}': {resp}")

                if remove_labels:
                    for lbl in remove_labels:
                        typ, resp = self.client.uid("STORE", uid_set, "-X-GM-LABELS", f'("{lbl}")')
                        if typ != "OK":
                            raise RuntimeError(f"IMAP STORE -X-GM-LABELS failed for '{lbl}': {resp}")

        return {"status": "success", "count": total_uids}
