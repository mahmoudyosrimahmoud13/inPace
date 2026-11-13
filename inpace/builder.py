"""The course builder: make a course by hand on one page.

The page keeps the whole course in the browser and sends it here as JSON. This turns it into a normal course,
keeping the ids (and so everyone's progress) of modules and lessons that already existed, and the tasks and
quizzes of each module. Modules with no lessons yet stay on the page but aren't saved until they have one.
"""
from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path

from . import editor
from .course import ID_RE, Course, CourseError, _nice_title, is_url, local_ref, media_kind
from .vault import Vault

UPLOAD_DIR = "uploads"


def lesson_kind(les: dict) -> str:
    """What the page shows for a lesson: youtube, video, audio, pdf, link, text..."""
    ref = str(les.get("media") or "")
    return media_kind(ref) if ref else "text"


def to_page(c: Course) -> dict:
    """The course as the builder page wants it."""
    def task_names(m):
        out = []
        for r in m["requires"]:
            if r["type"] == "quiz":
                out.append({"type": "quiz", "n": len(r.get("questions") or [])})
            else:
                out.append({"type": r["type"]})
        return out
    return {
        "cid": c.id, "title": c.title, "description": c.description, "language": c.language,
        "modules": [{"id": m["id"], "title": m["title"], "tasks": task_names(m),
                     "lessons": [{"id": les["id"], "title": les["title"], "media": les.get("media", ""),
                                  "content": _own_text(les),
                                  "minutes": int(les.get("minutes") or 0), "kind": lesson_kind(les)}
                                 for les in m["lessons"]]}
                    for m in c.modules],
    }


def _own_text(les: dict) -> str:
    """Notes written under a video or file (the lesson text without its title line)."""
    text = (les.get("content") or "").strip()
    return re.sub(r"^#\s+.*\n*", "", text).strip()


def _clean_media(ref: str) -> str:
    ref = (ref or "").strip().strip('"').strip("<>").replace("\\", "/")
    if ref and not (is_url(ref) or (local_ref(ref) and media_kind(ref))):
        raise CourseError([f"This isn't a video, audio, PDF, page or link inPace can show: {ref[:80]}"])
    return ref


def save(v: Vault, data: dict, upload_draft: Path | None = None) -> Course:
    """Save what the page sent. Raises CourseError with plain-language problems."""
    title = " ".join(str(data.get("title") or "").split())[:200]
    if not title:
        raise CourseError(["The course needs a title."])
    cid = str(data.get("cid") or "")
    old = v.get_course(cid) if cid else None
    if cid and not old:
        raise CourseError(["That course isn't installed."])
    old_modules = {m["id"]: m for m in old.modules} if old else {}
    taken: set[str] = set()

    def fresh(prefix: str) -> str:
        n = 1
        while f"{prefix}{n}" in taken:
            n += 1
        taken.add(f"{prefix}{n}")
        return f"{prefix}{n}"

    def keep(wanted: str) -> str | None:
        if wanted and ID_RE.match(wanted) and wanted not in taken:
            taken.add(wanted)
            return wanted
        return None

    # Reserve the ids the page sent first, so new items never take an existing one.
    raw_modules = [m for m in (data.get("modules") or []) if isinstance(m, dict)][:200]
    modules = []
    for rm in raw_modules:
        raw_lessons = [les for les in (rm.get("lessons") or []) if isinstance(les, dict)]
        raw_lessons = [les for les in raw_lessons
                       if str(les.get("title") or "").strip() or str(les.get("media") or "").strip()
                       or str(les.get("content") or "").strip()]
        if not raw_lessons:
            continue  # an empty module stays on the page until it has a lesson
        mid = keep(str(rm.get("id") or "")) or fresh("m")
        lessons = []
        for li, rl in enumerate(raw_lessons[:500], start=1):
            lid = keep(str(rl.get("id") or "")) or fresh(f"{mid}-l")
            media = _clean_media(str(rl.get("media") or ""))
            name = " ".join(str(rl.get("title") or "").split())[:200]
            if not name:
                name = _nice_title(media.rstrip("/").rsplit("/", 1)[-1]) if media and not is_url(media) else f"Lesson {li}"
            text = str(rl.get("content") or "").strip()
            les = {"id": lid, "title": name, "minutes": max(0, min(100000, int(rl.get("minutes") or 0)))}
            if media:
                les["media"] = media
                les["content"] = f"# {name}\n\n{text}\n" if text else ""
            else:
                les["content"] = f"# {name}\n\n{text or 'Write this lesson.'}\n"
            lessons.append(les)
        requires = copy.deepcopy(old_modules[mid]["requires"]) if mid in old_modules else []
        mtitle = " ".join(str(rm.get("title") or "").split())[:200] or f"Module {len(modules) + 1}"
        modules.append({"id": mid, "title": mtitle, "lessons": lessons, "requires": requires})
    if not modules:
        raise CourseError(["Add at least one lesson. A video, a file, a link or some text is enough."])

    language = "ar" if data.get("language") == "ar" else "en"
    description = " ".join(str(data.get("description") or "").split())[:2000]
    if old:
        c = copy.deepcopy(old)
        c.title, c.description, c.language, c.modules = title, description, language, modules
        editor.bump(c)
    else:
        cid = editor._slug(title)
        while v.get_course(cid):
            cid = editor._unique(cid + "-", {p.name for p in (v.home / "courses").iterdir()} if (v.home / "courses").exists() else set())
        c = Course(id=cid, title=title, version="1", description=description, language=language,
                   modules=modules, questions={}, answers={})
    saved = editor.save(v, c)
    if upload_draft and upload_draft.is_dir():  # files picked before the course existed
        dest = v.media_dir(saved.id) / UPLOAD_DIR
        dest.mkdir(parents=True, exist_ok=True)
        for f in upload_draft.iterdir():
            if f.is_file() and not (dest / f.name).exists():
                shutil.move(str(f), dest / f.name)
        shutil.rmtree(upload_draft, ignore_errors=True)
    return saved


def safe_name(name: str) -> str:
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .") or "file"
    return name[:150]


def unique_path(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    n = 2
    while p.exists():
        p = folder / (f"{stem} ({n}).{ext}" if ext else f"{stem} ({n})")
        n += 1
    return p
