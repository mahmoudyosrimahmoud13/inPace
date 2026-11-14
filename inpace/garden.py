"""Tempo's island: the reward mode.

Tempo carries a little island on his shell. Two things make it grow:

- Focus trips. You pick a plant and a length, and while you study, Tempo swims and the plant grows
  on his back. When the time is up, it joins the island. Bigger trips grow bigger plants.
- Learning. Lessons, milestones, reviews, races and finished courses bring animal friends to live
  on the island, and unlock new kinds of plants.

It is gentle on purpose (slow and steady): nothing ever dies. Stop early and the sprout rests with
the minutes it already has, ready for next time. Every 10 plants, Tempo's shell grows a ring and the
island gets room for more. When your checker approves a milestone, the island blooms for a week.

Everything stays in vault.db, like the rest of your data.
"""
from __future__ import annotations

import json
import math
import time
import uuid
from datetime import date, datetime, timedelta, timezone

from . import garden_art as art
from . import island_story as story
from . import mascot as tempo
from .vault import Vault

LENGTHS = (10, 15, 25, 45, 60, 90)
MODES = ("anywhere", "phone")

# key, name, goal (stat, n, words) or None when you have it from the start
PLANTS = [
    ("sunflower", "Sunflower", None),
    ("oak", "Oak", None),
    ("pine", "Pine", ("plants", 3, "Grow {n} plants")),
    ("cactus", "Cactus", ("longest", 60, "Finish a {n}-minute trip")),
    ("cherry", "Cherry blossom", ("streak", 3, "Focus {n} days in a row")),
    ("lemon", "Lemon tree", ("plants", 10, "Grow {n} plants")),
    ("lavender", "Lavender", ("morning", 3, "Focus before 8 am, {n} times")),
    ("bamboo", "Bamboo", ("hours", 5, "Focus {n} hours in total")),
    ("palm", "Date palm", ("modules", 1, "Finish your first module")),
    ("olive", "Olive tree", ("milestones", 1, "Save your first milestone")),
    ("lotus", "Lotus", ("night", 3, "Focus after 9 pm, {n} times")),
    ("maple", "Maple", ("plants", 25, "Grow {n} plants")),
    ("baobab", "Baobab", ("longest", 90, "Finish a {n}-minute trip")),
    ("golden", "Golden tree", ("plants", 50, "Grow {n} plants")),
]

# key, name, goal, how they came to the island
FRIENDS = [
    ("snail", "Zoon the snail", ("lessons", 1, "Finish your first lesson"),
     "Zoon climbed aboard the day you finished your first lesson. It took him three days to reach the top. He says it was worth it."),
    ("sparrow", "Kiko the sparrow", ("plants", 1, "Grow your first plant"),
     "Tired from flying against the wind, Kiko landed on your very first plant. \"Is this an island?\" \"Sort of,\" said Tempo. She stayed."),
    ("frog", "Fofo the frog", ("reviews", 7, "Finish {n} daily reviews"),
     "Fofo jumps back to the same lily pad every day, the way your reviews bring back old questions. \"Again!\" he croaks."),
    ("bee", "Zizi the bee", ("milestones", 3, "Save {n} milestones"),
     "Zizi counts milestones like flowers. When she reached three, she moved in, honey and all."),
    ("owl", "Boomy the owl", ("approved", 1, "Get a milestone approved by your checker"),
     "Boomy is a checker too. When your first milestone was approved, she flew over to see it for herself, and stayed."),
    ("butterfly", "Farfoura the butterfly", ("days", 7, "Focus on {n} different days"),
     "Seven days of small steps, and the little caterpillar in your branches came out with wings."),
    ("hare", "Arnoob the hare", ("races", 1, "Join a race"),
     "Yes, that hare. He heard you joined a race and came to cheer. He still can't believe Tempo won."),
    ("crab", "Kaboria the crab", ("courses", 1, "Finish a whole course"),
     "The day you finished a course, Kaboria found a treasure chest on the seabed. Inside was your certificate."),
    ("gull", "Nawras the seagull", ("roadmap_steps", 1, "Finish a course on one of your roadmaps"),
     "Nawras flies ahead of every ship to see what's next. When you reached your first port on a roadmap, he landed on the mast and said: \"I'll show you the way to the next one.\""),
]
GULL_GOAL = ("roadmap_steps", 1, "Finish a course on one of your roadmaps")
VOYAGE_PORT = 10      # shells for each roadmap course you finish (on top of what the course itself pays)
VOYAGE_HARBOUR = 100  # shells for reaching the end of a roadmap

PLANT_NAMES = {k: n for k, n, _ in PLANTS}
FRIEND_NAMES = {k: n for k, n, _, _ in FRIENDS}


def setup(v: Vault) -> None:
    v.db.execute("CREATE TABLE IF NOT EXISTS garden (id TEXT PRIMARY KEY, kind TEXT, goal INTEGER, banked REAL DEFAULT 0, "
                 "run_from REAL, mode TEXT, journey TEXT, state TEXT, started REAL, ended REAL)")
    cols = {r[1] for r in v.db.execute("PRAGMA table_info(garden)")}
    for col in ("wilted_at", "dead_at"):
        if col not in cols:
            v.db.execute(f"ALTER TABLE garden ADD COLUMN {col} REAL")
    v.db.commit()


def is_on(v: Vault) -> bool:
    return (v._meta("garden", "") or "") == "on"


def set_on(v: Vault, on: bool) -> None:
    setup(v)
    v._set_meta("garden", "on" if on else "")
    if on and v._meta("garden_seen") is None:
        # What you already earned before turning it on shows up quietly, not as a pile of pop-ups.
        u = unlocked(v)
        v._set_meta("garden_seen", json.dumps(sorted(u["plants"] | u["friends"])))


# ---- trips --------------------------------------------------------------------------------------------

def _row(r) -> dict | None:
    return dict(r) if r else None


def active(v: Vault) -> dict | None:
    setup(v)
    return _row(v.db.execute("SELECT * FROM garden WHERE state IN ('running','paused','resting') ORDER BY started DESC LIMIT 1").fetchone())


def elapsed(trip: dict, now: float | None = None) -> float:
    now = time.time() if now is None else now
    run = (now - trip["run_from"]) if trip.get("state") == "running" and trip.get("run_from") else 0
    return max(0.0, (trip.get("banked") or 0) + run)


def start(v: Vault, kind: str, minutes: int, mode: str = "anywhere", journey: str = "") -> dict:
    """Start a trip, or carry on with the sprout that's resting."""
    setup(v)
    now = time.time()
    trip = active(v)
    if trip:
        if trip["state"] != "running":
            v.db.execute("UPDATE garden SET state='running', run_from=?, mode=? WHERE id=?",
                         (now, mode if mode in MODES else trip["mode"], trip["id"]))
            v.db.commit()
        return active(v)
    if kind not in PLANT_NAMES or kind not in unlocked(v)["plants"]:
        kind = "sunflower"
    minutes = minutes if minutes in LENGTHS else 25
    tid = uuid.uuid4().hex[:12]
    v.db.execute("INSERT INTO garden (id, kind, goal, banked, run_from, mode, journey, state, started) VALUES (?,?,?,?,?,?,?,?,?)",
                 (tid, kind, minutes, 0, now, mode if mode in MODES else "anywhere", journey or "", "running", now))
    v.db.commit()
    return active(v)


def rest(v: Vault, state: str = "resting") -> dict | None:
    """Stop for now. The sprout keeps every minute it already has."""
    trip = active(v)
    if trip and trip["state"] == "running":
        v.db.execute("UPDATE garden SET banked=?, run_from=NULL, state=? WHERE id=?", (elapsed(trip), state, trip["id"]))
        v.db.commit()
    return active(v)


def resume(v: Vault) -> dict | None:
    """Back on the focus screen in phone-down mode: the clock goes on."""
    trip = active(v)
    if trip and trip["state"] == "paused":
        v.db.execute("UPDATE garden SET state='running', run_from=? WHERE id=?", (time.time(), trip["id"]))
        v.db.commit()
    return active(v)


def let_go(v: Vault) -> None:
    """Start fresh: the resting sprout goes back to the sea (no penalty, it just isn't kept)."""
    trip = active(v)
    if trip and trip["state"] != "running":
        v.db.execute("DELETE FROM garden WHERE id=?", (trip["id"],))
        v.db.commit()


def check(v: Vault, now: float | None = None) -> dict | None:
    """Plant the trip on the island if its time is up. Returns the plant when it just grew."""
    trip = active(v)
    if not trip:
        return None
    if elapsed(trip, now) >= trip["goal"] * 60 - 1:
        when = time.time() if now is None else now
        v.db.execute("UPDATE garden SET state='grown', banked=?, run_from=NULL, ended=? WHERE id=?",
                     (trip["goal"] * 60, when, trip["id"]))
        # A finished trip waters the island: up to 2 wilting plants get better, and friends who fled come back.
        sick = v.db.execute("SELECT id FROM garden WHERE state='wilted' ORDER BY wilted_at LIMIT 2").fetchall()
        for r in sick:
            v.db.execute("UPDATE garden SET state='grown', wilted_at=NULL WHERE id=?", (r["id"],))
        v.db.commit()
        if v._meta("island_fled"):
            v._set_meta("island_fled", "")
        v._set_meta("island_last_seen", str(when))
        return {**trip, "state": "grown", "watered": len(sick)}
    return None


EVER = "('grown','wilted','dead','gone')"


def grown(v: Vault) -> list[dict]:
    """Every plant you ever grew, even ones the fog took since (unlocks never go away)."""
    setup(v)
    return [dict(r) for r in v.db.execute(f"SELECT * FROM garden WHERE state IN {EVER} ORDER BY ended")]


