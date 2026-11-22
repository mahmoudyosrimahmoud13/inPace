"""v1.32.0: the PDF reader does what GNOME's PDF reader (Evince) does, and saves highlights and notes inside the PDF
the way Evince saves them, so the same file shows them in both."""
import io
import os
import re
import shutil
import stat
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from starlette.testclient import TestClient

from inpace import pdfnotes
from inpace.app import create_app
from inpace.vault import Vault

ROOT = Path(__file__).resolve().parent.parent
TPL = (ROOT / "inpace" / "templates" / "pdf_viewer.html").read_text(encoding="utf-8")


def _pdf(path: Path, pages: int = 3) -> Path:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=612, height=792)
    with open(path, "wb") as f:
        w.write(f)
    return path


HL = {"kind": "highlight", "quads": [72, 700, 300, 700, 72, 686, 300, 686], "color": "#ffd84d", "text": "remember", "author": "Mona"}


def test_marks_are_standard_annotations_appended_to_the_file(tmp_path):
    p = _pdf(tmp_path / "book.pdf")
    before = p.read_bytes()
    a = pdfnotes.add(p, 2, HL)
    b = pdfnotes.add(p, 2, {"kind": "note", "point": [400, 600], "text": "a note", "color": "#7ad151"})
    c = pdfnotes.add(p, 1, {"kind": "underline", "quads": [72, 650, 200, 650, 72, 636, 200, 636]})
    d = pdfnotes.add(p, 1, {"kind": "strike", "quads": [72, 600, 200, 600, 72, 586, 200, 586]})
    e = pdfnotes.add(p, 3, {"kind": "squiggly", "quads": [72, 560, 200, 560, 72, 546, 200, 546]})
    data = p.read_bytes()
    # an incremental update, like Evince saves: the original bytes stay as they were
    assert data.startswith(before) and data.rstrip().endswith(b"%%EOF")
    r = PdfReader(str(p))
    subtypes = {(n + 1, str(x.get_object()["/Subtype"])) for n, pg in enumerate(r.pages) for x in pg.get("/Annots") or []}
    assert subtypes == {(2, "/Highlight"), (2, "/Text"), (1, "/Underline"), (1, "/StrikeOut"), (3, "/Squiggly")}
    hl = next(x.get_object() for x in r.pages[1]["/Annots"] if x.get_object()["/Subtype"] == "/Highlight")
    assert [round(float(v)) for v in hl["/QuadPoints"]] == [72, 700, 300, 700, 72, 686, 300, 686]
    assert hl["/Contents"] == "remember" and hl["/T"] == "Mona" and hl["/NM"].startswith("inpace-")
    assert "/N" in hl["/AP"]  # its own drawing, so every reader shows it the same way
    assert [m["kind"] for m in pdfnotes.marks(p)] == ["underline", "strike", "highlight", "note", "squiggly"]
    # the object numbers the reader uses ("12R") stay the same after later saves
    ids = {m["id"] for m in pdfnotes.marks(p)}
    assert {a["id"], b["id"], c["id"], d["id"], e["id"]} == ids


def test_edit_and_remove_any_mark(tmp_path):
    p = _pdf(tmp_path / "book.pdf")
    a = pdfnotes.add(p, 1, HL)
    b = pdfnotes.add(p, 1, {"kind": "note", "point": [400, 600], "text": "x"})
    m = pdfnotes.edit(p, 1, a["id"], text="changed", color="#6cb8ff")
    assert m["text"] == "changed" and m["color"] == "#6cb8ff"
    got = {x["id"]: x for x in pdfnotes.marks(p)}
    assert got[a["id"]]["text"] == "changed" and got[a["id"]]["color"] == "#6cb8ff"
    pdfnotes.remove(p, 1, b["id"])
    assert [x["id"] for x in pdfnotes.marks(p)] == [a["id"]]
    with pytest.raises(pdfnotes.NoteError):
        pdfnotes.remove(p, 1, "999999R")
    with pytest.raises(pdfnotes.NoteError):
        pdfnotes.add(p, 9, HL)  # no page 9
    with pytest.raises(pdfnotes.NoteError):
        pdfnotes.add(p, 1, {"kind": "highlight", "quads": [1, 2, 3]})
    with pytest.raises(pdfnotes.NoteError):
        pdfnotes.add(p, 1, {"kind": "erase-everything", "quads": HL["quads"]})


def test_marks_made_by_another_reader_show_and_can_be_changed(tmp_path):
    """A highlight another program wrote (no /NM, written in one go): listed, and editable here."""
    from pypdf.annotations import Highlight
    from pypdf.generic import ArrayObject, FloatObject
    w = PdfWriter()
    w.add_blank_page(612, 792)
    w.add_annotation(0, Highlight(rect=(70, 680, 310, 702), quad_points=ArrayObject([FloatObject(v) for v in HL["quads"]])))
    p = tmp_path / "other.pdf"
    with open(p, "wb") as f:
        w.write(f)
    (m,) = pdfnotes.marks(p)
    assert m["kind"] == "highlight" and not m["nm"]
    pdfnotes.edit(p, 1, m["id"], text="noted in inPace")
    assert pdfnotes.marks(p)[0]["text"] == "noted in inPace"


