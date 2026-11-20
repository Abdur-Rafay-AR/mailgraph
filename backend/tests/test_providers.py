import pytest
from unittest.mock import MagicMock, patch
from backend.app.security.credential_store import CredentialStore
from backend.app.providers.imap import ImapProvider
from backend.app.providers.gmail import GmailProvider
from backend.app.providers.exceptions import UIDValidityChangedError
from backend.app.providers.base import AbstractMailProvider, ProviderCapabilities

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
    assert caps.supports_labels is True

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

def test_base_provider_label_interface():
    class DummyProvider(AbstractMailProvider):
        def get_capabilities(self):
            return ProviderCapabilities(supports_labels=True)
        def connect(self):
            return True
        def list_folders(self):
            return []
        def stream_messages(self, folder_id=None, limit=None):
            yield from ()

    p = DummyProvider()
    assert p.get_capabilities().supports_labels is True
    assert p.list_labels() == []
    with pytest.raises(NotImplementedError):
        p.apply_labels(["imap_INBOX_1"], add_labels=["MailGraph/Finance"])

def test_uid_validity_changed_error():
    err = UIDValidityChangedError("INBOX", "123", "456")
    assert err.folder == "INBOX"
    assert err.expected == "123"
    assert err.actual == "456"
    assert "UIDVALIDITY mismatch for folder 'INBOX': expected 123, got 456" in str(err)

def test_imap_apply_labels_uidvalidity_verification():
    provider = ImapProvider(host="imap.gmail.com", username="user@gmail.com", password="pwd")
    mock_client = MagicMock()
    provider.client = mock_client

    # Case 1: UIDVALIDITY mismatch raises error
    mock_client.select.return_value = ("OK", [b"123"])
    mock_client.response.return_value = ("OK", [b"99999"])
    
    with pytest.raises(UIDValidityChangedError):
        provider.apply_labels(
            ["imap_INBOX_101", "imap_INBOX_102"],
            add_labels=["MailGraph/Finance"],
            expected_uidvalidity={"INBOX": "11111"}
        )

    # Case 2: Matching UIDVALIDITY succeeds and issues STORE +X-GM-LABELS
    mock_client.response.return_value = ("OK", [b"11111"])
    mock_client.list.return_value = ("OK", [b'(\\HasNoChildren) "/" "MailGraph/Finance"'])
    mock_client.uid.return_value = ("OK", [b"Success"])

    res = provider.apply_labels(
        ["imap_INBOX_101", "imap_INBOX_102"],
        add_labels=["MailGraph/Finance"],
        expected_uidvalidity={"INBOX": "11111"}
    )
    assert res["status"] == "success"
    assert res["count"] == 2
    mock_client.uid.assert_called_with("STORE", "101,102", "+X-GM-LABELS", '("MailGraph/Finance")')

    # Case 3: Undo removes label with -X-GM-LABELS
    res_undo = provider.apply_labels(
        ["imap_INBOX_101"],
        remove_labels=["MailGraph/Finance"],
        expected_uidvalidity={"INBOX": "11111"}
    )
    assert res_undo["status"] == "success"
    mock_client.uid.assert_called_with("STORE", "101", "-X-GM-LABELS", '("MailGraph/Finance")')

def test_imap_get_folder_uidvalidity():
    provider = ImapProvider(host="imap.gmail.com", username="user@gmail.com", password="pwd")
    mock_client = MagicMock()
    provider.client = mock_client

    mock_client.select.return_value = ("OK", [b"42"])
    mock_client.response.return_value = ("OK", [b"12345"])

    uidval = provider.get_folder_uidvalidity("INBOX")
    assert uidval == "12345"
    mock_client.select.assert_called_with('"INBOX"', readonly=True)
    mock_client.response.assert_called_with("UIDVALIDITY")

def test_imap_apply_labels_creates_missing_label():
    provider = ImapProvider(host="imap.gmail.com", username="user@gmail.com", password="pwd")
    mock_client = MagicMock()
    provider.client = mock_client

    mock_client.select.return_value = ("OK", [b"1"])
    mock_client.response.return_value = ("OK", [b"11111"])
    mock_client.list.return_value = ("OK", [None])  # Mailbox does not exist
    mock_client.uid.return_value = ("OK", [b"Success"])

    res = provider.apply_labels(
        ["imap_INBOX_101"],
        add_labels=["MailGraph/NewTag"],
        expected_uidvalidity={"INBOX": "11111"}
    )
    assert res["status"] == "success"
    mock_client.create.assert_called_with('"MailGraph/NewTag"')
    mock_client.uid.assert_called_with("STORE", "101", "+X-GM-LABELS", '("MailGraph/NewTag")')

