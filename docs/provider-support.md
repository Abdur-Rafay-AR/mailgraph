# MailGraph: Mail Provider Support & Integration Guide

MailGraph supports offline archives, live mail protocols, and synthetic evaluation datasets.

## 1. Supported Providers Summary

| Provider | Ingestion Mode | Trash / Archive Support | Undo Support | Notes |
|---|---|---|---|---|
| **Synthetic Mailbox** | Instant generator | Full local support | Full local undo | Ideal for instant evaluation, benchmarks, and automated testing |
| **MBOX Archives** | Offline streaming | Full local support | Full local undo | Reads Google Takeout, Thunderbird, Apple Mail exports |
| **Generic IMAP** | TLS SSL / UID-based | Folder MOVE / Copy | Dependent on provider | Compatible with standard IMAP servers; uses `BODY.PEEK` to preserve unread state |
| **Gmail API** | OAuth 2.0 Loopback | Trash & Archive APIs | Untrash API | Least-privilege scopes (`gmail.readonly` initially; `gmail.modify` only on action) |

---

## 2. Synthetic Mailbox Generator

The synthetic mailbox generator creates multi-domain, multi-sender, multi-thread test mailboxes deterministically:
- Domains: Corporate (`acme-corp.com`), Newsletters (`substack.com`), Receipts (`stripe.com`, `uber.com`, `apple.com`), Security alerts (`accounts.google.com`), Notifications (`github.com`, `figma.com`), Academic (`mit.edu`).
- Realistic reply chains using RFC822 `In-Reply-To` and `References`.
- Realistic attachment sizes (`.pdf`, `.png`, `.xlsx`, `.zip`) with exact duplicate hash groups.

---

## 3. MBOX Archive Importer

- Memory-bounded streaming using standard `mailbox.mbox` and `email.policy.default`.
- Fault-tolerant: malformed MIME blocks are isolated and logged without aborting the import.
- Attachment filenames sanitized against directory traversal attacks.

---

## 4. Gmail OAuth2 Integration

- Scopes: Starts with `https://www.googleapis.com/auth/gmail.readonly`.
- User consent: Local loopback server (`http://127.0.0.1:28491/api/accounts/gmail/callback`).
- Secure Token Storage: OS Credential Manager (Windows Credential Locker / macOS Keychain via `keyring`).
- Deletion: Calls `users.messages.trash`, placing messages in the Gmail Trash folder for 30-day recovery.
