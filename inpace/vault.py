"""The vault: one folder holding everything for one person.

    inPace/
      vault.db        events, milestones, approvals, people, receipts
      identity.key    your private signing key (never share)
      courses/<id>/   installed courses
      evidence/       your work files, named by fingerprint
"""
from __future__ import annotations

import json
import re
import os
import sqlite3
from pathlib import Path
from typing import Any

from .canon import fingerprint, now_utc, sha256_hex
from .course import Course, CourseError, files_from_folder, load_course, save_course_folder
from .identity import Identity, verify

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
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


class Vault:
    def __init__(self, home: Path | None = None):
        self.home = Path(home or default_home())
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "courses").mkdir(exist_ok=True)
        (self.home / "evidence").mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.home / "vault.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(people)")}
        for col in ("avatar", "island"):
            # v1.17: people can have a turtle (from their contact card) instead of a coloured letter,
            # and a copy of their island that they chose to share
            if col not in cols:
                self.db.execute(f"ALTER TABLE people ADD COLUMN {col} TEXT DEFAULT ''")
                self.db.commit()
        self._courses: dict[str, Course] = {}
        self._identity: Identity | None = None

    # ---- small helpers ---------------------------------------------------
    def _meta(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def _set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))
        self.db.commit()

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
        return self.get_course(course.id) or course

    def get_course(self, course_id: str) -> Course | None:
        if course_id in self._courses:
            return self._courses[course_id]
        folder = self.home / "courses" / course_id
        if not (folder / "course.yaml").exists():
            return None
        try:
            c = load_course(files_from_folder(folder))
        except CourseError:
            return None
        self._courses[course_id] = c
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
        self.db.commit()
        self.add_event(jid, "journey_started", {"course": course_id})
        return jid

    def journeys(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM journeys WHERE archived=0 ORDER BY started_at").fetchall()
        return [dict(r) for r in rows]

    def journey(self, jid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM journeys WHERE id=?", (jid,)).fetchone()
        return dict(r) if r else None

    def journey_for_course(self, course_id: str) -> str | None:
        r = self.db.execute("SELECT id FROM journeys WHERE course_id=? AND archived=0", (course_id,)).fetchone()
        return r["id"] if r else None

    # ---- events --------------------------------------------------------------
    def add_event(self, journey: str, type_: str, data: dict) -> None:
        self.db.execute(
            "INSERT INTO events (journey, type, data, at) VALUES (?,?,?,?)",
            (journey, type_, json.dumps(data, ensure_ascii=False), now_utc()),
        )
        self.db.commit()

    def events(self, journey: str, after_seq: int = 0) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM events WHERE journey=? AND seq>? ORDER BY seq", (journey, after_seq)
        ).fetchall()
        return [{"seq": r["seq"], "type": r["type"], "data": json.loads(r["data"]), "at": r["at"]} for r in rows]

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
        j = self.journey(journey)
        course = self.get_course(j["course_id"]) if j else None
        evs = self.events(journey)
        done_lessons = {e["data"]["lesson"] for e in evs if e["type"] == "lesson_done"}
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
            lessons = [{**{k: v for k, v in les.items() if k != "content"}, "done": les["id"] in done_lessons}
                       for les in m["lessons"]]
            ldone = sum(1 for les in lessons if les["done"])
            total_lessons += len(lessons)
            done_count += ldone
            # Optional tasks can be done (and show as done), but the module doesn't wait for them.
            complete = ldone == len(lessons) and all(r["done"] for r in reqs if not r.get("optional"))
            status = "done" if complete else ("open" if unlocked else "locked")
            if status == "open" and next_step is None:
                nxt = next((les for les in lessons if not les["done"]), None)
                if nxt:
                    next_step = {"kind": "lesson", "id": nxt["id"], "title": nxt["title"], "module": m["title"], "mid": m["id"]}
                else:
                    r = next(r for r in reqs if not r["done"] and not r.get("optional"))
                    next_step = {"kind": "requirement", "id": r["id"], "title": r["prompt"], "module": m["title"],
                                 "mid": m["id"], "lesson": lessons[-1]["id"]}
            modules.append({"id": m["id"], "title": m["title"], "lessons": lessons, "requires": reqs,
                            "status": status, "lessons_done": ldone})
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

    # ---- milestones --------------------------------------------------------
    def milestones(self, journey: str) -> list[dict]:
        rows = self.db.execute("SELECT * FROM milestones WHERE journey=? ORDER BY seq", (journey,)).fetchall()
        out = []
        for r in rows:
            out.append({"seq": r["seq"], "hash": r["hash"], "sig": r["sig"], "body": json.loads(r["body"]),
                        "approvals": self.approvals_for(r["hash"])})
        return out

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
        h = fingerprint(body)
        sig = self.identity.sign({"kind": "milestone", "hash": h})
        self.db.execute("INSERT INTO milestones VALUES (?,?,?,?,?)",
                        (journey, body["seq"], h, json.dumps(body, ensure_ascii=False), sig))
        self.db.commit()
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
        return check_chain([{"body": m["body"], "hash": m["hash"], "sig": m["sig"]} for m in ms])

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

    def remove_person(self, pid: str) -> None:
        self.db.execute("DELETE FROM people WHERE id=?", (pid,))
        self.db.commit()

    def my_checkers(self) -> list[dict]:
        return [p for p in self.people() if p["checks_me"]]

    # ---- checker side ----------------------------------------------------------
    def store_received(self, data: dict) -> None:
        self.db.execute("INSERT OR REPLACE INTO received VALUES (?,?,?,?,?)",
                        (data["learner"]["id"], data["journey"]["id"], data["journey"]["course"]["title"],
                         json.dumps(data, ensure_ascii=False), now_utc()))
        self.db.commit()

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
