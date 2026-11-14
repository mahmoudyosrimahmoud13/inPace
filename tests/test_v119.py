"""v1.19: YouTube lessons offline: download them with yt-dlp (kept up to date), or point to videos you already
have and inPace matches the files to the lessons even when the names are a bit different."""
import hashlib
import html
import io
import re
import struct
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
00:50:14 Introduction to Docker
# More
Kubernetes basics | https://www.youtube.com/watch?v=X48VuDVv0do
Networking for beginners | https://youtu.be/qiQR5rTSshw
"""


@pytest.fixture(autouse=True)
def clean_up():
    """After each test: let background downloads end, and forget any stand-in yt-dlp, so tests never affect
    each other (whatever order they run in, on any machine)."""
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


def app(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    return v, c


def mp4(seconds: float, scale: int = 1000) -> bytes:
    """A tiny MP4 header: enough for inPace to read the video's length."""
    mvhd_body = bytes(4) + struct.pack(">IIII", 0, 0, scale, int(seconds * scale)) + bytes(80)
    mvhd = struct.pack(">I4s", 8 + len(mvhd_body), b"mvhd") + mvhd_body
    moov = struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd
    ftyp = struct.pack(">I4s", 16, b"ftyp") + b"isom" + bytes(4)
    return ftyp + moov


def course_with_videos(v, c):
    c.post("/add/links", data={"title": "DevOps", "links": LINKS})
    course = v.courses()[0]
    r = c.post(f"/courses/{course.id}/start", follow_redirects=False)
    return course, r.headers["location"].rsplit("/", 1)[-1]


# ---- finding the course's videos ------------------------------------------------------------------------------
def test_course_videos_are_listed_once(tmp_path):
    v, c = app(tmp_path)
    course, _ = course_with_videos(v, c)
    items = offline.course_videos(course)
    assert [i["id"] for i in items] == ["PrusdhS2lmo", "X48VuDVv0do", "qiQR5rTSshw"]
    assert len(items[0]["lessons"]) == 3  # three lessons cut from the same long video
    st = offline.status(v, course)
    assert (st["have"], st["total"]) == (0, 3)


# ---- matching names that are a bit different ------------------------------------------------------------------
def test_names_that_are_alike():
    assert offline.normalize("الدَّرسُ الأوّل: مقدمة") == offline.normalize("الدرس الاول مقدمه")
    assert offline.text_score("03 - Data Analytcs for Beginners (1080p)", "Data analytics for beginners") > 0.8
    assert offline.text_score("Kubernetes_Basics_FULL_COURSE", "Kubernetes basics") > 0.8
    assert offline.text_score("الحاويات من الصفر", "حاويات من الصفر") > 0.9
    assert offline.text_score("Cooking pasta at home", "Kubernetes basics") < 0.3
    assert offline._number("Lesson 7 - Pods") == 7 and offline._number("٠٤ - مقدمة") == 4
    assert offline._number("Kubernetes basics") is None


def test_match_pairs_each_file_once(tmp_path):
    names = ["01 - Intro to containers [720p].mp4", "2. Kubernetes Basics - full course.mkv",
             "networking 4 beginers.mp4", "random holiday clip.mp4", "Lesson 4 something else.mp4"]
    files = []
    for n in names:
        (tmp_path / n).write_bytes(b"x")
        files.append(tmp_path / n)
    targets = [
        {"key": "a", "id": "aaaaaaaaaaa", "names": ["Intro to containers"], "index": 1},
        {"key": "b", "id": "bbbbbbbbbbb", "names": ["Kubernetes basics"], "index": 2},
        {"key": "c", "id": "ccccccccccc", "names": ["Networking for beginners"], "index": 3},
        {"key": "d", "id": "ddddddddddd", "names": ["Linux shell scripting"], "index": 5},
    ]
    rows = {r["key"]: r for r in offline.match(targets, files, seconds=lambda f: 0)}
    assert rows["a"]["file"].name == names[0] and rows["a"]["sure"] == "yes"
    assert rows["b"]["file"].name == names[1]
    assert rows["c"]["file"].name == names[2]  # a typo in the file name
    assert rows["d"]["file"] is None and rows["d"]["sure"] == "no"
    used = [r["file"] for r in rows.values() if r["file"]]
    assert len(used) == len(set(used))


