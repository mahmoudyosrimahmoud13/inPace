"""v1.24: roadmaps (a path through several courses), in the app and the library, and voyage mode on the island."""
import html
import json
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from inpace import garden, library, roadmaps
from inpace.app import SAMPLES, create_app
from inpace.course import course_to_pack, files_from_folder, load_course
from inpace.vault import Vault


def lib_index(extra_roadmaps=None) -> dict:
    """A library list like the real one: two sample courses, and two roadmaps."""
    courses = []
    for cid in ("python-basics", "fastapi"):
        c = load_course(files_from_folder(SAMPLES / cid))
        courses.append({"id": c.id, "title": c.title, "description": c.description, "language": c.language,
                        "hash": c.hash, "modules": len(c.modules), "lessons": c.lesson_count, "minutes": 120,
                        "tags": ["python", "web"] if cid == "fastapi" else ["python", "beginner"],
                        "author": {"name": "inPace", "verified": True}, "pack": library.SITE + f"packs/{cid}.zip"})
    rms = [{"id": "python-web", "title": "Python for the web", "description": "From your first line to an API.",
            "language": "en", "author": {"name": "inPace", "verified": True}, "tags": ["python"],
            "steps": [{"course": "python-basics", "note": "Start here."}, {"course": "fastapi"}], "minutes": 240,
            "hash": "aaa"}]
    return {"inpace": "library", "v": 1, "courses": courses, "roadmaps": rms + (extra_roadmaps or [])}


@pytest.fixture
def app(tmp_path, monkeypatch):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    (v.home / "library.json").write_text(json.dumps(lib_index()), encoding="utf-8")

    def fake_download(entry):
        return course_to_pack(load_course(files_from_folder(SAMPLES / entry["id"])), True)
    monkeypatch.setattr(library, "download", fake_download)
    return v, c


def test_parse_checks_a_roadmap():
    rm = roadmaps.parse("title: Learn things\nsteps:\n  - python-basics\n  - course: fastapi\n    optional: yes\n")
    assert rm["id"] == "learn-things" and rm["steps"][1]["optional"] is True
    for bad, words in [("title: x\nsteps: []", "at least one course"),
                       ("title: Two\nsteps: [a-b, a-b]", "twice"),
                       ("steps: [abc]", "title"),
                       ("title: Opt\nsteps: [{course: abc, optional: true}]", "must be required")]:
        with pytest.raises(roadmaps.RoadmapError) as e:
            roadmaps.parse(bad)
        assert any(words in p for p in e.value.problems), (bad, e.value.problems)
    assert roadmaps.slug("تعلم الإنجليزي").startswith("roadmap-")
    again = roadmaps.parse(roadmaps.to_yaml(rm))
    assert roadmaps.fingerprint(again) == roadmaps.fingerprint(rm)


def test_suggest_puts_the_basics_first_and_series_in_order():
    courses = [{"id": "dl-2-cnns", "title": "Deep learning 2: CNNs", "tags": ["deep learning"]},
               {"id": "maths-1", "title": "Maths for ML 1", "tags": ["math", "machine learning"]},
               {"id": "dl-1-networks", "title": "Deep learning 1: networks", "tags": ["deep learning", "machine learning"]},
               {"id": "cooking", "title": "Cooking pasta", "tags": ["food"]},
               {"id": "python-basics", "title": "Python Basics", "tags": ["python", "beginner"], "language": "en"},
               {"id": "python-basics-ar", "title": "أساسيات بايثون", "tags": ["python", "beginner"], "language": "ar"}]
    assert roadmaps.suggest("machine learning", courses) == ["maths-1", "dl-1-networks", "dl-2-cnns"]
    assert roadmaps.suggest("python", courses, "ar") == ["python-basics-ar"]
    assert roadmaps.suggest("python", courses, "en") == ["python-basics"]
    assert roadmaps.suggest("knitting", courses) == []


