"""Stronger proof: verified exams, private questions, file requests, and extra checks.

Verified exams
  The checker's app builds the exam (it has the answers), signs it and sends it.
  The learner takes it offline. Their answers travel back inside a milestone,
  and the checker's app grades them with the answer key it kept.
"""
from __future__ import annotations

import difflib
import io
import json
import random
import secrets
import zipfile
from typing import Any

from .canon import fingerprint, now_utc, sha256_hex
from .course import Course, course_outline
from .exam import _rank, build_exam
from .exchange import FileProblem, check_chain
from .identity import verify
from .vault import Vault, display_name

APP_VERSION = 1


def _unsigned(d: dict, field: str = "sig") -> dict:
    return {k: v for k, v in d.items() if k != field}


# ---------------------------------------------------------------------------
# Private questions (kept only on the checker's computer)
# ---------------------------------------------------------------------------

def add_private_question(v: Vault, course_id: str, text: str, right: str, wrong: list[str]) -> str:
    wrong = [w.strip() for w in wrong if w.strip()]
    if not text.strip() or not right.strip() or len(wrong) < 1:
        raise ValueError("A question needs text, one right answer and at least one wrong answer.")
    qid = "p-" + secrets.token_hex(4)
    data = {"text": text.strip(), "right": right.strip(), "wrong": wrong}
    v.db.execute("INSERT INTO private_questions VALUES (?,?,?,?)", (course_id, qid, json.dumps(data), now_utc()))
    v.db.commit()
    return qid


def private_questions(v: Vault, course_id: str) -> list[dict]:
    rows = v.db.execute("SELECT * FROM private_questions WHERE course=? ORDER BY created_at", (course_id,)).fetchall()
    return [{"id": r["id"], **json.loads(r["data"])} for r in rows]


def delete_private_question(v: Vault, course_id: str, qid: str) -> None:
    v.db.execute("DELETE FROM private_questions WHERE course=? AND id=?", (course_id, qid))
    v.db.commit()


# ---------------------------------------------------------------------------
# Verified exams
# ---------------------------------------------------------------------------

def earlier_quiz_questions(course: Course, req_id: str) -> list[str]:
    """Questions from quizzes in modules before the one this exam is for."""
    out = []
    for m in course.modules:
        if any(r["id"] == req_id for r in m["requires"]):
            break
        for r in m["requires"]:
            if r["type"] == "quiz":
                out += r["questions"]
    return out


def make_exam(v: Vault, data: dict, course: Course, req_id: str, private_ids: list[str],
              surprise: bool) -> dict:
    """data = the learner's progress file (already stored by the checker)."""
    if not course.answers:
        raise FileProblem("Your copy of this course has no answers. Add the version with answers first.")
    found = course.find_requirement(req_id)
    if not found or found[1]["type"] != "quiz":
        raise FileProblem("That quiz wasn't found in your copy of the course.")
    module, req = found
    seed = secrets.token_hex(8)
    qids = list(req["questions"])
    surprise_id = None
    if surprise:
        pool = [q for q in earlier_quiz_questions(course, req_id) if q not in qids]
        if pool:
            surprise_id = random.SystemRandom().choice(pool)
            qids.append(surprise_id)
    items = build_exam(course, qids, seed)
    key = {}
    for it in items:
        right = set(course.answers[it["id"]]["right"])
        key[it["id"]] = next(c["id"] for c in it["choices"] if c["id"] in right)
        if it["id"] == surprise_id:
            it["note"] = "From an earlier module"
    bank = {q["id"]: q for q in private_questions(v, course.id)}
    for pid in private_ids:
        q = bank.get(pid)
        if not q:
            continue
        opts = [("r", q["right"])] + [(f"w{i}", w) for i, w in enumerate(q["wrong"][:5])]
        shown = sorted(opts, key=lambda o: _rank(seed, pid, o[0]))
        choices = [{"id": f"{pid}-{o[0]}", "text": o[1]} for o in shown]
        items.append({"id": pid, "text": q["text"], "choices": choices, "note": "A question from your checker"})
        key[pid] = f"{pid}-r"

    exam = {
        "inpace": "exam", "v": APP_VERSION, "id": "x-" + secrets.token_hex(8),
        "checker": v.me, "learner": data["learner"]["id"], "journey": data["journey"]["id"],
        "course": {"id": course.id, "title": course.title, "hash": course.hash},
        "req": req_id, "task": module["title"], "pass": req.get("pass", 70),
        "questions": items, "created_at": now_utc(),
    }
    exam["sig"] = v.identity.sign(_unsigned(exam))
    v.db.execute("INSERT INTO sent_exams VALUES (?,?,?,?,?,?,?)",
                 (exam["id"], exam["learner"], exam["journey"], req_id, json.dumps(exam), json.dumps(key),
                  exam["created_at"]))
    v.db.commit()
    return exam


