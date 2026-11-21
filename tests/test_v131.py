"""v1.31: works with CodeNote. "Practice in CodeNote" (only when CodeNote is found), CodeNote work as proof, and
lesson links back into inPace. Formats: the bridge spec v1 (Project doc claude/codenote-inpace-bridge.md)."""
import base64
import html
import json
import re
import time
import zlib

import pytest

from inpace import codenote, exchange, library
from tests.test_app import client


def spec_link(payload: dict) -> str:
    """The reference code from the bridge spec, section 1."""
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    body = base64.urlsafe_b64encode(zlib.compress(raw, 9)).rstrip(b"=").decode("ascii")
    return "codenote://open/" + body


@pytest.fixture(autouse=True)
def fresh_check(monkeypatch):
    """Each test starts with no cached answer, in inPace's own window."""
    monkeypatch.setitem(codenote.SHELL, "kind", "window")
    monkeypatch.setitem(codenote._CACHE, "at", 0.0)
    monkeypatch.setitem(codenote._CACHE, "found", False)
    monkeypatch.delenv("INPACE_MOBILE", raising=False)


def learner(tmp_path):
    v, c = client(tmp_path, "Lina")
    c.post("/courses/sample/python-basics")
    jid = c.post("/courses/python-basics/start", follow_redirects=False).headers["location"].rsplit("/", 1)[-1]
    return v, c, jid


def found(monkeypatch, yes: bool):
    monkeypatch.setattr(codenote, "_look", lambda: yes)
    codenote._CACHE["at"] = 0.0  # as if the last check were long ago
    codenote.installed(fresh=True)


# ---- 1. the link ---------------------------------------------------------------------------------------------
def test_link_round_trip_matches_the_spec(tmp_path):
    v, c, jid = learner(tmp_path)
    course = v.get_course("python-basics")
    module, les = course.find_lesson("m1-l2")
    task = course.find_requirement("m1-practical")[1]
    data = codenote.payload(course, module, les, task)
    assert data["codenote"] == "lesson" and data["v"] == 1 and data["markdown"] == les["content"]
    assert data["task"] == {"id": "m1-practical", "prompt": task["prompt"]} and data["language"] == "python"
    src = data["source"]
    assert (src["app"], src["course"], src["course_title"], src["module"], src["lesson"]) == \
        ("inpace", "python-basics", course.title, "m1", "m1-l2")
    link = codenote.link(data)
    assert link == spec_link(data)                      # byte for byte the spec's encoding
    assert codenote.read_link(link) == data             # and back to the same JSON
    assert codenote.read_link(codenote.web_link(data)) == data
    assert codenote.web_link(data).startswith("https://mahmoudyosrimahmoud13.github.io/code_note/open#")
    assert exchange.from_code(src["back"]) == {"inpace": "lesson", "course": "python-basics", "lesson": "m1-l2"}


def test_fences_and_language():
    assert codenote.has_code("Text\n```python\nprint(1)\n```\n") and not codenote.has_code("No code `here`.")
    assert codenote.main_language("```\nx\n```\n```js\ny\n```") == "js"
    assert codenote.main_language("no fences") == "python"


# ---- 2. when the button shows ------------------------------------------------------------------------------------
def test_button_only_on_lessons_with_code_and_only_when_codenote_is_found(tmp_path, monkeypatch):
    v, c, jid = learner(tmp_path)
    found(monkeypatch, True)
    with_code = c.get(f"/learn/{jid}/lesson/m1-l2").text
    assert re.search(r'data-codenote-lesson data-course="python-basics" data-lesson="m1-l2" data-on="1"', with_code)
    assert "data-codenote" not in c.get(f"/learn/{jid}/lesson/m1-l1").text  # no ``` fence: never a button
    module = html.unescape(c.get(f"/learn/{jid}/module/m1").text)
    assert 'data-task="m1-practical"' in module and "Use Export for inPace" in module
    assert "Get CodeNote" not in with_code


def test_button_hidden_when_codenote_isnt_found(tmp_path, monkeypatch):
    v, c, jid = learner(tmp_path)
    found(monkeypatch, False)
    page = c.get(f"/learn/{jid}/lesson/m1-l2").text
    assert 'data-lesson="m1-l2" data-on="0"' in page and "Get CodeNote" not in page
    assert re.search(r'<div class="codenote-row" data-codenote-only hidden', c.get(f"/learn/{jid}/module/m1").text)
    assert c.get("/codenote.json").json()["available"] is False
    monkeypatch.setattr(codenote, "_look", lambda: True)  # installed while inPace is open
    codenote._CACHE["at"] -= 60  # a minute later the window comes back to the front: checked again
    assert c.get("/codenote.json?fresh=1").json()["available"] is True


def test_a_plain_browser_never_shows_it(tmp_path, monkeypatch):
    v, c, jid = learner(tmp_path)
    found(monkeypatch, True)
    monkeypatch.setitem(codenote.SHELL, "kind", "")
    assert 'data-lesson="m1-l2" data-on="0"' in c.get(f"/learn/{jid}/lesson/m1-l2").text
    assert c.get("/codenote.json").json()["available"] is False


