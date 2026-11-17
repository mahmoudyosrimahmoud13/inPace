"""How inPace drives YouTube videos, as a few numbers and switches that can change without a new app version.

They come from the inPace website (site/youtube.json), checked once a day, like yt-dlp's updates. If YouTube
changes how its player talks to apps, fixing it is an edit to that file. It's data only, never code: every value is
checked against a list of known names and safe ranges, and anything odd falls back to the built-in default."""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

URL = "https://mahmoudyosrimahmoud13.github.io/inPace/youtube.json"
EVERY = 24 * 3600

# name: (default, smallest, largest). Booleans: (default, None, None).
RULES = {
    "own_controls": (True, None, None),        # False: use YouTube's own player and buttons everywhere
    "fallback_ms": (9000, 3000, 60000),       # no answer from YouTube by then: switch to YouTube's own player
    "cover_after_ms": (2500, 0, 10000),       # keep the still picture this long after playing starts
    "confirm_after_s": (3, 0, 60),            # a video that started at 0:00 counts as the lesson after this long
    "long_video_s": (60, 10, 600),            # ...or as soon as it's longer than this (ads are shorter)
    "ad_shorter_by_s": (2, 1, 30),            # a "video" this much shorter than the lesson, mid-way, is an ad
    "quality_menu": (True, None, None),       # show the Quality button
    "ad_guard": (True, None, None),           # step aside during ads and don't save their time as your place
}

_home: Path | None = None
_pref = None  # Settings → "Ad guard" (on unless you turn it off)
_lock = threading.Lock()


def clean(raw) -> dict:
    """Only known names, right types, inside the safe range; everything else is the default."""
    out = {}
    raw = raw if isinstance(raw, dict) else {}
    for name, (default, lo, hi) in RULES.items():
        v = raw.get(name, default)
        if isinstance(default, bool):
            out[name] = v if isinstance(v, bool) else default
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi:
            out[name] = int(v)
        else:
            out[name] = default
    return out


def use_home(home: Path, pref=None) -> None:
    global _home, _pref
    _home = Path(home)
    _pref = pref


def current() -> dict:
    """The rules to use now: the last good copy from the website, else the built-in ones."""
    rules = clean({})
    if _home is not None:
        try:
            rules = clean(json.loads((_home / "youtube-rules.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    if _pref is not None and not _pref():
        rules["ad_guard"] = False  # you turned the ad guard off in Settings
    return rules


def refresh_later() -> None:
    """Once a day, in the background, fetch the rules. Offline or a bad file: keep what we have."""
    if _home is None or not _lock.acquire(blocking=False):
        return
    stamp = _home / "youtube-rules.checked"
    try:
        if stamp.exists() and time.time() - stamp.stat().st_mtime < EVERY:
            _lock.release()
            return
    except OSError:
        pass

    def run():
        try:
            stamp.write_text(str(int(time.time())), encoding="utf-8")
            req = urllib.request.Request(URL, headers={"User-Agent": "inPace"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read(20_000).decode("utf-8"))
            if isinstance(data, dict):
                (_home / "youtube-rules.json").write_text(json.dumps(clean(data)), encoding="utf-8")
        except Exception:
            pass
        finally:
            _lock.release()
    threading.Thread(target=run, daemon=True).start()
