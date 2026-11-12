# Mailgraph: Agent Specification

> **Working title:** Mailgraph  
> **Document:** `agent-spec.md`  
> **Purpose:** Product, architecture, implementation, and safety specification for a local-first email intelligence and cleanup desktop application.  
> **Status:** Initial implementation specification  
> **Primary principle:** Understand the mailbox before changing it. Every destructive action must be inspectable, explicit, and recoverable where the provider allows.

---

## 0. Instructions to the coding agent

You are implementing a real desktop application, not a mockup or a landing page.

### Non-negotiable engineering rules

1. **Local-first:** Email content, metadata, indexes, graph data, and AI results remain on the user's machine by default.
2. **No surprise network calls:** Network access is limited to explicitly configured mail providers and explicitly enabled optional local-model endpoints. No telemetry, analytics, crash upload, remote fonts, remote scripts, or hosted AI by default.
3. **Read-only first:** Initial connection and indexing must never modify mailbox state.
4. **No autonomous deletion:** AI may classify, explain, and recommend. It must never execute delete, archive, unsubscribe, block, or move operations without an explicit user action.
5. **Preview before mutation:** Every bulk operation must show its exact target count, representative samples, exclusions, and expected outcome before confirmation.
6. **Recoverability:** Prefer moving messages to the provider's Trash/Deleted Items or a recoverable folder. Never permanently delete by default.
7. **Provider-aware behavior:** Do not assume Gmail, generic IMAP, Outlook, and local MBOX have identical semantics.
8. **Incremental processing:** Support resumable scans, checkpoints, cancellation, and incremental synchronization. Never require a full re-import for routine updates.
9. **Privacy by design:** Minimize stored message-body content, protect credentials, and make data retention visible and configurable.
10. **No fake functionality:** Do not ship buttons, filters, graph controls, or status indicators that are decorative or unimplemented.
11. **Test destructive flows:** Provider adapters, query compilation, selection counts, protection rules, and undo behavior require automated tests.
12. **Keep scope controlled:** Implement the milestones in order. Do not build speculative features before the core ingestion, indexing, graph, and safe-action pipeline works.

### Before changing the repository

- Inspect the existing repository and report its current structure, language, framework, and implementation status.
- Preserve useful existing code and conventions.
- Create or update `README.md`, `.gitignore`, and this specification only where appropriate.
- Never place real mailbox data, OAuth tokens, app passwords, `.env` files, database files, exports, or test fixtures derived from a real mailbox in Git.
- Use synthetic fixtures for tests and screenshots.
- If a design or provider detail is ambiguous, choose the safest reversible behavior and document the assumption.

---

# 1. Product definition

## 1.1 Vision

Build a local-first desktop application that turns a large mailbox into an explorable, searchable, and actionable model.

The application should help a user answer:

- Who and what is generating most of my email?
- Which organizations, senders, threads, and periods dominate my mailbox?
- Which messages are likely important, transactional, promotional, automated, or obsolete?
- What am I about to delete or archive, exactly?
- How much storage could I recover?
- Which conversations, attachments, or relationships might I be overlooking?
- Can I clean up years of email without handing my mailbox to a third-party service?

This is not intended to replace Gmail, Outlook, or Thunderbird. It is an intelligence and maintenance layer for existing mailboxes.

## 1.2 Product positioning

**An interactive map of your email, with safe tools to act on what you discover.**

The graph is a core interface, but the product must remain useful without it. Every insight shown in a graph must also be accessible through tables, search, filters, and keyboard-accessible controls.

## 1.3 Target user

Initial target:

- Individuals with years of accumulated email.
- Users with large Gmail or IMAP mailboxes.
- People who want local processing and do not want to upload mailbox contents to a SaaS cleaner.
- Technical users comfortable connecting an account or importing an archive.

Initial platform: Windows first, with architecture that does not prevent macOS and Linux support.

## 1.4 Non-goals for the first release

Do not build these in the MVP:

- A full email client or message composer.
- A new mail server.
- Automatic AI deletion.
- Cloud synchronization of the local index.
- Team collaboration or shared mailbox administration.
- A hosted account system.
- A general-purpose CRM.
- Automatic sending of unsubscribe emails without review.
- Permanent deletion or mailbox-wide empty-trash operations.
- A complex multi-agent architecture. A deterministic pipeline with optional local AI is sufficient.

---

# 2. Product principles and differentiators

Existing tools already cover parts of mailbox visualization, sender analytics, bulk deletion, attachment analysis, full-text search, and local AI. Do not claim these individual capabilities are novel.

The product should differentiate through the combination and depth of the following capabilities.

## 2.1 Multi-resolution mailbox graph

Provide a navigable hierarchy:

`Account → Organization/Domain → Sender → Thread → Message → Attachment`

The user can zoom between levels instead of rendering every email as a node immediately.

Graph requirements:

- Nodes represent accounts, domains/organizations, senders, threads, messages, and optionally attachments.
- Edges represent sender membership, message participation, thread membership, reply relationships, and attachment references.
- Node size can encode message count, total bytes, or another explicitly selected metric.
- Node color can encode user-selected categories or classification states.
- Clusters can be expanded and collapsed.
- Selecting a node filters the rest of the application.
- Selecting multiple nodes creates a union selection.
- The UI must display why two nodes are connected.
- Graph layout must be deterministic enough that the same dataset does not jump unpredictably after minor refreshes.
- Large graphs must use aggregation, progressive expansion, and viewport-aware rendering.
- Provide a non-graph table/list alternative for accessibility and performance.

Do not imply that graph edges establish trust, identity, or real-world relationships. They only represent observed email metadata.

## 2.2 Graph-to-action workflow

This is a core differentiator.

A user should be able to:

