# MailGraph

> **Local-First Email Intelligence & Safe Cleanup Desktop Application**

MailGraph is a desktop application that turns large, cluttered email mailboxes into an explorable, searchable, and actionable model. It maps email relationships across organizations, senders, and conversation threads, and provides safe, reversible cleanup tools with pre-action simulations, protection safeguards, and local audit logging.

---

## Key Features

- **Local-First Architecture:** All messages, metadata, graph topologies, and search indexes are stored locally in SQLite (`%APPDATA%/Mailgraph/mailgraph.db`). Absolutely zero telemetry, cloud sync, or external tracking.
- **Dedicated Sender Management:**
  - Rank senders by volume, storage footprint, unread count, and activity.
  - Search senders by name, email, or domain.
  - Multi-select senders with one click.
  - Mark senders as **Protected** so their emails are strictly shielded from bulk operations.
  - One-click bulk cleanup simulation and execution.
- **Interactive Relationship Graph (Cytoscape.js):**
  - Multi-resolution navigation: Domain Clusters &rarr; Senders &rarr; Conversation Threads.
  - Node sizes scaled by message count or storage bytes; colors mapped to categories.
  - Interactive selection and drill-down synchronized with the Message Explorer.
- **Message Explorer & Full-Text Search (SQLite FTS5):**
  - High performance search over subjects and messages.
  - Dynamic filters for categories, read/unread status, starred messages, attachments, and protected exclusions.
  - Sanitized email content viewer with remote image blocking.
  - CSV search export.
- **Safe Cleanup Studio:**
  - Formulate cleanup rules by category, age cutoff, and read state.
  - **Simulation Preview:** Shows exact target count, storage space recovered, protected messages excluded, and representative message samples before confirmation.
  - **Explicit Confirmation:** Buttons clearly state the exact action (e.g. `Move 842 messages to Trash`).
  - **Audit Trail & Undo:** Every operation is logged; one click restores original folder states.
- **Email Time Machine:**
  - Histograms showing message influx over time (grouped by Month, Year, or Day).
  - Sender activity lifecycles (first seen, peak activity, and most recent communication).
- **Attachment Intelligence & Duplicate Detection:**
  - Cryptographic content-hash (SHA-256) grouping of identical files attached across multiple emails.
  - Identifies redundant storage footprint.
- **Explainable Insights ("What am I missing?"):**
  - Identifies inactive subscriptions, storage dominators, large attachment clusters, and unreplied conversation threads with inspectable evidence.
- **Optional Local AI (Ollama):**
  - 100% optional. If Ollama is running on loopback (`http://127.0.0.1:11434`), MailGraph can translate natural language requests into structured queries.
  - Models are strictly prohibited from independently mutating or deleting emails.

---

## Technical Stack

- **Desktop Shell:** Electron (Node 24)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Cytoscape.js, Lucide Icons
- **Backend Service:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2
- **Database:** SQLite (WAL mode, Foreign Keys, FTS5 unicode61 tokenizer)
- **Security & Privacy:** Python standard library `email.policy.default`, Bleach HTML sanitizer, OS Credential Store (`keyring`)
- **Supported Ingestion Sources:**
  - Synthetic Mailbox Generator (instant evaluation & demo)
  - Offline `.mbox` archive files (Google Takeout, Thunderbird, Apple Mail)
  - Generic IMAP (TLS, UID-based, non-destructive read)
  - Gmail API (OAuth 2.0 loopback consent)

---

## Getting Started

### Prerequisites

- **Python 3.11+** installed
- **Node.js 18+** and `npm` installed

### 1. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Desktop Frontend Dependencies

```bash
cd apps/desktop
npm install
cd ../..
```

---

## Running MailGraph

### Launch Development Environment (Backend + Hot-Reload UI)

Run the single dev launcher script from the repository root:

```bash
python scripts/run_dev.py
```

This starts:
- Local Python API on `http://127.0.0.1:28491`
- Vite Desktop UI on `http://localhost:5173`

### Launch Desktop Window (Electron Desktop App)

To run the native Electron desktop application window:

```bash
python scripts/run_desktop.py
```

---

## Instant Demo Data

When launching MailGraph for the first time, click **"Load Demo Data"** in the top bar or navigate to **Settings &rarr; Add Mailbox Source &rarr; Synthetic Demo Box** and click **Start Ingestion**.

MailGraph will immediately generate realistic multi-domain emails with thread replies, attachments, receipts, and newsletters so you can explore the relationship graph, sender management, and cleanup simulation immediately!

---

## Automated Test Suite

Run the complete backend test suite:

```bash
python -m pytest backend/tests/
```

To build and verify the desktop frontend:

```bash
cd apps/desktop
npm run build
```

---

## Keyboard Shortcuts

- `Alt + 1`: Mailbox Overview
- `Alt + 2`: Graph Explorer
- `Alt + 3`: Message Explorer & FTS Search
- `Alt + 4`: Dedicated Sender Management
- `Alt + 5`: Cleanup Studio & Audit Log
- `Alt + 6`: Email Time Machine
- `Alt + 7`: Attachment Intelligence
- `Alt + 8`: Insights & Recommendations
- `Alt + 9`: Settings & Protection Rules
- `Escape`: Close modals and inspection drawers

---

## Connecting Your Real Mailbox

MailGraph provides two fast ways to index your real mailbox:

### Option 1: Direct In-App Link (Recommended for Gmail & IMAP)
1. In the MailGraph desktop app, navigate to **Settings (Alt + 9) &rarr; Add Mailbox Source**.
2. Select **Gmail (Direct Link)** or **Standard IMAP**.
3. For Gmail:
   - Ensure 2-Step Verification is active on your Google Account.
   - Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
   - Create a new App Password named `MailGraph`.
   - Paste your Gmail address and the 16-character App Password into MailGraph.
4. Click **Connect & Ingest**. Credentials are saved securely into your native OS Keyring (never in plain text), and your emails are indexed directly into local SQLite.

### Option 2: CLI Linker Script (`scripts/connect_gmail.py`)
Run the interactive terminal linking wizard:
```bash
python scripts/connect_gmail.py
```
This utility:
- Prompts for your Google email and App Password (or OAuth `credentials.json` if preferred).
- Securely tests the SSL connection.
- Stores credentials into your OS Keyring.
- Streams and indexes your initial batch of messages directly into `mailgraph.db`.
- When you launch the UI, your inbox is already indexed and ready to explore!

---

## Documentation

- [Product Specification (`agent-spec.md`)](agent-spec.md)
- [Technical Architecture (`docs/architecture.md`)](docs/architecture.md)
- [Provider Support Guide (`docs/provider-support.md`)](docs/provider-support.md)
- [Implementation Plan (`docs/superpowers/plans/2026-11-12-mailgraph-implementation.md`)](docs/superpowers/plans/2026-11-12-mailgraph-implementation.md)

---

## License

MIT License. Designed with privacy, reversibility, and local-first architecture.
