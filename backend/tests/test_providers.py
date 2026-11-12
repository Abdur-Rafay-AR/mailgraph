import pytest
from unittest.mock import MagicMock, patch
from backend.app.security.credential_store import CredentialStore
from backend.app.providers.imap import ImapProvider
from backend.app.providers.gmail import GmailProvider

def test_credential_store_save_and_retrieve():
    store = CredentialStore(service_name="MailGraph_Test")
    test_account = "test_user@example.com"
    test_secret = '{"token": "xyz123secret", "refresh_token": "ref456"}'
    
    saved = store.save_credentials(test_account, test_secret)
    assert saved is True
    
    retrieved = store.get_credentials(test_account)
    assert retrieved == test_secret
    
    store.delete_credentials(test_account)
    assert store.get_credentials(test_account) is None

def test_imap_provider_capabilities():
    provider = ImapProvider(
        host="imap.example.com",
        username="user@example.com",
        password="secretpassword",
        port=993,
        use_ssl=True
    )
    caps = provider.get_capabilities()
    assert caps.provider_name == "imap"
    assert caps.supports_trash is True
    assert caps.supports_archive is True

def test_gmail_provider_capabilities():
    provider = GmailProvider(account_email="user@gmail.com")
    caps = provider.get_capabilities()
    assert caps.provider_name == "gmail"
    assert caps.supports_trash is True
    assert caps.supports_undo is True
    assert caps.supports_archive is True
