"""Reminders, alarms and Tempo's nudges.

You set reminders (a time and some days). Each one is either a quiet notification or an alarm that rings until
you stop or snooze it. inPace also sends a few automatic notifications, each of which you can turn off:

  miss       Tempo misses you, after you haven't opened inPace for a while (7 days unless you change it)
  goal       your weekly milestone goal is at risk, near the end of the week
  review     old questions are due for review
  milestone  you finished a module but haven't saved a milestone yet

inPace isn't running most of the time, so the reminders are handed to the computer or the phone:
  computer  its scheduler starts `inpace --remind <id>` and `inpace --check-reminders` (see notifier.py)
  Android   the page sends `plan()` to the app, which schedules Android notifications (see mobile/lib/main.dart)
"""
from __future__ import annotations

import json
import re
import secrets
from datetime import date, datetime, timedelta, timezone

from . import pace
from .vault import Vault

AUTO_KINDS = ("miss", "goal", "review", "milestone")
DEFAULT_MISS_DAYS = 7
EVENING = (17, 22)          # on a computer, automatic notifications go out between 5 pm and 10 pm
WELCOME_BACK_DAYS = 3       # coming back after this many days: Tempo says welcome back


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# ---- settings ---------------------------------------------------------------------------------------------

def _valid(r: dict) -> bool:
    return (isinstance(r, dict) and isinstance(r.get("id"), str) and re.fullmatch(r"[0-9a-f]{8}", r["id"]) is not None
            and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(r.get("time", ""))) is not None
            and isinstance(r.get("days"), list) and bool(r["days"]) and all(d in range(7) for d in r["days"])
            and r.get("kind") in ("notify", "alarm"))


def load(v: Vault) -> dict:
    try:
        d = json.loads(v._meta("reminders", "") or "{}")
    except ValueError:
        d = {}
    items = [{**r, "label": str(r.get("label", ""))[:80], "on": bool(r.get("on", True))}
             for r in d.get("items", []) if _valid(r)]
    auto = {k: bool((d.get("auto") or {}).get(k, True)) for k in AUTO_KINDS}
    try:
        miss = min(max(int(d.get("miss_days") or DEFAULT_MISS_DAYS), 1), 14)
    except (TypeError, ValueError):
        miss = DEFAULT_MISS_DAYS
    return {"items": sorted(items, key=lambda r: r["time"]), "auto": auto, "miss_days": miss}


def save(v: Vault, d: dict) -> None:
    v._set_meta("reminders", json.dumps({"items": d["items"], "auto": d["auto"], "miss_days": d["miss_days"]}))


def add(v: Vault, time: str, days: list[int], kind: str, label: str = "") -> dict | None:
    r = {"id": secrets.token_hex(4), "time": time, "days": sorted(set(days)), "kind": kind,
         "label": label.strip()[:80], "on": True}
    if not _valid(r):
        return None
    d = load(v)
    d["items"].append(r)
    save(v, d)
    return r


def change(v: Vault, rid: str, action: str) -> None:
    d = load(v)
    if action == "delete":
        d["items"] = [r for r in d["items"] if r["id"] != rid]
    elif action == "toggle":
        for r in d["items"]:
            if r["id"] == rid:
                r["on"] = not r["on"]
    save(v, d)


def set_auto(v: Vault, auto: dict, miss_days: int) -> None:
    d = load(v)
    d["auto"] = {k: bool(auto.get(k)) for k in AUTO_KINDS}
    d["miss_days"] = min(max(int(miss_days), 1), 14)
    save(v, d)


def find(v: Vault, rid: str) -> dict | None:
    return next((r for r in load(v)["items"] if r["id"] == rid), None)


def any_active(v: Vault) -> bool:
    d = load(v)
    return any(r["on"] for r in d["items"]) or any(d["auto"].values())


# ---- when you were last here ------------------------------------------------------------------------------

def touch(v: Vault, now: datetime | None = None) -> int | None:
    """Note that you opened inPace. Returns how many days you were away, when it's long enough for a welcome back."""
    now = now or _now()
    last = _parse(v._meta("last_seen", "") or "")
    if last and now - last < timedelta(minutes=5):
        return None
    v._set_meta("last_seen", _iso(now))
    if last and (now - last).days >= WELCOME_BACK_DAYS:
        return (now - last).days
    return None


# ---- what to say ------------------------------------------------------------------------------------------

def _tr():
    from .app import say, t  # the app's translations (English or Arabic, from Settings)
    return say, t


def use_language(v: Vault) -> None:
    from .app import CURRENT
    CURRENT["lang"] = (v._meta("lang", "en") or "en") if v.is_set_up else "en"


