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
MAX_MEDIA_PACK_BYTES = 2 * 1024 * 1024 * 1024  # packs that carry their own videos can be big
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
REQ_TYPES = ("practical", "explain", "quiz")


# ---------------------------------------------------------------------------
# Media: videos, audio, web pages, pictures and online videos inside lessons
# ---------------------------------------------------------------------------

VIDEO_EXT = (".mp4", ".webm", ".m4v", ".mov", ".ogv", ".mkv")
AUDIO_EXT = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac", ".weba")
HTML_EXT = (".html", ".htm")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
DOC_EXT = (".pdf",)
OFFICE_EXT = (".docx", ".pptx", ".xlsx", ".xlsm")  # shown as a light, view-only preview (office.py)
CODE_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".kt", ".c", ".h", ".cpp", ".hpp", ".cc",
            ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".scala", ".dart", ".lua", ".r", ".jl", ".sh", ".bash",
            ".zsh", ".ps1", ".bat", ".sql", ".css", ".scss", ".less", ".vue", ".svelte", ".json", ".yaml", ".yml",
            ".toml", ".ini", ".cfg", ".conf", ".xml", ".env", ".txt", ".ipynb", ".tf", ".gradle", ".dockerignore",
            ".gitignore", ".csv", ".log", ".proto", ".graphql")
CODE_NAMES = ("dockerfile", "makefile", "procfile", "jenkinsfile", "vagrantfile", "gemfile", "rakefile")
MEDIA_EXT = VIDEO_EXT + AUDIO_EXT + HTML_EXT + IMAGE_EXT + DOC_EXT + OFFICE_EXT + CODE_EXT
_YT = re.compile(r"^https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{6,15})")
_VIMEO = re.compile(r"^https?://(?:www\.)?(?:player\.)?vimeo\.com/(?:video/)?(\d{5,12})")


def is_url(ref: str) -> bool:
    return bool(re.match(r"^https?://", ref or "", re.I))


def media_kind(ref: str) -> str:
    """video, audio, html, image, pdf, office, youtube, vimeo, link, code, folder, or '' for anything else."""
    ref = (ref or "").strip()
    if _YT.match(ref):
        return "youtube"
    if _VIMEO.match(ref):
        return "vimeo"
    low = ref.lower().split("?")[0].split("#")[0]
    for kind, exts in (("video", VIDEO_EXT), ("audio", AUDIO_EXT), ("html", HTML_EXT), ("image", IMAGE_EXT),
                       ("pdf", DOC_EXT), ("office", OFFICE_EXT)):
        if low.endswith(exts):
            return kind
    if is_url(ref):
        return "link"
    if low.endswith("/"):
        return "folder"  # a project folder: its code files are shown one under the other
    name = low.rsplit("/", 1)[-1]
    if low.endswith(CODE_EXT) or name in CODE_NAMES or name.startswith("dockerfile") or name.startswith("docker-compose"):
        return "code"
    return ""


def embed_id(ref: str) -> str:
    m = _YT.match(ref) or _VIMEO.match(ref)
    return m.group(1) if m else ""


def parse_downloads(raw) -> list[dict]:
    """Links where learners can download the course's own files (videos too big to share in the course file).
    In course.yaml:  downloads: [{title: All videos, url: https://..., size: 2.3 GB}]"""
    out = []
    for d in raw if isinstance(raw, list) else []:
        if isinstance(d, str):
            d = {"url": d}
        if not isinstance(d, dict) or not is_url(str(d.get("url", ""))):
            continue
        item = {"title": str(d.get("title") or "Course files").strip()[:120], "url": str(d["url"]).strip()}
        if d.get("size"):
            item["size"] = str(d["size"]).strip()[:20]
        out.append(item)
    return out[:10]


def downloads_from_lines(text: str) -> list[dict]:
    """The editor's box: one link per line, as  Title | https://link | size  (title and size optional)."""
    out = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split("|")]
        url = next((p for p in parts if is_url(p)), None)
        if not url:
            continue
        rest = [p for p in parts if p and p != url]
        item = {"title": rest[0] if rest else "Course files", "url": url}
        if len(rest) > 1:
            item["size"] = rest[1]
        out.append(item)
    return parse_downloads(out)


def safe_media_path(ref: str) -> str | None:
    """A file path inside the course (no going up a folder, no drive letters). None if it's not safe."""
    ref = (ref or "").strip().replace("\\", "/")
    if not ref or is_url(ref) or ref.startswith("/") or re.match(r"^[A-Za-z]:", ref):
        return None
    parts = [x for x in ref.split("/") if x not in ("", ".")]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


_PAGES = re.compile(r"#pages?=(\d{1,5})(?:-(\d{1,5}))?$")


def page_range(ref: str) -> tuple[str, tuple[int, int] | None]:
    """"book.pdf#pages=19-35" -> ("book.pdf", (19, 35)): a lesson that shows only part of a PDF."""
    m = _PAGES.search(ref or "")
    if not m:
        return ref, None
    a, b = int(m.group(1)), int(m.group(2) or m.group(1))
    return ref[:m.start()], (min(a, b), max(a, b))


