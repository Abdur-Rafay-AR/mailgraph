"""Developer launcher: runs Python FastAPI backend and Vite frontend simultaneously."""

import sys
import os
import subprocess
import time
import signal

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print("=" * 60)
    print("Starting MailGraph Development Environment...")
    print(f"Working Directory: {root_dir}")
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
        "28491",
        "--reload"
    ]
    print("-> Launching Python Backend on http://127.0.0.1:28491...")
    backend_proc = subprocess.Popen(backend_cmd, cwd=root_dir)

    # Allow backend to bind
    time.sleep(1.5)

    # 2. Start Vite Frontend
    frontend_dir = os.path.join(root_dir, "apps", "desktop")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    frontend_cmd = [npm_cmd, "run", "dev"]
    print("-> Launching Desktop UI on http://localhost:5173...")
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=frontend_dir)

    print("\nMailGraph is running! Press Ctrl+C in this terminal to stop both servers.\n")

    def shutdown(sig, frame):
        print("\nShutting down servers...")
        try:
            frontend_proc.terminate()
            backend_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        shutdown(None, None)

if __name__ == "__main__":
    main()
