"""Files people send each other: contact cards, progress files, approval files.

All are small JSON files ending in .inpace. The app looks at the "inpace"
field to know what kind of file it is, so users can drop any file anywhere.
"""
from __future__ import annotations

import base64
import json
import re
import zlib
from typing import Any
from urllib.parse import quote

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


# ---------------------------------------------------------------------------
# Codes: a small inPace file as one line of text you can paste into any chat
# ---------------------------------------------------------------------------

CODE_PREFIX = "inpace:"
# A link opens the inPace website, which hands the data to the app. Everything after "#" stays in the
# browser: it is never sent to the website.
WEB_LINK = "https://mahmoudyosrimahmoud13.github.io/inPace/open#"
APP_LINK = "inpace://open/"
# Longest link we offer to send in a chat message. Telegram allows 4096 characters per message.
LINK_LIMIT = 3500
# inpace:BODY (old codes), inpace://open/BODY (app links), .../open#BODY or .../open.html#BODY (web links)
_CODE_RE = re.compile(r"(?:inpace:(?://open/?)?|/open(?:\.html)?#)([A-Za-z0-9_-]{16,})")


def _body(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).rstrip(b"=").decode("ascii")


def to_code(data: dict) -> str:
    return CODE_PREFIX + _body(data)


def to_link(data: dict) -> str:
    return WEB_LINK + _body(data)


def link_body(text: str) -> str | None:
    """The data part of any inPace code or link found in the text, or None."""
    m = _CODE_RE.search(re.sub(r"\s+", "", text or ""))
    return m.group(1) if m else None


def from_code(text: str) -> dict:
    """Find an inPace code or link anywhere in pasted text (a whole chat message is fine)."""
    body = link_body(text)
    if not body:
        raise FileProblem("That doesn't look like an inPace link or code.")
    try:
        z = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        d = zlib.decompressobj()
        raw = d.decompress(z, 2_000_000)
        if d.unconsumed_tail or not d.eof:
            raise ValueError("too big or cut off")
    except Exception:
        raise FileProblem("This link is cut off or damaged. Copy the whole message again.")
    return read_inpace_file(raw)


def share_links(intro: str, data: dict | str, subject: str = "inPace") -> dict:
    """Ready-to-send links for chat apps and email. `data` is an inPace file (dict) or an old-style code."""
    link = to_link(data) if isinstance(data, dict) else WEB_LINK + (link_body(data) or "")
    message = f"{intro}\n{link}"
    return {"code": link, "link": link, "message": message, "fits": len(link) <= LINK_LIMIT,
            "telegram": f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(intro, safe='')}",
            "whatsapp": f"https://wa.me/?text={quote(message, safe='')}",
            "email": f"mailto:?subject={quote(subject, safe='')}&body={quote(message, safe='')}"}


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
    if me.get("avatar"):
        card["avatar"] = me["avatar"]  # your turtle; not signed, so older versions still read the card
    isle = _island(v)
    if isle:
        card["island"] = isle  # a copy of your island, if you share it (also not signed)
    return card


def _island(v: Vault) -> dict | None:
    from . import garden
    try:
        return garden.snapshot(v, v._meta("lang", "en") or "en")
    except Exception:
        return None


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

def checkers_have(v: Vault, journey: str) -> int:
    """How many of your milestones every one of your checkers already has. A checker who replied about
    milestone N had the whole history up to N, so an update for them only needs what came after."""
    checkers = [p["id"] for p in v.my_checkers()]
    if not checkers:
        return 0
    have = {c: 0 for c in checkers}
    for m in v.milestones(journey):
        for a in m["approvals"]:
            if a["checker"] in have:
                have[a["checker"]] = max(have[a["checker"]], m["seq"])
    return min(have.values())


def make_progress_file(v: Vault, journey: str, since: int = 0) -> dict:
    """Your progress for your checker. With `since`, only the milestones after that number are included
    (the checker already has the rest), which keeps it small enough to send as a link."""
    j = v.journey(journey)
    course = v.get_course(j["course_id"])
    ms = v.milestones(journey)
    since = max(0, min(since, len(ms) - 1))
    data = {
        "inpace": "progress",
        "v": APP_VERSION,
        "learner": v.me,
        "journey": {"id": journey, "started_at": j["started_at"],
                    "course": {"id": course.id, "title": course.title, "version": course.version, "hash": course.hash}},
        "milestones": [{"body": m["body"], "hash": m["hash"], "sig": m["sig"]} for m in ms[since:]],
        "created_at": now_utc(),
    }
    if since:
        data["since"] = since
    else:
        data["outline"] = course_outline(course)
    isle = _island(v)
    if isle:
        data["island"] = isle
    return data


def complete_progress(v: Vault, data: dict) -> dict:
    """Checker side: an update that only has the newest milestones gets the earlier ones from the copy we
    already have. The whole history is then checked as usual, so nothing is taken on trust."""
    since = int(data.get("since") or 0)
    if not since:
        return data
    name = (data.get("learner") or {}).get("name", "This learner")
    stored = v.received_one(data["learner"]["id"], data["journey"]["id"])
    old = stored["data"]["milestones"] if stored else []
    if len(old) < since:
        raise FileProblem(f"This link only has {name}'s newest milestones, and this computer doesn't have the "
                          f"earlier ones. Ask {name} to send the full progress file (Milestones → Download).")
    full = dict(data)
    full["milestones"] = old[:since] + list(data["milestones"])
    full.pop("since", None)
    full["outline"] = data.get("outline") or stored["data"].get("outline")
    return full


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
    isle = _island(v)
    if isle:
        out["island"] = isle
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
