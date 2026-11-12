"""v1.15: books (PDF) as courses with page ranges, Word/PowerPoint/Excel previews, the tour sample, AI with your files."""
import html
import io
import re
import shutil
import zipfile
from pathlib import Path

import pytest

from inpace import ai, office, organize
from inpace.course import load_course, page_range
from tests.test_app import client

TOUR = Path(__file__).resolve().parent.parent / "inpace" / "sample_courses" / "tour" / "files"
BOOK = TOUR / "small-steps.pdf"


def test_page_ranges():
    assert page_range("book.pdf#pages=19-35") == ("book.pdf", (19, 35))
    assert page_range("a b.pdf#pages=7") == ("a b.pdf", (7, 7))
    assert page_range("book.pdf#pages=9-3") == ("book.pdf", (3, 9))
    assert page_range("book.pdf") == ("book.pdf", None)


def test_book_bookmarks_become_modules_and_lessons():
    plan = organize.book_plan(BOOK, "Small Steps")
    assert [s["title"] for s in plan["sections"]] == ["Chapter 1: Learning a little every day",
                                                      "Chapter 2: Practice that sticks", "Chapter 3: Someone in your corner"]
    first = plan["sections"][0]["files"]
    assert first == ["small-steps.pdf#pages=2-2", "small-steps.pdf#pages=3-3", "small-steps.pdf#pages=4-4"]
    assert plan["names"][first[0]] == "Introduction" and plan["names"][first[1]] == "1.1 Why small steps work"
    assert plan["left_out"] == ["small-steps.pdf#pages=1-1"] and plan["how"] == "book"


def test_book_without_bookmarks_is_split(tmp_path):
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(30):
        w.add_blank_page(width=200, height=300)
    pdf = tmp_path / "scan.pdf"
    with open(pdf, "wb") as f:
        w.write(f)
    plan = organize.book_plan(pdf)
    assert plan["how"] == "pages" and plan["sections"][0]["files"][:2] == ["scan.pdf#pages=1-12", "scan.pdf#pages=13-24"]
    (tmp_path / "bad.pdf").write_bytes(b"not a pdf")
    with pytest.raises(Exception, match="couldn't be read"):
        organize.book_plan(tmp_path / "bad.pdf")


def test_add_a_book_and_read_part_of_it(tmp_path):
    v, c = client(tmp_path, "Omar")
    r = c.post("/add/book", data={"title": "Small Steps"}, files={"book": ("small-steps.pdf", BOOK.read_bytes())},
               follow_redirects=False)
    loc = r.headers["location"]
    page = html.unescape(c.get(loc).text)
    assert "read the book's chapters and sections from its bookmarks" in page and "1.2 Pick a time, not a mood" in page
    assert "Pages 3–3" in page and "Ask AI to sort it" not in page
    draft = re.search(r"draft=([0-9a-f]{16})", loc).group(1)
    plan = organize.book_plan(v.home / "drafts" / draft / "small-steps.pdf", "Small Steps")
    plan["names"] = {"small-steps.pdf#pages=3-3": "Small steps"}
    r = c.post("/add/organize", data={"draft": draft, "book": "small-steps.pdf", "plan": __import__("json").dumps(plan)},
               follow_redirects=True)
    assert "saved in inPace" in html.unescape(r.text)
    course = next(x for x in v.courses() if x.title == "Small Steps")
    assert course.extra["book"] == "small-steps.pdf" and course.modules[0]["lessons"][1]["title"] == "Small steps"
    assert course.modules[0]["lessons"][1]["media"] == "small-steps.pdf#pages=3-3"
    assert v.find_media(course.id, "small-steps.pdf#pages=3-3") == (v.media_dir(course.id) / "small-steps.pdf").resolve()
    c.post(f"/courses/{course.id}/start")
    jid = v.journey_for_course(course.id)
    lesson = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l2").text)
    assert "from=3&to=3" in lesson and "Page 3" in lesson
    reader = c.get(f"/pdf?src=/m/{course.id}/small-steps.pdf&key=x&from=3&to=4").text
    assert "let FIRST = 3, LAST = 4;" in reader
    # Sharing the course never sends the book itself.
    pack = zipfile.ZipFile(io.BytesIO(c.get(f"/courses/{course.id}/export?files=1").content))
    assert not any(n.endswith("small-steps.pdf") for n in pack.namelist())


def test_a_book_left_where_it_is(tmp_path):
    v, c = client(tmp_path, "Omar")
    shelf = tmp_path / "Books"
    shelf.mkdir()
    shutil.copy2(BOOK, shelf / "small-steps.pdf")
    r = c.post("/add/book", data={"path": str(shelf / "small-steps.pdf")}, follow_redirects=True)
    assert "Chapter 2: Practice that sticks" in html.unescape(r.text) and "Leave them where they are" in html.unescape(r.text)
    assert "wasn't found" in html.unescape(c.post("/add/book", data={"path": str(shelf / "nope.pdf")}, follow_redirects=True).text)


def test_word_powerpoint_and_excel_previews(tmp_path):
    doc = office.preview(TOUR / "study-notes.docx")
    assert "<h1>My study notes</h1>" in doc and "<li>Finish the Python Basics course</li>" in doc
    assert "<td>Wednesday</td>" in doc and "data:image/png;base64," in doc and "<b>Tip: </b>" in doc
    slides = office.preview(TOUR / "meet-inpace.pptx")
    assert slides.count('class="office-slide"') == 3 and "<h3>What you can add to a course</h3>" in slides
    assert 'class="lvl1">Only to view: edit them in Office' in slides and "data:image/png" in slides
    sheet = office.preview(TOUR / "study-plan.xlsx")
    assert "<summary>Study plan</summary>" in sheet and "<summary>Reading log</summary>" in sheet
    assert ">Read a book<" in sheet and "class=num>160<" in sheet
    (tmp_path / "broken.docx").write_bytes(b"nope")
    with pytest.raises(office.OfficeProblem, match="couldn't be opened"):
        office.preview(tmp_path / "broken.docx")
    evil = tmp_path / "evil.docx"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("word/document.xml", '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>')
    with pytest.raises(office.OfficeProblem, match="safely"):
        office.preview(evil)