def local_ref(ref: str) -> str | None:
    """A file on this computer: a path inside the course folder, or a full path the course points to."""
    ref = page_range((ref or "").strip())[0].replace("\\", "/")
    if not ref or is_url(ref):
        return None
    if ref.startswith(("/", "~/")) or re.match(r"^[A-Za-z]:/", ref):
        return None if ".." in ref.split("/") else ref
    rel = safe_media_path(ref)
    return rel + "/" if rel and ref.endswith("/") else rel


def is_full_path(ref: str) -> bool:
    return bool(ref) and (ref.startswith(("/", "~/")) or bool(re.match(r"^[A-Za-z]:/", ref)))


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


def files_from_zip(data) -> dict[str, str]:
    """data: the pack's bytes, or an open file (for big packs that carry videos)."""
    if isinstance(data, (bytes, bytearray)) and len(data) > MAX_PACK_BYTES:
        raise CourseError(["This course file is too big (over 50 MB)."])
    try:
        zf = zipfile.ZipFile(io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data)
    except zipfile.BadZipFile:
        raise CourseError(["This doesn't look like a course file."])
    files: dict[str, str] = {}
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        parts = name.split("/")
        if info.is_dir() or ".." in parts or name.startswith("/"):
            continue
        if name.endswith((".yaml", ".yml", ".md")) and "/files/" not in "/" + name and info.file_size < 20_000_000:
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
        if p.is_file() and p.suffix in (".yaml", ".yml", ".md") and "files" not in p.relative_to(folder).parts[:1]:
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
            media = str(rl.get("media") or rl.get("video") or rl.get("audio") or rl.get("url") or "").strip()
            if media and not is_url(media) and not local_ref(media):
                problems.append(f"Lesson {li} in module {mi}: the media '{media}' must be a web link or a file path.")
                media = ""
            elif media and not is_url(media):
                base, pages = page_range(media)
                media = local_ref(base) or ""
                if media and pages and media_kind(media) == "pdf":
                    media += f"#pages={pages[0]}-{pages[1]}"  # a part of a book
            content = rl.get("content")
            if content is None and rl.get("file"):
                fname = str(rl["file"]).replace("\\", "/")
                content = files.get(fname)
                if content is None:
                    problems.append(f"Module {mi}, lesson {li}: the file '{fname}' is missing.")
                    content = ""
            content = str(content or "")
            ltitle = str(rl.get("title") or _first_heading(content) or f"Lesson {li}")
            if not content.strip() and not media:
                problems.append(f"Lesson '{ltitle}' (module {mi}) has no content.")
            les = {"id": lid, "title": ltitle, "content": content, "minutes": _int(rl.get("minutes"), 0)}
            if media:
                les["media"] = media  # only present when used, so older courses keep the same fingerprint
            lessons.append(les)
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
    downloads = parse_downloads(raw.get("downloads"))
    if downloads:
        course.extra["downloads"] = downloads
    book = raw.get("book")
    if isinstance(book, str) and safe_media_path(book) and media_kind(book) == "pdf":
        course.extra["book"] = safe_media_path(book)  # the book the lessons show parts of (not shared with the course)
    image = raw.get("image")
    if isinstance(image, str) and safe_media_path(image) and media_kind(image) == "image":
        course.extra["image"] = safe_media_path(image)  # the course's cover picture, a file next to the course
    index = raw.get("media_index")
    if isinstance(index, dict):
        course.extra["media_index"] = {str(k): _int(v, 0) for k, v in index.items() if safe_media_path(str(k))}
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
            entry = {"id": les["id"], "title": les["title"]}
            if les.get("content", "").strip() or not les.get("media"):
                path = f"lessons/{les['id']}.md"
                files[path] = les["content"]
                entry["file"] = path
            if les.get("media"):
                entry["media"] = les["media"]
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
    if course.extra.get("image"):
        head["image"] = course.extra["image"]
    if course.extra.get("downloads"):
        head["downloads"] = course.extra["downloads"]
    if course.extra.get("book"):
        head["book"] = course.extra["book"]
    if course.extra.get("media_index"):
        head["media_index"] = course.extra["media_index"]
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


def write_pack_with_media(course: Course, include_answers: bool, media: dict[str, Path], out: Path) -> None:
    """Like course_to_pack, but written to a file on disk and carrying the course's own files."""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in course_to_files(course, include_answers).items():
            zf.writestr(name, text)
        for rel, src in media.items():
            # Videos and audio are already compressed; storing them is much faster.
            kind = zipfile.ZIP_DEFLATED if rel.lower().endswith(HTML_EXT + (".svg",)) else zipfile.ZIP_STORED
            zf.write(src, f"files/{rel}", compress_type=kind)


