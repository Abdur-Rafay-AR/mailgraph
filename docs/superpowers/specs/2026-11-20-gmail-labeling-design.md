# Gmail Labeling & Tagging System Design

## 1. Overview & Objective

MailGraph builds a rich, local-first intelligence model of email accounts by categorizing emails (e.g. Finance, Security, Newsletters, Receipts, Personal, Work) and mapping relationships across senders and threads. 

This design specification details the architecture for **Gmail Labeling and Tagging**:
1. **1-Click Category Sync**: Batch-syncing MailGraph's detected categories directly to the user's live Gmail account under the organized parent namespace `MailGraph/` (e.g., `MailGraph/Finance`, `MailGraph/Newsletters`, `MailGraph/Receipts`).
2. **Interactive Safe Labeling**: A precision labeling action inside Cleanup Studio and Message Explorer allowing users to select or type a label, preview matching targets with full safety simulation, confirm execution, and **reversibly undo** the label application at any time.
3. **Dual Provider Support**: Seamless compatibility with both **Gmail App Passwords (IMAP)** via RFC 6154 / Google `X-GM-LABELS` and **Google Cloud OAuth (Gmail API)** via `users.messages.batchModify`.

---

## 2. Architecture & System Flow

```
+-------------------------------------------------------------------------------+
|                             MailGraph Desktop UI                              |
|   +--------------------------+   +-------------------+   +----------------+   |
|   | 1-Click Category Sync    |   | Cleanup Studio    |   | Message        |   |
|   | (Overview / Settings)    |   | (Apply Label Tab) |   | Explorer       |   |
|   +--------------------------+   +-------------------+   +----------------+   |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                                FastAPI Layer                                  |
|  - POST /api/accounts/{id}/sync-labels/preview                                |
|  - POST /api/accounts/{id}/sync-labels/execute                                |
|  - POST /api/cleanup/preview  (operation_type="label")                        |
|  - POST /api/cleanup/execute  (operation_type="label")                        |
|  - POST /api/cleanup/undo     (undoes label operation)                       |
+-------------------------------------------------------------------------------+
                 |                                              |
                 v                                              v
+------------------------------------+        +---------------------------------+
|     CategoryLabelSyncService       |        |          ActionEngine           |
| - Resolves classified messages     |        | - Query AST target evaluation   |
| - Groups by category mapping       |        | - Protection rules enforcement  |
| - Per-category operation logging   |        | - Simulation preview & safeguards|
| - High-throughput batch dispatcher |        | - Audit logging & Undo records  |
+------------------------------------+        +---------------------------------+
                 \                                              /
                  \                                            /
                   v                                          v
+-------------------------------------------------------------------------------+
|                            Provider Abstraction Layer                         |
|  AbstractMailProvider.apply_labels(provider_message_ids, add_labels, remove) |
|                                                                               |
|       +--------------------------------+   +------------------------------+   |
|       |         ImapProvider           |   |        GmailProvider         |   |
|       | - Gated read-write capability  |   | - Fresh name->ID resolution  |   |
|       | - UIDVALIDITY verification     |   | - Cache busting on 404/409   |   |
|       | - STORE +X-GM-LABELS /         |   | - users.messages.            |   |
|       |   STORE -X-GM-LABELS           |   |   batchModify(1,000 IDs max) |   |
|       | - Chunks of 100 UIDs           |   | - Exponential backoff        |   |
|       +--------------------------------+   +------------------------------+   |
+-------------------------------------------------------------------------------+
                                      |
                                      v
                         Remote Gmail Account (Live)
```

---

## 3. Security, Privacy & Stated Capability Changes

### 3.1 IMAP Capability Transition: Read-Only to Explicit Gated Mutation
- **Explicit Capability Declaration**: The existing IMAP ingestion pipeline operates in strict read-only mode (`readonly=True` during `EXAMINE` or `SELECT`). Labeling requires issuing `STORE +X-GM-LABELS`, which mandates selecting the target mailbox with `readonly=False`.
- **Gating Mechanism**: The IMAP client will **never** open a mailbox in read-write mode during ingestion, search, or background scanning. Read-write selection is strictly isolated within `apply_labels()` and is only invoked when an action has been explicitly confirmed by the user.
- **Safety Boundary**: The provider will only ever issue `STORE +X-GM-LABELS` or `STORE -X-GM-LABELS`. It is programmatically barred from issuing `STORE +FLAGS (\Deleted)` or `EXPUNGE` during label mutations.

