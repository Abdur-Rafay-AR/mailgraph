"""Base abstraction for email providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator, List, Optional, Dict, Any
from backend.app.ingestion.mime_parser import ParsedEmail

@dataclass
class ProviderCapabilities:
    supports_archive: bool = False
    supports_trash: bool = False
    supports_undo: bool = False
    supports_labels: bool = False
    is_read_only: bool = True
    provider_name: str = "generic"

@dataclass
class ProviderFolder:
    id: str
    name: str
    folder_type: str  # 'inbox', 'sent', 'trash', 'archive', 'drafts', 'generic'
    is_special: bool = False

class AbstractMailProvider(ABC):
    """Abstract interface implemented by all mail ingestion/mutation sources."""

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Return provider-specific supported features."""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection or validate local file presence."""
        pass

    @abstractmethod
    def list_folders(self) -> List[ProviderFolder]:
        """List available folders or mailboxes."""
        pass

    @abstractmethod
    def stream_messages(self, folder_id: Optional[str] = None, limit: Optional[int] = None) -> Generator[ParsedEmail, None, None]:
        """Stream parsed messages from provider."""
        pass

    def archive_messages(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Archive messages if supported."""
        raise NotImplementedError("Archive not supported by this provider.")

    def move_to_trash(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Move messages to trash if supported."""
        raise NotImplementedError("Trash not supported by this provider.")

    def restore_messages(self, provider_message_ids: List[str]) -> Dict[str, Any]:
        """Restore messages from trash or archive."""
        raise NotImplementedError("Restore not supported by this provider.")