def sent_exams(v: Vault, learner: str, journey: str) -> list[dict]:
    rows = v.db.execute("SELECT * FROM sent_exams WHERE learner=? AND journey=? ORDER BY created_at",
                        (learner, journey)).fetchall()
    return [{"id": r["id"], "req": r["req"], "exam": json.loads(r["exam"]), "created_at": r["created_at"]}
            for r in rows]


def grade_exam_event(v: Vault, d: dict) -> dict | None:
    """Checker side: grade an exam_taken event with the key we kept."""
    r = v.db.execute("SELECT * FROM sent_exams WHERE id=?", (d.get("exam"),)).fetchone()
    if not r:
        return None
    exam, key = json.loads(r["exam"]), json.loads(r["key"])
    answers = d.get("answers") or {}
    details, score = [], 0
    for q in exam["questions"]:
        ok = answers.get(q["id"]) == key[q["id"]]
        score += ok
        pick = next((c["text"] for c in q["choices"] if c["id"] == answers.get(q["id"])), "No answer")
        details.append({"text": q["text"], "ok": ok, "chosen": pick, "note": q.get("note", "")})
    total = len(exam["questions"])
    pct = round(100 * score / total) if total else 0
    return {"exam": exam["id"], "score": score, "total": total, "percent": pct,
            "passed": pct >= exam["pass"], "details": details}


def import_exam(v: Vault, exam: dict) -> dict:
    """Learner side."""
    checker = exam.get("checker", {})
    if exam.get("learner") != v.identity.id:
        raise FileProblem("This exam is meant for someone else.")
    p = v.person(checker.get("id", ""))
    if not p or not p["checks_me"]:
        raise FileProblem(f"This exam is from {checker.get('name', 'someone')}, who isn't one of your checkers.")
    if not verify(checker["id"], _unsigned(exam), exam.get("sig", "")):
        raise FileProblem("This exam file has been changed or is damaged. Ask for a new one.")
    if not v.journey(exam["journey"]):
        raise FileProblem("This exam is for a course you haven't started on this computer.")
    v.db.execute("INSERT OR IGNORE INTO my_exams VALUES (?,?,?,?,?,?)",
                 (exam["id"], checker["id"], exam["journey"], exam["req"], json.dumps(exam), now_utc()))
    v.db.commit()
    return {"name": display_name(p), "task": exam["task"], "count": len(exam["questions"])}


def my_exams(v: Vault, journey: str) -> list[dict]:
    taken = {e["data"]["exam"] for e in v.events(journey) if e["type"] == "exam_taken"}
    rows = v.db.execute("SELECT * FROM my_exams WHERE journey=? ORDER BY received_at", (journey,)).fetchall()
    out = []
    for r in rows:
        exam = json.loads(r["data"])
        res = v.db.execute("SELECT * FROM exam_results WHERE exam=?", (exam["id"],)).fetchone()
        p = v.person(r["checker"])
        out.append({"exam": exam, "taken": exam["id"] in taken, "result": dict(res) if res else None,
                    "checker_name": display_name(p)})
    return out


