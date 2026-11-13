"""v1.22: a download button under each lesson's YouTube video, and a small "Download for offline" button at the
top of the course page (the full "Watch offline" box stays at the bottom)."""
import html
import io
import time
import zipfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from inpace import offline
from inpace.app import create_app
from inpace.vault import Vault

LINKS = """# Docker
https://www.youtube.com/watch?v=PrusdhS2lmo
00:00:30 Introduction to Containers
00:19:49 Container Architecture
Kubernetes basics | https://www.youtube.com/watch?v=X48VuDVv0do
Networking for beginners | https://youtu.be/qiQR5rTSshw
"""

FAKE_YTDLP = '''
class YoutubeDL:
    def __init__(self, opts):
        self.opts = opts
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def extract_info(self, url, download=False, process=True):
        vid = url.split("v=")[-1]
        if vid == "qiQR5rTSshw":
            raise Exception("ERROR: [youtube] qiQR5rTSshw: Video unavailable")
        info = {"id": vid, "title": "Title of " + vid, "duration": 100}
        if download:
            for h in self.opts["progress_hooks"]:
                h({"status": "downloading", "downloaded_bytes": 5, "total_bytes": 10})
            path = self.opts["outtmpl"].replace("%(title).120B", info["title"]).replace("%(id)s", vid).replace("%(ext)s", "mp4")
            with open(path, "wb") as f:
                f.write(b"video")
            info["requested_downloads"] = [{"filepath": path}]
        return info
'''


@pytest.fixture(autouse=True)
def clean_up():
    import sys
    yield
    for job in offline.JOBS.values():
        job["stop"] = True
    end = time.time() + 30
    while any(j.get("state") == "running" for j in offline.JOBS.values()) and time.time() < end:
        time.sleep(0.05)
    offline.JOBS.clear()
    for entry in [e for e in sys.path if e.endswith("yt-dlp.zip")]:
        sys.path.remove(entry)
        offline._purge(Path(entry))
    offline._purge()


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    (h / "Downloads").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(h / ".config"))
    monkeypatch.delenv("INPACE_MOBILE", raising=False)
    monkeypatch.setattr(offline, "free_space", lambda folder: 500 * 1024 ** 3)
    return h


def fake_tool(module: str) -> bytes:
    buf = io.BytesIO()
    buf.write(b"#!/usr/bin/env python3\n")
    with zipfile.ZipFile(buf, "a") as z:
        z.writestr("yt_dlp/__init__.py", module)
        z.writestr("yt_dlp/version.py", "__version__ = '2026.11.01'\n")
    return buf.getvalue()


def setup(tmp_path, tool: bool = True):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    c.post("/add/links", data={"title": "DevOps", "links": LINKS})
    course = v.courses()[0]
    jid = c.post(f"/courses/{course.id}/start", follow_redirects=False).headers["location"].rsplit("/", 1)[-1]
    if tool:
        offline.tool_path(v.home).parent.mkdir(parents=True)
        offline.tool_path(v.home).write_bytes(fake_tool(FAKE_YTDLP))
    return v, c, course, jid


def wait_for(course_id: str, seconds: float = 30) -> dict:
    end = time.time() + seconds
    while time.time() < end:
        job = offline.JOBS.get(course_id) or {}
        if job.get("state") != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("the download didn't finish in time")


def lesson_with(course, vid: str) -> str:
    for m in course.modules:
        for les in m["lessons"]:
            if vid in (les.get("media") or ""):
                return les["id"]
    raise AssertionError(vid)


def test_each_video_has_a_download_button(tmp_path, home):
    v, c, course, jid = setup(tmp_path)
    lid = lesson_with(course, "X48VuDVv0do")
    page = html.unescape(c.get(f"/learn/{jid}/lesson/{lid}").text)
    assert 'class="yt-save"' in page and "Download this video" in page
    assert f'action="/courses/{course.id}/offline/video"' in page and 'name="vid" value="X48VuDVv0do"' in page
    assert f'data-yt-save="/courses/{course.id}/offline/status?vid=X48VuDVv0do"' in page
    # Once YouTube told us how long it is, the button says how big it is.
    v._set_meta("yttitle:X48VuDVv0do", '{"title": "K8s", "duration": 3600}')
    page = html.unescape(c.get(f"/learn/{jid}/lesson/{lid}").text)
    assert "About 600 MB. Then it plays without internet." in page