def test_imap_apply_labels_chunking():
    provider = ImapProvider(host="imap.gmail.com", username="user@gmail.com", password="pwd")
    mock_client = MagicMock()
    provider.client = mock_client

    mock_client.select.return_value = ("OK", [b"250"])
    mock_client.response.return_value = ("OK", [b"11111"])
    mock_client.list.return_value = ("OK", [b'(\\HasNoChildren) "/" "MailGraph/Bulk"'])
    mock_client.uid.return_value = ("OK", [b"Success"])

    # 150 message IDs
    pids = [f"imap_INBOX_{i}" for i in range(1, 151)]
    res = provider.apply_labels(
        pids,
        add_labels=["MailGraph/Bulk"],
        expected_uidvalidity={"INBOX": "11111"}
    )
    assert res["status"] == "success"
    assert res["count"] == 150
    # Should have called uid STORE twice: chunk 1 (100) and chunk 2 (50)
    assert mock_client.uid.call_count == 2
    chunk1_uids = ",".join(str(i) for i in range(1, 101))
    chunk2_uids = ",".join(str(i) for i in range(101, 151))
    mock_client.uid.assert_any_call("STORE", chunk1_uids, "+X-GM-LABELS", '("MailGraph/Bulk")')
    mock_client.uid.assert_any_call("STORE", chunk2_uids, "+X-GM-LABELS", '("MailGraph/Bulk")')

def test_imap_apply_labels_select_failure_raises_runtime_error():
    provider = ImapProvider(host="imap.gmail.com", username="user@gmail.com", password="pwd")
    mock_client = MagicMock()
    provider.client = mock_client

    mock_client.select.return_value = ("NO", [b"Folder does not exist"])
    with pytest.raises(RuntimeError, match="Failed to select folder 'INBOX' in read-write mode"):
        provider.apply_labels(["imap_INBOX_101"], add_labels=["MailGraph/Tag"])

def test_imap_apply_labels_multi_folder_selection_and_status_checks():
    provider = ImapProvider(host="imap.gmail.com", username="user@gmail.com", password="pwd")
    mock_client = MagicMock()
    provider.client = mock_client

    mock_client.select.return_value = ("OK", [b"10"])
    mock_client.response.return_value = ("OK", [b"55555"])
    mock_client.list.return_value = ("OK", [b'(\\HasNoChildren) "/" "MailGraph/Multi"'])
    mock_client.uid.return_value = ("OK", [b"Success"])

    res = provider.apply_labels(
        ["imap_INBOX_101", "imap_Archive_201"],
        add_labels=["MailGraph/Multi"],
        expected_uidvalidity={"INBOX": "55555", "Archive": "55555"}
    )
    assert res["status"] == "success"
    assert res["count"] == 2

    # Verification that both folders were selected in Step 2 and re-selected in Step 4
    select_calls = [c.args for c in mock_client.select.call_args_list]
    assert ('"INBOX"',) in [c[:1] for c in select_calls]
    assert ('"Archive"',) in [c[:1] for c in select_calls]

    # Verify STORE was called for each folder's UID
    mock_client.uid.assert_any_call("STORE", "101", "+X-GM-LABELS", '("MailGraph/Multi")')
    mock_client.uid.assert_any_call("STORE", "201", "+X-GM-LABELS", '("MailGraph/Multi")')

def test_gmail_provider_apply_labels():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # 1. Label catalog lookup returns existing labels
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "labels": [{"id": "Label_123", "name": "MailGraph/Finance"}]
        }

        # 2. batchModify succeeds
        mock_post.return_value.status_code = 204

        res = provider.apply_labels(
            ["msg_1", "msg_2"],
            add_labels=["MailGraph/Finance"]
        )
        assert res["status"] == "success"
        assert res["count"] == 2
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "batchModify" in args[0]
        assert kwargs["json"]["addLabelIds"] == ["Label_123"]
        assert kwargs["json"]["ids"] == ["msg_1", "msg_2"]