def media_in_zip(zf: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    """The course's own files inside a pack: (zip entry, path inside the course)."""
    out = []
    names = [i.filename.replace("\\", "/") for i in zf.infolist()]
    tops = {n.split("/")[0] for n in names if "/" in n}
    strip = ""
    if "course.yaml" not in names and len(tops) == 1:
        strip = next(iter(tops)) + "/"
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if info.is_dir() or not name.startswith(strip + "files/"):
            continue
        rel = safe_media_path(name[len(strip + "files/"):])
        if rel:
            out.append((info, rel))
    return out


# ---------------------------------------------------------------------------
# A folder of videos (or any lesson files) already on this computer -> a course
# ---------------------------------------------------------------------------

def _natural(s: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def _nice_title(name: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", name)
    stem = re.sub(r"^\s*(?:\d+[\s._)\]-]+)+", "", stem)  # "01 - ", "3. ", "02_"
    stem = re.sub(r"[_]+", " ", stem).strip(" -.")
    return stem or name


LESSON_EXT = MEDIA_EXT + (".md",)
COVER_NAMES = {"cover", "folder", "poster", "thumbnail", "course"}  # a picture with one of these names is the cover
SKIP_DIRS = {"node_modules", "__pycache__", "venv", ".venv", ".git", "dist", "build", ".idea", ".vscode"}


def folder_groups(folder: Path, title: str = "") -> list[tuple[str, list[Path]]]:
    """The folder as it is: each sub-folder becomes a module and each video, audio, page or note inside it a lesson."""
    folder = Path(folder)
    if not folder.is_dir():
        raise CourseError(["That folder wasn't found. Copy its full path and paste it here."])

    def usable(p: Path) -> bool:
        if not p.is_file() or p.name.startswith(".") or p.name in ("course.yaml", "questions.yaml", "answers.yaml"):
            return False
        if p.parent == folder and p.stem.lower() in COVER_NAMES and media_kind(p.name) == "image":
            return False
        return p.suffix.lower() == ".md" or media_kind(p.name) not in ("", "folder", "link")

    def lessons_in(d: Path) -> list[Path]:
        return sorted((p for p in d.iterdir() if usable(p)), key=lambda p: _natural(p.name))

    groups: list[tuple[str, list[Path]]] = []
    top = lessons_in(folder)
    if top:
        groups.append((title or _nice_title(folder.name), top))
    for sub in sorted((p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: _natural(p.name)):
        found: list = []
        for item in sorted(sub.iterdir(), key=lambda p: _natural(p.name)):
            if item.is_file() and usable(item):
                found.append(item)
            elif item.is_dir() and not item.name.startswith(".") and item.name not in SKIP_DIRS:
                inner = [p for p in item.rglob("*") if usable(p)
                         and not any(x.startswith(".") or x in SKIP_DIRS for x in p.relative_to(item).parts[:-1])]
                if any(media_kind(p.name) in ("video", "audio") for p in inner):
                    found += sorted(inner, key=lambda p: _natural(str(p.relative_to(item))))
                elif inner:
                    found.append(item)  # a project folder with code: one lesson that shows all its files
        if found:
            groups.append((_nice_title(sub.name), found))
    if not groups:
        raise CourseError(["That folder has no videos, audio, web pages, PDFs, code or notes inside."])

    return groups


def course_from_folder(folder: Path, title: str = "") -> Course:
    """Each sub-folder becomes a module and each video, audio, page or note inside it a lesson.
    Nothing is copied: the course points to the files where they are."""
    folder = Path(folder)
    return course_from_groups(folder, title, folder_groups(folder, title))


def course_from_groups(folder: Path, title: str, groups: list[tuple[str, list[Path]]]) -> Course:
    """Make a course from sections of files (all inside the folder)."""
    folder = Path(folder)
    modules, index = [], {}
    for mi, (mtitle, files) in enumerate(groups, start=1):
        lessons = []
        for li, f in enumerate(files, start=1):
            rel = f.relative_to(folder).as_posix()
            les = {"id": f"m{mi}-l{li}", "title": _nice_title(f.name), "content": "", "minutes": 0}
            if f.is_dir():
                les["media"] = rel + "/"
                lessons.append(les)
                continue
            if f.suffix.lower() == ".md":
                les["content"] = f.read_text(encoding="utf-8", errors="replace")
                les["title"] = _first_heading(les["content"]) or les["title"]
            else:
                les["media"] = rel
                index[rel] = f.stat().st_size
            lessons.append(les)
        modules.append({"id": f"m{mi}", "title": mtitle, "lessons": lessons, "requires": []})
    name = title.strip() or _nice_title(folder.name)
    c = Course(id=_slug(name) or "course", title=name, version="1", description="", language="en",
               modules=modules, questions={}, answers=None)
    c.extra["media_index"] = index
    cover = next((p for p in sorted(folder.iterdir()) if p.is_file() and p.stem.lower() in COVER_NAMES
                  and media_kind(p.name) == "image"), None)
    if cover:
        c.extra["image"] = cover.name
        index[cover.name] = cover.stat().st_size
    c.hash = fingerprint(c.public_dict())
    return c
