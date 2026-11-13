"""Courses that read a book you get yourself.

Some books are free to read but not to share (for example Mathematics for Machine Learning, free for personal use
at mml-book.com). A course built on such a book never carries it: its lessons point to pages of the book
("mml-book.pdf#pages=23-30"), and each learner shows inPace where their own copy is.

The course says which book it needs in course.yaml:

    book: mml-book.pdf
    book_info:
      title: Mathematics for Machine Learning
      url: https://mml-book.com
      pages: 412

inPace then finds the learner's copy even when the file has another name: in a folder they choose, or by looking in
the usual places (Downloads, Documents, Desktop, and the phone's Download folder). It recognizes the book by the
title saved inside the PDF or by its number of pages, and warns when the page count is different (another edition,
so the lessons could open the wrong pages). The chosen file is remembered per course ("bookfile:<course>").
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def clean_info(raw) -> dict:
    """The book_info block of course.yaml, kept only if it makes sense."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    title = str(raw.get("title") or "").strip()
    if title:
        out["title"] = title[:200]
    url = str(raw.get("url") or "").strip()
    if re.match(r"^https://[^\s<>\"']+$", url):
        out["url"] = url[:300]
    try:
        pages = int(raw.get("pages") or 0)
        if 0 < pages < 100_000:
            out["pages"] = pages
    except (TypeError, ValueError):
        pass
    return out


def pdf_facts(path: Path) -> tuple[int, str]:
    """(number of pages, title saved inside the PDF). (0, '') if it can't be read."""
    try:
        from pypdf import PdfReader
        r = PdfReader(str(path))
        title = ""
        try:
            title = str((r.metadata or {}).get("/Title") or "")
        except Exception:
            pass
        return len(r.pages), title.strip()
    except Exception:
        return 0, ""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9؀-ۿ]+", " ", (text or "").lower()).strip()


def score(path: Path, info: dict, name: str = "") -> int:
    """How sure we are that this PDF is the course's book: 0 (no) to 3 (title and pages agree)."""
    pages, title = pdf_facts(path)
    if not pages:
        return 0
    s = 0
    want_title = _norm(info.get("title", ""))
    if want_title and want_title in _norm(title):
        s += 2
    if info.get("pages") and pages == info["pages"]:
        s += 1
    if not want_title and not info.get("pages") and name and _norm(Path(name).stem) in _norm(path.stem):
        s += 1  # the course says nothing about the book: fall back to the file name
    return s


def find_in(folder: Path, info: dict, name: str = "", depth: int = 2, limit: int = 300) -> Path | None:
    """The best match for the book among the PDFs in this folder (and a couple of levels below)."""
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        return None
    best, best_score, seen = None, 0, 0
    exact = folder / name if name else None
    if exact and exact.is_file():
        s = score(exact, info, name) if info else 3
        if s >= 2 or not info:
            return exact
    for root, dirs, files in os.walk(folder):
        level = len(Path(root).relative_to(folder).parts)
        dirs[:] = [] if level >= depth else sorted(d for d in dirs if not d.startswith((".", "node_modules")))
        for f in sorted(files):
            if not f.lower().endswith(".pdf"):
                continue
            seen += 1
            if seen > limit:
                return best
            p = Path(root) / f
            s = score(p, info, name)
            if s > best_score:
                best, best_score = p, s
                if s == 3:
                    return p
    return best if best_score >= 1 else None


def usual_places() -> list[Path]:
    """Where people usually keep a downloaded book, on this computer or phone."""
    if os.environ.get("INPACE_MOBILE") == "android" or hasattr(sys, "getandroidapilevel"):
        root = Path(os.environ.get("INPACE_STORAGE") or os.environ.get("EXTERNAL_STORAGE") or "/storage/emulated/0")
        places = [root / "Download", root / "Documents", root / "Books"]
    else:
        home = Path.home()
        places = [home / "Downloads", home / "Documents", home / "Desktop", home / "Books", home]
    return [p for p in places if p.is_dir()]


def search(info: dict, name: str = "") -> Path | None:
    for place in usual_places():
        found = find_in(place, info, name, depth=0 if place == Path.home() else 2)
        if found:
            return found
    return None


def check(path: Path, info: dict) -> str:
    """'' if the file looks right; otherwise a short warning (in English, translated by the app)."""
    pages, _ = pdf_facts(path)
    if not pages:
        return "That file couldn't be read as a PDF."
    if info.get("pages") and pages != info["pages"]:
        return ("This PDF has {got} pages, and the course expects {want}. It may be another edition, so lessons could "
                "open the wrong pages. You can keep it, or get the right one from the link above.")
    return ""