def test_youtube_id_and_length_decide(tmp_path):
    a, b = tmp_path / "video one [X48VuDVv0do].mp4", tmp_path / "clip.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    t = [{"key": "k", "id": "X48VuDVv0do", "names": ["Something unrelated"], "index": 1}]
    assert offline.match(t, [b, a], seconds=lambda f: 0)[0]["file"] == a
    # Same-looking names: the one with the right length wins.
    c1, c2 = tmp_path / "Pods part.mp4", tmp_path / "Pods part (old).mp4"
    c1.write_bytes(b"x")
    c2.write_bytes(b"x")
    lengths = {c1: 600.0, c2: 1500.0}
    t = [{"key": "k", "id": "", "names": ["Pods part"], "index": 1, "seconds": 1498}]
    row = offline.match(t, [c1, c2], seconds=lambda f: lengths[f])[0]
    assert row["file"] == c2 and "length" in row["why"]


def test_mp4_length_is_read_from_the_header(tmp_path):
    p = tmp_path / "v.mp4"
    p.write_bytes(mp4(125.5))
    assert abs(offline.mp4_seconds(p) - 125.5) < 0.01
    (tmp_path / "bad.mp4").write_bytes(b"not a video")
    assert offline.mp4_seconds(tmp_path / "bad.mp4") == 0.0


# ---- getting and updating yt-dlp ------------------------------------------------------------------------------
def fake_tool(ver: str, module: str = "") -> bytes:
    """A stand-in for the yt-dlp file: a zip app, built like the real one (the first line, then the zip,
    with the zip's own offsets counted from the start of the file)."""
    buf = io.BytesIO()
    buf.write(b"#!/usr/bin/env python3\n")
    with zipfile.ZipFile(buf, "a") as z:
        z.writestr("yt_dlp/__init__.py", module or "class YoutubeDL: pass\n")
        z.writestr("yt_dlp/version.py", f"__version__ = '{ver}'\n")
    return buf.getvalue()


def wait_for(course_id: str, seconds: float = 30) -> dict:
    """Wait for a background download to finish (CI machines can be slow)."""
    end = time.time() + seconds
    while time.time() < end:
        job = offline.JOBS.get(course_id) or {}
        if job.get("state") != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("the download didn't finish in time")


def fetcher(data: bytes, wrong_sum: bool = False):
    def fetch(url, timeout=0):
        if url.endswith("SHA2-256SUMS"):
            h = hashlib.sha256(b"other" if wrong_sum else data).hexdigest()
            return f"{'0' * 64}  yt-dlp.exe\n{h}  yt-dlp\n".encode()
        return data
    return fetch


def test_tool_is_checked_and_updated(tmp_path):
    with pytest.raises(offline.ToolProblem):
        offline.update_tool(tmp_path, fetcher(fake_tool("2026.01.01"), wrong_sum=True))
    assert not offline.tool_path(tmp_path).exists()
    assert offline.update_tool(tmp_path, fetcher(fake_tool("2026.01.01"))) == (True, "2026.01.01")
    assert offline.update_tool(tmp_path, fetcher(fake_tool("2026.01.01"))) == (False, "2026.01.01")  # same copy
    assert offline.update_tool(tmp_path, fetcher(fake_tool("2026.02.02"))) == (True, "2026.02.02")
    assert offline.version(tmp_path) == "2026.02.02"