1. Select a domain, sender, thread, or graph cluster.
2. Inspect the exact matching messages.
3. Add filters such as date, read state, labels/folders, size, attachment presence, and category.
4. Exclude protected senders, domains, or individual messages.
5. Preview the exact operation.
6. Confirm the operation.
7. See progress and per-message outcomes.
8. Undo where supported.
9. Inspect the operation in an audit log.

Graph selection must never directly execute a destructive action.

## 2.3 Email time machine

Build historical views using message timestamps and available metadata:

- Message volume by day, week, month, and year.
- Sender/domain activity over time.
- First-seen and last-seen dates.
- Subscription lifecycle: first observed, most recent, active/inactive.
- Periods of unusually high incoming volume.
- Conversation activity timelines.
- Changes in unread backlog over time, only where historical data actually exists.

Do not invent historical read/open data. Many providers do not expose reliable historical open events. Clearly distinguish observed facts from estimates.

## 2.4 Explainable sender and conversation intelligence

For each sender and domain, show observable metrics:

- Total received messages.
- First and last observed message.
- Total message bytes, with provider-specific caveats.
- Unread count.
- Number of distinct threads.
- Number of sent replies, when sent mail is included and reliably associated.
- Attachment count and total attachment bytes.
- Category distribution.
- Recent activity.

Do not present an opaque "trust score." Use transparent signals and labels such as `protected`, `known`, `unclassified`, `bulk sender`, or `user blocked`.

Reply rate and engagement metrics must be labelled as estimates and must account for incomplete sent-mail access, aliases, multiple recipients, and thread matching.

## 2.5 Cleanup simulation

Before any mutation, calculate and show:

- Number of messages matched.
- Number of threads affected.
- Total estimated message bytes.
- Attachment bytes involved, if known.
- Date range.
- Sender/domain breakdown.
- Protected messages excluded.
- Messages that cannot be safely acted upon.
- Whether the action is reversible and for how long, based on provider behavior.

The simulation must be based on the same query and protection logic used by the execution path. Do not calculate a preview with one filter implementation and execute with another.

## 2.6 Local semantic exploration

Optional local AI can help users find patterns that are difficult to express with exact filters.

Examples:

- "Find newsletters I have not interacted with in a year."
- "Show automated notifications from development tools."
- "Find old conversations with attachments larger than 5 MB."
- "Find likely receipts and invoices from 2023."
- "Show senders that became inactive."

AI output must be translated into an inspectable structured query. Show the interpreted filters and let the user edit them.

AI must not be the source of truth for message identity, provider state, or deletion targets. Final targets must be resolved by deterministic database queries.

## 2.7 Attachment intelligence

- List attachments independently of messages.
- Filter by filename, extension, MIME type, sender, date, and size.
- Detect exact duplicate attachment content using a cryptographic hash when the content is locally available.
- Show duplicate groups and all messages referencing each file.
- Support local export of selected attachments.
- Identify unusually large attachments and storage-heavy senders.
- Never delete or detach attachments in the MVP.
- Any future attachment removal must be a separate, provider-aware, backup-first operation with an explicit warning.

## 2.8 "What am I missing?" insights

Generate explainable, non-destructive insights such as:

- Old unread messages from frequently contacted senders.
- Threads with a received message and no detected reply.
- High-volume senders with little observed interaction.
- Subscriptions with no recent messages.
- Important senders buried among bulk notifications.
- Large attachment clusters.
- Sudden changes in sender volume.
- Messages from protected or user-starred senders that match a cleanup query.

Every insight must explain its evidence and limitations. Do not claim that a message was ignored or that a person expects a reply.

---

# 3. Core user journeys

## 3.1 First launch

1. User launches the application.
2. App explains local data handling and provider permissions.
3. User chooses one of:
   - Connect Gmail.
   - Connect another supported IMAP account.
   - Import MBOX.
   - Import Maildir.
   - Start with synthetic demo data.
4. App shows the exact requested permissions before OAuth consent.
5. User connects/imports.
6. App begins a read-only scan.
7. Progress shows folders, messages processed, current phase, errors, and cancellation.
8. App builds indexes and graph aggregates.
9. User lands on the mailbox overview.

No mailbox mutation is allowed during setup or indexing.

## 3.2 Explore the mailbox

1. Open Overview.
2. See message count, date coverage, unread count, largest senders, and storage estimates.
3. Open Graph Explorer.
4. Select a domain cluster.
5. Inspect sender nodes.
6. Select a sender.
7. Inspect matching threads and messages in a side panel.
8. Refine with date, category, unread, attachment, and folder filters.
9. Save the resulting selection as a named view.

## 3.3 Clean a sender or cluster

1. Select a sender/domain/cluster.
2. Choose `Review messages`.
3. Choose archive or move to Trash.
4. Review exact targets and protected exclusions.
5. Expand samples and inspect message details.
6. Confirm with an explicit action-specific button.
7. Show operation progress.
8. Show completed, failed, skipped, and uncertain results.
9. Offer undo if provider semantics permit.
10. Record the operation in the local audit log.

## 3.4 Natural-language exploration

1. User enters a request.
2. Local model interprets the request, if configured.
3. App displays the proposed structured filters.
4. User edits/approves the filters.
5. App executes a read-only query.
6. Results appear in the normal message list and graph.
7. User independently chooses whether to take an action.

## 3.5 Backup and restore

Before a destructive operation, allow the user to choose a local backup policy.

- Store raw RFC822 `.eml` messages where supported.
- Store a manifest with provider/account identifier, message identifier, thread identifier, labels/folders, and backup timestamp.
- Encrypt backups when configured.
- Clearly state that restoring an exported message may not restore original server IDs, labels, flags, or thread placement.
- Never promise perfect restoration across providers.

---

# 4. Functional requirements

Priority levels:

- **P0:** Required for a usable and safe MVP.
- **P1:** Important after the core MVP.
- **P2:** Advanced/future capability.

