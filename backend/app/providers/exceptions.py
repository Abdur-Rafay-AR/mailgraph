class ProviderError(Exception):
    """Base exception for mail provider operations."""
    pass

class UIDValidityChangedError(ProviderError):
    """Raised when an IMAP folder's UIDVALIDITY does not match cached state."""
    def __init__(self, folder: str, expected: str, actual: str):
        super().__init__(f"UIDVALIDITY mismatch for folder '{folder}': expected {expected}, got {actual}")
        self.folder = folder
        self.expected = expected
        self.actual = actual
