"""Turn a folder of course material (neat or messy) into a course plan the learner can fix before adding it.

A plan is plain data:  {"title": "...", "sections": [{"title": "Week 1", "files": ["slides/w1.pdf", ...]}]}
File paths are relative to the folder. A folder of code is one item and ends with "/".
"""
from __future__ import annotations

import json
import re
import shutil
import threading
from pathlib import Path

from .course import (COVER_NAMES, SKIP_DIRS, CourseError, Course, _natural, _nice_title, course_from_groups,
                     folder_groups, media_kind, strip_fences)

# Words that usually number the parts of a course, in English and Arabic.
_PART_WORDS = {
    "week": "Week", "wk": "Week", "w": "Week", "lecture": "Lecture", "lec": "Lecture", "l": "Lecture",
    "chapter": "Chapter", "ch": "Chapter", "chap": "Chapter", "unit": "Unit", "module": "Module", "mod": "Module",
    "part": "Part", "session": "Session", "lesson": "Lesson", "topic": "Topic", "day": "Day", "section": "Section",
    "sec": "Section", "lab": "Lab", "tutorial": "Tutorial", "tut": "Tutorial", "class": "Class",
    "أسبوع": "الأسبوع", "الأسبوع": "الأسبوع", "محاضرة": "المحاضرة", "المحاضرة": "المحاضرة", "فصل": "الفصل",
    "الفصل": "الفصل", "وحدة": "الوحدة", "الوحدة": "الوحدة", "جزء": "الجزء", "الجزء": "الجزء", "درس": "الدرس",
    "الدرس": "الدرس", "سكشن": "السكشن", "السكشن": "السكشن",
}
_PART_RE = re.compile(
    r"(?<![A-Za-z؀-ۿ])(" + "|".join(sorted((re.escape(w) for w in _PART_WORDS), key=len, reverse=True)) +
    r")[\s._\-#]*0*(\d{1,3})(?!\d)", re.I)
_TYPE_SECTIONS = [("video", "Videos"), ("audio", "Audio"), ("pdf", "Slides and PDFs"), ("html", "Web pages"),
                  ("note", "Notes"), ("image", "Pictures"), ("code", "Code"), ("folder", "Code"), ("other", "Other files")]
CANT_SHOW = (".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx", ".odt", ".odp", ".key", ".pages", ".rtf", ".epub",
             ".zip", ".rar", ".7z")


def _kind(rel: str) -> str:
    if rel.endswith("/"):
        return "folder"
    if rel.lower().endswith(".md"):
        return "note"
    return media_kind(rel) or "other"


def _part_key(rel: str) -> tuple[str, int] | None:
    """('Week', 3) for 'Week 3 - intro.pdf' or 'slides/W03.pdf'."""
    for piece in reversed(rel.rstrip("/").split("/")):
        m = _PART_RE.search(piece)
        if m:
            word = m.group(1)
            if len(word) == 1 and not re.match(r"^[A-Za-z]\d", piece[m.start():]):  # "w3"/"l3" only when glued
                continue
            return _PART_WORDS.get(word.lower(), word.title()), int(m.group(2))
    return None


def _size(p: Path) -> int:
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return p.stat().st_size if p.exists() else 0


def file_info(folder: Path, rels: list[str]) -> dict[str, dict]:
    out = {}
    for rel in rels:
        p = folder / rel.rstrip("/")
        out[rel] = {"name": _nice_title(p.name), "file": p.name + ("/" if rel.endswith("/") else ""),
                    "kind": _kind(rel), "size": _size(p)}
    return out