def get_my_exam(v: Vault, exam_id: str) -> dict | None:
    r = v.db.execute("SELECT data FROM my_exams WHERE id=?", (exam_id,)).fetchone()
    return json.loads(r["data"]) if r else None


# ---------------------------------------------------------------------------
# File requests and file packs
# ---------------------------------------------------------------------------

def evidence_in(data: dict) -> dict[str, dict]:
    """Every file fingerprint the learner's milestones mention."""
    out = {}
    for m in data["milestones"]:
        for e in m["body"]["events"]:
            if e["type"] == "evidence_added":
                out[e["data"]["sha256"]] = e["data"]
    return out


def requests_for(v: Vault, journey: str) -> list[dict]:
    rows = v.db.execute("SELECT * FROM file_requests WHERE journey=? ORDER BY at", (journey,)).fetchall()
    return [{**dict(r), "checker_name": display_name(v.person(r["checker"]))} for r in rows]


def make_file_pack(v: Vault, journey: str) -> bytes:
    reqs = requests_for(v, journey)
    if not reqs:
        raise FileProblem("Nobody has asked for files yet.")
    files = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        seen = set()
        for r in reqs:
            if r["sha256"] in seen:
                continue
            seen.add(r["sha256"])
            p = v.home / "evidence" / r["sha256"][:2] / r["sha256"]
            if not p.exists():
                continue
            zf.writestr(f"files/{r['sha256']}", p.read_bytes())
            files.append({"sha256": r["sha256"], "name": r["name"]})
        manifest = {"inpace": "files", "v": APP_VERSION, "learner": v.me, "journey": journey,
                    "files": files, "created_at": now_utc()}
        manifest["sig"] = v.identity.sign(_unsigned(manifest))
        zf.writestr("inpace-files.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    return buf.getvalue()


def is_file_pack(raw: bytes) -> bool:
    try:
        return "inpace-files.json" in zipfile.ZipFile(io.BytesIO(raw)).namelist()
    except zipfile.BadZipFile:
        return False


def import_file_pack(v: Vault, raw: bytes) -> dict:
    zf = zipfile.ZipFile(io.BytesIO(raw))
    manifest = json.loads(zf.read("inpace-files.json").decode("utf-8"))
    learner = manifest["learner"]["id"]
    if not verify(learner, _unsigned(manifest), manifest.get("sig", "")):
        raise FileProblem("This file pack has been changed or is damaged.")
    rec = v.received_one(learner, manifest["journey"])
    if not rec:
        raise FileProblem("Open this person's progress file first.")
    known = evidence_in(rec["data"])
    saved = 0
    folder = v.home / "received_files"
    folder.mkdir(exist_ok=True)
    for f in manifest["files"]:
        sha = f["sha256"]
        if sha not in known:
            continue
        content = zf.read(f"files/{sha}")
        if sha256_hex(content) != sha:
            raise FileProblem(f"“{f['name']}” doesn't match the file in their milestones. It was changed.")
        (folder / sha).write_bytes(content)
        v.db.execute("INSERT OR REPLACE INTO received_files VALUES (?,?,?,?)", (sha, learner, f["name"], now_utc()))
        saved += 1
    v.db.commit()
    return {"learner": learner, "journey": manifest["journey"], "count": saved,
            "name": display_name(v.person(learner)) if v.person(learner) else manifest["learner"]["name"]}


def received_file(v: Vault, sha: str) -> tuple[bytes, str] | None:
    r = v.db.execute("SELECT * FROM received_files WHERE sha256=?", (sha,)).fetchone()
    p = v.home / "received_files" / sha
    if not r or not p.exists():
        return None
    return p.read_bytes(), r["name"]


def has_received_files(v: Vault) -> set[str]:
    return {r["sha256"] for r in v.db.execute("SELECT sha256 FROM received_files").fetchall()}


# ---------------------------------------------------------------------------
# Signed extras inside the approval file
# ---------------------------------------------------------------------------

def sign_extras(v: Vault, learner: str, journey: str, exam_results: list[dict], requests: list[dict]) -> dict:
    extras = {"kind": "extras", "learner": learner, "journey": journey, "checker": v.identity.id,
              "exam_results": exam_results, "requests": requests, "at": now_utc()}
    extras["sig"] = v.identity.sign(_unsigned(extras))
    return extras


def import_extras(v: Vault, extras: dict, checker_id: str) -> dict:
    if not extras:
        return {"results": 0, "requests": 0}
    if extras.get("checker") != checker_id or extras.get("learner") != v.identity.id or \
            not verify(checker_id, _unsigned(extras), extras.get("sig", "")):
        raise FileProblem("This reply file has been changed or is damaged. Ask for a new one.")
    for r in extras.get("exam_results", []):
        v.db.execute("INSERT OR REPLACE INTO exam_results VALUES (?,?,?,?,?,?,?)",
                     (r["exam"], checker_id, r["score"], r["total"], r["percent"], int(r["passed"]), extras["at"]))
    for q in extras.get("requests", []):
        v.db.execute("INSERT OR IGNORE INTO file_requests VALUES (?,?,?,?,?)",
                     (extras["journey"], q["sha256"], q["name"], checker_id, extras["at"]))
    v.db.commit()
    return {"results": len(extras.get("exam_results", [])), "requests": len(extras.get("requests", []))}


# ---------------------------------------------------------------------------
# Extra review checks
# ---------------------------------------------------------------------------

def similar_writeups(v: Vault, data: dict, threshold: float = 0.8) -> list[str]:
    """Compare this learner's write-ups with other learners' on the same course."""
    me = data["learner"]["id"]
    course = data["journey"]["course"]["id"]
    mine = [(e["data"]["req"], e["data"]["text"]) for m in data["milestones"] for e in m["body"]["events"]
            if e["type"] == "writeup_saved"]
    warnings = []
    for other in v.received():
        if other["learner"] == me or other["data"]["journey"]["course"]["id"] != course:
            continue
        theirs = {}
        for m in other["data"]["milestones"]:
            for e in m["body"]["events"]:
                if e["type"] == "writeup_saved":
                    theirs[e["data"]["req"]] = e["data"]
        for req, text in mine:
            t = theirs.get(req)
            if not t:
                continue
            ratio = difflib.SequenceMatcher(None, text.lower(), t["text"].lower()).ratio()
            if ratio >= threshold:
                who = display_name(v.person(other["learner"])) or other["data"]["learner"]["name"]
                task = t.get("task") or req
                msg = (f"{display_name(v.person(me)) or data['learner']['name']}'s answer to “{task}” is "
                       f"{round(ratio * 100)}% the same as {who}'s.")
                if msg not in warnings:
                    warnings.append(msg)
    return warnings


def outline_differences(mine: Course, theirs: dict | None, their_hash: str) -> list[str]:
    """What's different between the checker's copy of a course and the learner's."""
    if theirs is None or their_hash == mine.hash:
        return []

    def lines(outline: dict) -> list[str]:
        out = []
        for i, m in enumerate(outline["modules"], start=1):
            out += [f"Module {i}, lesson “{les}”" for les in m["lessons"]]
            out += [f"Module {i}, task “{r}”" for r in m["requires"]]
        return out

    a, b = set(lines(course_outline(mine))), set(lines(theirs))
    diffs = [f"Missing in their copy: {x}" for x in sorted(a - b)] + \
            [f"Only in their copy: {x}" for x in sorted(b - a)]
    if not diffs:
        diffs = ["The lesson text or questions differ, but the modules, lessons and tasks are the same."]
    return diffs[:12]