def next_lesson(v: Vault) -> dict | None:
    """The lesson to do next: in the course you used last, else in any course you've started."""
    row = v.db.execute(
        "SELECT e.journey FROM events e JOIN journeys j ON j.id = e.journey WHERE j.archived = 0 "
        "ORDER BY e.seq DESC LIMIT 1").fetchone()
    order = [row["journey"]] if row else []
    order += [j["id"] for j in v.journeys() if j["id"] not in order]
    for jid in order:
        prog = v.progress(jid)
        nxt, course = prog.get("next"), prog.get("course")
        if nxt and course:
            lesson = nxt["id"] if nxt["kind"] == "lesson" else nxt.get("lesson", "")
            return {"title": nxt["title"], "course": course.title,
                    "url": f"/learn/{jid}/lesson/{lesson}" if lesson else f"/learn/{jid}"}
    return None


def reminder_message(v: Vault, r: dict | None) -> dict:
    say, t = _tr()
    nxt = next_lesson(v)
    title = (r or {}).get("label") or say("Time to study")
    if nxt:
        body = t("Next: “{lesson}” in {course}. Slow and steady!", lesson=nxt["title"], course=nxt["course"])
    else:
        body = say("Pick a course and take one small step today.")
    return {"title": title, "body": body, "url": (nxt or {}).get("url", "/")}


def _miss_message(v: Vault, days: int) -> dict:
    say, t = _tr()
    nxt = next_lesson(v)
    if nxt:
        body = t("It's been {n} days. Your next lesson is “{lesson}”. Just 10 minutes today?", n=days, lesson=nxt["title"])
    else:
        body = t("It's been {n} days. Just 10 minutes today?", n=days)
    return {"title": say("Tempo misses you"), "body": body, "url": (nxt or {}).get("url", "/")}


def _goals(v: Vault, now: datetime) -> list[dict]:
    """Weekly goals that are behind, with how many days are left in the week."""
    say, t = _tr()
    out = []
    for j in v.journeys():
        evs = v.events(j["id"])
        wk = pace.weeks(evs, [m["body"]["created_at"] for m in v.milestones(j["id"])], now)
        tw, c = wk.get("this_week"), wk.get("commitment")
        if not tw or not c or pace.is_paused(evs) or tw["count"] >= c["per_week"]:
            continue
        end = datetime.fromisoformat(tw["start"]).replace(tzinfo=timezone.utc) + timedelta(days=7)
        course = v.get_course(j["course_id"])
        out.append({"key": f"goal:{j['id']}:{tw['start']}", "end": end,
                    "title": say("Your weekly goal"),
                    "body": t("You planned {goal} milestones this week and saved {done}. Keep going in “{course}”.",
                              goal=c["per_week"], done=tw["count"], course=course.title if course else ""),
                    "url": f"/learn/{j['id']}"})
    return out


def _review(v: Vault, today: date) -> tuple[int, date | None, str]:
    """(questions due today, the next day more become due, a course to review)"""
    due, nxt, url = 0, None, "/"
    for j in v.journeys():
        n = len(pace.due_cards(v, j["course_id"], today))
        if n and not due:
            url = f"/learn/{j['id']}/practice"
        due += n
        row = v.db.execute("SELECT MIN(due) d FROM review_cards WHERE course=? AND due>?",
                           (j["course_id"], today.isoformat())).fetchone()
        if row and row["d"]:
            d = date.fromisoformat(row["d"])
            nxt = d if nxt is None or d < nxt else nxt
    return due, nxt, url


def _milestones_to_save(v: Vault) -> list[dict]:
    say, t = _tr()
    out = []
    checkers = v.my_checkers()
    for j in v.journeys():
        ms = v.milestones(j["id"])
        saved = ms[-1]["body"]["summary"]["modules_done"] if ms else 0
        prog = v.progress(j["id"])
        if prog["modules_done"] <= saved:
            continue
        done = [m for m in prog["modules"] if m["status"] == "done"]
        module = done[-1]["title"] if done else ""
        body = (t("You finished “{module}”. Save a milestone and send it to {name}.", module=module,
                  name=checkers[0]["name"]) if checkers else
                t("You finished “{module}”. Save a milestone so your progress is on record.", module=module))
        out.append({"key": f"milestone:{j['id']}:{prog['modules_done']}", "title": say("Save your milestone"),
                    "body": body, "url": "/milestones"})
    return out


# ---- on a computer: what to show now ----------------------------------------------------------------------