## 4.1 Account and import management

| ID | Priority | Requirement |
|---|---|---|
| ACC-01 | P0 | Support MBOX import. |
| ACC-02 | P0 | Support Gmail OAuth connection. |
| ACC-03 | P0 | Support generic IMAP connection through a provider adapter. |
| ACC-04 | P0 | Support multiple local account profiles. |
| ACC-05 | P0 | Store credentials in OS credential storage where available. |
| ACC-06 | P0 | Display account identity and granted permissions. |
| ACC-07 | P0 | Allow disconnecting an account and separately choosing whether to delete its local index. |
| ACC-08 | P1 | Support Maildir import. |
| ACC-09 | P1 | Support incremental synchronization. |
| ACC-10 | P1 | Support resumable import after interruption. |
| ACC-11 | P2 | Add Outlook/Microsoft Graph adapter. |

## 4.2 Ingestion and normalization

| ID | Priority | Requirement |
|---|---|---|
| ING-01 | P0 | Parse RFC822/MIME messages safely. |
| ING-02 | P0 | Normalize sender, recipients, subject, timestamps, message IDs, references, labels/folders, flags, and size. |
| ING-03 | P0 | Preserve original provider identifiers. |
| ING-04 | P0 | Deduplicate imported messages using stable identifiers and content fingerprints where appropriate. |
| ING-05 | P0 | Handle malformed MIME messages without aborting the full scan. |
| ING-06 | P0 | Process attachments as metadata first; do not extract all attachment bodies by default. |
| ING-07 | P0 | Record ingestion errors and allow retry. |
| ING-08 | P1 | Detect probable duplicate messages across accounts. |
| ING-09 | P1 | Parse List-Unsubscribe headers without automatically unsubscribing. |
| ING-10 | P1 | Support incremental updates and deletion/state reconciliation. |

## 4.3 Search and filtering

| ID | Priority | Requirement |
|---|---|---|
| SRCH-01 | P0 | Search sender, recipient, subject, date, folder/label, read state, and attachment presence. |
| SRCH-02 | P0 | Full-text search subject and locally indexed body text, configurable by user. |
| SRCH-03 | P0 | Combine filters with explicit AND/OR groups. |
| SRCH-04 | P0 | Show live result counts. |
| SRCH-05 | P0 | Save and rename searches. |
| SRCH-06 | P0 | Export search results as CSV. |
| SRCH-07 | P1 | Search attachment filenames and MIME types. |
| SRCH-08 | P1 | Support semantic search using optional local embeddings. |
| SRCH-09 | P1 | Parse natural-language requests into visible structured filters. |
| SRCH-10 | P2 | Cross-account unified search. |

## 4.4 Graph explorer

| ID | Priority | Requirement |
|---|---|---|
| GRAPH-01 | P0 | Show domain/sender/thread relationships. |
| GRAPH-02 | P0 | Aggregate large message sets instead of rendering every message. |
| GRAPH-03 | P0 | Expand and collapse graph nodes. |
| GRAPH-04 | P0 | Select one or multiple nodes. |
| GRAPH-05 | P0 | Selecting graph nodes filters the message table. |
| GRAPH-06 | P0 | Show node metrics and evidence in a details panel. |
| GRAPH-07 | P0 | Provide date and category filters. |
| GRAPH-08 | P1 | Add timeline-based graph exploration. |
| GRAPH-09 | P1 | Add thread-level and attachment-level views. |
| GRAPH-10 | P1 | Add graph clustering and community detection with explainable parameters. |
| GRAPH-11 | P1 | Save graph layouts and named selections. |
| GRAPH-12 | P2 | Add cross-account relationship graphs. |

## 4.5 Classification and insights

| ID | Priority | Requirement |
|---|---|---|
| CLS-01 | P0 | Provide deterministic baseline categories. |
| CLS-02 | P0 | Allow users to override categories. |
| CLS-03 | P0 | Display classification reason and confidence/uncertainty. |
| CLS-04 | P0 | Never let category alone trigger deletion. |
| CLS-05 | P1 | Optional local model classification. |
| CLS-06 | P1 | Sender behavior metrics and activity history. |
| CLS-07 | P1 | Subscription lifecycle discovery. |
| CLS-08 | P1 | "What am I missing?" insight feed. |
| CLS-09 | P1 | Learn user preferences from explicit keep/archive/delete decisions, with opt-in and inspectable rules. |
| CLS-10 | P2 | Local anomaly detection for unusual sender or volume behavior. |

Initial categories:

- `important`
- `personal`
- `work`
- `university`
- `transactional`
- `receipt_invoice`
- `security`
- `calendar`
- `notification`
- `newsletter`
- `promotional`
- `social`
- `automated_report`
- `cold_outreach`
- `unknown`

Categories are suggestions, not facts. Users can rename, merge, disable, and override them.

## 4.6 Cleanup and actions

| ID | Priority | Requirement |
|---|---|---|
| ACT-01 | P0 | Archive selected messages where provider supports it. |
| ACT-02 | P0 | Move selected messages to Trash/Deleted Items where supported. |
| ACT-03 | P0 | Preview exact targets before action. |
| ACT-04 | P0 | Enforce protected sender/domain/message rules. |
| ACT-05 | P0 | Require explicit confirmation for every bulk mutation. |
| ACT-06 | P0 | Log operation and per-message outcomes. |
| ACT-07 | P0 | Provide undo where provider supports a reliable inverse operation. |
| ACT-08 | P0 | Support cancellation of long-running actions. |
| ACT-09 | P0 | Make retries idempotent where possible. |
| ACT-10 | P1 | Apply/remove labels or move to folders. |
| ACT-11 | P1 | Generate unsubscribe review list from headers. |
| ACT-12 | P1 | Execute one-click unsubscribe only after separate user approval. |
| ACT-13 | P2 | Optional scheduled cleanup, disabled by default and always scoped to a saved user-approved rule. |

