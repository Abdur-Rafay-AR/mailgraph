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
| - Groups by category mapping       |        | - Simulation preview & safeguards|
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
|       | - Ensures mailbox exists       |   | - users.labels.create()      |   |
|       | - STORE +X-GM-LABELS /         |   | - users.messages.            |   |
|       |   STORE -X-GM-LABELS           |   |   batchModify()              |   |
|       | - Chunks of 100 UIDs           |   | - Exponential backoff        |   |
|       +--------------------------------+   +------------------------------+   |
+-------------------------------------------------------------------------------+
                                      |
                                      v
                         Remote Gmail Account (Live)
```

---

## 3. Provider Layer Implementation

### 3.1 Interface Expansion (`backend/app/providers/base.py`)
Extend `AbstractMailProvider` with methods for label inspection and mutation:
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

### 3.2 IMAP Implementation (`backend/app/providers/imap.py`)
When connecting to Gmail via IMAP (`imap.gmail.com` with App Password):
1. **Label Creation / Verification**:
   - Check if folder/label exists via `list(pattern=f'"{label_name}"')`.
   - If not found, create via `client.create(f'"{label_name}"')`.
   - Gmail automatically exposes created folders as Gmail labels and respects hierarchical slashes (`MailGraph/Finance`).
2. **Applying Labels (`+X-GM-LABELS`)**:
   - Parse UIDs and active folders from `provider_message_ids` (format: `imap_<folder>_<uid>`).
   - Group by folder and select the folder in read-write mode (`client.select(f'"{folder}"', readonly=False)`).
   - In chunks of 100 UIDs:
     ```python
     uid_set = ",".join(chunk)
     for lbl in add_labels:
         # Escape label name in quotes
         client.uid("STORE", uid_set, "+X-GM-LABELS", f'("{lbl}")')
     ```
3. **Removing Labels (`-X-GM-LABELS` for Undo)**:
   - For undoing:
     ```python
     for lbl in remove_labels:
         client.uid("STORE", uid_set, "-X-GM-LABELS", f'("{lbl}")')
     ```
4. **Safety**: Never modifies message flags (`\Seen`, `\Deleted`), never executes `EXPUNGE`, and never removes messages from `INBOX`.

### 3.3 Gmail REST API Implementation (`backend/app/providers/gmail.py`)
1. **OAuth Scopes**:
   - Update default scope in `scripts/connect_gmail.py` and `backend/app/providers/gmail.py` to `MODIFY_SCOPE` (`https://www.googleapis.com/auth/gmail.modify`).
2. **Label Resolution**:
   - Cache Gmail labels via `GET https://gmail.googleapis.com/gmail/v1/users/me/labels`.
   - If `MailGraph/Category` label does not exist, create via `POST https://gmail.googleapis.com/gmail/v1/users/me/labels` with `{"name": "MailGraph/...", "labelListVisibility": "labelShow", "messageListVisibility": "show"}`.
3. **Batch Modification**:
   - Call `POST https://gmail.googleapis.com/gmail/v1/users/me/messages/batchModify` with:
     ```json
     {
       "ids": ["msg_id_1", "msg_id_2", ...],
       "addLabelIds": [label_id],
       "removeLabelIds": []
     }
     ```
   - Chunks of up to 1,000 message IDs with exponential backoff on HTTP 429/503.

---

## 4. ActionEngine & Safe Operations

### 4.1 Schema & Operation Types (`backend/app/actions/engine.py`)
Extend `ActionEngine` to support `operation_type == "label"`:
- **`calculate_preview(account_id, operation_type, ast, label_name=None)`**:
  - Compiles the AST to find all target messages.
  - Calculates count, total size bytes, distinct thread count, protected messages excluded, and top senders.
  - Returns `reversibility_note="Reversible: Labels can be completely removed using the Undo button."` and `reversible=True`.
- **`execute_action(account_id, operation_type, ast, label_name=None, sync_remote=True)`**:
  - Validates `label_name` is non-empty.
  - Inserts row in `operations` table (`operation_type='label'`).
  - For each message, records `operation_items`:
    - `original_state_json`: records current label state or `{}`.
    - `result_state_json`: `{"added_label": label_name}`.
  - Dispatches remote call to `remote_provider.apply_labels(target_pids, add_labels=[label_name])`.
- **`undo_operation(operation_id)`**:
  - Fetches successful `operation_items`.
  - Extracts `added_label` from `result_state_json`.
  - Calls `remote_provider.apply_labels(target_pids, remove_labels=[added_label])`.
  - Sets operation status to `'undone'`.

