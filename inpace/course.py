"""Course packs: loading, checking, saving and sharing.

A course can arrive as:
  * a folder or .lpack file with course.yaml, lessons/*.md, questions.yaml, answers.yaml
  * one single YAML text (the "all in one" format AI chats produce),
    with lesson text inline and questions written as right/wrong lists.
Both become the same normalized course. See SPEC.md, "Course packs".
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .canon import fingerprint, sha256_hex

MAX_PACK_BYTES = 50 * 1024 * 1024
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
REQ_TYPES = ("practical", "explain", "quiz")


class CourseError(Exception):
    """Raised with a list of plain-language problems."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class Course:
    id: str
    title: str
    version: str
    description: str
    language: str
    modules: list[dict]
    questions: dict[str, dict]
    answers: dict[str, dict] | None = None
    hash: str = ""
    extra: dict = field(default_factory=dict)

    # ---- lookups -------------------------------------------------------
    def find_lesson(self, lesson_id: str) -> tuple[dict, dict] | None:
        for m in self.modules:
            for les in m["lessons"]:
                if les["id"] == lesson_id:
                    return m, les
        return None

    def find_requirement(self, req_id: str) -> tuple[dict, dict] | None:
        for m in self.modules:
            for r in m["requires"]:
                if r["id"] == req_id:
                    return m, r
        return None

    @property
    def lesson_count(self) -> int:
        return sum(len(m["lessons"]) for m in self.modules)

    @property
    def has_answers(self) -> bool:
        return bool(self.answers)

    def public_dict(self) -> dict:
        """Everything except the answers. This is what the fingerprint covers."""
        return {
            "id": self.id,
            "title": self.title,
            "version": self.version,
            "description": self.description,
            "language": self.language,
            "modules": self.modules,
            "questions": self.questions,
        }


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _yaml(text: str, name: str, problems: list[str]) -> Any:
    try:
        return yaml.safe_load(text) if text.strip() else None
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" (around line {mark.line + 1})" if mark else ""
        problems.append(f"{name} has a formatting mistake{where}. Check spacing and colons.")
        return None


def strip_fences(text: str) -> str:
    """AI chats often wrap the answer in ``` fences or add a sentence before it.

    Only fences at the start of a line count. Code blocks inside lesson text are
    indented, so they are never mistaken for the wrapper."""
    m = re.search(r"^```ya?ml[ \t]*\n(.*?)^```[ \t]*$", text, re.S | re.M | re.I)
    if m:
        return m.group(1)
    if text.lstrip().startswith("```"):
        m = re.search(r"^```[^\n]*\n(.*?)^```[ \t]*$", text, re.S | re.M)
        if m:
            return m.group(1)
    return text


def files_from_zip(data: bytes) -> dict[str, str]:
    if len(data) > MAX_PACK_BYTES:
        raise CourseError(["This course file is too big (over 50 MB)."])
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise CourseError(["This doesn't look like a course file."])
    files: dict[str, str] = {}
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        parts = name.split("/")
        if info.is_dir() or ".." in parts or name.startswith("/"):
            continue
        if name.endswith((".yaml", ".yml", ".md")):
            files[name] = zf.read(info).decode("utf-8", errors="replace")
    # Remove a single shared top-level folder if present.
    tops = {n.split("/")[0] for n in files if "/" in n}
    if "course.yaml" not in files and len(tops) == 1:
        top = tops.pop() + "/"
        files = {n[len(top):]: t for n, t in files.items() if n.startswith(top)}
    return files


def files_from_folder(folder: Path) -> dict[str, str]:
    files = {}
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix in (".yaml", ".yml", ".md"):
            files[p.relative_to(folder).as_posix()] = p.read_text(encoding="utf-8")
    return files


