"""v1.25: optional lessons (the module doesn't wait for them), in the course format, progress, pages, editors and the
AI prompt."""
import html
import io
import re
import zipfile
from pathlib import Path

import pytest
import yaml

from inpace import ai, builder, editor
from inpace import app as app_mod
from inpace.course import CourseError, course_to_files, load_course
from inpace.exam import build_exam
from inpace.vault import lesson_ahead
from tests.test_app import client

SAMPLE = Path(app_mod.__file__).parent / "sample_courses" / "python-basics"
CID = "python-basics-extra"


def _files(optional=True) -> dict[str, str]:
    """The Python Basics sample with an extra lesson between the two lessons of module 1."""
    files = {p.relative_to(SAMPLE).as_posix(): p.read_text(encoding="utf-8") for p in SAMPLE.rglob("*")
             if p.is_file() and p.suffix in (".yaml", ".md")}
    head = yaml.safe_load(files["course.yaml"])
    head["id"] = CID
    extra = {"id": "m1-extra", "title": "Going further", "minutes": 10, "content": "# Going further\n\nMore to read.\n"}
    if optional:
        extra["optional"] = True
    head["modules"][0]["lessons"].insert(1, extra)
    files["course.yaml"] = yaml.safe_dump(head, allow_unicode=True, sort_keys=False)
    return files


def _pack() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in _files().items():
            z.writestr(name, text)
    return buf.getvalue()


def _start(tmp_path):
    v, c = client(tmp_path, "Nour")
    assert c.post("/open", files={"file": ("course.lpack", _pack())}).status_code == 200
    c.post(f"/courses/{CID}/start")
    return v, c, v.journeys()[0]["id"]


def _pass_quiz(v, c, jid):
    r = c.get(f"/learn/{jid}/task/m1-quiz/quiz")
    seed = re.search(r'name="seed" value="([0-9a-f]+)"', r.text).group(1)
    course = v.get_course(CID)
    qids = next(r for r in course.modules[0]["requires"] if r["type"] == "quiz")["questions"]
    exam = build_exam(course, qids, seed)
    ans = {q["id"]: next(ch["id"] for ch in q["choices"] if ch["id"] in course.answers[q["id"]]["right"]) for q in exam}
    c.post(f"/learn/{jid}/task/m1-quiz/quiz", data={"seed": seed, **ans})


def test_the_course_format_reads_and_writes_optional_lessons():
    c = load_course(_files())
    lessons = c.modules[0]["lessons"]
    assert [les.get("optional", False) for les in lessons] == [False, True, False]
    again = load_course(course_to_files(c))
    assert again.modules[0]["lessons"][1]["optional"] is True and again.hash == c.hash
    # "yes" works too, and courses without the flag keep the same fingerprint as before.
    assert load_course({**_files(), "course.yaml": _files()["course.yaml"].replace("optional: true", "optional: yes")}
                       ).modules[0]["lessons"][1]["optional"] is True
    plain = load_course(_files(optional=False))
    assert "optional" not in plain.modules[0]["lessons"][1]
    assert "optional" not in yaml.safe_load(course_to_files(plain)["course.yaml"])["modules"][0]["lessons"][1]


def test_a_module_needs_at_least_one_required_lesson():
    files = _files()
    head = yaml.safe_load(files["course.yaml"])
    for les in head["modules"][1]["lessons"]:
        les["optional"] = True
    with pytest.raises(CourseError) as e:
        load_course({**files, "course.yaml": yaml.safe_dump(head, sort_keys=False)})
    assert any("every lesson is optional" in p for p in e.value.problems)


def test_lesson_ahead_passes_over_optional_lessons_already_opened():
    ls = [{"id": "a", "done": True}, {"id": "b", "done": False, "optional": True, "opened": False},
          {"id": "c", "done": False}]
    assert lesson_ahead(ls)["id"] == "b"
    ls[1]["opened"] = True
    assert lesson_ahead(ls)["id"] == "c"
    ls[2]["done"] = True
    assert lesson_ahead(ls) is None


def test_the_module_finishes_without_its_optional_lesson(tmp_path):
    v, c, jid = _start(tmp_path)
    p = v.progress(jid)
    assert p["lessons_total"] == 4 and p["modules"][0]["lessons_needed"] == 2   # the optional lesson isn't counted
    c.post(f"/learn/{jid}/lesson/m1-l1/done", data={"next": "m1-extra"}, follow_redirects=False)
    assert v.progress(jid)["next"]["id"] == "m1-extra" and v.progress(jid)["next"]["optional"] is True
    home = html.unescape(c.get("/").text)
    assert "Going further" in home and ">Optional<" in home

    page = html.unescape(c.get(f"/learn/{jid}/lesson/m1-extra").text)
    assert "This lesson is optional" in page and ">Optional<" in page
    # "Skip it" sits at the top, next to the note, before the lesson text.
    skip = re.search(r'href="/learn/[^"]+/lesson/m1-l2">Skip it ', page)
    assert skip and skip.start() < page.index("More to read.")
    # Opened and left: "Continue" moves on to the next required lesson.
    assert v.progress(jid)["next"]["id"] == "m1-l2"
    course_page = html.unescape(c.get(f"/learn/{jid}").text)
    assert "stone" in course_page and " opt" in course_page

    c.post(f"/learn/{jid}/lesson/m1-l2/done", data={})
    for rid in ("m1-practical", "m1-explain"):
        if rid == "m1-explain":
            c.post(f"/learn/{jid}/task/{rid}/writeup", data={"text": "print shows things on the screen " * 10})
        else:
            c.post(f"/learn/{jid}/task/{rid}/evidence", files={"file": ("work.txt", b"my work")})
    _pass_quiz(v, c, jid)
    state = v.progress(jid)
    assert state["modules"][0]["status"] == "done" and state["modules"][0]["lessons_done"] == 2
    module = html.unescape(c.get(f"/learn/{jid}/module/m1").text)
    assert "Optional lessons:" in module and "Going further" in module and "2 of 2 done." in module
    # Reading it later is still recorded, without pushing the totals past 100%.
    c.post(f"/learn/{jid}/lesson/m1-extra/done", data={})
    state = v.progress(jid)
    assert next(les for les in state["modules"][0]["lessons"] if les["id"] == "m1-extra")["done"]
    assert state["lessons_done"] == 2 and state["percent"] <= 100


