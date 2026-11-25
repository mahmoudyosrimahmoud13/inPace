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


DAYS_KEY = "focus_days"


def _bank(v, seconds: float) -> None:
    """Add focused time to today's total (v1.33), so a sprint can show the hours you really timed each day.
    Less than half a minute isn't counted. Only the last 120 days are kept."""
    if not seconds or seconds < 30:
        return
    import datetime as _dt
    try:
        days = json.loads(v._meta(DAYS_KEY, "") or "{}")
        days = days if isinstance(days, dict) else {}
    except ValueError:
        days = {}
    hour = time.strftime("%Y-%m-%dT%H")  # by the hour, so a sprint day can start at 4 pm and end at 4 am
    days[hour] = int(days.get(hour, 0)) + int(seconds)
    cut = (_dt.date.today() - _dt.timedelta(days=120)).isoformat()
    for k in [k for k in days if k[:10] < cut]:
        del days[k]
    v._set_meta(DAYS_KEY, json.dumps(days))


def hour_totals(v) -> dict:
    """Seconds of focus timed in each hour: {"2026-11-25T16": 3000, ...} (older totals are whole days,
    "2026-11-24"), with the timer running now added to this hour."""
    try:
        days = json.loads(v._meta(DAYS_KEY, "") or "{}")
        days = {k: int(x) for k, x in days.items()} if isinstance(days, dict) else {}
    except (ValueError, TypeError):
        days = {}
    now = _running_seconds(v)
    if now:
        h = time.strftime("%Y-%m-%dT%H")
        days[h] = days.get(h, 0) + int(now)
    return days


def _running_seconds(v) -> float:
    t = _trip(v)
    if t:
        return garden.elapsed(t)
    d = _load(v)
    if d and (d.get("chain") or {}).get("phase") != "break":
        return min(elapsed(d), d["goal"])
    return 0.0


def seconds_since(v, ts: float) -> int:
    """Focus seconds banked from the hour `ts` falls in until now (not counting a timer that is running)."""
    from datetime import datetime
    since = datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H")
    try:
        days = json.loads(v._meta(DAYS_KEY, "") or "{}")
    except ValueError:
        return 0
    return sum(int(n) for k, n in (days.items() if isinstance(days, dict) else []) if "T" in k and k >= since)


def day_totals(v) -> dict:
    """Seconds of focus timed each calendar day: {"2026-11-25": 5400, ...}, with the timer running now added."""
    out: dict = {}
    for k, n in hour_totals(v).items():
        out[k[:10]] = out.get(k[:10], 0) + n
    return out


def elapsed(d: dict, now: float | None = None) -> float:
    now = time.time() if now is None else now
    run = (now - d["run_from"]) if d.get("state") == "running" and d.get("run_from") else 0
    return max(0.0, float(d.get("banked") or 0) + run)


def _trip(v) -> dict | None:
    if not garden.is_on(v):
        return None
    t = garden.active(v)
    return t if t and t["state"] in ("running", "paused") else None


class Busy(Exception):
    """Another timer is on: a sprint timer must be stopped before any other timer starts, and the other way round."""


def sprint_on(v) -> bool:
    """A sprint timer is on screen: running, on a break, paused, or ready."""
    d = _load(v)
    return bool(d and d.get("chain"))


def start(v, minutes: int, plant: bool = False, label: str = "", journey: str = "") -> dict:
    if sprint_on(v):
        raise Busy("Stop the sprint timer first. Then you can start another timer.")
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
        d.pop("ready", None)
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
        _bank(v, garden.elapsed(t))
        if t["state"] == "paused":
            garden.resume(v)
        garden.rest(v)  # the sprout keeps its minutes, as on the island page
    else:
        d = _load(v)
        if d and (d.get("chain") or {}).get("phase") != "break":
            _bank(v, min(elapsed(d), d["goal"]))
        if d and d.get("chain"):  # you stopped the sprint timer: it doesn't start again this sprint day
            ch = d["chain"]
            v._set_meta("sprint_timer_off", f"{int(ch.get('day_from') or 0)}|{ch['rid']}")
    _save(v, None)


def stopped_today(v, rid: str, day_from: float = 0) -> bool:
    """You pressed Stop for today on this sprint day (day_from: when the day started, as a timestamp)."""
    return (v._meta("sprint_timer_off", "") or "") == f"{int(day_from or 0)}|{rid}"


def ready_sprint(v, rid: str, label: str, target_seconds: int, focus_min: int, break_min: int, journey: str = "",
                 break_label: str = "Break", day_from: float = 0) -> None:
    """Put the sprint timer on screen, paused and ready: it shows up by itself when you open the sprint or one
    of today's courses, and counts nothing until you press play."""
    start_sprint(v, rid, label, target_seconds, focus_min, break_min, journey, break_label, day_from)
    d = _load(v)
    if d:
        d.update(banked=0, run_from=None, state="paused", ready=True)
        _save(v, d)


def drop_ready(v) -> None:
    """Take a ready sprint timer you never started off the screen again (you left the sprint)."""
    d = _load(v)
    if d and d.get("ready") and d["state"] == "paused" and not d.get("banked"):
        _save(v, None)