def test_settings_page_and_choices(tmp_path, monkeypatch):
    monkeypatch.setattr(offline, "version", lambda home: "")  # as on a computer without yt-dlp installed in Python
    v, c = app(tmp_path)
    page = html.unescape(c.get("/settings").text)
    assert "Video downloads" in page and "Get yt-dlp now" in page
    c.post("/settings/videos", data={"updates": "manual", "quality": "480"})
    assert v._meta("ytdlp_updates") == "manual" and v._meta("ytdlp_quality") == "480"
    c.post("/settings/videos", data={"updates": "sometimes", "quality": "9999"})
    assert v._meta("ytdlp_updates") == "manual" and v._meta("ytdlp_quality") == "480"


def test_auto_update_only_when_chosen_and_once_a_day(tmp_path, monkeypatch):
    v = Vault(tmp_path / "me")
    calls = []
    monkeypatch.setattr(offline, "update_tool", lambda home, fetch=None: calls.append(1) or (False, "x"))
    offline.auto_update(v)
    assert calls == []  # no tool yet: nothing to update
    offline.tool_path(v.home).parent.mkdir(parents=True)
    offline.tool_path(v.home).write_bytes(fake_tool("1"))
    offline.auto_update(v)
    offline.auto_update(v)  # again the same day: no second check
    assert calls == [1]
    v._set_meta("ytdlp_checked", "0")
    v._set_meta("ytdlp_updates", "manual")
    offline.auto_update(v)
    assert calls == [1]


