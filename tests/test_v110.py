"""v1.10: delete courses, update courses (new file or refreshed folder), search and jump, colors, PDF reader."""
import html
import shutil

from inpace.editor import course_to_yaml
from tests.test_app import client
from tests.test_media import make_folder


def started(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    jid = v.journeys()[0]["id"]
    c.post(f"/learn/{jid}/lesson/m1-l1/done", data={})
    return v, c, jid


def test_delete_a_started_course_needs_a_tick(tmp_path):
    v, c, jid = started(tmp_path)
    page = html.unescape(c.get("/courses/python-basics/remove").text)
    assert "I understand my progress" in page
    r = c.post("/courses/python-basics/remove", data={})
    assert "Tick the box" in html.unescape(r.text) and v.get_course("python-basics")
    r = c.post("/courses/python-basics/remove", data={"sure": "1"})
    assert "Deleted" in html.unescape(r.text)
    assert not v.get_course("python-basics") and not v.journeys()
    # Adding it again starts fresh.
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    assert v.journeys()[0]["id"] != jid
    assert v.progress(v.journeys()[0]["id"])["percent"] == 0


def test_update_from_a_newer_file_keeps_progress(tmp_path):
    v, c, jid = started(tmp_path)
    text = course_to_yaml(v.get_course("python-basics")).replace("version: '1'", "version: '2'")
    text = text.replace("title: Printing and simple math", "title: Printing and maths")
    r = c.post("/open", files={"file": ("python.yaml", text.encode())})
    page = html.unescape(r.text)
    assert "A newer copy" in page and "Printing and maths" in page and "Printing and simple math" in page
    r = c.post("/courses/python-basics/update", data={"choice": "update"})
    assert "Your progress is kept" in html.unescape(r.text)
    assert v.journey_for_course("python-basics") == jid
    assert v.get_course("python-basics").modules[0]["lessons"][1]["title"] == "Printing and maths"
    assert v.progress(jid)["modules"][0]["lessons"][0]["done"]
    # Same file again, as a separate course.
    text2 = text.replace("Printing and maths", "Printing, again")
    c.post("/open", files={"file": ("python.yaml", text2.encode())})
    c.post("/courses/python-basics/update", data={"choice": "separate"})
    assert len(v.courses()) == 2


def test_refresh_folder_adds_new_videos(tmp_path):
    v, c = client(tmp_path, "Omar")
    folder = make_folder(tmp_path / "Course")
    c.post("/courses/from-folder", data={"folder": str(folder)})
    cid = v.courses()[0].id
    c.post(f"/edit/{cid}", data={"action": "add_task", "module": "m1", "type": "explain", "prompt": "Why?"})
    (folder / "01 Intro" / "03 - New bonus.mp4").write_bytes(b"\x00\x00\x00\x18ftyp")
    (folder / "03 Extra").mkdir()
    (folder / "03 Extra" / "01 Wrap up.mp4").write_bytes(b"\x00\x00\x00\x18ftyp")
    r = c.post(f"/courses/{cid}/refresh", headers={"referer": "http://testserver/courses"})
    assert "Added 2 new lesson(s)" in html.unescape(r.text)
    co = v.get_course(cid)
    assert [les["title"] for les in co.modules[0]["lessons"]][-1] == "New bonus"
    assert co.modules[0]["requires"][0]["prompt"] == "Why?"  # your edits stay
    assert co.modules[-1]["title"] == "Extra"
    r = c.post(f"/courses/{cid}/refresh", headers={"referer": "http://testserver/courses"})
    assert "up to date" in html.unescape(r.text)


def test_search_continue_outline_and_colors(tmp_path):
    v, c, jid = started(tmp_path)
    items = c.get("/nav.json").json()
    assert any(i["t"] == "What is Python?" and i["u"] == f"/learn/{jid}/lesson/m1-l1" for i in items)
    assert any(i["u"] == "/settings" for i in items)
    c.get(f"/learn/{jid}/lesson/m1-l2")
    home = html.unescape(c.get("/").text)
    assert 'class="continue"' in home and "Printing and simple math" in home
    lesson = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l1").text)
    assert "Course outline" in lesson and "Variables" in lesson
    c.post("/settings/colors", data={"accent": "ocean"})
    assert 'data-accent="ocean"' in c.get("/").text
    c.post("/settings/colors", data={"accent": "<bad>"})
    assert "data-accent" not in c.get("/").text.split(">")[1]


def test_pdf_reader(tmp_path):
    v, c = client(tmp_path, "Omar")
    folder = tmp_path / "Reading"
    (folder / "01 Week one").mkdir(parents=True)
    (folder / "01 Week one" / "Chapter 1.pdf").write_bytes(b"%PDF-1.4 test")
    c.post("/courses/from-folder", data={"folder": str(folder)})
    course = v.courses()[0]
    c.post(f"/courses/{course.id}/start")
    jid = v.journeys()[0]["id"]
    pdf_lesson = course.modules[0]["lessons"][0]["id"]
    page = c.get(f"/learn/{jid}/lesson/{pdf_lesson}").text
    assert 'src="/pdf?src=' in page
    src = page.split('src="/pdf?')[1].split('"')[0]
    viewer = c.get("/pdf?" + html.unescape(src))
    assert viewer.status_code == 200 and "pdf.min.mjs" in viewer.text
    assert c.get("/static/pdfjs/pdf.min.mjs").headers["content-type"].startswith("text/javascript")
    assert c.get("/pdf?src=https://evil.example/x.pdf").status_code == 404
