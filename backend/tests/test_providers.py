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

def test_imap_provider_remote_trash_and_archive_calls(monkeypatch):
    provider = ImapProvider(
        host="imap.gmail.com",
        username="user@gmail.com",
        password="secretpassword"
    )
    mock_client = MagicMock()
    mock_client.uid.return_value = ("OK", [b"Success"])
    provider.client = mock_client
    monkeypatch.setattr(provider, "connect", lambda: True)
    monkeypatch.setattr(provider, "_get_trash_folder_name", lambda: "[Gmail]/Trash")
    monkeypatch.setattr(provider, "_get_archive_folder_name", lambda: "[Gmail]/All Mail")

    pids = ["imap_INBOX_101", "imap_INBOX_102"]
    
    # 1. Test move to trash
    trash_res = provider.move_to_trash(pids)
    assert trash_res["status"] == "success"
    assert trash_res["count"] == 2
    mock_client.select.assert_called_with('"INBOX"', readonly=False)
    mock_client.uid.assert_called_with("MOVE", "101,102", '"[Gmail]/Trash"')

    # 2. Test archive messages
    archive_res = provider.archive_messages(pids)
    assert archive_res["status"] == "success"
    assert archive_res["count"] == 2

    # 3. Test restore messages (undo)
    restore_res = provider.restore_messages(pids, dest_folder="INBOX")
    assert restore_res["status"] == "success"
    assert restore_res["count"] == 2