def test_the_tour_sample_shows_every_kind_of_lesson(tmp_path):
    v, c = client(tmp_path, "Omar")
    assert "A tour of inPace" in html.unescape(c.get("/courses").text)
    c.post("/courses/sample/tour")
    c.post("/courses/tour/start")
    jid = v.journey_for_course("tour")
    seen = {}
    for m in v.get_course("tour").modules:
        for les in m["lessons"]:
            seen[les["id"]] = c.get(f"/learn/{jid}/lesson/{les['id']}").text
            c.post(f"/learn/{jid}/lesson/{les['id']}/done", data={})  # the next module opens when this one is done
    assert all("can not find this file" not in t for t in seen.values())
    assert "<video" in seen["m2-l1"] and "<audio" in seen["m2-l2"] and "youtube" in seen["m2-l3"]
    assert "from=3&to=3" in seen["m3-l1"] and "from=5&to=7" in seen["m3-l3"]
    assert 'class="office office-docx"' in seen["m4-l1"] and 'class="office office-pptx"' in seen["m4-l2"]
    assert 'class="office office-xlsx"' in seen["m4-l3"] and "<iframe sandbox" in seen["m5-l1"]
    assert "study_timer.py" in seen["m1-l2"] and "how-it-works.png" in seen["m1-l1"]


def test_ai_course_with_your_own_book_and_files(tmp_path):
    v, c = client(tmp_path, "Omar")
    r = c.post("/ai", data={"action": "prompt", "source": "book", "book_title": "Small Steps", "level": "beginner",
                            "weeks": "3", "hours": "2", "language": "English"},
               files=[("src_files", ("small-steps.pdf", BOOK.read_bytes())),
                      ("src_files", ("study-notes.docx", (TOUR / "study-notes.docx").read_bytes()))])
    page = html.unescape(r.text)
    assert "Attached to the course:" in page and "10 pages" in page
    assert "- 1.1 Why small steps work (pages 3-3)" in page and '"study-notes.docx" (a Word, PowerPoint or Excel file)' in page
    assert 'media: "<file>#pages=A-B"' in page and "Start every lesson with a line like" not in page
    draft = re.search(r'name="src_draft" value="([0-9a-f]{16})"', r.text).group(1)
    reply = """```yaml
title: Small Steps, the course
description: Learning a little every day.
version: 1
language: en
modules:
  - title: Chapter 1
    lessons:
      - title: Why small steps work
        media: "small-steps.pdf#pages=3-3"
        minutes: 10
        content: |
          Small steps add up.
      - title: My notes
        media: "study-notes.docx"
        minutes: 5
        content: |
          Your notes, next to the book.
```"""
    r = c.post("/ai", data={"action": "save", "reply": reply, "src_draft": draft}, follow_redirects=True)
    assert "It's ready to start" in html.unescape(r.text)
    course = next(x for x in v.courses() if x.title == "Small Steps, the course")
    assert course.extra["book"] == "small-steps.pdf" and not (v.home / "drafts" / draft).exists()
    assert (v.media_dir(course.id) / "study-notes.docx").exists()
    assert not v.missing_media(course)


def test_ai_prompt_without_sources_is_unchanged():
    p = ai.build_prompt("Excel", "beginner", 4, 3, "English")
    assert "attached" not in p and "#pages" not in p


def test_folder_organizer_includes_office_files(tmp_path):
    d = tmp_path / "class"
    d.mkdir()
    shutil.copy2(TOUR / "study-notes.docx", d / "Week 1 notes.docx")
    shutil.copy2(TOUR / "meet-inpace.pptx", d / "Week 1 slides.pptx")
    shutil.copy2(TOUR / "study-plan.xlsx", d / "Week 2 plan.xlsx")
    (d / "old.doc").write_bytes(b"x")
    plan = organize.guess_plan(d)
    assert [s["title"] for s in plan["sections"]] == ["Week 1", "Week 2"] and plan["cant_show"] == ["old.doc"]
    c = organize.course_from_plan(d, organize.clean_plan(d, plan, organize.all_files(d)))
    assert load_course  # the course builds with Office lessons
    assert [les["media"] for les in c.modules[0]["lessons"]] == ["Week 1 notes.docx", "Week 1 slides.pptx"]


def test_update_check_waits_for_a_release_still_being_published(tmp_path, monkeypatch):
    import time
    from inpace import updater
    v, c = client(tmp_path, "Omar")
    monkeypatch.setattr(updater, "install_kind", lambda: "windows")
    # The Android file arrived first: a newer release with no file for this computer and no checksums yet.
    monkeypatch.setattr(updater, "check", lambda: {"version": "99.0.0", "page": "", "assets": {
        "inPace-android-arm64-v8a.apk": "https://example.com/a.apk"}})
    status = updater.run(v, force=True)
    assert status["state"] == "waiting"
    next_check = int(v._meta("update_checked")) + updater.CHECK_EVERY
    assert time.time() + 3000 < next_check < time.time() + 3700  # in an hour, not tomorrow
    assert "being published right now" in html.unescape(c.get("/settings").text)
    # Phones never try to install from here.
    monkeypatch.setattr(updater, "install_kind", lambda: "android")
    assert updater.run(v, force=True)["state"] == "none"
