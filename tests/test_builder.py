"""The course builder: start from a title or a list of links, reorder, move, edit tasks and questions,
undo, edit as one file, preview, and the AI prompts for books, playlists and more."""
import html

from inpace import ai, editor
from tests.test_app import client


def test_start_from_title_only(tmp_path):
    v, c = client(tmp_path, "Omar")
    r = c.post("/edit/new", data={"title": "Guitar", "start": "blank"})
    assert "Course created" in html.unescape(r.text)
    assert v.courses()[0].modules[0]["lessons"][0]["title"] == "Welcome"


def test_start_from_links_with_modules(tmp_path):
    v, c = client(tmp_path, "Omar")
    links = """# Basics
https://www.youtube.com/watch?v=dQw4w9WgXcQ
Installing Docker | https://youtu.be/abcdefghijk
# Compose
/home/me/Videos/03 - Compose intro.mp4
"""
    c.post("/edit/new", data={"title": "Docker", "start": "links", "links": links})
    course = v.courses()[0]
    assert [m["title"] for m in course.modules] == ["Basics", "Compose"]
    titles = [les["title"] for les in course.modules[0]["lessons"]]
    assert titles == ["Video 1", "Installing Docker"]
    assert course.modules[1]["lessons"][0]["title"] == "Compose intro"
    assert course.modules[1]["lessons"][0]["media"] == "/home/me/Videos/03 - Compose intro.mp4"
    r = c.post("/edit/new", data={"title": "Bad", "start": "links", "links": "not a link"})
    assert "isn't a link" in html.unescape(r.text)


def test_reorder_move_edit_and_undo(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/edit/new", data={"title": "Cooking", "start": "blank", "lesson_title": "Knives", "content": "Hold it."})
    cid = v.courses()[0].id
    c.post(f"/edit/{cid}", data={"action": "add_lesson", "module": "m1", "title": "Pans", "content": "Heat it."})
    c.post(f"/edit/{cid}", data={"action": "add_lesson", "module": "m1", "media": "https://youtu.be/dQw4w9WgXcQ"})
    c.post(f"/edit/{cid}", data={"action": "add_module", "title": "Baking", "lesson_title": "Bread", "content": "Knead."})
    titles = lambda: [[l["title"] for l in m["lessons"]] for m in v.get_course(cid).modules]  # noqa: E731
    assert titles() == [["Knives", "Pans", "Video"], ["Bread"]]
    c.post(f"/edit/{cid}", data={"action": "move_lesson", "lesson": "m1-l2", "dir": "up"})
    assert titles()[0] == ["Pans", "Knives", "Video"]
    c.post(f"/edit/{cid}", data={"action": "move_lesson", "lesson": "m1-l2", "to_module": "m2"})
    assert titles() == [["Knives", "Video"], ["Bread", "Pans"]]
    c.post(f"/edit/{cid}", data={"action": "move_module", "module": "m2", "dir": "up"})
    assert titles() == [["Bread", "Pans"], ["Knives", "Video"]]
    # Undo goes back one change at a time.
    r = c.post(f"/edit/{cid}", data={"action": "undo"})
    assert "Undone" in html.unescape(r.text)
    assert titles() == [["Knives", "Video"], ["Bread", "Pans"]]
    # Tasks and questions can be changed after they're made.
    c.post(f"/edit/{cid}", data={"action": "add_question", "text": "Sharpest?", "right": "Chef knife", "wrong": "Spoon\nFork\nCup"})
    c.post(f"/edit/{cid}", data={"action": "add_task", "module": "m1", "type": "explain", "prompt": "Why?"})
    task = v.get_course(cid).modules[0]["requires"][0]
    c.post(f"/edit/{cid}", data={"action": "edit_task", "module": "m1", "task": task["id"], "prompt": "Why sharp?", "min_words": "15"})
    t2 = v.get_course(cid).modules[0]["requires"][0]
    assert t2["prompt"] == "Why sharp?" and t2["min_words"] == 15
    c.post(f"/edit/{cid}", data={"action": "edit_question", "question": "q1", "text": "Sharpest knife?",
                                "right": "Chef knife\nSantoku", "wrong": "Spoon\nFork\nCup", "show": "4"})
    co = v.get_course(cid)
    assert co.questions["q1"]["text"] == "Sharpest knife?" and len(co.answers["q1"]["right"]) == 2


def test_whole_course_as_one_file(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/courses/sample/python-basics")
    page = html.unescape(c.get("/edit/python-basics/yaml").text)
    assert "What is Python?" in page and "right:" in page
    text = editor.course_to_yaml(v.get_course("python-basics")).replace("title: Python Basics", "title: Python Basics 2", 1)
    r = c.post("/edit/python-basics/yaml", data={"yaml": text})
    co = v.get_course("python-basics")
    assert co.title == "Python Basics 2" and co.modules[0]["lessons"][0]["id"] == "m1-l1" and co.has_answers
    r = c.post("/edit/python-basics/yaml", data={"yaml": "title: [broken"})
    assert "formatting mistake" in html.unescape(r.text)


def test_preview(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/edit/new", data={"title": "P", "start": "blank"})
    cid = v.courses()[0].id
    r = c.post(f"/edit/{cid}/preview", data={"title": "T", "content": "**Hi**\n\nhttps://youtu.be/dQw4w9WgXcQ", "media": ""})
    assert "<strong>Hi</strong>" in r.text and "youtube-nocookie" in r.text


def test_ai_prompt_kinds():
    book = ai.build_prompt("", "beginner", 4, 3, "English", source="book", book_title="Atomic Habits", book_author="James Clear")
    assert 'the book "Atomic Habits" by James Clear' in book and "Never copy" in book
    pl = ai.build_prompt("", "beginner", 4, 3, "English", source="playlist", playlist="Docker for beginners",
                         videos="Intro | https://youtu.be/abc")
    assert "Docker for beginners" in pl and "https://youtu.be/abc" in pl and "NEVER invent video links" in pl
    for kind, field in (("course", "course_name"), ("project", "project"), ("exam", "exam"), ("material", "material")):
        assert "Topic:" not in ai.build_prompt("", "beginner", 4, 3, "English", source=kind, **{field: "X"})
    assert "Topic: Excel" in ai.build_prompt("Excel", "beginner", 4, 3, "English")