def _by_parts(rels: list[str]) -> list[dict] | None:
    """Group files by the week/lecture/chapter number in their names, when most files have one."""
    keyed: dict[tuple[str, int], list[str]] = {}
    rest = []
    for rel in rels:
        k = _part_key(rel)
        (keyed.setdefault(k, []) if k else rest).append(rel)
    if len(keyed) < 2 or sum(len(v) for v in keyed.values()) < len(rels) / 2:
        return None
    # Use the most common word ("Week") so "Lecture 3" files of week 3 don't make their own sections.
    words: dict[str, int] = {}
    for (w, _), files in keyed.items():
        words[w] = words.get(w, 0) + len(files)
    main = max(words, key=words.get)
    merged: dict[int, list[str]] = {}
    for (w, n), files in keyed.items():
        if w == main:
            merged.setdefault(n, []).extend(files)
        else:
            rest.extend(files)
    sections = [{"title": f"{main} {n}", "files": sorted(merged[n], key=_natural)} for n in sorted(merged)]
    if rest:  # a syllabus or general notes usually come first
        sections.insert(0, {"title": "General", "files": sorted(rest, key=_natural)})
    return sections


def _by_type(rels: list[str]) -> list[dict]:
    groups: dict[str, list[str]] = {}
    for rel in rels:
        k = _kind(rel)
        title = next(t for kind, t in _TYPE_SECTIONS if kind == k)
        groups.setdefault(title, []).append(rel)
    order = [t for _, t in _TYPE_SECTIONS]
    return [{"title": t, "files": sorted(groups[t], key=_natural)} for t in sorted(groups, key=order.index)]


def guess_plan(folder: Path, title: str = "") -> dict:
    """The best first guess. Sub-folders become sections; a flat (messy) folder is sorted by the week/lecture/
    chapter numbers in the file names, or else by kind of file (videos, slides, notes)."""
    folder = Path(folder)
    if not folder.is_dir():
        raise CourseError(["That folder wasn't found. Copy its full path and paste it here."])
    title = title.strip() or _nice_title(folder.name)
    try:
        groups = folder_groups(folder, title)
    except CourseError:
        groups = []
    rels_of = lambda files: [p.relative_to(folder).as_posix() + ("/" if p.is_dir() else "") for p in files]
    every = [r for _, files in groups for r in rels_of(files)]
    organized = len(groups) > 1
    if organized:
        sections = [{"title": t, "files": rels_of(files)} for t, files in groups]
        # Sub-folders with numbers but no clear order still sort naturally (done by folder_groups).
    else:
        sections = _by_parts(every) or (_by_type(every) if len({_kind(r) for r in every}) > 1 else
                                        [{"title": title, "files": every}])
    cant = sorted((p.relative_to(folder).as_posix() for p in folder.rglob("*")
                   if p.is_file() and p.suffix.lower() in CANT_SHOW
                   and not any(x.startswith(".") or x in SKIP_DIRS for x in p.relative_to(folder).parts[:-1])),
                  key=_natural)[:200]
    return {"title": title, "sections": sections, "organized": organized, "cant_show": cant}


def clean_plan(folder: Path, raw: dict, allowed: set[str]) -> dict:
    """Keep only files that were found in the folder; drop empty sections."""
    title = str(raw.get("title") or "").strip()[:150] or _nice_title(Path(folder).name)
    seen, sections = set(), []
    for s in raw.get("sections") or []:
        if not isinstance(s, dict):
            continue
        files = [f for f in (s.get("files") or []) if isinstance(f, str) and f in allowed and f not in seen]
        seen.update(files)
        if files:
            sections.append({"title": (str(s.get("title") or "").strip() or "Section")[:150], "files": files})
    names = raw.get("names") if isinstance(raw.get("names"), dict) else {}
    names = {k: str(v).strip()[:150] for k, v in names.items() if k in seen and str(v).strip()}
    return {"title": title, "sections": sections, "names": names}


def all_files(folder: Path, title: str = "") -> set[str]:
    plan = guess_plan(folder, title)
    return {f for s in plan["sections"] for f in s["files"]}


