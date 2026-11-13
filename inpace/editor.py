"""Make and change courses with simple forms. Every change is checked before it's saved."""
from __future__ import annotations

import copy
import re

from .course import Course, CourseError, course_to_files, load_course
import yaml
from .vault import Vault


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "course"


def _unique(prefix: str, taken: set[str]) -> str:
    n = 1
    while f"{prefix}{n}" in taken:
        n += 1
    return f"{prefix}{n}"


def all_ids(c: Course) -> set[str]:
    ids = set()
    for m in c.modules:
        ids.add(m["id"])
        ids.update(les["id"] for les in m["lessons"])
        ids.update(r["id"] for r in m["requires"])
    return ids


HISTORY_KEEP = 30


def _history(v: Vault, course_id: str):
    return v.home / "course_history" / course_id


def save(v: Vault, c: Course) -> Course:
    """Round-trip through the normal loader so every rule is checked. The version before is kept for Undo."""
    fresh = load_course(course_to_files(c))
    fresh.extra.update({k: val for k, val in c.extra.items() if k not in fresh.extra})
    old_folder = v.home / "courses" / c.id
    if old_folder.exists():
        import shutil
        import time
        hist = _history(v, c.id)
        hist.mkdir(parents=True, exist_ok=True)
        shutil.copytree(old_folder, hist / f"{time.time_ns()}")
        for extra in sorted(hist.iterdir())[:-HISTORY_KEEP]:
            shutil.rmtree(extra, ignore_errors=True)
    return v.install_course(fresh)


def can_undo(v: Vault, course_id: str) -> bool:
    h = _history(v, course_id)
    return h.exists() and any(h.iterdir())


def undo(v: Vault, course_id: str) -> Course:
    """Go back to the course as it was before the last change."""
    import shutil
    from .course import files_from_folder
    h = _history(v, course_id)
    snaps = sorted(h.iterdir()) if h.exists() else []
    if not snaps:
        raise CourseError(["There's nothing to undo."])
    last = snaps[-1]
    c = load_course(files_from_folder(last))
    c.id = course_id
    shutil.rmtree(last)
    return v.install_course(c)


def new_course(v: Vault, title: str, description: str, module_title: str = "", lesson_title: str = "",
               content: str = "", links: str = "", language: str = "en", fetch_titles: bool = False) -> Course:
    """A new course from just a title. Optionally a first lesson, or a list of links that become lessons."""
    title = title.strip()
    if not title:
        raise CourseError(["The course needs a title."])
    cid = _slug(title)
    while v.get_course(cid):
        cid = _unique(cid + "-", set(p.name for p in (v.home / "courses").iterdir()))
    if links.strip():
        modules = modules_from_links(links, fetch_titles, first_title=module_title.strip() or "Module 1")
    else:
        lesson = {"id": "m1-l1", "title": lesson_title.strip() or "Welcome",
                  "content": content.strip() or f"# {lesson_title.strip() or 'Welcome'}\n\nWrite this lesson in the editor.",
                  "minutes": 0}
        modules = [{"id": "m1", "title": module_title.strip() or "Module 1", "lessons": [lesson], "requires": []}]
    c = Course(id=cid, title=title, version="1", description=description.strip(),
               language="ar" if language == "ar" else "en", modules=modules, questions={}, answers={})
    return save(v, c)


# ---------- many lessons at once, from a list of links or file paths -------

def youtube_title(url: str) -> str:
    """The video's title from YouTube (only when you ask for it: this goes online)."""
    import json
    import urllib.parse
    import urllib.request
    try:
        q = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url, safe="")
        from .net import urlopen
        with urlopen(urllib.request.Request(q, headers={"User-Agent": "inPace"}), timeout=8) as r:
            return str(json.loads(r.read().decode("utf-8")).get("title") or "")[:150]
    except Exception:
        return ""


_CHAPTER = re.compile(r"^[\(\[]?((?:\d{1,2}:)?\d{1,2}:\d{2})[\)\]]?\s*(?:[-–—:|.]\s*)?(.*)$")