### Protected data defaults

Create a protection system with multiple layers:

- User-protected senders.
- User-protected domains.
- User-protected messages and threads.
- Provider labels/folders such as starred, important, flagged, or user-defined protected labels where available.
- Configurable high-risk categories such as security, financial, government, identity, password reset, receipts, invoices, travel, and calendar.
- Optional user-defined rules.

Protection must be evaluated in the final target query, not just displayed as a warning.

A protected message must not be included in an action unless the user explicitly overrides protection in a separate, clearly explained confirmation step. Do not make broad override the default.

## 4.7 Attachment intelligence

| ID | Priority | Requirement |
|---|---|---|
| ATT-01 | P0 | Index attachment filename, MIME type, message association, and known size. |
| ATT-02 | P1 | Search and filter attachments. |
| ATT-03 | P1 | Detect exact duplicate attachment content when downloaded locally. |
| ATT-04 | P1 | Export selected attachments to a user-chosen directory. |
| ATT-05 | P1 | Show storage contribution by sender and attachment type. |
| ATT-06 | P2 | Investigate safe attachment detachment only as a separate future project. |

---

# 5. UX and application structure

## 5.1 Main navigation

Use a desktop-first layout with these primary sections:

1. **Overview**: mailbox health, key counts, recent insights.
2. **Graph Explorer**: interactive domain/sender/thread/message graph.
3. **Messages**: searchable table with filters and previews.
4. **Senders**: sender/domain directory and activity metrics.
5. **Timeline**: volume and relationship history.
6. **Attachments**: attachment search and storage analysis.
7. **Cleanup Studio**: saved queries, previews, operations, and undo.
8. **Insights**: explainable suggestions and anomalies.
9. **Settings**: accounts, privacy, local AI, storage, backups, and protections.

## 5.2 Overview dashboard

Show:

- Total indexed messages.
- Accounts connected.
- Date coverage.
- Unread count, if available.
- Number of unique senders and domains.
- Largest senders by message count.
- Largest senders by known bytes.
- Messages by category.
- Volume over time.
- Recent scan status.
- Top three actionable insights.

Do not show fake precision. Mark estimated sizes and incomplete provider data.

## 5.3 Graph interaction details

Graph controls:

- Search node.
- Zoom in/out and fit.
- Reset layout.
- Expand/collapse.
- Toggle node types.
- Choose node size metric.
- Choose node color metric.
- Date range.
- Category filter.
- Show/hide edges by relationship type.
- Multi-select.
- Clear selection.
- Open selected results in Messages.
- Create cleanup preview from selection.

Side panel:

- Node name.
- Node type.
- Message/thread counts.
- Date range.
- Unread count.
- Size estimate.
- Category breakdown.
- Connected nodes.
- Recent messages.
- Available non-destructive actions.

The graph must never be the only place to access a feature.

## 5.4 Message table

Columns:

- Selection checkbox.
- Sender.
- Subject.
- Date.
- Category.
- Read/unread.
- Attachment indicator.
- Size, if known.
- Folder/label.

Features:

- Virtualized rows for large datasets.
- Sort and filter.
- Multi-page selection that is explicit and visible.
- Select current page vs select all matching results.
- Message preview panel.
- Open original message in provider where a stable URL is available.
- Show why a message matched the active query.

## 5.5 Cleanup preview

Before action, show:

- Operation type.
- Account/provider.
- Exact message count.
- Thread count.
- Estimated size.
- Date range.
- Included senders.
- Protected/excluded count.
- A sample of matching messages.
- Whether local backup is enabled.
- Provider-specific recoverability note.

Confirmation copy must name the action, e.g. `Move 842 messages to Trash`, not a vague `Continue`.

## 5.6 Visual direction

Aim for a polished, technical desktop application rather than a generic admin template.

- Dark theme as the initial default, with light theme support.
- High information density without visual clutter.
- Clear hierarchy and consistent spacing.
- Graph colors must remain distinguishable and accessible.
- Avoid relying on color alone to communicate categories or risk.
- Use restrained accent colors.
- Use clear empty, loading, partial, error, and disconnected states.
- No decorative metrics or meaningless charts.
- Keyboard navigation for core workflows.
- Confirm destructive actions with accessible dialogs.

---

# 6. Technical architecture

## 6.1 Recommended stack

Preferred initial implementation:

| Layer | Technology | Reason |
|---|---|---|
| Desktop shell | Tauri 2 | Small native desktop shell and OS integration |
| Frontend | React + TypeScript | Mature UI ecosystem |
| Build tooling | Vite | Fast development and bundling |
| Backend/core | Python 3.12+ initially | Strong email parsing and data tooling |
| Local API | FastAPI or Tauri sidecar IPC | Structured frontend/backend boundary |
| Database | SQLite | Embedded, portable, no server dependency |
| Full-text search | SQLite FTS5 | Local full-text indexing |
| Graph rendering | Cytoscape.js | Graph interaction and layouts |
| Charts | ECharts or a similarly capable local library | Timelines and analytics |
| Email parsing | Python standard `email` package plus tested MIME utilities | RFC822/MIME processing |
| Gmail | Official Gmail API | Provider-native OAuth and operations |
| Generic mail | IMAP with provider adapters | Broad compatibility |
| Local AI | Ollama-compatible local endpoint, optional | No hosted model requirement |
| Testing | pytest + frontend test framework + Playwright | Unit, integration, and UI tests |

The architecture may change after repository inspection. Do not introduce Rust solely for performance assumptions. Profile real workloads first.

## 6.2 Process boundaries

Separate the application into:

- Desktop/UI process.
- Application service/API.
- Provider adapters.
- Ingestion and normalization pipeline.
- Local database and search index.
- Graph aggregation service.
- Classification/insight service.
- Action execution service.
- Audit and recovery service.