def test_editors_keep_the_flag(tmp_path):
    v, c, jid = _start(tmp_path)
    c.post(f"/edit/{CID}", data={"action": "edit_lesson", "lesson": "m1-l2", "module": "m1", "title": "Variables",
                                 "content": "# Variables\n\nText.", "minutes": "5", "has_optional": "1", "optional": "1"})
    assert v.get_course(CID).modules[0]["lessons"][2]["optional"] is True
    form = html.unescape(c.get(f"/edit/{CID}/lesson/m1-l2").text)
    assert 'name="optional" value="1" checked' in form
    c.post(f"/edit/{CID}", data={"action": "edit_lesson", "lesson": "m1-l2", "module": "m1", "title": "Variables",
                                 "content": "# Variables\n\nText.", "minutes": "5", "has_optional": "1"})
    assert "optional" not in v.get_course(CID).modules[0]["lessons"][2]
    c.post(f"/edit/{CID}", data={"action": "add_lesson", "module": "m2", "title": "Bonus", "content": "# Bonus\n\nX",
                                 "optional": "1"})
    assert v.get_course(CID).modules[1]["lessons"][-1]["optional"] is True
    assert "optional: true" in editor.course_to_yaml(v.get_course(CID))
    # The drag-and-drop builder sends the flag back and keeps it.
    data = builder.to_page(v.get_course(CID))
    assert [les["optional"] for les in data["modules"][0]["lessons"]] == [False, True, False]
    builder.save(v, {**data, "modules": [{**m, "lessons": [dict(les) for les in m["lessons"]]} for m in data["modules"]]})
    assert v.get_course(CID).modules[0]["lessons"][1]["optional"] is True


def test_the_ai_prompt_explains_optional_lessons():
    prompt = ai.build_prompt("Python", "beginner", 4, 3, "en")
    assert "optional: true" in prompt and "never put core teaching there" in prompt


def test_notes_on_a_lesson_stay_private(tmp_path):
    v, c, jid = _start(tmp_path)
    url = f"/learn/{jid}/lesson/m1-l1/notes"
    # "Take a note" on selected text: saved without leaving the page, sent back as one note.
    r = c.post(url, data={"quote": "  print  shows\n things ", "text": "Remember this"}, headers={"X-Inpace-Fetch": "1"})
    assert r.status_code == 200 and 'data-quote="print shows things"' in r.text and "Remember this" in r.text
    assert c.post(url, data={"quote": "", "text": "  "}, headers={"X-Inpace-Fetch": "1"}).status_code == 400
    c.post(url, data={"text": "A note without a quote"})
    notes = v.notes(CID, "m1-l1")
    assert [n["quote"] for n in notes] == ["print shows things", ""]
    page = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l1").text)
    assert 'data-notes="/learn/' in page and "Remember this" in page and "A note without a quote" in page
    assert "All your notes on this course" in page
    # Edit and delete.
    nid = notes[1]["id"]
    c.post(f"/notes/{nid}", data={"text": "Changed", "back": f"/learn/{jid}/lesson/m1-l1"})
    assert v.note(nid)["text"] == "Changed"
    c.post(f"/notes/{nid}", data={"delete": "1", "back": f"/learn/{jid}/lesson/m1-l1"})
    assert v.note(nid) is None
    # The course page links to them, the notes page lists them in order, and they download as Markdown.
    assert f"/learn/{jid}/notes" in c.get(f"/learn/{jid}").text
    c.post(f"/learn/{jid}/lesson/m2-l1/notes", data={"text": "Later lesson"})
    all_notes = html.unescape(c.get(f"/learn/{jid}/notes").text)
    assert all_notes.index("Remember this") < all_notes.index("Later lesson")
    md = c.get(f"/learn/{jid}/notes.md")
    assert md.status_code == 200 and "attachment" in md.headers["content-disposition"]
    assert "> print shows things" in md.text and "Later lesson" in md.text
    # Private: not in events, so never in a milestone.
    assert all("note" not in e["type"] for e in v.events(jid))
    # An outside "back" link isn't followed.
    r = c.post(f"/notes/{notes[0]['id']}", data={"text": "x", "back": "https://example.com/"}, follow_redirects=False)
    assert r.headers["location"].startswith("/")
