"""The vault: one folder holding everything for one person.

    inPace/
      vault.db        events, milestones, approvals, people, receipts
      identity.key    your private signing key (never share)
      courses/<id>/   installed courses
      evidence/       your work files, named by fingerprint
"""
from __future__ import annotations

import json
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
        return {"id": self.identity.id, "name": self._meta("name", "Learner"), "color": self._meta("color", COLORS[0])}

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
        self._courses.pop(course_id, None)

    # ---- journeys ----------------------------------------------------------
    def start_journey(self, course_id: str) -> str:
        existing = self.db.execute(
            "SELECT id FROM journeys WHERE course_id=? AND archived=0", (course_id,)
        ).fetchone()
        if existing:
            return existing["id"]
        started = now_utc()
        jid = fingerprint({"learner": self.identity.id, "course": course_id, "started": started})[:16]
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
        for e in evs:
            d = e["data"]
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
                    ok = quizzes.get(r["id"], {}).get("percent", 0) >= r.get("pass", 70)
                reqs.append({**r, "done": ok, "evidence": evidence.get(r["id"], []),
                             "writeup": writeups.get(r["id"]), "quiz": quizzes.get(r["id"])})
            lessons = [{**{k: v for k, v in les.items() if k != "content"}, "done": les["id"] in done_lessons}
                       for les in m["lessons"]]
            ldone = sum(1 for les in lessons if les["done"])
            total_lessons += len(lessons)
            done_count += ldone
            complete = ldone == len(lessons) and all(r["done"] for r in reqs)
            status = "done" if complete else ("open" if unlocked else "locked")
            if status == "open" and next_step is None:
                nxt = next((les for les in lessons if not les["done"]), None)
                if nxt:
                    next_step = {"kind": "lesson", "id": nxt["id"], "title": nxt["title"], "module": m["title"]}
                else:
                    r = next(r for r in reqs if not r["done"])
                    next_step = {"kind": "requirement", "id": r["id"], "title": r["prompt"], "module": m["title"],
                                 "lesson": lessons[-1]["id"]}
            modules.append({"id": m["id"], "title": m["title"], "lessons": lessons, "requires": reqs,
                            "status": status, "lessons_done": ldone})
            unlocked = unlocked and complete

        mods_done = sum(1 for m in modules if m["status"] == "done")
        units = total_lessons + sum(len(m["requires"]) for m in modules)
        units_done = done_count + sum(1 for m in modules for r in m["requires"] if r["done"])
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

    def add_person(self, pid: str, name: str, color: str, checks_me: bool, i_check: bool) -> None:
        old = self.person(pid)
        if old:
            self.db.execute(
                "UPDATE people SET name=?, color=?, checks_me=?, i_check=? WHERE id=?",
                (name, color, int(checks_me or old["checks_me"]), int(i_check or old["i_check"]), pid),
            )
        else:
            self.db.execute("INSERT INTO people VALUES (?,?,?,?,?,?,?)",
                            (pid, name, color, "", int(checks_me), int(i_check), now_utc()))
        self.db.commit()

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
