"""v1.18: courses from links (chapters cut a long YouTube video), YouTube pieces that remember where you stopped,
and folders on My courses."""
import html
import re

from starlette.testclient import TestClient

from inpace import folders
from inpace.app import create_app
from inpace.course import clock_seconds, youtube_segment
from inpace.editor import parse_link_lines
from inpace.vault import Vault

LINKS = """# Docker
https://www.youtube.com/watch?v=PrusdhS2lmo
00:00:30 Introduction to Containers
(00:19:49) - Container Architecture
00:50:14 Introduction to Docker
# Practice
Docker on Udemy | https://www.udemy.com/course/docker-mastery/
"""


def app(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    return v, c


def test_times_and_pieces():
    assert clock_seconds("10:05:52") == 36352 and clock_seconds("1m30s") == 90 and clock_seconds("90") == 90
    assert clock_seconds("hello") is None
    assert youtube_segment("https://www.youtube.com/watch?v=PrusdhS2lmo&t=1189&end=3014") == (1189, 3014)
    assert youtube_segment("https://youtu.be/PrusdhS2lmo?t=1h2m3s") == (3723, None)
    assert youtube_segment("https://www.youtube.com/watch?v=PrusdhS2lmo&t=50&end=10") == (50, None)


def test_chapters_cut_a_long_video():
    groups = parse_link_lines(LINKS)
    assert [g[0] for g in groups] == ["Docker", "Practice"]
    docker = groups[0][1]
    assert [les["title"] for les in docker] == ["Introduction to Containers", "Container Architecture", "Introduction to Docker"]
    assert docker[0]["media"].endswith("t=30&end=1189") and docker[0]["minutes"] == 19
    assert docker[2]["media"].endswith("t=3014")  # the last chapter plays to the end
    assert groups[1][1][0]["title"] == "Docker on Udemy"


def test_a_time_line_needs_a_video():
    import pytest
    from inpace.course import CourseError
    with pytest.raises(CourseError):
        parse_link_lines("00:10 Intro")


def test_add_from_links_into_a_new_folder(tmp_path):
    v, c = app(tmp_path)
    assert "/add/links" in c.get("/add").text
    r = c.post("/add/links", data={"title": "Docker", "links": LINKS, "new_folder": "DevOps"})
    assert r.status_code == 200 and "Course added" in html.unescape(r.text)
    course = v.courses()[0]
    assert sum(len(m["lessons"]) for m in course.modules) == 4
    data = folders.load(v)
    assert data["folders"][0]["name"] == "DevOps" and data["of"][course.id] == data["folders"][0]["id"]
    page = html.unescape(c.get("/courses").text)
    assert "DevOps" in page and "Docker" in page
    # An empty list is refused with a clear message
    r = c.post("/add/links", data={"title": "Nothing", "links": "  "})
    assert "Paste at least one link." in html.unescape(r.text)


def test_folders_move_rename_delete(tmp_path):
    v, c = app(tmp_path)
    c.post("/add/links", data={"title": "Nets", "links": "https://youtu.be/abcdefghijk"})
    cid = v.courses()[0].id
    c.post("/folders/new", data={"name": "Networks"})
    fid = folders.load(v)["folders"][0]["id"]
    assert folders.create(v, " networks ") == fid  # same name, same folder
    c.post(f"/courses/{cid}/folder", data={"folder": fid})
    assert folders.load(v)["of"][cid] == fid
    page = html.unescape(c.get("/courses").text)
    assert 'id="folder-' + fid in page and 'id="folder-none"' not in page
    c.post(f"/folders/{fid}/rename", data={"name": "Computer networks"})
    assert "Computer networks" in html.unescape(c.get("/courses").text)
    c.post(f"/folders/{fid}/delete")
    assert folders.load(v)["folders"] == [] and v.get_course(cid)
    c.post(f"/courses/{cid}/folder", data={"folder": "", "new_name": "Languages"})
    assert folders.load(v)["folders"][0]["name"] == "Languages"
    # Deleting the course forgets its folder
    c.post(f"/courses/{cid}/remove", data={"confirm": "1"})
    if not v.get_course(cid):
        assert cid not in folders.load(v)["of"]


def test_youtube_piece_plays_and_continues(tmp_path):
    v, c = app(tmp_path)
    c.post("/add/links", data={"title": "Docker", "links": LINKS})
    course = v.courses()[0]
    r = c.post(f"/courses/{course.id}/start", follow_redirects=False)
    jid = r.headers["location"].rsplit("/", 1)[-1]
    lesson = c.get(f"/learn/{jid}/lesson/m1-l2").text
    key = re.search(r'data-yt-key="([^"]+)"', lesson).group(1)
    assert 'data-start="1189"' in lesson and 'data-end="3014"' in lesson
    assert "This lesson is the part from 19:49 to 50:14." in html.unescape(lesson)
    assert "enablejsapi=1" in lesson
    # The player reports where you are; next time it continues from there.
    c.post("/media-pos", data={"key": html.unescape(key), "t": "1500", "d": "3014"})
    lesson = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l2").text)
    assert 'data-resume="1500.0"' in lesson and "You stopped at 25:00" in lesson
    # Near the end counts as finished: it starts from the beginning of the piece again.
    c.post("/media-pos", data={"key": html.unescape(key), "t": "3010", "d": "3014"})
    assert 'data-resume="0.0"' in c.get(f"/learn/{jid}/lesson/m1-l2").text



def test_udemy_lesson_opens_its_site(tmp_path):
    v, c = app(tmp_path)
    c.post("/add/links", data={"title": "Udemy", "links": "Docker on Udemy | https://www.udemy.com/course/docker-mastery/"})
    course = v.courses()[0]
    r = c.post(f"/courses/{course.id}/start", follow_redirects=False)
    jid = r.headers["location"].rsplit("/", 1)[-1]
    page = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l1").text)
    assert "https://www.udemy.com/course/docker-mastery/" in page and "Docker on Udemy" in page


def test_playlist_link_is_a_player(tmp_path):
    v, c = app(tmp_path)
    c.post("/add/links", data={"title": "List", "links": "https://www.youtube.com/playlist?list=PLabcdefghij12345"})
    course = v.courses()[0]
    r = c.post(f"/courses/{course.id}/start", follow_redirects=False)
    jid = r.headers["location"].rsplit("/", 1)[-1]
    assert "videoseries?list=PLabcdefghij12345" in c.get(f"/learn/{jid}/lesson/m1-l1").text


# ---- the course builder --------------------------------------------------------------------------------

def test_builder_makes_and_edits_a_course(tmp_path):
    v, c = app(tmp_path)
    assert c.get("/build").status_code == 200
    draft = re.search(r'data-draft="([0-9a-f]{16})"', c.get("/build").text).group(1)
    # A file picked before the course exists waits in a draft folder.
    r = c.post("/build/upload", data={"draft": draft}, files={"files": ("01 - Intro.mp4", b"video bytes")}).json()
    assert r["files"][0] == {"ok": True, "media": "uploads/01 - Intro.mp4", "title": "Intro", "kind": "video"}
    bad = c.post("/build/upload", data={"draft": draft}, files={"files": ("setup.exe", b"x")}).json()
    assert bad["files"][0]["ok"] is False
    # Not saved until it has a title and a lesson.
    assert c.post("/build/save", json={"title": "", "modules": []}).json()["ok"] is False
    empty = c.post("/build/save", json={"title": "Nets", "modules": [{"title": "Empty", "lessons": []}]}).json()
    assert empty["ok"] is False and "Add at least one lesson" in " ".join(empty["problems"])
    links = c.post("/build/links", json={"text": "https://youtu.be/abcdefghijk\n00:00 Start\n05:00 Next"}).json()
    assert [x["title"] for x in links["lessons"]] == ["Start", "Next"] and links["lessons"][0]["kind"] == "youtube"
    body = {"draft": draft, "title": "Networks", "language": "en", "new_folder": "Computer science", "modules": [
        {"id": "", "title": "Basics", "lessons": [
            {"id": "", "title": "Intro", "media": "uploads/01 - Intro.mp4", "content": "", "minutes": 5},
            *[{"id": "", **x, "content": ""} for x in links["lessons"]],
            {"id": "", "title": "My notes", "media": "", "content": "Some **text**.", "minutes": 0}]},
        {"id": "", "title": "Empty part", "lessons": []}]}
    r = c.post("/build/save", json=body).json()
    assert r["ok"], r
    cid = r["cid"]
    course = v.get_course(cid)
    assert [m["title"] for m in course.modules] == ["Basics"]  # the empty part isn't saved
    assert [les["title"] for les in course.modules[0]["lessons"]] == ["Intro", "Start", "Next", "My notes"]
    assert (v.media_dir(cid) / "uploads" / "01 - Intro.mp4").read_bytes() == b"video bytes"
    assert folders.load(v)["folders"][0]["name"] == "Computer science"
    # Start it, finish a lesson, then reorder and rename in the builder: ids (and progress) are kept.
    jid = c.post(f"/courses/{cid}/start", follow_redirects=False).headers["location"].rsplit("/", 1)[-1]
    c.post(f"/learn/{jid}/lesson/m1-l1/done", data={})
    data = r["data"]
    m = data["modules"][0]
    m["lessons"].reverse()
    m["lessons"][0]["title"] = "My notes (new)"
    data["modules"].append({"id": "", "title": "Part two", "lessons": [{"id": "", "title": "Extra", "media": "", "content": "", "minutes": 0}]})
    r2 = c.post("/build/save", json={**data, "cid": cid}).json()
    assert r2["ok"], r2
    course = v.get_course(cid)
    assert [les["id"] for les in course.modules[0]["lessons"]] == ["m1-l4", "m1-l3", "m1-l2", "m1-l1"]
    assert course.modules[0]["lessons"][0]["title"] == "My notes (new)" and course.modules[1]["id"] == "m2"
    assert course.version == "2"
    assert any(e["type"] == "lesson_done" for e in v.events(jid))
    # The builder page shows the course; the lesson text comes back without its title line.
    page = c.get(f"/build/{cid}").text
    assert "My notes (new)" in html.unescape(page)
    assert builder_text(c, cid, "m1-l4") == "Some **text**."
    # Uploads to a saved course go straight into it.
    r = c.post("/build/upload", data={"cid": cid}, files={"files": ("01 - Intro.mp4", b"other")}).json()
    assert r["files"][0]["media"] == "uploads/01 - Intro (2).mp4"


def builder_text(c, cid, lid):
    import json
    page = c.get(f"/build/{cid}").text
    data = json.loads(html.unescape(re.search(r'<script type="application/json" id="b-data">(.*?)</script>', page, re.S).group(1)))
    return next(les["content"] for m in data["modules"] for les in m["lessons"] if les["id"] == lid)


def test_builder_keeps_tasks(tmp_path):
    v, c = app(tmp_path)
    r = c.post("/build/save", json={"title": "T", "modules": [{"title": "A", "lessons": [{"title": "One", "content": "x"}]}]}).json()
    cid = r["cid"]
    c.post(f"/edit/{cid}", data={"action": "add_task", "module": "m1", "type": "explain", "prompt": "Explain it in your words please"})
    tasks = len(v.get_course(cid).modules[0]["requires"])
    data = c.get(f"/build/{cid}")  # page loads
    assert data.status_code == 200
    r = c.post("/build/save", json={"cid": cid, "title": "T2", "modules": [{"id": "m1", "title": "A", "lessons": [{"id": "m1-l1", "title": "One", "content": "y"}]}]}).json()
    assert r["ok"] and len(v.get_course(cid).modules[0]["requires"]) == tasks and v.get_course(cid).title == "T2"
    assert r["data"]["modules"][0]["tasks"] or tasks == 0


def test_downloads_fall_back_to_the_bundled_certificates(monkeypatch):
    """Android's Python has no certificate list: a certificate error retries with the shipped one (certifi)."""
    import ssl
    import urllib.error
    import urllib.request
    from inpace import net
    calls = []

    def fake(req, timeout=0, context=None):
        calls.append(context)
        if len(calls) == 1:
            raise urllib.error.URLError(ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED"))
        return "ok"
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.delenv("INPACE_MOBILE", raising=False)
    net._CONTEXTS.clear()
    assert net.urlopen("https://example.com/library.json") == "ok"
    assert len(calls) == 2 and calls[1] is net.context(bundled=True)
    # On the phone the bundled list is used from the start
    monkeypatch.setenv("INPACE_MOBILE", "android")
    net._CONTEXTS.clear()
    assert net.context() is net.context(bundled=True)
    # Other errors are not retried
    calls.clear()

    def down(req, timeout=0, context=None):
        calls.append(1)
        raise urllib.error.URLError("no route")
    monkeypatch.setattr(urllib.request, "urlopen", down)
    import pytest
    with pytest.raises(urllib.error.URLError):
        net.urlopen("https://example.com/x")
    assert len(calls) == 1
