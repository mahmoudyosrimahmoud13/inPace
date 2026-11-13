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
import time
import uuid
from datetime import date, datetime, timedelta

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
]

PLANT_NAMES = {k: n for k, n, _ in PLANTS}
FRIEND_NAMES = {k: n for k, n, _, _ in FRIENDS}


def setup(v: Vault) -> None:
    v.db.execute("CREATE TABLE IF NOT EXISTS garden (id TEXT PRIMARY KEY, kind TEXT, goal INTEGER, banked REAL DEFAULT 0, "
                 "run_from REAL, mode TEXT, journey TEXT, state TEXT, started REAL, ended REAL)")
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
        v.db.execute("UPDATE garden SET state='grown', banked=?, run_from=NULL, ended=? WHERE id=?",
                     (trip["goal"] * 60, time.time() if now is None else now, trip["id"]))
        v.db.commit()
        return {**trip, "state": "grown"}
    return None


def grown(v: Vault) -> list[dict]:
    setup(v)
    return [dict(r) for r in v.db.execute("SELECT * FROM garden WHERE state='grown' ORDER BY ended")]


def last_grown(v: Vault) -> dict | None:
    setup(v)
    return _row(v.db.execute("SELECT * FROM garden WHERE state='grown' ORDER BY ended DESC LIMIT 1").fetchone())


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


