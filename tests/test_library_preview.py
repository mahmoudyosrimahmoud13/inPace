"""The course library: topic buttons, and looking inside a course before adding it."""
import html
import json

from starlette.testclient import TestClient

from inpace.app import create_app
from inpace.vault import Vault


def entry(cid, **extra):
    return {"id": cid, "title": f"Course {cid}", "description": "About it", "language": "en", "version": 1,
            "hash": "x", "modules": 1, "lessons": 2, "minutes": 125, "tags": ["python", "web"],
            "license": "CC-BY-4.0", "author": {"name": "inPace", "id": None, "verified": True}, "downloads": [],
            "cover": None, "pack": "https://example.invalid/p.zip", "sha256": "0", "size": 1, **extra}


def app_with(tmp_path, courses):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    (v.home / "library.json").write_text(json.dumps({"inpace": "library", "v": 1, "courses": courses}), encoding="utf-8")
    return c


def test_library_grid_and_topics(tmp_path):
    c = app_with(tmp_path, [entry("a"), entry("b", tags=["python"]), entry("c", tags=["art"])])
    r = c.get("/library")
    assert r.status_code == 200
    page = html.unescape(r.text)
    assert 'data-lib-topic="python"' in page          # shared by two courses
    assert 'data-lib-topic="art"' not in page          # only one course has it
    assert "about 2 h of lessons" in page
    assert page.count("See what's inside") == 3


def test_preview_shows_outline_tasks_and_a_lesson(tmp_path):
    outline = [{"title": "Day 1: Basics", "lessons": [{"title": "Hello", "minutes": 20, "media": "pdf"},
                                                       {"title": "Lists", "minutes": 25, "media": ""}],
                "tasks": [{"type": "practical", "prompt": "Build it"}, {"type": "quiz", "questions": 4}]}]
    sample = {"title": "Hello", "text": "# Hello\n\nSome **bold** text <script>alert(1)</script>\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"}
    c = app_with(tmp_path, [entry("a", outline=outline, sample=sample, credit="Slides by someone")])
    r = c.get("/library/a")
    assert r.status_code == 200
    page = html.unescape(r.text)
    assert "What's inside" in page and "Day 1: Basics" in page and "Lists" in page
    assert "slides" in page and "Quiz: 4 questions" in page and "Practical task" in page
    assert "<strong>bold</strong>" in r.text and "<table" in r.text
    assert "<script>alert(1)</script>" not in r.text      # lesson text can't add HTML
    assert "Slides by someone" in page
    assert "Add this course" in page


def test_preview_of_an_older_list_and_a_missing_course(tmp_path):
    c = app_with(tmp_path, [entry("old")])
    r = c.get("/library/old")
    assert r.status_code == 200 and "Add it to see everything inside" in html.unescape(r.text)
    r = c.get("/library/nope", follow_redirects=False)
    assert r.status_code == 303 and "/library" in r.headers["location"]


def test_preview_in_arabic(tmp_path):
    c = app_with(tmp_path, [entry("a", outline=[{"title": "M", "lessons": [{"title": "L", "minutes": 5, "media": ""}], "tasks": []}])])
    Vault(tmp_path / "me")._set_meta("lang", "ar")
    page = html.unescape(c.get("/library/a").text)
    assert "محتوى الدورة" in page
