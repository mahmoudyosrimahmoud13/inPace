"""Getting a course's files from where the learner downloaded them.

A course's slides or videos may live outside the course (official sources, too big to share). The learner downloads
them; then "Find them for me" looks in the usual places (Downloads, Documents, Desktop; on a phone, Download):
- a folder that has them, even a few folders down, becomes the course's folder;
- a .zip that has them is unzipped into inPace's folder first.
Only names are compared. Nothing is sent anywhere."""
from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from .books import usual_places

MAX_ZIP = 4 * 1024 ** 3        # bigger zips are skipped
MAX_UNZIPPED = 8 * 1024 ** 3   # never write more than this from one zip
SKIP_DIRS = {"__MACOSX", "node_modules", ".git", ".cache", "AppData", "Library"}


def _walk(place: Path, depth: int):
    start = len(place.parts)
    for here, dirs, files in os.walk(place):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
        if len(Path(here).parts) - start >= depth:
            dirs[:] = []
        yield Path(here), files


def find_folder(names: set[str], places: list[Path] | None = None) -> Path | None:
    """The folder (right under Downloads, Documents...) holding the most of these file names."""
    want = {n.lower() for n in names}
    best, best_n = None, 0
    for place in places if places is not None else usual_places():
        deep = 1 if place == Path.home() else 4
        counts: dict[Path, set] = {}
        for here, files in _walk(place, deep):
            hits = want & {f.lower() for f in files}
            if not hits:
                continue
            rel = here.relative_to(place).parts
            top = place / rel[0] if rel else place
            counts.setdefault(top, set()).update(hits)
        for top, hits in counts.items():
            if len(hits) > best_n:
                best, best_n = top, len(hits)
    return best


def find_zip(names: set[str], places: list[Path] | None = None) -> Path | None:
    """The newest .zip in the usual places that holds the most of these file names."""
    want = {n.lower() for n in names}
    zips = []
    for place in places if places is not None else usual_places():
        deep = 1 if place == Path.home() else 2
        for here, files in _walk(place, deep):
            for f in files:
                if f.lower().endswith(".zip"):
                    p = here / f
                    try:
                        if p.stat().st_size <= MAX_ZIP:
                            zips.append(p)
                    except OSError:
                        pass
    zips.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    best, best_n = None, 0
    for p in zips[:40]:
        try:
            with zipfile.ZipFile(p) as zf:
                inside = {PurePosixPath(n).name.lower() for n in zf.namelist() if not n.endswith("/")}
        except (zipfile.BadZipFile, OSError):
            continue
        n = len(want & inside)
        if n > best_n:
            best, best_n = p, n
    return best


def unzip(zip_path: Path, dest: Path) -> Path:
    """Unzip safely (no paths outside dest, no Mac leftovers) into dest/<zip name>. Returns that folder."""
    out = dest / zip_path.stem
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    base = out.resolve()
    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            parts = [x for x in name.split("/") if x and x not in (".", "..")]
            if not parts or info.is_dir() or parts[0] == "__MACOSX" or parts[-1].startswith("._") or parts[-1] == ".DS_Store":
                continue
            target = base.joinpath(*parts).resolve()
            try:
                target.relative_to(base)
            except ValueError:
                continue
            total += info.file_size
            if total > MAX_UNZIPPED:
                raise ValueError("This zip is too big to unzip here.")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
    return out