# ---- downloading a course (with a stand-in yt-dlp) ------------------------------------------------------------
FAKE_YTDLP = '''
import os
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


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A pretend home folder, so downloads never land in the real Downloads folder."""
    h = tmp_path / "home"
    (h / "Downloads").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(h / ".config"))
    monkeypatch.delenv("INPACE_MOBILE", raising=False)
    return h


def test_download_a_course(tmp_path, home, monkeypatch):
    monkeypatch.setattr(offline, "free_space", lambda folder: 500 * 1024 ** 3)  # plenty, whatever the machine has
    v, c = app(tmp_path)
    course, jid = course_with_videos(v, c)
    offline.tool_path(v.home).parent.mkdir(parents=True)
    offline.tool_path(v.home).write_bytes(fake_tool("2026.03.03", FAKE_YTDLP))
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert "Watch offline" in page and "0 of 3 videos on this computer" in page
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert '<option value="1080"' in page and "Best available" in page
    c.post(f"/courses/{course.id}/offline/download", data={"quality": "480"})
    assert offline.JOBS[course.id]["quality"] == "480" and v._meta(f"ytdlp_quality:{course.id}") == "480"
    wait_for(course.id)
    st = c.get(f"/courses/{course.id}/offline/status").json()
    assert st["job"]["state"] == "partly" and st["have"] == 2 and st["total"] == 3
    assert "Video unavailable" in st["job"]["failed"][0]["why"]
    p = offline.local_file(v, course.id, "PrusdhS2lmo")
    # By default: the Downloads folder, in inPace/<course name>
    assert p and p.parent == home / "Downloads" / "inPace" / "DevOps" and "[PrusdhS2lmo]" in p.name
    assert offline.video_info(v, "PrusdhS2lmo")["title"] == "Title of PrusdhS2lmo"
    # Delete the downloads: lessons go back to YouTube.
    c.post(f"/courses/{course.id}/offline/forget", data={"delete": "1"})
    assert not p.exists() and not offline.local_file(v, course.id, "PrusdhS2lmo")
    assert not (home / "Downloads" / "inPace" / "DevOps").exists()  # the empty course folder goes too
    offline.JOBS.clear()


# ---- lessons play the copy on this computer -------------------------------------------------------------------
def test_lesson_plays_the_local_piece(tmp_path):
    v, c = app(tmp_path)
    course, jid = course_with_videos(v, c)
    f = tmp_path / "docker.mp4"
    f.write_bytes(mp4(4000))
    offline.set_local_file(v, course.id, "PrusdhS2lmo", f)
    lesson = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l2").text)
    assert f'src="/yt/{course.id}/PrusdhS2lmo#t=1189,3014"' in lesson
    assert 'data-start="1189"' in lesson and 'data-end="3014"' in lesson and "data-player" in lesson
    assert "Playing the copy on this computer." in lesson and "youtube-nocookie" not in lesson
    # The same saved place as on YouTube
    key = f"{course.id}|yt:PrusdhS2lmo:1189-3014"
    assert f'data-key="{key}"' in lesson
    c.post("/media-pos", data={"key": key, "t": "1500", "d": "3014"})
    assert 'data-resume="1500.0"' in c.get(f"/learn/{jid}/lesson/m1-l2").text
    r = c.get(f"/yt/{course.id}/PrusdhS2lmo")
    assert r.status_code == 200 and r.content == f.read_bytes()
    assert c.get(f"/yt/{course.id}/X48VuDVv0do").status_code == 404
    # Without a copy it plays from YouTube again, from the same saved place
    offline.set_local_file(v, course.id, "PrusdhS2lmo", None)
    again = c.get(f"/learn/{jid}/lesson/m1-l2").text
    assert "youtube-nocookie" in again and 'data-resume="1500.0"' in again
    # The file was deleted by hand: it falls back to YouTube instead of a broken player
    offline.set_local_file(v, course.id, "PrusdhS2lmo", f)
    f.unlink()
    assert "youtube-nocookie" in c.get(f"/learn/{jid}/lesson/m1-l2").text


def test_match_my_own_folder(tmp_path):
    v, c = app(tmp_path)
    course, jid = course_with_videos(v, c)
    folder = tmp_path / "My Videos"
    (folder / "k8s").mkdir(parents=True)
    (folder / "Docker and Kubernetes full course.mp4").write_bytes(b"x")
    (folder / "k8s" / "02_kubernetes-basics.mp4").write_bytes(b"x")
    (folder / "notes.txt").write_text("not a video")
    r = c.post(f"/courses/{course.id}/offline/match", data={"folder": str(folder)})
    page = html.unescape(r.text)
    assert "Match your videos" in page
    k8s = re.search(r'<select name="file:X48VuDVv0do".*?</select>', page, re.S).group(0)
    assert re.search(r'<option value="[^"]*02_kubernetes-basics\.mp4" selected>', k8s)
    net = re.search(r'<select name="file:qiQR5rTSshw".*?</select>', page, re.S).group(0)
    assert " selected" not in net
    # Save what the person checked (they fixed the Docker one by hand)
    c.post(f"/courses/{course.id}/offline/save", data={
        "folder": str(folder),
        "file:PrusdhS2lmo": str(folder / "Docker and Kubernetes full course.mp4"),
        "file:X48VuDVv0do": str(folder / "k8s" / "02_kubernetes-basics.mp4"),
        "file:qiQR5rTSshw": "",
        "file:notacourseid": str(folder / "notes.txt"),
    })
    assert offline.local_file(v, course.id, "X48VuDVv0do").name == "02_kubernetes-basics.mp4"
    assert offline.local_file(v, course.id, "PrusdhS2lmo")
    assert offline.status(v, course)["have"] == 2
    # A file outside the searched folder is refused
    outside = tmp_path / "secret.mp4"
    outside.write_bytes(b"x")
    c.post(f"/courses/{course.id}/offline/save", data={"folder": str(folder), "file:qiQR5rTSshw": str(outside)})
    assert not offline.local_file(v, course.id, "qiQR5rTSshw")
    # "Play from YouTube again" forgets the files but never deletes them
    c.post(f"/courses/{course.id}/offline/forget")
    assert (folder / "k8s" / "02_kubernetes-basics.mp4").exists()
    assert offline.status(v, course)["have"] == 0
    # A folder that doesn't exist, or has no videos
    r = c.post(f"/courses/{course.id}/offline/match", data={"folder": str(tmp_path / "nope")})
    assert "That folder wasn" in html.unescape(r.text)


def test_a_file_linked_before_is_kept(tmp_path):
    v, c = app(tmp_path)
    course, _ = course_with_videos(v, c)
    mine = tmp_path / "elsewhere.mp4"
    mine.write_bytes(b"x")
    offline.set_local_file(v, course.id, "PrusdhS2lmo", mine)
    folder = tmp_path / "f"
    folder.mkdir()
    (folder / "kubernetes basics.mp4").write_bytes(b"x")
    page = html.unescape(c.post(f"/courses/{course.id}/offline/match", data={"folder": str(folder)}).text)
    assert "Keep the current file" in page and "Lessons from this video: Introduction to Containers" in page
    c.post(f"/courses/{course.id}/offline/save", data={"folder": str(folder), "file:PrusdhS2lmo": "keep",
                                                      "file:X48VuDVv0do": str(folder / "kubernetes basics.mp4")})
    assert offline.local_file(v, course.id, "PrusdhS2lmo") == mine
    assert offline.status(v, course)["have"] == 2


def test_an_update_is_used_without_restarting(tmp_path):
    import sys
    offline.update_tool(tmp_path, fetcher(fake_tool("1", "WHICH = 'old'\n")))
    assert offline.load(tmp_path).WHICH == "old"
    offline.update_tool(tmp_path, fetcher(fake_tool("2", "WHICH = 'new, and longer than before'\n")))
    assert offline.load(tmp_path).WHICH == "new, and longer than before"


def test_quality_choices_make_valid_formats(monkeypatch):
    for ff in (True, False):
        monkeypatch.setattr(offline.shutil, "which", lambda n, ff=ff: "/bin/ffmpeg" if ff and n == "ffmpeg" else None)
        for q in offline.QUALITIES:
            fmt, merge = offline._format(q)
            assert fmt and merge == ff
            assert ("height<=" not in fmt) == (q == "best")


def test_where_videos_are_saved(tmp_path, home, monkeypatch):
    v, c = app(tmp_path)
    course, jid = course_with_videos(v, c)
    assert offline.download_folder(v, course) == home / "Downloads" / "inPace" / "DevOps"  # the default
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert str(home / "Downloads" / "inPace" / "DevOps") in page
    # This course only: another folder and another folder name
    other = tmp_path / "Courses"
    other.mkdir()
    c.post(f"/courses/{course.id}/offline/folder", data={"base": str(other), "name": "Docker: K8s?"})
    assert offline.download_folder(v, course) == other / "Docker K8s"
    c.post(f"/courses/{course.id}/offline/folder", data={"base": str(tmp_path / "missing"), "name": ""})
    assert offline.download_folder(v, course) == other / "Docker K8s"  # a missing folder is refused
    c.post(f"/courses/{course.id}/offline/folder", data={"base": "", "name": ""})
    assert offline.download_folder(v, course) == home / "Downloads" / "inPace" / "DevOps"
    # Settings: Videos, inPace's own folder, or any folder
    c.post("/settings/videos", data={"folder": "videos"})
    assert offline.download_folder(v, course).parent.parent.name in ("Videos", "Movies")
    c.post("/settings/videos", data={"folder": "inpace"})
    assert offline.download_folder(v, course) == v.media_dir(course.id) / "videos"
    c.post("/settings/videos", data={"folder": "custom", "folder_path": str(other)})
    assert offline.download_folder(v, course) == other / "DevOps"
    c.post("/settings/videos", data={"folder": "custom", "folder_path": str(tmp_path / "nope")})
    assert v._meta("ytdlp_folder_path") == str(other)
    # On Android: the phone's Download folder
    monkeypatch.setenv("INPACE_MOBILE", "android")
    monkeypatch.setenv("INPACE_STORAGE", "/storage/emulated/0")
    c.post("/settings/videos", data={"folder": "downloads"})
    assert offline.download_folder(v, course) == Path("/storage/emulated/0/Download/inPace/DevOps")


def test_unwritable_folder_falls_back_and_says_so(tmp_path, home, monkeypatch):
    monkeypatch.setattr(offline, "free_space", lambda folder: 500 * 1024 ** 3)
    v, c = app(tmp_path)
    course, jid = course_with_videos(v, c)
    offline.tool_path(v.home).parent.mkdir(parents=True)
    offline.tool_path(v.home).write_bytes(fake_tool("2026.03.03", FAKE_YTDLP))
    monkeypatch.setattr(offline, "_writable", lambda folder: False)
    c.post(f"/courses/{course.id}/offline/download")
    wait_for(course.id)
    assert offline.local_file(v, course.id, "X48VuDVv0do").parent == v.media_dir(course.id) / "videos"
    assert "couldn't save to" in html.unescape(c.get(f"/learn/{jid}").text)
    offline.JOBS.clear()


def test_delete_never_touches_your_own_files(tmp_path, home):
    v, c = app(tmp_path)
    course, _ = course_with_videos(v, c)
    mine = home / "Downloads" / "my own copy.mp4"
    mine.write_bytes(b"x")
    offline.set_local_file(v, course.id, "X48VuDVv0do", mine)  # matched, not downloaded by inPace
    c.post(f"/courses/{course.id}/offline/forget", data={"delete": "1"})
    assert mine.exists()


def test_space_is_checked_before_downloading(tmp_path, home, monkeypatch):
    v, c = app(tmp_path)
    course, jid = course_with_videos(v, c)
    need = offline.space_needed(v, course)
    assert need["1080"] > need["720"] > need["360"] > 0
    monkeypatch.setattr(offline, "free_space", lambda folder: 500 * 1024 ** 3)
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert "free where the videos are saved" in page and "Not enough space." not in page
    monkeypatch.setattr(offline, "free_space", lambda folder: 50 * 1024 * 1024)  # 50 MB left
    page = html.unescape(c.get(f"/learn/{jid}").text)
    assert "Not enough space." in page and "Download anyway" in page
    r = c.post(f"/courses/{course.id}/offline/download", data={"quality": "720"})
    assert "Not enough space: these videos need about" in html.unescape(r.text)
    assert course.id not in offline.JOBS


def test_download_stops_when_the_disk_fills(tmp_path, home, monkeypatch):
    v, c = app(tmp_path)
    course, jid = course_with_videos(v, c)
    offline.tool_path(v.home).parent.mkdir(parents=True)
    offline.tool_path(v.home).write_bytes(fake_tool("2026.03.03", FAKE_YTDLP))
    monkeypatch.setattr(offline, "free_space", lambda folder: 10 * 1024 * 1024)
    c.post(f"/courses/{course.id}/offline/download", data={"anyway": "1"})
    wait_for(course.id)
    job = offline.JOBS[course.id]
    assert job["state"] == "failed" and "almost full" in job["error"]
    assert offline.status(v, course)["have"] == 0
    offline.JOBS.clear()


def test_backup_leaves_out_videos_and_the_downloader(tmp_path):
    from inpace import pace
    v, c = app(tmp_path)
    (v.home / "tools").mkdir()
    (v.home / "tools" / "yt-dlp.zip").write_bytes(b"x")
    (v.media_dir("c1") / "videos").mkdir(parents=True)
    (v.media_dir("c1") / "videos" / "big [abc].mp4").write_bytes(b"x")
    (v.media_dir("c1") / "notes.pdf").write_bytes(b"%PDF")
    names = pace.open_backup(pace.make_backup(v, "secret1"), "secret1").namelist()
    assert "media/c1/notes.pdf" in names
    assert not any(n.startswith("tools/") or "/videos/" in n for n in names)
