"""Folders on My courses: put courses into folders like "Programming languages" or "Networks".

Kept in one setting (meta "course_folders"):  {"folders": [{"id": "f1", "name": "Networks"}], "of": {course_id: "f1"}}
A course is in one folder or none. Deleting a folder keeps its courses; they go back to "Not in a folder".
"""
from __future__ import annotations

import json
import secrets

from .vault import Vault

KEY = "course_folders"
MAX_FOLDERS = 60
MAX_NAME = 60


def load(v: Vault) -> dict:
    try:
        data = json.loads(v._meta(KEY, "") or "{}")
    except ValueError:
        data = {}
    folders = [f for f in data.get("folders", []) if isinstance(f, dict) and f.get("id") and f.get("name")]
    ids = {f["id"] for f in folders}
    of = {str(c): str(f) for c, f in (data.get("of") or {}).items() if f in ids}
    return {"folders": folders, "of": of}


def _save(v: Vault, data: dict) -> None:
    v._set_meta(KEY, json.dumps(data, ensure_ascii=False))


def clean_name(name: str) -> str:
    return " ".join(str(name or "").split())[:MAX_NAME]


def create(v: Vault, name: str) -> str:
    """A new folder (or the one that already has this name). Returns its id, or '' if the name is empty."""
    name = clean_name(name)
    if not name:
        return ""
    data = load(v)
    for f in data["folders"]:
        if f["name"].lower() == name.lower():
            return f["id"]
    if len(data["folders"]) >= MAX_FOLDERS:
        return ""
    fid = "f" + secrets.token_hex(3)
    data["folders"].append({"id": fid, "name": name})
    _save(v, data)
    return fid


def rename(v: Vault, fid: str, name: str) -> bool:
    name = clean_name(name)
    data = load(v)
    for f in data["folders"]:
        if f["id"] == fid and name:
            f["name"] = name
            _save(v, data)
            return True
    return False


def delete(v: Vault, fid: str) -> bool:
    data = load(v)
    before = len(data["folders"])
    data["folders"] = [f for f in data["folders"] if f["id"] != fid]
    data["of"] = {c: f for c, f in data["of"].items() if f != fid}
    _save(v, data)
    return len(data["folders"]) < before


def move(v: Vault, course_id: str, fid: str) -> None:
    """Put a course in a folder ('' takes it out of any folder)."""
    data = load(v)
    if fid and any(f["id"] == fid for f in data["folders"]):
        data["of"][course_id] = fid
    else:
        data["of"].pop(course_id, None)
    _save(v, data)


def forget(v: Vault, course_id: str) -> None:
    data = load(v)
    if data["of"].pop(course_id, None):
        _save(v, data)


def group(v: Vault, rows: list[dict]) -> list[dict]:
    """Rows of My courses, by folder: [{"id", "name", "rows"}], folders A-Z, then those not in a folder (id '')."""
    data = load(v)
    out = {f["id"]: {"id": f["id"], "name": f["name"], "rows": []} for f in data["folders"]}
    loose = {"id": "", "name": "", "rows": []}
    for r in rows:
        out.get(data["of"].get(r["course"].id, ""), loose)["rows"].append(r)
    groups = sorted(out.values(), key=lambda g: g["name"].lower())
    return groups + ([loose] if loose["rows"] else [])
