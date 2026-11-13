"""v1.21: optional tasks (the module doesn't wait for them), a faster start (compiled templates kept between starts,
Markdown loaded only when needed), and the phone app's start-up time in Settings."""
import html
import io
import re
import zipfile
from pathlib import Path

import yaml

from inpace import app as app_mod
from inpace.course import load_course
from inpace.exam import build_exam
from tests.test_app import client

SAMPLE = Path(app_mod.__file__).parent / "sample_courses" / "python-basics"


def _pack(optional: bool) -> bytes:
    """The Python Basics sample, with its first module's upload and write-up tasks marked optional."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for f in SAMPLE.rglob("*"):
            if f.is_file():
                rel = f.relative_to(SAMPLE).as_posix()
                data = f.read_bytes()
                if rel == "course.yaml":
                    head = yaml.safe_load(data)
                    head["id"] = "python-basics-optional"
                    for r in head["modules"][0]["requires"]:
                        if r["type"] in ("practical", "explain") and optional:
                            r["optional"] = True
                    data = yaml.safe_dump(head, allow_unicode=True, sort_keys=False).encode()
                z.writestr(rel, data)
    return buf.getvalue()


def _start(tmp_path):
    v, c = client(tmp_path, "Layla")
    r = c.post("/open", files={"file": ("course.lpack", _pack(True))})
    assert r.status_code == 200
    c.post("/courses/python-basics-optional/start")
    jid = v.journeys()[0]["id"]
    return v, c, jid


def _pass_quiz(v, c, jid, cid):
    r = c.get(f"/learn/{jid}/task/m1-quiz/quiz")
    seed = re.search(r'name="seed" value="([0-9a-f]+)"', r.text).group(1)
    course = v.get_course(cid)
    qids = next(r for r in course.modules[0]["requires"] if r["type"] == "quiz")["questions"]
    exam = build_exam(course, qids, seed)
    ans = {q["id"]: next(ch["id"] for ch in q["choices"] if ch["id"] in course.answers[q["id"]]["right"]) for q in exam}
    c.post(f"/learn/{jid}/task/m1-quiz/quiz", data={"seed": seed, **ans})


def test_a_module_finishes_without_its_optional_tasks(tmp_path):
    v, c, jid = _start(tmp_path)
    course = v.get_course("python-basics-optional")
    assert [r.get("optional", False) for r in course.modules[0]["requires"]] == [True, True, False]
    for les in course.modules[0]["lessons"]:
        c.post(f"/learn/{jid}/lesson/{les['id']}/done", data={})
    page = html.unescape(c.get(f"/learn/{jid}/module/m1").text)
    assert "complete the tasks that aren't marked optional" in page and page.count(">Optional<") == 2
    assert v.progress(jid)["modules"][0]["status"] == "open"   # the quiz is still required
    lesson = html.unescape(c.get(f"/learn/{jid}/lesson/{course.modules[0]['lessons'][0]['id']}").text)
    assert "Module tasks · 0/1" in lesson                              # only required tasks are counted
    _pass_quiz(v, c, jid, "python-basics-optional")
    state = v.progress(jid)
    assert state["modules"][0]["status"] == "done" and state["modules"][1]["status"] == "open"
    # Doing an optional task later still shows it as done.
    c.post(f"/learn/{jid}/task/m1-explain/writeup", data={"text": "print shows things on the screen " * 10})
    assert next(r for r in v.progress(jid)["modules"][0]["requires"] if r["id"] == "m1-explain")["done"]


def test_older_courses_keep_their_fingerprint_and_the_flag_survives_editing(tmp_path):
    plain = load_course({p.relative_to(SAMPLE).as_posix(): p.read_text(encoding="utf-8") for p in SAMPLE.rglob("*")
                         if p.is_file() and p.suffix in (".yaml", ".md")})
    assert all("optional" not in r for m in plain.public_dict()["modules"] for r in m["requires"])
    v, c, jid = _start(tmp_path)
    # The editor shows it, keeps it in "Edit as one file", and can turn it off and on.
    page = html.unescape(c.get("/edit/python-basics-optional").text)
    assert "Optional: the module can be finished without it" in page
    from inpace.editor import course_to_yaml
    assert "optional: true" in course_to_yaml(v.get_course("python-basics-optional"))
    c.post("/edit/python-basics-optional", data={"action": "edit_task", "module": "m1", "task": "m1-practical",
                                                 "prompt": "Make a file"})
    assert "optional" not in v.get_course("python-basics-optional").modules[0]["requires"][0]
    c.post("/edit/python-basics-optional", data={"action": "edit_task", "module": "m1", "task": "m1-practical",
                                                 "prompt": "Make a file", "optional": "1"})
    assert v.get_course("python-basics-optional").modules[0]["requires"][0]["optional"] is True
    c.post("/edit/python-basics-optional", data={"action": "add_task", "module": "m2", "type": "explain",
                                                 "prompt": "Say it in your words", "optional": "1"})
    assert v.get_course("python-basics-optional").modules[1]["requires"][-1]["optional"] is True


def test_compiled_templates_are_kept_and_markdown_loads_when_needed(tmp_path):
    v, c = client(tmp_path, "Layla")
    app_mod.env.cache.clear()   # a fresh start: nothing compiled in memory yet
    c.get("/")
    cache = v.home / "cache" / "templates"
    assert cache.is_dir() and any(cache.iterdir())
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    jid = v.journeys()[0]["id"]
    assert "<p" in c.get(f"/learn/{jid}/lesson/m1-l1").text
    assert app_mod.md.render("**hi**").strip() == "<p dir=\"ltr\"><strong>hi</strong></p>"   # with the bidi rule


def test_phone_start_time_shows_in_settings(tmp_path):
    v, c = client(tmp_path, "Layla")
    assert c.post("/startup-time", data={"python": "1234", "page": "1900"}).json() == {"ok": True}
    assert c.post("/startup-time", data={"python": "lots"}).json() == {"ok": False}
    page = html.unescape(c.get("/settings").text)
    assert "Last start: ready in 1.2 s, first page in 1.9 s." in page