Provider-specific API calls must not leak into UI components.

## 6.3 Provider adapter interface

Define a common interface with provider-specific implementations.

Conceptual methods:

```python
class MailProvider:
    def connect(self) -> None: ...
    def get_account_info(self): ...
    def list_folders(self): ...
    def scan_messages(self, folder_id, cursor=None): ...
    def fetch_message_metadata(self, message_id): ...
    def fetch_message_content(self, message_id): ...
    def get_attachment(self, message_id, attachment_id): ...
    def archive_messages(self, message_ids): ...
    def move_to_trash(self, message_ids): ...
    def restore_messages(self, message_ids): ...
    def apply_labels(self, message_ids, labels): ...
    def get_capabilities(self): ...
```

This is an interface sketch, not a requirement to force identical semantics. Each adapter must declare supported capabilities and limitations.

### Gmail-specific notes

- Use OAuth 2.0 through Google's supported flow.
- Request the least-privilege scopes possible.
- Start with read-only scopes for indexing.
- Request modify permission only when the user enables actions.
- Treat Gmail labels as labels, not ordinary folders.
- Use Gmail's Trash operation for recoverable deletion.
- Use provider message/thread IDs and history mechanisms for incremental sync where supported.
- Handle API pagination, rate limits, quota errors, expired tokens, and partial failures.
- Never log OAuth access or refresh tokens.
- Do not use a user's Google password.

### IMAP-specific notes

- Use TLS.
- Support provider-specific folder names and special-use folders.
- Use UID and UIDVALIDITY correctly.
- Do not assume message sequence numbers are stable.
- Handle server-side search carefully and allow strict local matching.
- Distinguish marking `\\Deleted`, moving to Trash, and expunging.
- Do not expunge by default.
- Make provider limitations visible.

### Local archive notes

- MBOX is an import source, not a live synchronized mailbox.
- Imported archives are read-only in the MVP.
- Preserve source filename and import timestamp.
- Detect duplicate imports.
- Support malformed and large archives without loading the entire archive into memory.

## 6.4 Ingestion pipeline

Recommended pipeline:

1. Discover source folders or archive.
2. Enumerate message identifiers.
3. Fetch metadata in batches.
4. Parse and normalize headers.
5. Resolve sender/recipient identities.
6. Resolve thread relationships.
7. Extract attachment metadata.
8. Optionally fetch and index body text.
9. Store normalized records.
10. Update FTS index.
11. Update graph aggregates.
12. Record checkpoint and progress.

Requirements:

- Streaming/batched processing.
- Bounded memory usage.
- Retry with backoff for transient failures.
- Cooperative cancellation.
- Idempotent upserts.
- Checkpoint after safe batches.
- Per-message error isolation.
- Progress events with counts and current phase.
- No mutation of source mailbox during scan.

---

# 7. Data model

Use SQLite with migrations. Use integer primary keys internally and preserve provider identifiers separately.

Suggested initial tables:

## 7.1 `accounts`

- `id`
- `provider`
- `display_name`
- `email_address`
- `provider_account_id`
- `created_at`
- `last_sync_at`
- `sync_cursor`
- `status`
- `settings_json`

Do not store raw credentials in this table.

## 7.2 `folders`

- `id`
- `account_id`
- `provider_folder_id`
- `name`
- `folder_type`
- `parent_id`
- `is_special`
- `last_scanned_at`

For Gmail, also model labels separately or through a provider-neutral labels relation.

## 7.3 `messages`

- `id`
- `account_id`
- `provider_message_id`
- `provider_thread_id`
- `folder_id`
- `message_id_header`
- `in_reply_to`
- `references_header`
- `subject`
- `sender_name`
- `sender_address`
- `sent_at`
- `received_at`
- `is_read`
- `is_starred`
- `is_important`
- `has_attachments`
- `size_bytes`
- `body_text`
- `body_indexed`
- `content_hash`
- `created_at`
- `updated_at`

Use unique constraints appropriate to `(account_id, provider_message_id)`. Provider IDs are not globally unique.

## 7.4 `message_addresses`

- `id`
- `message_id`
- `address`
- `display_name`
- `role` (`from`, `to`, `cc`, `bcc`, `reply_to`)

## 7.5 `senders`

- `id`
- `normalized_address`
- `display_name`
- `domain`
- `first_seen_at`
- `last_seen_at`
- `user_category`
- `is_protected`
- `notes`

Do not merge people based only on display name. Address normalization must be conservative.

## 7.6 `threads`

- `id`
- `account_id`
- `provider_thread_id`
- `subject_normalized`
- `first_message_at`
- `last_message_at`
- `message_count`

## 7.7 `attachments`

- `id`
- `message_id`
- `provider_attachment_id`
- `filename`
- `mime_type`
- `size_bytes`
- `content_hash`
- `local_path`
- `is_inline`
- `content_available`

Do not download attachment contents automatically.

## 7.8 `categories`

- `id`
- `name`
- `description`
- `is_system`
- `color`

## 7.9 `message_categories`

- `message_id`
- `category_id`
- `source` (`rule`, `model`, `user`)
- `confidence`
- `reason`
- `created_at`

User overrides take precedence over model/rule suggestions.

## 7.10 `protection_rules`

- `id`
- `account_id`
- `rule_type` (`sender`, `domain`, `message`, `thread`, `query`)
- `rule_value`
- `reason`
- `created_at`
- `enabled`

## 7.11 `saved_queries`

- `id`
- `name`
- `query_json`
- `created_at`
- `updated_at`

## 7.12 `operations`

- `id`
- `account_id`
- `operation_type`
- `query_snapshot_json`
- `target_count`
- `completed_count`
- `failed_count`
- `skipped_count`
- `status`
- `created_at`
- `completed_at`
- `backup_manifest_path`
- `undo_status`

