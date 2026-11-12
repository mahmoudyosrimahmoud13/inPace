"""The inPace course library: a public GitHub repository of courses people made and shared.

  github.com/mahmoudyosrimahmoud13/inpace-library   the courses, the submission form and the checking bots
  .../inpace-library/library.json                  the list the app reads (built by GitHub Actions)

Authors publish from the app: inPace makes a course file signed with the author's own key, and opens the
library's submission form. The library only accepts updates to a course signed by the same key, so nobody can
take over someone else's course. The app only goes online here when you open the library or add a course.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile
from pathlib import Path
from urllib.parse import quote, urlencode

from .canon import now_utc
from .course import Course, CourseError, course_to_files, files_from_zip, load_course
from .identity import verify

REPO = "mahmoudyosrimahmoud13/inpace-library"
SITE = "https://mahmoudyosrimahmoud13.github.io/inpace-library/"
INDEX_URL = SITE + "library.json"
SUBMIT_URL = f"https://github.com/{REPO}/issues/new"
REPORT_URL = f"https://github.com/{REPO}/issues/new"
AUTHOR_FILE = "inpace-author.json"
MAX_COURSE_BYTES = 20 * 1024 * 1024
CACHE_SECONDS = 3600
LICENSES = {
    "CC-BY-4.0": "CC BY 4.0: anyone can use and share it, and must credit you",
    "CC-BY-SA-4.0": "CC BY-SA 4.0: like CC BY, and changed copies must use the same license",
    "CC0-1.0": "CC0: no rights reserved, anyone can do anything with it",
}


class LibraryProblem(Exception):
    pass


# ---------------------------------------------------------------------------
# Authors: a signed course file for the library
# ---------------------------------------------------------------------------

def _author_payload(course_id: str, version: str, course_hash: str, author_id: str, name: str, at: str) -> dict:
    return {"kind": "library-course", "course": course_id, "version": str(version), "hash": course_hash,
            "author": author_id, "name": name, "at": at}


def sign_course(identity, name: str, course: Course) -> dict:
    at = now_utc()
    payload = _author_payload(course.id, course.version, course.hash, identity.id, name, at)
    return {**payload, "sig": identity.sign(payload)}


def make_submission(identity, name: str, course: Course, media: dict[str, Path] | None = None) -> bytes:
    """A .zip with the course (with answers, so practice quizzes work), its own small files such as the
    cover picture, and the author's signature."""
    files = course_to_files(course, True)
    signed = load_course(files)  # sign exactly what the library will read back
    signed.extra.update({k: v for k, v in course.extra.items() if k not in signed.extra})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, text in files.items():
            zf.writestr(fname, text)
        for rel, src in (media or {}).items():
            zf.write(src, f"files/{rel}")
        zf.writestr(AUTHOR_FILE, json.dumps(sign_course(identity, name, signed), ensure_ascii=False, indent=1))
    data = buf.getvalue()
    if len(data) > MAX_COURSE_BYTES:
        raise LibraryProblem("This course is over 20 MB with its files. Put big videos on YouTube and use links.")
    return data


def check_author(author: dict, course: Course) -> str | None:
    """None if the signature is good and matches this exact course, otherwise what's wrong."""
    try:
        payload = _author_payload(author["course"], author["version"], author["hash"], author["author"],
                                  author["name"], author["at"])
    except (KeyError, TypeError):
        return "The author signature is missing parts. Make the file again with Publish to the library."
    if not verify(str(author["author"]), payload, str(author.get("sig", ""))):
        return "The author signature doesn't match. Make the file again with Publish to the library."
    if author["course"] != course.id or author["hash"] != course.hash:
        return "The course was changed after it was signed. Make the file again with Publish to the library."
    return None


def read_submission(data: bytes) -> tuple[Course, dict]:
    """Library side: open a submitted .zip and check it. Returns the course and the author signature."""
    if len(data) > MAX_COURSE_BYTES:
        raise LibraryProblem("The course file is over 20 MB.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise LibraryProblem("The attached file isn't a .zip course file.")
    try:
        course = load_course(files_from_zip(data))
    except CourseError as e:
        raise LibraryProblem("The course has problems:\n- " + "\n- ".join(e.problems))
    names = {i.filename.split("/")[-1]: i for i in zf.infolist()}
    if AUTHOR_FILE not in names:
        raise LibraryProblem("The course isn't signed. In inPace, use More → Publish to the library to make the file.")
    author = json.loads(zf.read(names[AUTHOR_FILE]).decode("utf-8"))
    problem = check_author(author, course)
    if problem:
        raise LibraryProblem(problem)
    return course, author


def submit_url(course: Course) -> str:
    q = {"template": "submit-course.yml", "title": f"Course: {course.title}", "course_title": course.title,
         "course_id": course.id, "description": course.description or "",
         "language": "Arabic" if course.language == "ar" else "English"}
    return SUBMIT_URL + "?" + urlencode(q, quote_via=quote)


# ---------------------------------------------------------------------------
# Learners: browse and add courses
# ---------------------------------------------------------------------------

def _get(url: str, timeout: float = 20):
    from .updater import _get as get
    return get(url, timeout)


def load_index(home: Path, refresh: bool = False) -> dict:
    """The library's list of courses, from a copy saved within the last hour or freshly downloaded."""
    cache = home / "library.json"
    if not refresh and cache.exists() and time.time() - cache.stat().st_mtime < CACHE_SECONDS:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            pass
    try:
        with _get(INDEX_URL) as r:
            raw = r.read(5_000_000)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("courses"), list):
            raise ValueError("not a library index")
    except Exception as e:
        if cache.exists():  # offline: show the last list we had
            data = json.loads(cache.read_text(encoding="utf-8"))
            data["offline"] = True
            return data
        raise LibraryProblem("The library couldn't be reached. Check your internet connection and try again.") from e
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def cached_index(home: Path) -> dict:
    """The last library list we downloaded, without going online. Empty if we never looked."""
    try:
        return json.loads((home / "library.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def share_data(entry: dict) -> dict:
    """What goes inside an inPace link that points to a library course (small, no course content)."""
    return {"inpace": "library-course", "id": entry["id"], "title": entry.get("title", ""),
            "author": (entry.get("author") or {}).get("name", "")}


def find(index: dict, course_id: str) -> dict | None:
    return next((c for c in index.get("courses", []) if c.get("id") == course_id), None)


def download(entry: dict) -> bytes:
    """Download a course from the library and make sure it's exactly the file the library lists."""
    url = str(entry.get("pack", ""))
    if not url.startswith(SITE):
        raise LibraryProblem("That course's link doesn't point to the inPace library.")
    try:
        with _get(url, timeout=60) as r:
            data = r.read(MAX_COURSE_BYTES + 1)
    except Exception as e:
        raise LibraryProblem("The course couldn't be downloaded. Check your internet connection.") from e
    if len(data) > MAX_COURSE_BYTES or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
        raise LibraryProblem("The downloaded course doesn't match the library's list. Try again later.")
    return data