def test_follow_a_library_roadmap_and_walk_it(app):
    v, c = app
    page = html.unescape(c.get("/library?tab=roadmaps").text)
    assert "Python for the web" in page and 'action="/roadmaps/python-web/follow"' in page
    page = html.unescape(c.get("/roadmaps/python-web").text)  # a preview before following
    assert "Follow this roadmap" in page and "Start here." in page and "voyage-chart" in page
    c.post("/roadmaps/python-web/follow")
    rm = roadmaps.get(v.home, "python-web")
    assert rm["source"] == "library" and rm["steps"][0]["title"] == "Python Basics"
    page = html.unescape(c.get("/roadmaps/python-web").text)
    assert "Add course 1 from the library" in page
    r = c.post("/roadmaps/python-web/add/python-basics", follow_redirects=False)
    assert r.headers["location"].startswith("/roadmaps/python-web")
    assert v.get_course("python-basics")
    page = html.unescape(c.get("/roadmaps/python-web").text)
    assert "Start course 1" in page
    jid = c.post("/roadmaps/python-web/start/python-basics", follow_redirects=False).headers["location"].rsplit("/", 1)[-1]
    # Home and the course page show where you are on the roadmap
    home = html.unescape(c.get("/").text)
    assert "Your roadmap" in home and "Course 1 of 2: Python Basics" in home
    assert "Course 1 of 2 on “Python for the web”" in html.unescape(c.get(f"/learn/{jid}").text)
    # finish the course: the roadmap moves on, and the island counts the port
    st = roadmaps.status(v, rm, lib_index())
    assert st["current"]["course"] == "python-basics" and st["done"] == 0
    _finish_course(v, jid)
    st = roadmaps.status(v, rm, lib_index())
    assert st["steps"][0]["state"] == "done" and st["current"]["course"] == "fastapi" and st["percent"] == 50
    assert roadmaps.island_stats(v) == {"roadmap_steps": 1, "roadmaps": 0}
    assert garden._have(garden.GULL_GOAL, garden.stats(v))
    # Following again only updates; stopping keeps the courses
    c.post("/roadmaps/python-web/remove")
    assert not roadmaps.get(v.home, "python-web") and v.get_course("python-basics")


def _finish_course(v, jid):
    """Mark a course finished the way progress reads it: every lesson, task and quiz done."""
    course = v.get_course(v.journey(jid)["course_id"])
    for m in course.modules:
        for les in m["lessons"]:
            v.add_event(jid, "lesson_done", {"lesson": les["id"], "title": les["title"]})
        for r in m["requires"]:
            v.add_event(jid, "quiz_taken", {"req": r["id"], "percent": 100})
            v.add_event(jid, "writeup_saved", {"req": r["id"], "text": "done", "words": 999})
            v.add_event(jid, "evidence_added", {"req": r["id"], "name": "x.txt", "sha256": "0" * 64, "size": 1})


