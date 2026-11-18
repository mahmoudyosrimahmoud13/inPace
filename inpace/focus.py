"""The floating timer: a focus timer you can start from any page and keep in view while you study.

It works on its own (no Tempo's island needed). If you tick "grow a plant", it starts a focus trip on the
island instead, and the floating timer shows that trip.

A plain timer is kept in the data folder's meta table as JSON, so it keeps counting across pages, windows
(the pop-out mini window too) and restarts:
    {"id", "goal": seconds, "banked": seconds already counted, "run_from": when it last started or None,
     "state": "running" | "paused", "label": what you're studying, "journey": course journey id}
"""
from __future__ import annotations

import json
import time
import uuid

from . import garden

LOOKS = ("pill", "card", "ring")
LENGTHS = (10, 15, 25, 45, 60, 90)
KEY = "focus_timer"


def look(v) -> str:
    x = v._meta("timer_look", "pill") or "pill"
    return x if x in LOOKS else "pill"


def set_look(v, x: str) -> None:
    v._set_meta("timer_look", x if x in LOOKS else "pill")


def _load(v) -> dict | None:
    try:
        d = json.loads(v._meta(KEY, "") or "null")
    except ValueError:
        return None
    return d if isinstance(d, dict) and d.get("goal") else None


def _save(v, d: dict | None) -> None:
    v._set_meta(KEY, json.dumps(d) if d else "")


def elapsed(d: dict, now: float | None = None) -> float:
    now = time.time() if now is None else now
    run = (now - d["run_from"]) if d.get("state") == "running" and d.get("run_from") else 0
    return max(0.0, float(d.get("banked") or 0) + run)


def _trip(v) -> dict | None:
    if not garden.is_on(v):
        return None
    t = garden.active(v)
    return t if t and t["state"] in ("running", "paused") else None


def start(v, minutes: int, plant: bool = False, label: str = "", journey: str = "") -> dict:
    minutes = minutes if minutes in LENGTHS else 25
    if plant and garden.is_on(v):
        _save(v, None)
        garden.start(v, "", minutes, "anywhere", journey)
        return live(v)
    now = time.time()
    _save(v, {"id": uuid.uuid4().hex[:12], "goal": minutes * 60, "banked": 0, "run_from": now, "state": "running",
              "label": label[:80], "journey": journey, "started": now})
    return live(v)


def pause(v) -> dict:
    t = _trip(v)
    if t:
        if t["state"] == "running":
            garden.rest(v, state="paused")
        return live(v)
    d = _load(v)
    if d and d["state"] == "running":
        d.update(banked=elapsed(d), run_from=None, state="paused")
        _save(v, d)
    return live(v)


def resume(v) -> dict:
    t = _trip(v)
    if t:
        if t["state"] == "paused":
            garden.resume(v)
        return live(v)
    d = _load(v)
    if d and d["state"] == "paused":
        d.update(run_from=time.time(), state="running")
        _save(v, d)
    return live(v)


def add(v, minutes: int = 5) -> dict:
    """A few more minutes: on the plain timer, or on the island trip (its plant then grows for the longer time)."""
    t = _trip(v)
    if t:
        v.db.execute("UPDATE garden SET goal=? WHERE id=?", (min(t["goal"] + minutes, 240), t["id"]))
        v.db.commit()
        return live(v)
    d = _load(v)
    if d:
        d["goal"] = min(d["goal"] + minutes * 60, 4 * 3600)
        _save(v, d)
    return live(v)


def stop(v) -> None:
    t = _trip(v)
    if t:
        if t["state"] == "paused":
            garden.resume(v)
        garden.rest(v)  # the sprout keeps its minutes, as on the island page
    _save(v, None)


def check(v, now: float | None = None) -> dict | None:
    """The plain timer, if its time just ran out (it's then cleared). A trip finishes through garden.check."""
    d = _load(v)
    if d and elapsed(d, now) >= d["goal"] - 0.5:
        _save(v, None)
        return d
    return None


def live(v) -> dict:
    """What the floating timer shows: {"on": False} or the running timer, plain or island trip."""
    t = _trip(v)
    if t:
        grown = garden.check(v)
        if grown:
            return {"on": False, "done": True, "goal": grown["goal"] * 60, "label": "", "plant": grown["kind"]}
        t = _trip(v)
    if t:
        left = max(0.0, t["goal"] * 60 - garden.elapsed(t))
        label = ""
        if t.get("journey"):
            try:
                j = v.journey(t["journey"])
                c = v.get_course(j["course_id"]) if j else None
                label = c.title if c else ""
            except Exception:
                label = ""
        return {"on": True, "kind": "trip", "id": t["id"], "state": t["state"], "goal": t["goal"] * 60,
                "left": round(left, 1), "label": label, "plant": t["kind"]}
    done = check(v)
    if done:
        return {"on": False, "done": True, "goal": done["goal"], "label": done.get("label", "")}
    d = _load(v)
    if not d:
        return {"on": False}
    return {"on": True, "kind": "timer", "id": d["id"], "state": d["state"], "goal": d["goal"],
            "left": round(max(0.0, d["goal"] - elapsed(d)), 1), "label": d.get("label", "")}