def on_island(v: Vault) -> list[dict]:
    """What the islands show: living plants, wilting ones, and dead ones you haven't cleared."""
    setup(v)
    return [dict(r) for r in v.db.execute("SELECT * FROM garden WHERE state IN ('grown','wilted','dead') ORDER BY ended")]


def last_grown(v: Vault) -> dict | None:
    setup(v)
    return _row(v.db.execute(f"SELECT * FROM garden WHERE state IN {EVER} ORDER BY ended DESC LIMIT 1").fetchone())


def clear_dead(v: Vault, jid: str | None = None) -> int:
    """Clear the dead plants away (they still count for what you've unlocked)."""
    setup(v)
    q, args = "UPDATE garden SET state='gone' WHERE state='dead'", ()
    if jid is not None:
        q, args = q + " AND COALESCE(journey,'')=?", (jid,)
    n = v.db.execute(q, args).rowcount
    v.db.commit()
    return n


# ---- the villain: when you stay away, the fog comes for the island ------------------------------------------
WILT_AFTER = 10   # days away before the first plant wilts
WILT_EVERY = 2    # then one more every 2 days
DIE_AFTER = 14    # a wilting plant dies after 14 days unless a trip waters it
FLEE_AFTER = 10   # friends flee when the fog reaches the island, and come back after your next trip


def gentle(v: Vault) -> bool:
    return (v._meta("island_gentle", "") or "") == "1"