def parse_link_lines(text: str, fetch_titles: bool = False) -> list:
    """One lesson per line:  link   or   Title | link   or   a file path.
    A line starting with '#' starts a new module:  # Module title
    Time lines under a YouTube link split that video into lessons, one per chapter:
        https://www.youtube.com/watch?v=...
        00:00 Intro
        12:30 Installing
    Links to Udemy or any other site become lessons that open the page.
    Returns [(module title or None, [lesson, ...]), ...]."""
    from .course import _nice_title, clock_seconds, embed_id, is_url, local_ref, media_kind, youtube_segment
    groups: list = [[None, []]]
    last_video = None  # the YouTube lesson that time lines belong to
    for raw in text.splitlines():
        line = raw.strip().replace("\u200f", "").replace("\u200e", "")
        if not line:
            continue
        chap = _CHAPTER.match(line)
        if chap and not is_url(line):
            if last_video is None:
                raise CourseError([f"This time line needs a YouTube link above it: {line[:80]}"])
            sec = clock_seconds(chap.group(1))
            last_video["chapters"].append((sec, chap.group(2).strip() or chap.group(1)))
            continue
        if line.startswith("#"):
            groups.append([line.lstrip("#").strip() or "Module", []])
            last_video = None
            continue
        title, _, ref = line.rpartition("|") if "|" in line else ("", "", line)
        ref, title = ref.strip().strip('"').strip("<>"), title.strip()
        if not is_url(ref) and " http" in ref:  # "Title https://..." without the |
            title, ref = ref.rsplit(" http", 1)[0].strip(" -–:"), "http" + ref.rsplit(" http", 1)[1]
        if not (is_url(ref) or (local_ref(ref) and media_kind(ref))):
            raise CourseError([f"This line isn't a link or a file inPace can show: {line[:80]}"])
        kind = media_kind(ref)
        if not title:
            if fetch_titles and kind in ("youtube", "vimeo"):
                title = youtube_title(ref) if kind == "youtube" else ""
            if not title and not is_url(ref):
                title = _nice_title(ref.rstrip("/").rsplit("/", 1)[-1])
        lesson = {"title": title, "media": ref.replace("\\", "/"), "chapters": []}
        groups[-1][1].append(lesson)
        last_video = lesson if kind == "youtube" and embed_id(ref) else None
    out = []
    for mtitle, lessons in groups:
        flat = []
        for les in lessons:
            chapters = sorted(les.pop("chapters"))
            if not chapters:
                flat.append(les)
                continue
            vid = embed_id(les["media"])
            first, _ = youtube_segment(les["media"])
            for i, (sec, name) in enumerate(chapters):
                nxt = chapters[i + 1][0] if i + 1 < len(chapters) else None
                if nxt is not None and nxt <= sec:
                    continue
                url = f"https://www.youtube.com/watch?v={vid}&t={sec}" + (f"&end={nxt}" if nxt else "")
                flat.append({"title": name[:150], "media": url, "minutes": round((nxt - sec) / 60) if nxt else 0})
        if flat:
            out.append((mtitle, flat))
    return out


def modules_from_links(text: str, fetch_titles: bool, first_title: str = "Module 1", start: int = 1) -> list:
    from .course import media_kind
    out = []
    for gi, (mtitle, lessons) in enumerate(parse_link_lines(text, fetch_titles)):
        mid = f"m{start + gi}"
        les = []
        for li, l in enumerate(lessons, start=1):
            kind = media_kind(l["media"])
            fallback = f"Video {li}" if kind in ("youtube", "vimeo", "video") else f"Lesson {li}"
            les.append({"id": f"{mid}-l{li}", "title": l["title"] or fallback, "content": "",
                        "minutes": int(l.get("minutes") or 0), "media": l["media"]})
        out.append({"id": mid, "title": mtitle or (first_title if gi == 0 else f"Module {start + gi}"),
                    "lessons": les, "requires": []})
    if not out:
        raise CourseError(["Paste at least one link or file path."])
    return out


