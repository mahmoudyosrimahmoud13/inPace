"""Pace races with friends.

Everyone keeps their own data. Racers swap small signed "race update" files,
by hand or through a shared folder (Google Drive, Dropbox, OneDrive...).
Only milestones approved by a checker count, so cheating doesn't pay.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .canon import now_utc
from .exchange import FileProblem
from .identity import verify
from .pace import weeks
from .vault import Vault, display_name

KINDS = {
    "pace": "Pace race: most weeks hitting your weekly goal",
    "points": "Points race: most of your course completed (approved) during the race",
}
CHEERS = ["Nice one!", "Keep going!", "You've got this!", "Great pace!", "So close!"]


def _unsigned(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "sig"}


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def setup_tables(v: Vault) -> None:
    v.db.executescript("""
    CREATE TABLE IF NOT EXISTS races (id TEXT PRIMARY KEY, data TEXT, journey TEXT, folder TEXT, joined_at TEXT);
    CREATE TABLE IF NOT EXISTS race_updates (race TEXT, racer TEXT, data TEXT, at TEXT, PRIMARY KEY (race, racer));
    CREATE TABLE IF NOT EXISTS race_cheers (race TEXT, to_id TEXT, text TEXT, at TEXT);
    """)


def create_race(v: Vault, name: str, kind: str, days: int) -> dict:
    if kind not in KINDS:
        raise ValueError("Pick a race type.")
    days = max(3, min(int(days), 90))
    start = datetime.now(timezone.utc).replace(microsecond=0)
    race = {"inpace": "race", "v": 1, "id": "r-" + secrets.token_hex(6), "name": name.strip()[:60] or "Our race",
            "kind": kind, "starts": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ends": (start + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creator": v.me, "created_at": now_utc()}
    race["sig"] = v.identity.sign(_unsigned(race))
    return race


def check_race(race: dict) -> None:
    if race.get("kind") not in KINDS or not verify(race.get("creator", {}).get("id", ""), _unsigned(race),
                                                     race.get("sig", "")):
        raise FileProblem("This race invite has been changed or is damaged.")


def join_race(v: Vault, race: dict, journey: str, folder: str = "") -> None:
    check_race(race)
    if not v.journey(journey):
        raise FileProblem("Pick one of your courses for this race.")
    v.db.execute("INSERT OR REPLACE INTO races VALUES (?,?,?,?,?)",
                 (race["id"], json.dumps(race), journey, folder.strip(), now_utc()))
    v.db.commit()


def my_races(v: Vault) -> list[dict]:
    rows = v.db.execute("SELECT * FROM races ORDER BY joined_at DESC").fetchall()
    return [{**dict(r), "race": json.loads(r["data"])} for r in rows]


def get_race(v: Vault, rid: str) -> dict | None:
    r = v.db.execute("SELECT * FROM races WHERE id=?", (rid,)).fetchone()
    return {**dict(r), "race": json.loads(r["data"])} if r else None


def leave_race(v: Vault, rid: str) -> None:
    v.db.execute("DELETE FROM races WHERE id=?", (rid,))
    v.db.execute("DELETE FROM race_updates WHERE race=?", (rid,))
    v.db.commit()


# ---- scoring ------------------------------------------------------------------

def my_score(v: Vault, race: dict, journey: str) -> dict:
    start, end = _dt(race["starts"]), _dt(race["ends"])
    ms = v.milestones(journey)
    approved = [m for m in ms if any(a["decision"] == "approved" for a in m["approvals"])]
    before = max((m["body"]["summary"]["percent"] for m in approved if _dt(m["body"]["created_at"]) < start), default=0)
    during = [m for m in approved if start <= _dt(m["body"]["created_at"]) <= end]
    best = max((m["body"]["summary"]["percent"] for m in during), default=before)
    wk = weeks(v.events(journey), [m["body"]["created_at"] for m in approved])
    on_pace = sum(1 for w in wk["weeks"] if w["state"] == "met" and _dt(w["start"] + "T00:00:00Z") >= start - timedelta(days=6))
    pending = sum(1 for m in ms if not m["approvals"] and _dt(m["body"]["created_at"]) >= start)
    points = max(0, best - before)
    main = on_pace if race["kind"] == "pace" else points
    return {"main": main, "points": points, "weeks_on_pace": on_pace, "approved": len(during), "pending": pending,
            "has_goal": bool(wk["commitment"])}


def badges(v: Vault, journey: str) -> list[str]:
    ms = v.milestones(journey)
    approved = [m for m in ms if any(a["decision"] == "approved" for a in m["approvals"])]
    evs = v.events(journey)
    wk = weeks(evs, [m["body"]["created_at"] for m in approved])
    out = []
    if approved:
        out.append("First milestone")
    if wk["streak"] >= 4:
        out.append("4 weeks on pace")
    if any(m["body"]["summary"]["percent"] >= 100 for m in approved):
        out.append("Finisher")
    if v.db.execute("SELECT COUNT(*) c FROM receipts").fetchone()["c"]:
        out.append("Helper")
    if any(e["type"] == "pause_ended" for e in evs) and wk["streak"] >= 1:
        out.append("Comeback")
    return out


# ---- updates ----------------------------------------------------------------------

def make_update(v: Vault, rid: str) -> dict:
    r = get_race(v, rid)
    if not r:
        raise FileProblem("You're not in this race.")
    cheers = [{"to": c["to_id"], "text": c["text"]} for c in
              v.db.execute("SELECT * FROM race_cheers WHERE race=? ORDER BY at DESC LIMIT 20", (rid,)).fetchall()]
    upd = {"inpace": "race_update", "v": 1, "race": rid, "racer": v.me,
           "score": my_score(v, r["race"], r["journey"]), "badges": badges(v, r["journey"]),
           "cheers": cheers, "at": now_utc()}
    upd["sig"] = v.identity.sign(_unsigned(upd))
    return upd


def import_update(v: Vault, upd: dict) -> str:
    racer = upd.get("racer", {})
    if not verify(racer.get("id", ""), _unsigned(upd), upd.get("sig", "")):
        raise FileProblem("This race update has been changed or is damaged.")
    if not get_race(v, upd.get("race", "")):
        raise FileProblem("This update is for a race you haven't joined. Open the race invite first.")
    if racer["id"] == v.identity.id:
        return racer["name"]
    old = v.db.execute("SELECT at FROM race_updates WHERE race=? AND racer=?", (upd["race"], racer["id"])).fetchone()
    if not old or old["at"] <= upd["at"]:
        v.db.execute("INSERT OR REPLACE INTO race_updates VALUES (?,?,?,?)",
                     (upd["race"], racer["id"], json.dumps(upd), upd["at"]))
        v.db.commit()
    return racer.get("name", "Someone")


def sync_folder(v: Vault, rid: str) -> int:
    """Write my update into the shared folder and read everyone else's."""
    r = get_race(v, rid)
    if not r or not r["folder"]:
        return 0
    folder = Path(r["folder"]).expanduser()
    if not folder.is_dir():
        raise FileProblem("The shared folder wasn't found. Check the path in the race settings.")
    mine = folder / f"{rid}-{v.identity.id[:12]}.inpace"
    mine.write_text(json.dumps(make_update(v, rid), ensure_ascii=False), encoding="utf-8")
    count = 0
    for p in folder.glob(f"{rid}-*.inpace"):
        if p == mine:
            continue
        try:
            import_update(v, json.loads(p.read_text(encoding="utf-8")))
            count += 1
        except (FileProblem, ValueError, KeyError):
            continue
    return count


