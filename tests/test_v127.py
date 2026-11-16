"""v1.27: lessons that play part of a long video say so (and get a bar for just that part), your own subtitle
files, and a clear way out when a video can't play in the app window."""
import html
import re

from inpace import media
from inpace.course import VIDEO_EXT, media_kind
from tests.test_app import client
from tests.test_media import make_folder
from tests.test_v118 import LINKS


def test_srt_becomes_vtt_in_any_encoding(tmp_path):
    srt = "1\r\n00:00:01,000 --> 00:00:02,500\r\nمرحبا\r\n".encode("cp1256")
    vtt = media.srt_to_vtt(srt)
    assert vtt.startswith("WEBVTT") and "00:00:01.000 --> 00:00:02.500" in vtt and "مرحبا" in vtt
    assert media.srt_to_vtt("WEBVTT\n\n00:01.000 --> 00:02.000\nhi".encode()).startswith("WEBVTT\n\n00:01.000")
    assert "Hello" in media.srt_to_vtt("﻿1\n00:00:01,000 --> 00:00:02,000\nHello".encode("utf-8"))


def test_subtitles_next_to_a_video_are_found(tmp_path):
    v = tmp_path / "01 - Welcome.mp4"
    v.write_bytes(b"x")
    for name in ("01 - Welcome.srt", "01 - Welcome.ar.srt", "01 - Welcome.English.vtt", "01 - Welcome 2.srt", "other.srt"):
        (tmp_path / name).write_text("1\n00:00:01,000 --> 00:00:02,000\nx")
    found = {(label, lang) for label, lang, _ in media.sibling_subs(v)}
    assert found == {("Subtitles", ""), ("العربية", "ar"), ("English", "en")}


def _folder_lesson(tmp_path):
    v, c = client(tmp_path, "Omar")
    folder = make_folder(tmp_path / "Downloads" / "Big course")
    (folder / "01 Intro" / "01 - Welcome.ar.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nأهلا", encoding="utf-8")
    c.post("/courses/from-folder", data={"folder": str(folder)})
    course = v.courses()[0]
    c.post(f"/courses/{course.id}/start")
    jid = v.journeys()[0]["id"]
    return v, c, course, jid


def test_lesson_video_has_subtitles_and_you_can_add_your_own(tmp_path):
    v, c, course, jid = _folder_lesson(tmp_path)
    page = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l1").text)
    tr = re.search(r'<track kind="subtitles" src="([^"]+)" label="العربية" srclang="ar">', page)
    assert tr, "the .ar.srt next to the video is offered"
    got = c.get(tr.group(1))
    assert got.status_code == 200 and got.headers["content-type"].startswith("text/vtt") and "أهلا" in got.text
    assert 'data-sub-action="/courses/' in page and 'data-media="01 Intro/01 - Welcome.mp4"' in page
    # Add your own file: kept by inPace, offered next time.
    srt = b"1\n00:00:03,000 --> 00:00:04,000\nMy own words\n"
    r = c.post(f"/courses/{course.id}/subs/add", data={"media": "01 Intro/01 - Welcome.mp4"},
               files={"file": ("Mine.srt", srt)}, headers={"X-Inpace-Fetch": "1"})
    assert r.json() == {"ok": True}
    page = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l1").text)
    mine = re.search(r'<track kind="subtitles" src="([^"]+)" label="Mine">', page)
    assert mine and "00:00:03.000 --> 00:00:04.000" in c.get(mine.group(1)).text
    # Not a subtitle file, or a video that isn't in the course: refused.
    bad = c.post(f"/courses/{course.id}/subs/add", data={"media": "01 Intro/01 - Welcome.mp4"},
                 files={"file": ("x.srt", b"hello")}, headers={"X-Inpace-Fetch": "1"})
    assert bad.status_code == 400
    bad = c.post(f"/courses/{course.id}/subs/add", data={"media": "../../etc/passwd.mp4"},
                 files={"file": ("x.srt", srt)}, headers={"X-Inpace-Fetch": "1"})
    assert bad.status_code == 400
    assert c.get(f"/courses/{course.id}/subs?media=x&f=../../a.vtt&u=1").status_code == 404


def test_open_in_your_player(tmp_path, monkeypatch):
    v, c, course, jid = _folder_lesson(tmp_path)
    opened = []
    import inpace.app as app_mod
    monkeypatch.setattr(app_mod.subprocess, "Popen", lambda args, **k: opened.append(args))
    monkeypatch.setattr(app_mod.os, "startfile", lambda p: opened.append([p]), raising=False)
    page = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l1").text)
    assert 'data-open-action="/courses/' in page and 'data-ext="mp4"' in page
    assert "This video can't play here." in page  # the help is ready in case it's needed
    r = c.post(f"/courses/{course.id}/open-media", data={"media": "01 Intro/01 - Welcome.mp4"})
    assert r.json() == {"ok": True} and opened and str(opened[0][-1]).endswith("01 - Welcome.mp4")
    assert c.post(f"/courses/{course.id}/open-media", data={"media": "nope.mp4"}).status_code == 404


def test_more_video_formats_are_lessons():
    for ext in (".avi", ".wmv", ".mkv", ".mpg"):
        assert ext in VIDEO_EXT and media_kind("x" + ext) == "video"
    assert media_kind("x.ts") == "code"  # TypeScript, not a video


def test_youtube_parts_are_labelled_and_marked(tmp_path):
    from tests.test_v118 import app
    v, c = app(tmp_path)
    c.post("/add/links", data={"title": "Docker", "links": LINKS})
    course = v.courses()[0]
    r = c.post(f"/courses/{course.id}/start", follow_redirects=False)
    jid = r.headers["location"].rsplit("/", 1)[-1]
    lesson = html.unescape(c.get(f"/learn/{jid}/lesson/m1-l3").text)
    assert "Part 3 of 3" in lesson and "Plays from 50:14 to the end of the full video." in lesson
    assert "Watch the full video" in lesson and 'data-l-piece="This part"' in lesson
    trail = html.unescape(c.get(f"/learn/{jid}").text)
    assert "part 1/3" in trail and "part 3/3" in trail
    # A plain lesson with no piece has no label.
    assert "Part of a longer video" not in html.unescape(c.get(f"/learn/{jid}/lesson/m2-l1").text)