def _move(items: list, idx: int, step: int) -> None:
    j = idx + step
    if 0 <= idx < len(items) and 0 <= j < len(items):
        items[idx], items[j] = items[j], items[idx]


def _find_lesson(c: Course, lid: str):
    for m in c.modules:
        for i, les in enumerate(m["lessons"]):
            if les["id"] == lid:
                return m, i, les
    return None, -1, None


def _lesson_media(f: dict) -> str:
    from .course import is_url, local_ref, media_kind
    ref = (f.get("media") or "").strip().strip('"').strip("<>").replace("\\", "/")
    if ref and not (is_url(ref) or (local_ref(ref) and media_kind(ref))):
        raise CourseError(["That isn't a video, audio, web page, PDF or picture inPace can show."])
    return ref


def bump(c: Course) -> None:
    try:
        c.version = str(int(c.version) + 1)
    except ValueError:
        c.version = c.version + ".1"


def edit(v: Vault, course_id: str, action: str, f: dict) -> Course:
    c = v.get_course(course_id)
    if not c:
        raise CourseError(["That course isn't installed."])
    c = copy.deepcopy(c)
    c.answers = c.answers or {}
    ids = all_ids(c)
    mod = next((m for m in c.modules if m["id"] == f.get("module")), None)

    if action == "info":
        c.title = f.get("title", "").strip() or c.title
        c.description = f.get("description", "").strip()
        c.language = "ar" if f.get("language") == "ar" else "en"
        if "downloads" in f:
            from .course import downloads_from_lines
            dl = downloads_from_lines(f.get("downloads", ""))
            if dl:
                c.extra["downloads"] = dl
            else:
                c.extra.pop("downloads", None)
    elif action == "add_module":
        mid = _unique("m", ids)
        lid = f"{mid}-l1"
        c.modules.append({"id": mid, "title": f.get("title", "").strip() or "New module",
                          "lessons": [{"id": lid, "title": f.get("lesson_title", "").strip() or "First lesson",
                                       "content": f.get("content", ""), "minutes": 0}], "requires": []})
    elif action == "add_lesson" and mod:
        lid = _unique(f"{mod['id']}-l", ids)
        media = _lesson_media(f)
        title = f.get("title", "").strip()
        if not title and media:
            from .course import _nice_title, is_url, media_kind
            if media_kind(media) == "youtube" and f.get("fetch_titles"):
                title = youtube_title(media)
            title = title or (_nice_title(media.rstrip("/").rsplit("/", 1)[-1]) if not is_url(media) else "Video")
        les = {"id": lid, "title": title or "New lesson", "content": f.get("content", ""),
               "minutes": int(f.get("minutes") or 0)}
        if media:
            les["media"] = media
        mod["lessons"].append(les)
    elif action == "add_links" and mod:
        for l in parse_link_lines(f.get("links", ""), bool(f.get("fetch_titles"))):
            for item in l[1]:
                lid = _unique(f"{mod['id']}-l", ids)
                ids.add(lid)
                mod["lessons"].append({"id": lid, "title": item["title"] or "Video", "content": "", "minutes": 0,
                                       "media": item["media"]})
    elif action == "move_module":
        idx = next((i for i, m in enumerate(c.modules) if m["id"] == f.get("module")), -1)
        _move(c.modules, idx, -1 if f.get("dir") == "up" else 1)
    elif action == "move_lesson":
        m, idx, les = _find_lesson(c, f.get("lesson", ""))
        if not les:
            raise CourseError(["That lesson wasn't found."])
        target = f.get("to_module")
        if target and target != m["id"]:
            dest = next((x for x in c.modules if x["id"] == target), None)
            if not dest:
                raise CourseError(["That module wasn't found."])
            if len(m["lessons"]) <= 1:
                raise CourseError(["A module needs at least one lesson. Delete the module instead."])
            m["lessons"].pop(idx)
            dest["lessons"].append(les)
        else:
            _move(m["lessons"], idx, -1 if f.get("dir") == "up" else 1)
    elif action == "move_task" and mod:
        idx = next((i for i, r in enumerate(mod["requires"]) if r["id"] == f.get("task")), -1)
        _move(mod["requires"], idx, -1 if f.get("dir") == "up" else 1)
    elif action == "edit_task" and mod:
        task = next((r for r in mod["requires"] if r["id"] == f.get("task")), None)
        if not task:
            raise CourseError(["That task wasn't found."])
        task["prompt"] = f.get("prompt", "").strip() or task["prompt"]
        if f.get("optional") == "1":
            task["optional"] = True
        else:
            task.pop("optional", None)
        if task["type"] == "explain":
            task["min_words"] = int(f.get("min_words") or task.get("min_words") or 40)
        if task["type"] == "quiz":
            task["questions"] = [q for q in f.get("questions", []) if q in c.questions] or task["questions"]
            task["pass"] = int(f.get("pass") or task.get("pass") or 70)
    elif action == "edit_question":
        qid = f.get("question")
        if qid not in c.questions:
            raise CourseError(["That question wasn't found."])
        right = [x.strip() for x in f.get("right", "").splitlines() if x.strip()]
        wrong = [x.strip() for x in f.get("wrong", "").splitlines() if x.strip()]
        if not right or not wrong:
            raise CourseError(["A question needs text, one right answer and at least one wrong answer."])
        from .canon import sha256_hex
        texts = right + wrong
        keys = sorted(texts, key=lambda t: sha256_hex(f"{qid}{t}".encode()))
        options = {f"o{i}": t for i, t in enumerate(keys, start=1)}
        back = {t: k for k, t in options.items()}
        c.questions[qid] = {"text": f.get("text", "").strip() or c.questions[qid]["text"], "options": options,
                            "show": max(2, min(int(f.get("show") or 4), len(options)))}
        c.answers[qid] = {"right": [back[t] for t in right], "why": f.get("why", "").strip()}
    elif action == "edit_lesson":
        for m in c.modules:
            for les in m["lessons"]:
                if les["id"] == f.get("lesson"):
                    les["title"] = f.get("title", "").strip() or les["title"]
                    les["content"] = f.get("content", "")
                    les["minutes"] = int(f.get("minutes") or 0)
                    if "media" in f:
                        media = _lesson_media(f)
                        if media:
                            les["media"] = media
                        else:
                            les.pop("media", None)
    elif action == "add_media":
        ref = f.get("ref", "").strip()
        target = (f"<{ref}>" if " " in ref else ref)
        for m in c.modules:
            for les in m["lessons"]:
                if les["id"] == f.get("lesson"):
                    line = f"![{f.get('label', '').strip()}]({target})"
                    les["content"] = (les["content"].rstrip() + "\n\n" + line + "\n").lstrip()
    elif action == "delete_lesson" and mod:
        if len(mod["lessons"]) <= 1:
            raise CourseError(["A module needs at least one lesson. Delete the module instead."])
        mod["lessons"] = [les for les in mod["lessons"] if les["id"] != f.get("lesson")]
    elif action == "rename_module" and mod:
        mod["title"] = f.get("title", "").strip() or mod["title"]
    elif action == "delete_module" and mod:
        if len(c.modules) <= 1:
            raise CourseError(["A course needs at least one module."])
        c.modules = [m for m in c.modules if m is not mod]
    elif action == "add_task" and mod:
        kind = f.get("type")
        rid = _unique(f"{mod['id']}-r", ids)
        task = {"id": rid, "type": kind, "prompt": f.get("prompt", "").strip()}
        if f.get("optional") == "1":
            task["optional"] = True
        if kind == "quiz":
            task["questions"] = [q for q in f.get("questions", []) if q in c.questions]
            task["pass"] = int(f.get("pass") or 70)
        elif kind == "explain":
            task["min_words"] = int(f.get("min_words") or 40)
        mod["requires"].append(task)
    elif action == "delete_task" and mod:
        mod["requires"] = [r for r in mod["requires"] if r["id"] != f.get("task")]
    elif action == "add_question":
        right = [x.strip() for x in f.get("right", "").splitlines() if x.strip()]
        wrong = [x.strip() for x in f.get("wrong", "").splitlines() if x.strip()]
        qid = _unique("q", set(c.questions))
        opts = {f"o{i}": t for i, t in enumerate(right + wrong, start=1)}
        # Shuffle option ids so their order says nothing about which are right.
        from .canon import sha256_hex
        keys = sorted(opts, key=lambda k: sha256_hex(f"{qid}{opts[k]}".encode()))
        options = {f"o{i}": opts[k] for i, k in enumerate(keys, start=1)}
        back = {t: k for k, t in options.items()}
        c.questions[qid] = {"text": f.get("text", "").strip(), "options": options,
                            "show": max(2, min(int(f.get("show") or 4), len(options)))}
        c.answers[qid] = {"right": [back[t] for t in right], "why": f.get("why", "").strip()}
    elif action == "delete_question":
        qid = f.get("question")
        used = [m["title"] for m in c.modules for r in m["requires"] if qid in r.get("questions", [])]
        if used:
            raise CourseError([f"This question is used in a quiz ({', '.join(used)}). Remove it from the quiz first."])
        c.questions.pop(qid, None)
        c.answers.pop(qid, None)
    else:
        raise CourseError(["That change isn't possible."])
    bump(c)
    return save(v, c)


