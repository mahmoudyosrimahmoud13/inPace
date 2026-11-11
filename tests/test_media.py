"""Media in lessons: folders of videos that stay where they are, moving them, online videos, packs with files."""
import html
import io
import shutil
import zipfile

from inpace.course import course_from_folder, load_course, media_kind
from tests.test_app import client


def make_folder(root):
    (root / "01 Intro").mkdir(parents=True)
    (root / "02 Going further").mkdir()
    (root / "01 Intro" / "01 - Welcome.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"v" * 5000)
    (root / "01 Intro" / "02_setup_guide.mp3").write_bytes(b"ID3" + b"a" * 100)
    (root / "02 Going further" / "sim.html").write_text("<script>document.write('hi')</script>")
    (root / "02 Going further" / "10 notes.md").write_text("# Notes\n\nRead me.")
    (root / "02 Going further" / "2 slides.pdf").write_bytes(b"%PDF-1.4")
    return root


def test_folder_becomes_course(tmp_path):
    c = course_from_folder(make_folder(tmp_path / "Python Pro Course"))
    assert c.title == "Python Pro Course"
    assert [m["title"] for m in c.modules] == ["Intro", "Going further"]
    titles = [les["title"] for les in c.modules[0]["lessons"]]
    assert titles == ["Welcome", "setup guide"]
    m2 = [les["title"] for les in c.modules[1]["lessons"]]
    assert m2 == ["slides", "Notes", "sim"]  # natural order: 2 before 10
    assert c.extra["media_index"]["01 Intro/01 - Welcome.mp4"] > 5000


def test_folder_course_plays_moves_and_is_found_again(tmp_path):
    v, c = client(tmp_path, "Omar")
    folder = make_folder(tmp_path / "Downloads" / "Big course")
    r = c.post("/courses/from-folder", data={"folder": str(folder)})
    assert "files stay where they are" in html.unescape(r.text)
    course = v.courses()[0]
    c.post(f"/courses/{course.id}/start")
    jid = v.journeys()[0]["id"]
    r = c.get(f"/learn/{jid}/lesson/m1-l1")
    assert '<video controls' in r.text and f'src="/m/{course.id}/01%20Intro/01%20-%20Welcome.mp4"' in r.text
    # Served from where it lives, with seeking (range requests).
    got = c.get(f"/m/{course.id}/01%20Intro/01%20-%20Welcome.mp4", headers={"Range": "bytes=0-9"})
    assert got.status_code == 206 and got.content == b"\x00\x00\x00\x18ftypmp"
    # Web pages run sealed off.
    page = c.get(f"/m/{course.id}/02%20Going%20further/sim.html")
    assert "sandbox allow-scripts" in page.headers["content-security-policy"]
    assert "connect-src 'none'" in page.headers["content-security-policy"]
    # Can't wander outside the folder.
    assert c.get(f"/m/{course.id}/..%2F..%2Fsecret.mp4").status_code == 404
    # Move the folder: inPace asks where it went.
    moved = tmp_path / "Videos" / "Renamed course"
    moved.parent.mkdir()
    shutil.move(str(folder), str(moved))
    r = c.get(f"/learn/{jid}/lesson/m1-l1")
    assert "can not find this file" in html.unescape(r.text) and "data-pick-folder" in r.text
    assert "Where are this course" in html.unescape(c.get(f"/learn/{jid}").text)
    r = c.post(f"/courses/{course.id}/media-folder", data={"folder": str(moved)},
               headers={"referer": f"http://testserver/learn/{jid}"})
    assert "Found all the course files" in html.unescape(r.text)
    assert '<video controls' in c.get(f"/learn/{jid}/lesson/m1-l1").text


def test_old_full_paths_are_found_in_a_new_folder(tmp_path):
    v, c = client(tmp_path, "Omar")
    old = tmp_path / "old" / "Course"
    (old / "Week 1").mkdir(parents=True)
    (old / "Week 1" / "talk.mp4").write_bytes(b"video")
    yaml_text = f"""title: Talks
modules:
  - title: Week 1
    lessons:
      - title: The talk
        media: {(old / 'Week 1' / 'talk.mp4').as_posix()}
"""
    r = c.post("/open", files={"file": ("talks.yaml", yaml_text.encode())})
    course = v.courses()[0]
    assert v.find_media(course.id, course.modules[0]["lessons"][0]["media"])
    new = tmp_path / "new place"
    shutil.move(str(old), str(new))
    assert not v.find_media(course.id, course.modules[0]["lessons"][0]["media"])
    v.set_media_root(course.id, str(new))
    assert v.find_media(course.id, course.modules[0]["lessons"][0]["media"]).read_bytes() == b"video"


def test_online_videos_wait_for_play(tmp_path):
    v, c = client(tmp_path, "Omar")
    text = """title: Watch
modules:
  - title: One
    lessons:
      - title: Videos
        content: |
          Watch this:

          ![The talk](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

          https://vimeo.com/76979871

          [A normal link](https://example.com)
      - title: Just a video
        media: https://youtu.be/dQw4w9WgXcQ
"""
    c.post("/open", files={"file": ("w.yaml", text.encode())})
    course = v.courses()[0]
    c.post(f"/courses/{course.id}/start")
    jid = v.journeys()[0]["id"]
    r = c.get(f"/learn/{jid}/lesson/m1-l1").text
    assert 'data-embed="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ' in r
    assert 'data-embed="https://player.vimeo.com/video/76979871' in r
    assert "<iframe" not in r.split('class="prose"')[1]  # nothing loads from the internet before play
    assert 'href="https://example.com" target="_blank"' in r
    assert "youtube-nocookie" in c.get(f"/learn/{jid}/lesson/m1-l2").text


def test_pack_with_files_travels(tmp_path):
    av, a = client(tmp_path, "Omar")
    bv, b = client(tmp_path, "Sara")
    folder = make_folder(tmp_path / "Course")
    a.post("/courses/from-folder", data={"folder": str(folder)})
    course = av.courses()[0]
    pack = a.get(f"/courses/{course.id}/export?files=1")
    assert pack.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(pack.content)).namelist()
    assert "files/01 Intro/01 - Welcome.mp4" in names and "course.yaml" in names
    r = b.post("/open", files={"file": ("c.lpack", pack.content)})
    assert "Added the course" in html.unescape(r.text)
    got = bv.find_media(course.id, "01 Intro/01 - Welcome.mp4")
    assert got and got.read_bytes().startswith(b"\x00\x00\x00\x18ftyp")
    # Without files, the other person is told to choose the folder.
    plain = a.get(f"/courses/{course.id}/export").content
    cv, cc = client(tmp_path, "Lina")
    r = cc.post("/open", files={"file": ("c.lpack", plain)})
    assert "Choose their folder" in html.unescape(r.text)


