"""v1.32.1: "Open it" on a code file or notebook opens it in your own app (VS Code, Jupyter, your editor) instead of
showing raw text, and "Show in folder" opens the folder it's in. Phones keep the plain-text view."""
from pathlib import Path

import pytest

import inpace.app as app_mod
from inpace import media
from inpace.app import open_on_desktop


class Files:
    def __init__(self, action):
        self.open_action = action


def tr(s):
    return s


def test_computers_get_open_and_show_in_folder():
    out = media.open_buttons(Files("/courses/c1/open-media"), "files/lab/p01.ipynb", "/m/c1/files/lab/p01.ipynb", tr)
    assert 'data-open-file="/courses/c1/open-media"' in out and 'data-media="files/lab/p01.ipynb"' in out
    assert "Open it" in out and "Show in folder" in out and "data-reveal" in out
    assert 'data-view="/m/c1/files/lab/p01.ipynb?view=1"' in out  # the plain-text view, if opening fails


def test_phones_keep_the_plain_text_view():
    out = media.open_buttons(Files(""), "files/a.py", "/m/c1/files/a.py", tr)
    assert out.startswith("<a ") and "?view=1" in out and "Show in folder" not in out
    assert media.open_buttons(Files(""), "files/", "", tr, folder=True) == ""


def test_a_project_folder_has_open_the_folder_and_a_button_per_file(tmp_path):
    (tmp_path / "lab").mkdir()
    (tmp_path / "lab" / "p01.py").write_text("print(1)\n")
    (tmp_path / "lab" / "p02.ipynb").write_text('{"cells": []}')
    out = media.folder_view("c1", "files/lab/", tmp_path / "lab", tr, Files("/courses/c1/open-media"))
    assert "Open the folder" in out and 'data-media="files/lab/"' in out
    assert 'data-media="files/lab/p01.py"' in out and 'data-media="files/lab/p02.ipynb"' in out
    assert "Open it" not in media.folder_view("c1", "files/lab/", tmp_path / "lab", tr)  # old callers: unchanged


