"""Desktop launcher: starts the local backend and launches the Electron desktop application window."""

import sys
import os
import subprocess
import time
import signal

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    frontend_dir = os.path.join(root_dir, "apps", "desktop")

    print("=" * 60)
    print("Launching MailGraph Desktop Application...")
    print("=" * 60)

    # 1. Start Python Backend
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "28491"
    ]
    print("-> Launching local backend service on 127.0.0.1:28491...")
    backend_proc = subprocess.Popen(backend_cmd, cwd=root_dir)

    time.sleep(1.5)

    # 2. Check if dist exists, otherwise build it or run dev
    dist_index = os.path.join(frontend_dir, "dist", "index.html")
    npm_cmd = "npx.cmd" if sys.platform == "win32" else "npx"

    if not os.path.exists(dist_index):
        print("-> Building production desktop bundle...")
        build_npm = "npm.cmd" if sys.platform == "win32" else "npm"
        subprocess.run([build_npm, "run", "build"], cwd=frontend_dir, check=True)

    # 3. Launch Electron window
    print("-> Opening native desktop window...")
    electron_cmd = [npm_cmd, "electron", "."]
    electron_proc = subprocess.Popen(electron_cmd, cwd=frontend_dir)

    def shutdown(sig, frame):
        print("\nExiting desktop application...")
        try:
            electron_proc.terminate()
            backend_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        electron_proc.wait()
    finally:
        shutdown(None, None)

if __name__ == "__main__":
    main()
