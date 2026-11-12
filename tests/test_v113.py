"""v1.13: the easy way to add a course (sort a neat or messy folder, AI help, copy or keep files) and the phone layout."""
import html
import json
import time

from inpace import organize
from tests.test_app import client


def _messy(tmp_path):
    d = tmp_path / "Algorithms class"
    d.mkdir()
    for name in ("Lecture 1 - Intro.pdf", "lec2_sorting.pdf", "Lecture 03 Graphs.mp4", "L4 trees.pdf",
                 "Lecture 4 trees recording.mp4", "syllabus.pdf", "slides.ppt"):
        (d / name).write_bytes(b"x" * 10)
    (d / "notes.md").write_text("# My notes\nHello", encoding="utf-8")
    return d


def test_messy_folder_is_sorted_by_lecture_numbers(tmp_path):
    plan = organize.guess_plan(_messy(tmp_path), "Algorithms")
    titles = [s["title"] for s in plan["sections"]]
    assert titles == ["General", "Lecture 1", "Lecture 2", "Lecture 3", "Lecture 4"]
    assert plan["sections"][4]["files"] == ["L4 trees.pdf", "Lecture 4 trees recording.mp4"]
    assert plan["cant_show"] == ["slides.ppt"] and not plan["organized"]


def test_no_numbers_sorts_by_kind_and_subfolders_stay(tmp_path):
    d = tmp_path / "stuff"
    d.mkdir()
    for n in ("intro.mp4", "graphs.mp4", "reading.pdf"):
        (d / n).write_bytes(b"x")
    assert [s["title"] for s in organize.guess_plan(d)["sections"]] == ["Videos", "Slides and PDFs"]
    neat = tmp_path / "neat"
    (neat / "01 Basics").mkdir(parents=True)
    (neat / "02 More").mkdir()
    (neat / "01 Basics" / "a.mp4").write_bytes(b"x")
    (neat / "02 More" / "b.mp4").write_bytes(b"x")
    p = organize.guess_plan(neat)
    assert p["organized"] and [s["title"] for s in p["sections"]] == ["Basics", "More"]


def test_organize_and_add_keeping_files_where_they_are(tmp_path):
    v, c = client(tmp_path, "Omar")
    d = _messy(tmp_path)
    page = html.unescape(c.get("/add/organize", params={"folder": str(d), "title": "Algorithms"}).text)
    assert "sorted them by the week, lecture or chapter numbers" in page and "Lecture 4" in page
    assert "1 files can't be shown" in page or "files can't be shown" in page
    plan = {"title": "Algorithms 101", "names": {"lec2_sorting.pdf": "Sorting"},
            "sections": [{"title": "Start here", "files": ["syllabus.pdf"]},
                         {"title": "Lecture 2", "files": ["lec2_sorting.pdf", "../../etc/passwd", "nope.pdf"]}]}
    r = c.post("/add/organize", data={"folder": str(d), "plan": json.dumps(plan), "storage": "keep", "action": "create"},
               follow_redirects=True)
    assert "The files stay where they are" in html.unescape(r.text)
    course = next(x for x in v.courses() if x.title == "Algorithms 101")
    assert [m["title"] for m in course.modules] == ["Start here", "Lecture 2"]
    assert [l["title"] for l in course.modules[1]["lessons"]] == ["Sorting"]
    assert v.find_media(course.id, "lec2_sorting.pdf") == d / "lec2_sorting.pdf"


def test_copy_files_into_inpace(tmp_path):
    v, c = client(tmp_path, "Omar")
    d = _messy(tmp_path)
    plan = {"title": "Copied", "sections": [{"title": "All", "files": ["Lecture 1 - Intro.pdf", "notes.md"]}]}
    r = c.post("/add/organize", data={"folder": str(d), "plan": json.dumps(plan), "storage": "copy"}, follow_redirects=False)
    assert r.headers["location"].startswith("/add/copying/")
    cid = r.headers["location"].rsplit("/", 1)[1]
    deadline = time.time() + 30  # test machines can be slow (Mac runners especially)
    while organize.JOBS[cid]["state"] == "copying" and time.time() < deadline:
        time.sleep(.05)
    assert organize.JOBS[cid]["state"] == "done", organize.JOBS[cid]
    assert (v.media_dir(cid) / "Lecture 1 - Intro.pdf").exists() and not v.media_root(cid)
    (d / "Lecture 1 - Intro.pdf").unlink()  # the original can go now
    assert v.find_media(cid, "Lecture 1 - Intro.pdf") == v.media_dir(cid) / "Lecture 1 - Intro.pdf"


def test_picked_files_are_saved_in_inpace(tmp_path):
    v, c = client(tmp_path, "Omar")
    r = c.post("/add/files", data={"title": "Physics"},
               files=[("files", ("Week 1 forces.pdf", b"%PDF")), ("files", ("Week 2 energy.mp4", b"vid")),
                      ("files", ("../evil.pdf", b"x"))], follow_redirects=False)
    loc = r.headers["location"]
    assert loc.startswith("/add/organize?draft=")
    page = html.unescape(c.get(loc).text)
    assert "Week 1" in page and "Week 2" in page and "Where should the files live" not in page
    draft = loc.split("draft=")[1].split("&")[0]
    plan = organize.guess_plan(v.home / "drafts" / draft, "Physics")
    r = c.post("/add/organize", data={"draft": draft, "plan": json.dumps(plan)}, follow_redirects=True)
    assert "saved in inPace" in html.unescape(r.text)
    course = next(x for x in v.courses() if x.title == "Physics")
    assert (v.media_dir(course.id) / "Week 1 forces.pdf").exists() and not (v.home / "drafts" / draft).exists()
    assert not (v.home / "evil.pdf").exists()


def test_ai_sorting_by_copy_paste(tmp_path):
    v, c = client(tmp_path, "Omar")
    d = _messy(tmp_path)
    page = html.unescape(c.get("/add/organize", params={"folder": str(d)}).text)
    assert "Copy the request" in page and "lec2_sorting.pdf" in page
    reply = ('Sure! ```json\n{"title": "Algo", "sections": [{"title": "Week 1: Basics", "files": ["syllabus.pdf", '
             '"Lecture 1 - Intro.pdf", "made-up.pdf"]}], "names": {"syllabus.pdf": "Course outline"}}\n```')
    r = html.unescape(c.post("/add/organize", data={"folder": str(d), "plan": "{}", "action": "ai_paste", "reply": reply}).text)
    assert "This is how the AI sorted your files" in r and "Week 1: Basics" in r and "Course outline" in r
    assert "Not sorted yet" in r and "made-up.pdf" not in r  # nothing goes missing, nothing invented
    bad = html.unescape(c.post("/add/organize", data={"folder": str(d), "plan": "{}", "action": "ai_paste", "reply": "no idea"}).text)
    assert "has no plan in it" in bad


def test_phone_tabs_and_add_page(tmp_path):
    v, c = client(tmp_path, "Omar")
    page = html.unescape(c.get("/add").text)
    assert 'class="tabbar"' in page and "A folder on this device" in page and "Write it myself" in page
    assert 'href="/add" class="tab-add on"' in page
