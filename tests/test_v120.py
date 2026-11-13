"""v1.20: a course that reads a book each learner gets themselves (it never travels with the course). inPace finds
the learner's copy by its title and page count, whatever the file is called."""
import html
import io
import zipfile
from pathlib import Path

import pytest
import yaml
from pypdf import PdfWriter
from starlette.testclient import TestClient

from inpace import books
from inpace.app import create_app
from inpace.vault import Vault

COURSE = {
    "id": "mml-test", "title": "Maths for ML, part 1", "version": "1", "language": "en", "description": "A test.",
    "book": "mml-book.pdf",
    "book_info": {"title": "Mathematics for Machine Learning", "url": "https://mml-book.com", "pages": 12},
    "modules": [{"id": "m1", "title": "Vectors", "lessons": [
        {"id": "m1-l1", "title": "Read: systems of equations", "content": "Read these pages.", "media": "mml-book.pdf#pages=3-5"}]}],
}


def make_pdf(path: Path, pages: int, title: str = "") -> Path:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(200, 200)
    if title:
        w.add_metadata({"/Title": title})
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        w.write(f)
    return path


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    (h / "Downloads").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.delenv("INPACE_MOBILE", raising=False)
    return h


def app(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    pack = io.BytesIO()
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("course.yaml", yaml.safe_dump(COURSE))
    r = c.post("/open", files={"file": ("mml.lpack", pack.getvalue())})
    assert r.status_code == 200
    course = v.get_course("mml-test")
    jid = c.post(f"/courses/{course.id}/start", follow_redirects=False).headers["location"].rsplit("/", 1)[-1]
    return v, c, course, jid


def test_book_info_is_read_and_kept(tmp_path):
    v, c, course, jid = app(tmp_path)
    assert course.extra["book"] == "mml-book.pdf" and course.extra["book_info"]["pages"] == 12
    assert books.clean_info({"title": "x", "url": "javascript:alert(1)", "pages": "lots"}) == {"title": "x"}
    shared = c.get(f"/courses/{course.id}/export")
    with zipfile.ZipFile(io.BytesIO(shared.content)) as z:
        head = yaml.safe_load(z.read("course.yaml"))
        assert head["book_info"]["title"] == "Mathematics for Machine Learning"
        assert not any(n.endswith(".pdf") for n in z.namelist())    # the book never travels


def test_course_and_lesson_ask_for_the_book(tmp_path, home):
    v, c, course, jid = app(tmp_path)
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert "This course reads a book you get yourself" in page and "https://mml-book.com" in page
    assert "Where are this course's files?" not in page
    lesson = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l1").text)
    assert "This lesson reads your own copy of the course book." in lesson and f"/courses/{course.id}/go#book" in lesson
    assert c.get(f"/courses/{course.id}/go", follow_redirects=False).headers["location"] == f"/learn/{jid}"


def test_find_it_for_me_in_downloads_even_renamed(tmp_path, home):
    v, c, course, jid = app(tmp_path)
    make_pdf(home / "Downloads" / "some other.pdf", 3, "A cookbook")
    mine = make_pdf(home / "Downloads" / "papers" / "maths (1).pdf", 12, "Mathematics for Machine Learning")
    r = c.post(f"/courses/{course.id}/book", data={"search": "1"})
    assert "Found your book" in html.unescape(r.text)
    assert v.book_file(course.id) == mine and v.find_media(course.id, "mml-book.pdf") == mine
    lesson = c.get(f"/learn/{jid}/lesson/m1-l1").text
    assert "/pdf?" in lesson and "from=3" in lesson
    assert c.get(f"/m/{course.id}/mml-book.pdf").content == mine.read_bytes()


def test_choose_a_folder_or_a_file_and_get_warned_about_another_edition(tmp_path, home):
    v, c, course, jid = app(tmp_path)
    folder = tmp_path / "Library"
    other = make_pdf(folder / "mml-old-draft.pdf", 30, "Mathematics for Machine Learning")   # same title, other edition
    r = c.post(f"/courses/{course.id}/book", data={"path": str(folder)})
    assert v.book_file(course.id) == other
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert "This PDF has 30 pages, and the course expects 12." in page
    good = make_pdf(tmp_path / "anything.pdf", 12)        # no title inside, but the right page count
    c.post(f"/courses/{course.id}/book", data={"path": str(good)})
    assert v.book_file(course.id) == good
    assert "expects 12" not in html.unescape(c.get(f"/learn/{jid}").text)
    r = c.post(f"/courses/{course.id}/book", data={"path": str(tmp_path / "nope.pdf")})
    assert "wasn" in html.unescape(r.text)
    (tmp_path / "notes.txt").write_text("hi")
    r = c.post(f"/courses/{course.id}/book", data={"path": str(tmp_path / "notes.txt")})
    assert "Choose a PDF file." in html.unescape(r.text)


def test_nothing_found(tmp_path, home):
    v, c, course, jid = app(tmp_path)
    r = c.post(f"/courses/{course.id}/book", data={"search": "1"})
    assert "didn't find the book" in html.unescape(r.text)
    assert v.book_file(course.id) is None