def test_make_a_roadmap_from_a_goal_and_share_it(app):
    v, c = app
    page = html.unescape(c.get("/roadmaps/new?goal=python").text)
    assert "courses for “python”" in page and 'data-course="python-basics"' in page
    steps = [{"course": "python-basics", "note": "Basics first."}, {"course": "fastapi", "optional": True}]
    r = c.post("/roadmaps/new", data={"title": "My Python path", "description": "Mine.", "language": "en",
                                      "tags": "python, web", "steps": json.dumps(steps)}, follow_redirects=False)
    assert r.headers["location"].startswith("/roadmaps/my-python-path")
    rm = roadmaps.get(v.home, "my-python-path")
    assert rm["source"] == "mine" and rm["author"] == "Mona" and rm["steps"][1]["optional"] and rm["tags"] == ["python", "web"]
    # without JavaScript: the ticked courses
    c.post("/roadmaps/new", data={"title": "Ticked", "pick": ["fastapi", "python-basics"]})
    assert [s["course"] for s in roadmaps.get(v.home, "ticked")["steps"]] == ["fastapi", "python-basics"]
    # problems come back on the same page
    page = html.unescape(c.post("/roadmaps/new", data={"title": "", "steps": "[]"}).text)
    assert "Give the roadmap a title." in page and "Add at least one course" in page
    # edit keeps the id
    c.post("/roadmaps/my-python-path/edit", data={"title": "My Python path, v2", "steps": json.dumps(steps[:1])})
    assert roadmaps.get(v.home, "my-python-path")["title"] == "My Python path, v2"
    # share: the whole roadmap in a link, and the library form ready to fill
    page = html.unescape(c.get("/roadmaps/my-python-path/share").text)
    assert "Send on Telegram" in page and "template=submit-roadmap.yml" in page and "Publish it to the library" in page
    from inpace import exchange
    link = page.split('id="roadmap-link"')[1].split("</textarea>")[0]
    data = exchange.from_code(link)
    assert data["inpace"] == "roadmap" and data["steps"][0]["course"] == "python-basics"
    # someone opens the link: a preview, then follow
    v2 = Vault(v.home.parent / "friend")
    c2 = TestClient(create_app(v2))
    c2.post("/setup", data={"name": "Sam", "color": "#1F7A56"})
    (v2.home / "library.json").write_text(json.dumps(lib_index()), encoding="utf-8")
    raw = c2.post("/open", data={"code": link}).text
    page = html.unescape(raw)
    assert "My Python path, v2" in page and "Follow this roadmap" in page
    shared = raw.split('name="data" value="')[1].split('"')[0]
    c2.post("/roadmaps/shared", data={"data": html.unescape(shared)})
    assert roadmaps.get(v2.home, "my-python-path")["source"] == "link"
    # the file opens too
    yml = c.get("/roadmaps/my-python-path/file").content
    assert b"steps:" in yml
    page = html.unescape(c2.post("/open", files={"file": ("path.roadmap.yaml", yml, "text/yaml")}).text)
    assert "Follow this roadmap" in page


def test_library_course_shows_its_roadmaps_and_links_open(app):
    v, c = app
    page = html.unescape(c.get("/library/fastapi").text)
    assert "On these roadmaps:" in page and "/roadmaps/python-web" in page
    from inpace import exchange
    link = exchange.to_link(roadmaps.share_data(roadmaps.library_find(lib_index(), "python-web"), True))
    r = c.post("/open", data={"code": link}, follow_redirects=False)
    assert r.headers["location"] == "/roadmaps/python-web"


def test_voyage_mode(app):
    v, c = app
    page = html.unescape(c.get("/island/voyages").text)
    assert "No voyage yet" in page and "A friend is waiting" in page
    c.post("/roadmaps/python-web/follow")
    page = html.unescape(c.get("/island/voyages").text)
    assert "Python for the web" in page and "voyage-chart" in page and "Port 0 of 2" in page
    st = roadmaps.status(v, roadmaps.get(v.home, "python-web"), lib_index())
    svg = garden.voyage_chart(st)
    assert svg.count('class="port ') == 2 and "voyage-boat" in svg and "harbour" in svg
    # shells: 10 a port, 100 for the harbour
    base = {k: 0 for k in ("focus_min", "lessons", "reviews", "modules", "milestones", "approved", "courses")}
    assert garden.earned({**base, "roadmap_steps": 2, "roadmaps": 1}) == 120


def test_old_library_lists_without_roadmaps_still_work(app):
    v, c = app
    idx = lib_index()
    del idx["roadmaps"]
    (v.home / "library.json").write_text(json.dumps(idx), encoding="utf-8")
    assert "Roadmaps" in c.get("/library").text
    page = html.unescape(c.get("/library?tab=roadmaps").text)
    assert "No roadmaps in the library yet" in page
    assert c.get("/roadmaps").status_code == 200
