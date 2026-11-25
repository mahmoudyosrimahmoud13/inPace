"""v1.36.1: faster pages. Progress is computed once per change, roadmap files are parsed once per change,
and no page waits for the library's list to download (it's fetched behind the page, and a failure is
remembered for ten minutes)."""
import json
import time

import pytest
from starlette.testclient import TestClient

from inpace import library, roadmaps
from inpace.app import create_app
from inpace.vault import Vault


@pytest.fixture
def app(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    c.post("/courses/sample/python-basics")
    return v, c


def test_progress_is_kept_until_something_changes(app, monkeypatch):
    v, c = app
    jid = v.start_journey("python-basics")
    calls = {"n": 0}
    real = Vault._progress_uncached

    def counted(self, *a):
        calls["n"] += 1
        return real(self, *a)
    monkeypatch.setattr(Vault, "_progress_uncached", counted)
    a = v.progress(jid); b = v.progress(jid)
    assert calls["n"] == 1 and a == b and a["course"] is b["course"]
    a["percent"] = 99  # a caller's own copy: the next caller isn't affected
    assert v.progress(jid)["percent"] != 99
    lesson = v.get_course("python-basics").modules[0]["lessons"][0]["id"]
    c.post(f"/learn/{jid}/lesson/{lesson}/done")
    p = v.progress(jid)
    assert calls["n"] == 2 and p["lessons_done"] == 1
    v.install_course(v.get_course("python-basics"))  # the course changed (same content, but a fresh install)
    v.progress(jid)
    assert calls["n"] >= 2


def test_roadmap_files_are_parsed_once_per_change(tmp_path, monkeypatch):
    home = tmp_path / "me"
    rm = roadmaps.parse({"id": "rrr", "title": "R", "steps": [{"course": "a"}]}, "mine")
    roadmaps.save(home, rm)
    calls = {"n": 0}
    real = roadmaps.parse

    def counted(*a, **k):
        calls["n"] += 1
        return real(*a, **k)
    monkeypatch.setattr(roadmaps, "parse", counted)
    roadmaps._PARSED.clear()
    one = roadmaps.mine(home); two = roadmaps.get(home, "rrr"); three = roadmaps.mine(home)
    assert calls["n"] == 1 and one[0]["title"] == two["title"] == three[0]["title"] == "R"
    two["title"] = "changed by a caller"
    assert roadmaps.get(home, "rrr")["title"] == "R"
    time.sleep(0.01)
    roadmaps.save(home, {**rm, "title": "R2"})
    assert roadmaps.get(home, "rrr")["title"] == "R2" and calls["n"] >= 2  # parse() is also used by save()
    roadmaps.delete(home, "rrr")
    assert roadmaps.get(home, "rrr") is None and roadmaps.mine(home) == []


def test_no_page_waits_for_the_library(app, monkeypatch):
    v, c = app
    (v.home / "library.json").write_text(json.dumps({"inpace": "library", "v": 1, "courses": [], "roadmaps": []}))
    import os
    old = time.time() - 2 * 3600
    os.utime(v.home / "library.json", (old, old))  # the saved list is two hours old
    slow = {"n": 0}

    def never_answers(home, refresh=False):
        slow["n"] += 1
        time.sleep(0.4)
        raise library.LibraryProblem("no internet")
    monkeypatch.setattr(library, "load_index", never_answers)
    rm = roadmaps.parse({"id": "rrr", "title": "R", "steps": [{"course": "python-basics"}]}, "mine")
    roadmaps.save(v.home, rm)
    t = time.perf_counter()
    assert c.get("/roadmaps/rrr").status_code == 200
    assert time.perf_counter() - t < 0.35  # the page didn't wait for the download
    time.sleep(0.6)
    assert slow["n"] == 1
    for _ in range(3):
        c.get("/roadmaps/rrr"); c.get("/library")
    assert slow["n"] == 1  # the failure is remembered: no new try on every page
    assert "last time you looked" in c.get("/library").text
    assert c.get("/library?refresh=1").status_code == 200  # asking for it yourself still tries
    assert slow["n"] == 2


def test_followed_roadmaps_still_sync_when_the_library_changes(app):
    v, c = app
    lib = {"inpace": "library", "v": 1, "courses": [], "roadmaps": [
        {"id": "pw", "title": "PW", "language": "en", "author": {"name": "inPace"}, "tags": [],
         "steps": [{"course": "python-basics"}], "minutes": 10, "hash": "h1"}]}
    (v.home / "library.json").write_text(json.dumps(lib))
    c.post("/roadmaps/pw/follow")
    lib["roadmaps"][0].update(title="PW two", hash="h2")
    (v.home / "library.json").write_text(json.dumps(lib))
    c.get("/")
    assert roadmaps.get(v.home, "pw")["title"] == "PW two"


def test_the_window_tries_the_graphics_card_again_after_an_update(tmp_path, monkeypatch):
    from inpace import window as win
    home = tmp_path
    win.remember(home, "safe")
    assert win._order(win.GTK_MODES, home)[0] == "safe"  # same version: what worked last time
    assert win.drawing_on_cpu(home)
    monkeypatch.setattr(win, "__version__", "0.0.0", raising=False)
    import inpace
    monkeypatch.setattr(inpace, "__version__", "9.9.9")
    assert win._order(win.GTK_MODES, home)[0] == "gpu"  # a new version: the graphics card first again
    win.remember(home, "gpu")
    (home / "window.json").write_text('{"version": "1.0.0", "way": "gpu"}')
    assert win._order(win.GTK_MODES, home)[0] == "gpu" and not win.drawing_on_cpu(home)


def test_settings_offers_to_retry_the_graphics_card(app, monkeypatch):
    from inpace import window as win
    v, c = app
    monkeypatch.setattr(win.sys, "platform", "linux")
    import inpace.app as app_mod
    monkeypatch.setattr(app_mod.sys, "platform", "linux")
    assert "Slow scrolling?" not in c.get("/settings").text
    win.remember(v.home, "safe")
    page = c.get("/settings").text
    assert "Slow scrolling?" in page and 'action="/settings/window-retry"' in page
    c.post("/settings/window-retry")
    assert not (v.home / "window.json").exists() and "Slow scrolling?" not in c.get("/settings").text


def test_forms_that_answer_with_a_file_are_saved_not_opened_again(app):
    """The backup showed "Method Not Allowed": the page sent the form in the background, got a file back, then
    opened its address again without the form. Forms that answer with a file are sent the usual way now."""
    from pathlib import Path
    v, c = app
    page = c.get("/settings").text
    assert 'action="/settings/backup" class="row" data-progress' in page  # v1.37: a progress bar, then a download link
    assert 'action="/me/turtle.png" class="row wrap" data-turtle-png data-file-form' in page
    island = (Path(__file__).parent.parent / "inpace" / "templates" / "island.html").read_text(encoding="utf-8")
    assert 'action="/island/share.png" data-share-island data-file-form' in island
    js = (Path(__file__).parent.parent / "inpace" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'if (f.hasAttribute("data-file-form")) return;' in js and "HTMLFormElement.prototype.submit.call(f)" in js
    for path, back in (("/settings/backup", "/settings"), ("/me/turtle.png", "/settings"), ("/island/share.png", "/island")):
        r = c.get(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith(back), path
    c.post("/settings/backup", data={"password": "secret123"})
    r = c.get("/settings/backup/file")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