## 7.13 `operation_items`

- `id`
- `operation_id`
- `message_id`
- `provider_message_id`
- `original_state_json`
- `result_state_json`
- `status`
- `error_code`
- `error_message`

## 7.14 `sync_runs`

- `id`
- `account_id`
- `started_at`
- `completed_at`
- `status`
- `scanned_count`
- `inserted_count`
- `updated_count`
- `failed_count`
- `checkpoint_json`

## 7.15 `insights`

- `id`
- `account_id`
- `insight_type`
- `title`
- `description`
- `evidence_json`
- `confidence`
- `created_at`
- `dismissed_at`

## 7.16 Search index

Use FTS5 for configurable local text search. Avoid indexing sensitive content unless the user explicitly enables body indexing.

Store a setting indicating whether message bodies are indexed. Provide a command/action to purge body text and rebuild the index.

---

# 8. Graph model and algorithms

## 8.1 Initial graph levels

Start with a sender/domain graph, not a graph containing every message.

Suggested node types:

- `domain`
- `sender`
- `thread`
- `message`
- `attachment`
- `account`

Suggested edge types:

- `belongs_to_domain`
- `sent_message`
- `participates_in_thread`
- `reply_to`
- `contains_attachment`
- `belongs_to_account`

Only create an edge when the underlying evidence exists.

## 8.2 Aggregation

For large datasets:

- Build graph summaries in SQL.
- Return only nodes/edges relevant to the selected level and viewport.
- Collapse messages into sender/thread aggregates.
- Expand a node on demand.
- Paginate message details.
- Cache graph aggregates and invalidate them after relevant sync changes.

## 8.3 Metrics

Possible node metrics:

- Message count.
- Thread count.
- Unread count.
- Total known bytes.
- First-seen and last-seen.
- Distinct counterparties.
- Attachment count.
- User-defined importance.

Do not combine unrelated metrics into one unexplained score.

## 8.4 Clustering

Potential future methods:

- Domain grouping.
- Sender-to-thread bipartite graph.
- Community detection on communication relationships.
- Time-windowed clustering.
- Similarity clusters based on sender/domain and metadata.

Clustering must be explainable and parameterized. A cluster is a navigation aid, not proof of a real-world organization or relationship.

---

# 9. Query and action engine

## 9.1 Structured query format

Represent all filters as a validated, versioned query AST.

Example:

```json
{
  "version": 1,
  "account_ids": [1],
  "all": [
    {"field": "sender_domain", "op": "eq", "value": "example.com"},
    {"field": "received_at", "op": "before", "value": "2024-01-01"},
    {"field": "is_read", "op": "eq", "value": true}
  ],
  "none": [
    {"field": "is_starred", "op": "eq", "value": true}
  ]
}
```

The actual schema must be validated and versioned. Never execute arbitrary SQL generated by the frontend or an LLM.

## 9.2 Query execution

- Validate query fields and operators.
- Resolve account scope.
- Apply protection exclusions.
- Return deterministic target IDs.
- Calculate counts and estimates.
- Use the same query compiler for preview and execution.
- Revalidate targets immediately before mutation to avoid stale state.
- Detect messages that changed since preview.

## 9.3 Operation lifecycle

States:

- `draft`
- `previewed`
- `awaiting_confirmation`
- `running`
- `completed`
- `completed_with_errors`
- `cancelled`
- `failed`
- `undo_available`
- `undone`
- `undo_partial`
- `undo_expired`

## 9.4 Undo semantics

Undo is provider-dependent. Store enough state to attempt a safe inverse action, but do not promise an undo if the provider cannot guarantee it.

Examples:

- Archive: restore original labels/folder state if still available.
- Move to Trash: restore from Trash if the message still exists and the provider supports it.
- Label change: restore previous label set.
- Unsubscribe: generally not reliably reversible; do not show an undo button.

Show per-item undo results and explain failures.

---

# 10. Privacy and security

This section is a release blocker, not optional polish.

## 10.1 Data handling

- All mailbox data stays local by default.
- No telemetry or analytics in the initial release.
- No remote AI by default.
- No third-party tracking.
- No remote frontend assets at runtime.
- No content in application logs.
- No subjects, addresses, snippets, or message bodies in crash reports.
- Clear local data deletion controls.
- Configurable body indexing and retention.
- Explain exactly what is stored locally.

## 10.2 Credentials

- Use OS credential storage/keychain where available.
- Never store tokens in source code, logs, plain config files, or SQLite.
- Redact authorization headers and secrets from exceptions.
- Support revocation/disconnect.
- Use least-privilege OAuth scopes.
- Refresh tokens securely.
- Keep local development secrets outside the repository.

## 10.3 Local AI

- Disabled until explicitly configured.
- Prefer loopback-only model endpoints.
- Verify endpoint configuration and display it to the user.
- Never silently fall back to a hosted provider.
- Show what fields are sent to the local model.
- Do not include attachment content by default.
- Treat email content as untrusted input and potential prompt injection.
- Never allow email text to invoke tools or actions.
- Model output must pass schema validation.
- The model may propose a query but cannot authorize or execute a mutation.

## 10.4 Email content is untrusted

Treat subjects, bodies, attachments, HTML, headers, and embedded instructions as untrusted data.

- Do not execute HTML, scripts, links, macros, or attachments.
- Sanitize rendered HTML previews.
- Disable remote images by default.
- Do not follow links automatically.
- Prevent prompt injection from changing system behavior.
- Keep message content separate from trusted application instructions.
- Never allow an email to cause deletion, data export, or network access.

## 10.5 Local database

- Restrict database file permissions where possible.
- Offer optional database encryption if the implementation can support it reliably.
- Explain that encryption at rest depends on platform and configuration.
- Provide a secure local-data wipe flow.
- Avoid copying raw message bodies into temporary files unnecessarily.