def test_download_only_this_video(tmp_path, home):
    v, c, course, jid = setup(tmp_path)
    lid = lesson_with(course, "X48VuDVv0do")
    r = c.post(f"/courses/{course.id}/offline/video", data={"vid": "X48VuDVv0do"},
               headers={"Accept": "application/json"})
    d = r.json()
    assert d["ok"] and d["state"] in ("downloading", "waiting", "saved")
    wait_for(course.id)
    assert offline.local_file(v, course.id, "X48VuDVv0do")
    assert not offline.local_file(v, course.id, "PrusdhS2lmo")  # only the one asked for
    st = c.get(f"/courses/{course.id}/offline/status?vid=X48VuDVv0do").json()
    assert st["video"]["state"] == "saved" and st["have"] == 1
    page = html.unescape(c.get(f"/learn/{jid}/lesson/{lid}").text)
    assert "Playing the copy on this computer." in page and "Download this video" not in page


def test_a_video_that_fails_says_why_under_it(tmp_path, home):
    v, c, course, jid = setup(tmp_path)
    c.post(f"/courses/{course.id}/offline/video", data={"vid": "qiQR5rTSshw"}, headers={"Accept": "application/json"})
    wait_for(course.id)
    st = c.get(f"/courses/{course.id}/offline/status?vid=qiQR5rTSshw").json()["video"]
    assert st["state"] == "failed" and st["why"] == "YouTube says this video isn't available anymore."
    assert offline.plain_why("ERROR: Unable to download API page: Tunnel connection failed: 403").startswith("No internet")
    assert offline.plain_why("something new went wrong") == "something new went wrong"
    lid = lesson_with(course, "qiQR5rTSshw")
    page = html.unescape(c.get(f"/learn/{jid}/lesson/{lid}").text)
    assert "It didn't download." in page and "Try again" in page


def test_without_javascript_it_comes_back_to_the_lesson(tmp_path, home):
    v, c, course, jid = setup(tmp_path)
    lid = lesson_with(course, "X48VuDVv0do")
    r = c.post(f"/courses/{course.id}/offline/video", data={"vid": "X48VuDVv0do"},
               headers={"Referer": f"http://testserver/learn/{jid}/lesson/{lid}"}, follow_redirects=False)
    assert r.status_code in (302, 303) and r.headers["location"].startswith(f"/learn/{jid}/lesson/{lid}")
    wait_for(course.id)
    # Someone else's page can't send you anywhere: only inPace's own lesson pages count.
    r = c.post(f"/courses/{course.id}/offline/video", data={"vid": "X48VuDVv0do"},
               headers={"Referer": "https://evil.example/somewhere"}, follow_redirects=False)
    assert r.headers["location"].startswith(f"/learn/{jid}")
    wait_for(course.id)


def test_only_the_course_videos_and_space_is_checked(tmp_path, home, monkeypatch):
    v, c, course, jid = setup(tmp_path)
    d = c.post(f"/courses/{course.id}/offline/video", data={"vid": "zzzzzzzzzzz"}, headers={"Accept": "application/json"}).json()
    assert not d["ok"] and "isn't part of the course" in d["message"]
    assert course.id not in offline.JOBS
    v._set_meta("yttitle:X48VuDVv0do", '{"title": "K8s", "duration": 36000}')  # ten hours: about 5.9 GB at 720p
    monkeypatch.setattr(offline, "free_space", lambda folder: 1024 ** 3)
    d = c.post(f"/courses/{course.id}/offline/video", data={"vid": "X48VuDVv0do"}, headers={"Accept": "application/json"}).json()
    assert not d["ok"] and "Not enough space" in d["message"] and course.id not in offline.JOBS


