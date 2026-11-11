"""Files people send each other: contact cards, progress files, approval files.

All are small JSON files ending in .inpace. The app looks at the "inpace"
field to know what kind of file it is, so users can drop any file anywhere.
"""
from __future__ import annotations

import json
from typing import Any

from .canon import fingerprint, now_utc
from .course import course_outline
from .identity import verify
from .vault import Vault, display_name

APP_VERSION = 1


class FileProblem(Exception):
    pass


def read_inpace_file(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FileProblem("This isn't an inPace file.")
    if not isinstance(data, dict) or "inpace" not in data:
        raise FileProblem("This isn't an inPace file.")
    return data


def dump(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")


# ---------------------------------------------------------------------------
# Contact cards
# ---------------------------------------------------------------------------

def make_contact_card(v: Vault) -> dict:
    me = v.me
    card = {"inpace": "contact", "v": APP_VERSION, "id": me["id"], "name": me["name"], "color": me["color"],
            "created_at": now_utc()}
    card["sig"] = v.identity.sign({k: card[k] for k in ("inpace", "id", "name", "color", "created_at")})
    return card


def check_contact_card(card: dict) -> None:
    fields = {k: card.get(k) for k in ("inpace", "id", "name", "color", "created_at")}
    if not verify(str(card.get("id")), fields, str(card.get("sig"))):
        raise FileProblem("This contact card has been changed or is damaged. Ask for a new one.")


# ---------------------------------------------------------------------------
# Chains (shared by learner and checker)
# ---------------------------------------------------------------------------

def check_chain(milestones: list[dict], learner_id: str | None = None) -> list[str]:
    """Every milestone must match its fingerprint, be signed by the learner,
    and point to the one before it."""
    problems = []
    prev = ""
    for i, m in enumerate(milestones, start=1):
        body = m["body"]
        if body.get("seq") != i:
            problems.append(f"Milestone {i} is missing or out of order.")
            break
        if fingerprint(body) != m["hash"]:
            problems.append(f"Milestone {i} was changed after it was saved.")
            break
        if body.get("prev", "") != prev:
            problems.append(f"Milestone {i} doesn't connect to milestone {i - 1}.")
            break
        who = learner_id or body.get("learner")
        if body.get("learner") != who or not verify(who, {"kind": "milestone", "hash": m["hash"]}, m.get("sig", "")):
            problems.append(f"Milestone {i} wasn't signed by this learner.")
            break
        prev = m["hash"]
    return problems


# ---------------------------------------------------------------------------
# Progress files (learner -> checker)
# ---------------------------------------------------------------------------

def make_progress_file(v: Vault, journey: str) -> dict:
    j = v.journey(journey)
    course = v.get_course(j["course_id"])
    ms = v.milestones(journey)
    return {
        "inpace": "progress",
        "v": APP_VERSION,
        "learner": v.me,
        "journey": {"id": journey, "started_at": j["started_at"],
                    "course": {"id": course.id, "title": course.title, "version": course.version, "hash": course.hash}},
        "milestones": [{"body": m["body"], "hash": m["hash"], "sig": m["sig"]} for m in ms],
        "outline": course_outline(course),
        "created_at": now_utc(),
    }


def review_progress(v: Vault, data: dict) -> dict:
    """What the checker sees. Plain sentences, worst news first."""
    learner = data["learner"]["id"]
    jid = data["journey"]["id"]
    ms = data["milestones"]
    report: dict[str, Any] = {"learner": data["learner"], "journey": data["journey"], "problems": [],
                              "history_ok": True, "course_changes": [], "new": [], "old": [], "milestones": ms}
    chain_problems = check_chain(ms, learner)
    if chain_problems:
        report["problems"] += chain_problems
        report["history_ok"] = False

    by_seq = {m["body"]["seq"]: m for m in ms}
    receipts = v.receipts(learner, jid)
    for r in receipts:
        m = by_seq.get(r["seq"])
        if m is None:
            report["problems"].append(f"Milestone {r['seq']} that you already reviewed is missing from this file.")
            report["history_ok"] = False
        elif m["hash"] != r["hash"]:
            report["problems"].append(
                f"Milestone {r['seq']} was changed after you reviewed it on {r['at'][:10]}. "
                "Its history was rewritten.")
            report["history_ok"] = False
    approved = {r["seq"] for r in receipts if r["decision"] == "approved"}
    for m in ms:
        (report["old"] if m["body"]["seq"] in approved else report["new"]).append(m)

    seen = None
    for m in ms:
        c = m["body"]["course"]
        if seen and c["hash"] != seen["hash"]:
            report["course_changes"].append(
                f"The course changed before milestone {m['body']['seq']} (version {seen['version']} to {c['version']}).")
        seen = c
    report["last_reviewed"] = max((r["at"] for r in receipts), default=None)
    return report


# ---------------------------------------------------------------------------
# Approval files (checker -> learner)
# ---------------------------------------------------------------------------

def _decision_payload(d: dict) -> dict:
    return {k: d[k] for k in ("kind", "milestone", "journey", "learner", "checker", "decision", "note", "at")}


def make_approval_file(v: Vault, data: dict, decision: str, note: str, seqs: list[int],
                       extras: dict | None = None) -> dict:
    assert decision in ("approved", "question", "flag")
    learner = data["learner"]["id"]
    jid = data["journey"]["id"]
    at = now_utc()
    decisions = []
    for m in data["milestones"]:
        if m["body"]["seq"] not in seqs:
            continue
        d = {"kind": "decision", "milestone": m["hash"], "journey": jid, "learner": learner,
             "checker": v.identity.id, "decision": decision, "note": note.strip(), "at": at}
        d["sig"] = v.identity.sign(_decision_payload(d))
        d["seq"] = m["body"]["seq"]
        decisions.append(d)
        v.add_receipt(learner, jid, m["body"]["seq"], m["hash"], decision, note.strip(), at)
    out = {"inpace": "approval", "v": APP_VERSION, "checker": v.me, "learner": learner,
           "journey": jid, "decisions": decisions, "created_at": at}
    if extras:
        out["extras"] = extras
    return out


def import_approval_file(v: Vault, data: dict) -> dict:
    checker = data["checker"]
    if data.get("learner") != v.identity.id:
        raise FileProblem("This file is meant for someone else.")
    person = v.person(checker["id"])
    if not person or not person["checks_me"]:
        raise FileProblem(
            f"This is from {checker.get('name', 'someone')}, who isn't set as one of your checkers yet. "
            "Add their contact card first and choose 'They check my progress'.")
    mine = {m["hash"] for m in v.milestones(data["journey"])}
    # Check everything first, then save, so a damaged file never saves half.
    for d in data["decisions"]:
        if d.get("checker") != checker["id"] or not verify(checker["id"], _decision_payload(d), d.get("sig", "")):
            raise FileProblem("This approval file has been changed or is damaged. Ask for a new one.")
        if d["milestone"] not in mine:
            raise FileProblem("This approval is for milestones you don't have. Was it meant for another course?")
    from .checks import import_extras
    try:
        extra = import_extras(v, data.get("extras") or {}, checker["id"])
        for d in data["decisions"]:
            v.db.execute("INSERT OR IGNORE INTO approvals VALUES (?,?,?,?,?,?)",
                         (d["milestone"], d["checker"], d["decision"], d["note"], d["at"], d["sig"]))
        v.db.commit()
    except Exception:
        v.db.rollback()
        raise
    count = len(data["decisions"])
    first = data["decisions"][0] if data["decisions"] else {"decision": "approved", "note": ""}
    return {"name": display_name(person), "count": count, "decision": first["decision"], "note": first["note"],
            "results": extra["results"], "requests": extra["requests"]}
