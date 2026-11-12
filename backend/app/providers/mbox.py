"""Streaming MBOX archive provider."""

import os
import mailbox
from pathlib import Path
from typing import Generator, List, Optional
from backend.app.providers.base import AbstractMailProvider, ProviderCapabilities, ProviderFolder
from backend.app.ingestion.mime_parser import MimeParser, ParsedEmail

class MboxProvider(AbstractMailProvider):
    """Imports messages from an offline RFC4155 / standard mbox file."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.parser = MimeParser()

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_archive=False,
            supports_trash=False,
            supports_undo=False,
            supports_labels=False,
            is_read_only=True,
            provider_name="mbox"
        )

    def connect(self) -> bool:
        if not os.path.isfile(self.file_path):
            raise FileNotFoundError(f"MBOX file not found at: {self.file_path}")
        return True

    def list_folders(self) -> List[ProviderFolder]:
        basename = os.path.basename(self.file_path)
        return [ProviderFolder(id="mbox_archive", name=basename, folder_type="archive", is_special=True)]

    def stream_messages(self, folder_id: Optional[str] = None, limit: Optional[int] = None) -> Generator[ParsedEmail, None, None]:
        """Stream messages from the mbox file one at a time."""
        self.connect()
        mbox = mailbox.mbox(self.file_path)
        
        count = 0
        try:
            for key, msg in mbox.items():
                if limit and count >= limit:
                    break
                try:
                    # Get raw bytes of message
                    raw_bytes = msg.as_bytes()
                    provider_msg_id = f"mbox_{key}"
                    parsed = self.parser.parse_bytes(raw_bytes, provider_message_id=provider_msg_id)
                    yield parsed
                    count += 1
                except Exception:
                    # Error tolerance: skip individual unparseable message without breaking the whole import
                    continue
        finally:
            mbox.close()
