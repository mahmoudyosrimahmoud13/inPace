"""Keeping people going: commitments, pauses, finish forecast, spaced review, backups."""
from __future__ import annotations

import io
import json
from pathlib import Path
import os
import re
import zipfile
from datetime import date, datetime, timedelta, timezone

import nacl.pwhash
import nacl.secret
import nacl.utils
from nacl.exceptions import CryptoError

from .vault import Vault

LEITNER_DAYS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
BACKUP_MAGIC = b"INPACEBK1"


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Commitments and pauses
# ---------------------------------------------------------------------------

def commitment(events: list[dict]) -> dict | None:
    c = None
    for e in events:
        if e["type"] == "commitment_set":
            c = {"per_week": int(e["data"]["per_week"]), "since": e["at"]}
    return c


def pauses(events: list[dict]) -> list[dict]:
    out, open_p = [], None
    for e in events:
        if e["type"] == "pause_started" and not open_p:
            open_p = {"start": e["at"], "end": None, "reason": e["data"].get("reason", "")}
        elif e["type"] == "pause_ended" and open_p:
            open_p["end"] = e["at"]
            out.append(open_p)
            open_p = None
    if open_p:
        out.append(open_p)
    return out


def is_paused(events: list[dict]) -> dict | None:
    p = pauses(events)
    return p[-1] if p and p[-1]["end"] is None else None


def weeks(events: list[dict], milestone_times: list[str], now: datetime | None = None) -> dict:
    """Week-by-week: met, missed, paused, or this week (in progress)."""
    c = commitment(events)
    if not c:
        return {"commitment": None, "weeks": [], "streak": 0, "met": 0, "missed": 0, "this_week": None}
    now = now or _now()
    start = _dt(c["since"])
    ps = [(_dt(p["start"]), _dt(p["end"]) if p["end"] else now) for p in pauses(events)]
    times = [_dt(t) for t in milestone_times]
    out = []
    w = start
    while w <= now:
        end = w + timedelta(days=7)
        count = sum(1 for t in times if w <= t < end)
        paused = any(a < end and b > w for a, b in ps)
        if end > now:
            state = "now"
        elif count >= c["per_week"]:
            state = "met"
        elif paused:
            state = "paused"
        else:
            state = "missed"
        out.append({"start": w.date().isoformat(), "count": count, "state": state})
        w = end
    streak = 0
    for wk in reversed([x for x in out if x["state"] != "now"]):
        if wk["state"] == "met":
            streak += 1
        elif wk["state"] == "paused":
            continue
        else:
            break
    this_week = out[-1] if out and out[-1]["state"] == "now" else None
    return {"commitment": c, "weeks": out[-12:], "streak": streak,
            "met": sum(1 for x in out if x["state"] == "met"),
            "missed": sum(1 for x in out if x["state"] == "missed"), "this_week": this_week}


def forecast(started_at: str, percent: int, now: datetime | None = None) -> str | None:
    """At the pace so far, roughly when the course will be finished."""
    if percent <= 0 or percent >= 100:
        return None
    now = now or _now()
    days = (now - _dt(started_at)).total_seconds() / 86400
    if days < 2:
        return None  # too early to guess well
    remaining = days * (100 - percent) / percent
    d = (now + timedelta(days=remaining)).date()
    return f"{d:%b} {d.day}, {d.year}"


# ---------------------------------------------------------------------------
# Spaced review (Leitner boxes)
# ---------------------------------------------------------------------------

def update_cards(v: Vault, course_id: str, results: dict[str, bool], today: date | None = None) -> None:
    today = today or _now().date()
    for qid, ok in results.items():
        row = v.db.execute("SELECT box FROM review_cards WHERE course=? AND qid=?", (course_id, qid)).fetchone()
        box = row["box"] if row else 1
        box = min(box + 1, 5) if ok else 1
        due = (today + timedelta(days=LEITNER_DAYS[box])).isoformat()
        v.db.execute("INSERT OR REPLACE INTO review_cards VALUES (?,?,?,?)", (course_id, qid, box, due))
    v.db.commit()


def due_cards(v: Vault, course_id: str, today: date | None = None) -> list[str]:
    today = (today or _now().date()).isoformat()
    rows = v.db.execute("SELECT qid FROM review_cards WHERE course=? AND due<=? ORDER BY due, box",
                        (course_id, today)).fetchall()
    return [r["qid"] for r in rows]


def card_count(v: Vault, course_id: str) -> int:
    return v.db.execute("SELECT COUNT(*) c FROM review_cards WHERE course=?", (course_id,)).fetchone()["c"]


# ---------------------------------------------------------------------------
# Encrypted backups
# ---------------------------------------------------------------------------

def _key(password: str, salt: bytes) -> bytes:
    return nacl.pwhash.argon2id.kdf(nacl.secret.SecretBox.KEY_SIZE, password.encode("utf-8"), salt,
                                    opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
                                    memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE)


BACKUP_FILE_LIMIT = 50 * 1024 * 1024


def _belongs_in_backup(p, rel: str) -> bool:
    """Backups keep your progress small and safe: no downloader, no downloaded YouTube videos, no huge files
    (videos come back from YouTube or your own folders)."""
    parts = rel.split("/")
    if parts[0] == "tools" or (len(parts) >= 3 and parts[0] == "media" and parts[2] == "videos"):
        return False
    if parts[0] == "cache" or rel.endswith((".tmp", ".part")):  # made again when needed (and may be half written)
        return False
    try:
        return p.stat().st_size <= BACKUP_FILE_LIMIT
    except OSError:
        return False