### 3.2 OAuth Scope Escalation (`gmail.modify`) & Consent UX
- Connecting via Google OAuth previously requested `READONLY_SCOPE` (`https://www.googleapis.com/auth/gmail.readonly`). Applying labels requires `MODIFY_SCOPE` (`https://www.googleapis.com/auth/gmail.modify`).
- **UI Consent Notice**: When a user initiates Gmail OAuth connection or attempts to use labeling with an existing read-only token, the UI presents an explicit dialog:
  > *"To organize your inbox, MailGraph requires permission to create and apply labels in your Gmail account. MailGraph runs 100% locally on your computer—your emails and credentials never leave this machine."*
- If an existing account only has `readonly` authorization, labeling triggers a prompt to re-authenticate with write consent.

---

## 4. Provider Layer Implementation

### 4.1 Interface Expansion (`backend/app/providers/base.py`)
```python
def apply_labels(
    self,
    provider_message_ids: List[str],
    add_labels: Optional[List[str]] = None,
    remove_labels: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Apply or remove labels on target messages on the remote server."""
    raise NotImplementedError("Label manipulation not supported by this provider.")

def list_labels(self) -> List[str]:
    """List existing custom and system labels from the provider."""
    return []
```
Update `ProviderCapabilities(supports_labels=True)`.

### 4.2 IMAP Implementation (`backend/app/providers/imap.py`)
When connecting to Gmail via IMAP (`imap.gmail.com` with App Password):

#### A. UIDVALIDITY Verification (Preventing Silent Mislabeling)
IMAP UIDs are strictly valid only within a specific mailbox's `UIDVALIDITY` generation value.
1. During initial ingestion, MailGraph stores `uidvalidity` in the `folders` table alongside `provider_folder_id`.
2. Before executing any `UID STORE` in `apply_labels()`:
   - Select the target folder in read-write mode: `typ, data = self.client.select(f'"{folder}"', readonly=False)`
   - Parse `UIDVALIDITY` from response: `res, val = self.client.response("UIDVALIDITY")` or regex match `[UIDVALIDITY <value>]`.
   - Compare with stored `uidvalidity`. If there is a mismatch (indicating UIDs were invalidated by the server), the operation **aborts immediately** with a `UIDValidityChangedError` and prompts the user to refresh their folder index.

#### B. Label Creation & Sanitization
- Check if folder/label exists via `list(pattern=f'"{label_name}"')`.
- If missing, create via `client.create(f'"{label_name}"')`.
- Gmail automatically exposes created folders as Gmail labels and respects hierarchical slashes (`MailGraph/Finance`).

#### C. Applying Labels (`+X-GM-LABELS`) & Removing (`-X-GM-LABELS`)
- Parse UIDs and active folders from `provider_message_ids` (format: `imap_<folder>_<uid>`).
- Group by folder, verify `UIDVALIDITY`, and process in chunks of **100 UIDs** (to prevent command-line buffer overflows).
  ```python
  uid_set = ",".join(chunk)
  for lbl in add_labels:
      self.client.uid("STORE", uid_set, "+X-GM-LABELS", f'("{lbl}")')
  ```
- For undoing:
  ```python
  for lbl in remove_labels:
      self.client.uid("STORE", uid_set, "-X-GM-LABELS", f'("{lbl}")')
  ```

### 4.3 Gmail REST API Implementation (`backend/app/providers/gmail.py`)