# ---------- the whole course as one text file (for people who like that) ----

def course_to_yaml(c: Course) -> str:
    """Everything in one YAML: lessons with their text, tasks, and questions as right/wrong lists."""
    modules = []
    for m in c.modules:
        lessons = []
        for les in m["lessons"]:
            e = {"id": les["id"], "title": les["title"]}
            if les.get("media"):
                e["media"] = les["media"]
            if les.get("minutes"):
                e["minutes"] = les["minutes"]
            if les.get("content", "").strip():
                e["content"] = les["content"].rstrip() + "\n"
            lessons.append(e)
        mod = {"id": m["id"], "title": m["title"], "lessons": lessons}
        if m["requires"]:
            mod["requires"] = m["requires"]
        modules.append(mod)
    head = {"id": c.id, "title": c.title, "version": c.version, "description": c.description,
            "language": c.language, "modules": modules}
    if c.extra.get("image"):
        head["image"] = c.extra["image"]
    if c.extra.get("book"):
        head["book"] = c.extra["book"]
    if c.extra.get("book_info"):
        head["book_info"] = c.extra["book_info"]
    if c.extra.get("downloads"):
        head["downloads"] = c.extra["downloads"]
    if c.questions:
        qs = {}
        ans = c.answers or {}
        for qid, q in c.questions.items():
            right_ids = ans.get(qid, {}).get("right", [])
            qs[qid] = {"text": q["text"], "right": [q["options"][o] for o in right_ids if o in q["options"]],
                       "wrong": [t for o, t in q["options"].items() if o not in right_ids], "show": q["show"]}
            if ans.get(qid, {}).get("why"):
                qs[qid]["why"] = ans[qid]["why"]
        head["questions"] = qs

    class _Dumper(yaml.SafeDumper):
        pass

    def _str(dumper, data):
        style = "|" if "\n" in data else None
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)
    _Dumper.add_representer(str, _str)
    return yaml.dump(head, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110)


def save_yaml(v: Vault, course_id: str, text: str) -> Course:
    """Save the whole course from its YAML text. Checked like any course file; the id stays the same."""
    c = load_course({"course.yaml": text})
    c.id = course_id
    old = v.get_course(course_id)
    if old:
        c.extra.update(old.extra)
        if c.answers is None and old.answers:
            c.answers = old.answers
    return save(v, c)