@pytest.fixture
def launched(monkeypatch):
    got = []
    monkeypatch.setattr(app_mod.subprocess, "Popen", lambda args, **k: got.append(args))
    monkeypatch.setattr(app_mod.subprocess, "run", lambda args, **k: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(app_mod.shutil, "which", lambda name: None)
    return got


def _on(monkeypatch, platform):
    monkeypatch.setattr(app_mod.sys, "platform", platform)


def test_code_goes_to_vs_code_when_it_is_installed(tmp_path, monkeypatch, launched):
    _on(monkeypatch, "linux")
    nb = tmp_path / "p01.ipynb"
    nb.write_text("{}")
    monkeypatch.setattr(app_mod.shutil, "which", lambda name: "/usr/bin/code" if name == "code" else None)
    open_on_desktop(nb)
    assert launched == [["/usr/bin/code", str(nb)]]


def test_a_notebook_opens_in_its_own_app(tmp_path, monkeypatch, launched):
    _on(monkeypatch, "linux")
    nb = tmp_path / "p01.ipynb"
    nb.write_text("{}")
    open_on_desktop(nb)
    assert launched == [["xdg-open", str(nb)]]


def test_a_script_is_never_run(tmp_path, monkeypatch, launched):
    py = tmp_path / "p01.py"
    py.write_text("print(1)")
    _on(monkeypatch, "darwin")
    open_on_desktop(py)
    assert launched[-1] == ["open", "-t", str(py)]  # the text editor, not Python
    _on(monkeypatch, "win32")
    verbs = []
    monkeypatch.setattr(app_mod.os, "startfile", lambda p, *v: verbs.append(v), raising=False)
    open_on_desktop(py)
    assert verbs == [("edit",)]  # Windows' "Edit", never "Open" (which runs it)
    _on(monkeypatch, "linux")
    launched.clear()
    desk = tmp_path / "x.desktop"
    desk.write_text("[Desktop Entry]")
    open_on_desktop(desk)
    assert launched == [["xdg-open", str(tmp_path)]]  # only its folder


def test_show_in_folder_on_each_system(tmp_path, monkeypatch, launched):
    f = tmp_path / "p01.py"
    f.write_text("")
    _on(monkeypatch, "darwin")
    open_on_desktop(f, reveal=True)
    assert launched[-1] == ["open", "-R", str(f)]
    _on(monkeypatch, "win32")
    open_on_desktop(f, reveal=True)
    assert launched[-1] == f'explorer /select,"{f}"'
    _on(monkeypatch, "linux")
    open_on_desktop(f, reveal=True)  # no file manager answered: the folder opens
    assert launched[-1] == ["xdg-open", str(tmp_path)]


def test_the_route_shows_a_course_file_in_its_folder(tmp_path, monkeypatch, launched):
    from tests.test_v127 import _folder_lesson
    _on(monkeypatch, "linux")
    v, c, course, jid = _folder_lesson(tmp_path)
    r = c.post(f"/courses/{course.id}/open-media", data={"media": "01 Intro/01 - Welcome.mp4", "reveal": "1"})
    assert r.json() == {"ok": True} and launched[-1][0] == "xdg-open" and launched[-1][1].endswith("01 Intro")
    assert c.post(f"/courses/{course.id}/open-media", data={"media": "../../etc/passwd", "reveal": "1"}).status_code == 404


def _library(home, steps, h, rid="python-web", extra=None):
    import json as _json
    from tests.test_v124 import lib_index
    idx = lib_index()
    idx["roadmaps"][0].update(steps=steps, hash=h)
    idx["roadmaps"] += extra or []
    (home / "library.json").write_text(_json.dumps(idx), encoding="utf-8")
    return idx


def test_every_followed_library_roadmap_updates_itself(tmp_path, monkeypatch):
    """When the library changes a roadmap's order or courses, every copy you follow changes with it, all at once,
    without an update button per roadmap. Roadmaps you made yourself are never touched."""
    from starlette.testclient import TestClient
    from inpace import library, roadmaps
    from inpace.app import create_app
    from inpace.vault import Vault
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    two = {"id": "web-two", "title": "Second path", "language": "en", "author": {"name": "inPace"},
           "steps": [{"course": "python-basics"}], "hash": "b1"}
    _library(v.home, [{"course": "python-basics", "note": "Start here."}, {"course": "fastapi"}], "aaa", extra=[two])
    c.post("/roadmaps/python-web/follow")
    c.post("/roadmaps/web-two/follow")
    roadmaps.save(v.home, {"id": "my-own", "title": "Mine", "steps": [{"course": "fastapi"}], "source": "mine"})
    started = roadmaps.get(v.home, "python-web")["followed_at"]

    # The library reorders one roadmap and adds a course to the other.
    two2 = {**two, "steps": [{"course": "python-basics"}, {"course": "fastapi", "optional": True}], "hash": "b2"}
    _library(v.home, [{"course": "fastapi", "note": "API first now."}, {"course": "python-basics"}], "bbb", extra=[two2])
    c.get("/")                                               # any page that reads the library list syncs
    rm = roadmaps.get(v.home, "python-web")
    assert [s["course"] for s in rm["steps"]] == ["fastapi", "python-basics"]
    assert rm["library_hash"] == "bbb" and rm["followed_at"] == started and rm["source"] == "library"
    assert [s["course"] for s in roadmaps.get(v.home, "web-two")["steps"]] == ["python-basics", "fastapi"]
    assert [s["course"] for s in roadmaps.get(v.home, "my-own")["steps"]] == ["fastapi"]   # yours: untouched
    assert "newer version of this roadmap" not in c.get("/roadmaps/python-web").text  # nothing left to click

    # A roadmap that leaves the library stays as you had it; offline lists change nothing.
    idx = _library(v.home, [{"course": "python-basics"}], "ccc")
    idx["offline"] = True
    assert roadmaps.sync_library(v.home, idx) == []
    idx.pop("offline")
    assert roadmaps.sync_library(v.home, idx) == ["python-web"]
    assert [s["course"] for s in roadmaps.get(v.home, "web-two")["steps"]] == ["python-basics", "fastapi"]
    assert roadmaps.sync_library(v.home, idx) == []          # already up to date: nothing to do


def test_one_button_updates_every_course_and_roadmap(tmp_path, monkeypatch):
    import html
    import json as _json
    from starlette.testclient import TestClient
    from inpace import library, roadmaps
    from inpace.app import SAMPLES, create_app
    from inpace.course import course_to_pack, files_from_folder, load_course
    from inpace.vault import Vault
    from tests.test_v124 import lib_index
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    idx = lib_index()
    (v.home / "library.json").write_text(_json.dumps(idx), encoding="utf-8")
    calls = []

    def fake_download(entry):
        calls.append(entry["id"])
        return course_to_pack(load_course(files_from_folder(SAMPLES / entry["id"])), True)
    monkeypatch.setattr(library, "download", fake_download)
    monkeypatch.setattr(library, "load_index", lambda home, refresh=False: _json.loads(
        (home / "library.json").read_text(encoding="utf-8")))
    c.post("/library/python-basics/add")
    c.post("/roadmaps/python-web/follow")
    page = html.unescape(c.get("/library").text)
    assert 'action="/library/update-all"' in page and "Update everything" in page

    # The library publishes a new version of the course and reorders the roadmap.
    idx["courses"][0]["hash"] = "new-version"
    idx["roadmaps"][0].update(hash="r2", steps=[{"course": "fastapi"}, {"course": "python-basics"}])
    (v.home / "library.json").write_text(_json.dumps(idx), encoding="utf-8")
    roadmaps.save(v.home, {**roadmaps.get(v.home, "python-web")})        # (no sync yet: nothing opened)
    page = html.unescape(c.get("/library").text)
    assert 'Update everything <span class="n">1</span>' in page
    calls.clear()
    r = c.post("/library/update-all", follow_redirects=False)
    assert calls == ["python-basics"]                                     # fastapi was never added: not downloaded
    msg = html.unescape(c.get(r.headers["location"]).text)
    assert "Updated “Python Basics”. Your progress is kept." in msg or "Updated" in msg
    assert [s["course"] for s in roadmaps.get(v.home, "python-web")["steps"]] == ["fastapi", "python-basics"]

    # Nothing newer: the button says so and downloads nothing.
    idx["courses"][0]["hash"] = v.get_course("python-basics").hash
    (v.home / "library.json").write_text(_json.dumps(idx), encoding="utf-8")
    calls.clear()
    r = c.post("/library/update-all")
    assert calls == [] and "Everything from the library is up to date." in html.unescape(r.text)
