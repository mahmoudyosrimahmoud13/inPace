"""Make and change courses with simple forms. Every change is checked before it's saved."""
from __future__ import annotations

import copy
import re

from .course import Course, CourseError, course_to_files, load_course
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


def save(v: Vault, c: Course) -> Course:
    """Round-trip through the normal loader so every rule is checked."""
    fresh = load_course(course_to_files(c))
    return v.install_course(fresh)


def new_course(v: Vault, title: str, description: str, module_title: str, lesson_title: str, content: str) -> Course:
    cid = _slug(title)
    while v.get_course(cid):
        cid = _unique(cid + "-", set(p.name for p in (v.home / "courses").iterdir()))
    c = Course(id=cid, title=title.strip(), version="1", description=description.strip(), language="en",
               modules=[{"id": "m1", "title": module_title.strip() or "Module 1",
                         "lessons": [{"id": "m1-l1", "title": lesson_title.strip(), "content": content, "minutes": 0}],
                         "requires": []}],
               questions={}, answers={})
    return save(v, c)


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
    elif action == "add_module":
        mid = _unique("m", ids)
        lid = f"{mid}-l1"
        c.modules.append({"id": mid, "title": f.get("title", "").strip() or "New module",
                          "lessons": [{"id": lid, "title": f.get("lesson_title", "").strip() or "First lesson",
                                       "content": f.get("content", ""), "minutes": 0}], "requires": []})
    elif action == "add_lesson" and mod:
        lid = _unique(f"{mod['id']}-l", ids)
        mod["lessons"].append({"id": lid, "title": f.get("title", "").strip(), "content": f.get("content", ""),
                               "minutes": int(f.get("minutes") or 0)})
    elif action == "edit_lesson":
        for m in c.modules:
            for les in m["lessons"]:
                if les["id"] == f.get("lesson"):
                    les["title"] = f.get("title", "").strip() or les["title"]
                    les["content"] = f.get("content", "")
                    les["minutes"] = int(f.get("minutes") or 0)
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
