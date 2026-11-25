"""v1.26: a pop-up when a new version is out (every platform, phones too), feedback and ideas as a ready GitHub issue,
and a form for publishing a course."""
import html
import json
import time

from starlette.testclient import TestClient

from inpace import updater
from inpace.app import SAMPLES, create_app
from inpace.course import files_from_folder, load_course
from inpace.vault import Vault


def _app(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "lang": "en"})
    v._set_meta("tour_done", "x")
    return v, c


def _news(v, version="99.0.0"):
    v._set_meta("update_news", json.dumps({"version": version, "page": "https://github.com/x/releases/tag/v" + version,
                                           "notes": "- **Notes on lessons.** Select a line.\n\n## Older\n- old",
                                           "assets": {updater.ANDROID_APK: "https://example.com/inPace.apk"}}))
    v._set_meta("update_news_checked", str(int(time.time())))


def test_latest_and_check_news(tmp_path, monkeypatch):
    v = Vault(tmp_path / "me")
    monkeypatch.setattr(updater, "latest", lambda: {"version": "99.1.0", "page": "p", "notes": "n", "assets": {}})
    assert updater.check_news(v, force=True)["version"] == "99.1.0"
    assert updater.news(v)["version"] == "99.1.0"
    monkeypatch.setattr(updater, "latest", lambda: (_ for _ in ()).throw(OSError("offline")))
    assert updater.check_news(v, force=True)["version"] == "99.1.0"   # offline: keeps what it knew, quietly
    v._set_meta("update_news", json.dumps({"version": updater.__version__}))
    assert updater.news(v) == {}                                       # not newer than this copy


def test_the_pop_up_shows_once_until_later(tmp_path, monkeypatch):
    v, c = _app(tmp_path)
    _news(v)
    monkeypatch.setattr(updater, "install_kind", lambda: "windows")
    page = html.unescape(c.get("/").text)
    assert "inPace 99.0.0 is out!" in page and "Notes on lessons." in page and "Older" not in page
    assert 'action="/updates/check"' in page and "data-news-dialog" in page
    c.post("/updates/later", headers={"X-Inpace-Fetch": "1"})
    assert "data-news-dialog" not in c.get("/").text
    _news(v, "99.0.1")                                                 # a newer one: it shows again
    assert "inPace 99.0.1 is out!" in html.unescape(c.get("/courses").text)


def test_the_pop_up_fits_each_kind_of_copy(tmp_path, monkeypatch):
    v, c = _app(tmp_path)
    _news(v)
    monkeypatch.setattr(updater, "install_kind", lambda: "android")
    page = html.unescape(c.get("/").text)
    assert 'href="https://example.com/inPace.apk"' in page and "Download and install" in page
    monkeypatch.setattr(updater, "install_kind", lambda: "source")
    assert "git pull" in html.unescape(c.get("/").text)
    monkeypatch.setattr(updater, "install_kind", lambda: "mac")
    v._set_meta("updates", "auto")                                     # updates itself: its own bar says so
    assert "data-news-dialog" not in c.get("/").text


def test_no_pop_up_without_news_or_during_the_tour(tmp_path, monkeypatch):
    v, c = _app(tmp_path)
    monkeypatch.setattr(updater, "install_kind", lambda: "windows")
    assert "data-news-dialog" not in c.get("/").text
    _news(v)
    assert "data-news-dialog" not in c.get("/?tour=1").text


def test_feedback_page_builds_a_github_issue(tmp_path):
    v, c = _app(tmp_path)
    page = html.unescape(c.get("/feedback?kind=Idea or suggestion").text)
    assert 'data-base="https://github.com/mahmoudyosrimahmoud13/inpace/issues/new"' in page
    assert 'data-template="feedback.yml"' in page and 'value="Idea or suggestion" data-param="kind" checked' in page
    assert updater.__version__ in page and "Continue on GitHub" in page
    assert 'href="/feedback"' in c.get("/").text                      # in the menu


def test_publish_is_a_form_and_share_picks_a_course(tmp_path):
    v, c = _app(tmp_path)
    v.install_course(load_course(files_from_folder(SAMPLES / "python-basics")))
    page = html.unescape(c.get("/share").text)
    assert 'href="/courses/python-basics/publish"' in page
    page = html.unescape(c.get("/courses/python-basics/publish").text)
    assert 'data-template="submit-course.yml"' in page and 'data-param="license"' in page
    assert 'data-param="course_id" value="python-basics"' in page and "Open the form on GitHub" in page


def test_course_page_has_share_button(tmp_path):
    v, c = _app(tmp_path)
    v.install_course(load_course(files_from_folder(SAMPLES / "python-basics")))
    r = c.post("/courses/python-basics/start")
    page = html.unescape(c.get(str(r.url)).text)
    assert 'href="/courses/python-basics/share"' in page and "Share this course" in page
    assert c.get("/courses/python-basics/share").status_code == 200
