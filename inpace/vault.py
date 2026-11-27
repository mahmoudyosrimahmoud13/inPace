"""The vault: one folder holding everything for one person.

    inPace/
      vault.db        events, milestones, approvals, people, receipts, your notes
      identity.key    your private signing key (never share)
      courses/<id>/   installed courses
      evidence/       your work files, named by fingerprint
"""
from __future__ import annotations

import json
import pickle
import re
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from .canon import fingerprint, now_utc, sha256_hex
from .course import Course, CourseError, files_from_folder, load_course, save_course_folder
from .identity import Identity, verify

# v1.38: short-lived copies of what pages read again and again (settings, events, milestones). Any write by any
# Vault in this process (the download worker has its own) moves this counter on, and every copy is read again.
_GEN = [0]


def _bump() -> None:
    _GEN[0] += 1


class _Connection(sqlite3.Connection):
    """Every commit, from any part of inPace, moves the counter on."""

    def commit(self) -> None:
        super().commit()
        _GEN[0] += 1


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS progress_cache (journey TEXT PRIMARY KEY, key TEXT, data BLOB);
CREATE TABLE IF NOT EXISTS journeys (
  id TEXT PRIMARY KEY, course_id TEXT, started_at TEXT, archived INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, journey TEXT, type TEXT, data TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS milestones (
  journey TEXT, seq INTEGER, hash TEXT UNIQUE, body TEXT, sig TEXT, PRIMARY KEY (journey, seq));
CREATE TABLE IF NOT EXISTS approvals (
  milestone TEXT, checker TEXT, decision TEXT, note TEXT, at TEXT, sig TEXT,
  PRIMARY KEY (milestone, checker, at));
CREATE TABLE IF NOT EXISTS people (
  id TEXT PRIMARY KEY, name TEXT, color TEXT, nickname TEXT,
  checks_me INTEGER DEFAULT 0, i_check INTEGER DEFAULT 0, added_at TEXT);
CREATE TABLE IF NOT EXISTS received (
  learner TEXT, journey TEXT, course TEXT, data TEXT, received_at TEXT, PRIMARY KEY (learner, journey));
CREATE TABLE IF NOT EXISTS receipts (
  learner TEXT, journey TEXT, seq INTEGER, hash TEXT, decision TEXT, note TEXT, at TEXT,
  PRIMARY KEY (learner, journey, seq, at));
CREATE TABLE IF NOT EXISTS sent_exams (
  id TEXT PRIMARY KEY, learner TEXT, journey TEXT, req TEXT, exam TEXT, key TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS my_exams (
  id TEXT PRIMARY KEY, checker TEXT, journey TEXT, req TEXT, data TEXT, received_at TEXT);
CREATE TABLE IF NOT EXISTS exam_results (
  exam TEXT PRIMARY KEY, checker TEXT, score INTEGER, total INTEGER, percent INTEGER, passed INTEGER, at TEXT);
CREATE TABLE IF NOT EXISTS private_questions (
  course TEXT, id TEXT, data TEXT, created_at TEXT, PRIMARY KEY (course, id));
CREATE TABLE IF NOT EXISTS file_requests (
  journey TEXT, sha256 TEXT, name TEXT, checker TEXT, at TEXT, PRIMARY KEY (journey, sha256, checker));
CREATE TABLE IF NOT EXISTS received_files (
  sha256 TEXT PRIMARY KEY, learner TEXT, name TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY, course TEXT, lesson TEXT, journey TEXT, quote TEXT, text TEXT, created_at TEXT, updated_at TEXT);
CREATE INDEX IF NOT EXISTS notes_by_lesson ON notes (course, lesson);
CREATE INDEX IF NOT EXISTS events_by_journey ON events (journey, seq);
CREATE TABLE IF NOT EXISTS review_cards (
  course TEXT, qid TEXT, box INTEGER, due TEXT, PRIMARY KEY (course, qid));
CREATE TABLE IF NOT EXISTS races (id TEXT PRIMARY KEY, data TEXT, journey TEXT, folder TEXT, joined_at TEXT);
CREATE TABLE IF NOT EXISTS race_updates (race TEXT, racer TEXT, data TEXT, at TEXT, PRIMARY KEY (race, racer));
CREATE TABLE IF NOT EXISTS race_cheers (race TEXT, to_id TEXT, text TEXT, at TEXT);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
  BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
  BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS milestones_no_update BEFORE UPDATE ON milestones
  BEGIN SELECT RAISE(ABORT, 'milestones are append-only'); END;
CREATE TRIGGER IF NOT EXISTS milestones_no_delete BEFORE DELETE ON milestones
  BEGIN SELECT RAISE(ABORT, 'milestones are append-only'); END;
"""

COLORS = ["#3A506B", "#1F7A56", "#B4691B", "#7A4FA0", "#2F7EA8", "#B23A5B", "#5B7A1F", "#8A5A3C"]
SESSION_GAP_MIN = 30


def default_home() -> Path:
    env = os.environ.get("INPACE_HOME")
    if env:
        return Path(env).expanduser()
    docs = Path.home() / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "inPace"


def lesson_ahead(lessons: list[dict]) -> dict | None:
    """The lesson to read next: the first one not done. An optional lesson you already opened and left counts as
    looked at, so "Continue" doesn't keep sending you back to it."""
    return next((les for les in lessons if not les["done"] and not (les.get("optional") and les.get("opened"))), None)


_NAME_INDEX: dict = {}


def _names_in(root: Path, depth: int = 5, limit: int = 20000) -> dict:
    """File name (lower case) -> path, for every file up to `depth` folders inside `root`. Remembered until the
    folder changes, so looking up many lessons stays fast. The first file found wins; hidden folders are skipped."""
    root = root.resolve()
    try:
        stamp = root.stat().st_mtime
    except OSError:
        return {}
    got = _NAME_INDEX.get(root)
    if got and got[0] == stamp:
        return got[1]
    names: dict = {}
    count = 0
    start = len(root.parts)
    for here, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith((".", "__MACOSX")))
        if len(Path(here).parts) - start >= depth:
            dirs[:] = []
        for f in sorted(files):
            if f.startswith("."):
                continue
            names.setdefault(f.lower(), Path(here) / f)
            count += 1
        if count > limit:
            break
    _NAME_INDEX[root] = (stamp, names)
    return names


class Vault:
    def __init__(self, home: Path | None = None):
        self.home = Path(home or default_home())
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "courses").mkdir(exist_ok=True)
        (self.home / "evidence").mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.home / "vault.db", check_same_thread=False, factory=_Connection)
        self._progress_cache: dict[str, tuple] = {}
        self.db.row_factory = sqlite3.Row
        try:  # v1.38: a write no longer waits for the phone's storage to confirm it (WAL journal; the data is safe
            # unless the phone loses power in that second). Opening a lesson used to spend half its time here.
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError:
            pass
        self.db.executescript(SCHEMA)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(people)")}
        for col in ("avatar", "island"):
            # v1.17: people can have a turtle (from their contact card) instead of a coloured letter,
            # and a copy of their island that they chose to share
            if col not in cols:
                self.db.execute(f"ALTER TABLE people ADD COLUMN {col} TEXT DEFAULT ''")
                self.db.commit()
                _bump()
        self._courses: dict[str, Course] = {}
        self._identity: Identity | None = None
        self._meta_cache: dict[str, tuple[float, str | None]] = {}
        self._journey_of: dict[str, str | None] | None = None
        # v1.38: Home asks for a journey's events and milestones three or four times each, for every course.
        # Both are kept for two seconds (and dropped at once when this copy adds to them).
        self._events_cache: dict[str, tuple] = {}
        self._milestones_cache: dict[str, tuple] = {}
        self._chain_ok: dict[str, tuple[tuple, list]] = {}
        self._journeys_cache: tuple | None = None
        self._no_course: dict[str, float] = {}
        self._last_seq: tuple | None = None

    def fresh(self) -> None:
        """Forget the short-lived copies (settings, events, milestones): called as each page starts, so a page
        reads each thing once, and the next page sees whatever another part of inPace wrote meanwhile."""
        self._meta_cache.clear()
        self._events_cache.clear()
        self._milestones_cache.clear()
        self._no_course.clear()

    def checkpoint(self) -> None:
        """Fold the journal back into vault.db (before a backup copies the file)."""
        try:
            self.db.commit()
            _bump()
            self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.DatabaseError:
            pass

    # ---- small helpers ---------------------------------------------------
    META_TTL = 5.0  # a copy is kept this long at most, in case another process wrote to the database

    def _live(self, hit) -> bool:
        return bool(hit) and hit[0] == _GEN[0] and time.monotonic() - hit[1] < self.META_TTL

    def _meta(self, key: str, default: str | None = None) -> str | None:
        hit = self._meta_cache.get(key)
        if self._live(hit):
            return hit[2] if hit[2] is not None else default
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        value = row["value"] if row else None
        self._meta_cache[key] = (_GEN[0], time.monotonic(), value)
        return value if value is not None else default

    def _set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))
        self.db.commit()
        _bump()

    # ---- me ----------------------------------------------------------------
    @property
    def is_set_up(self) -> bool:
        return (self.home / "identity.key").exists() and self._meta("name") is not None

    def setup(self, name: str, color: str | None = None) -> None:
        if not (self.home / "identity.key").exists():
            Identity.create().save(self.home / "identity.key")
        self._set_meta("name", name.strip() or "Learner")
        self._set_meta("color", color if color in COLORS else COLORS[0])
        self._identity = None

    @property
    def identity(self) -> Identity:
        if self._identity is None:
            self._identity = Identity.load(self.home / "identity.key")
        return self._identity

    @property
    def me(self) -> dict:
        out = {"id": self.identity.id, "name": self._meta("name", "Learner"), "color": self._meta("color", COLORS[0])}
        try:
            av = json.loads(self._meta("avatar", "") or "null")
        except ValueError:
            av = None
        if isinstance(av, dict):
            out["avatar"] = av
        return out

    def set_avatar(self, avatar: dict, color: str) -> None:
        """Your turtle (shell, scarf, skin, accessory). Your colour follows the shell."""
        self._set_meta("avatar", json.dumps(avatar, sort_keys=True))
        if color in COLORS:
            self._set_meta("color", color)

    def rename(self, name: str, color: str) -> None:
        self.setup(name, color)

    # ---- courses -----------------------------------------------------------
    def install_course(self, course: Course) -> Course:
        folder = self.home / "courses" / course.id
        if folder.exists():
            old = self.get_course(course.id)
            # Keep answers we already had if the new copy came without them.
            if old and old.answers and not course.answers:
                course.answers = old.answers
            import shutil
            shutil.rmtree(folder)
        save_course_folder(course, folder)
        self._courses.pop(course.id, None)
        self._no_course.pop(course.id, None)
        return self.get_course(course.id) or course

    def _course_stamp(self, folder: Path) -> str:
        """What the course's text files look like on disk: changes when any of them does."""
        parts = []
        for p in sorted(folder.rglob("*")):
            if p.is_file() and p.suffix in (".yaml", ".yml", ".md") and "files" not in p.relative_to(folder).parts[:1]:
                st = p.stat()
                parts.append(f"{p.relative_to(folder).as_posix()}:{st.st_mtime_ns}:{st.st_size}")
        return "|".join(parts)

    def get_course(self, course_id: str) -> Course | None:
        if course_id in self._courses:
            return self._courses[course_id]
        folder = self.home / "courses" / course_id
        if self._no_course.get(course_id, 0) > time.monotonic():
            return None  # asked for a course that isn't here, a moment ago (roadmaps name courses you don't have)
        if not (folder / "course.yaml").exists():
            self._no_course[course_id] = time.monotonic() + 2.0
            return None
        # v1.38: reading a course means parsing its YAML, slow in plain Python on a phone (a quarter of a second
        # each, 89 courses on one phone: most of a 30-second first Home). The parsed course is kept in the cache
        # folder and read back from there until one of its files changes.
        from . import __version__
        cache = self.home / "cache" / "courses" / f"{course_id}.pickle"
        stamp = f"{__version__}|{self._course_stamp(folder)}"
        try:
            with open(cache, "rb") as f:
                saved_stamp, c = pickle.load(f)
            if saved_stamp == stamp and isinstance(c, Course):
                self._courses[course_id] = c
                return c
        except Exception:
            pass
        try:
            c = load_course(files_from_folder(folder))
        except CourseError:
            return None
        self._courses[course_id] = c
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                pickle.dump((stamp, c), f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, cache)
        except Exception:
            pass
        return c

    def courses(self) -> list[Course]:
        out = []
        for p in sorted((self.home / "courses").iterdir()):
            if p.is_dir():
                c = self.get_course(p.name)
                if c:
                    out.append(c)
        return out

    def delete_course(self, course_id: str) -> None:
        import shutil
        folder = self.home / "courses" / course_id
        if folder.exists():
            shutil.rmtree(folder)
        if self.media_dir(course_id).exists():
            shutil.rmtree(self.media_dir(course_id))
        self._set_meta(f"media_root:{course_id}", "")
        self._courses.pop(course_id, None)

    def archive_course(self, course_id: str) -> None:
        """Delete a course you've started. Its signed history can't be erased (it's append-only and your
        checker may have it), so the progress is hidden instead, and the course and its own files are removed.
        Adding the course again later starts fresh."""
        self.db.execute("UPDATE journeys SET archived=1 WHERE course_id=?", (course_id,))
        self.db.commit()
        _bump()
        self._journey_of = None
        self.delete_course(course_id)

    # ---- the course's own files (videos, audio, pages) -----------------------
    # Two places are checked, in this order:
    #   1. files that came inside the course pack or were added in the editor: <home>/media/<course>/
    #   2. a folder on this computer the person pointed inPace to (big courses are never copied)
    def media_dir(self, course_id: str) -> Path:
        return self.home / "media" / course_id

    def media_root(self, course_id: str) -> Path | None:
        root = self._meta(f"media_root:{course_id}", "") or ""
        return Path(root) if root else None

    def set_media_root(self, course_id: str, folder: str) -> None:
        self._set_meta(f"media_root:{course_id}", str(Path(folder).expanduser()) if folder.strip() else "")

    def book_file(self, course_id: str) -> Path | None:
        """The learner's own copy of the course's book, if they showed inPace where it is."""
        p = self._meta(f"bookfile:{course_id}", "") or ""
        return Path(p) if p and Path(p).is_file() else None

    def set_book_file(self, course_id: str, path) -> None:
        self._set_meta(f"bookfile:{course_id}", str(path) if path else "")

    def find_media(self, course_id: str, ref: str) -> Path | None:
        """Where a course file is on this computer, or None.

        Full paths are tried as they are. Then each folder is searched for the path, and for shorter
        and shorter endings of it, so a course still works after its folder was moved or renamed."""
        from .course import is_full_path, local_ref, media_kind
        ref = local_ref(ref)
        if not ref or not media_kind(ref):
            return None
        c = self.get_course(course_id)
        if c and c.extra.get("book") and ref == c.extra["book"]:
            mine = self.book_file(course_id)
            if mine:
                return mine  # the learner's own copy, whatever its name
        want_dir = ref.endswith("/")

        def ok(p: Path) -> bool:
            return p.is_dir() if want_dir else p.is_file()
        if is_full_path(ref):
            p = Path(ref).expanduser()
            if ok(p):
                return p
        parts = [x for x in ref.split("/") if x and not re.match(r"^[A-Za-z]:$", x) and x != "~"]
        for root in (self.media_dir(course_id), self.media_root(course_id)):
            if not root or not root.is_dir():
                continue
            base = root.resolve()
            for i in range(len(parts)):
                try:
                    p = base.joinpath(*parts[i:]).resolve()
                    p.relative_to(base)  # stays inside the folder
                except (ValueError, OSError):
                    continue
                if ok(p):
                    return p
        # The chosen folder may keep the files one or more folders down ("DLS Slides/DLS_C1/C1_W1.pdf"):
        # look for the file by its name inside it.
        root = self.media_root(course_id)
        if root and root.is_dir() and parts and not want_dir:
            hit = _names_in(root).get(parts[-1].lower())
            if hit and hit.is_file():
                return hit
        return None

    def missing_media(self, course) -> list[str]:
        from .media import media_refs
        refs = set()
        for m in course.modules:
            for les in m["lessons"]:
                refs |= media_refs(les)
        return sorted(r for r in refs if not self.find_media(course.id, r))

    # ---- journeys ----------------------------------------------------------
    def start_journey(self, course_id: str) -> str:
        existing = self.db.execute(
            "SELECT id FROM journeys WHERE course_id=? AND archived=0", (course_id,)
        ).fetchone()
        if existing:
            return existing["id"]
        started = now_utc()
        n = self.db.execute("SELECT COUNT(*) AS n FROM journeys WHERE course_id=?", (course_id,)).fetchone()["n"]
        jid = fingerprint({"learner": self.identity.id, "course": course_id, "started": started, "n": n})[:16]
        self.db.execute("INSERT INTO journeys (id, course_id, started_at) VALUES (?,?,?)", (jid, course_id, started))
        self._journey_of = None
        self.db.commit()
        _bump()
        self.add_event(jid, "journey_started", {"course": course_id})
        return jid

    def journeys(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM journeys WHERE archived=0 ORDER BY started_at").fetchall()
        return [dict(r) for r in rows]

    def _journeys_now(self) -> dict:
        """Every journey by id, read once per write (v1.38: progress() asks for the journey on every call)."""
        hit = self._journeys_cache
        if hit and hit[0] == _GEN[0] and time.monotonic() - hit[1] < self.META_TTL:
            return hit[2]
        rows = {r["id"]: dict(r) for r in self.db.execute("SELECT * FROM journeys").fetchall()}
        self._journeys_cache = (_GEN[0], time.monotonic(), rows)
        return rows

    def journey(self, jid: str) -> dict | None:
        r = self._journeys_now().get(jid)
        return dict(r) if r else None

    def journey_for_course(self, course_id: str) -> str | None:
        # v1.38: asked once per course per roadmap on Home and Roadmaps (thousands of times with many courses);
        # one query fills the map, kept until a course is started or archived.
        if self._journey_of is None:
            rows = self.db.execute("SELECT id, course_id FROM journeys WHERE archived=0").fetchall()
            self._journey_of = {r["course_id"]: r["id"] for r in rows}
        return self._journey_of.get(course_id)

    # ---- events --------------------------------------------------------------
    def add_event(self, journey: str, type_: str, data: dict) -> None:
        self.db.execute(
            "INSERT INTO events (journey, type, data, at) VALUES (?,?,?,?)",
            (journey, type_, json.dumps(data, ensure_ascii=False), now_utc()),
        )
        self.db.commit()
        _bump()
        self._progress_cache.pop(journey, None)
        _bump()

    def events(self, journey: str, after_seq: int = 0) -> list[dict]:
        hit = self._events_cache.get(journey)
        if self._live(hit):
            evs = hit[2]
        else:
            rows = self.db.execute("SELECT * FROM events WHERE journey=? ORDER BY seq", (journey,)).fetchall()
            evs = [{"seq": r["seq"], "type": r["type"], "data": json.loads(r["data"]), "at": r["at"]} for r in rows]
            self._events_cache[journey] = (_GEN[0], time.monotonic(), evs)
        out = [e for e in evs if e["seq"] > after_seq] if after_seq else list(evs)
        return [dict(e) for e in out]  # callers may add to an event; the kept list stays as it was

    def save_evidence(self, journey: str, req_id: str, filename: str, content: bytes, task: str = "") -> str:
        digest = sha256_hex(content)
        folder = self.home / "evidence" / digest[:2]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / digest).write_bytes(content)
        safe_name = Path(filename or "file").name[:120]
        self.add_event(journey, "evidence_added", {"req": req_id, "task": task, "name": safe_name,
                                                   "sha256": digest, "size": len(content)})
        return digest

    # ---- progress (everything is calculated from events) --------------------
    def progress(self, journey: str) -> dict:
        """Where you are in a course. Computed from every event of the journey, so it's kept (v1.36.1): pages
        like Home ask for the same course's progress many times (once per roadmap it's on), and each time used
        to walk and date-parse the whole history. The copy is dropped when an event is added or the course
        changes; a caller gets its own copy, so what it does to it can't leak into the next page."""
        j = self.journey(journey)
        course = self.get_course(j["course_id"]) if j else None
        ls = self._last_seq
        if not (ls and ls[0] == _GEN[0] and time.monotonic() - ls[1] < self.META_TTL):
            rows = self.db.execute("SELECT journey, MAX(seq) AS last FROM events GROUP BY journey").fetchall()
            ls = self._last_seq = (_GEN[0], time.monotonic(), {r["journey"]: r["last"] for r in rows})
        last = ls[2].get(journey, 0)
        key = (last, course.hash if course else "", bool(j and j.get("archived")))
        hit = self._progress_cache.get(journey)
        if hit and hit[0] == key:
            return _copy_progress(hit[1])
        out = None
        skey = json.dumps(key)
        if course is not None:  # v1.38: kept in the database too, so a fresh start doesn't work it all out again
            try:
                row = self.db.execute("SELECT key, data FROM progress_cache WHERE journey=?", (journey,)).fetchone()
                if row and row["key"] == skey:
                    out = pickle.loads(row["data"])
                    out["course"] = course
            except Exception:
                out = None
        if out is None:
            out = self._progress_uncached(journey, j, course)
            if course is not None:
                try:
                    data = pickle.dumps({k: v for k, v in out.items() if k != "course"}, protocol=pickle.HIGHEST_PROTOCOL)
                    self.db.execute("INSERT OR REPLACE INTO progress_cache VALUES (?,?,?)", (journey, skey, data))
                    self.db.commit()
                    _bump()
                except Exception:
                    pass
        self._progress_cache[journey] = (key, _copy_progress(out))
        return out

    def _progress_uncached(self, journey: str, j, course) -> dict:
        evs = self.events(journey)
        done_lessons = {e["data"]["lesson"] for e in evs if e["type"] == "lesson_done"}
        opened = {e["data"].get("lesson") for e in evs if e["type"] == "lesson_opened"}
        evidence: dict[str, list] = {}
        writeups: dict[str, dict] = {}
        quizzes: dict[str, dict] = {}
        exams_taken: dict[str, dict] = {}
        for e in evs:
            d = e["data"]
            if e["type"] == "exam_taken":
                exams_taken[d["req"]] = d
            if e["type"] == "evidence_added":
                evidence.setdefault(d["req"], []).append(d)
            elif e["type"] == "writeup_saved":
                writeups[d["req"]] = d
            elif e["type"] == "quiz_taken":
                best = quizzes.get(d["req"])
                if not best or d["percent"] > best["percent"]:
                    quizzes[d["req"]] = d

        modules, unlocked, next_step = [], True, None
        total_lessons = done_count = 0
        for m in course.modules if course else []:
            reqs = []
            for r in m["requires"]:
                if r["type"] == "practical":
                    ok = bool(evidence.get(r["id"]))
                elif r["type"] == "explain":
                    ok = writeups.get(r["id"], {}).get("words", 0) >= r.get("min_words", 40)
                else:
                    # A practice pass, or a verified exam taken (graded by the checker).
                    ok = (quizzes.get(r["id"], {}).get("percent", 0) >= r.get("pass", 70)
                          or r["id"] in exams_taken)
                reqs.append({**r, "done": ok, "evidence": evidence.get(r["id"], []),
                             "writeup": writeups.get(r["id"]), "quiz": quizzes.get(r["id"]),
                             "exam_taken": exams_taken.get(r["id"])})
            lessons = [{**{k: v for k, v in les.items() if k != "content"}, "done": les["id"] in done_lessons,
                        "opened": les["id"] in opened} for les in m["lessons"]]
            # Optional lessons and tasks can be done (and show as done), but the module doesn't wait for them,
            # and they don't count in the lessons and percent totals.
            need = [les for les in lessons if not les.get("optional")]
            ldone = sum(1 for les in need if les["done"])
            total_lessons += len(need)
            done_count += ldone
            complete = ldone == len(need) and all(r["done"] for r in reqs if not r.get("optional"))
            status = "done" if complete else ("open" if unlocked else "locked")
            if status == "open" and next_step is None:
                nxt = lesson_ahead(lessons)
                if nxt:
                    next_step = {"kind": "lesson", "id": nxt["id"], "title": nxt["title"], "module": m["title"], "mid": m["id"],
                                 "optional": bool(nxt.get("optional"))}
                else:
                    # Every required lesson is done here (lesson_ahead never passes one over), so a task is left.
                    r = next(r for r in reqs if not r["done"] and not r.get("optional"))
                    next_step = {"kind": "requirement", "id": r["id"], "title": r["prompt"], "module": m["title"],
                                 "mid": m["id"], "lesson": lessons[-1]["id"]}
            modules.append({"id": m["id"], "title": m["title"], "lessons": lessons, "requires": reqs,
                            "status": status, "lessons_done": ldone, "lessons_needed": len(need)})
            unlocked = unlocked and complete

        mods_done = sum(1 for m in modules if m["status"] == "done")
        units = total_lessons + sum(1 for m in modules for r in m["requires"] if not r.get("optional"))
        units_done = done_count + sum(1 for m in modules for r in m["requires"] if r["done"] and not r.get("optional"))
        return {
            "course": course,
            "modules": modules,
            "lessons_total": total_lessons,
            "lessons_done": done_count,
            "modules_total": len(modules),
            "modules_done": mods_done,
            "percent": round(100 * units_done / units) if units else 0,
            "finished": bool(modules) and mods_done == len(modules),
            "next": next_step,
            "minutes": active_minutes(evs),
            "current_module": next((m for m in modules if m["status"] == "open"), None),
        }

    # ---- notes (v1.25) -----------------------------------------------------
    # Your own notes on lessons, often on a sentence you selected. They're private: they stay in vault.db (so they're
    # in your backups) and never go into milestones, progress files or shared courses.
    NOTE_QUOTE_MAX, NOTE_TEXT_MAX = 2000, 10000

    def notes(self, course_id: str, lesson: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM notes WHERE course=?", [course_id]
        if lesson is not None:
            sql += " AND lesson=?"
            args.append(lesson)
        return [dict(r) for r in self.db.execute(sql + " ORDER BY created_at, rowid", args).fetchall()]

    def note_counts(self, course_id: str) -> dict[str, int]:
        rows = self.db.execute("SELECT lesson, COUNT(*) AS n FROM notes WHERE course=? GROUP BY lesson", (course_id,))
        return {r["lesson"]: r["n"] for r in rows.fetchall()}

    def note(self, nid: str) -> dict | None:
        row = self.db.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
        return dict(row) if row else None

    def add_note(self, course_id: str, lesson: str, journey: str, quote: str = "", text: str = "") -> dict:
        quote = " ".join(str(quote or "").split())[:self.NOTE_QUOTE_MAX]
        text = str(text or "").strip()[:self.NOTE_TEXT_MAX]
        if not quote and not text:
            raise ValueError("Write a note, or select some of the lesson first.")
        now = now_utc()
        n = {"id": secrets.token_hex(8), "course": course_id, "lesson": lesson, "journey": journey, "quote": quote,
             "text": text, "created_at": now, "updated_at": now}
        self.db.execute("INSERT INTO notes VALUES (:id, :course, :lesson, :journey, :quote, :text, :created_at, :updated_at)", n)
        self.db.commit()
        _bump()
        return n

    def edit_note(self, nid: str, text: str) -> None:
        text = str(text or "").strip()[:self.NOTE_TEXT_MAX]
        n = self.note(nid)
        if n and not text and not n["quote"]:
            raise ValueError("A note needs some text.")
        self.db.execute("UPDATE notes SET text=?, updated_at=? WHERE id=?", (text, now_utc(), nid))
        self.db.commit()
        _bump()

    def delete_note(self, nid: str) -> None:
        self.db.execute("DELETE FROM notes WHERE id=?", (nid,))
        self.db.commit()
        _bump()

    # ---- milestones --------------------------------------------------------
    def milestones(self, journey: str) -> list[dict]:
        hit = self._milestones_cache.get(journey)
        if self._live(hit):
            return [dict(m) for m in hit[2]]
        rows = self.db.execute("SELECT * FROM milestones WHERE journey=? ORDER BY seq", (journey,)).fetchall()
        out = []
        for r in rows:
            out.append({"seq": r["seq"], "hash": r["hash"], "sig": r["sig"], "body": json.loads(r["body"]),
                        "approvals": self.approvals_for(r["hash"])})
        self._milestones_cache[journey] = (_GEN[0], time.monotonic(), out)
        return [dict(m) for m in out]

    def last_event_in_milestones(self, journey: str) -> int:
        ms = self.milestones(journey)
        return ms[-1]["body"]["last_event"] if ms else 0

    def has_new_activity(self, journey: str) -> bool:
        return any(e["type"] != "journey_started" for e in self.events(journey, self.last_event_in_milestones(journey)))

    def create_milestone(self, journey: str) -> dict | None:
        new_events = self.events(journey, self.last_event_in_milestones(journey))
        if not new_events:
            return None
        ms = self.milestones(journey)
        prog = self.progress(journey)
        course: Course = prog["course"]
        j = self.journey(journey)
        body = {
            "kind": "milestone",
            "v": 1,
            "learner": self.identity.id,
            "journey": journey,
            "journey_started": j["started_at"],
            "seq": len(ms) + 1,
            "prev": ms[-1]["hash"] if ms else "",
            "course": {"id": course.id, "title": course.title, "version": course.version, "hash": course.hash},
            "events": new_events,
            "last_event": new_events[-1]["seq"],
            "summary": {
                "percent": prog["percent"],
                "lessons_done": prog["lessons_done"],
                "lessons_total": prog["lessons_total"],
                "modules_done": prog["modules_done"],
                "modules_total": prog["modules_total"],
                "minutes": active_minutes(new_events),
            },
            "created_at": now_utc(),
        }
        import os as _os
        if _os.environ.get("INPACE_HOSTED"):  # made in a shared inPace (host mode): say so, inside what's signed
            body["server"] = {"name": _os.environ.get("INPACE_HOST_NAME", "")[:80]}
        h = fingerprint(body)
        sig = self.identity.sign({"kind": "milestone", "hash": h})
        self.db.execute("INSERT INTO milestones VALUES (?,?,?,?,?)",
                        (journey, body["seq"], h, json.dumps(body, ensure_ascii=False), sig))
        self.db.commit()
        _bump()
        return {"seq": body["seq"], "hash": h, "body": body, "sig": sig}

    def approvals_for(self, milestone_hash: str) -> list[dict]:
        rows = self.db.execute("SELECT * FROM approvals WHERE milestone=? ORDER BY at", (milestone_hash,)).fetchall()
        out = []
        for r in rows:
            p = self.person(r["checker"])
            out.append({**dict(r), "checker_name": display_name(p) if p else "Unknown"})
        return out

    def check_my_chain(self, journey: str) -> list[str]:
        """Re-check my own milestones. Returns plain-language problems."""
        from .exchange import check_chain
        ms = self.milestones(journey)
        key = tuple((m["hash"], m["sig"]) for m in ms)
        hit = self._chain_ok.get(journey)
        if hit and hit[0] == key:  # the same milestones check out the same way (v1.38: no signature maths per page)
            return list(hit[1])
        out = check_chain([{"body": m["body"], "hash": m["hash"], "sig": m["sig"]} for m in ms])
        self._chain_ok[journey] = (key, out)
        return list(out)

    # ---- people --------------------------------------------------------------
    def people(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM people ORDER BY name").fetchall()]

    def person(self, pid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM people WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None

    def update_person_extras(self, pid: str, avatar: str = "", island: str = "") -> None:
        """Newer files from someone bring their newest turtle and island (only what they sent is changed)."""
        if avatar:
            self.db.execute("UPDATE people SET avatar=? WHERE id=?", (avatar, pid))
        if island:
            self.db.execute("UPDATE people SET island=? WHERE id=?", (island, pid))
        self.db.commit()
        _bump()

    def add_person(self, pid: str, name: str, color: str, checks_me: bool, i_check: bool, avatar: str = "",
                   island: str = "") -> None:
        old = self.person(pid)
        if old:
            self.db.execute(
                "UPDATE people SET name=?, color=?, checks_me=?, i_check=?, avatar=? WHERE id=?",
                (name, color, int(checks_me or old["checks_me"]), int(i_check or old["i_check"]),
                 avatar or old["avatar"] or "", pid),
            )
        else:
            self.db.execute("INSERT INTO people (id, name, color, nickname, checks_me, i_check, added_at, avatar) "
                            "VALUES (?,?,?,?,?,?,?,?)",
                            (pid, name, color, "", int(checks_me), int(i_check), now_utc(), avatar or ""))
        self.update_person_extras(pid, island=island)

    def set_roles(self, pid: str, checks_me: bool, i_check: bool, nickname: str) -> None:
        self.db.execute("UPDATE people SET checks_me=?, i_check=?, nickname=? WHERE id=?",
                        (int(checks_me), int(i_check), nickname.strip(), pid))
        self.db.commit()
        _bump()

    def remove_person(self, pid: str) -> None:
        self.db.execute("DELETE FROM people WHERE id=?", (pid,))
        self.db.commit()
        _bump()

    def my_checkers(self) -> list[dict]:
        return [p for p in self.people() if p["checks_me"]]

    # ---- checker side ----------------------------------------------------------
    def store_received(self, data: dict) -> None:
        self.db.execute("INSERT OR REPLACE INTO received VALUES (?,?,?,?,?)",
                        (data["learner"]["id"], data["journey"]["id"], data["journey"]["course"]["title"],
                         json.dumps(data, ensure_ascii=False), now_utc()))
        self.db.commit()
        _bump()

    def received(self, learner: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM received", ()
        if learner:
            q, args = q + " WHERE learner=?", (learner,)
        rows = self.db.execute(q + " ORDER BY received_at DESC", args).fetchall()
        return [{**dict(r), "data": json.loads(r["data"])} for r in rows]

    def received_one(self, learner: str, journey: str) -> dict | None:
        r = self.db.execute("SELECT * FROM received WHERE learner=? AND journey=?", (learner, journey)).fetchone()
        return {**dict(r), "data": json.loads(r["data"])} if r else None

    def receipts(self, learner: str, journey: str) -> list[dict]:
        rows = self.db.execute("SELECT * FROM receipts WHERE learner=? AND journey=? ORDER BY seq, at",
                               (learner, journey)).fetchall()
        return [dict(r) for r in rows]

    def add_receipt(self, learner: str, journey: str, seq: int, h: str, decision: str, note: str, at: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO receipts VALUES (?,?,?,?,?,?,?)",
                        (learner, journey, seq, h, decision, note, at))
        self.db.commit()
        _bump()

    def waiting_count(self, learner: str) -> int:
        total = 0
        for r in self.received(learner):
            approved = {x["seq"] for x in self.receipts(learner, r["journey"]) if x["decision"] == "approved"}
            total += sum(1 for m in r["data"]["milestones"] if m["body"]["seq"] not in approved)
        return total


def display_name(p: dict | None) -> str:
    if not p:
        return "Unknown"
    return p.get("nickname") or p.get("name") or "Someone"


def _copy_progress(p: dict) -> dict:
    """A copy of a progress dict that shares the (unchanging) Course object and copies everything else."""
    import copy
    return {k: (v if k == "course" else copy.deepcopy(v)) for k, v in p.items()}


def active_minutes(events: list[dict]) -> int:
    """Time between activities, counting only gaps under 30 minutes.
    It's the learner's own count, shown as such."""
    from datetime import datetime
    times = sorted(datetime.strptime(e["at"], "%Y-%m-%dT%H:%M:%SZ") for e in events)
    total = 0.0
    for a, b in zip(times, times[1:]):
        gap = (b - a).total_seconds() / 60
        if gap <= SESSION_GAP_MIN:
            total += gap
    return int(total)


def verify_signature(person_id: str, data: Any, sig: str) -> bool:
    return verify(person_id, data, sig)
