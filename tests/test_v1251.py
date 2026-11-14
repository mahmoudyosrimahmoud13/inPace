"""v1.25.1: roadmaps with courses you can't get (not in the library, or no library list yet), and adding all of a
roadmap's courses at once."""
import html
import json

from inpace import library, roadmaps
from tests.test_v124 import app, lib_index  # noqa: F401  (the fixture)


def _shared(c, steps):
    data = {"inpace": "roadmap", "id": "from-a-friend", "title": "From a friend", "steps": steps}
    return c.post("/roadmaps/shared", data={"data": json.dumps(data)}, follow_redirects=False)


def test_a_course_that_isnt_in_the_library_never_blocks_the_way(app, monkeypatch):
    v, c = app
    monkeypatch.setattr(library, "load_index", lambda home, force=False: lib_index())
    _shared(c, [{"course": "secret-course", "title": "My private course"}, {"course": "python-basics"}])
    rm = roadmaps.get(v.home, "from-a-friend")
    st = roadmaps.status(v, rm, lib_index())
    assert st["steps"][0]["state"] == "missing" and st["blocked"][0]["course"] == "secret-course"
    assert st["current"]["course"] == "python-basics"  # the next course you can take, not the dead end
    page = html.unescape(c.get("/roadmaps/from-a-friend").text)
    assert "Add course 2 from the library" in page and "aren’t on this device or in the library" in page
    assert 'action="/roadmaps/from-a-friend/drop-missing"' in page and 'href="/open"' in page
    # take it off: the roadmap becomes your own version, and can now be finished
    c.post("/roadmaps/from-a-friend/drop-missing")
    rm = roadmaps.get(v.home, "from-a-friend")
    assert [s["course"] for s in rm["steps"]] == ["python-basics"] and rm["source"] == "mine"


def test_nothing_is_taken_off_when_the_library_cant_be_checked(app, monkeypatch):
    v, c = app
    _shared(c, [{"course": "secret-course"}, {"course": "python-basics"}])

    def offline(home, force=False):
        raise library.LibraryProblem("The library couldn't be reached. Check your internet connection.")
    monkeypatch.setattr(library, "load_index", offline)
    r = c.post("/roadmaps/from-a-friend/drop-missing", follow_redirects=False)
    assert "internet" in html.unescape(r.headers["location"].replace("%20", " "))
    assert len(roadmaps.get(v.home, "from-a-friend")["steps"]) == 2
    # with no library list at all, courses aren't called missing: they're waiting for the internet
    (v.home / "library.json").unlink()
    st = roadmaps.status(v, roadmaps.get(v.home, "from-a-friend"), {})
    assert {s["state"] for s in st["steps"]} == {"unknown"} and not st["missing"] and st["current"]["course"] == "secret-course"
    page = html.unescape(c.get("/roadmaps/from-a-friend").text)
    assert "Connect to the internet, then check again" in page and "Not in the library" not in page
    assert "aren’t in the library" not in html.unescape(c.get("/roadmaps/from-a-friend/share").text)


def test_only_required_courses_that_are_gone_block_and_all_gone_cant_be_dropped(app, monkeypatch):
    v, c = app
    monkeypatch.setattr(library, "load_index", lambda home, force=False: lib_index())
    _shared(c, [{"course": "secret-course"}, {"course": "python-basics", "optional": True}])
    r = c.post("/roadmaps/from-a-friend/drop-missing", follow_redirects=False)
    assert "nothing would be left" in html.unescape(r.headers["location"].replace("%20", " "))
    assert len(roadmaps.get(v.home, "from-a-friend")["steps"]) == 2


def test_follow_adds_nothing_and_add_all_adds_every_course(app, monkeypatch):
    v, c = app
    monkeypatch.setattr(library, "load_index", lambda home, force=False: lib_index())
    c.post("/roadmaps/python-web/follow")
    assert not v.get_course("python-basics") and not v.get_course("fastapi")  # following downloads nothing
    page = html.unescape(c.get("/roadmaps/python-web").text)
    assert 'action="/roadmaps/python-web/add-all"' in page and "Add all 2" in page
    r = c.post("/roadmaps/python-web/add-all", follow_redirects=False)
    assert "Added 2 courses" in html.unescape(r.headers["location"].replace("%20", " "))
    assert v.get_course("python-basics") and v.get_course("fastapi")
    assert "add-all" not in c.get("/roadmaps/python-web").text


def test_a_roadmap_cant_be_used_to_add_a_course_it_doesnt_list(app):
    v, c = app
    c.post("/roadmaps/python-web/follow")
    r = c.post("/roadmaps/python-web/add/some-other-course", follow_redirects=False)
    assert "isn" in r.headers["location"] and not v.get_course("some-other-course")


def test_a_shared_roadmap_says_which_courses_cant_be_added_before_you_follow(app):
    v, c = app
    yml = b"title: X\nsteps:\n  - secret-course\n  - python-basics\n"
    page = html.unescape(c.post("/open", files={"file": ("x.roadmap.yaml", yml, "text/yaml")}).text)
    assert "Follow this roadmap" in page and "so you can’t add them from here" in page and "secret-course" in page