def course_from_plan(folder: Path, plan: dict) -> Course:
    folder = Path(folder)
    if not plan["sections"]:
        raise CourseError(["Keep at least one file in the course."])
    groups = [(s["title"], [folder / f.rstrip("/") for f in s["files"]]) for s in plan["sections"]]
    c = course_from_groups(folder, plan["title"], groups)
    names = plan.get("names") or {}
    for m in c.modules:
        for les in m["lessons"]:
            ref = les.get("media", "")
            if ref in names:
                les["title"] = names[ref]
    from .canon import fingerprint
    c.hash = fingerprint(c.public_dict())
    return c


def plan_size(folder: Path, plan: dict) -> int:
    return sum(_size(Path(folder) / f.rstrip("/")) for s in plan["sections"] for f in s["files"])


def nice_size(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


# ---- asking AI ---------------------------------------------------------------------------------------------

def ai_prompt(title: str, files: list[str], notes: str = "") -> str:
    listing = "\n".join(f"- {f}" for f in files[:600])
    extra = f"\nThe learner adds: {notes.strip()}\n" if notes.strip() else ""
    return f"""I'm turning a folder of course material into a course called "{title}".
Sort these files into sections a learner should study in order (for example by week, lecture or topic).
Give each file a short, clear lesson title. Leave out files that aren't course material (duplicates, junk).
{extra}
The files (paths inside the folder):
{listing}

Answer with JSON only, no other text, in exactly this shape:
{{"title": "course title",
  "sections": [{{"title": "Week 1: Introduction", "files": ["path/as/given.pdf", "..."]}}],
  "names": {{"path/as/given.pdf": "Short lesson title"}}}}
Use the file paths exactly as written above."""


def parse_ai(reply: str) -> dict:
    text = strip_fences(reply or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise CourseError(["That answer has no plan in it. Copy the whole answer from the AI chat."])
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        raise CourseError(["That answer isn't complete JSON. Ask the AI to answer with the JSON only, then paste it again."])
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise CourseError(["That answer has no sections. Ask the AI again."])
    return data


def merge_ai(plan_from_ai: dict, folder: Path, allowed: set[str], keep_title: str) -> dict:
    """The AI's plan, with any file it forgot put in 'Not sorted yet' so nothing goes missing silently."""
    if not plan_from_ai.get("title"):
        plan_from_ai["title"] = keep_title
    plan = clean_plan(folder, plan_from_ai, allowed)
    used = {f for s in plan["sections"] for f in s["files"]}
    left = sorted(allowed - used, key=_natural)
    if left:
        plan["sections"].append({"title": "Not sorted yet", "files": left})
    return plan


# ---- copying files into inPace (runs in the background, a course can be many GB) --------------------------

JOBS: dict[str, dict] = {}


def start_copy(job_id: str, folder: Path, plan: dict, target: Path, done=None) -> None:
    files = []
    for s in plan["sections"]:
        for f in s["files"]:
            p = Path(folder) / f.rstrip("/")
            if p.is_dir():
                files += [(x, x.relative_to(folder)) for x in p.rglob("*") if x.is_file()]
            elif p.is_file():
                files.append((p, p.relative_to(folder)))
    for p in Path(folder).iterdir():
        if p.is_file() and p.stem.lower() in COVER_NAMES and media_kind(p.name) == "image":
            files.append((p, p.relative_to(folder)))
    total = sum(p.stat().st_size for p, _ in files) or 1
    job = JOBS[job_id] = {"total": total, "done": 0, "state": "copying", "error": ""}

    def run():
        try:
            for src, rel in files:
                dst = target / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                with open(src, "rb") as a, open(dst, "wb") as b:
                    while chunk := a.read(4 * 1024 * 1024):
                        b.write(chunk)
                        job["done"] += len(chunk)
                shutil.copystat(src, dst, follow_symlinks=True)
        except OSError as e:
            job["state"], job["error"] = "failed", str(e)
            return
        # Finish everything (like forgetting the original folder) before saying "done", because
        # the progress page and the tests act as soon as they see "done".
        if done:
            try:
                done()
            except Exception:  # the files are copied either way, and inPace looks in its own copy first
                pass
        job["state"] = "done"

    threading.Thread(target=run, daemon=True).start()
