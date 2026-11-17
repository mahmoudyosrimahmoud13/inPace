"""v1.28.3: honest update notice, new library courses, Markdown extras, YouTube with inPace's controls."""
import html
import json

from inpace import library, media, updater
from inpace.app import md
from tests.test_app import client


def test_the_running_copy_is_not_called_out_of_date():
    assert not updater.newer(updater.__version__)
    assert updater.newer("99.0.0")


def _index(*ids):
    return {"courses": [{"id": i, "title": f"Course {i}", "hash": "h", "modules": 1, "lessons": 1} for i in ids]}


def test_new_library_courses_get_a_badge_then_a_new_tag(tmp_path, monkeypatch):
    v, c = client(tmp_path, "Omar")
    monkeypatch.setattr(library, "load_index", lambda home, refresh=False: _index("a", "b"))
    c.get("/library")                     # first look: remembers, nothing is "new"
    assert json.loads(v._meta("library_new", "[]")) == []
    monkeypatch.setattr(library, "load_index", lambda home, refresh=False: _index("a", "b", "c"))
    page = html.unescape(c.get("/library").text)
    assert "New</span>" in page and "1 new course(s)" in page
    assert page.index("Course c") < page.index("Course a")   # new ones first
    assert json.loads(v._meta("library_new", "[]")) == []    # seen now: the badge goes away
    assert "Look for new courses" in page                    # the Refresh button


def test_markdown_extras():
    out = md.render("~~old~~ see https://ex.org/x.\n\n- [x] done\n\n> [!TIP]\n> hi\n\nA[^1].\n\n[^1]: note\n")
    assert "<s>old</s>" in out and '<a href="https://ex.org/x">' in out
    assert 'type="checkbox" disabled checked' in out and "callout-tip" in out
    assert 'href="#fn-1"' in out and '<li id="fn-1"' in out and "note" in out


def test_youtube_hides_its_own_controls():
    class T(str):
        pass
    out = media.youtube_player("c1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "", lambda _: False, lambda s: s)
    assert "controls=0" in out and 'data-l-full="Full screen"' in out
    assert 'data-yt-id="dQw4w9WgXcQ"' in out and 'data-l-pip=' in out   # the same player labels as video files


def test_script_and_style_links_change_when_the_files_change(tmp_path):
    from inpace.app import STATIC_V
    v, c = client(tmp_path, "Omar")
    page = c.get("/").text
    assert f"/static/app.js?v={STATIC_V['app.js']}" in page and f"/static/style.css?v={STATIC_V['style.css']}" in page
    assert "?v=30" not in page and "?v=36" not in page


def test_delete_all_my_data(tmp_path):
    v, c = client(tmp_path, "Omar")
    (v.home / "courses" / "mine").mkdir()
    (v.home / "notes.txt").write_text("x")
    r = c.post("/settings/delete-everything", data={"confirm": "nope"})
    assert "Nothing was deleted" in html.unescape(r.text) and (v.home / "notes.txt").exists()
    r = c.post("/settings/delete-everything", data={"confirm": "DELETE"})
    assert not (v.home / "notes.txt").exists() and not (v.home / "courses" / "mine").exists()
    assert not v.is_set_up and "Welcome to inPace" in html.unescape(r.text)


def test_youtube_has_quality_and_ad_labels():
    out = media.youtube_player("c1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "", lambda _: False, lambda s: s)
    assert 'data-l-quality="Quality"' in out and 'data-l-auto="Auto"' in out and "data-l-ad=" in out


def test_youtube_rules_are_data_only_and_checked():
    from inpace import ytrules
    r = ytrules.clean({"own_controls": "yes", "fallback_ms": 10**9, "cover_after_ms": 1000, "evil": "<script>"})
    assert r["own_controls"] is True and r["fallback_ms"] == 9000 and r["cover_after_ms"] == 1000 and "evil" not in r


def test_ad_guard_is_on_by_default_and_can_be_turned_off(tmp_path):
    v, c = client(tmp_path, "Omar")
    assert "Ad guard" in html.unescape(c.get("/settings").text)
    out = media.youtube_player("c1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "", lambda _: False, lambda s: s)
    assert "&quot;ad_guard&quot;: true" in out and "controls=0" in out
    c.post("/settings/youtube", data={})                       # unticked
    out = media.youtube_player("c1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "", lambda _: False, lambda s: s)
    assert "&quot;ad_guard&quot;: false" in out and "controls=0" in out   # still inPace's player
