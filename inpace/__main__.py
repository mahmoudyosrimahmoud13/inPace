"""Start inPace: runs on this computer only and opens your browser.

    inpace                      start normally
    inpace --home FOLDER        use a different data folder (e.g. to try being a checker too)
    inpace --port 8800          pick the port
    inpace --no-browser         don't open the browser
"""
from __future__ import annotations

import argparse
import socket
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .app import create_app
from .vault import Vault, default_home


def free_port(preferred: int) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 50)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    ap = argparse.ArgumentParser(prog="inpace", description="inPace: learn at your pace, prove you kept it.")
    ap.add_argument("--home", type=Path, default=None, help=f"data folder (default: {default_home()})")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    vault = Vault(args.home)
    port = free_port(args.port)
    url = f"http://127.0.0.1:{port}/"
    print(f"\n  inPace is running at {url}")
    print(f"  Your data folder: {vault.home}")
    print("  Keep this window open while you use inPace. Close it (or press Ctrl+C) to stop.\n")
    if not args.no_browser:
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
    # 127.0.0.1 means only this computer can reach it.
    uvicorn.run(create_app(vault), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
