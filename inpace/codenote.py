"""Works with CodeNote (inPace 1.31): inPace teaches, CodeNote is the lab.

CodeNote (github.com/mahmoudyosrimahmoud13/code_note) is a separate, free code notebook app. A lesson with code (or a
practical task) can be sent to it with "Practice in CodeNote"; the work comes back to inPace as normal evidence
(an .html, .ipynb or .codenote file exported from CodeNote). The two apps share only the formats in the bridge spec
(Project doc claude/codenote-inpace-bridge.md, v1):

    codenote://open/BODY                                   the link inPace makes
    https://mahmoudyosrimahmoud13.github.io/code_note/open#BODY   web fallback, same BODY
    BODY = the payload's compact JSON, zlib level 9, URL-safe base64 without padding (like inPace links, SPEC §11)

The button only shows when CodeNote is found on this device (spec §8). On a computer inPace's own server does the
check (and opens the link, so it works the same in every kind of app window); on Android the app shell does both.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

from . import exchange

APP_LINK = "codenote://open/"
WEB_LINK = "https://mahmoudyosrimahmoud13.github.io/code_note/open#"
SITE = "https://mahmoudyosrimahmoud13.github.io/code_note/"
LINK_LIMIT = 30_000          # longer: the lesson goes as a .md file instead (spec §3)
PROOF_EXT = (".html", ".htm", ".ipynb", ".codenote")   # what "Export for inPace" makes (spec §5)
_FENCE = re.compile(r"^[ \t]{0,3}```[ \t]*([A-Za-z0-9_+#.-]*)", re.M)


# ---------------------------------------------------------------------------------------------------------------
# The payload and the link (spec §1 and §2)
# ---------------------------------------------------------------------------------------------------------------
def has_code(markdown: str) -> bool:
    """Does the lesson have at least one ``` code fence?"""
    return bool(_FENCE.search(markdown or ""))


def main_language(markdown: str) -> str:
    """The lesson's language for unmarked fences: the first fence that names one, else python."""
    for m in _FENCE.finditer(markdown or ""):
        if m.group(1):
            return m.group(1).lower()
    return "python"


def lesson_link(course_id: str, lesson_id: str) -> str:
    """The inPace link that opens this lesson again (SPEC §14): CodeNote's "Back to inPace"."""
    return exchange.APP_LINK + exchange._body({"inpace": "lesson", "course": course_id, "lesson": lesson_id})


def payload(course, module: dict, lesson: dict, task: dict | None = None) -> dict:
    """What CodeNote opens: the lesson's Markdown as inPace stores it, and where it came from."""
    md = lesson.get("content") or ""
    out = {"codenote": "lesson", "v": 1, "title": (lesson.get("title") or "")[:200], "language": main_language(md),
           "markdown": md}
    if task:
        out["task"] = {"id": task["id"], "prompt": task.get("prompt", "")}
        out["title"] = (f"{lesson.get('title', '')} · {task.get('prompt', '')}")[:200] if task.get("prompt") else out["title"]
    out["source"] = {"app": "inpace", "course": course.id, "course_title": course.title, "module": module["id"],
                     "lesson": lesson["id"], "lesson_title": lesson.get("title", ""),
                     "back": lesson_link(course.id, lesson["id"])}
    return out


def link(data: dict) -> str:
    return APP_LINK + exchange._body(data)


def web_link(data: dict) -> str:
    return WEB_LINK + exchange._body(data)


def read_link(text: str) -> dict:
    """Read a codenote:// link back (for tests and for anyone checking what inPace sent)."""
    import base64
    import zlib
    body = (text or "").split("codenote://open/", 1)[-1].split("#", 1)[-1]
    raw = zlib.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    return json.loads(raw.decode("utf-8"))


def lesson_file(data: dict) -> str:
    """The .md fallback (spec §3): front matter with title, language, task and source, then the lesson."""
    head = ["---", "codenote: lesson", "v: 1"]
    for key in ("title", "language", "task", "source"):
        if key in data:  # JSON is also YAML, so strings and the nested fields need no special quoting
            head.append(f"{key}: {json.dumps(data[key], ensure_ascii=False)}")
    head.append("---")
    return "\n".join(head) + "\n" + (data.get("markdown") or "")


def task_lesson(module: dict) -> dict | None:
    """The lesson a module's practical task goes with: the module's last lesson that has code, else its last one."""
    lessons = module.get("lessons") or []
    with_code = [les for les in lessons if has_code(les.get("content") or "")]
    return (with_code or lessons or [None])[-1]


# ---------------------------------------------------------------------------------------------------------------
# Is CodeNote on this computer? (spec §8) — cached, never slow
# ---------------------------------------------------------------------------------------------------------------
# Where inPace's pages show (set at start by __main__): "window" = inPace's own app window, which the server can
# open links for. In a plain browser tab ("") the button stays hidden (spec §8). Android: the app shell decides.
SHELL = {"kind": ""}
_CACHE = {"at": 0.0, "found": False}
_CHECK_LOCK = threading.Lock()
CACHE_SECONDS = 300


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _look() -> bool:
    if sys.platform == "win32":
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    winreg.CloseKey(winreg.OpenKey(root, r"Software\Classes\codenote\shell\open\command"))
                    return True
                except OSError:
                    continue
        except ImportError:
            pass
        return False
    if sys.platform == "darwin":
        try:
            from LaunchServices import LSCopyDefaultHandlerForURLScheme  # PyObjC, when it's there
            if LSCopyDefaultHandlerForURLScheme("codenote"):
                return True
        except Exception:
            pass
        return bool(_run(["mdfind", "kMDItemCFBundleIdentifier == 'org.code.note.codeNote'"]))
    if shutil.which("xdg-mime"):
        return _run(["xdg-mime", "query", "default", "x-scheme-handler/codenote"]).endswith(".desktop")
    return False


def installed(fresh: bool = False) -> bool:
    """CodeNote found on this computer. Asked again after 5 minutes, or sooner with fresh=True (the window came
    back to the front). Any error or a check over 1 second counts as not installed."""
    if os.environ.get("INPACE_MOBILE") == "android":
        return False  # the app shell checks on Android
    now = time.time()
    if not fresh and now - _CACHE["at"] < CACHE_SECONDS:
        return _CACHE["found"]
    if fresh and now - _CACHE["at"] < 15:  # coming back to the window often: at most every 15 seconds
        return _CACHE["found"]
    with _CHECK_LOCK:
        _CACHE["found"] = _look_within(TIMEOUT)
        _CACHE["at"] = time.time()
    return _CACHE["found"]


TIMEOUT = 1.0


def _look_within(seconds: float) -> bool:
    """_look(), but anything slower than `seconds` (or any error) is "not installed"."""
    box = {"found": False}

    def run() -> None:
        try:
            box["found"] = bool(_look())
        except Exception:
            box["found"] = False
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    return False if t.is_alive() else box["found"]


def available(fresh: bool = False) -> bool:
    """Show "Practice in CodeNote" on a computer: only in inPace's own window, and only when CodeNote is found.
    (This one may take up to a second: it's for /codenote.json, never for drawing a page.)"""
    return SHELL["kind"] == "window" and installed(fresh)


def available_now() -> bool:
    """For drawing a page: the last answer, right away. If it's old, a fresh check starts in the background and
    the page's script asks /codenote.json, so the button still appears without a reload."""
    if SHELL["kind"] != "window":
        return False
    if time.time() - _CACHE["at"] >= CACHE_SECONDS and not _CHECK_LOCK.locked():
        threading.Thread(target=installed, daemon=True).start()
    return _CACHE["found"]


def open_on_computer(app_link: str, web: str) -> str:
    """Open the link with CodeNote (the system's handler for codenote://). If that fails, the web fallback page in
    the browser. Returns "app", "web" or "" (nothing could be opened)."""
    try:
        if sys.platform == "win32":
            os.startfile(app_link)  # type: ignore[attr-defined]
            return "app"
        cmd = ["open", app_link] if sys.platform == "darwin" else ["xdg-open", app_link]
        from .window import _clean_env
        if subprocess.run(cmd, env=_clean_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=10).returncode == 0:
            return "app"
    except Exception:
        pass
    try:
        import webbrowser
        return "web" if webbrowser.open(web) else ""
    except Exception:
        return ""
