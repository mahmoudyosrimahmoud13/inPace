"""v1.11: invite links, progress and replies as links (only what's new), opening links from other apps."""
import html
import re

import pytest

from inpace import exchange
from tests.test_app import client, upload


def _box(page: str, sid: str) -> str:
    return html.unescape(re.search(rf'<textarea id="{sid}"[^>]*>(.*?)</textarea>', page, re.S).group(1))


def test_every_link_shape_opens():
    data = {"inpace": "contact", "id": "x" * 64, "name": "Omar"}
    body = exchange.to_code(data)[len("inpace:"):]
    for text in (exchange.to_code(data), exchange.to_link(data), "inpace://open/" + body,
                 "Hi! Add me:\nhttps://mahmoudyosrimahmoud13.github.io/inPace/open.html#" + body):
        assert exchange.from_code(text)["name"] == "Omar", text
    sh = exchange.share_links("Add me", data)
    assert sh["fits"] and sh["link"].startswith(exchange.WEB_LINK)
    assert sh["email"].startswith("mailto:") and "t.me/share" in sh["telegram"] and "wa.me" in sh["whatsapp"]
    with pytest.raises(exchange.FileProblem):
        exchange.from_code("https://example.com/open#short")


def _connect(tmp_path):
    lv, learner = client(tmp_path, "Omar")
    cv, checker = client(tmp_path, "Sara")
    # Sara taps Omar's link (it opens /link in her app), adds him, then sends her link back in one tap.
    link = exchange.link_body(_box(learner.get("/people").text, "my-code"))
    r = checker.get("/link?d=" + link)
    code = re.search(r'name="code" value="([^"]+)"', r.text).group(1)
    r = checker.post("/open", data={"code": code, "from": "people"})
    card = html.unescape(re.search(r'<textarea name="card" hidden>(.*?)</textarea>', r.text, re.S).group(1))
    r = checker.post("/people/add", data={"card": card, "relationship": "i_check"})
    assert "Send your link back to Omar" in html.unescape(r.text)
    back = _box(r.text, "send-back")
    r = learner.post("/open", data={"code": back, "from": "people"})
    card = html.unescape(re.search(r'<textarea name="card" hidden>(.*?)</textarea>', r.text, re.S).group(1))
    learner.post("/people/add", data={"card": card, "relationship": "checks_me"})
    assert lv.my_checkers()[0]["name"] == "Sara" and cv.person(lv.identity.id)["i_check"]
    return lv, learner, cv, checker


def _lesson(learner, lv, jid, lid):
    learner.post(f"/learn/{jid}/lesson/{lid}/done", data={})
    learner.post(f"/milestones/{jid}/save")


def test_progress_and_reply_as_links(tmp_path):
    lv, learner, cv, checker = _connect(tmp_path)
    learner.post("/courses/sample/python-basics")
    learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    _lesson(learner, lv, jid, "m1-l1")

    # First send: the whole history, as a link.
    page = learner.get("/milestones").text
    first = _box(page, "send-" + jid)
    assert "/open#" in first and "Or download the full progress file" in html.unescape(page)
    r = checker.post("/open", data={"code": first, "from": "people"}, follow_redirects=True)
    assert "Nothing was changed since you last checked" in html.unescape(r.text)

    # Sara approves; her reply is a link too, and Omar opens it.
    r = checker.post(f"/review/{lv.identity.id}/{jid}", data={"decision": "approved", "note": "Nice"},
                     follow_redirects=True)
    reply = _box(r.text, "reply-link")
    r = learner.post("/open", data={"code": reply}, follow_redirects=True)
    assert "Sara approved 1 milestone" in html.unescape(r.text)

    # Next time the link only carries what Sara hasn't seen.
    _lesson(learner, lv, jid, "m1-l2")
    assert exchange.checkers_have(lv, jid) == 1
    second = exchange.from_code(_box(learner.get("/milestones").text, "send-" + jid))
    assert second["since"] == 1 and [m["body"]["seq"] for m in second["milestones"]] == [2]
    assert "outline" not in second
    r = checker.post("/open", data={"code": exchange.to_link(second), "from": "people"}, follow_redirects=True)
    assert "Nothing was changed since you last checked" in html.unescape(r.text)
    full = cv.received_one(lv.identity.id, jid)["data"]
    assert [m["body"]["seq"] for m in full["milestones"]] == [1, 2] and full.get("outline")

    # A changed old milestone is still caught: the whole history is checked, not just the new part.
    tampered = exchange.make_progress_file(lv, jid, 1)
    tampered["milestones"][0]["body"]["prev"] = "0" * 64
    r = checker.post("/open", data={"code": exchange.to_link(tampered), "from": "people"}, follow_redirects=True)
    assert "doesn't connect" in html.unescape(r.text) or "changed" in html.unescape(r.text)