def stats(v: Vault, today: date | None = None) -> dict:
    setup(v)
    today = today or date.today()
    plants = grown(v)
    days = {_day(p["ended"]) for p in plants if p["ended"]}
    hours = [datetime.fromtimestamp(p["started"]).hour for p in plants if p["started"]]
    q = lambda sql: v.db.execute(sql).fetchone()[0] or 0
    modules = courses = 0
    for j in v.journeys():
        try:
            prog = v.progress(j["id"])
        except Exception:
            continue
        modules += prog.get("modules_done", 0)
        courses += 1 if prog.get("finished") else 0
    focus_min = sum(p["goal"] for p in plants)
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    return {
        "plants": len(plants), "focus_min": focus_min, "hours": focus_min // 60,
        "longest": max((p["goal"] for p in plants), default=0),
        "days": len(days), "streak": _streak(days, today),
        "morning": sum(1 for h in hours if 4 <= h < 8), "night": sum(1 for h in hours if h >= 21 or h < 4),
        "week_min": sum(p["goal"] for p in plants if p["ended"] and _day(p["ended"]) > today - timedelta(days=7)),
        "lessons": q("SELECT COUNT(DISTINCT journey || data) FROM events WHERE type='lesson_done'"),
        "reviews": q("SELECT COUNT(*) FROM events WHERE type='review_done'"),
        "milestones": q("SELECT COUNT(*) FROM milestones"),
        "approved": q("SELECT COUNT(*) FROM approvals WHERE decision='approved'"),
        "races": q("SELECT COUNT(*) FROM races"),
        "modules": modules, "courses": courses,
        "blooming": bool(v.db.execute("SELECT 1 FROM approvals WHERE decision='approved' AND at >= ? LIMIT 1",
                                      (week_ago[:10],)).fetchone()),
    }


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
    """Clear, mist, fog or lost: how long since you last studied. Never a punishment, just the sea."""
    now = time.time() if now is None else now
    last = last_active(v)
    days = int((now - last) // 86400) if last else 0
    fog = 0 if days < 2 else 1 if days < 4 else 2 if days < 7 else 3
    return {"days": days, "fog": fog, "fair": goal_met and fog == 0}


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
TURTLE_NAMES = {
    "universal": ["Pip", "Juno", "Basil", "Marlo", "Nova", "Sage", "Otto", "Wren", "Clover", "Bo"],
    "arab": ["Shams", "Nour", "Ziad", "Farida", "Karam", "Lulu", "Adham", "Yasmin", "Fares", "Hala"],
}
TURTLE_NAMES_AR = {
    "universal": ["بيب", "جونو", "بازل", "مارلو", "نوفا", "سيج", "أوتو", "رين", "كلوفر", "بو"],
    "arab": ["شمس", "نور", "زياد", "فريدة", "كرم", "لولو", "أدهم", "ياسمين", "فارس", "هالة"],
}


def _pick(seed: str, n: int) -> int:
    return sum(ord(c) * (i + 1) for i, c in enumerate(seed)) % n


def turtles(v: Vault, world: str, lang: str) -> list[dict]:
    """Your fleet: Tempo carries trips that aren't for a course; each course has its own turtle and island."""
    names = json.loads(v._meta("island_names", "{}") or "{}")
    plants = grown(v)
    out = [{"id": "", "name": "Tempo" if lang != "ar" else "تمبو", "palette": PALETTES[0], "course": "",
            "plants": [p for p in plants if not p.get("journey")], "percent": None, "tempo": True}]
    pool = (TURTLE_NAMES_AR if lang == "ar" else TURTLE_NAMES)[world]
    for j in v.journeys():
        c = v.get_course(j["course_id"])
        if not c:
            continue
        try:
            pct = v.progress(j["id"])["percent"]
        except Exception:
            pct = 0
        out.append({"id": j["id"], "name": names.get(j["id"]) or pool[_pick(j["id"], len(pool))],
                    "palette": PALETTES[1 + _pick(j["id"] + "p", len(PALETTES) - 1)], "course": c.title,
                    "plants": [p for p in plants if p.get("journey") == j["id"]], "percent": pct, "tempo": False})
    return out


def rename(v: Vault, jid: str, name: str) -> None:
    names = json.loads(v._meta("island_names", "{}") or "{}")
    name = " ".join(name.split())[:24]
    if name:
        names[jid] = name
    else:
        names.pop(jid, None)
    v._set_meta("island_names", json.dumps(names))


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


def _sky(hour: int) -> tuple[str, str, bool]:
    if 5 <= hour < 8:
        return "#FFD9A8", "#CDE8F2", False
    if 8 <= hour < 17:
        return "#9FD3F0", "#E4F4FB", False
    if 17 <= hour < 20:
        return "#FF9E7A", "#FFD9A8", False
    return "#16213E", "#33456E", True


def _cloud(x: float, y: float, s: float) -> str:
    return (f'<g transform="translate({x} {y}) scale({s})">'
            '<path d="M0 30 Q-4 12 14 12 Q18 -6 40 2 Q56 -8 66 12 Q86 10 84 30 Z" fill="#fff" stroke="#111" stroke-width="3" stroke-linejoin="round"/></g>')


def _zzz(x: float, y: float) -> str:
    z = 'font-family="system-ui,sans-serif" font-weight="900" fill="#fff" stroke="#111" stroke-width="2" paint-order="stroke"'
    return f'<text x="{x}" y="{y}" font-size="18" {z}>z</text><text x="{x + 12}" y="{y - 12}" font-size="13" {z}>z</text>'


def island_svg(plants: list[dict], friends: set[str], ring: int, blooming: bool = False, hour: int | None = None,
               labels: dict | None = None, palette=None, fog: int = 0, fair: bool = False, home: bool = True) -> str:
    """The whole island scene: sky, sea, a turtle, the newest plants on its shell, and your friends.
    fog 0..3 greys it out and puts the friends to sleep (never hurts anything); fair adds a rainbow."""
    labels = labels or {}
    palette = palette or PALETTES[0]
    hour = datetime.now().hour if hour is None else hour
    top, low, night = _sky(hour)
    if fog >= 2:
        top, low = "#9AA3AD", "#C9CED3"
    I = art.INK
    asleep = fog >= 2
    u = f"i{next(tempo._ids)}"  # ids must be unique if two islands share a page
    parts = [f'<svg class="island-art fog-{fog}" viewBox="0 0 800 470" role="img" aria-label="{labels.get("island", "Tempo carries your island")}">',
             f'<defs><linearGradient id="{u}-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
             f'<stop offset="1" stop-color="{low}"/></linearGradient>'
             f'<clipPath id="{u}-dome"><path d="M110 372 C106 236 230 150 380 150 C530 150 654 236 650 372 Z"/></clipPath>'
             f'<filter id="{u}-grey"><feColorMatrix type="saturate" values="{1 if fog == 0 else .6 if fog == 1 else .22}"/></filter></defs>',
             f'<rect width="800" height="470" fill="url(#{u}-sky)"/>']
    if night and fog < 2:
        for x, y, r in ((60, 40, 2), (150, 90, 1.6), (240, 30, 2.2), (520, 50, 1.8), (600, 110, 1.4), (720, 30, 2), (430, 90, 1.5), (330, 60, 1.4)):
            parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" opacity=".9"/>')
        parts.append(f'<path d="M690 52 a30 30 0 1 0 22 50 a24 24 0 1 1 -22 -50 z" fill="#FFF3B0" stroke="{I}" stroke-width="3"/>')
    elif fog < 2:
        parts.append(f'<circle cx="690" cy="78" r="34" fill="#FFD43B" stroke="{I}" stroke-width="3"/>'
                     f'<circle cx="680" cy="68" r="10" fill="#fff" opacity=".45"/>')
        parts.append(_cloud(90, 60, 1) + _cloud(470, 40, .8))
    if fair and fog == 0:
        for k, c in enumerate(("#E6007E", "#FF9F1C", "#FFD43B", "#4CAF50", "#3D8FD1", "#8E5CC2")):
            r = 330 - k * 12
            parts.append(f'<path d="M{380 - r} 330 A{r} {r} 0 0 1 {380 + r} 330" fill="none" stroke="{c}" stroke-width="12" opacity=".75"/>')
    parts.append(f'<g filter="url(#{u}-grey)">')
    parts.append(f'<rect x="0" y="330" width="800" height="140" fill="#4DA8D6"/>'
                 f'<path d="M0 330 H800" stroke="{I}" stroke-width="3"/>'
                 '<path d="M40 350 q20 -8 40 0 M520 346 q20 -8 40 0 M700 356 q16 -6 32 0" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".7"/>')
    # the turtle: head and neck behind the shell's edge, then the shell
    s = 2.4
    mood = "sleepy" if asleep else ("think" if fog == 1 else "cheer" if (fair or blooming) else "happy")
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
    parts.append(f'<ellipse cx="380" cy="150" rx="320" ry="96" fill="#6CBF4A"/>'
                 f'<path d="M60 222 Q120 250 180 232 Q240 262 300 240 Q360 268 420 242 Q480 266 540 240 Q600 258 660 230 Q700 220 720 210" '
                 f'fill="none" stroke="#3E8E2E" stroke-width="5" stroke-linecap="round"/>'
                 '<path d="M170 196 q30 -30 70 -36" fill="none" stroke="#B8E58F" stroke-width="7" stroke-linecap="round" opacity=".8"/>'
                 '</g>'
                 f'<path d="M110 372 C106 236 230 150 380 150 C530 150 654 236 650 372 Z" fill="none" stroke="{I}" stroke-width="4" stroke-linejoin="round"/>')
    for gx in (200, 280, 470, 560):
        gy = dome_y(gx)
        parts.append(f'<path d="M{gx - 8} {gy + 2} l3 -10 l3 8 l3 -12 l3 12 l3 -8 l3 10" fill="none" stroke="#2E7D3B" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')
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
            bloom = blooming or p["goal"] >= 60
            parts.append(f'<g class="isle-plant" transform="translate({x - 60 * sc:.1f} {y - 150 * sc:.1f}) scale({sc:.3f})">'
                         f'<title>{labels.get("plant_" + p["kind"], PLANT_NAMES.get(p["kind"], ""))}</title>{art.plant(p["kind"], 1, bloom)}</g>')
    if home:
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
        for key, (fx, fy, fs) in {"sparrow": (250, 66, .74), "butterfly": (556, 118, .56), "bee": (470, 160, .5)}.items():
            if key in friends:
                if asleep:  # in the fog the flyers sit down and nap
                    fx, fy = {"sparrow": (300, dome_y(300) - 6), "butterfly": (520, dome_y(520) - 4), "bee": (440, dome_y(440) - 2)}[key]
                parts.append(friend(key, f"translate({fx - 40 * fs:.1f} {fy - 40 * fs:.1f}) scale({fs})"))
    if blooming and fog == 0:
        for x, y in ((150, 140), (620, 170), (330, 110), (430, 96), (250, 200)):
            parts.append(art._flower5(x, y, 4, "#F8BBD0", "#FFD43B"))
    wave = "M0 382"
    for _ in range(20):
        wave += " q20 -10 40 0"
    parts.append(f'<path d="{wave} V470 H0 Z" fill="#5BB7E0" stroke="{I}" stroke-width="3" stroke-linejoin="round"/>'
                 '<path d="M80 414 q24 -10 48 0 M300 432 q24 -10 48 0 M600 420 q24 -10 48 0" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".75"/>')
    if home and "frog" in friends:
        parts.append(f'<ellipse cx="72" cy="436" rx="44" ry="11" fill="#4CAF50" stroke="{I}" stroke-width="3"/>'
                     f'<g class="isle-friend" data-friend="frog" transform="translate(42 376) scale(.74)"><title>{labels.get("frog", FRIEND_NAMES["frog"])}</title>{art.frog()}{_zzz(66, 12) if asleep else ""}</g>')
    if home and "crab" in friends:
        parts.append(f'<g class="isle-friend" data-friend="crab" transform="translate(700 400) scale(.74)"><title>{labels.get("crab", FRIEND_NAMES["crab"])}</title>{art.crab()}{_zzz(66, 12) if asleep else ""}</g>')
    parts.append("</g>")
    if fog:
        op = {1: .28, 2: .5, 3: .62}[fog]
        parts.append(f'<g class="isle-fog" opacity="{op}">'
                     '<ellipse cx="140" cy="250" rx="260" ry="70" fill="#E9ECEF"/><ellipse cx="620" cy="200" rx="280" ry="80" fill="#E9ECEF"/>'
                     '<ellipse cx="380" cy="380" rx="420" ry="70" fill="#F1F3F5"/><ellipse cx="420" cy="110" rx="300" ry="60" fill="#F1F3F5"/></g>')
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


TRIP_STAGES = (0.05, 0.25, 0.42, 0.6, 0.8, 1.0)


def stage_for(progress: float) -> float:
    """The drawing to show for how far a trip is (0..1)."""
    return max([g for g in TRIP_STAGES if g <= max(progress, 0.05) + 1e-9])


def trip_svg(kind: str, growth: float, mood: str = "read", label: str = "Tempo swims while your plant grows",
             stages: bool = False) -> str:
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
    return (f'<svg class="trip-art" viewBox="-40 -112 290 256" role="img" aria-label="{label}">'
            f'<g class="trip-tempo">{tempo._tail()}{tempo._neck()}{tempo._rim()}{tempo._shell(uid)}{g}{tempo.scarf()}{tempo.head(mood)}'
            f'<path d="M150 104 q22 2 34 14 q-20 8 -38 -4 z" fill="{tempo.SKIN}" stroke="{art.INK}" stroke-width="3" stroke-linejoin="round"/></g>'
            f'<g class="trip-water"><path d="{wave} V140 H-60 Z" fill="#5BB7E0" stroke="{art.INK}" stroke-width="3" stroke-linejoin="round"/>'
            '<path d="M-20 126 q16 -6 32 0 M120 130 q16 -6 32 0" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" opacity=".8"/></g>'
            '</svg>')
