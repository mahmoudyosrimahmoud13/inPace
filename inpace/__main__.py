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


def _stop_old_copy(home: Path) -> None:
    """If inPace is already running with this data folder (maybe an older version), close it first."""
    import json
    import urllib.request
    try:
        port = int(json.loads((home / "running.json").read_text(encoding="utf-8"))["port"])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=2) as r:
            info = json.loads(r.read().decode("utf-8"))
        if info.get("app") != "inpace" or Path(info.get("home", "")).resolve() != home.resolve():
            return
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/quit", data=b"", method="POST"),
                               timeout=3).read()
    except Exception:
        return
    for _ in range(30):  # wait until it has let go of the port
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(0.2)


def _start_updates(vault: Vault) -> None:
    """Installed apps: tidy up after the last update, then check for new versions once a day (if you said yes)."""
    from . import updater
    updater.clean_old_copies()
    if updater.install_kind() == "source":
        return

    def loop() -> None:
        while True:
            if vault.is_set_up and (vault._meta("updates", "") or "") == "auto":
                updater.run(vault)
            time.sleep(3600)

    threading.Thread(target=loop, daemon=True).start()


def _remember_port(home: Path, port: int) -> None:
    import json
    try:
        (home / "running.json").write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")
    except OSError:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(prog="inpace", description="inPace: learn at your pace, prove you kept it.")
    ap.add_argument("--home", type=Path, default=None, help=f"data folder (default: {default_home()})")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--browser", action="store_true", help="use your browser instead of the app window")
    ap.add_argument("--no-browser", action="store_true", help="don't open a window or browser")
    ap.add_argument("--which-window", nargs="?", const="-", metavar="FILE",
                    help="say which app window would be used (optionally into FILE), then exit")
    ap.add_argument("link", nargs="?", default=None, help="an inPace link to open (inpace://open/...)")
    args, _unknown = ap.parse_known_args()  # macOS may add its own arguments (-psn_...)
    if args.which_window:
        from .window import which
        kind = which()
        if args.which_window == "-":
            print(kind)
        else:
            Path(args.which_window).write_text(kind, encoding="utf-8")
        return

    vault = Vault(args.home)
    _quiet_streams(vault.home)
    _stop_old_copy(vault.home)
    _start_updates(vault)
    port = free_port(args.port)
    _remember_port(vault.home, port)
    from .links import register, start_path
    threading.Thread(target=register, daemon=True).start()  # tapping inPace links opens this copy
    url = f"http://127.0.0.1:{port}/" + start_path(args.link)

    # 127.0.0.1 means only this computer can reach it.
    config = uvicorn.Config(create_app(vault), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    if args.no_browser:
        print(f"\n  inPace is running at {url}\n  Data folder: {vault.home}\n  Press Ctrl+C to stop.\n")
        server.run()
        return

    if not args.browser:
        from .window import open_window
        threading.Thread(target=server.run, daemon=True).start()
        _wait_until_up(port)
        if open_window(url, vault.home):
            os._exit(0)  # window closed: stop everything
        print("No app window available here; opening your browser instead.")

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