## 10.6 Threat model

Consider:

- Stolen or exposed OAuth token.
- Malicious email content attempting prompt injection.
- Malformed MIME parser input.
- Malicious attachment filenames/path traversal.
- SQL injection through search filters.
- Accidental mailbox-wide deletion.
- Provider rate limits and partial action failures.
- Local device compromise.
- Database or backup accidentally committed to Git.
- A compromised or misconfigured local model endpoint.

---

# 11. Performance and reliability targets

Targets are engineering goals, not claims to make before benchmarking.

- Import should be streaming and bounded-memory.
- A 100,000-message synthetic mailbox should be usable on a typical modern laptop.
- Initial overview queries should feel responsive after indexing.
- Graph should aggregate by default and avoid creating 100,000 DOM elements.
- Search should use indexes rather than repeatedly scanning full message bodies.
- Cancellation should stop new work promptly and leave the database consistent.
- Interrupted scans should resume from checkpoints.
- Duplicate imports should not create duplicate records.
- A provider failure should not corrupt already imported data.
- Every long-running task should expose progress and a cancellation control.

Benchmark at 10k, 100k, and 500k synthetic messages. Record hardware, dataset shape, memory, import time, query latency, and graph rendering time. Do not optimize prematurely.

---

# 12. Testing strategy

## 12.1 Unit tests

- Header normalization.
- Address parsing.
- Date parsing and timezone handling.
- MIME parsing.
- Attachment metadata extraction.
- Thread/reference resolution.
- Query AST validation.
- Query compilation.
- Protection rules.
- Classification precedence.
- Graph aggregation.
- Duplicate detection.
- Operation state transitions.

## 12.2 Integration tests

Use fake provider adapters and synthetic mailbox fixtures.

Test:

- Initial scan.
- Interrupted scan and resume.
- Incremental sync.
- Duplicate import.
- Provider pagination.
- Rate-limit retry.
- Partial fetch failures.
- Archive operation.
- Trash operation.
- Undo success and partial failure.
- Stale preview detection.
- Protected sender exclusion.
- Cancellation during action execution.

Never use a real mailbox in automated tests.

## 12.3 Security tests

- Malformed MIME.
- HTML/script sanitization.
- Path traversal filenames.
- SQL injection-like query values.
- Prompt injection in subject/body.
- Token redaction in logs.
- Ensure no network call occurs during offline import.
- Ensure model output cannot invoke a mutation.
- Ensure protected targets are excluded from final execution.

## 12.4 UI tests

- First-run onboarding.
- Connect/import screens.
- Scan progress and cancellation.
- Graph selection and table synchronization.
- Saved filters.
- Cleanup preview.
- Explicit confirmation.
- Operation progress.
- Undo and partial undo.
- Disconnect and local-data deletion.

---

# 13. Implementation roadmap

Do not implement every feature simultaneously.

## Phase 0: Repository and design foundation

Deliverables:

- Repository audit.
- Architecture decision record.
- Application shell.
- Theme and navigation.
- SQLite migrations.
- Synthetic dataset generator.
- Basic test harness.
- Privacy and security baseline.

Acceptance criteria:

- App starts locally.
- No remote assets or telemetry.
- Database is created in an OS-appropriate application-data directory.
- Synthetic data can be loaded and cleared.
- No real credentials are required.

## Phase 1: Read-only mailbox ingestion

Deliverables:

- MBOX importer.
- Gmail read-only OAuth adapter.
- Normalized account/folder/message/sender/thread/attachment records.
- Incremental/resumable scan framework.
- Scan status UI.
- Error reporting.

Acceptance criteria:

- Import a synthetic MBOX archive.
- Connect Gmail with read-only permission.
- Index messages without modifying the source.
- Resume an interrupted scan.
- Re-import without duplicate records.
- Disconnect an account.

## Phase 2: Search and mailbox overview

Deliverables:

- Overview dashboard.
- Message table.
- Sender/domain directory.
- Filters and saved queries.
- SQLite FTS5.
- CSV export.

Acceptance criteria:

- Search and filter indexed messages.
- Show exact result counts.
- Inspect message metadata.
- Search can be restricted to selected accounts/folders.
- Large result sets are paginated or virtualized.

## Phase 3: Graph explorer

Deliverables:

- Domain/sender graph.
- Node details panel.
- Expand/collapse behavior.
- Graph-to-table selection synchronization.
- Date/category filters.
- Graph aggregation and performance tests.

Acceptance criteria:

- Selecting a domain displays its senders.
- Selecting a sender filters the message table.
- User can inspect the exact messages represented by a node.
- Graph does not render every message at once.
- Graph selection never triggers a mutation.

## Phase 4: Safe cleanup engine

Deliverables:

- Protection rules.
- Preview engine.
- Archive and Trash actions for supported providers.
- Confirmation UI.
- Operation log.
- Backup manifest.
- Undo where supported.

Acceptance criteria:

- Preview and execution use the same validated query.
- Protected messages are excluded.
- Exact targets are shown before confirmation.
- No operation occurs without explicit confirmation.
- Partial failures are reported.
- Undo behavior is provider-aware and tested.
- No permanent deletion by default.

## Phase 5: Intelligence and insights

Deliverables:

- Deterministic categories.
- Explainable sender metrics.
- Subscription discovery.
- Timeline.
- "What am I missing?" insights.
- User overrides.

Acceptance criteria:

- Every category has an explanation or rule provenance.
- User override wins over automated classification.
- Insights link to exact supporting messages.
- Unavailable metrics are shown as unavailable, not fabricated.

## Phase 6: Optional local AI

Deliverables:

- Local model configuration.
- Natural-language-to-query translation.
- Classification suggestions.
- Insight explanations.
- Prompt-injection defenses.

Acceptance criteria:

- AI is disabled by default.
- No hosted fallback exists.
- Proposed filters are visible and editable.
- Model cannot execute actions.
- Invalid model output is rejected safely.
- Email content is treated as untrusted input.

## Phase 7: Hardening and release

Deliverables:

- Windows packaging.
- macOS/Linux packaging where feasible.
- Backup/restore documentation.
- Security review.
- Performance benchmarks.
- User guide.
- Synthetic demo dataset.
- Release checklist.

Acceptance criteria:

- Clean installation on a fresh machine.
- No secrets or mailbox data in build artifacts.
- Core flows work offline after local import.
- All destructive operations are covered by tests.
- Known provider limitations are documented.

---

# 14. Suggested repository structure

Adapt to the existing repository if it already has a sound structure.

```text
mailgraph/
├── apps/
│   └── desktop/
│       ├── src/
│       │   ├── app/
│       │   ├── components/
│       │   ├── features/
│       │   │   ├── overview/
│       │   │   ├── graph/
│       │   │   ├── messages/
│       │   │   ├── senders/
│       │   │   ├── timeline/
│       │   │   ├── attachments/
│       │   │   ├── cleanup/
│       │   │   └── settings/
│       │   ├── hooks/
│       │   ├── lib/
│       │   └── types/
│       └── src-tauri/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── providers/
│   │   ├── ingestion/
│   │   ├── search/
│   │   ├── graph/
│   │   ├── classification/
│   │   ├── actions/
│   │   ├── audit/
│   │   └── security/
│   └── tests/
├── fixtures/
│   └── synthetic/
├── docs/
│   ├── architecture.md
│   ├── security.md
│   ├── provider-support.md
│   └── decisions/
├── scripts/
├── .gitignore
├── README.md
└── agent-spec.md
```

Do not create empty directories for every future feature. Add modules when the corresponding phase begins.

---

# 15. Configuration and local storage

Use OS-appropriate application data/config directories.

Example configuration (illustrative):

```toml
[app]
theme = "dark"
telemetry = false

[privacy]
index_message_bodies = false
download_attachments_automatically = false
local_ai_enabled = false

[graph]
default_level = "domain"
max_visible_nodes = 1500

[cleanup]
default_delete_mode = "trash"
require_preview = true
require_confirmation = true
backup_before_mutation = true
```

The actual configuration format may be JSON or TOML. Secrets must not be stored here.

Provide a privacy panel that answers:

- What data is stored?
- Where is it stored?
- Are message bodies indexed?
- Are attachments downloaded?
- Is a local model enabled?
- Does the app make any network requests?
- Which accounts are connected?
- How do I delete all local data?

---

# 16. Error handling and observability

Use structured local logs with sensitive fields redacted.

Log:

- Scan started/completed.
- Counts and durations.
- Provider error codes.
- Retry attempts.
- Operation IDs and status transitions.
- Database migration failures.

Do not log:

- Message bodies.
- Full subjects by default.
- Full recipient lists.
- OAuth tokens.
- Passwords.
- Attachment contents.

User-facing errors should explain:

- What failed.
- Whether any messages were changed.
- Whether retry is safe.
- Whether the operation partially completed.
- Where to inspect the audit record.

---

# 17. Definition of done for the MVP

The MVP is complete only when all of the following work:

- [ ] App runs locally on Windows.
- [ ] User can import MBOX.
- [ ] User can connect Gmail read-only.
- [ ] Initial scan is resumable and read-only.
- [ ] Messages, senders, threads, and attachment metadata are indexed.
- [ ] User can search and filter the mailbox.
- [ ] User can explore domain/sender/thread relationships visually.
- [ ] Graph selection synchronizes with message results.
- [ ] User can protect senders/domains/messages.
- [ ] User can preview a bulk archive or Trash operation.
- [ ] Preview and execution target the same query results, subject to stale-state revalidation.
- [ ] Every mutation requires explicit confirmation.
- [ ] Operations are logged.
- [ ] Undo is implemented where supported, with limitations disclosed.
- [ ] No AI can autonomously mutate mailbox state.
- [ ] No mailbox data, tokens, or credentials are sent to a hosted service.
- [ ] Synthetic test data is used in automated tests.
- [ ] No real mailbox data or secrets are committed to Git.
- [ ] README explains installation, permissions, privacy, limitations, and backup behavior.

---

# 18. Product decisions to keep explicit

The following decisions should not be silently changed by an implementation agent:

1. **Desktop app vs browser-only local app:** Desktop is the target; a localhost web UI may be used during development.
2. **Initial provider priority:** Gmail and MBOX first; generic IMAP next.
3. **Initial graph level:** Domain and sender, with thread/message drill-down.
4. **Initial deletion behavior:** Move to Trash/Deleted Items, never permanent delete by default.
5. **Initial AI behavior:** Disabled by default; local-only when enabled.
6. **Body indexing:** Off by default or explicitly opted into during setup.
7. **Telemetry:** None in the initial release.
8. **Attachment handling:** Metadata first; no automatic download or detachment.
9. **User confirmation:** Required for every bulk mutation.
10. **Public release:** The owner may keep the repository private. Do not publish, package, upload, or deploy anything without explicit instruction.

---

# 19. First task for the coding agent

Do not immediately implement the entire application.

Start by:

1. Inspecting the repository.
2. Reporting its current state and any existing implementation.
3. Comparing it against this specification.
4. Proposing a minimal architecture and concrete Phase 0/Phase 1 task breakdown.
5. Identifying provider/API risks, especially Gmail OAuth scope requirements.
6. Listing any assumptions that need the owner's decision.
7. Implementing Phase 0 only after the audit and plan are clear.

The first milestone is a working local application shell with a synthetic mailbox dataset, not a half-built email client.

**Guiding rule:** Build a trustworthy mailbox intelligence system first. Add intelligence only where it improves understanding, and add automation only where the user retains control.