---

## 5. 1-Click Category Sync Service

### 5.1 Mapping Rules (`backend/app/classification/category_sync.py`)
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

### 5.2 Workflow
1. **Preview**:
   - Queries `SELECT c.name, COUNT(mc.message_id) FROM message_categories mc JOIN categories c ON mc.category_id = c.id JOIN messages m ON mc.message_id = m.id WHERE m.account_id = ? GROUP BY c.name;`
   - Returns a structured preview: categories list, corresponding Gmail label names, and message count per label.
2. **Execute**:
   - Iterates through categories, fetching provider message IDs.
   - Applies the corresponding `MailGraph/<Name>` label via `remote_provider.apply_labels()`.
   - Records an aggregate operation entry in `operations` so the sync operation is fully auditable and undoable.

---

## 6. API Endpoints

1. `POST /api/cleanup/preview`:
   - Extends payload with `label_name: Optional[str]`.
   - Allows previewing cleanup actions with `operation_type="label"`.
2. `POST /api/cleanup/execute`:
   - Extends payload with `label_name: Optional[str]`.
   - Executes label operation across query-matched messages.
3. `POST /api/accounts/{account_id}/sync-labels/preview`:
   - Returns JSON:
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
   - Triggers batch labeling across selected categories.
   - Returns operation details (`operation_id`, `labeled_count`, `categories_synced`).
5. `GET /api/accounts/{account_id}/labels`:
   - Returns existing labels in the user's Gmail account.

---

## 7. Frontend User Experience

### 7.1 Cleanup Studio (`apps/desktop/src/features/cleanup`)
- Adds a third action pill/tab: **"Apply Label"** (joining "Move to Trash" and "Archive").
- When selected:
  - Label Input: Dropdown populated with standard suggestions (`MailGraph/Finance`, `MailGraph/Receipts`, etc.) with an input field to type any custom label name.
  - Real-time simulation preview showing:
    - Target count & total size.
    - Protected messages excluded.
    - Top senders affected.
    - Representative message samples.
  - Action button: `Apply Label 'MailGraph/Finance' to 342 Messages`.
  - Audit log at the bottom displays past label operations with a 1-click **Undo** button.

### 7.2 Overview Page (`apps/desktop/src/features/overview`)
- Adds a **"Gmail Category Sync"** banner card:
  - Summarizes detected intelligence: *"MailGraph has categorized 1,420 messages across 6 categories."*
  - Action button: `Sync Categories to Gmail`.
  - Clicking opens a breakdown modal showing each category, its count, and target Gmail label, with a `Confirm & Sync` button.
  - Progress bar displays real-time sync progress (`Syncing: 450/1,420 (31%)`).

### 7.3 Message Explorer (`apps/desktop/src/features/messages`)
- Toolbar includes a `Tag in Gmail` dropdown button.
- Applies a selected or custom label directly to all messages matching the current search filters.

---

## 8. Safety, Reversibility & Error Handling

1. **Non-Destructive**: Labeling only adds tags; it never removes messages from the Inbox, never deletes messages, and never modifies subject or body.
2. **Chunking & Throttling**: Batch size limited to 100 UIDs for IMAP and 500 IDs for Gmail REST API to avoid buffer and rate limits.
3. **Resilience**: If IMAP disconnects, the provider reconnects and retries the failed chunk.
4. **Complete Undoability**: All label applications log `operation_items` mapping each message ID to the applied label, allowing instant bulk undo via `STORE -X-GM-LABELS`.
5. **Protection Rules**: Safeguards are strictly applied so protected contacts (e.g. Google security notifications) are never mislabeled or modified without explicit user choice.

---

## 9. Verification & Testing

1. **Backend Tests**:
   - `test_actions_engine.py`: Test preview, execution, and undo for `label` operation type.
   - `test_providers.py`: Mock IMAP client testing `client.create()` and `STORE +X-GM-LABELS` / `-X-GM-LABELS`.
   - `test_category_sync.py`: Unit test category mapping, preview aggregation, and chunked execution.
   - `test_api_endpoints.py`: Integration test for all new endpoints (`/api/accounts/{id}/sync-labels/*`, `/api/cleanup/*`).
2. **Frontend Build & UI Check**:
   - Run `npm run build` in `apps/desktop` to ensure TypeScript compilation and zero build warnings.
   - Verify modal, tabs, and progress indicator rendering in the desktop UI.