def backup_files(v: Vault) -> list[tuple]:
    """What goes in a backup, besides the database: [(path, name inside, size)].

    v1.37.8: folders that never go in (earlier backups, caches, the downloader, downloaded videos) are skipped
    without being opened. On a phone the cache holds a copy of Python's libraries, thousands of files, and
    walking them made Settings take 2 to 3 seconds every time."""
    out = []
    home = str(v.home)
    for root, dirs, files in os.walk(home):
        rel_root = os.path.relpath(root, home).replace(os.sep, "/")
        rel_root = "" if rel_root == "." else rel_root + "/"
        depth = rel_root.count("/")
        if depth == 0:
            dirs[:] = [d for d in dirs if d not in ("backups", "cache", "tools")]
        elif depth == 2 and rel_root.startswith("media/"):
            dirs[:] = [d for d in dirs if d != "videos"]
        for name in files:
            rel = rel_root + name
            if rel.startswith(("vault.db", "inpace.log")):
                continue
            p = Path(root) / name
            if _belongs_in_backup(p, rel):
                try:
                    out.append((p, rel, p.stat().st_size))
                except OSError:
                    continue
    return out


_SIZE = {"at": 0.0, "home": "", "size": 0}


def backup_size(v: Vault, fresh: bool = False) -> int:
    """About how much a backup would hold, before compression (for the Settings page). Remembered for ten
    minutes, so opening Settings again doesn't walk the folder again."""
    import time as _time
    if not fresh and _SIZE["home"] == str(v.home) and _time.time() - _SIZE["at"] < 600:
        return _SIZE["size"]
    try:
        db = (v.home / "vault.db").stat().st_size
    except OSError:
        db = 0
    size = db + sum(size for _p, _rel, size in backup_files(v))
    _SIZE.update(at=_time.time(), home=str(v.home), size=size)
    return size


def make_backup(v: Vault, password: str, on_progress=None) -> bytes:
    """Everything, as one encrypted file. on_progress(done_bytes, total_bytes) is called as files go in."""
    if len(password) < 6:
        raise ValueError("Use a password with at least 6 characters.")
    v.db.commit()
    _SIZE["at"] = 0.0  # Settings works the size out again after this
    files = backup_files(v)
    total = sum(size for _p, _rel, size in files) + 1
    done = 0
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # A consistent copy of the database, even while the app is running.
        import sqlite3
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            copy = sqlite3.connect(f"{tmp}/vault.db")
            v.db.backup(copy)
            copy.close()
            with open(f"{tmp}/vault.db", "rb") as f:
                zf.writestr("vault.db", f.read())
        for p, rel, size in files:
            try:  # a file another part of inPace is writing right now (locked on Windows) is skipped
                data = p.read_bytes()
            except OSError:
                continue
            zf.writestr(rel, data)
            done += size
            if on_progress:
                on_progress(done, total)
        zf.writestr("backup.json", json.dumps({"made": _now().isoformat(), "name": v.me["name"]}))
    salt = nacl.utils.random(nacl.pwhash.argon2id.SALTBYTES)
    box = nacl.secret.SecretBox(_key(password, salt))
    if on_progress:
        on_progress(total, total)
    return BACKUP_MAGIC + salt + box.encrypt(buf.getvalue())


def save_backup(v: Vault, password: str, on_progress=None) -> Path:
    """Make a backup and keep it in <data folder>/backups/, so it can be downloaded (and its size shown).
    Only the newest one is kept there."""
    folder = v.home / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    data = make_backup(v, password, on_progress)
    name = f"inPace backup - {v.me['name']} - {_now().strftime('%Y-%m-%d %H.%M')}.inpace-backup"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    for old in folder.glob("*.inpace-backup"):
        old.unlink(missing_ok=True)
    tmp = folder / (name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(folder / name)
    return folder / name


def latest_backup(v: Vault) -> Path | None:
    folder = v.home / "backups"
    found = sorted(folder.glob("*.inpace-backup"), key=lambda p: p.stat().st_mtime) if folder.is_dir() else []
    return found[-1] if found else None


def open_backup(data: bytes, password: str) -> zipfile.ZipFile:
    if not data.startswith(BACKUP_MAGIC):
        raise ValueError("This isn't an inPace backup.")
    n = len(BACKUP_MAGIC)
    salt, body = data[n:n + nacl.pwhash.argon2id.SALTBYTES], data[n + nacl.pwhash.argon2id.SALTBYTES:]
    try:
        plain = nacl.secret.SecretBox(_key(password, salt)).decrypt(body)
    except CryptoError:
        raise ValueError("Wrong password, or the backup is damaged.")
    zf = zipfile.ZipFile(io.BytesIO(plain))
    names = set(zf.namelist())
    if "vault.db" not in names or "identity.key" not in names:
        raise ValueError("This backup is incomplete.")
    return zf


def restore_backup(v: Vault, data: bytes, password: str, on_progress=None) -> int:
    """Put a backup's files in place. on_progress(n, of) as files are written. Returns how many."""
    _SIZE["at"] = 0.0
    zf = open_backup(data, password)
    v.db.close()
    for extra in ("vault.db-wal", "vault.db-shm"):  # the old database's journal must not meet the new file
        try:
            (v.home / extra).unlink()
        except OSError:
            pass
    names = [n for n in zf.namelist() if ".." not in n.split("/") and not n.startswith("/") and n != "backup.json"]
    for i, name in enumerate(names, 1):
        target = v.home.joinpath(*name.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(name))
        if on_progress:
            on_progress(i, len(names))
    return len(names)
