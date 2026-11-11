"""Start inPace. It runs only on this computer.

    inpace                      open inPace in its own window (or your browser)
    inpace --home FOLDER        use a different data folder (e.g. to try being a checker too)
    inpace --browser            use your browser instead of the app window
    inpace --port 8800          pick the port
    inpace --no-browser         just run, don't open anything
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
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


def _quiet_streams(home: Path) -> None:
    """Installed apps have no terminal; send output to a log file instead."""
    if sys.stdout is None or sys.stderr is None:
        log = open(home / "inpace.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def _wait_until_up(port: int, timeout: float = 15) -> None:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)


def main() -> None:
    ap = argparse.ArgumentParser(prog="inpace", description="inPace: learn at your pace, prove you kept it.")
    ap.add_argument("--home", type=Path, default=None, help=f"data folder (default: {default_home()})")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--browser", action="store_true", help="use your browser instead of the app window")
    ap.add_argument("--no-browser", action="store_true", help="don't open a window or browser")
    args = ap.parse_args()

    vault = Vault(args.home)
    _quiet_streams(vault.home)
    port = free_port(args.port)
    url = f"http://127.0.0.1:{port}/"

    # 127.0.0.1 means only this computer can reach it.
    config = uvicorn.Config(create_app(vault), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    if args.no_browser:
        print(f"\n  inPace is running at {url}\n  Data folder: {vault.home}\n  Press Ctrl+C to stop.\n")
        server.run()
        return

    use_window = not args.browser
    webview = None
    if use_window:
        try:
            import webview  # type: ignore  # pywebview, optional
        except Exception:
            webview = None

    if webview is not None:
        threading.Thread(target=server.run, daemon=True).start()
        _wait_until_up(port)
        try:
            webview.create_window("inPace", url, width=1280, height=860, min_size=(420, 600))
            webview.start()
            os._exit(0)  # window closed: stop everything
        except Exception as e:  # no window support on this system: fall back to the browser
            print(f"App window unavailable ({e}); opening your browser instead.")

    print(f"\n  inPace is running at {url}")
    print(f"  Your data folder: {vault.home}")
    print("  Keep this window open while you use inPace. Close it (or press Ctrl+C) to stop.")
    print("  You can also use Settings > Quit inPace.\n")
    threading.Thread(target=lambda: (_wait_until_up(port), webbrowser.open(url)), daemon=True).start()
    if server.started:
        while True:  # already running in a thread after a failed window
            time.sleep(3600)
    server.run()


if __name__ == "__main__":
    main()