def test_gmail_provider_resolve_or_create_label_cached():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"
    provider._label_cache["MailGraph/Receipts"] = "Label_Receipts"

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        label_id = provider.resolve_or_create_label_id("MailGraph/Receipts")
        assert label_id == "Label_Receipts"
        mock_get.assert_not_called()
        mock_post.assert_not_called()

def test_gmail_provider_resolve_or_create_label_creates_new():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # 1. Catalog does not contain the label
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"labels": []}

        # 2. POST creates the label
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": "Label_Created", "name": "MailGraph/NewTag"}

        label_id = provider.resolve_or_create_label_id("MailGraph/NewTag")
        assert label_id == "Label_Created"
        assert provider._label_cache["MailGraph/NewTag"] == "Label_Created"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "users/me/labels" in args[0]
        assert kwargs["json"]["name"] == "MailGraph/NewTag"

def test_gmail_provider_resolve_or_create_label_409_conflict():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # 1st get (refresh before post) returns empty
        # 2nd get (refresh after 409) returns newly detected label
        get_response_empty = MagicMock(status_code=200)
        get_response_empty.json.return_value = {"labels": []}
        get_response_conflict = MagicMock(status_code=200)
        get_response_conflict.json.return_value = {
            "labels": [{"id": "Label_Race", "name": "MailGraph/Conflict"}]
        }
        mock_get.side_effect = [get_response_empty, get_response_conflict]

        mock_post.return_value.status_code = 409

        label_id = provider.resolve_or_create_label_id("MailGraph/Conflict")
        assert label_id == "Label_Race"
        assert provider._label_cache["MailGraph/Conflict"] == "Label_Race"
        assert mock_get.call_count == 2
        mock_post.assert_called_once()

def test_gmail_provider_apply_labels_chunking_1000():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"
    provider._label_cache["MailGraph/Bulk"] = "Label_Bulk"

    # 1500 messages should split into chunks of 1000 and 500
    msg_ids = [f"gmail_msg_{i}" for i in range(1500)]

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200

        res = provider.apply_labels(msg_ids, add_labels=["MailGraph/Bulk"])
        assert res["status"] == "success"
        assert res["count"] == 1500
        assert mock_post.call_count == 2

        call1_kwargs = mock_post.call_args_list[0][1]
        assert len(call1_kwargs["json"]["ids"]) == 1000
        assert call1_kwargs["json"]["ids"] == msg_ids[:1000]

        call2_kwargs = mock_post.call_args_list[1][1]
        assert len(call2_kwargs["json"]["ids"]) == 500
        assert call2_kwargs["json"]["ids"] == msg_ids[1000:]

def test_gmail_provider_apply_labels_rate_limiting_retry():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"
    provider._label_cache["MailGraph/Tag"] = "Label_Tag"

    with patch("requests.post") as mock_post, patch("time.sleep") as mock_sleep:
        # First call: 429 Rate Limit; Second call: 204 Success
        resp_429 = MagicMock(status_code=429, text="Rate limit exceeded")
        resp_204 = MagicMock(status_code=204)
        mock_post.side_effect = [resp_429, resp_204]

        res = provider.apply_labels(["msg_1"], add_labels=["MailGraph/Tag"])
        assert res["status"] == "success"
        assert res["count"] == 1
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()

def test_gmail_provider_oauth_scope():
    from backend.app.providers.gmail import MODIFY_SCOPE
    provider = GmailProvider(account_email="test@gmail.com", client_id="test_client_id")
    url = provider.get_oauth_url()
    assert f"scope={MODIFY_SCOPE}" in url

def test_gmail_provider_apply_labels_404_cache_busting():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"
    # Seed cache with stale label ID
    provider._label_cache["MailGraph/Stale"] = "Label_Old"

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # First batchModify returns 404 (stale label ID)
        resp_404 = MagicMock(status_code=404, text="Label not found")
        # Second batchModify returns 204
        resp_204 = MagicMock(status_code=204)
        mock_post.side_effect = [resp_404, resp_204]

        # GET refresh_labels returns new label ID
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "labels": [{"id": "Label_Fresh", "name": "MailGraph/Stale"}]
        }

        res = provider.apply_labels(["msg_1"], add_labels=["MailGraph/Stale"])
        assert res["status"] == "success"
        assert res["count"] == 1
        assert mock_post.call_count == 2
        mock_get.assert_called_once()
        # Verify second call used Label_Fresh
        second_call_kwargs = mock_post.call_args_list[1][1]
        assert second_call_kwargs["json"]["addLabelIds"] == ["Label_Fresh"]