def due_now(v: Vault, now_local: datetime | None = None, now: datetime | None = None) -> list[dict]:
    """Automatic notifications to show now (each at most once). Called every hour by the computer's scheduler."""
    now = now or _now()
    now_local = now_local or datetime.now()
    d = load(v)
    if not (EVENING[0] <= now_local.hour < EVENING[1]):
        return []
    try:
        log = json.loads(v._meta("notify_log", "") or "{}")
    except ValueError:
        log = {}
    out = []
    if d["auto"]["miss"]:
        last = _parse(v._meta("last_seen", "") or "")
        if last:
            away = (now - last).days
            sent = log.get("miss", {}) if log.get("miss", {}).get("since") == _iso(last) else {}
            count = int(sent.get("count", 0))
            if (count == 0 and away >= d["miss_days"]) or (count == 1 and away >= 2 * d["miss_days"]):
                out.append({**_miss_message(v, away), "log": ("miss", {"since": _iso(last), "count": count + 1})})
    if d["auto"]["goal"]:
        for g in _goals(v, now):
            if (g["end"] - now) <= timedelta(days=2) and log.get("goal") != g["key"]:
                out.append({**g, "log": ("goal", g["key"])})
                break
    if d["auto"]["review"]:
        due, _, url = _review(v, now_local.date())
        key = f"review:{now_local.date().isoformat()}"
        if due and log.get("review") != key:
            say, t = _tr()
            out.append({"title": say("Time for a quick review"),
                        "body": t("{n} questions are ready. It takes a few minutes.", n=due), "url": url,
                        "log": ("review", key)})
    if d["auto"]["milestone"]:
        for m in _milestones_to_save(v):
            if log.get("milestone") != m["key"]:
                out.append({**m, "log": ("milestone", m["key"])})
                break
    return out[:2]  # never a pile of notifications at once


def mark_sent(v: Vault, item: dict) -> None:
    try:
        log = json.loads(v._meta("notify_log", "") or "{}")
    except ValueError:
        log = {}
    kind, value = item["log"]
    log[kind] = value
    v._set_meta("notify_log", json.dumps(log))


# ---- on Android: the whole plan, scheduled by the app -----------------------------------------------------

def plan(v: Vault, now: datetime | None = None) -> dict:
    """Everything the Android app should schedule. Times for automatic ones are "not before" moments (UTC);
    the app shows them at 6:30 pm phone time on or after that moment. The page sends this plan again whenever
    you use inPace, so it always matches your latest progress."""
    say, t = _tr()
    now = now or _now()
    d = load(v)
    reminders = []
    for r in d["items"]:
        if r["on"]:
            msg = reminder_message(v, r)
            reminders.append({"id": r["id"], "time": r["time"], "days": r["days"], "kind": r["kind"], **msg})
    auto = []
    if d["auto"]["miss"]:
        last = _parse(v._meta("last_seen", "") or "") or now
        for n in (d["miss_days"], 2 * d["miss_days"]):
            auto.append({"key": f"miss{n}", "after": _iso(last + timedelta(days=n)), **_miss_message(v, n)})
    if d["auto"]["goal"]:
        for g in _goals(v, now)[:1]:
            auto.append({"key": "goal", "after": _iso(max(now, g["end"] - timedelta(days=2))),
                         "title": g["title"], "body": g["body"], "url": g["url"]})
    if d["auto"]["review"]:
        due, nxt, url = _review(v, now.date())
        if due:
            auto.append({"key": "review", "after": _iso(now), "title": say("Time for a quick review"),
                         "body": t("{n} questions are ready. It takes a few minutes.", n=due), "url": url})
        elif nxt:
            auto.append({"key": "review", "after": _iso(datetime(nxt.year, nxt.month, nxt.day, tzinfo=timezone.utc)),
                         "title": say("Time for a quick review"),
                         "body": say("Some questions are ready for review. It takes a few minutes."), "url": url})
    if d["auto"]["milestone"]:
        for m in _milestones_to_save(v)[:1]:
            auto.append({"key": "milestone", "after": _iso(now), "title": m["title"], "body": m["body"], "url": m["url"]})
    labels = {"stop": say("Stop"), "snooze": say("Snooze 10 min"), "open": say("Start studying"),
              "snoozed": say("Snoozed for 10 minutes."), "channel": say("Reminders"), "alarms": say("Alarms"),
              "tempo": say("Tempo")}
    test = reminder_message(v, {"label": say("Test: this is how a reminder looks")})
    return {"reminders": reminders, "auto": auto, "labels": labels, "evening": "18:30", "test": test}


# ---- the job the computer's scheduler runs ----------------------------------------------------------------

def run_job(v: Vault, remind: str | None, check: bool) -> None:
    """`inpace --remind <id>` and `inpace --check-reminders`: show what's due, then exit."""
    from . import notifier
    if not v.is_set_up:
        return
    use_language(v)
    say, _ = _tr()
    labels = {"stop": say("Stop"), "snooze": say("Snooze 10 min"), "open": say("Start studying")}
    if remind:
        if remind in ("test", "test-alarm"):
            r = {"label": say("Test: this is how a reminder looks"), "kind": "alarm" if remind == "test-alarm" else "notify"}
        else:
            r = find(v, remind)
            if not r or not r["on"] or datetime.now().weekday() not in r["days"]:
                return
        msg = reminder_message(v, r)
        if r["kind"] == "alarm":
            notifier.alarm(msg["title"], msg["body"], msg["url"], labels, v.home)
        else:
            notifier.notify(msg["title"], msg["body"], msg["url"], v.home)
    if check:
        for item in due_now(v):
            if notifier.notify(item["title"], item["body"], item["url"], v.home):
                mark_sent(v, item)