def test_asking_while_it_runs_adds_to_the_same_download(tmp_path, home):
    v, c, course, jid = setup(tmp_path, tool=False)
    items = {it["id"]: it for it in offline.course_videos(course)}
    job = {"state": "running", "pending": [], "queue": ["PrusdhS2lmo"], "want_all": False, "all": False,
           "asked": ["PrusdhS2lmo"], "current": "PrusdhS2lmo", "percent": 40.0, "failed": []}
    offline.JOBS[course.id] = job
    assert offline.start_download(v, course, only=[items["X48VuDVv0do"]]) is job
    assert [p["id"] for p in job["pending"]] == ["X48VuDVv0do"]
    offline.start_download(v, course, only=[items["X48VuDVv0do"]])  # twice: still once
    offline.start_download(v, course, only=[items["PrusdhS2lmo"]])  # already in the list
    assert [p["id"] for p in job["pending"]] == ["X48VuDVv0do"]
    assert offline.video_state(v, course, "PrusdhS2lmo") == {"state": "downloading", "percent": 40.0}
    assert offline.video_state(v, course, "X48VuDVv0do")["state"] == "waiting"
    assert offline.video_state(v, course, "qiQR5rTSshw")["state"] == "none"
    offline.start_download(v, course)  # "download all" now: the rest of the course comes after
    assert job["want_all"] and offline.video_state(v, course, "qiQR5rTSshw")["state"] == "waiting"
    job["state"] = "done"


def test_one_video_then_the_whole_course(tmp_path, home):
    v, c, course, jid = setup(tmp_path)
    c.post(f"/courses/{course.id}/offline/video", data={"vid": "X48VuDVv0do"}, headers={"Accept": "application/json"})
    wait_for(course.id)
    c.post(f"/courses/{course.id}/offline/download", data={"from": "top"})
    job = wait_for(course.id)
    assert job["state"] == "partly" and job["total"] == 3
    assert offline.local_file(v, course.id, "PrusdhS2lmo") and offline.local_file(v, course.id, "X48VuDVv0do")


def test_small_download_button_at_the_top_of_the_course_page(tmp_path, home):
    v, c, course, jid = setup(tmp_path)
    page = html.unescape(c.get(f"/learn/{jid}").text)
    top, bottom = page.index("Download for offline"), page.index('id="offline"')
    assert top < page.index("trail-module") < bottom  # the button on top, the whole box still at the bottom
    assert "Options" in page[top:top + 800]
    r = c.post(f"/courses/{course.id}/offline/download", data={"from": "top"}, follow_redirects=False)
    assert r.headers["location"].split("?")[0] == f"/learn/{jid}"  # back to the top, not down to the box
    wait_for(course.id)
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert "Download the rest for offline" in page  # one video didn't download
    for vid in ("PrusdhS2lmo", "X48VuDVv0do", "qiQR5rTSshw"):
        f = tmp_path / f"{vid}.mp4"
        f.write_bytes(b"x")
        offline.set_local_file(v, course.id, vid, f)
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert "Videos saved for offline" in page and "Download for offline" not in page


def test_top_button_uses_the_course_quality(tmp_path, home):
    v, c, course, jid = setup(tmp_path)
    v._set_meta(f"ytdlp_quality:{course.id}", "360")
    c.post(f"/courses/{course.id}/offline/download", data={"from": "top"})
    assert offline.JOBS[course.id]["quality"] == "360"
    wait_for(course.id)


def test_running_download_shows_at_the_top(tmp_path, home):
    v, c, course, jid = setup(tmp_path, tool=False)
    offline.JOBS[course.id] = {"state": "running", "done": 1, "total": 3, "title": "x", "percent": 0, "failed": [],
                               "pending": [], "queue": [], "asked": [], "current": "", "want_all": False, "all": True}
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert "Downloading videos" in page and "data-offline-quick-num>1 / 3" in page
    offline.JOBS[course.id]["state"] = "done"
