"""Open inPace from other apps.

Tapping an inPace link in a chat, an email or the inPace website opens `inpace://open/<data>`. This module
tells the computer that inPace handles those links, and turns the link it was opened with into the page
to show first.

  Windows   a per-user registry entry (no admin needed), refreshed on every start
  Mac       declared in the app's Info.plist (see packaging/build.py); links arrive as Apple events
  Linux     the .deb's inpace.desktop declares it; other installs get a small .desktop file in
            ~/.local/share/applications
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SCHEME = "inpace"


def start_path(link: str | None) -> str:
    """The first page to show when inPace was opened with a link, or "" for Home."""
    if not link:
        return ""
    from .exchange import link_body
    body = link_body(link if link.startswith("inpace:") or "#" in link else "inpace:" + link)
    return f"link?d={body}" if body else ""


def _command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    # Running from the code folder: make sure Python finds it whatever folder the link is opened from.
    root = str(Path(__file__).resolve().parent.parent)
    return ["env", f"PYTHONPATH={root}", sys.executable, "-m", "inpace"]


def register() -> str:
    """Make inpace:// links open this copy of inPace. Never fails loudly; returns what it did."""
    try:
        if sys.platform == "win32":
            return _windows()
        if sys.platform.startswith("linux"):
            return _linux()
        return "mac: Info.plist"
    except Exception as e:  # a missing tool or a locked registry shouldn't stop the app
        return f"skipped: {e}"


def _windows() -> str:
    if not getattr(sys, "frozen", False):
        return "skipped: running from source"
    import winreg  # type: ignore
    cmd = f'"{sys.executable}" "%1"'
    base = rf"Software\Classes\{SCHEME}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:inPace")
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\DefaultIcon") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{sys.executable}",0')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
    return "windows: registered"


def _desktop_quote(arg: str) -> str:
    if not any(c in arg for c in ' "\'\\$`'):
        return arg
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'


def _linux() -> str:
    if str(Path(sys.executable).resolve()).startswith("/opt/inpace/"):
        return "linux: handled by the installed package"
    xdg = shutil.which("xdg-mime")
    if not xdg:
        return "skipped: no xdg-mime"
    mime = f"x-scheme-handler/{SCHEME}"
    current = subprocess.run([xdg, "query", "default", mime], capture_output=True, text=True, timeout=5).stdout.strip()
    if current and current != "inpace-link.desktop":
        return f"linux: already handled by {current}"
    apps = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    exec_line = " ".join(_desktop_quote(a) for a in _command()) + " %u"
    entry = ("[Desktop Entry]\nType=Application\nName=inPace\nComment=Open inPace links\n"
             f"Exec={exec_line}\nIcon=inpace\nTerminal=false\nNoDisplay=true\nMimeType={mime};\n")
    target = apps / "inpace-link.desktop"
    if not target.exists() or target.read_text(encoding="utf-8") != entry:
        target.write_text(entry, encoding="utf-8")
        db = shutil.which("update-desktop-database")
        if db:
            subprocess.run([db, str(apps)], capture_output=True, timeout=10)
    if current != "inpace-link.desktop":
        subprocess.run([xdg, "default", "inpace-link.desktop", mime], capture_output=True, timeout=5)
    return "linux: registered"


def mac_listen(open_path) -> None:
    """Mac: links are sent to the running app as Apple events, not as command-line arguments.
    `open_path(path)` is called with the page to show."""
    try:
        import objc  # type: ignore
        from Foundation import NSAppleEventManager, NSObject  # type: ignore
    except Exception:
        return

    def fourcc(s: str) -> int:
        return int.from_bytes(s.encode("ascii"), "big")

    class _LinkHandler(NSObject):  # type: ignore[misc, valid-type]
        def handleURL_withReply_(self, event, reply):
            try:
                url = event.paramDescriptorForKeyword_(fourcc("----")).stringValue()
                path = start_path(str(url))
                if path:
                    open_path(path)
            except Exception:
                pass
        handleURL_withReply_ = objc.selector(handleURL_withReply_, signature=b"v@:@@")

    handler = _LinkHandler.alloc().init()
    mac_listen.handler = handler  # keep it alive
    NSAppleEventManager.sharedAppleEventManager().setEventHandler_andSelector_forEventClass_andEventID_(
        handler, "handleURL:withReply:", fourcc("GURL"), fourcc("GURL"))