def test_restore_writes_back_marks_a_replaced_file_lost(tmp_path):
    p = _pdf(tmp_path / "book.pdf")
    clean = p.read_bytes()
    a = pdfnotes.add(p, 2, HL)
    saved = [{k: v for k, v in a.items() if k != "id"}]
    p.write_bytes(clean)  # a course update put the original file back
    assert pdfnotes.marks(p) == []
    assert pdfnotes.restore(p, saved) == 1
    (m,) = pdfnotes.marks(p)
    assert m["nm"] == a["nm"] and m["text"] == "remember"
    assert pdfnotes.restore(p, saved) == 0  # already there


# ---- The app's routes ----

def _app(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "lang": "en"})
    v._set_meta("tour_done", "x")
    folder = tmp_path / "course"
    folder.mkdir()
    _pdf(folder / "book.pdf")
    r = c.post("/courses/from-folder", data={"folder": str(folder), "title": "Book"})
    assert r.status_code == 200
    cid = v.courses()[0].id
    return v, c, f"/m/{cid}/book.pdf", folder / "book.pdf"


def _post(c, url, body):
    return c.post(url, json=body)


def test_mark_routes_save_in_the_file(tmp_path):
    v, c, src, path = _app(tmp_path)
    page = c.get("/pdf", params={"src": src, "full": "1", "name": "book.pdf"})
    assert page.status_code == 200 and 'id="notebtn"' in page.text  # this file can be marked
    r = _post(c, "/pdf/mark", {"src": src, "page": 1, **HL})
    assert r.status_code == 200 and r.json()["ok"]
    mark = r.json()["mark"]
    assert mark["author"] == "Mona"  # the learner's name, like Evince uses yours
    assert [m["kind"] for m in pdfnotes.marks(path)] == ["highlight"]
    r = _post(c, "/pdf/mark/edit", {"src": src, "page": 1, "id": mark["id"], "text": "new", "color": "#ff8fc8"})
    assert r.json()["ok"] and pdfnotes.marks(path)[0]["text"] == "new"
    r = _post(c, "/pdf/mark", {"src": src, "page": 2, "kind": "note", "point": [300, 500], "text": "hi"})
    assert r.json()["ok"]
    r = _post(c, "/pdf/mark/delete", {"src": src, "page": 2, "id": r.json()["mark"]["id"]})
    assert r.json()["ok"] and [m["kind"] for m in pdfnotes.marks(path)] == ["highlight"]


def test_only_json_from_the_app_and_only_course_files(tmp_path):
    v, c, src, path = _app(tmp_path)
    # a plain form (what another website could send) is refused
    assert c.post("/pdf/mark", data={"src": src, "page": "1", "kind": "highlight"}).status_code == 415
    assert c.post("/pdf/open-outside", data={"src": src}).status_code == 415
    # not a course file, or a path that tries to leave the course
    assert _post(c, "/pdf/mark", {"src": "/evidence/abc", "page": 1, **HL}).status_code == 404
    assert _post(c, "/pdf/mark", {"src": src.replace("book.pdf", "../../etc/passwd"), "page": 1, **HL}).status_code == 404
    assert _post(c, "/pdf/mark", {"src": src, "page": 1, "kind": "highlight", "quads": "x"}).status_code == 400
    assert pdfnotes.marks(path) == []


def test_a_read_only_pdf_is_shown_but_not_changed(tmp_path):
    v, c, src, path = _app(tmp_path)
    if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("root and Windows ignore the read-only bit here")
    path.chmod(stat.S_IRUSR)
    try:
        page = c.get("/pdf", params={"src": src})
        assert page.status_code == 200 and 'id="notebtn"' not in page.text
        assert _post(c, "/pdf/mark", {"src": src, "page": 1, **HL}).status_code == 403
    finally:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_marks_come_back_after_a_course_update_replaces_the_pdf(tmp_path):
    v, c, src, path = _app(tmp_path)
    clean = path.read_bytes()
    _post(c, "/pdf/mark", {"src": src, "page": 1, **HL})
    path.write_bytes(clean)  # the update brought the original file
    c.get("/pdf", params={"src": src})  # opening the PDF puts them back
    assert [m["text"] for m in pdfnotes.marks(path)] == ["remember"]


def test_a_mark_deleted_in_another_reader_stays_deleted(tmp_path):
    """Evince removed one of two marks: the file still has the other, so it wasn't replaced. Nothing comes back."""
    v, c, src, path = _app(tmp_path)
    a = _post(c, "/pdf/mark", {"src": src, "page": 1, **HL}).json()["mark"]
    _post(c, "/pdf/mark", {"src": src, "page": 2, **HL})
    pdfnotes.remove(path, 1, a["id"])  # as if done in another reader
    c.get("/pdf", params={"src": src})
    assert [m["page"] for m in pdfnotes.marks(path)] == [2]


def test_the_reader_has_evince_features():
    for piece in ["pdfjs.TextLayer", "getOutline", "openFind", "F9", "F5", "F11", "Ctrl+L",
                  "Ctrl+D", "Ctrl+P", "Ctrl+S", "Ctrl+I", "Alt+←", "dual", "continuous", "oddLeft", "present(",
                  "getMetadata", "window.print()", "/pdf/mark", "/pdf/mark/edit", "/pdf/mark/delete", "/pdf/open-outside",
                  "convertToPdfPoint", "undoLast", "pdf-thumb", "goDest"]:
        assert piece in TPL, piece
    # marks are sent as JSON, so other websites can't send them
    assert '"content-type": "application/json"' in TPL