def test_errors_and_slow_checks_count_as_not_installed(monkeypatch):
    def broken():
        raise OSError("no registry")
    monkeypatch.setattr(codenote, "_look", broken)
    assert codenote.installed(fresh=True) is False

    def slow():
        time.sleep(1.5)
        return True
    monkeypatch.setattr(codenote, "_look", slow)
    monkeypatch.setitem(codenote._CACHE, "at", 0.0)
    t = time.time()
    assert codenote.installed(fresh=True) is False and time.time() - t < 1.4  # gave up after 1 second


def test_the_answer_is_cached_for_a_few_minutes(monkeypatch):
    calls = []
    monkeypatch.setattr(codenote, "_look", lambda: calls.append(1) or True)
    assert codenote.installed() and codenote.installed() and len(calls) == 1


# ---- opening it --------------------------------------------------------------------------------------------------
def test_open_on_a_computer_sends_the_lesson(tmp_path, monkeypatch):
    v, c, jid = learner(tmp_path)
    got = []
    monkeypatch.setattr(codenote, "open_on_computer", lambda link, web: got.append((link, web)) or "app")
    d = c.post("/codenote/open", data={"course": "python-basics", "task": "m1-practical"}).json()
    assert d["ok"] and d["opened"] == "app"
    sent = codenote.read_link(got[0][0])
    assert sent["task"]["id"] == "m1-practical" and sent["source"]["lesson"] == "m1-l2"  # the module's lesson with code
    assert c.post("/codenote/open", data={"course": "python-basics", "lesson": "nope"}).status_code == 404


def test_long_lessons_come_as_a_md_file(tmp_path, monkeypatch):
    v, c, jid = learner(tmp_path)
    monkeypatch.setattr(codenote, "LINK_LIMIT", 50)  # as if the lesson were over 30,000 characters
    monkeypatch.setattr(codenote, "open_on_computer", lambda link, web: pytest.fail("no link for a long lesson"))
    d = c.post("/codenote/open", data={"course": "python-basics", "lesson": "m1-l2"}).json()
    assert d["file"].startswith("/codenote/lesson.md?")
    r = c.get(d["file"])
    text = r.content.decode("utf-8")
    assert "attachment" in r.headers["content-disposition"] and r.headers["content-disposition"].endswith(".md")
    head, body = text.split("\n---\n", 1)
    assert head.startswith("---\ncodenote: lesson\nv: 1\n") and '"lesson": "m1-l2"' in head
    assert body == v.get_course("python-basics").find_lesson("m1-l2")[1]["content"]


def test_the_limit_is_thirty_thousand():
    assert codenote.LINK_LIMIT == 30_000


# ---- 3. CodeNote work as proof ------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["report.html", "notebook.ipynb", "lists.codenote"])
def test_codenote_exports_are_proof(tmp_path, name):
    v, c, jid = learner(tmp_path)
    body = b"<html><body><h1>Lists</h1><script>alert(1)</script></body></html>" if name.endswith(".html") else b'{"cells": []}'
    r = c.post(f"/learn/{jid}/task/m1-practical/evidence", files={"file": (name, body)}, follow_redirects=True)
    assert "Saved" in html.unescape(r.text)
    ev = [e for e in v.events(jid) if e["type"] == "evidence_added"]
    import hashlib
    assert ev and ev[-1]["data"]["sha256"] == hashlib.sha256(body).hexdigest() and ev[-1]["data"]["name"] == name
    page = c.get(f"/learn/{jid}/module/m1").text
    if name.endswith(".html"):
        assert '<iframe sandbox=""' in page
        sha = ev[-1]["data"]["sha256"]
        shown = c.get(f"/evidence/{sha}?name={name}&view=1")
        assert shown.headers["content-type"].startswith("text/html")
        assert shown.headers["content-security-policy"].startswith("sandbox")  # no scripts, even opened directly
    else:
        assert name in html.unescape(page)


# ---- 4. lesson links ---------------------------------------------------------------------------------------------
def test_a_lesson_link_opens_the_lesson(tmp_path):
    v, c, jid = learner(tmp_path)
    code = exchange.to_link({"inpace": "lesson", "course": "python-basics", "lesson": "m1-l2"})
    r = c.post("/open", data={"code": code}, follow_redirects=False)
    assert r.headers["location"] == f"/learn/{jid}/lesson/m1-l2"
    r = c.post("/open", data={"code": exchange.to_link({"inpace": "lesson", "course": "python-basics", "lesson": "zz"})},
               follow_redirects=False)
    assert "anymore" in html.unescape(r.headers["location"].replace("%20", " "))


def test_a_lesson_link_for_a_course_thats_not_here(tmp_path, monkeypatch):
    v, c = client(tmp_path, "Lina")
    code = exchange.to_link({"inpace": "lesson", "course": "fastapi-basics", "lesson": "m1-l1"})
    r = c.post("/open", data={"code": code}, follow_redirects=True)
    assert "isn't on this device" in html.unescape(r.text)
    monkeypatch.setattr(library, "cached_index", lambda home: {"courses": [{"id": "fastapi-basics", "title": "FastAPI"}]})
    r = c.post("/open", data={"code": code}, follow_redirects=False)
    assert r.headers["location"].startswith("/library/fastapi-basics")