def decay(v: Vault, now: float | None = None) -> dict:
    """What the fog did while you were away. It catches up when you come back, so it's fair either way."""
    setup(v)
    now = time.time() if now is None else now
    out = {"wilted": 0, "dead": 0, "new_wilted": 0, "new_dead": 0, "next_death": None, "next_wilt": None}
    last = last_active(v)
    if last is None or not is_on(v):
        return out
    seen = float(v._meta("island_last_seen", "") or last)
    # the absence: from the last activity we knew about, to your new activity (or to now, if you're still away)
    start = min(seen, last) if last - seen < 60 else seen
    end = last if last - start >= WILT_AFTER * 86400 and last > seen + 60 else now
    if not gentle(v):
        away = (end - start) / 86400
        if away >= FLEE_AFTER and not v._meta("island_fled"):
            v._set_meta("island_fled", "1")
        should = int((away - WILT_AFTER) // WILT_EVERY) + 1 if away >= WILT_AFTER else 0
        done = v.db.execute("SELECT COUNT(*) FROM garden WHERE wilted_at >= ? AND state IN ('wilted','dead','gone')",
                            (start,)).fetchone()[0]
        healthy = v.db.execute("SELECT id FROM garden WHERE state='grown' ORDER BY ended").fetchall()
        for k, r in zip(range(done, should), healthy):
            when = start + (WILT_AFTER + WILT_EVERY * k) * 86400
            v.db.execute("UPDATE garden SET state='wilted', wilted_at=? WHERE id=?", (when, r["id"]))
            out["new_wilted"] += 1
        for r in v.db.execute("SELECT id, wilted_at FROM garden WHERE state='wilted'").fetchall():
            if r["wilted_at"] + DIE_AFTER * 86400 <= now:
                v.db.execute("UPDATE garden SET state='dead', dead_at=? WHERE id=?", (r["wilted_at"] + DIE_AFTER * 86400, r["id"]))
                out["new_dead"] += 1
        v.db.commit()
        if end == now and now - last < WILT_AFTER * 86400:
            out["next_wilt"] = last + WILT_AFTER * 86400
    v._set_meta("island_last_seen", str(max(last, seen if end == now else last)))
    out["wilted"] = v.db.execute("SELECT COUNT(*) FROM garden WHERE state='wilted'").fetchone()[0]
    out["dead"] = v.db.execute("SELECT COUNT(*) FROM garden WHERE state='dead'").fetchone()[0]
    first = v.db.execute("SELECT MIN(wilted_at) FROM garden WHERE state='wilted'").fetchone()[0]
    out["next_death"] = first + DIE_AFTER * 86400 if first else None
    if v.db.execute("SELECT COUNT(*) FROM garden WHERE state IN ('dead','gone')").fetchone()[0]:
        v._set_meta("island_lost_any", "1")
    return out


def threat(days: int, is_gentle: bool = False) -> int:
    """How close the villain is: 0 gone, 1 watching from far away, 2 coming closer, 3 at the shore, 4 on the island."""
    lv = 0 if days < 2 else 1 if days < 4 else 2 if days < 7 else 3 if days < WILT_AFTER else 4
    return min(lv, 3) if is_gentle else lv


# ---- what you've earned -------------------------------------------------------------------------------

def _day(ts: float) -> date:
    return datetime.fromtimestamp(ts).date()


def _streak(days: set[date], today: date) -> int:
    d = today if today in days else today - timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= timedelta(days=1)
    return n


# ---- your courses pay off ------------------------------------------------------------------------------
# Lessons, modules and finished courses give shells (see earned()). On top of that, every course hides
# treasure chests at 25%, 50% and 75%, and a finished course puts a trophy on the island.
# Each course counts once: restarting it, removing and adding it again, or having the same course
# installed twice never pays twice.
CHESTS = ((25, 10), (50, 20), (75, 30))   # (% of the course, shells in the chest)


def _course_key(c) -> str:
    return getattr(c, "hash", "") or c.id


def _lessons_done(v: Vault) -> set[tuple[str, str]]:
    """(course, lesson) pairs you finished, across every start of every course, each pair once."""
    course_of = {r["id"]: r["course_id"] for r in v.db.execute("SELECT id, course_id FROM journeys")}
    keys = {c.id: _course_key(c) for c in v.courses()}
    out = set()
    for r in v.db.execute("SELECT journey, data FROM events WHERE type='lesson_done'"):
        try:
            lesson = json.loads(r["data"]).get("lesson")
        except (ValueError, TypeError):
            continue
        cid = course_of.get(r["journey"], r["journey"])
        out.add((keys.get(cid, cid), str(lesson)))
    return out


def course_rewards(v: Vault) -> list[dict]:
    """Every course you started, once, with its progress, its chests and what it paid you."""
    best: dict[str, dict] = {}
    for j in v.journeys():
        c = v.get_course(j["course_id"])
        if not c:
            continue
        try:
            prog = v.progress(j["id"])
        except Exception:
            continue
        row = {"journey": j["id"], "course_id": c.id, "key": _course_key(c), "title": c.title,
               "percent": int(prog.get("percent", 0) or 0), "finished": bool(prog.get("finished")),
               "modules": int(prog.get("modules_done", 0) or 0)}
        if row["key"] not in best or row["percent"] > best[row["key"]]["percent"]:
            best[row["key"]] = row  # the same course installed twice: the furthest one counts
    try:
        opened = json.loads(v._meta("course_chests", "{}") or "{}")
    except ValueError:
        opened = {}
    changed = False
    lessons = _lessons_done(v)
    rows = []
    for row in best.values():
        # chests stay open even if a course later gets longer and the percent drops
        reached = max([pct for pct, _ in CHESTS if row["percent"] >= pct] + [100 if row["finished"] else 0, 0])
        had = int(opened.get(row["course_id"], 0) or 0)
        if reached > had:
            opened[row["course_id"]] = reached
            changed = True
        top = max(had, reached)
        row["chests"] = [{"at": pct, "shells": n, "open": top >= pct} for pct, n in CHESTS]
        row["chest_shells"] = sum(n for pct, n in CHESTS if top >= pct)
        row["trophy"] = row["finished"] or top >= 100
        row["lessons"] = sum(1 for k, _ in lessons if k == row["key"])
        row["shells"] = 2 * row["lessons"] + 10 * row["modules"] + row["chest_shells"] + (50 if row["trophy"] else 0)
        nxt = next(((pct, n) for pct, n in CHESTS if top < pct), None)
        row["next"] = {"at": nxt[0], "shells": nxt[1]} if nxt else ({"at": 100, "shells": 50} if not row["trophy"] else None)
        rows.append(row)
    if changed:
        v._set_meta("course_chests", json.dumps(opened, sort_keys=True))
    rows.sort(key=lambda r: (r["trophy"], -r["percent"]))
    return rows


def stats(v: Vault, today: date | None = None) -> dict:
    setup(v)
    today = today or date.today()
    plants = grown(v)
    days = {_day(p["ended"]) for p in plants if p["ended"]}
    hours = [datetime.fromtimestamp(p["started"]).hour for p in plants if p["started"]]
    q = lambda sql: v.db.execute(sql).fetchone()[0] or 0
    mine = course_rewards(v)
    modules = sum(c["modules"] for c in mine)
    courses = sum(1 for c in mine if c["trophy"])
    focus_min = sum(p["goal"] for p in plants)
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    return {
        "plants": len(plants), "focus_min": focus_min, "hours": focus_min // 60,
        "longest": max((p["goal"] for p in plants), default=0),
        "days": len(days), "streak": _streak(days, today),
        "morning": sum(1 for h in hours if 4 <= h < 8), "night": sum(1 for h in hours if h >= 21 or h < 4),
        "week_min": sum(p["goal"] for p in plants if p["ended"] and _day(p["ended"]) > today - timedelta(days=7)),
        "lessons": len(_lessons_done(v)),
        "chest_shells": sum(c["chest_shells"] for c in mine),
        "reviews": q("SELECT COUNT(*) FROM events WHERE type='review_done'"),
        "milestones": q("SELECT COUNT(*) FROM milestones"),
        "approved": q("SELECT COUNT(*) FROM approvals WHERE decision='approved'"),
        "races": q("SELECT COUNT(*) FROM races"),
        "modules": modules, "courses": courses, **_roadmap_stats(v),
        "blooming": bool(v.db.execute("SELECT 1 FROM approvals WHERE decision='approved' AND at >= ? LIMIT 1",
                                      (week_ago[:10],)).fetchone()),
    }


def _roadmap_stats(v: Vault) -> dict:
    try:
        from . import roadmaps
        return roadmaps.island_stats(v)
    except Exception:
        return {"roadmap_steps": 0, "roadmaps": 0}


def _have(goal, st: dict) -> bool:
    return goal is None or st.get(goal[0], 0) >= goal[1]


def unlocked(v: Vault, st: dict | None = None) -> dict:
    st = st or stats(v)
    return {"plants": {k for k, _, g in PLANTS if _have(g, st)},
            "friends": {k for k, _, g, _ in FRIENDS if _have(g, st)}}


def collection(v: Vault, st: dict) -> dict:
    counts: dict[str, int] = {}
    for p in grown(v):
        counts[p["kind"]] = counts.get(p["kind"], 0) + 1
    plants = [{"key": k, "name": n, "goal": g, "have": _have(g, st), "grown": counts.get(k, 0),
               "progress": min(st.get(g[0], 0), g[1]) if g else 0} for k, n, g in PLANTS]
    friends = [{"key": k, "name": n, "goal": g, "story": story, "have": _have(g, st),
                "progress": min(st.get(g[0], 0), g[1])} for k, n, g, story in FRIENDS]
    return {"plants": plants, "friends": friends}


def news(v: Vault) -> list[dict]:
    """Plants and friends you just earned, once each (for the little pop-up)."""
    if not is_on(v):
        return []
    key = "|".join(str(v.db.execute(sql).fetchone()[0] or 0) for sql in (
        "SELECT MAX(seq) FROM events", "SELECT COUNT(*) FROM milestones", "SELECT COUNT(*) FROM approvals",
        "SELECT COUNT(*) FROM races")) + "|" + str(len(grown(v)))
    if v._meta("garden_key") == key:
        return []
    v._set_meta("garden_key", key)
    have = unlocked(v)
    seen = set(json.loads(v._meta("garden_seen", "[]") or "[]"))
    new = [{"kind": "plant", "key": k, "name": PLANT_NAMES[k]} for k in sorted(have["plants"] - seen)]
    new += [{"kind": "friend", "key": k, "name": FRIEND_NAMES[k]} for k in sorted(have["friends"] - seen)]
    for c in course_rewards(v):
        for ch in c["chests"]:
            k = f'chest:{c["course_id"]}:{ch["at"]}'
            if ch["open"] and k not in seen:
                new.append({"kind": "chest", "key": k, "name": c["title"], "at": ch["at"], "shells": ch["shells"]})
        k = f'trophy:{c["course_id"]}'
        if c["trophy"] and k not in seen:
            new.append({"kind": "trophy", "key": k, "name": c["title"], "shells": 50})
    try:  # the end of a roadmap: the harbour (v1.24)
        from . import roadmaps
        for rm in roadmaps.mine(v.home):
            k = f'harbour:{rm["id"]}'
            if k not in seen and roadmaps.status(v, rm)["finished"]:
                new.append({"kind": "harbour", "key": k, "name": rm["title"], "shells": VOYAGE_HARBOUR})
    except Exception:
        pass
    if new:
        v._set_meta("garden_seen", json.dumps(sorted(seen | {x["key"] for x in new})))
    return new


# ---- the weather is your pace -------------------------------------------------------------------------

def last_active(v: Vault) -> float | None:
    """When you last showed up: anything you did in a course (opening a lesson counts), or a focus trip."""
    row = v.db.execute("SELECT MAX(at) FROM events").fetchone()
    times = []
    if row and row[0]:
        try:
            times.append(datetime.fromisoformat(str(row[0]).replace("Z", "+00:00")).timestamp())
        except ValueError:
            pass
    trip = v.db.execute("SELECT MAX(COALESCE(ended, started)) FROM garden").fetchone()
    if trip and trip[0]:
        times.append(float(trip[0]))
    started = v._meta("garden_since")
    if started:
        times.append(float(started))
    return max(times) if times else None


def weather(v: Vault, goal_met: bool = False, now: float | None = None) -> dict:
    """Clear, mist, fog or lost: how long since you last studied, and how close the villain is."""
    now = time.time() if now is None else now
    last = last_active(v)
    days = int((now - last) // 86400) if last else 0
    fog = 0 if days < 2 else 1 if days < 4 else 2 if days < 7 else 3
    g = gentle(v)
    return {"days": days, "fog": fog, "fair": goal_met and fog == 0, "threat": threat(days, g), "gentle": g,
            "fled": bool(v._meta("island_fled")) and not g,
            "wilt_in": max(0, WILT_AFTER - days) if not g else None}


# ---- the story ------------------------------------------------------------------------------------------

def story_state(v: Vault, st: dict, wx: dict, lang: str, people: int = 0) -> dict:
    """Open the chapters you've earned and the interludes your real pace caused. Opened ones stay open."""
    world = story.world_for(v._meta("island_world", "") or "", lang)
    opened = json.loads(v._meta("island_story", "[]") or "[]")
    peak = int(v._meta("island_fog_peak", "0") or 0)
    added = []
    if wx["fog"] < 2:  # in thick fog, the story waits for you
        for key, _, _, _ in story.CHAPTERS:
            if key not in opened and story.opens(key, st):
                opened.append(key)
                added.append(key)
    if wx["fog"] >= 2:
        v._set_meta("island_fog_peak", str(max(peak, wx["fog"])))
    elif peak >= 2:
        v._set_meta("island_fog_peak", "0")
        if "fog_lifts" not in opened:
            opened.append("fog_lifts")
        added.append("fog_lifts")  # it can happen again: it moves to the top each time
        opened = [k for k in opened if k != "fog_lifts"] + ["fog_lifts"]
    if wx["fair"] and "fair_winds" not in opened:
        opened.append("fair_winds")
        added.append("fair_winds")
    if people and "meeting" not in opened:
        opened.append("meeting")
        added.append("meeting")
    if wx.get("threat", 0) >= 3 and "villain" not in opened:
        opened.append("villain")
        added.append("villain")
    if v._meta("island_lost_any") and "loss" not in opened:
        opened.append("loss")
        added.append("loss")
    if added:
        v._set_meta("island_story", json.dumps(opened))
    shown = [story.chapter(k, world, lang) for k in opened]
    for c in shown:
        c["new"] = c["key"] in added
    locked = [{"key": k, "title": t[0 if lang != "ar" else 1], "need": need}
              for k, t, need, _ in story.CHAPTERS if k not in opened]
    return {"world": world, "chapters": shown, "locked": locked, "added": added,
            "act": 1 if len([k for k in opened if k.startswith("c")]) <= 4 else 2 if "c9" not in opened else 3}


# ---- your turtles: one for each course, and Tempo for everything else ----------------------------------

PALETTES = [  # shell, dark, shade, light, scarf, scarf dark
    ("#25A06C", "#17774C", "#1C8A5B", "#6FD3A0", "#E6007E", "#A8005C"),   # Tempo
    ("#3D8FD1", "#25679E", "#2F7AB8", "#8CC3EE", "#FFB400", "#C98A00"),
    ("#B5651D", "#7E4513", "#985518", "#E0A06A", "#2EC4B6", "#1D8A80"),
    ("#8E5CC2", "#623C8C", "#7649A6", "#C3A0E8", "#FF6B6B", "#C94848"),
    ("#2A9D8F", "#1C6E64", "#227F74", "#7FD1C7", "#F4A261", "#C67B3E"),
    ("#D1495B", "#962F3D", "#B23B4C", "#F0909C", "#FFD43B", "#D9A90F"),
    ("#556B2F", "#3A4A1F", "#475A27", "#9DB36E", "#4CC9F0", "#2E93B5"),
    ("#E07A1F", "#A35512", "#C26818", "#F5B272", "#7B2CBF", "#561F87"),
]
def island(v: Vault, lang: str = "en") -> dict:
    """Your island: one for everything. Every focus trip grows here, whatever you were studying."""
    plants = on_island(v)
    out = {"id": "", "name": "Tempo" if lang != "ar" else "تمبو", "palette": PALETTES[0], "tempo": True,
           "title": titles(v).get("") or ("Tempo's Island" if lang != "ar" else "جزيرة تمبو"), "plants": plants}
    out["living"] = sum(1 for p in plants if p["state"] == "grown")
    out["wilting"] = sum(1 for p in plants if p["state"] == "wilted")
    out["dead"] = sum(1 for p in plants if p["state"] == "dead")
    return out


def recolor(svg: str, palette) -> str:
    """Draw a turtle in another turtle's colours."""
    base = PALETTES[0]
    for a, b in zip(base, palette):
        if a != b:
            svg = svg.replace(a, b)
    return svg


# ---- drawing ------------------------------------------------------------------------------------------

def size_of(goal: int) -> float:
    return 0.72 if goal <= 15 else 0.86 if goal <= 30 else 1.0 if goal <= 60 else 1.14


def plant_svg(kind: str, growth: float = 1.0, bloom: bool = False, px: int = 96, title: str = "") -> str:
    t = f"<title>{title}</title>" if title else ""
    return (f'<svg class="plant-art" width="{px}" height="{int(px * 4 / 3)}" viewBox="0 0 120 160" role="img" aria-label="{title}">'
            f'{t}{art.plant(kind, growth, bloom)}</svg>')


def friend_svg(key: str, px: int = 64, title: str = "") -> str:
    draw = art.FRIEND_ART.get(key)
    if not draw:
        return ""
    return f'<svg class="friend-art" width="{px}" height="{px}" viewBox="0 0 80 80" role="img" aria-label="{title}">{draw()}</svg>'


def _dome_points():
    """Points along the top of the island shell, to stand plants on."""
    def bez(p0, p1, p2, p3, t):
        a = (1 - t) ** 3
        b = 3 * (1 - t) ** 2 * t
        c = 3 * (1 - t) * t ** 2
        d = t ** 3
        return (a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])
    pts = [bez((110, 372), (106, 236), (230, 150), (380, 150), i / 60) for i in range(61)]
    pts += [bez((380, 150), (530, 150), (654, 236), (650, 372), i / 60) for i in range(1, 61)]
    return pts


_DOME = _dome_points()


def dome_y(x: float) -> float:
    best = min(_DOME, key=lambda p: abs(p[0] - x))
    return best[1]


def sun_times(day: date) -> tuple[float, float]:
    """About when the sun rises and sets (hours), for a place like Cairo, Rome or Dallas.
    Short days in December, long days in June."""
    swing = math.cos(2 * math.pi * (day.timetuple().tm_yday - 172) / 365)
    return 6.0 - 1.0 * swing, 18.0 + 1.0 * swing


# (name, top of the sky, bottom of the sky); the sky blends from one to the next as the clock moves
_SKY = {"night": ("#0F1A33", "#2A3A63"), "dawn": ("#6E7FB8", "#FFC6A0"), "morning": ("#8CCBF0", "#FFF1D6"),
        "day": ("#7EC4F0", "#E4F4FB"), "sunset": ("#FF7A50", "#FFD08A"), "dusk": ("#4B3C7A", "#E07A8A")}


def _mix(a: str, b: str, t: float) -> str:
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(f"{round(int(a[k:k + 2], 16) * (1 - t) + int(b[k:k + 2], 16) * t):02X}" for k in (0, 2, 4))


def sky_at(when: datetime | None = None) -> dict:
    """The sky at a real moment: its colors, where the sun or moon is, and how bright the stars are."""
    when = when or datetime.now()
    rise, sets = sun_times(when.date())
    h = when.hour + when.minute / 60
    keys = [(rise - 1.3, "night"), (rise - .2, "dawn"), (rise + 1.2, "morning"), (11.5, "day"), (sets - 1.6, "day"),
            (sets - .2, "sunset"), (sets + .6, "dusk"), (sets + 1.4, "night")]
    if h < keys[0][0] or h >= keys[-1][0]:
        top, low = _SKY["night"]
        phase = "night"
    else:
        for (h0, a), (h1, b) in zip(keys, keys[1:]):
            if h0 <= h < h1:
                t = (h - h0) / (h1 - h0)
                top, low = _mix(_SKY[a][0], _SKY[b][0], t), _mix(_SKY[a][1], _SKY[b][1], t)
                phase = a if t < .5 else b
                break
    night = h < rise - .4 or h >= sets + .9
    stars = 1.0 if night else max(0.0, min(1.0, (h - sets) / .9)) if h > 12 else max(0.0, min(1.0, (rise - h) / .9))
    if rise - .3 <= h <= sets + .3:  # the sun crosses the sky from left to right
        t = (h - (rise - .3)) / (sets - rise + .6)
        body = {"kind": "sun", "x": 70 + 660 * t, "y": 300 - 240 * math.sin(math.pi * t),
                "color": _mix("#FFD43B", "#FF8A3D", max(0.0, 1 - math.sin(math.pi * t) * 2.2))}
    else:  # the moon crosses the night
        length = 24 - (sets - rise) - .6
        gone = (h - (sets + .3)) % 24
        t = max(0.0, min(1.0, gone / length))
        body = {"kind": "moon", "x": 70 + 660 * t, "y": 300 - 230 * math.sin(math.pi * t), "color": "#FFF3B0"}
    return {"phase": phase, "top": top, "low": low, "night": night, "stars": round(stars, 2), "body": body,
            "rise": rise, "set": sets, "hour": h}


def _cloud(x: float, y: float, s: float) -> str:
    return (f'<g transform="translate({x} {y}) scale({s})">'
            '<path d="M0 30 Q-4 12 14 12 Q18 -6 40 2 Q56 -8 66 12 Q86 10 84 30 Z" fill="#fff" stroke="#111" stroke-width="3" stroke-linejoin="round"/></g>')


def _zzz(x: float, y: float) -> str:
    z = 'font-family="system-ui,sans-serif" font-weight="900" fill="#fff" stroke="#111" stroke-width="2" paint-order="stroke"'
    return f'<text x="{x}" y="{y}" font-size="18" {z}>z</text><text x="{x + 12}" y="{y - 12}" font-size="13" {z}>z</text>'


# ---- shells: what learning earns, and what you can buy with it ------------------------------------------------
THEMES = {"meadow": 0, "beach": 40, "blossom": 60, "autumn": 60, "desert": 70, "snow": 80}
THEME_COLORS = {"meadow": ("#6CBF4A", "#3E8E2E", "#B8E58F"), "beach": ("#F2D8A0", "#C9A86A", "#FFF1C9"),
                "blossom": ("#F7B7CF", "#D97FA5", "#FFE0EC"), "autumn": ("#D9A24A", "#A9702A", "#F2C98A"),
                "desert": ("#E3B46C", "#B98436", "#F6D8A3"), "snow": ("#F4F7FA", "#B8C6D3", "#FFFFFF")}
SKIES = {"auto": 0, "balloons": 30, "starry": 50, "aurora": 100}  # every sky still follows the real clock
WATERS = {"sea": 0, "turquoise": 25, "deep": 30, "lagoon": 40}
WATER_COLORS = {"sea": ("#4DA8D6", "#5BB7E0"), "turquoise": ("#3CC8C8", "#5FE0D8"),
                "deep": ("#25507E", "#3567A0"), "lagoon": ("#2FA88A", "#55C9A8")}
DECOR = {"flag": 20, "rocks": 15, "bench": 25, "campfire": 30, "lanterns": 35, "well": 40, "hut": 50,
         "windmill": 90, "lighthouse": 120}
DECOR_SPOT = {"lighthouse": 132, "windmill": 140, "well": 168, "bench": 214, "lanterns": 300, "campfire": 470,
              "rocks": 560, "hut": 598, "flag": 628}
MAX_DECOR = 4
SHOP_NAMES = {"meadow": "Green meadow", "beach": "Sandy beach", "blossom": "Blossom pink", "autumn": "Autumn gold",
              "desert": "Desert dunes", "snow": "Snowy island", "auto": "The real sky", "balloons": "Balloons by day, lanterns by night",
              "starry": "Starry nights", "aurora": "Northern lights", "sea": "Blue sea", "turquoise": "Turquoise water",
              "deep": "Deep ocean", "lagoon": "Green lagoon", "flag": "Flag with the island's name", "rocks": "Rocks",
              "bench": "Bench", "campfire": "Campfire", "lanterns": "Lanterns", "well": "Well", "hut": "Hut",
              "windmill": "Windmill", "lighthouse": "Lighthouse", "crown": "Crown", "wizard": "Wizard hat"}
SHOP = {"theme": THEMES, "sky": SKIES, "water": WATERS, "decor": DECOR, "accessory": tempo.PAID_ACCESSORIES}
FREE = {"theme:meadow", "sky:auto", "water:sea"}


def earned(st: dict) -> int:
    """Shells: 1 for every 5 minutes of focus, and more for real learning."""
    return (st["focus_min"] // 5 + 2 * st["lessons"] + 3 * st["reviews"] + 10 * st["modules"]
            + 15 * st["milestones"] + 20 * st["approved"] + 50 * st["courses"] + st.get("chest_shells", 0)
            + VOYAGE_PORT * st.get("roadmap_steps", 0) + VOYAGE_HARBOUR * st.get("roadmaps", 0))


def wallet(v: Vault, st: dict) -> dict:
    spent = int(v._meta("island_spent", "0") or 0)
    owned = set(json.loads(v._meta("island_owned", "[]") or "[]")) | FREE
    return {"earned": earned(st), "spent": spent, "balance": max(0, earned(st) - spent), "owned": owned}


def buy(v: Vault, kind: str, key: str, st: dict) -> str | None:
    """Buy something. Returns a problem in words, or None when it worked."""
    price = SHOP.get(kind, {}).get(key)
    if price is None:
        return "That isn't in the shop."
    w = wallet(v, st)
    item = f"{kind}:{key}"
    if item in w["owned"]:
        return None
    if w["balance"] < price:
        return "Not enough shells yet. Study a little more and come back."
    v._set_meta("island_spent", str(w["spent"] + price))
    v._set_meta("island_owned", json.dumps(sorted((w["owned"] - FREE) | {item})))
    return None


def looks(v: Vault, iid: str) -> dict:
    allv = json.loads(v._meta("island_looks", "{}") or "{}")
    lk = allv.get(iid, {})
    return {"theme": lk.get("theme", "meadow"), "sky": lk.get("sky", "auto"), "water": lk.get("water", "sea"),
            "decor": [d for d in lk.get("decor", []) if d in DECOR][:MAX_DECOR]}


def set_look(v: Vault, iid: str, kind: str, key: str) -> None:
    owned = set(json.loads(v._meta("island_owned", "[]") or "[]")) | FREE
    if f"{kind}:{key}" not in owned:
        return
    allv = json.loads(v._meta("island_looks", "{}") or "{}")
    lk = looks(v, iid)
    if kind == "decor":
        lk["decor"] = [d for d in lk["decor"] if d != key] if key in lk["decor"] else (lk["decor"] + [key])[-MAX_DECOR:]
    elif kind in ("theme", "sky", "water"):
        lk[kind] = key
    allv[iid] = lk
    v._set_meta("island_looks", json.dumps(allv))


def titles(v: Vault) -> dict:
    return json.loads(v._meta("island_titles", "{}") or "{}")


def set_title(v: Vault, iid: str, title: str) -> None:
    allv = titles(v)
    title = " ".join(title.split())[:30]
    if title:
        allv[iid] = title
    else:
        allv.pop(iid, None)
    v._set_meta("island_titles", json.dumps(allv))


# ---- sharing your island ------------------------------------------------------------------------------
# A small picture-free copy of your island travels on your contact card and the files you send, so the
# people you add can see it. It's only what's drawn: names of plants, friends, the look, a few numbers.

def share_on(v: Vault) -> bool:
    return (v._meta("island_share", "1") or "1") != "0"


def snapshot(v: Vault, lang: str = "en") -> dict | None:
    """Your island as data to share, or None when the island is off or you chose not to share it."""
    if not is_on(v) or not share_on(v):
        return None
    st = stats(v)
    isle = island(v, lang)
    shown = [{"kind": p["kind"], "goal": int(p["goal"]), "state": p["state"]} for p in isle["plants"]][-13:]
    return {"v": 1, "title": isle["title"], "look": looks(v, ""), "plants": shown,
            "friends": sorted(unlocked(v, st)["friends"]), "ring": 1 + isle["living"] // 10,
            "trophies": st["courses"], "stats": {"plants": st["plants"], "hours": st["hours"], "streak": st["streak"]},
            "at": int(time.time())}


def clean_snapshot(d) -> dict | None:
    """Someone else's island from their card or file: keep only what we know how to draw."""
    if not isinstance(d, dict) or d.get("v") != 1:
        return None
    look = d.get("look") if isinstance(d.get("look"), dict) else {}
    plants = []
    for p in (d.get("plants") or [])[-13:]:
        if isinstance(p, dict) and p.get("kind") in PLANT_NAMES and p.get("state") in ("grown", "wilted", "dead"):
            try:
                plants.append({"kind": p["kind"], "goal": max(10, min(90, int(p.get("goal", 25)))), "state": p["state"]})
            except (TypeError, ValueError):
                continue
    num = lambda x, top: max(0, min(top, int(x))) if isinstance(x, (int, float)) else 0
    stats_in = d.get("stats") if isinstance(d.get("stats"), dict) else {}
    return {"v": 1, "title": " ".join(str(d.get("title", "")).split())[:30],
            "look": {"theme": look.get("theme") if look.get("theme") in THEMES else "meadow",
                     "sky": look.get("sky") if look.get("sky") in SKIES else "auto",
                     "water": look.get("water") if look.get("water") in WATERS else "sea",
                     "decor": [x for x in (look.get("decor") or []) if x in DECOR][:MAX_DECOR]},
            "plants": plants, "friends": sorted({f for f in (d.get("friends") or []) if f in FRIEND_NAMES}),
            "ring": num(d.get("ring", 1), 9) or 1, "trophies": num(d.get("trophies", 0), 99),
            "stats": {k: num(stats_in.get(k, 0), 100000) for k in ("plants", "hours", "streak")},
            "at": num(d.get("at", 0), 10 ** 11)}


def season(month: int) -> str:
    return "winter" if month in (12, 1, 2) else "spring" if month in (3, 4, 5) else "summer" if month in (6, 7, 8) else "autumn"


def visitor_today(v: Vault, today: date | None = None) -> str | None:
    """Study today and something comes to visit: a dolphin, a whale, gulls, a jellyfish, a boat."""
    today = today or date.today()
    start = datetime(today.year, today.month, today.day).timestamp()
    trip = v.db.execute(f"SELECT 1 FROM garden WHERE state IN {EVER} AND ended >= ? LIMIT 1", (start,)).fetchone()
    les = v.db.execute("SELECT 1 FROM events WHERE type='lesson_done' AND at >= ? LIMIT 1",
                       (datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),)).fetchone()
    return art.VISITORS[today.toordinal() % len(art.VISITORS)] if (trip or les) else None


