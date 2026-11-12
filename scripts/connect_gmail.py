"""Direct Gmail Account Linker CLI for MailGraph.

Allows users to directly connect their real Gmail account using either:
1. Gmail App Password (Recommended & fastest: takes 10 seconds, zero developer console setup, 100% local IMAP).
2. Google Cloud OAuth 2.0 (Official desktop OAuth flow with loopback consent).
"""

import sys
import os
import getpass
import json
import imaplib
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

# Add repo root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.app.db.database import get_database
from backend.app.security.credential_store import CredentialStore
from backend.app.providers.imap import ImapProvider
from backend.app.providers.gmail import GmailProvider, READONLY_SCOPE
from backend.app.ingestion.pipeline import IngestionPipeline

def print_banner():
    print("=" * 65)
    print("        MailGraph — Direct Gmail Account Linker")
    print("=" * 65)
    print("All email data and credentials remain strictly on your local machine.")
    print("=" * 65)

def connect_via_app_password():
    print("\n--- Method 1: Gmail App Password (Recommended) ---")
    print("How to get a Gmail App Password in 30 seconds:")
    print("  1. Go to: https://myaccount.google.com/apppasswords")
    print("  2. If prompted, sign in to your Google Account.")
    print("  3. Under 'App name', enter 'MailGraph' and click 'Create'.")
    print("  4. Google will give you a 16-character password (e.g. 'abcd efgh ijkl mnop').\n")

    email_addr = input("Enter your Gmail address (e.g. user@gmail.com): ").strip()
    if not email_addr or "@" not in email_addr:
        print("Invalid email address.")
        return

    password = getpass.getpass("Enter your 16-character Gmail App Password: ").strip()
    # Remove any spaces that Google displays
    password = password.replace(" ", "")

    if not password:
        print("Password cannot be empty.")
        return

    print("\n-> Testing secure SSL connection to imap.gmail.com:993...")
    try:
        client = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        typ, data = client.login(email_addr, password)
        if typ != "OK":
            print(f"Authentication failed: {data}")
            return
        client.logout()
        print("✓ Successfully authenticated with Gmail IMAP!")
    except Exception as ex:
        print(f"\n[Error] Could not connect to Gmail: {ex}")
        print("Ensure you generated an 'App Password' at https://myaccount.google.com/apppasswords")
        return

    # Store credentials securely in local OS Keyring
    cred_store = CredentialStore()
    cred_json = json.dumps({
        "provider": "imap",
        "host": "imap.gmail.com",
        "port": 993,
        "username": email_addr,
        "password": password
    })
    cred_store.save_credentials(email_addr, cred_json)
    print("✓ Securely saved credentials in local OS Credential Locker.")

    # Register in MailGraph SQLite Database
    db = get_database()
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM accounts WHERE email_address = ?;", (email_addr,))
        row = cursor.fetchone()
        if row:
            account_id = row[0]
            cursor.execute("UPDATE accounts SET status = 'active', last_sync_at = datetime('now') WHERE id = ?;", (account_id,))
            print(f"✓ Updated existing account #{account_id} in local database.")
        else:
            cursor.execute("""
                INSERT INTO accounts (provider, display_name, email_address, settings_json)
                VALUES ('imap', ?, ?, ?);
            """, (f"Gmail ({email_addr})", email_addr, json.dumps({"host": "imap.gmail.com", "port": 993, "ssl": True})))
            account_id = cursor.lastrowid
            print(f"✓ Created new account #{account_id} in local database.")

    # Offer to run initial scan
    print("\n" + "-" * 50)
    start_scan = input("Would you like to import recent emails into MailGraph now? (y/n) [y]: ").strip().lower()
    if start_scan in ("", "y", "yes"):
        limit_str = input("How many recent messages to index? (e.g. 50, 200, 1000) [100]: ").strip()
        limit = int(limit_str) if limit_str.isdigit() else 100

        print(f"\n-> Streaming {limit} recent messages from Gmail INBOX (read-only)...")
        provider = ImapProvider("imap.gmail.com", email_addr, password, port=993, use_ssl=True)
        pipeline = IngestionPipeline(db)

        def progress(res):
            print(f"   Indexed: {res.inserted_count} msgs | Skipped: {res.skipped_count} | Errors: {res.failed_count}", end="\r")

        result = pipeline.ingest_messages(account_id, provider.stream_messages(folder_id="INBOX", limit=limit), progress_callback=progress)
        print(f"\n✓ Scan complete! Inserted {result.inserted_count} new messages into your local database.")
        print("Launch the desktop app with 'python scripts/run_desktop.py' to explore your graph and senders!")