def test_gmail_provider_apply_labels_remove_and_add():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"
    provider._label_cache["MailGraph/New"] = "Label_New"
    provider._label_cache["MailGraph/Old"] = "Label_Old"

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 204

        res = provider.apply_labels(
            ["msg_1"],
            add_labels=["MailGraph/New"],
            remove_labels=["MailGraph/Old"]
        )
        assert res["status"] == "success"
        assert res["count"] == 1
        kwargs = mock_post.call_args[1]
        assert kwargs["json"]["addLabelIds"] == ["Label_New"]
        assert kwargs["json"]["removeLabelIds"] == ["Label_Old"]

def test_gmail_provider_apply_labels_empty_messages():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"

    res = provider.apply_labels([], add_labels=["MailGraph/New"])
    assert res["status"] == "success"
    assert res["count"] == 0

def test_gmail_provider_list_labels():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "labels": [
                {"id": "INBOX", "name": "INBOX"},
                {"id": "Label_1", "name": "MailGraph/Finance"}
            ]
        }
        labels = provider.list_labels()
        assert "INBOX" in labels
        assert "MailGraph/Finance" in labels

def test_gmail_provider_remove_nonexistent_label_does_not_create():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # GET labels returns empty catalog
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"labels": []}
        # batchModify returns 204
        mock_post.return_value.status_code = 204

        res = provider.apply_labels(["msg_1"], remove_labels=["MailGraph/NonExistent"])
        assert res["status"] == "success"
        assert res["count"] == 1
        # mock_post should only be called once for batchModify, NEVER for label creation
        assert mock_post.call_count == 1
        args, kwargs = mock_post.call_args
        assert "batchModify" in args[0]
        assert kwargs["json"]["removeLabelIds"] == []
        assert kwargs["timeout"] == 30.0

def test_gmail_provider_apply_labels_404_after_429():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"
    provider._label_cache["MailGraph/Stale"] = "Label_Old"

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post, patch("time.sleep"):
        # Attempt 0: 429 rate limit
        resp_429 = MagicMock(status_code=429, text="Rate limit")
        # Attempt 1: 404 not found (due to stale label ID)
        resp_404 = MagicMock(status_code=404, text="Not found")
        # Attempt 2: 204 success
        resp_204 = MagicMock(status_code=204)
        mock_post.side_effect = [resp_429, resp_404, resp_204]

        # refresh_labels returns new label ID
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "labels": [{"id": "Label_Recovered", "name": "MailGraph/Stale"}]
        }

        res = provider.apply_labels(["msg_1"], add_labels=["MailGraph/Stale"])
        assert res["status"] == "success"
        assert res["count"] == 1
        assert mock_post.call_count == 3
        # Third call must have used the updated Label_Recovered
        third_call_kwargs = mock_post.call_args_list[2][1]
        assert third_call_kwargs["json"]["addLabelIds"] == ["Label_Recovered"]

def test_gmail_provider_apply_labels_connection_error_retry():
    import requests
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"
    provider._label_cache["MailGraph/Tag"] = "Label_Tag"

    with patch("requests.post") as mock_post, patch("time.sleep") as mock_sleep:
        # Attempt 0: ConnectionError; Attempt 1: 204 Success
        resp_204 = MagicMock(status_code=204)
        mock_post.side_effect = [requests.ConnectionError("Network down"), resp_204]

        res = provider.apply_labels(["msg_1"], add_labels=["MailGraph/Tag"])
        assert res["status"] == "success"
        assert res["count"] == 1
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()

def test_gmail_provider_apply_labels_no_labels_early_return():
    provider = GmailProvider(account_email="test@gmail.com")
    provider._access_token = "mock_token"

    with patch("requests.post") as mock_post:
        res = provider.apply_labels(["msg_1", "msg_2"], add_labels=[], remove_labels=[])
        assert res["status"] == "success"
        assert res["count"] == 2
        mock_post.assert_not_called()






