"""v1.30.14: the Downloads page (progress, waiting, failed, retry, how many at once, speed limit) and progress for
courses downloaded from the library."""
import hashlib
import html
import io

from inpace import library, offline
from tests.test_v119 import FAKE_YTDLP, app, course_with_videos, fake_tool, home, wait_for  # noqa: F401


def test_downloads_page_and_settings(tmp_path, home):
    v, c = app(tmp_path)
    page = html.unescape(c.get("/downloads").text)
    assert "Videos at the same time" in page and 'href="/downloads"' in page and "No videos saved yet" in page
    c.post("/downloads/settings", data={"parallel": "4", "rate": "2m", "quality": "480"})
    assert v._meta("dl_parallel") == "4" and v._meta("dl_rate") == "2m" and v._meta("ytdlp_quality") == "480"
    assert offline.SETTINGS["parallel"] == 4 and offline.SETTINGS["rate"] == 2 * 1024 ** 2
    c.post("/downloads/settings", data={"parallel": "9", "rate": "fast"})  # not a choice: unchanged
    assert offline.SETTINGS["parallel"] == 4
    c.post("/downloads/settings", data={"parallel": "2", "rate": "0"})


def test_videos_download_side_by_side_and_failed_ones_can_be_retried(tmp_path, home, monkeypatch):
    monkeypatch.setattr(offline, "free_space", lambda folder: 500 * 1024 ** 3)
    v, c = app(tmp_path)
    course, jid = course_with_videos(v, c)
    offline.tool_path(v.home).parent.mkdir(parents=True)
    offline.tool_path(v.home).write_bytes(fake_tool("2026.03.03", FAKE_YTDLP))
    c.post("/downloads/settings", data={"parallel": "3"})
    c.post(f"/courses/{course.id}/offline/download", data={"quality": "720"})
    job = wait_for(course.id)
    assert job["state"] == "partly" and [f["id"] for f in job["failed"]] == ["qiQR5rTSshw"]
    d = c.get("/downloads.json").json()
    cd = next(x for x in d["courses"] if x["course"] == course.id)
    assert cd["failed"][0]["why"] and len(cd["completed"]) == job["saved"] >= 2 and not d["running"]
    assert html.unescape(c.get("/downloads").text).count(f"/downloads/delete/{course.id}") == 1  # on this device now
    c.post("/downloads/retry", data={"course": course.id, "video": "qiQR5rTSshw"})
    job = wait_for(course.id)
    assert job["failed"][0]["id"] == "qiQR5rTSshw"  # still unavailable, and listed again
    c.post("/downloads/clear")
    assert course.id not in offline.JOBS
    c.post("/downloads/settings", data={"parallel": "2"})


def test_cancel_and_download_next_change_a_running_list(tmp_path, home):
    v, c = app(tmp_path)
    course, jid = course_with_videos(v, c)
    job = {"state": "running", "queue": ["a", "b", "c"], "pending": [], "active": {}, "failed": [], "titles": {}}
    offline.JOBS[course.id] = job
    c.post("/downloads/cancel", data={"course": course.id, "video": "b"})
    c.post("/downloads/next", data={"course": course.id, "video": "c"})
    assert "b" in job["skip"] and job["first"] == ["c"]
    o = offline.overview()
    assert [w["id"] for w in o["courses"][0]["waiting_list"]] == ["a", "c"]
    job["state"] = "done"


def test_a_library_course_reports_its_progress(monkeypatch):
    data = b"x" * 300_000

    class R(io.BytesIO):
        headers = {"Content-Length": str(len(data))}
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(library, "_get", lambda url, timeout=0: R(data))
    entry = {"pack": library.SITE + "x.zip", "sha256": hashlib.sha256(data).hexdigest(), "title": "FastAPI"}
    assert library.download_tracked(entry, "tok", 1, 2) == data
    x = library.PROGRESS["tok"]
    assert x["got"] == x["size"] == len(data) and x["title"] == "FastAPI" and x["of"] == 2
    library.PROGRESS.clear()


def test_backup_leaves_out_the_cache_and_half_written_files(tmp_path):
    """The Windows test machine: a template being saved in the background was locked and broke the backup."""
    from inpace import pace
    v, c = app(tmp_path)
    (v.home / "cache" / "templates").mkdir(parents=True, exist_ok=True)
    (v.home / "cache" / "templates" / "x.cachej3b9udnt.tmp").write_bytes(b"half")
    (v.home / "notes.part").write_bytes(b"half")
    z = pace.open_backup(pace.make_backup(v, "longpassword"), "longpassword")
    names = z.namelist()
    assert "vault.db" in names and not any(n.startswith("cache/") or n.endswith((".tmp", ".part")) for n in names)


def test_missing_ytdlp_is_explained_and_fetched_first(tmp_path, home, monkeypatch):
    """v1.30.17: no yt-dlp yet: inPace gets it before downloading, even while that download is running, and
    when it can't, it says what yt-dlp is and what to do."""
    import sys
    monkeypatch.setattr(offline, "load", lambda h: None if not offline.tool_path(h).is_file() else sys)

    def offline_net(url, timeout=0):
        raise OSError("Network is unreachable")
    try:
        offline.ensure_tool(tmp_path, offline_net)
        raise AssertionError("it should have failed")
    except offline.ToolProblem as e:
        assert str(e).startswith(offline.NEED_TOOL) and "internet" in str(e)
    # a download running (this one) doesn't block getting it the first time
    offline.JOBS["x"] = {"state": "running"}
    data = fake_tool("2026.05.05")
    fetch = lambda url, timeout=0: (f"{hashlib.sha256(data).hexdigest()}  yt-dlp\n".encode() if url.endswith("SUMS") else data)
    assert offline.ensure_tool(tmp_path, fetch) is sys and offline.tool_path(tmp_path).is_file()
    offline.JOBS.clear()
    monkeypatch.setattr(offline, "version", lambda h: "")
    v, c = app(tmp_path / "app")
    page = html.unescape(c.get("/downloads").text)
    assert "isn't on this device yet" in page and "Get yt-dlp now" in page