def send_cheer(v: Vault, rid: str, to_id: str, text: str) -> None:
    if text not in CHEERS:
        text = CHEERS[0]
    v.db.execute("INSERT INTO race_cheers VALUES (?,?,?,?)", (rid, to_id, text, now_utc()))
    v.db.commit()


def board(v: Vault, rid: str) -> dict:
    r = get_race(v, rid)
    race = r["race"]
    me = {"racer": v.me, "score": my_score(v, race, r["journey"]), "badges": badges(v, r["journey"]),
          "at": now_utc(), "me": True}
    rows = [me]
    cheers_for_me = []
    for u in v.db.execute("SELECT data FROM race_updates WHERE race=?", (rid,)).fetchall():
        d = json.loads(u["data"])
        rows.append({**d, "me": False})
        for c in d.get("cheers", []):
            if c["to"] == v.identity.id:
                cheers_for_me.append({"from": d["racer"]["name"], "text": c["text"]})
    rows.sort(key=lambda x: (-x["score"]["main"], -x["score"]["approved"], x["racer"]["name"]))
    top = max((x["score"]["main"] for x in rows), default=0) or 1
    for i, x in enumerate(rows, start=1):
        x["place"] = i
        x["track"] = round(100 * x["score"]["main"] / top) if top else 0
    now = datetime.now(timezone.utc)
    left = max(0, (_dt(race["ends"]) - now).days)
    finished = now > _dt(race["ends"])
    names = [display_name(v.person(x["racer"]["id"])) if not x["me"] and v.person(x["racer"]["id"])
             else x["racer"]["name"] for x in rows]
    for x, n in zip(rows, names):
        x["name"] = n
    my_place = next(x["place"] for x in rows if x["me"])
    recap = []
    if len(rows) > 1:
        recap.append(f"{rows[0]['name']} is in the lead.")
        if my_place > 1:
            gap = rows[my_place - 2]["score"]["main"] - me["score"]["main"]
            unit = "week" if race["kind"] == "pace" else "point"
            recap.append(f"You're {gap} {unit}{'s' if gap != 1 else ''} from place {my_place - 1}.")
        else:
            recap.append("You're in first place. Keep it up!")
    if me["score"]["pending"]:
        recap.append(f"{me['score']['pending']} of your milestones are waiting for approval and don't count yet.")
    return {"race": race, "rows": rows, "left": left, "finished": finished, "cheers": cheers_for_me[-5:],
            "recap": recap, "folder": r["folder"], "journey": r["journey"]}