def connect_via_oauth():
    print("\n--- Method 2: Google Cloud OAuth 2.0 ---")
    print("Requires a Google Cloud project with the Gmail API enabled.")
    print("If you don't have one, Method 1 (App Password) is recommended.\n")

    creds_path = input("Enter path to your OAuth 'credentials.json' (or press Enter to enter Client ID manually): ").strip()
    client_id = ""
    client_secret = ""

    if creds_path and os.path.exists(creds_path):
        with open(creds_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            info = data.get("installed") or data.get("web") or {}
            client_id = info.get("client_id", "")
            client_secret = info.get("client_secret", "")

    if not client_id:
        client_id = input("Enter your OAuth Client ID: ").strip()
        client_secret = input("Enter your OAuth Client Secret: ").strip()

    if not client_id or not client_secret:
        print("Client ID and Client Secret are required for OAuth.")
        return

    email_addr = input("Enter your Gmail address: ").strip()

    # Local loopback server to capture authorization code
    auth_code_container = {}

    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if "code" in query:
                auth_code_container["code"] = query["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>MailGraph Authentication Successful!</h1><p>You can close this browser window and return to your terminal.</p>")
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, format, *args):
            return  # Silence server logs

    server = HTTPServer(("127.0.0.1", 8080), OAuthCallbackHandler)
    redirect_uri = "http://127.0.0.1:8080"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": READONLY_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": email_addr
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{requests.compat.urlencode(params)}"

    print("\n-> Opening browser for Google OAuth consent...")
    webbrowser.open(auth_url)
    print("Waiting for authorization callback on http://127.0.0.1:8080...")

    server.handle_request()

    code = auth_code_container.get("code")
    if not code:
        print("Failed to capture authorization code.")
        return

    print("-> Exchanging authorization code for tokens...")
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    resp = requests.post(token_url, data=token_data)
    if resp.status_code != 200:
        print(f"Token exchange failed: {resp.text}")
        return

    tokens = resp.json()
    cred_store = CredentialStore()
    cred_store.save_credentials(email_addr, json.dumps(tokens))
    print("✓ Securely saved OAuth tokens in OS Keyring.")

    # Register in SQLite
    db = get_database()
    with db.connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM accounts WHERE email_address = ?;", (email_addr,))
        row = cursor.fetchone()
        if row:
            account_id = row[0]
            cursor.execute("UPDATE accounts SET status = 'active', last_sync_at = datetime('now') WHERE id = ?;", (account_id,))
        else:
            cursor.execute("""
                INSERT INTO accounts (provider, display_name, email_address, settings_json)
                VALUES ('gmail', ?, ?, ?);
            """, (f"Gmail ({email_addr})", email_addr, json.dumps({"client_id": client_id})))
            account_id = cursor.lastrowid

    print(f"✓ Linked Gmail account #{account_id} successfully!")

def main():
    print_banner()
    print("Select how you want to link your Gmail account:")
    print("  [1] Gmail App Password (Fastest — 10 seconds, zero Google Cloud setup, 100% local)")
    print("  [2] Google Cloud OAuth 2.0 (Developer Console setup)")
    print("  [3] Exit\n")

    choice = input("Enter choice (1, 2, or 3) [1]: ").strip()
    if choice in ("", "1"):
        connect_via_app_password()
    elif choice == "2":
        connect_via_oauth()
    else:
        print("Exiting.")

if __name__ == "__main__":
    main()