def load_course(files: dict[str, str]) -> Course:
    problems: list[str] = []
    if "course.yaml" not in files:
        raise CourseError(["The course is missing its main file (course.yaml)."])
    raw = _yaml(files["course.yaml"], "course.yaml", problems)
    if problems:
        raise CourseError(problems)
    if not isinstance(raw, dict):
        raise CourseError(["course.yaml should describe the course (title, modules, ...)."])

    title = str(raw.get("title") or "").strip()
    if not title:
        problems.append("The course needs a title.")
    cid = str(raw.get("id") or _slug(title) or "course")
    if not ID_RE.match(cid):
        cid = _slug(cid) or "course"

    # ---- questions + answers -------------------------------------------
    questions: dict[str, dict] = {}
    answers: dict[str, dict] = {}
    inline = raw.get("questions")
    if inline:
        questions, answers = _normalize_inline_questions(inline, problems)
    if "questions.yaml" in files:
        q2 = _yaml(files["questions.yaml"], "questions.yaml", problems) or {}
        if isinstance(q2, dict):
            for qid, q in q2.items():
                questions[str(qid)] = _normalize_split_question(str(qid), q, problems)
    if "answers.yaml" in files:
        a2 = _yaml(files["answers.yaml"], "answers.yaml", problems) or {}
        if isinstance(a2, dict):
            for qid, a in a2.items():
                if isinstance(a, dict):
                    answers[str(qid)] = {
                        "right": [str(x) for x in (a.get("right") or [])],
                        "why": str(a.get("why") or ""),
                    }
    for qid, a in answers.items():
        q = questions.get(qid)
        if not q:
            problems.append(f"The answer key mentions question '{qid}', which doesn't exist.")
            continue
        bad = [r for r in a["right"] if r not in q["options"]]
        if bad:
            problems.append(f"Question '{qid}': the answer key points to options that don't exist ({', '.join(bad)}).")
        wrong_count = len(q["options"]) - len(a["right"])
        if not a["right"]:
            problems.append(f"Question '{qid}' needs at least one right answer.")
        if wrong_count < q["show"] - 1:
            problems.append(
                f"Question '{qid}' shows {q['show']} choices, so it needs at least {q['show'] - 1} wrong answers (it has {wrong_count})."
            )

    # ---- modules --------------------------------------------------------
    modules = []
    raw_modules = raw.get("modules") or []
    if not isinstance(raw_modules, list) or not raw_modules:
        problems.append("The course needs at least one module.")
        raw_modules = []
    seen: set[str] = set()
    for mi, rm in enumerate(raw_modules, start=1):
        if not isinstance(rm, dict):
            problems.append(f"Module {mi} is not written correctly.")
            continue
        mid = str(rm.get("id") or f"m{mi}")
        mtitle = str(rm.get("title") or "").strip() or f"Module {mi}"
        lessons = []
        for li, rl in enumerate(rm.get("lessons") or [], start=1):
            if isinstance(rl, str):
                rl = {"file": rl}
            if not isinstance(rl, dict):
                problems.append(f"Module {mi}, lesson {li} is not written correctly.")
                continue
            lid = str(rl.get("id") or f"{mid}-l{li}")
            content = rl.get("content")
            if content is None and rl.get("file"):
                fname = str(rl["file"]).replace("\\", "/")
                content = files.get(fname)
                if content is None:
                    problems.append(f"Module {mi}, lesson {li}: the file '{fname}' is missing.")
                    content = ""
            content = str(content or "")
            ltitle = str(rl.get("title") or _first_heading(content) or f"Lesson {li}")
            if not content.strip():
                problems.append(f"Lesson '{ltitle}' (module {mi}) has no content.")
            lessons.append({"id": lid, "title": ltitle, "content": content, "minutes": _int(rl.get("minutes"), 0)})
            _dup(lid, seen, problems)
        if not lessons:
            problems.append(f"Module {mi} ('{mtitle}') has no lessons.")
        reqs = []
        for ri, rr in enumerate(rm.get("requires") or [], start=1):
            if not isinstance(rr, dict):
                problems.append(f"Module {mi}, requirement {ri} is not written correctly.")
                continue
            rtype = str(rr.get("type") or "").lower()
            if rtype not in REQ_TYPES:
                problems.append(
                    f"Module {mi}, requirement {ri}: type should be practical, explain or quiz (it says '{rtype}')."
                )
                continue
            rid = str(rr.get("id") or f"{mid}-r{ri}")
            req = {"id": rid, "type": rtype, "prompt": str(rr.get("prompt") or "").strip()}
            if rtype == "quiz":
                qids = [str(q) for q in (rr.get("questions") or [])]
                if not qids:
                    problems.append(f"Module {mi}: the quiz needs a list of questions.")
                missing = [q for q in qids if q not in questions]
                if missing:
                    problems.append(f"Module {mi}: the quiz uses questions that don't exist ({', '.join(missing)}).")
                req["questions"] = qids
                req["pass"] = _int(rr.get("pass"), 70)
                if not req["prompt"]:
                    req["prompt"] = f"Quiz: {len(qids)} questions, {req['pass']}% to pass."
            elif rtype == "explain":
                req["min_words"] = _int(rr.get("min_words"), 40)
                if not req["prompt"]:
                    problems.append(f"Module {mi}: the 'explain' requirement needs a prompt (what to explain).")
            elif not req["prompt"]:
                problems.append(f"Module {mi}: the practical requirement needs a prompt (what to make).")
            reqs.append(req)
            _dup(rid, seen, problems)
        modules.append({"id": mid, "title": mtitle, "lessons": lessons, "requires": reqs})
        _dup(mid, seen, problems)

    if problems:
        raise CourseError(problems)

    course = Course(
        id=cid,
        title=title,
        version=str(raw.get("version") or "1"),
        description=str(raw.get("description") or "").strip(),
        language=str(raw.get("language") or "en"),
        modules=modules,
        questions=questions,
        answers=answers or None,
    )
    course.hash = fingerprint(course.public_dict())
    return course


