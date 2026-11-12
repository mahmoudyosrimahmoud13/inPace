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

from .course import (COVER_NAMES, SKIP_DIRS, CourseError, Course, _natural, _nice_title, _slug, course_from_groups,
                     folder_groups, media_kind, page_range, strip_fences)

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
_TYPE_SECTIONS = [("video", "Videos"), ("audio", "Audio"), ("pdf", "Slides and PDFs"), ("office", "Documents and sheets"), ("html", "Web pages"),
                  ("note", "Notes"), ("image", "Pictures"), ("code", "Code"), ("folder", "Code"), ("other", "Other files")]
CANT_SHOW = (".ppt", ".doc", ".xls", ".odt", ".odp", ".ods", ".key", ".pages", ".numbers", ".rtf", ".epub",
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
    files = {page_range(f)[0] for s in plan["sections"] for f in s["files"]}
    return sum(_size(Path(folder) / f.rstrip("/")) for f in files)


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
    seen = set()
    for s in plan["sections"]:
        for f in s["files"]:
            f = page_range(f)[0]  # a part of a book is the book's file
            if f in seen:
                continue
            seen.add(f)
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


# ---- a book (PDF): its bookmarks become modules and lessons -----------------------------------------------

BOOK_SPLIT = 12          # pages per lesson when a part of the book has no smaller bookmarks
BOOK_LONG = 30           # a chapter longer than this, with no sections, is split into parts


def _book_reader(pdf: Path):
    try:
        from pypdf import PdfReader
        r = PdfReader(str(pdf))
        if r.is_encrypted and not r.decrypt(""):
            raise CourseError(["This PDF is protected with a password. Save a copy without the password, then try again."])
        return r
    except CourseError:
        raise
    except Exception:
        raise CourseError(["This PDF couldn't be read. It may be damaged."])


def book_outline(pdf: Path) -> tuple[list[dict], int]:
    """The book's bookmarks ("Chapter 2", "2.1 ...") with their pages, and the number of pages."""
    r = _book_reader(pdf)
    total = len(r.pages)
    items: list[dict] = []

    def walk(nodes, level: int) -> None:
        for n in nodes:
            if isinstance(n, list):
                walk(n, level + 1)
                continue
            try:
                page = r.get_destination_page_number(n) + 1
            except Exception:
                continue
            title = re.sub(r"\s+", " ", str(getattr(n, "title", "") or "")).strip()[:150]
            if title and 1 <= page <= total:
                items.append({"level": level, "title": title, "page": page})
    try:
        walk(r.outline, 0)
    except Exception:
        items = []
    # Some books put everything under one bookmark with the book's name: use the level below it.
    while items and sum(1 for i in items if i["level"] == items[0]["level"]) == 1 and any(i["level"] > items[0]["level"] for i in items):
        top = items[0]["level"]
        items = [{**i, "level": i["level"] - 1} for i in items[1:] if i["level"] > top]
    return items, total


def _pages_ref(name: str, a: int, b: int) -> str:
    return f"{name}#pages={a}-{b}"


def _split(name: str, title: str, a: int, b: int, size: int = BOOK_SPLIT) -> list[tuple[str, str]]:
    parts = []
    n = 1
    for start in range(a, b + 1, size):
        end = min(b, start + size - 1)
        parts.append((_pages_ref(name, start, end), f"{title} ({n})" if b - a + 1 > size else title))
        n += 1
    return parts


def book_plan(pdf: Path, title: str = "") -> dict:
    """Chapters become sections (modules) and their parts become lessons, each showing its own pages.
    A book without bookmarks is split into lessons of 12 pages."""
    pdf = Path(pdf)
    items, total = book_outline(pdf)
    name = pdf.name
    title = title.strip() or _nice_title(pdf.name)
    names: dict[str, str] = {}
    sections: list[dict] = []
    left: list[str] = []
    if items:
        top = min(i["level"] for i in items)
        chapters = [k for k, i in enumerate(items) if i["level"] == top]
        if chapters and items[chapters[0]]["page"] > 1:  # the cover, contents and preface: left out to start with
            ref = _pages_ref(name, 1, items[chapters[0]]["page"] - 1)
            names[ref] = "Front matter"
            left.append(ref)
        for n, k in enumerate(chapters):
            ch = items[k]
            nxt = items[chapters[n + 1]]["page"] if n + 1 < len(chapters) else total + 1
            end = max(ch["page"], nxt - 1)
            subs = [i for i in items[k + 1:chapters[n + 1] if n + 1 < len(chapters) else len(items)]
                    if i["level"] == top + 1 and ch["page"] <= i["page"] <= end]
            lessons: list[tuple[str, str]] = []
            if subs:
                if subs[0]["page"] > ch["page"]:
                    lessons.append((_pages_ref(name, ch["page"], subs[0]["page"] - 1), "Introduction"))
                for j, s in enumerate(subs):
                    s_end = max(s["page"], (subs[j + 1]["page"] - 1) if j + 1 < len(subs) else end)
                    lessons.append((_pages_ref(name, s["page"], s_end), s["title"]))
            elif end - ch["page"] + 1 > BOOK_LONG:
                lessons += _split(name, ch["title"], ch["page"], end)
            else:
                lessons.append((_pages_ref(name, ch["page"], end), ch["title"]))
            seen = set()
            files = []
            for ref, t in lessons:
                if ref in seen:
                    continue
                seen.add(ref)
                names[ref] = t
                files.append(ref)
            sections.append({"title": ch["title"], "files": files})
        how = "book"
    else:
        for start in range(1, total + 1, BOOK_SPLIT * 5):
            end = min(total, start + BOOK_SPLIT * 5 - 1)
            files = []
            for ref, _ in _split(name, "", start, end):
                a, b = page_range(ref)[1]
                names[ref] = f"Pages {a}–{b}"
                files.append(ref)
            sections.append({"title": f"Pages {start}–{end}", "files": files})
        how = "pages"
    return {"title": title, "sections": sections, "names": names, "left_out": left, "organized": False,
            "cant_show": [], "how": how, "pages": total}


def book_info(pdf: Path, plan: dict) -> dict[str, dict]:
    """What the organizer shows for each part of the book."""
    size = Path(pdf).stat().st_size
    total = max(plan.get("pages") or 1, 1)
    out = {}
    for ref, title in plan["names"].items():
        a, b = page_range(ref)[1]
        n = b - a + 1
        out[ref] = {"name": title, "file": f"{a}–{b}", "kind": "pdf", "size": size * n // total, "pages": n}
    return out


def course_from_book(folder: Path, book: str, plan: dict, info: dict[str, dict]) -> Course:
    if not plan["sections"]:
        raise CourseError(["Keep at least one part of the book in the course."])
    names = plan.get("names") or {}
    modules = []
    for mi, s in enumerate(plan["sections"], start=1):
        lessons = []
        for li, ref in enumerate(s["files"], start=1):
            pages = info.get(ref, {}).get("pages", 1)
            lessons.append({"id": f"m{mi}-l{li}", "title": names.get(ref) or info.get(ref, {}).get("name") or ref,
                            "content": "", "minutes": max(5, min(240, pages * 4)), "media": ref})
        modules.append({"id": f"m{mi}", "title": s["title"], "lessons": lessons, "requires": []})
    from .canon import fingerprint
    name = plan["title"].strip() or _nice_title(book)
    c = Course(id=_slug(name) or "book", title=name, version="1", description="", language="en",
               modules=modules, questions={}, answers=None)
    c.extra["book"] = book
    c.extra["media_index"] = {book: (Path(folder) / book).stat().st_size}
    c.hash = fingerprint(c.public_dict())
    return c


def book_toc(pdf: Path, limit: int = 160) -> tuple[list[tuple[int, str, int, int]], int]:
    """The book's contents for an AI request: (level, title, first page, last page), and the number of pages."""
    items, total = book_outline(pdf)
    out = []
    for i, it in enumerate(items[:limit]):
        nxt = next((j["page"] for j in items[i + 1:] if j["level"] <= it["level"]), total + 1)
        out.append((it["level"], it["title"], it["page"], max(it["page"], nxt - 1)))
    return out, total


def describe_sources(folder: Path, names: list[str]) -> list[dict]:
    """What the AI should know about the files attached to a course (names, pages, chapters)."""
    out = []
    for name in names[:200]:
        p = Path(folder) / name
        item = {"file": name, "kind": _kind(name)}
        if item["kind"] == "pdf" and p.is_file() and len([x for x in out if x.get("toc") is not None]) < 3:
            try:
                item["toc"], item["pages"] = book_toc(p)
            except CourseError:
                pass
        out.append(item)
    return out
