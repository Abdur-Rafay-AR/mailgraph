# Providers package
from backend.app.providers.base import AbstractMailProvider, ProviderCapabilities, ProviderFolder
from backend.app.providers.synthetic import SyntheticMailboxGenerator
from backend.app.providers.mbox import MboxProvider

__all__ = ["AbstractMailProvider", "ProviderCapabilities", "ProviderFolder", "SyntheticMailboxGenerator", "MboxProvider"]