#### A. Fresh Name &rarr; Label ID Resolution & Cache Busting
`batchModify` requires Google label IDs (e.g. `Label_142`), not display names.
1. `resolve_or_create_label_id(display_name: str) -> str`:
   - Checks local cache of `{display_name: label_id}`.
   - If not in cache or if a previous call returned 404, queries `GET https://gmail.googleapis.com/gmail/v1/users/me/labels` to refresh the label catalog.
   - If label name does not exist on Gmail:
     - Issues `POST https://gmail.googleapis.com/gmail/v1/users/me/labels` with `{"name": display_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}`.
     - On HTTP 409 (Conflict/Already Exists - user created label concurrently in web): forces a fresh cache refresh from `GET .../labels` and grabs the newly detected label ID.
   - Returns the verified Google `label_id`.

#### B. Batch Modification & Rate Limiting
- Chunks message IDs into **up to 1,000 IDs per request** (Gmail API's official maximum for `batchModify`).
- Payload structure:
  ```json
  {
    "ids": ["msg_id_1", "msg_id_2", ...],
    "addLabelIds": ["Label_142"],
    "removeLabelIds": []
  }
  ```
- Implements exponential backoff with jitter on HTTP 429 (rate limit) or 503 (backend overload).

---

## 5. ActionEngine & Safe Operations

### 5.1 Enforcement of Protection Rules
In `backend/app/actions/engine.py`:
- By default, all operations enforce `exclude_protected=True`.
- When querying targets for `operation_type="label"`:
  - Query compilation automatically joins active `protection_rules` (e.g. `no-reply@accounts.google.com`, `apple.com`, `github.com`, and starred senders marked as protected).
  - Protected messages are strictly filtered out of the target set.
  - The preview calculation explicitly reports `protected_excluded_count`. If a user attempts to label protected messages, they are notified that protected contacts have been safeguarded and will not be labeled unless explicitly unshielded.

### 5.2 Label Operations, Idempotency & Undo
- **`calculate_preview(account_id, operation_type, ast, label_name=None)`**:
  - Compiles the AST to find all target messages.
  - Returns target count, total size bytes, distinct thread count, protected exclusions, and top senders.
  - Returns `reversibility_note="Reversible: Labels can be completely removed using the Undo button."` and `reversible=True`.
- **`execute_action(account_id, operation_type, ast, label_name=None, sync_remote=True)`**:
  - Validates `label_name` is non-empty.
  - Inserts row in `operations` table (`operation_type='label'`).
  - Records each target in `operation_items`:
    - `original_state_json`: `{}`.
    - `result_state_json`: `{"added_label": label_name}`.
  - Dispatches remote call to `remote_provider.apply_labels(target_pids, add_labels=[label_name])`.
- **`undo_operation(operation_id)`**:
  - Fetches successful `operation_items`.
  - Extracts `added_label` from `result_state_json`.
  - Calls `remote_provider.apply_labels(target_pids, remove_labels=[added_label])`.
  - Sets operation status to `'undone'`.

---

## 6. 1-Click Category Sync Service

### 6.1 Category Mapping Rules (`backend/app/classification/category_sync.py`)
Maps MailGraph's 16 local categories to human-friendly Gmail nested labels:

| MailGraph Category | Gmail Label |
|---|---|
| `finance` | `MailGraph/Finance` |
| `security` | `MailGraph/Security` |
| `receipt_invoice` | `MailGraph/Receipts` |
| `newsletter` | `MailGraph/Newsletters` |
| `promotional` | `MailGraph/Promotional` |
| `work` | `MailGraph/Work` |
| `personal` | `MailGraph/Personal` |
| `university` | `MailGraph/University` |
| `social` | `MailGraph/Social` |
| `calendar` | `MailGraph/Calendar` |
| `notification` | `MailGraph/Notifications` |
| `automated_report` | `MailGraph/Reports` |
| `cold_outreach` | `MailGraph/Cold Outreach` |

### 6.2 Granular Undo Architecture & Batch Linking
To ensure users are not forced into an all-or-nothing undo:
- When a user triggers **Category Sync**, a unique `batch_sync_id` (UUID) is generated.
- MailGraph executes the sync per-category and records **one distinct record in the `operations` table per category** (e.g., `operation_type='label'`, `label_name='MailGraph/Finance'`, query snapshot, `batch_id=batch_sync_id`).
- **Granular Undo**: The user can selectively undo just one category (e.g. undo `MailGraph/Promotional` while keeping `MailGraph/Finance` and `MailGraph/Receipts`).
- **Batch Undo**: The user can also click "Undo Entire Sync" which restores all operations associated with that `batch_sync_id`.

### 6.3 Idempotency & Partial Execution Resume
- Before dispatching label additions, MailGraph checks `operation_items` for messages that already have a successful `'label'` operation recorded with the target label.
- If a sync is interrupted mid-batch (e.g., laptop sleep, network drop, server restart):
  - On restart/resume, the service queries already-labeled items and only processes the remaining un-synced delta.
  - No duplicate requests are sent to Gmail.

---

## 7. API Endpoints

1. `POST /api/cleanup/preview`:
   - Payload: `CleanupPreviewRequest` with `operation_type="label"` and `label_name: str`.
   - Returns preview metrics with protected exclusions.
2. `POST /api/cleanup/execute`:
   - Payload: `CleanupExecuteRequest` with `operation_type="label"` and `label_name: str`.
   - Executes label operation across query-matched messages and logs undoable audit trail.
3. `POST /api/accounts/{account_id}/sync-labels/preview`:
   - Returns JSON breakdown:
     ```json
     {
       "account_id": 1,
       "total_messages": 1420,
       "categories": [
         {"category": "finance", "label": "MailGraph/Finance", "count": 320},
         {"category": "newsletter", "label": "MailGraph/Newsletters", "count": 650},
         {"category": "receipt_invoice", "label": "MailGraph/Receipts", "count": 210}
       ]
     }
     ```
4. `POST /api/accounts/{account_id}/sync-labels/execute`:
   - Body: `{"categories": ["finance", "newsletter", ...], "batch_id": Optional[str]}`
   - Triggers batch labeling across selected categories.
   - Returns list of created `operation_ids` per category and sync summary.
5. `GET /api/accounts/{account_id}/labels`:
   - Returns current labels in the user's Gmail account.

---

## 8. Frontend User Experience

### 8.1 Cleanup Studio (`apps/desktop/src/features/cleanup`)
- Adds a third action pill/tab: **"Apply Label"** (joining "Move to Trash" and "Archive").
- Label selector: Suggests `MailGraph/<Category>` presets with custom input support.
- Real-time simulation preview showing target count, storage size, protected exclusions, and samples.
- Action button: `Apply Label 'MailGraph/Finance' to 342 Messages`.
- Audit log includes 1-click **Undo** to remove applied labels from Gmail.

### 8.2 Overview Page (`apps/desktop/src/features/overview`)
- Adds a **"Gmail Category Sync"** banner card:
  - Summarizes detected intelligence: *"MailGraph has categorized 1,420 messages across 6 categories."*
  - Action button: `Sync Categories to Gmail`.
  - Preview modal with category checklist toggles (choose which categories to sync).
  - Progress bar displaying real-time sync progress (`Syncing Finance: 150/320 (47%)`).

### 8.3 Message Explorer (`apps/desktop/src/features/messages`)
- Toolbar includes a `Tag in Gmail` dropdown button.
- Applies a selected or custom label directly to all messages matching current search filters.

---

## 9. Verification & Testing

1. **Backend Tests**:
   - `test_actions_engine.py`: Test preview, execution, protected contact shielding, and undo for `label` operation type.
   - `test_providers.py`:
     - Test IMAP UIDVALIDITY mismatch detection and error abort.
     - Mock IMAP client testing `client.create()` and `STORE +X-GM-LABELS` / `-X-GM-LABELS`.
     - Test Gmail API fresh name &rarr; ID resolution, cache refresh on 404/409, and `batchModify` with 1,000 chunk limit.
   - `test_category_sync.py`: Unit test category mapping, granular per-category operation generation, resume on partial failure, and batch undo.
   - `test_api_endpoints.py`: Integration test for all new endpoints (`/api/accounts/{id}/sync-labels/*`, `/api/cleanup/*`).
2. **Frontend Build & UI Check**:
   - Run `npm run build` in `apps/desktop` to ensure TypeScript compilation and zero build warnings.
   - Verify modal, tabs, and progress indicator rendering in the desktop UI.
