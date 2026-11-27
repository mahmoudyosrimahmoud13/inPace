"""Roadmaps (v1.24): a path through several existing courses, in order, toward one goal.

A roadmap holds no lessons of its own. It's a short list of course ids with a note for each step ("start here
because…"), so it stays tiny: it can travel in a link, and the library can list many of them.

    id: data-analyst
    title: Become a data analyst
    description: From spreadsheets to dashboards and Python, in the order that makes sense.
    language: en
    author: Mahmoud
    tags: [data, career]
    steps:
      - course: excel-tutorial-for-data-analysts
        note: Start with spreadsheets. Everything else builds on them.
      - course: data-analytics-beginners
      - course: python-basics
        optional: true

Where they live:
- Roadmaps you made or follow: <data folder>/roadmaps/<id>.json (with "source": mine, library or link).
- Library roadmaps: the "roadmaps" list in the library's library.json (older libraries simply have none).

A step is finished when its course is finished. Optional steps never hold the roadmap back.

Sprints (v1.33): a roadmap can also be a short, intensive plan with a day for each step.

    sprint: {days: 7, hours: 12}      # how many days, and about how many hours a day
    steps:
      - course: fastapi
        day: 2                        # or "4-5" for a step that runs over two days
        tasks:                        # the parts of the course to do in the sprint (optional)
          - Modules 1-6, fast
          - The final project, on PostgreSQL

Any roadmap you follow can be run as a sprint: inPace spreads its courses over the days you choose (by their
length) when the roadmap doesn't say. Your run lives with your copy of the roadmap ("sprint_run": the start day,
the plan and the tasks you ticked), so a library update never loses it. In a sprint a step counts as done when you
tick all its tasks, or when you finish its course.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
COURSE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
MAX_STEPS = 30
MAX_SPRINT_DAYS = 60
MAX_TASKS = 12
MAX_LOG = 600
SOURCES = ("mine", "library", "link")


class RoadmapError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def slug(text: str) -> str:
    """An id from a title: lower case letters, digits and dashes (Arabic titles get a short code instead)."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:48].strip("-")
    if len(t) < 3:
        t = "roadmap-" + hashlib.sha256((text or str(time.time())).encode("utf-8")).hexdigest()[:8]
    return t


def _text(v, limit: int) -> str:
    return re.sub(r"[ \t]+", " ", str(v or "")).strip()[:limit]


def day_range(v, days: int = MAX_SPRINT_DAYS) -> tuple[int, int] | None:
    """A step's day: 3, "3", "4-5", [4, 5] -> (from, to), or None."""
    if v is None or v == "" or isinstance(v, bool):
        return None
    if isinstance(v, (list, tuple)) and v:
        a, b = v[0], v[-1]
    elif isinstance(v, int):
        a = b = v
    else:
        m = re.match(r"^\s*(\d{1,2})\s*(?:[-\u2013to ]+\s*(\d{1,2}))?\s*$", str(v))
        if not m:
            return None
        a, b = m.group(1), m.group(2) or m.group(1)
    try:
        a, b = int(a), int(b)
    except (TypeError, ValueError):
        return None
    if a < 1 or b < a or b > days:
        return None
    return a, b


def _sprint(v) -> dict | None:
    """The roadmap's sprint settings: {"days": 1-60, "hours": 0-16} (hours may be 0: not said)."""
    if isinstance(v, (int, str)) and not isinstance(v, bool):
        v = {"days": v}
    if not isinstance(v, dict):
        return None
    try:
        days = int(v.get("days") or 0)
    except (TypeError, ValueError):
        return None
    if not 1 <= days <= MAX_SPRINT_DAYS:
        return None
    try:
        hours = float(v.get("hours") or 0)
    except (TypeError, ValueError):
        hours = 0
    hours = max(0.0, min(16.0, hours))
    return {"days": days, "hours": int(hours) if hours == int(hours) else round(hours, 1)}


def _run(v, course_ids: set[str]) -> dict | None:
    """Your sprint run, cleaned: start date, days, hours, the plan (course -> [from, to]) and your ticks."""
    if not isinstance(v, dict) or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(v.get("start") or "")):
        return None
    sp = _sprint(v)
    if not sp:
        return None
    plan, ticks = {}, {}
    for cid, d in (v.get("plan") or {}).items() if isinstance(v.get("plan"), dict) else []:
        r = day_range(d, sp["days"])
        if cid in course_ids and r:
            plan[cid] = list(r)
    for cid, t in (v.get("ticks") or {}).items() if isinstance(v.get("ticks"), dict) else []:
        if cid in course_ids and isinstance(t, list):
            got = sorted({int(x) for x in t if isinstance(x, int) and not isinstance(x, bool) and 0 <= x < MAX_TASKS})
            if got:
                ticks[cid] = got
    tasks = {}  # your own tasks for a step, instead of the roadmap's
    for cid, t in (v.get("tasks") or {}).items() if isinstance(v.get("tasks"), dict) else []:
        if cid in course_ids and isinstance(t, list):
            t = [x for x in (_text(y, 200) for y in t if isinstance(y, str)) if x][:MAX_TASKS]
            tasks[cid] = t
    log = []  # when you ticked or unticked each task: [time, course, task, 1 or 0]
    for e in v.get("log") or [] if isinstance(v.get("log"), list) else []:
        if (isinstance(e, list) and len(e) == 4 and isinstance(e[0], str) and e[1] in course_ids
                and isinstance(e[2], int) and e[3] in (0, 1)):
            log.append([e[0][:19], e[1], e[2], e[3]])
    out = {"start": str(v["start"]), **sp, "plan": plan, "ticks": ticks}
    try:
        hour = int(v.get("hour") or 0)
    except (TypeError, ValueError):
        hour = 0
    if 0 < hour < 24:  # a sprint day starts at this hour (a 4 pm start runs 4 pm to 4 pm)
        out["hour"] = hour
    try:
        end = int(v["end"]) if v.get("end") not in (None, "") else None
    except (TypeError, ValueError):
        end = None
    if end is not None and 0 <= end < 24:  # each day's window ends at this hour (the countdown strip)
        out["end"] = end
    rh = v.get("rhythm")  # the timer's blocks: [focus minutes, break minutes]
    if isinstance(rh, (list, tuple)) and len(rh) == 2:
        try:
            f, b = int(rh[0]), int(rh[1])
            if 10 <= f <= 120 and 3 <= b <= 30:
                out["rhythm"] = [f, b]
        except (TypeError, ValueError):
            pass
    if tasks:
        out["tasks"] = tasks
    if log:
        out["log"] = log[-MAX_LOG:]
    return out