def island_svg(plants: list[dict], friends: set[str], ring: int, blooming: bool = False, hour: int | None = None,
               labels: dict | None = None, palette=None, fog: int = 0, fair: bool = False, home: bool = True,
               look: dict | None = None, title: str = "", villain: int = 0, season_now: str = "", visitor: str | None = None,
               fled: bool = False, trophies: int = 0) -> str:
    """The whole island scene: sky, sea, a turtle, the newest plants on its shell, your friends,
    the things you bought, and, when you've been away, the villain."""
    labels = labels or {}
    palette = palette or PALETTES[0]
    look = look or {"theme": "meadow", "sky": "auto", "water": "sea", "decor": []}
    when = datetime.now() if hour is None else datetime.now().replace(hour=hour, minute=0)
    sk = sky_at(when)
    top, low, night = sk["top"], sk["low"], sk["night"]
    sky = look.get("sky", "auto")
    if fog >= 2:
        top, low = _mix(top, "#9AA3AD", .7), _mix(low, "#C9CED3", .7)
    grass, edge, shine = THEME_COLORS.get(look.get("theme", "meadow"), THEME_COLORS["meadow"])
    back_sea, front_sea = WATER_COLORS.get(look.get("water", "sea"), WATER_COLORS["sea"])
    if sk["stars"] > .5:  # the sea is darker at night
        back_sea, front_sea = _mix(back_sea, "#0F1A33", .45), _mix(front_sea, "#0F1A33", .4)
    I = art.INK
    asleep = fog >= 2
    u = f"i{next(tempo._ids)}"  # ids must be unique if two islands share a page
    aria = labels.get("island", "Tempo carries your island")
    if labels.get("phase_" + sk["phase"]):
        aria += ". " + labels["phase_" + sk["phase"]]
    parts = [f'<svg class="island-art fog-{fog} threat-{villain} sky-{sk["phase"]}" viewBox="0 0 800 470" role="img" aria-label="{aria}">',
             f'<defs><linearGradient id="{u}-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
             f'<stop offset="1" stop-color="{low}"/></linearGradient>'
             f'<radialGradient id="{u}-glow"><stop offset="0" stop-color="#FFD98A" stop-opacity=".75"/><stop offset="1" stop-color="#FFD98A" stop-opacity="0"/></radialGradient>'
             f'<clipPath id="{u}-dome"><path d="M110 372 C106 236 230 150 380 150 C530 150 654 236 650 372 Z"/></clipPath>'
             f'<filter id="{u}-grey"><feColorMatrix type="saturate" values="{1 if fog == 0 else .6 if fog == 1 else .22}"/></filter>'
             f'<filter id="{u}-wilt"><feColorMatrix type="matrix" values=".5 .3 .1 0 .08  .35 .4 .1 0 .04  .2 .2 .2 0 0  0 0 0 1 0"/></filter></defs>',
             f'<rect width="800" height="470" fill="url(#{u}-sky)"/>']
    clear = fog < 2
    if clear and sk["stars"] > 0:
        dots = ((60, 40, 2), (150, 90, 1.6), (240, 30, 2.2), (520, 50, 1.8), (600, 110, 1.4), (720, 30, 2),
                (430, 90, 1.5), (330, 60, 1.4), (90, 150, 1.2), (380, 24, 1.6), (650, 170, 1.2), (200, 200, 1.1))
        if sky == "starry":  # a sky full of stars, the Milky Way, and a shooting star
            dots += tuple((37 * k % 800, 13 + 29 * k % 220, .9 + k % 3 * .4) for k in range(1, 40))
            parts.append(f'<path d="M-20 260 Q300 60 820 40" stroke="#C9D6FF" stroke-width="70" fill="none" opacity="{.16 * sk["stars"]:.2f}" stroke-linecap="round"/>'
                         f'<path class="isle-shooting" d="M560 30 l-90 40" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity="{sk["stars"]:.2f}"/>')
        parts.append(f'<g class="isle-stars" opacity="{sk["stars"]:.2f}">'
                     + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff"/>' for x, y, r in dots) + '</g>')
    if sky == "aurora" and clear and sk["stars"] > .2:
        parts.append(f'<g opacity="{sk["stars"]:.2f}"><path class="isle-aurora" d="M0 120 Q200 40 400 110 T800 80 V170 Q600 150 400 190 T0 170 Z" fill="#5CF2B8" opacity=".35"/>'
                     '<path class="isle-aurora" d="M0 90 Q240 20 420 80 T800 50 V110 Q600 100 420 140 T0 130 Z" fill="#A98BFF" opacity=".28"/></g>')
    if clear:
        b = sk["body"]
        bx, by = b["x"], b["y"]
        if b["kind"] == "sun":
            parts.append(f'<circle cx="{bx:.0f}" cy="{by:.0f}" r="70" fill="url(#{u}-glow)" opacity=".7"/>'
                         f'<circle class="isle-sun" cx="{bx:.0f}" cy="{by:.0f}" r="34" fill="{b["color"]}" stroke="{I}" stroke-width="3"/>'
                         f'<circle cx="{bx - 10:.0f}" cy="{by - 10:.0f}" r="10" fill="#fff" opacity=".45"/>')
        else:
            parts.append(f'<path class="isle-moon" d="M{bx:.0f} {by - 26:.0f} a30 30 0 1 0 22 50 a24 24 0 1 1 -22 -50 z" fill="{b["color"]}" stroke="{I}" stroke-width="3"/>')
        if not night:
            parts.append(f'<g class="isle-clouds">{_cloud(90, 60, 1)}{_cloud(470, 40, .8)}</g>')
            if sky == "balloons":
                for bx2, by2, c1, c2 in ((180, 96, "#E6007E", "#FFD43B"), (612, 150, "#3D8FD1", "#FFFFFF")):
                    parts.append(f'<g class="isle-balloon" transform="translate({bx2} {by2})"><path d="M0 -30 C-24 -30 -26 -2 -6 14 H6 C26 -2 24 -30 0 -30 Z" fill="{c1}" stroke="{I}" stroke-width="3"/>'
                                 f'<path d="M0 -30 C-8 -20 -8 0 -3 14 M0 -30 C8 -20 8 0 3 14" fill="none" stroke="{c2}" stroke-width="3"/>'
                                 f'<path d="M-6 14 L-5 22 M6 14 L5 22" stroke="{I}" stroke-width="2"/><rect x="-6" y="22" width="12" height="9" rx="2" fill="#B7793E" stroke="{I}" stroke-width="2.4"/></g>')
        elif sky == "balloons":  # at night: floating paper lanterns
            for lx, ly in ((160, 110), (250, 70), (560, 90), (640, 140)):
                parts.append(f'<g class="isle-balloon"><circle cx="{lx}" cy="{ly}" r="16" fill="url(#{u}-glow)"/>'
                             f'<path d="M{lx - 6} {ly - 8} h12 l3 14 h-18 z" fill="#FFB648" stroke="{I}" stroke-width="2"/></g>')
    if fair and fog == 0 and not night:
        for k, c in enumerate(("#E6007E", "#FF9F1C", "#FFD43B", "#4CAF50", "#3D8FD1", "#8E5CC2")):
            r = 330 - k * 12
            parts.append(f'<path d="M{380 - r} 330 A{r} {r} 0 0 1 {380 + r} 330" fill="none" stroke="{c}" stroke-width="12" opacity=".75"/>')
    # the villain, far away or close behind the island
    def villain_at(x, y, sc, cls=""):
        return (f'<g class="isle-villain {cls}" transform="translate({x} {y}) scale({sc})"><title>{labels.get("villain", "The Fog of Someday")}</title>'
                f'{art.villain(villain)}</g>')
    if villain == 1:
        parts.append(f'<g opacity=".75">{villain_at(686, 238, .34)}</g>')
    elif villain == 2:
        parts.append(villain_at(10, 150, .62))
    elif villain == 3:
        parts.append(villain_at(-30, 70, 1.0))
    parts.append(f'<g filter="url(#{u}-grey)">')
    parts.append(f'<rect x="0" y="330" width="800" height="140" fill="{back_sea}"/>'
                 f'<path d="M0 330 H800" stroke="{I}" stroke-width="3"/>'
                 '<path d="M40 350 q20 -8 40 0 M520 346 q20 -8 40 0 M700 356 q16 -6 32 0" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".7"/>')
    if visitor and fog < 2:
        vx = {"dolphin": 740, "whale": 735, "seagull": 520, "jellyfish": 750, "boat": 742}.get(visitor, 740)
        parts.append(f'<g class="isle-visitor isle-visitor-{visitor}" transform="translate({vx} 352) scale(.8)"><title>{labels.get("visitor", "")}</title>{art.visitor(visitor)}</g>')
    if "lighthouse" in look.get("decor", []):
        glow = f'<circle cx="0" cy="-96" r="70" fill="url(#{u}-glow)"/>' if sk["stars"] > .3 else ""
        parts.append(f'<g class="isle-deco" transform="translate(46 344) scale(.9)"><title>{labels.get("deco_lighthouse", "lighthouse")}</title>{glow}'
                     f'<path d="M-30 6 Q-26 -10 -6 -8 Q8 -16 24 -4 Q34 0 30 8 Z" fill="#8E877D" stroke="{I}" stroke-width="3"/>'
                     f'<g transform="translate(0 -6)">{art.deco("lighthouse")}</g></g>')
    # the turtle: head and neck behind the shell's edge, then the shell
    s = 2.4
    mood = "sleepy" if asleep else ("oops" if villain >= 3 else "think" if fog == 1 else "cheer" if (fair or blooming) else "happy")
    if villain >= 4:
        mood = "sad"
    turtle = (f'<path d="M600 350 C640 330 668 312 690 290" fill="none" stroke="{I}" stroke-width="{20 * s + 6}" stroke-linecap="round"/>'
              f'<path d="M600 350 C640 330 668 312 690 290" fill="none" stroke="{tempo.SKIN}" stroke-width="{20 * s - 1}" stroke-linecap="round"/>'
              f'<g transform="translate({704 - 171 * s:.1f} {258 - 49 * s:.1f}) scale({s})">{tempo.scarf()}{tempo.head(mood)}</g>')
    rim = "M100 360 H660 V372"
    x = 660
    for _ in range(14):
        rim += f" Q{x - 20} 394 {x - 40} 372"
        x -= 40
    turtle += f'<path d="{rim} Z" fill="{tempo.RIM}" stroke="{I}" stroke-width="4" stroke-linejoin="round"/>'
    turtle += (f'<path d="M110 372 C106 236 230 150 380 150 C530 150 654 236 650 372 Z" fill="{tempo.SHELL}"/>'
               f'<g clip-path="url(#{u}-dome)">'
               f'<ellipse cx="380" cy="390" rx="300" ry="80" fill="{tempo.SHELL_SHADE}"/>'
               f'<path d="M300 300 L330 250 H430 L460 300 L430 350 H330 Z M330 250 L300 200 M430 250 L460 200 M300 300 H100 M460 300 H660 '
               f'M330 350 L300 400 M430 350 L460 400" fill="none" stroke="{tempo.SHELL_DARK}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append(recolor(turtle, palette))
    parts.append(f'<ellipse cx="380" cy="150" rx="320" ry="96" fill="{grass}"/>'
                 f'<path d="M60 222 Q120 250 180 232 Q240 262 300 240 Q360 268 420 242 Q480 266 540 240 Q600 258 660 230 Q700 220 720 210" '
                 f'fill="none" stroke="{edge}" stroke-width="5" stroke-linecap="round"/>'
                 f'<path d="M170 196 q30 -30 70 -36" fill="none" stroke="{shine}" stroke-width="7" stroke-linecap="round" opacity=".8"/>'
                 '</g>'
                 f'<path d="M110 372 C106 236 230 150 380 150 C530 150 654 236 650 372 Z" fill="none" stroke="{I}" stroke-width="4" stroke-linejoin="round"/>')
    for gx in (200, 280, 470, 560):
        gy = dome_y(gx)
        parts.append(f'<path d="M{gx - 8} {gy + 2} l3 -10 l3 8 l3 -12 l3 12 l3 -8 l3 10" fill="none" stroke="{edge}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')
    if not plants:
        parts.append(f'<g transform="translate({380 - 60 * .7:.0f} {dome_y(380) + 8 - 150 * .7:.0f}) scale(.7)">{art.seed()}</g>')
    # plants: the newest ones, from the middle outwards
    room = min(5 + 2 * ring, 13)
    shown = plants[-room:]
    n = len(shown)
    if n:
        span = min(400, 64 * (n - 1))
        xs = [380 - span / 2 + (span * i / (n - 1) if n > 1 else span / 2) for i in range(n)]
        order = sorted(range(n), key=lambda i: abs(xs[i] - 380))  # middle first
        placed = list(zip(order, reversed(shown)))  # the newest plant takes the middle
        for slot, p in sorted(placed, key=lambda t: abs(xs[t[0]] - 380)):
            x = xs[slot]
            y = dome_y(x) + 10
            sc = 0.78 * size_of(p["goal"])
            state = p.get("state", "grown")
            name = labels.get("plant_" + p["kind"], PLANT_NAMES.get(p["kind"], ""))
            if state == "dead":
                parts.append(f'<g class="isle-plant dead" transform="translate({x - 60 * .7:.1f} {y - 150 * .7:.1f}) scale(.7)">'
                             f'<title>{labels.get("dead", "")}</title>{art.dead_plant()}</g>')
                continue
            bloom = (blooming or p["goal"] >= 60) and state == "grown"
            extra = f' filter="url(#{u}-wilt)"' if state == "wilted" else ""
            tilt = f" rotate({8 if slot % 2 else -8} 60 150)" if state == "wilted" else ""
            parts.append(f'<g class="isle-plant {state}" transform="translate({x - 60 * sc:.1f} {y - 150 * sc:.1f}) scale({sc:.3f}){tilt}"{extra}>'
                         f'<title>{name}{(" · " + labels["wilting"]) if state == "wilted" and labels.get("wilting") else ""}</title>{art.plant(p["kind"], 1, bloom)}</g>')
    # the things you bought, on the grass in front of the plants (the lighthouse stands in the sea)
    front = [d for d in look.get("decor", []) if d != "lighthouse"]
    for d, (dx, dy) in zip(front, ((240, 232), (520, 232), (380, 242), (310, 240))):
        glow = (f'<circle cx="0" cy="-40" r="60" fill="url(#{u}-glow)"/>'
                if sk["stars"] > .3 and d in ("lanterns", "campfire", "hut") else "")
        parts.append(f'<g class="isle-deco" transform="translate({dx} {dy}) scale(.72)"><title>{labels.get("deco_" + d, d)}</title>'
                     f'{glow}{art.deco(d, title)}</g>')
    # a golden cup for every course you finished (up to 5 shown)
    for k in range(min(trophies, 5)):
        tx = 452 + 22 * k
        parts.append(f'<g class="isle-trophy" transform="translate({tx} {238 + 4 * (k % 2)}) scale(.55)"><title>{labels.get("trophy", "A finished course")}</title>'
                     f'<path d="M-12 -38 H12 V-26 Q12 -12 0 -10 Q-12 -12 -12 -26 Z" fill="#FFD43B" stroke="{I}" stroke-width="3" stroke-linejoin="round"/>'
                     f'<path d="M-12 -34 Q-22 -34 -18 -24 Q-15 -19 -10 -20 M12 -34 Q22 -34 18 -24 Q15 -19 10 -20" fill="none" stroke="{I}" stroke-width="3"/>'
                     f'<path d="M-3 -10 V-4 H3 V-10 M-9 0 H9 V-4 H-9 Z" fill="#D9A90F" stroke="{I}" stroke-width="3" stroke-linejoin="round"/>'
                     f'<path d="M-6 -33 Q-6 -20 0 -16" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" opacity=".7"/></g>')
    if home and not fled:
        def friend(key, transform, extra=""):
            z = _zzz(70, 10) if asleep else ""
            return (f'<g class="isle-friend" data-friend="{key}" transform="{transform}"><title>{labels.get(key, FRIEND_NAMES[key])}</title>'
                    f'{art.FRIEND_ART[key]()}{z}</g>{extra}')
        for key, fx, fs in (("owl", 176, .78), ("hare", 600, .78)):
            if key in friends:
                y = dome_y(fx) + 8
                parts.append(friend(key, f"translate({fx - 40 * fs:.1f} {y - 78 * fs:.1f}) scale({fs})"))
        if "snail" in friends:
            parts.append(friend("snail", "translate(112 300) rotate(-38) scale(.62)"))
        for key, (fx, fy, fs) in {"sparrow": (250, 66, .74), "butterfly": (556, 118, .56), "bee": (470, 160, .5),
                                  "gull": (690, 70, .66)}.items():
            if key in friends:
                if asleep:  # in the fog the flyers sit down and nap
                    fx, fy = {"sparrow": (300, dome_y(300) - 6), "butterfly": (520, dome_y(520) - 4), "bee": (440, dome_y(440) - 2),
                              "gull": (640, dome_y(640) - 6)}[key]
                parts.append(friend(key, f"translate({fx - 40 * fs:.1f} {fy - 40 * fs:.1f}) scale({fs})", ""))
    if blooming and fog == 0:
        for x, y in ((150, 140), (620, 170), (330, 110), (430, 96), (250, 200)):
            parts.append(art._flower5(x, y, 4, "#F8BBD0", "#FFD43B"))
    wave = "M0 382"
    for _ in range(20):
        wave += " q20 -10 40 0"
    parts.append(f'<path class="isle-wave" d="{wave} V470 H0 Z" fill="{front_sea}" stroke="{I}" stroke-width="3" stroke-linejoin="round"/>'
                 '<path d="M80 414 q24 -10 48 0 M300 432 q24 -10 48 0 M600 420 q24 -10 48 0" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".75"/>')
    if home and not fled and "frog" in friends:
        parts.append(f'<ellipse cx="72" cy="436" rx="44" ry="11" fill="#4CAF50" stroke="{I}" stroke-width="3"/>'
                     f'<g class="isle-friend" data-friend="frog" transform="translate(42 376) scale(.74)"><title>{labels.get("frog", FRIEND_NAMES["frog"])}</title>{art.frog()}{_zzz(66, 12) if asleep else ""}</g>')
    if home and not fled and "crab" in friends:
        parts.append(f'<g class="isle-friend" data-friend="crab" transform="translate(700 400) scale(.74)"><title>{labels.get("crab", FRIEND_NAMES["crab"])}</title>{art.crab()}{_zzz(66, 12) if asleep else ""}</g>')
    parts.append("</g>")
    if season_now and fog < 2:
        parts.append(art.season_bits(season_now))
    if fog:
        op = {1: .28, 2: .5, 3: .62}[fog]
        parts.append(f'<g class="isle-fog" opacity="{op}">'
                     '<ellipse cx="140" cy="250" rx="260" ry="70" fill="#E9ECEF"/><ellipse cx="620" cy="200" rx="280" ry="80" fill="#E9ECEF"/>'
                     '<ellipse cx="380" cy="380" rx="420" ry="70" fill="#F1F3F5"/><ellipse cx="420" cy="110" rx="300" ry="60" fill="#F1F3F5"/></g>')
    if villain >= 4:  # on the island, arms around your plants
        parts.append('<rect width="800" height="470" fill="#1B2030" opacity=".22"/>')
        parts.append(villain_at(170, 20, 1.3, "attack"))
    parts.append("</svg>")
    return "".join(parts)


def sea_chart(fleet: list[dict], others: list[dict], story_pos: float, labels: dict | None = None) -> str:
    """The way to the Far Shore: your turtles and your friends' turtles on one route.
    Tempo goes by the story; a course's turtle goes by how much of the course is done."""
    labels = labels or {}
    I = art.INK
    W, H = 800, 220
    parts = [f'<svg class="sea-chart" viewBox="0 0 {W} {H}" role="img" aria-label="{labels.get("chart", "The way to the Far Shore")}">',
             f'<rect width="{W}" height="{H}" fill="#CDE8F2"/>',
             f'<path d="M40 150 C180 70 300 190 430 120 S650 60 760 100" fill="none" stroke="#fff" stroke-width="10" stroke-linecap="round" stroke-dasharray="2 18"/>']
    # landmarks: the bay, the lighthouse, the heart of the fog, the far shore
    parts.append(f'<path d="M14 170 q20 -30 50 -6 q14 -18 36 0 v40 h-86 z" fill="#E7D3A1" stroke="{I}" stroke-width="3" stroke-linejoin="round"/>')
    parts.append(f'<g transform="translate(330 70)"><rect x="-9" y="0" width="18" height="52" fill="#fff" stroke="{I}" stroke-width="3"/>'
                 f'<rect x="-9" y="14" width="18" height="10" fill="#E6007E"/><path d="M-13 0 h26 l-13 -14 z" fill="#FFD43B" stroke="{I}" stroke-width="3" stroke-linejoin="round"/>'
                 f'<path d="M14 -6 l40 -12 M14 -2 l40 8" stroke="#FFD43B" stroke-width="4" stroke-linecap="round"/></g>')
    parts.append('<g opacity=".7"><ellipse cx="560" cy="110" rx="60" ry="26" fill="#9AA3AD"/><ellipse cx="590" cy="96" rx="40" ry="18" fill="#B8BEC5"/></g>')
    parts.append(f'<g transform="translate(730 40)"><rect x="-10" y="20" width="60" height="44" fill="#F2EDE2" stroke="{I}" stroke-width="3"/>'
                 f'<path d="M-16 20 h72 l-36 -22 z" fill="#3D8FD1" stroke="{I}" stroke-width="3" stroke-linejoin="round"/>'
                 f'<path d="M2 64 v-24 M20 64 v-24 M38 64 v-24" stroke="{I}" stroke-width="3"/></g>')

    def at(f: float):
        # a point along the route, f in 0..1
        f = min(max(f, 0), 1)
        x = 40 + 720 * f
        y = 150 - 60 * __import__("math").sin(f * 3.4) + 20 * f
        return x, y

    def little(x, y, palette, name, scale=.34, ring=False):
        body = recolor(str(tempo.mascot("happy", 80)).replace('class="tempo tempo-happy"', 'class="chart-turtle"'), palette)
        body = body.replace('width="80" height="57"', f'x="{x - 40 * scale * 2.6:.0f}" y="{y - 30 * scale * 2.6:.0f}" width="{80 * scale * 2.6:.0f}" height="{57 * scale * 2.6:.0f}"')
        label = (f'<text x="{x:.0f}" y="{y + 30:.0f}" text-anchor="middle" font-size="13" font-weight="700" '
                 f'font-family="system-ui,sans-serif" fill="#111" stroke="#fff" stroke-width="3" paint-order="stroke">{name}</text>')
        return body + label

    for i, o in enumerate(others):
        x, y = at(o["pos"])
        parts.append(f'<g class="chart-other" opacity=".9">{little(x, y + 14 + 6 * (i % 2), o["palette"], o["name"], .26)}</g>')
    for t in fleet:
        pos = story_pos if t["tempo"] else (t["percent"] or 0) / 100
        x, y = at(pos)
        parts.append(f'<g class="chart-mine">{little(x, y - 6, t["palette"], t["name"])}</g>')
    parts.append("</svg>")
    return "".join(parts)


def voyage_chart(st: dict, labels: dict | None = None, compact: bool = False) -> str:
    """Voyage mode (v1.24): a roadmap as a sea route. Each course is a little island port, numbered in order.
    Finished ports have a lit lighthouse, Tempo sails his boat next to the port you're on, optional ports are
    smaller, and the route ends at the harbour, whose chest opens when the whole roadmap is done."""
    labels = labels or {}
    I = art.INK
    steps = st["steps"]
    n = max(1, len(steps))
    W = max(560, 140 + 115 * n)  # about the same space for each port, so long roadmaps scroll instead of shrinking
    H = 200 if compact else 240
    top, bottom = 58, H - 52
    # on a phone the chart keeps a readable size (about 70 px a port) and scrolls sideways
    parts = [f'<div class="voyage-scroll"><svg class="voyage-chart" style="--vw:{round(W * 0.62)}px;--vmax:{W}px" viewBox="0 0 {W} {H}" role="img" aria-label="{labels.get("chart", "Voyage")}">',
             f'<rect width="{W}" height="{H}" fill="#CDE8F2"/>']
    for x in range(30, W, 120):  # little waves
        parts.append(f'<path d="M{x} {H - 18} q10 -6 20 0 q10 -6 20 0" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" opacity=".7"/>')
    left, right = 110, W - 120

    def at(i: int):
        f = i / (n - 1) if n > 1 else 0.5
        x = left + (right - left) * f
        y = (top + bottom) / 2 + ((bottom - top) / 2 - 6) * math.sin(f * math.pi * (2 if n > 4 else 1) + 0.4)
        return x, y

    pts = [at(i) for i in range(n)] + [(W - 54, (top + bottom) / 2)]
    d = f"M{pts[0][0]:.0f} {pts[0][1]:.0f}" + "".join(
        f" Q{(a[0] + b[0]) / 2:.0f} {(a[1] + b[1]) / 2 + (14 if k % 2 else -14):.0f} {b[0]:.0f} {b[1]:.0f}"
        for k, (a, b) in enumerate(zip(pts, pts[1:])))
    parts.append(f'<path d="{d}" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-dasharray="2 14"/>')
    scale = 1.0
    here = st.get("current")
    for i, s in enumerate(steps):
        x, y = pts[i]
        k = scale * (0.75 if s.get("optional") else 1.0)
        done = s["state"] == "done"
        land = "#6CBF4A" if done else "#E7D3A1"
        dash = ' stroke-dasharray="5 4"' if s.get("optional") else ""
        title = str(s.get("title", "")).replace("&", "&amp;").replace("<", "&lt;")
        g = [f'<g class="port port-{s["state"]}" transform="translate({x:.0f} {y:.0f}) scale({k:.2f})"><title>{s["n"]}. {title}</title>',
             f'<ellipse cx="0" cy="10" rx="34" ry="13" fill="{land}" stroke="{I}" stroke-width="3"{dash}/>',
             f'<ellipse cx="-6" cy="6" rx="14" ry="5" fill="#fff" opacity=".35"/>']
        if done:  # a lit lighthouse
            g.append(f'<rect x="-6" y="-26" width="12" height="32" fill="#fff" stroke="{I}" stroke-width="2.6"/>'
                     f'<rect x="-6" y="-16" width="12" height="7" fill="#E6007E"/>'
                     f'<path d="M-9 -26 h18 l-9 -10 z" fill="#FFD43B" stroke="{I}" stroke-width="2.6" stroke-linejoin="round"/>'
                     f'<path d="M10 -32 l22 -8 M10 -28 l22 4" stroke="#FFD43B" stroke-width="3.4" stroke-linecap="round"/>')
        elif s["percent"]:  # a flag that rises with your progress
            h = 8 + 22 * s["percent"] / 100
            g.append(f'<path d="M-10 6 V-30" stroke="{I}" stroke-width="2.6"/>'
                     f'<path d="M-10 {-30 + (30 - h):.0f} h18 l-5 5 l5 5 h-18 z" fill="#FFD43B" stroke="{I}" stroke-width="2.2" stroke-linejoin="round"/>')
        else:
            g.append(f'<path d="M-4 6 q-2 -16 8 -22 M4 -16 q-12 -2 -16 4 M4 -16 q10 -6 16 0" fill="none" stroke="#3E8E2E" stroke-width="3" stroke-linecap="round"/>')
        g.append(f'<circle cx="0" cy="28" r="12" fill="{"#1F9D6A" if done else "#FFD43B" if s is here else "#fff"}" stroke="{I}" stroke-width="2.6"/>'
                 f'<text x="0" y="33" text-anchor="middle" font-size="14" font-weight="800" font-family="system-ui,sans-serif" '
                 f'fill="{"#fff" if done else "#111"}">{s["n"]}</text></g>')
        parts.append("".join(g))
    # the harbour at the end
    hx, hy = pts[-1]
    chest_open = st.get("finished")
    parts.append(f'<g class="harbour" transform="translate({hx:.0f} {hy:.0f})"><title>{labels.get("harbour", "Harbour")}</title>'
                 f'<path d="M-40 18 q10 -16 40 -14 q30 -2 40 14 z" fill="#E7D3A1" stroke="{I}" stroke-width="3"/>'
                 f'<rect x="-22" y="-20" width="30" height="26" fill="#F2EDE2" stroke="{I}" stroke-width="3"/>'
                 f'<path d="M-27 -20 h40 l-20 -16 z" fill="#3D8FD1" stroke="{I}" stroke-width="3" stroke-linejoin="round"/>'
                 f'<rect x="12" y="{-6 if chest_open else -2}" width="20" height="{14 if chest_open else 10}" fill="#B5651D" stroke="{I}" stroke-width="2.6"/>'
                 + (f'<path d="M12 -6 l4 -12 h16 l-4 12 z" fill="#B5651D" stroke="{I}" stroke-width="2.6"/><circle cx="22" cy="-8" r="4" fill="#FFD43B"/>'
                    f'<path d="M22 -20 v-6 M14 -18 l-4 -5 M30 -18 l4 -5" stroke="#FFD43B" stroke-width="2.6" stroke-linecap="round"/>'
                    if chest_open else f'<path d="M12 -2 h20 v-5 q-10 -6 -20 0 z" fill="#8B4A12" stroke="{I}" stroke-width="2.6"/>')
                 + '</g>')
    # Tempo in his boat, next to the port you're on (at the harbour when it's all done)
    if here is not None or chest_open:
        bx, by = (pts[-1][0] - 44, pts[-1][1] + 34) if chest_open else (pts[here["n"] - 1][0] - 30 * scale - 28, pts[here["n"] - 1][1] - 6)
        body = str(tempo.mascot("happy" if chest_open else "wave", 80)).replace('class="tempo', 'class="voyage-tempo tempo')
        body = body.replace('width="80" height="57"', f'x="{bx - 26:.0f}" y="{by - 42:.0f}" width="52" height="37"', 1)
        parts.append(f'<g class="voyage-boat"><title>{labels.get("you", "You are here")}</title>'
                     f'<path d="M{bx - 30:.0f} {by - 6:.0f} h60 l-10 16 h-40 z" fill="#B5651D" stroke="{I}" stroke-width="3" stroke-linejoin="round"/>'
                     f'<path d="M{bx + 8:.0f} {by - 6:.0f} V{by - 52:.0f}" stroke="{I}" stroke-width="2.6"/>'
                     f'<path d="M{bx + 10:.0f} {by - 50:.0f} q18 14 0 30 z" fill="#fff" stroke="{I}" stroke-width="2.6" stroke-linejoin="round"/>'
                     f'{body}</g>')
    parts.append("</svg></div>")
    return "".join(parts)


TRIP_STAGES = (0.05, 0.25, 0.42, 0.6, 0.8, 1.0)


def stage_for(progress: float) -> float:
    """The drawing to show for how far a trip is (0..1)."""
    return max([g for g in TRIP_STAGES if g <= max(progress, 0.05) + 1e-9])


def trip_svg(kind: str, growth: float, mood: str = "read", label: str = "Tempo swims while your plant grows",
             stages: bool = False, sky: dict | None = None) -> str:
    """The focus screen: Tempo swimming with your plant growing on his shell.
    With stages=True every stage is drawn and the page shows the one that fits the time."""
    uid = f"trip{int(time.time() * 1000) % 100000}"
    sc = 0.8
    pos = f'translate({88 - 60 * sc:.1f} {30 - 150 * sc:.1f}) scale({sc})'
    if stages:
        cur = stage_for(growth)
        g = "".join(f'<g class="trip-stage" data-g="{st}" transform="{pos}"{"" if st == cur else " hidden"}>{art.plant(kind, st)}</g>'
                    for st in TRIP_STAGES)
    else:
        g = f'<g transform="{pos}">{art.plant(kind, growth)}</g>'
    wave = "M-60 112"
    for _ in range(9):
        wave += " q20 -8 40 0"
    back = ""
    if sky:  # the real sky behind Tempo: the same sun, moon and stars as the island
        back = (f'<defs><linearGradient id="{uid}-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{sky["top"]}"/>'
                f'<stop offset="1" stop-color="{sky["low"]}"/></linearGradient></defs>'
                f'<rect x="-40" y="-112" width="290" height="256" fill="url(#{uid}-sky)"/>')
        if sky["stars"]:
            back += (f'<g opacity="{sky["stars"]}">' + "".join(f'<circle cx="{x}" cy="{y}" r="1.4" fill="#fff"/>' for x, y in
                     ((-20, -90), (30, -70), (80, -100), (140, -80), (200, -96), (230, -60), (-10, -40), (170, -40))) + '</g>')
        b = sky["body"]
        bx, by = -40 + b["x"] / 800 * 290, -112 + b["y"] / 470 * 200
        if b["kind"] == "sun":
            back += f'<circle cx="{bx:.0f}" cy="{by:.0f}" r="15" fill="{b["color"]}" stroke="{art.INK}" stroke-width="2.4"/>'
        else:
            back += f'<path d="M{bx:.0f} {by - 12:.0f} a13 13 0 1 0 10 22 a10 10 0 1 1 -10 -22 z" fill="{b["color"]}" stroke="{art.INK}" stroke-width="2.4"/>'
    return (f'<svg class="trip-art" viewBox="-40 -112 290 256" role="img" aria-label="{label}">{back}'
            f'<g class="trip-tempo">{tempo._tail()}{tempo._neck()}{tempo._rim()}{tempo._shell(uid)}{g}{tempo.scarf()}{tempo.head(mood)}'
            f'<path d="M150 104 q22 2 34 14 q-20 8 -38 -4 z" fill="{tempo.SKIN}" stroke="{art.INK}" stroke-width="3" stroke-linejoin="round"/></g>'
            f'<g class="trip-water"><path d="{wave} V140 H-60 Z" fill="#5BB7E0" stroke="{art.INK}" stroke-width="3" stroke-linejoin="round"/>'
            '<path d="M-20 126 q16 -6 32 0 M120 130 q16 -6 32 0" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" opacity=".8"/></g>'
            '</svg>')
