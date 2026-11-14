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
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
COURSE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
MAX_STEPS = 30
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
        steps.append(step)
    if len(steps) > MAX_STEPS:
        problems.append(f"A roadmap can have up to {MAX_STEPS} courses. Make two roadmaps instead.")
    if steps and all(s.get("optional") for s in steps):
        problems.append("At least one course on the roadmap must be required.")
    if problems:
        raise RoadmapError(problems)
    out = {"id": rid, "title": title, "description": _text(data.get("description"), 600), "language": lang,
           "author": author, "tags": tags, "steps": steps}
    out["source"] = source if source in SOURCES else "mine"
    for k in ("followed_at", "made_at", "library_hash"):
        if data.get(k):
            out[k] = data[k]
    return out


def fingerprint(rm: dict) -> str:
    """What makes two copies of a roadmap the same: its title and its steps (not where it's saved)."""
    core = {"title": rm.get("title", ""), "description": rm.get("description", ""),
            "steps": [{k: s.get(k) for k in ("course", "note", "optional") if s.get(k)} for s in rm.get("steps", [])]}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def to_yaml(rm: dict) -> str:
    """The roadmap as the library keeps it (roadmaps/<id>.yaml), readable and easy to review."""
    import yaml
    data = {"id": rm["id"], "title": rm["title"], "description": rm.get("description", ""),
            "language": rm.get("language", "en"), "author": rm.get("author", ""), "tags": rm.get("tags", []),
            "steps": [{k: s[k] for k in ("course", "note", "optional") if s.get(k)} for s in rm["steps"]]}
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


def get(home: Path, rid: str) -> dict | None:
    if not ID_RE.match(rid or ""):
        return None
    p = _folder(home) / f"{rid}.json"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return parse(raw, raw.get("source", "mine"))
    except (OSError, ValueError, RoadmapError):
        return None


def mine(home: Path) -> list[dict]:
    """Roadmaps you made or follow, the newest first."""
    out = []
    f = _folder(home)
    if f.is_dir():
        for p in f.glob("*.json"):
            rm = get(home, p.stem)
            if rm:
                rm["_mtime"] = p.stat().st_mtime
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


def library_find(index: dict, rid: str) -> dict | None:
    return next((r for r in library_list(index) if r["id"] == rid), None)


def share_data(rm: dict, in_library: bool) -> dict:
    """What goes inside an inPace link: a pointer when the library has it, else the whole (small) roadmap."""
    if in_library:
        return {"inpace": "library-roadmap", "id": rm["id"], "title": rm["title"], "author": rm.get("author", "")}
    return {"inpace": "roadmap", "id": rm["id"], "title": rm["title"], "description": rm.get("description", ""),
            "language": rm.get("language", "en"), "author": rm.get("author", ""), "tags": rm.get("tags", []),
            "steps": [{k: s[k] for k in ("course", "note", "optional", "title") if s.get(k)} for s in rm["steps"]]}


# ---- how far along you are -----------------------------------------------------------------------------------

def status(v, rm: dict, index: dict | None = None) -> dict:
    """Each step with its course and your progress, and the roadmap as a whole.

    A step's state: done (course finished), active (started), start (added, not started), add (in the library,
    not added yet), missing (neither on this device nor in the library)."""
    index = index or {}
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
        state = "done" if finished else "active" if jid else "start" if c else "add" if e else "missing"
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
    current = next((s for s in steps if s["state"] != "done" and not s["optional"]), None) or \
        next((s for s in steps if s["state"] != "done"), None)
    percent = round(sum(s["percent"] for s in need) / len(need)) if need else 0
    return {"steps": steps, "done": len(done), "total": len(need), "percent": percent,
            "finished": bool(need) and len(done) == len(need), "current": current,
            "minutes": sum(s["minutes"] for s in steps), "missing": [s for s in steps if s["state"] == "missing"],
            "to_add": [s for s in steps if s["state"] == "add"]}


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