def parse(data, source: str = "mine") -> dict:
    """Check a roadmap (a dict, or YAML/JSON text) and return it cleaned up. Raises RoadmapError."""
    if isinstance(data, (str, bytes)):
        import yaml
        try:
            data = yaml.safe_load(data)
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            where = f" (line {mark.line + 1})" if mark else ""
            raise RoadmapError([f"This isn't a roadmap: the text couldn't be read{where}. A note with a colon in it "
                                "needs quotes around it."])
    if not isinstance(data, dict):
        raise RoadmapError(["This isn't a roadmap."])
    problems = []
    title = _text(data.get("title"), 120)
    rid = str(data.get("id") or "").strip().lower() or slug(title)
    if not title:
        problems.append("Give the roadmap a title.")
    if not ID_RE.match(rid):
        problems.append("The roadmap's id can only have small letters, digits and dashes (3 to 63 of them).")
    author = data.get("author")
    author = _text(author.get("name") if isinstance(author, dict) else author, 80)
    lang = str(data.get("language") or "en").strip().lower()[:5]
    if not re.match(r"^[a-z]{2}(-[a-z]{2})?$", lang):
        lang = "en"
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = tags.split(",")
    tags = [t for t in (_text(x, 30).lower() for x in tags if isinstance(x, (str, int))) if t][:8]
    sprint = _sprint(data.get("sprint"))
    steps, seen = [], set()
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        problems.append("Add at least one course to the roadmap.")
        raw_steps = []
    for i, s in enumerate(raw_steps, 1):
        if isinstance(s, str):
            s = {"course": s}
        if not isinstance(s, dict):
            problems.append(f"Step {i} isn't a course.")
            continue
        cid = str(s.get("course") or "").strip()
        if not COURSE_RE.match(cid):
            problems.append(f"Step {i} needs a course id.")
            continue
        if cid in seen:
            problems.append(f"The course “{cid}” is on the roadmap twice.")
            continue
        seen.add(cid)
        step = {"course": cid, "note": _text(s.get("note"), 400)}
        if s.get("optional") is True or str(s.get("optional") or "").strip().lower() in ("true", "yes", "1"):
            step["optional"] = True
        if s.get("title"):  # the course's name, remembered so the step still reads well before the course is added
            step["title"] = _text(s["title"], 160)
        if s.get("day") not in (None, ""):
            r = day_range(s["day"], sprint["days"] if sprint else MAX_SPRINT_DAYS)
            if not r:
                problems.append(f"Step {i}: the day should be a number like 3, or two like 4-5"
                                + (f", from 1 to {sprint['days']}." if sprint else "."))
            else:
                step["day"] = r[0] if r[0] == r[1] else f"{r[0]}-{r[1]}"
        tasks = s.get("tasks")
        if isinstance(tasks, str):
            tasks = [tasks]
        if isinstance(tasks, list):
            tasks = [t for t in (_text(x, 200) for x in tasks if isinstance(x, (str, int, float))) if t]
            if len(tasks) > MAX_TASKS:
                problems.append(f"Step {i} has {len(tasks)} tasks. Up to {MAX_TASKS}, please.")
            elif tasks:
                step["tasks"] = tasks
        steps.append(step)
    if len(steps) > MAX_STEPS:
        problems.append(f"A roadmap can have up to {MAX_STEPS} courses. Make two roadmaps instead.")
    if steps and all(s.get("optional") for s in steps):
        problems.append("At least one course on the roadmap must be required.")
    if problems:
        raise RoadmapError(problems)
    out = {"id": rid, "title": title, "description": _text(data.get("description"), 600), "language": lang,
           "author": author, "tags": tags, "steps": steps}
    if sprint:
        out["sprint"] = sprint
    out["source"] = source if source in SOURCES else "mine"
    for k in ("followed_at", "made_at", "library_hash"):
        if data.get(k):
            out[k] = data[k]
    run = _run(data.get("sprint_run"), {st["course"] for st in steps})
    if run:
        out["sprint_run"] = run
    return out


PLAN_KEYS = ("course", "note", "optional", "day", "tasks")


def _plan_step(s: dict, keys=PLAN_KEYS) -> dict:
    return {k: s[k] for k in keys if s.get(k)}