def _normalize_inline_questions(inline: Any, problems: list[str]) -> tuple[dict, dict]:
    """Author format: right: [...] wrong: [...]  -> options with neutral ids."""
    items = inline.items() if isinstance(inline, dict) else (
        (q.get("id") or f"q{i}", q) for i, q in enumerate(inline, start=1) if isinstance(q, dict)
    )
    questions, answers = {}, {}
    for qid, q in items:
        qid = str(qid)
        if not isinstance(q, dict):
            problems.append(f"Question '{qid}' is not written correctly.")
            continue
        right = [str(x) for x in (q.get("right") or [])]
        wrong = [str(x) for x in (q.get("wrong") or [])]
        if "options" in q:  # already split style, inline
            questions[qid] = _normalize_split_question(qid, q, problems)
            if right:
                answers[qid] = {"right": right, "why": str(q.get("why") or "")}
            continue
        if not right:
            problems.append(f"Question '{qid}' needs at least one right answer.")
        # Option ids come from the text's fingerprint, so their order says nothing
        # about which ones are right.
        texts = right + wrong
        ids = {}
        for t in texts:
            oid = "o" + sha256_hex(f"{qid}\x1f{t}".encode())[:6]
            ids[t] = oid
        options = {ids[t]: t for t in sorted(texts, key=lambda t: ids[t])}
        questions[qid] = {"text": str(q.get("text") or "").strip(), "options": options, "show": _int(q.get("show"), 4)}
        if not questions[qid]["text"]:
            problems.append(f"Question '{qid}' has no question text.")
        answers[qid] = {"right": [ids[t] for t in right], "why": str(q.get("why") or "")}
    return questions, answers


def _normalize_split_question(qid: str, q: Any, problems: list[str]) -> dict:
    if not isinstance(q, dict):
        problems.append(f"Question '{qid}' is not written correctly.")
        return {"text": "", "options": {}, "show": 4}
    opts = q.get("options") or {}
    if isinstance(opts, list):
        opts = {f"o{i}": v for i, v in enumerate(opts, start=1)}
    text = str(q.get("text") or "").strip()
    if not text:
        problems.append(f"Question '{qid}' has no question text.")
    return {"text": text, "options": {str(k): str(v) for k, v in opts.items()}, "show": max(2, _int(q.get("show"), 4))}


def _first_heading(md: str) -> str:
    for line in md.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")
    return s[:60]


def _int(v: Any, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _dup(i: str, seen: set[str], problems: list[str]) -> None:
    if i in seen:
        problems.append(f"The id '{i}' is used twice. Every module, lesson and requirement needs its own id.")
    seen.add(i)


def course_outline(course: Course) -> dict:
    return {"modules": [{"title": m["title"], "lessons": [les["title"] for les in m["lessons"]],
                         "requires": [f"{r['type']}: {r['prompt']}" for r in m["requires"]]}
                        for m in course.modules]}


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def course_to_files(course: Course, include_answers: bool = True) -> dict[str, str]:
    """The standard split layout: lessons as Markdown, questions and answers apart."""
    files: dict[str, str] = {}
    modules = []
    for m in course.modules:
        lessons = []
        for les in m["lessons"]:
            path = f"lessons/{les['id']}.md"
            files[path] = les["content"]
            entry = {"id": les["id"], "title": les["title"], "file": path}
            if les.get("minutes"):
                entry["minutes"] = les["minutes"]
            lessons.append(entry)
        modules.append({"id": m["id"], "title": m["title"], "lessons": lessons, "requires": m["requires"]})
    head = {
        "id": course.id,
        "title": course.title,
        "version": course.version,
        "description": course.description,
        "language": course.language,
        "modules": modules,
    }
    files["course.yaml"] = yaml.safe_dump(head, sort_keys=False, allow_unicode=True, width=100)
    if course.questions:
        files["questions.yaml"] = yaml.safe_dump(course.questions, sort_keys=False, allow_unicode=True, width=100)
    if include_answers and course.answers:
        files["answers.yaml"] = yaml.safe_dump(course.answers, sort_keys=False, allow_unicode=True, width=100)
    return files


def save_course_folder(course: Course, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in course_to_files(course).items():
        p = folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def course_to_pack(course: Course, include_answers: bool) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in course_to_files(course, include_answers).items():
            zf.writestr(name, text)
    return buf.getvalue()
