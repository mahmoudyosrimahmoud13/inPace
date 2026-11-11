"""v1.5: friend codes, sharing links, the app window chooser, Arabic everywhere."""
import html
import re

import pytest

from inpace import exchange
from tests.test_app import client


def test_friend_code_round_trip(tmp_path):
    av, a = client(tmp_path, "Omar")
    bv, b = client(tmp_path, "Sara")
    page = a.get("/people").text
    msg = html.unescape(re.search(r'<textarea id="my-code"[^>]*>(.*?)</textarea>', page, re.S).group(1))
    assert "inpace:" in msg and "t.me/share/url" in page and "wa.me" in page
    # Pasting the whole chat message, even broken over lines, works.
    r = b.post("/open", data={"code": "Omar said:\n" + msg[:40] + "\n" + msg[40:], "from": "people"})
    assert "How are you connected?" in html.unescape(r.text) and "Omar" in html.unescape(r.text)
    # A cut-off code gives a clear message.
    r = b.post("/open", data={"code": msg[:-30], "from": "people"}, follow_redirects=True)
    assert "cut off" in html.unescape(r.text) or "doesn't look like" in html.unescape(r.text)


def test_bad_code():
    with pytest.raises(exchange.FileProblem):
        exchange.from_code("hello")
    with pytest.raises(exchange.FileProblem):
        exchange.from_code("inpace:AAAAAAAAAAAAAAAAAAAAAAAA")


def test_window_chooser_runs():
    from inpace.window import which
    assert which() in ("pywebview", "gtk", "app-mode browser", "browser tab")


def test_arabic_everywhere(tmp_path):
    av, a = client(tmp_path, "Omar")
    av._set_meta("lang", "ar")
    for path in ["/", "/courses", "/milestones", "/people", "/open", "/races", "/settings", "/ai"]:
        r = a.get(path)
        assert r.status_code == 200 and 'dir="rtl"' in r.text, path
    # Run-time messages are translated too, including ones with names in them.
    r = a.get("/people?ok=Added%20Sara.")
    assert "تمت إضافة Sara." in html.unescape(r.text)
    r = a.get("/courses?err=" + "That%20course%20isn%27t%20installed.")
    assert "هذه الدورة غير مثبّتة." in html.unescape(r.text)
    # Settings page title is plain text again.
    assert "<title>الإعدادات" in a.get("/settings").text


def test_dates():
    from inpace import app as A
    A.CURRENT["lang"] = "en"
    assert A.nice_date("2026-11-11T10:00:00Z") == "Nov 11, 2026"
    A.CURRENT["lang"] = "ar"
    assert A.nice_date("2026-11-11") == "11 نوفمبر 2026"
    A.CURRENT["lang"] = "en"


def test_theme_switch(tmp_path):
    v, c = client(tmp_path, "Omar")
    assert "data-theme=" not in c.get("/").text.split(">")[1]
    assert c.post("/theme", data={"theme": "dark"}).status_code == 204
    assert 'data-theme="dark"' in c.get("/").text
    c.post("/theme", data={"theme": "light"})
    assert 'data-theme="light"' in c.get("/").text
    c.post("/theme", data={"theme": "<script>"})
    assert "data-theme=" not in c.get("/").text.split(">")[1]


def test_arabic_sample_course_listed_first(tmp_path):
    v, c = client(tmp_path, "Omar")
    v._set_meta("lang", "ar")
    page = c.get("/courses").text
    assert page.index("أساسيات بايثون") < page.index("Python Basics")
