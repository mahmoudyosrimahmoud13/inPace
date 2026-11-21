"""Progress for anything that takes a while (v1.31.2): adding a course or a roadmap, updating inPace, getting yt-dlp.

One small, shared way, so every long button behaves the same:

  * The page sends the form in the background with a random `progress` token (app.js, forms marked
    [data-progress]) and asks /progress.json?t=<token> a few times a second.
  * The route doing the work calls report(token, ...) as it goes: what it's doing, how much is done, step n of m.
  * The button fills up and says it ("Downloading 2/5 · 45% · 3.1 / 7 MB"), so the app never looks frozen. When the
    route answers, the page goes where it says.

Entries are kept a couple of minutes after they finish, then forgotten.
"""
from __future__ import annotations

import threading
import time

STATES = ("running", "installing", "done", "failed")
PROGRESS: dict[str, dict] = {}
_NOW = threading.local()
_KEEP = 120


def report(token: str, **info) -> None:
    """Start or update one task's progress: title, note, got, size, n, of, state. No token: nothing happens."""
    if not token:
        return
    now = time.time()
    for k in [k for k, x in list(PROGRESS.items()) if x.get("state") in ("done", "failed") and now - x.get("at", 0) > _KEEP]:
        PROGRESS.pop(k, None)
    entry = PROGRESS.setdefault(token, {"title": "", "note": "", "got": 0, "size": 0, "n": 1, "of": 1, "state": "running"})
    entry.update({k: v for k, v in info.items() if v is not None}, at=now)


def get(token: str) -> dict:
    return dict(PROGRESS.get(token) or {})


def running() -> list[dict]:
    """Tasks still going (for the Downloads page and the phone's notification)."""
    return [dict(x) for x in list(PROGRESS.values()) if x.get("state") in ("running", "installing")]


class watching:
    """Within this block (in one thread), bytes() calls report how far a download got under `token`.
    Lets code deep down (a download loop) report progress without passing the token everywhere."""
    def __init__(self, token: str, **info):
        self.token, self.info = token, info

    def __enter__(self):
        if self.token:
            report(self.token, got=0, state="running", **self.info)
        _NOW.token = self.token
        return self

    def __exit__(self, kind, value, tb):
        _NOW.token = ""
        if value is not None and self.token:
            report(self.token, state="failed")
        return False


def within(token: str, info: dict, fn, *args, **kwargs):
    """Run fn(*args) in this thread while watching(token): for run_in_threadpool, where the work runs in another
    thread than the route."""
    with watching(token, **info):
        return fn(*args, **kwargs)


def bytes_done(got: int, size: int = 0) -> None:
    """Called from a download loop: how many bytes so far (size 0: unknown)."""
    token = getattr(_NOW, "token", "")
    if token:
        report(token, got=got, size=size or PROGRESS.get(token, {}).get("size", 0))


def watched() -> bool:
    return bool(getattr(_NOW, "token", ""))