def fingerprint(rm: dict) -> str:
    """What makes two copies of a roadmap the same: its title and its steps (not where it's saved)."""
    core = {"title": rm.get("title", ""), "description": rm.get("description", ""),
            "steps": [_plan_step(s) for s in rm.get("steps", [])]}
    if rm.get("sprint"):  # only sprints add it, so older roadmaps keep the fingerprint they always had
        core["sprint"] = rm["sprint"]
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def to_yaml(rm: dict) -> str:
    """The roadmap as the library keeps it (roadmaps/<id>.yaml), readable and easy to review."""
    import yaml
    data = {"id": rm["id"], "title": rm["title"], "description": rm.get("description", ""),
            "language": rm.get("language", "en"), "author": rm.get("author", ""), "tags": rm.get("tags", []),
            "steps": [_plan_step(s) for s in rm["steps"]]}
    if rm.get("sprint"):
        data = {**{k: v for k, v in data.items() if k != "steps"}, "sprint": rm["sprint"], "steps": data["steps"]}
    if not data["tags"]:
        del data["tags"]
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110)


# ---- on this device ----------------------------------------------------------------------------------------

def _folder(home: Path) -> Path:
    return Path(home) / "roadmaps"


def save(home: Path, rm: dict) -> dict:
    rm = parse(rm, rm.get("source", "mine"))
    f = _folder(home)
    f.mkdir(parents=True, exist_ok=True)
    tmp = f / f".{rm['id']}.json.tmp"
    tmp.write_text(json.dumps(rm, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f / f"{rm['id']}.json")
    return rm


_PARSED: dict[str, tuple[tuple, dict | None]] = {}  # file -> ((mtime, size), parsed): read and parsed once per change


def _read(p: Path) -> dict | None:
    """A roadmap file, parsed. Kept in memory until the file changes (v1.36.1): pages ask for your roadmaps
    several times each (the sprint strip, the sprint timer, Home's list), and parsing them all every time
    took a good part of a page on a phone. A caller gets its own copy."""
    try:
        st = p.stat()
    except OSError:
        _PARSED.pop(str(p), None)
        return None
    key = (st.st_mtime_ns, st.st_size)
    hit = _PARSED.get(str(p))
    if hit and hit[0] == key:
        return json.loads(hit[1]) if hit[1] is not None else None  # v1.38: a JSON copy is 20x faster than deepcopy
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        rm = parse(raw, raw.get("source", "mine"))
    except (OSError, ValueError, RoadmapError):
        rm = None
    text = json.dumps(rm, ensure_ascii=False) if rm is not None else None
    _PARSED[str(p)] = (key, text)
    return json.loads(text) if text is not None else None


def get(home: Path, rid: str) -> dict | None:
    if not ID_RE.match(rid or ""):
        return None
    return _read(_folder(home) / f"{rid}.json")


def mine(home: Path) -> list[dict]:
    """Roadmaps you made or follow, the newest first."""
    out = []
    f = _folder(home)
    if f.is_dir():
        with os.scandir(f) as it:
            for e in it:
                if e.name.endswith(".json") and not e.name.startswith(".") and e.is_file():
                    rm = _read(Path(e.path))
                    if rm:
                        rm["_mtime"] = e.stat().st_mtime
                        out.append(rm)
    out.sort(key=lambda r: -r.pop("_mtime"))
    return out


def delete(home: Path, rid: str) -> bool:
    if not ID_RE.match(rid or ""):
        return False
    p = _folder(home) / f"{rid}.json"
    if p.exists():
        p.unlink()
        return True
    return False


def free_id(home: Path, rid: str) -> str:
    """rid, or rid-2, rid-3… if you already have a roadmap with that id."""
    n, out = 2, rid
    while (_folder(home) / f"{out}.json").exists():
        out = f"{rid[:58]}-{n}"
        n += 1
    return out


# ---- the library -------------------------------------------------------------------------------------------

def library_list(index: dict) -> list[dict]:
    out = []
    for e in index.get("roadmaps") or []:
        try:
            rm = parse(e, "library")
        except RoadmapError:
            continue
        rm["minutes"] = int(e.get("minutes") or 0)
        rm["hash"] = str(e.get("hash") or fingerprint(rm))
        rm["verified"] = bool((e.get("author") or {}).get("verified")) if isinstance(e.get("author"), dict) else False
        out.append(rm)
    return out


def sync_library(home: Path, index: dict, title_of=lambda cid: "") -> list[str]:
    """Bring every library roadmap you follow up to the library's current version, all at once (v1.32.1).

    A library roadmap is the library's path, so when the library changes its order or its courses, your copy
    follows: no "update" button per roadmap. Your progress is kept (it lives in your courses, not in the roadmap),
    and so is when you started following it. Roadmaps you made yourself, or got in a link, are never touched, and a
    roadmap that left the library stays as you had it. Returns the ids that changed."""
    if not index or index.get("offline"):
        return []
    lib = {r["id"]: r for r in library_list(index)}
    changed = []
    for rm in mine(home):
        new = lib.get(rm["id"]) if rm.get("source") == "library" else None
        if not new or (new["hash"] == rm.get("library_hash") and fingerprint(new) == fingerprint(rm)):
            continue
        copy = {k: v for k, v in new.items() if k not in ("minutes", "verified")}
        copy.update(source="library", library_hash=new["hash"], followed_at=rm.get("followed_at", ""))
        if rm.get("sprint_run"):  # your sprint goes on; courses that left the roadmap drop out of it in parse()
            copy["sprint_run"] = rm["sprint_run"]
        old_titles = {s["course"]: s.get("title", "") for s in rm["steps"]}
        for st in copy["steps"]:  # course names, for before the courses are added
            st["title"] = st.get("title") or title_of(st["course"]) or old_titles.get(st["course"], "")
        try:
            save(home, copy)
        except RoadmapError:
            continue
        if fingerprint(new) != fingerprint(rm):
            changed.append(rm["id"])
    return changed


def library_find(index: dict, rid: str) -> dict | None:
    return next((r for r in library_list(index) if r["id"] == rid), None)


def share_data(rm: dict, in_library: bool) -> dict:
    """What goes inside an inPace link: a pointer when the library has it, else the whole (small) roadmap."""
    if in_library:
        return {"inpace": "library-roadmap", "id": rm["id"], "title": rm["title"], "author": rm.get("author", "")}
    out = {"inpace": "roadmap", "id": rm["id"], "title": rm["title"], "description": rm.get("description", ""),
           "language": rm.get("language", "en"), "author": rm.get("author", ""), "tags": rm.get("tags", []),
           "steps": [_plan_step(s, PLAN_KEYS + ("title",)) for s in rm["steps"]]}
    if rm.get("sprint"):
        out["sprint"] = rm["sprint"]
    return out


# ---- how far along you are -----------------------------------------------------------------------------------

def status(v, rm: dict, index: dict | None = None) -> dict:
    """Each step with its course and your progress, and the roadmap as a whole.

    A step's state: done (course finished), active (started), start (added, not started), add (in the library,
    not added yet), unknown (not on this device, and we have no library list to look in: offline, or the library
    was never opened), missing (neither on this device nor in the library).

    A missing course can't be added, so it's never the "current" step: the roadmap points at the next course you
    can take, and "blocked" lists the required courses that keep the roadmap from finishing."""
    index = index or {}
    known = bool(index.get("courses"))
    lib = {str(e.get("id")): e for e in index.get("courses") or [] if isinstance(e, dict)}
    steps = []
    for i, s in enumerate(rm["steps"]):
        c = v.get_course(s["course"])
        e = lib.get(s["course"])
        jid = v.journey_for_course(s["course"]) if c else None
        prog = None
        if jid:
            try:
                prog = v.progress(jid)
            except Exception:
                prog = None
        percent = int((prog or {}).get("percent") or 0)
        finished = bool(prog and prog.get("finished"))
        state = ("done" if finished else "active" if jid else "start" if c else "add" if e
                 else "missing" if known else "unknown")
        minutes = 0
        if c:
            minutes = sum(int(les.get("minutes") or 0) for m in c.modules for les in m["lessons"])
        elif e:
            minutes = int(e.get("minutes") or 0)
        title = c.title if c else (e or {}).get("title") or s.get("title") or s["course"]
        nxt = (prog or {}).get("next")
        steps.append({**s, "n": i + 1, "state": state, "percent": 100 if finished else percent, "journey": jid,
                      "title": title, "course_obj": c, "entry": e, "minutes": minutes,
                      "lessons": (c.lesson_count if c else int((e or {}).get("lessons") or 0)),
                      "cover": (e or {}).get("cover"), "next_up": nxt, "optional": bool(s.get("optional"))})
    need = [s for s in steps if not s["optional"]]
    done = [s for s in need if s["state"] == "done"]
    open_ = [s for s in steps if s["state"] not in ("done", "missing")]
    current = next((s for s in open_ if not s["optional"]), None) or next(iter(open_), None)
    percent = round(sum(s["percent"] for s in need) / len(need)) if need else 0
    return {"steps": steps, "done": len(done), "total": len(need), "percent": percent,
            "finished": bool(need) and len(done) == len(need), "current": current,
            "minutes": sum(s["minutes"] for s in steps), "missing": [s for s in steps if s["state"] == "missing"],
            "to_add": [s for s in steps if s["state"] == "add"],
            "unknown": [s for s in steps if s["state"] == "unknown"],
            "blocked": [s for s in need if s["state"] == "missing"],
            "add_bytes": sum(int((s["entry"] or {}).get("size") or 0) for s in steps if s["state"] == "add")}


# ---- sprints (v1.33) -------------------------------------------------------------------------------------------

def auto_plan(rm: dict, minutes_of: dict, days: int) -> dict:
    """A day (or days) for every step: what the roadmap says, else spread over the days by course length.

    Required steps without a day share the days in proportion to their minutes (a course with no known length
    counts as an hour). An optional step without a day goes with the step before it."""
    days = max(1, min(MAX_SPRINT_DAYS, int(days)))
    authored = (rm.get("sprint") or {}).get("days") or days
    plan, free = {}, []
    for s in rm["steps"]:
        r = day_range(s.get("day"), MAX_SPRINT_DAYS)
        if r:
            if authored != days:  # the roadmap was planned for another length: stretch or squeeze it
                r = tuple(max(1, min(days, round((d - 1) * days / authored) + 1)) for d in r)
            plan[s["course"]] = [r[0], max(r)]
        elif not s.get("optional"):
            free.append(s["course"])
    if free:
        mins = [max(1, int(minutes_of.get(c) or 60)) for c in free]
        total, before = sum(mins), 0
        for c, m in zip(free, mins):
            a = min(days, int(before * days / total) + 1)
            b = min(days, max(a, -(-int((before + m) * days) // total)))
            plan[c] = [a, b]
            before += m
    last = [1, 1]
    for s in rm["steps"]:
        if s["course"] in plan:
            last = plan[s["course"]]
        else:
            plan[s["course"]] = list(last)
    return plan


def start_sprint(rm: dict, minutes_of: dict, days: int, hours: float, start: str, hour: int = 0,
                 end: int | None = None, rhythm: tuple | None = None) -> dict:
    """Start (or restart) a sprint on your copy of the roadmap. Ticks from an earlier run are dropped.
    hour: when each sprint day starts (0-23). Start at 16 and every day runs from 4 pm to 4 pm the next day, so
    late-night work still counts for the day you started it."""
    sp = _sprint({"days": days, "hours": hours}) or {"days": 7, "hours": 0}
    run = {"start": start, **sp, "plan": auto_plan(rm, minutes_of, sp["days"]), "ticks": {}}
    if 0 < int(hour or 0) < 24:
        run["hour"] = int(hour)
    if end is not None and 0 <= int(end) < 24:
        run["end"] = int(end)
    if rhythm:
        run["rhythm"] = [int(rhythm[0]), int(rhythm[1])]
    return {**rm, "sprint_run": run}


def rhythm_of(run: dict) -> tuple[int, int]:
    """The timer's blocks for this sprint: (focus minutes, break minutes), 50 and 10 unless you chose."""
    rh = run.get("rhythm") or [50, 10]
    return int(rh[0]), int(rh[1])


def sprint_window(run: dict, now) -> dict | None:
    """Today's sprint window, for the countdown strip: it opens when the sprint day starts and closes at the
    end hour you chose (12:00 to 00:00 is a 12-hour window). Without an end hour, the window is as long as the
    hours a day. It follows the clock, so nothing pauses it, and it comes back after a restart.
    Returns None once the sprint's last day is over."""
    day = sprint_day(run, now)
    days = int(run.get("days") or 0)
    if day > days:
        return None
    if day < 1:
        start = day_start(run, 1)
        return {"state": "before", "day": 0, "days": days, "start": start, "end": start, "next": start}
    import datetime as _dt
    start = day_start(run, day)
    hour = int(run.get("hour") or 0)
    if run.get("end") is not None:
        length = (int(run["end"]) - hour) % 24 or 24
    else:
        length = min(24.0, float(run.get("hours") or 0) or 24.0)
    end = start + _dt.timedelta(hours=length)
    nxt = start + _dt.timedelta(days=1)
    state = "open" if now < end else ("closed" if day < days else "done")
    return {"state": state, "day": day, "days": days, "start": start, "end": end, "next": nxt,
            "rhythm": rhythm_of(run)}


def sprint_day(run: dict, now) -> int:
    """Which day of the sprint it is: `now` is a datetime (or a date, taken as that sprint day)."""
    import datetime as _dt
    start = _dt.date.fromisoformat(run["start"])
    if isinstance(now, _dt.datetime):
        now = (now - _dt.timedelta(hours=int(run.get("hour") or 0))).date()
    return (now - start).days + 1


def day_start(run: dict, day: int):
    """When a sprint day starts, as a datetime on this computer's clock."""
    import datetime as _dt
    start = _dt.datetime.combine(_dt.date.fromisoformat(run["start"]), _dt.time(int(run.get("hour") or 0)))
    return start + _dt.timedelta(days=day - 1)


def _hour_key(k: str):
    """A focus total's key: "2026-11-24T16" (an hour) or "2026-11-24" (a whole day, older totals)."""
    import datetime as _dt
    try:
        d, _, h = str(k).partition("T")
        return _dt.datetime.combine(_dt.date.fromisoformat(d), _dt.time(int(h or 0)))
    except ValueError:
        return None


def stop_sprint(rm: dict) -> dict:
    return {k: v for k, v in rm.items() if k != "sprint_run"}


def tasks_for(rm: dict, step: dict) -> list[str]:
    """A step's tasks in your sprint: your own if you changed them, else the roadmap's."""
    own = ((rm.get("sprint_run") or {}).get("tasks") or {})
    return list(own[step["course"]]) if step["course"] in own else list(step.get("tasks") or [])


def tick(rm: dict, course: str, index: int, on: bool, at: str = "") -> dict:
    """Tick (or untick) one task of a step in your sprint. Every change is written in the sprint's log with
    its time, so the report shows when the work was marked done, not just that it was."""
    run = rm.get("sprint_run")
    step = next((s for s in rm["steps"] if s["course"] == course), None)
    if not run or not step:
        return rm
    n = len(tasks_for(rm, step)) or 1
    if not 0 <= index < n:
        return rm
    have = set(run["ticks"].get(course, []))
    if (index in have) == bool(on):
        return rm
    have = have | {index} if on else have - {index}
    ticks = {**run["ticks"], course: sorted(have)}
    if not have:
        del ticks[course]
    at = at or time.strftime("%Y-%m-%dT%H:%M:%S")
    log = (list(run.get("log") or []) + [[at, course, index, 1 if on else 0]])[-MAX_LOG:]
    return {**rm, "sprint_run": {**run, "ticks": ticks, "log": log}}


def customize(rm: dict, days: int, hours: float, plan: dict, tasks: dict, end: int | None | str = "keep",
              rhythm: tuple | None = None) -> dict:
    """Change your running sprint: its length, hours, the day of each step and its tasks.

    plan: course -> "3" or "4-5" (blank keeps the step where it was); tasks: course -> lines of text (the same as
    the roadmap's -> no change of your own). Ticks on tasks that are gone are dropped. Raises RoadmapError."""
    run = rm.get("sprint_run")
    if not run:
        raise RoadmapError(["Start the sprint first."])
    sp = _sprint({"days": days, "hours": hours})
    if not sp:
        raise RoadmapError([f"A sprint can be 1 to {MAX_SPRINT_DAYS} days."])
    problems, new_plan, own = [], {}, {}
    for i, st in enumerate(rm["steps"], 1):
        cid = st["course"]
        raw = str(plan.get(cid, "") or "").strip()
        if raw:
            r = day_range(raw, sp["days"])
            if not r:
                problems.append(f"Course {i}: the day should be like 3 or 4-5, from 1 to {sp['days']}.")
                continue
            new_plan[cid] = list(r)
        elif cid in run["plan"]:
            a, b = run["plan"][cid]
            new_plan[cid] = [min(a, sp["days"]), min(b, sp["days"])]
        lines = tasks.get(cid)
        if lines is not None:
            lines = [x for x in (_text(y, 200) for y in lines) if x]
            if len(lines) > MAX_TASKS:
                problems.append(f"Course {i} has {len(lines)} tasks. Up to {MAX_TASKS}, please.")
            elif lines != list(st.get("tasks") or []):
                own[cid] = lines
        elif cid in (run.get("tasks") or {}):
            own[cid] = run["tasks"][cid]
    if problems:
        raise RoadmapError(problems)
    out = {**run, **sp, "plan": new_plan}
    if rhythm:
        out["rhythm"] = [int(rhythm[0]), int(rhythm[1])]
    if end != "keep":  # the hour each day's window ends (None: as long as the hours a day)
        out.pop("end", None)
        if end is not None and 0 <= int(end) < 24:
            out["end"] = int(end)
    out.pop("tasks", None)
    if own:
        out["tasks"] = own
    new_rm = {**rm, "sprint_run": out}
    ticks = {}
    for st in rm["steps"]:  # keep only ticks that still point at a task
        n = len(tasks_for(new_rm, st)) or 1
        keep = [x for x in run["ticks"].get(st["course"], []) if x < n]
        if keep:
            ticks[st["course"]] = keep
    out["ticks"] = ticks
    return new_rm


def as_plan(rm: dict) -> dict:
    """Your sprint, the way you changed it, as a roadmap someone else can follow (days, hours, days and tasks
    baked into the steps). Your ticks and log stay with you."""
    run = rm.get("sprint_run")
    if not run:
        return rm
    steps = []
    for st in rm["steps"]:
        new = {k: v for k, v in st.items() if k not in ("day", "tasks")}
        r = run["plan"].get(st["course"])
        if r:
            new["day"] = r[0] if r[0] == r[1] else f"{r[0]}-{r[1]}"
        t = tasks_for(rm, st)
        if t:
            new["tasks"] = t
        steps.append(new)
    out = {k: v for k, v in rm.items() if k not in ("sprint_run", "library_hash", "followed_at")}
    out.update(steps=steps, sprint={"days": run["days"], "hours": run["hours"]})
    return out


def sprint_status(rm: dict, st: dict, today, focus: dict | None = None) -> dict:
    """Where your sprint stands today: the day number, today's steps, what's late, and a strip of the days.

    `today` is the time now (a datetime) or a date. `focus`: seconds on the focus timer per hour
    ("2026-11-24T16") or per date, from focus.hour_totals. Without a running sprint: {"running": False, ...}."""
    import datetime as _dt
    sp = rm.get("sprint") or {}
    run = rm.get("sprint_run")
    if not run:
        return {"running": False, "days": sp.get("days") or 7, "hours": sp.get("hours") or 0, "planned": bool(sp)}
    day = sprint_day(run, today)
    plan, ticks = run["plan"], run["ticks"]
    steps, units, done_units = [], 0, 0
    for s in st["steps"]:
        tasks = tasks_for(rm, s)
        n = len(tasks) or 1
        on = set(ticks.get(s["course"], []))
        course_done = s["state"] == "done"
        items = [{"i": i, "text": t, "on": course_done or i in on} for i, t in enumerate(tasks)] or \
                [{"i": 0, "text": "", "on": course_done or 0 in on}]
        got = sum(1 for x in items if x["on"])
        rng = plan.get(s["course"])
        row = {**s, "tasks": tasks, "range": rng, "items": items, "sprint_done": got == n, "got": got, "units": n,
               "proven": course_done}
        steps.append(row)
        if not s["optional"]:
            units += n
            done_units += got
    def due_on(d):
        return [r for r in steps if r["range"] and r["range"][1] == d and not r["optional"]]
    strip = []
    for d in range(1, run["days"] + 1):
        due = due_on(d)
        ok = all(r["sprint_done"] for r in due)
        state = "today" if d == day else ("done" if ok else "late") if d < day else ("done" if due and ok else "ahead")
        strip.append({"d": d, "state": state, "due": len(due)})
    in_days = 1 <= day <= run["days"]
    today_steps = [r for r in steps if r["range"] and in_days and r["range"][0] <= day <= r["range"][1]]
    late = [r for r in steps if r["range"] and r["range"][1] < min(day, run["days"] + 1) and not r["optional"]
            and not r["sprint_done"] and r not in today_steps]
    by_day: dict[int, int] = {}  # ticks made on each day of the sprint (unticks don't count)
    for at, _c, _i, on in run.get("log") or []:
        try:
            d = sprint_day(run, _dt.datetime.fromisoformat(at))
        except ValueError:
            continue
        if on and 1 <= d <= run["days"]:
            by_day[d] = by_day.get(d, 0) + 1
    secs: dict[int, int] = {}  # focus seconds on each day of the sprint
    for k, n in (focus or {}).items():
        at = _hour_key(k)
        if at:
            d = sprint_day(run, at)
            secs[d] = secs.get(d, 0) + int(n)
    for x in strip:
        x["ticks"] = by_day.get(x["d"], 0)
        x["focus"] = secs.get(x["d"], 0) // 60  # minutes
    focus_today = secs.get(day, 0) // 60
    return {"running": True, "start": run["start"], "day": day, "days": run["days"], "hours": run["hours"],
            "hour": int(run.get("hour") or 0),
            "end_time": f"{int(run['end']):02d}:00" if run.get("end") is not None else "",
            "rhythm": list(rhythm_of(run)),
            "active_days": len(by_day), "custom": bool(run.get("tasks")), "focus_today": focus_today,
            "focus_total": sum(x["focus"] for x in strip),
            "focus_goal": int(round(float(run["hours"] or 0) * 60)),
            "before": day < 1, "over": day > run["days"], "steps": steps, "today": today_steps, "late": late,
            "strip": strip, "percent": round(100 * done_units / units) if units else 0,
            "finished": bool(units) and done_units == units,
            "unplanned": [r for r in steps if not r["range"]]}


def report(rm: dict, sp: dict, name: str = "") -> str:
    """Your sprint as a short Markdown report, to send to the person who checks on you.

    It says which steps are proven (the course finished in inPace: lessons, tasks and quizzes done) and which
    are only ticked by you, and on which days you ticked work, so a checker can tell the two apart."""
    if not sp.get("running"):
        return ""
    lines = [f"# Sprint report: {rm['title']}", ""]
    who = f"{name}, " if name else ""
    at = f" at {sp['hour']:02d}:00 (each day runs {sp['hour']:02d}:00 to {sp['hour']:02d}:00)" if sp.get("hour") else ""
    lines.append(f"{who}started {sp['start']}{at}, {sp['days']} days" + (f", about {sp['hours']} h a day" if sp["hours"] else "")
                 + f". Today is day {max(0, min(sp['day'], sp['days']))} of {sp['days']}." + (" The days are over." if sp["over"] else ""))
    lines += ["", f"**{sp['percent']}% of the plan ticked.** Worked (ticked something) on {sp['active_days']} of the "
              f"{min(max(sp['day'], 0), sp['days'])} days so far.", "",
              "| Day | Course | Tasks done | How we know |", "|---|---|---|---|"]
    for r in sp["steps"]:
        day = "" if not r["range"] else (str(r["range"][0]) if r["range"][0] == r["range"][1] else f"{r['range'][0]}-{r['range'][1]}")
        how = "Course finished in inPace" if r["proven"] else ("Ticked by the learner" if r["got"] else "Not started")
        opt = " (optional)" if r["optional"] else ""
        lines.append(f"| {day} | {r['title']}{opt} | {r['got']} of {r['units']} | {how} |")
    if sp["late"]:
        lines += ["", "**Late:** " + ", ".join(r["title"] for r in sp["late"]) + "."]
    lines += ["", "Ticks per day: " + ", ".join(f"day {x['d']}: {x['ticks']}" for x in sp["strip"])]
    if sp.get("focus_total"):
        goal = f" (goal {sp['hours']} h a day)" if sp["hours"] else ""
        lines += ["", f"Focus timer{goal}: " + ", ".join(f"day {x['d']}: {x['focus'] // 60} h {x['focus'] % 60} min"
                                                          for x in sp["strip"] if x["focus"])
                  + f". Total {sp['focus_total'] // 60} h {sp['focus_total'] % 60} min, timed in inPace."]
    lines += ["",
              "_Made by inPace. A course counts as proven only when its lessons, tasks and quizzes are done in the app; "
              "ask for the progress file to check the work itself._", ""]
    return "\n".join(lines)


AI_TEMPLATE = """You are helping me plan an intensive study sprint in the inPace app.

My goal: {goal}
Sprint length: {days} days, about {hours} hours a day
{know_line}{notes_line}Language of the notes and tasks: {language}

Use ONLY courses from this list (id: title, lessons, hours). Pick the ones that serve the goal, in a sensible order.
{courses}

Write the plan as ONE YAML document inside a single ```yaml code block, and nothing else. Use exactly this structure:

```yaml
title: "Short name of the sprint"
description: "One or two sentences: who it is for and what they will have at the end"
language: {lang_code}
tags: [sprint, ...]
sprint: {{days: {days}, hours: {hours}}}
steps:
  - course: course-id-from-the-list
    day: 1            # the day for this course, or a range like "4-5"
    note: "Why this course, and which part of it to take in the sprint"
    tasks:
      - "A concrete thing to do or build today, checkable as done or not done"
      - "Another one"
  - course: another-course-id
    day: 2
    optional: true    # only for nice-to-have courses
    note: "..."
    tasks: ["..."]
```

Rules:
- Use each course id at most once, exactly as written in the list. Up to {max_steps} courses.
- Every day from 1 to {days} has at least one course. A course can span days ("4-5").
- Fit the hours: a {hours}-hour day is the limit. Say in the note which modules or projects to do and what to skip.
- 2 to 6 tasks per course. Each task is something you can see is done: a project built, a quiz passed, a module
  finished, code pushed. No vague tasks like "understand X".
- Put a note in quotes if it has a colon in it.
- At least one course must not be optional.
"""


def ai_prompt(goal: str, days: int, hours: float, courses: list[dict], know: str = "", notes: str = "",
              language: str = "English") -> str:
    """The prompt to paste into any AI chat for a sprint plan, made from the courses you can get.

    courses: [{"id", "title", "lessons", "minutes"}] (your courses and the library's)."""
    sp = _sprint({"days": days, "hours": hours}) or {"days": 7, "hours": 4}
    rows = []
    for c in courses[:400]:
        h = round(int(c.get("minutes") or 0) / 60, 1)
        rows.append(f"- {c['id']}: {c.get('title', '')}" + (f", {c['lessons']} lessons" if c.get("lessons") else "")
                    + (f", {h} h" if h else ""))
    lang_code = "ar" if str(language).lower().startswith(("ar", "عرب")) else "en"
    return AI_TEMPLATE.format(goal=_text(goal, 300) or "Get better at my field", days=sp["days"], hours=sp["hours"] or 4,
                              know_line=f"What I already know: {_text(know, 400)}\n" if know.strip() else "",
                              notes_line=f"Extra wishes: {_text(notes, 600)}\n" if notes.strip() else "",
                              language=language or "English", lang_code=lang_code, courses="\n".join(rows),
                              max_steps=MAX_STEPS)


def without(rm: dict, course_ids: set[str]) -> dict:
    """A copy of the roadmap without some courses (the ones you can't get), as your own version. Raises
    RoadmapError if nothing required would be left."""
    steps = [s for s in rm["steps"] if s["course"] not in course_ids]
    return parse({**rm, "steps": steps, "source": "mine"}, "mine")


def on_roadmaps(home: Path, course_id: str) -> list[tuple[dict, int]]:
    """The roadmaps you follow that include this course, with its step number."""
    out = []
    for rm in mine(home):
        for i, s in enumerate(rm["steps"], 1):
            if s["course"] == course_id:
                out.append((rm, i))
    return out


def island_stats(v) -> dict:
    """For Tempo's island: courses you finished that are on one of your roadmaps (each course once), and
    roadmaps you finished."""
    steps_done, finished = set(), 0
    cache: dict[str, bool] = {}

    def course_done(cid: str) -> bool:
        if cid not in cache:
            jid = v.journey_for_course(cid) if v.get_course(cid) else None
            ok = False
            if jid:
                try:
                    ok = bool(v.progress(jid).get("finished"))
                except Exception:
                    ok = False
            cache[cid] = ok
        return cache[cid]

    for rm in mine(v.home):
        need = [s for s in rm["steps"] if not s.get("optional")]
        for s in rm["steps"]:
            if course_done(s["course"]):
                steps_done.add(s["course"])
        if need and all(course_done(s["course"]) for s in need):
            finished += 1
    return {"roadmap_steps": len(steps_done), "roadmaps": finished}


# ---- making one from the courses there are -------------------------------------------------------------------

_FIRST = {"beginner", "beginners", "basics", "basic", "intro", "introduction", "math", "maths", "a1", "foundations",
          "fundamentals", "excel", "html"}
_LATER = {"advanced", "deep", "interview", "b1", "production", "clean", "architecture"}
_STOP = {"a", "an", "the", "to", "and", "or", "of", "for", "in", "on", "with", "learn", "become", "be", "how",
         "i", "want", "my", "course", "courses", "من", "في", "على", "و", "أن", "تعلم", "تعلّم", "أريد"}
_SERIES = re.compile(r"-(\d{1,2})(?=-|$)")
_LANG_END = re.compile(r"-(ar|en|fr|es|de)$")


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w]+", (text or "").lower()) if w not in _STOP and len(w) > 1]


def _level(c: dict) -> int:
    """0 for courses to take first (basics, maths, beginner), 2 for courses that build on others, 1 otherwise."""
    words = set(_words(c.get("title", "") + " " + c.get("id", "").replace("-", " ") + " " + " ".join(c.get("tags") or [])))
    title = set(_words(c.get("title", "")))
    if "interview" in title:
        return 3
    if words & _FIRST and not title & _LATER:
        return 0
    return 2 if title & _LATER else 1


def _series(cid: str) -> str:
    m = _SERIES.search(cid)
    return cid[:m.start()] if m else ""


def _order_key(c: dict, levels: dict, score: int = 0) -> tuple:
    """Courses to take first, then the rest; the parts of a series together and in order (1, 2, 3…); among
    the others, the best match first."""
    sid = _series(c["id"])
    m = _SERIES.search(c["id"])
    return (levels.get(sid, _level(c)) if sid else _level(c), sid, int(m.group(1)) if m else 0, -score, c.get("title", ""))


def suggest(goal: str, courses: list[dict], language: str = "", limit: int = 8) -> list[str]:
    """Course ids for a goal ("data analyst", "machine learning", "English"), in a sensible order.

    courses: dicts with id, title, description, tags and language (installed and library courses alike).
    A course scores for each goal word found in its title (most), tags, id or description. The same course in
    two languages (python-basics, python-basics-ar) counts once, in your language when there's a choice. Parts
    of a series (ml-1, ml-2…) come together and in order, and basics come before what builds on them."""
    want = _words(goal)
    if not want:
        return []

    def hit(w: str, ws: list[str]) -> bool:
        return any(x == w or (len(w) > 3 and len(x) > 3 and (x.startswith(w) or w.startswith(x))) for x in ws)

    scored = {}
    for c in courses:
        if not c.get("id"):
            continue
        title, tags = _words(c.get("title", "")), _words(" ".join(c.get("tags") or []))
        ids, desc = _words(c["id"].replace("-", " ")), _words(c.get("description", ""))
        score = sum(4 * hit(w, title) + 3 * hit(w, tags) + 2 * hit(w, ids) + hit(w, desc) for w in want)
        if score:
            scored[c["id"]] = (score, c)
    if not scored:
        return []
    # one language per course
    by_base: dict[str, tuple] = {}
    for cid, (score, c) in scored.items():
        base = _LANG_END.sub("", cid)
        mine_lang = bool(language) and c.get("language") == language
        rank = (mine_lang, score)
        if base not in by_base or rank > by_base[base][0]:
            by_base[base] = (rank, score, c)
    picked = sorted(((score, c) for _, score, c in by_base.values()), key=lambda x: -x[0])
    best = picked[0][0]
    keep = [c for score, c in picked if score >= max(2, best / 2)][:limit]
    # a whole series: if part 2 of something is in, its other parts come too
    series = {_series(c["id"]) for c in keep} - {""}
    have = {c["id"] for c in keep}
    for c in courses:
        if c.get("id") and c["id"] not in have and _series(c["id"]) in series:
            keep.append(c)
            have.add(c["id"])
    levels: dict[str, int] = {}
    for c in keep:
        sid = _series(c["id"])
        if sid:
            levels[sid] = min(levels.get(sid, 9), _level(c))
    scores = {cid: sc for cid, (sc, _c) in scored.items()}
    keep.sort(key=lambda c: _order_key(c, levels, scores.get(c["id"], 0)))
    return [c["id"] for c in keep[:MAX_STEPS]]
