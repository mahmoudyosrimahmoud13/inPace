"""v1.12: the course library (publish, browse, add, share links) and download links for big course files."""
import hashlib
import html
import io
import json
import re
import zipfile

import pytest

from inpace import exchange, library
from inpace.course import downloads_from_lines, load_course, course_to_files
from tests.test_app import client


def _course(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/courses/sample/fastapi")
    return v, c


def test_publish_file_is_signed_and_checks_out(tmp_path):
    v, c = _course(tmp_path)
    page = html.unescape(c.get("/courses/fastapi/publish").text)
    assert "Download the course file" in page and "issues/new?template=submit-course.yml" in page
    r = c.get("/courses/fastapi/publish/file")
    assert r.headers["content-disposition"].startswith("attachment")
    course, author = library.read_submission(r.content)
    assert course.id == "fastapi" and author["name"] == "Omar" and author["author"] == v.identity.id
    assert course.answers  # practice quizzes work for others


def test_changed_or_unsigned_submissions_are_refused(tmp_path):
    v, c = _course(tmp_path)
    data = c.get("/courses/fastapi/publish/file").content
    zin = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for i in zin.infolist():
            raw = zin.read(i)
            if i.filename == "course.yaml":
                raw = raw.replace(b"FastAPI: from first API", b"FastAPI: from FIRST API")
            z.writestr(i.filename, raw)
    with pytest.raises(library.LibraryProblem, match="changed after it was signed"):
        library.read_submission(out.getvalue())
    plain = c.get("/courses/fastapi/export?answers=1").content
    with pytest.raises(library.LibraryProblem, match="isn't signed"):
        library.read_submission(plain)


def _fake_library(tmp_path, monkeypatch, v, c):
    data = c.get("/courses/fastapi/publish/file").content
    course, author = library.read_submission(data)
    entry = {"id": course.id, "title": course.title, "description": course.description, "language": "en",
             "version": course.version, "hash": course.hash, "modules": len(course.modules),
             "lessons": course.lesson_count, "tags": ["python"], "license": "CC-BY-4.0",
             "author": {"name": "Omar", "id": author["author"], "verified": True},
             "downloads": [{"title": "All videos", "url": "https://example.com/v.zip", "size": "1.2 GB"}],
             "cover": None, "pack": library.SITE + "packs/fastapi.zip",
             "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    index = {"inpace": "library", "courses": [entry]}

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def fake_get(url, timeout=20):
        return R(json.dumps(index).encode() if url == library.INDEX_URL else data)
    monkeypatch.setattr(library, "_get", fake_get)
    return entry


def test_browse_add_and_share_from_the_library(tmp_path, monkeypatch):
    v, c = _course(tmp_path)
    _fake_library(tmp_path, monkeypatch, v, c)
    # A friend browses the library and adds the course.
    fv, f = client(tmp_path, "Sara")
    page = html.unescape(f.get("/library").text)
    assert "FastAPI: from first API to production" in page and "by Omar ✓" in page
    assert "Videos download separately · 1.2 GB" in page
    r = f.post("/library/fastapi/add", follow_redirects=True)
    assert "Added the course" in html.unescape(r.text) and fv.get_course("fastapi")
    assert "Added" in html.unescape(f.get("/library").text)
    # Sharing a library course gives a small link that points to the library, not the whole course.
    share = html.unescape(f.get("/courses/fastapi/share").text)
    link = re.search(r'<textarea id="course-link"[^>]*>(.*?)</textarea>', share, re.S).group(1)
    data = exchange.from_code(link)
    assert data == {"inpace": "library-course", "id": "fastapi", "title": "FastAPI: from first API to production",
                    "author": "Omar"}
    assert len(link) < 400
    # A third person taps it: inPace opens the library on that course.
    tv, t = client(tmp_path, "Nour")
    r = t.post("/open", data={"code": link}, follow_redirects=True)
    assert r.url.path == "/library" and 'value="fastapi"' in r.text


def test_share_page_without_library(tmp_path):
    v, c = _course(tmp_path)
    page = html.unescape(c.get("/courses/fastapi/share").text)
    assert "Publish to the library" in page and "Or send the course file" in page


def test_library_offline(tmp_path, monkeypatch):
    v, c = client(tmp_path, "Omar")

    def boom(url, timeout=20):
        raise OSError("offline")
    monkeypatch.setattr(library, "_get", boom)
    assert "couldn't be reached" in html.unescape(c.get("/library").text)


def test_download_must_match_the_list(monkeypatch):
    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): pass
    monkeypatch.setattr(library, "_get", lambda url, timeout=20: R(b"evil"))
    with pytest.raises(library.LibraryProblem, match="doesn't match"):
        library.download({"pack": library.SITE + "packs/x.zip", "sha256": "0" * 64})
    with pytest.raises(library.LibraryProblem, match="doesn't point"):
        library.download({"pack": "https://evil.example/x.zip", "sha256": "0" * 64})


def test_download_links_in_courses(tmp_path):
    assert downloads_from_lines("All videos | https://drive.google.com/x | 2.3 GB\nnot a link\nhttps://mega.nz/y") == [
        {"title": "All videos", "url": "https://drive.google.com/x", "size": "2.3 GB"},
        {"title": "Course files", "url": "https://mega.nz/y"}]
    v, c = client(tmp_path, "Omar")
    d = tmp_path / "Docker course"
    (d / "01 Intro").mkdir(parents=True)
    (d / "01 Intro" / "01 Welcome.mp4").write_bytes(b"x")
    c.post("/courses/from-folder", data={"folder": str(d), "title": "Docker"})
    cid = v.courses()[0].id
    c.post(f"/edit/{cid}", data={"action": "info", "title": "Docker", "description": "", "language": "en",
                                  "downloads": "All videos | https://archive.org/download/x.zip | 1 GB"})
    course = v.get_course(cid)
    assert course.extra["downloads"][0]["url"] == "https://archive.org/download/x.zip"
    assert load_course(course_to_files(course, True)).extra["downloads"] == course.extra["downloads"]
    # The publish page reminds you when videos only live on your computer.
    c.post(f"/edit/{cid}", data={"action": "info", "title": "Docker", "description": "", "language": "en", "downloads": ""})
    assert "Where will learners get the videos?" in html.unescape(c.get(f"/courses/{cid}/publish").text)