def test_editor_adds_media(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/edit/new", data={"title": "Cooking", "module_title": "Basics", "lesson_title": "Knives", "content": "Hold it like this."})
    course = v.courses()[0]
    c.post(f"/edit/{course.id}/lesson/m1-l1/media", data={"ref": "https://youtu.be/dQw4w9WgXcQ", "label": "Demo"})
    c.post(f"/edit/{course.id}/lesson/m1-l1/media", data={"label": "Sound"}, files={"file": ("chop sound.mp3", b"ID3xx")})
    les = v.get_course(course.id).modules[0]["lessons"][0]
    assert "![Demo](https://youtu.be/dQw4w9WgXcQ)" in les["content"]
    assert "![Sound](<media/chop sound.mp3>)" in les["content"]
    assert v.find_media(course.id, "media/chop sound.mp3").read_bytes() == b"ID3xx"
    c.post(f"/courses/{course.id}/start")
    jid = v.journeys()[0]["id"]
    assert "<audio controls" in c.get(f"/learn/{jid}/lesson/m1-l1").text


def test_voice_note_evidence_plays_back(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    jid = v.journeys()[0]["id"]
    c.post(f"/learn/{jid}/lesson/m1-l1/done", data={})
    c.post(f"/learn/{jid}/lesson/m1-l2/done", data={})
    c.post(f"/learn/{jid}/task/m1-practical/evidence", files={"file": ("voice note.webm", b"\x1aE\xdf\xa3webm")})
    page = c.get(f"/learn/{jid}/module/m1").text
    assert "<audio controls" in page and "data-recorder" in page
    sha = page.split('src="/evidence/')[1].split("?")[0]
    assert c.get(f"/evidence/{sha}?name=voice%20note.webm").content == b"\x1aE\xdf\xa3webm"


def test_kinds():
    assert media_kind("https://youtu.be/dQw4w9WgXcQ") == "youtube"
    assert media_kind("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "youtube"
    assert media_kind("clip.MP4") == "video" and media_kind("a.opus") == "audio" and media_kind("x.htm") == "html"
    assert media_kind("https://example.com/page") == "link"


def test_old_courses_keep_their_fingerprint():
    files = {"course.yaml": "title: T\nmodules:\n  - title: M\n    lessons:\n      - title: L\n        content: hi\n"}
    a = load_course(files)
    assert "media" not in a.modules[0]["lessons"][0]
