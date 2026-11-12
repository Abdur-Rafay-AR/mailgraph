# MailGraph — Technical Architecture

## 1. Overview

MailGraph is a local-first desktop application designed to explore, understand, and safely clean up large email mailboxes. It models a mailbox into a multi-resolution interactive relationship graph and provides deterministic search, sender volume intelligence, and safe bulk actions with exact simulations and audit undo tracking.

## 2. Core Architectural Principles

- **Strictly Local-First:** All email messages, headers, attachments, contacts, graph layouts, and search indexes are stored on the user's machine in an embedded SQLite database (`%APPDATA%/Mailgraph/mailgraph.db`).
- **No Cloud Dependencies:** Zero telemetry, zero analytics scripts, zero external fonts or CDNs.
- **AI Is Strictly Optional:** All searches, filters, category heuristics, and sender analytics are 100% deterministic. If a local model (Ollama) is detected on loopback, it is restricted to proposing structured query ASTs for user inspection; it can never modify email state independently.
- **Destructive Safety Guarantee:** The query compiler used during preview simulation is identical to the compiler used during execution. Every mutation requires explicit confirmation naming the target count and safe action (`Move to Trash` or `Archive`). Protected senders and starred messages are excluded by default.

---

## 3. System Components

```
+-----------------------------------------------------------------+
|                        Electron Desktop Shell                   |
|                                                                 |
|  React 18 + TypeScript + Vite + Tailwind CSS + Cytoscape.js     |
|                                                                 |
|  - Overview Dashboard         - Dedicated Sender Management     |
|  - Interactive Graph          - Message Explorer & FTS5         |
|  - Safe Cleanup Studio        - Email Time Machine              |
|  - Duplicate Attachments      - Explainable Insights            |
+-----------------------------------------------------------------+
                                |
               HTTP REST & SSE (127.0.0.1:28491)
                                |
+-----------------------------------------------------------------+
|                       Python 3.11+ Backend                      |
|                                                                 |
|  - FastAPI Local Server      - Streaming MIME / RFC822 Parser   |
|  - Ingestion Pipeline        - Deterministic Category Rules     |
|  - Query AST Compiler        - Graph Aggregation Service        |
|  - Action Engine (Undo Log)  - Insight Telemetry Engine         |
|  - Keyring Credential Store  - Optional Loopback Ollama AI      |
+-----------------------------------------------------------------+
                                |
+-----------------------------------------------------------------+
|                       Local Storage Layer                       |
|                                                                 |
|  SQLite Database (WAL Mode + FTS5 Full-Text Search)             |
|  Tables: accounts, folders, senders, threads, messages,        |
|          message_addresses, attachments, categories,            |
|          message_categories, protection_rules, operations,      |
|          operation_items, sync_runs, insights, messages_fts     |
+-----------------------------------------------------------------+
```

---

## 4. Ingestion & Normalization Pipeline

1. **Provider Discovery:** Connects to an MBOX file, IMAP mailbox, or Synthetic generator.
2. **Streaming Read:** Uses Python's standard `email.policy.default` with memory-safe chunking to prevent memory bloat on 100,000+ message mailboxes.
3. **MIME Sanitization:** Attachment filenames are sanitized to prevent directory traversal (`..`, slashes, null bytes).
4. **Deduplication:** Prevents duplicate rows using `(account_id, provider_message_id)` and SHA-256 message content hashes.
5. **Entity Linking:** Automatically links senders, normalizes email domains, creates or joins threads using `In-Reply-To` / `References` headers, and populates `messages_fts` virtual table.

---

## 5. Multi-Resolution Graph Model

Cytoscape.js renders the network topology using a hierarchical aggregation model:
- **Level 1 (Domain Clusters):** Aggregates senders into domain clusters (e.g. `github.com`, `stripe.com`, `acme.corp`) connected to the central mailbox hub. Node sizes encode volume or storage bytes.
- **Level 2 (Sender Network):** Double-clicking or selecting a domain expands its individual senders, showing their respective message counts, unread ratios, and dominant categories.
- **Level 3 (Conversation Threads):** Explores active multi-party reply chains.

---

## 6. Safe Cleanup Simulation & Undo Engine

Every bulk action follows a 4-step lifecycle:
1. **Query AST Formulation:** Validates conditions (`sender_address`, `domain`, `category`, `received_at`, `is_read`, `exclude_protected`).
2. **Simulation Preview:** Compiles the parameterized SQL to return exact target count, affected threads, total bytes, protected exclusions, and 10 representative message samples.
3. **Explicit Confirmation:** Displays a clear action button (e.g., `Move 842 messages to Trash`).
4. **Audit Snapshot & Undo:** Records the operation in `operations` and snapshots original states in `operation_items`. If the user clicks `Undo Operation`, MailGraph restores every message back to its original folder state.