def test_update_link_without_the_earlier_history(tmp_path):
    lv, learner, cv, checker = _connect(tmp_path)
    learner.post("/courses/sample/python-basics")
    learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    _lesson(learner, lv, jid, "m1-l1")
    _lesson(learner, lv, jid, "m1-l2")
    newest = exchange.make_progress_file(lv, jid, 1)
    r = checker.post("/open", data={"code": exchange.to_link(newest), "from": "people"}, follow_redirects=True)
    assert "full progress file" in html.unescape(r.text)


def test_link_opened_before_setup(tmp_path):
    from starlette.testclient import TestClient
    from inpace.app import create_app
    from inpace.vault import Vault
    lv, learner = client(tmp_path, "Omar")
    body = exchange.link_body(_box(learner.get("/people").text, "my-code"))
    v = Vault(tmp_path / "New")
    c = TestClient(create_app(v))
    assert c.get("/link?d=" + body).url.path == "/setup"
    r = c.post("/setup", data={"name": "Nour", "color": "#1F7A56"})
    if "Opening the link" not in html.unescape(r.text):
        r = c.get("/")
    assert "Opening the link" in html.unescape(r.text)
    assert "Opening the link" not in html.unescape(c.get("/").text)  # only once


def test_milestone_page_falls_back_to_a_file_when_too_big(tmp_path, monkeypatch):
    lv, learner, cv, checker = _connect(tmp_path)
    learner.post("/courses/sample/python-basics")
    learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    _lesson(learner, lv, jid, "m1-l1")
    monkeypatch.setattr(exchange, "LINK_LIMIT", 50)
    page = html.unescape(learner.get("/milestones").text)
    assert "too big for a link" in page and f'id="send-{jid}"' not in page


PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


def test_course_picture_and_search(tmp_path):
    lv, a = client(tmp_path, "Omar")
    a.post("/courses/sample/python-basics")
    a.post("/courses/sample/python-basics-ar")
    page = html.unescape(a.get("/courses").text)
    assert "data-course-search" in page  # the search box shows from 4 courses
    assert "printing and simple math" in page  # lesson titles are searchable
    # Add a picture, see it, share it, remove it.
    r = a.post("/edit/python-basics/image", files={"image": ("me.png", PNG)}, follow_redirects=True)
    assert "Saved the picture." in html.unescape(r.text)
    assert lv.get_course("python-basics").extra["image"] == "cover.png"
    assert "/m/python-basics/cover.png" in a.get("/courses").text
    assert a.get("/m/python-basics/cover.png").content == PNG
    pack = a.get("/courses/python-basics/export").content
    import io
    import zipfile
    assert "files/cover.png" in zipfile.ZipFile(io.BytesIO(pack)).namelist()
    bv, b = client(tmp_path, "Sara")
    upload(b, "py.lpack", pack)
    assert bv.get_course("python-basics").extra.get("image") == "cover.png"
    assert b.get("/m/python-basics/cover.png").content == PNG
    r = a.post("/edit/python-basics/image", files={"image": ("x.txt", b"hi")}, follow_redirects=True)
    assert "JPG, PNG" in html.unescape(r.text)
    a.post("/edit/python-basics/image", data={"remove": "1"})
    assert "image" not in lv.get_course("python-basics").extra
    assert 'class="cover blank"' in a.get("/courses").text


def test_folder_cover(tmp_path):
    from inpace.course import course_from_folder
    d = tmp_path / "Docker course"
    (d / "01 Intro").mkdir(parents=True)
    (d / "01 Intro" / "01 Welcome.mp4").write_bytes(b"x")
    (d / "cover.jpg").write_bytes(b"jpg")
    c = course_from_folder(d)
    assert c.extra["image"] == "cover.jpg"
    assert all(les.get("media") != "cover.jpg" for m in c.modules for les in m["lessons"])


def test_sample_courses_have_pictures(tmp_path):
    lv, a = client(tmp_path, "Omar")
    page = a.get("/courses").text
    assert "/sample-file/python-basics/cover.jpg" in page
    assert a.get("/sample-file/python-basics/cover.jpg").content[:2] == b"\xff\xd8"
    assert a.get("/sample-file/python-basics/../course.yaml").status_code == 404
    a.post("/courses/sample/python-basics")
    assert lv.get_course("python-basics").extra["image"] == "cover.jpg"
    assert a.get("/m/python-basics/cover.jpg").content[:2] == b"\xff\xd8"