def check(v, now: float | None = None) -> dict | None:
    """The plain timer, if its time just ran out (it's then cleared). A trip finishes through garden.check."""
    d = _load(v)
    if d and elapsed(d, now) >= d["goal"] - 0.5:
        if d.get("chain"):
            return _advance(v, d, now)
        _save(v, None)
        _bank(v, d["goal"])
        return d
    return None


# ---- the sprint timer (v1.33): one button for the whole sprint day, focus blocks with breaks between ----------

def today_seconds(v) -> int:
    """Seconds already banked today, since midnight (not counting a timer that is running)."""
    import datetime as _dt
    return seconds_since(v, _dt.datetime.combine(_dt.date.today(), _dt.time()).timestamp())


def _chain_done_seconds(v, ch: dict) -> int:
    """Focus banked so far in this sprint day (which may have started at 4 pm yesterday)."""
    return seconds_since(v, ch["day_from"]) if ch.get("day_from") else today_seconds(v)


def start_sprint(v, rid: str, label: str, target_seconds: int, focus_min: int = 50, break_min: int = 10,
                 journey: str = "", break_label: str = "Break", day_from: float = 0) -> dict:
    """Run the sprint day: a focus block, then a break, then the next block, until today's focus reaches
    target_seconds (the sprint's hours a day). Breaks are never counted as focus."""
    focus_min = max(10, min(120, int(focus_min or 50)))
    break_min = max(3, min(30, int(break_min or 10)))
    target = max(600, int(target_seconds or 0)) if target_seconds else 8 * 3600
    d = _load(v)
    if (d and not d.get("chain")) or _trip(v):
        raise Busy("Stop the timer that's running first. Then start the sprint timer.")
    ch0 = {"day_from": day_from} if day_from else {}
    left = max(600, target - _chain_done_seconds(v, ch0))
    now = time.time()
    _save(v, {"id": uuid.uuid4().hex[:12], "goal": min(focus_min * 60, left), "banked": 0, "run_from": now,
              "state": "running", "label": label[:80], "journey": journey, "started": now,
              "chain": {"rid": rid, "focus": focus_min * 60, "brk": break_min * 60, "target": target, "block": 1,
                        "phase": "focus", "label": label[:80], "break_label": break_label[:40] or "Break", **ch0}})
    return live(v)


def _advance(v, d: dict, now: float | None = None) -> dict | None:
    """A sprint block just ran out: a focus block is banked and a break starts (or the day is done); a break
    ends and the next focus block starts. If you were away long after a break ended, the next block waits,
    paused, so time you weren't there is never counted."""
    now = time.time() if now is None else now
    ch = dict(d["chain"])
    ended_at = now - max(0.0, elapsed(d, now) - d["goal"])
    if ch["phase"] == "focus":
        _bank(v, d["goal"])
        if _chain_done_seconds(v, ch) >= ch["target"] - 30:
            _save(v, None)
            return {**d, "chain_done": True}
        ch["phase"] = "break"
        nxt = {"goal": ch["brk"], "label": ch.get("break_label") or "Break", "run_from": ended_at, "state": "running", "banked": 0}
    else:
        ch["phase"], ch["block"] = "focus", ch["block"] + 1
        left = max(60, ch["target"] - _chain_done_seconds(v, ch))
        late = now - ended_at > 120
        nxt = {"goal": min(ch["focus"], left), "label": ch["label"], "banked": 0,
               "run_from": None if late else ended_at, "state": "paused" if late else "running"}
    new = {**d, **nxt, "id": uuid.uuid4().hex[:12], "chain": ch}
    _save(v, new)
    if new["state"] == "running" and elapsed(new, now) >= new["goal"] - 0.5:
        return _advance(v, new, now)  # this one ran out too while nobody looked
    return {**new, "switched": ch["phase"]}


def sprint_timer(v, rid: str = "") -> dict | None:
    """The sprint timer, if one is running (for this roadmap, when rid is given)."""
    d = _load(v)
    if not d or not d.get("chain") or (rid and d["chain"]["rid"] != rid):
        return None
    ch = d["chain"]
    return {"phase": ch["phase"], "block": ch["block"], "state": d["state"], "left": round(max(0.0, d["goal"] - elapsed(d))),
            "goal": d["goal"], "focus_min": ch["focus"] // 60, "break_min": ch["brk"] // 60, "rid": ch["rid"],
            "target": ch["target"], "ready": bool(d.get("ready"))}


def live(v) -> dict:
    """What the floating timer shows: {"on": False} or the running timer, plain or island trip."""
    t = _trip(v)
    if t:
        grown = garden.check(v)
        if grown:
            _bank(v, grown["goal"] * 60)
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
    if done and not done.get("chain"):
        return {"on": False, "done": True, "goal": done["goal"], "label": done.get("label", "")}
    if done and done.get("chain_done"):
        return {"on": False, "done": True, "goal": done["goal"], "label": done.get("label", ""), "sprint_day_done": True}
    d = _load(v)
    if not d:
        return {"on": False}
    out = {"on": True, "kind": "timer", "id": d["id"], "state": d["state"], "goal": d["goal"],
           "left": round(max(0.0, d["goal"] - elapsed(d)), 1), "label": d.get("label", "")}
    if d.get("chain"):
        out["sprint"] = {"phase": d["chain"]["phase"], "block": d["chain"]["block"], "rid": d["chain"]["rid"]}
        if d.get("ready"):
            out["ready"] = True
        if done and done.get("switched"):
            out["switched"] = done["switched"]
    return out
