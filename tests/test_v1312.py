"""v1.31.2: long buttons show their progress, light/dark and colors stay in step, and the Linux window's scrollbar."""
import io
from pathlib import Path

from inpace import progress, updater
from tests.test_app import client

ROOT = Path(__file__).resolve().parent.parent


def test_progress_is_reported_and_read_back(tmp_path):
    v, c = client(tmp_path, "Lina")
    assert c.get("/progress.json?t=nothing123").json() == {}
    progress.report("abc123xyz", title="inPace 9.9", got=5, size=10, note="download")
    assert c.get("/progress.json?t=abc123xyz").json()["got"] == 5
    progress.report("", got=1)  # no token: nothing kept
    assert "" not in progress.PROGRESS
    progress.PROGRESS.clear()


def test_an_update_download_reports_its_megabytes(tmp_path, monkeypatch):
    data = b"x" * 600_000

    class R(io.BytesIO):
        headers = {"Content-Length": str(len(data))}
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(updater, "_get", lambda url, timeout=0: R(data))
    progress.within("upd123456", {"title": "inPace 9.9", "note": "download"}, updater._download, "https://x/y", tmp_path / "f")
    x = progress.get("upd123456")
    assert (tmp_path / "f").read_bytes() == data and x["got"] == x["size"] == len(data) and x["note"] == "download"
    updater._download("https://x/y", tmp_path / "g")  # nobody watching: the plain way
    assert (tmp_path / "g").read_bytes() == data
    progress.PROGRESS.clear()


def test_long_buttons_are_marked():
    T = ROOT / "inpace" / "templates"
    assert 'action="/library/{{ e.id }}/add" data-progress' in (T / "library_course.html").read_text(encoding="utf-8")
    roadmap = (T / "roadmap.html").read_text(encoding="utf-8")
    assert roadmap.count("data-progress") == 4 and "data-busy" not in roadmap  # v1.33: the sprint's Add too
    base = (T / "base.html").read_text(encoding="utf-8")
    assert 'action="/updates/check" data-progress' in base and 'action="/updates/install" data-progress' in base
    assert 'data-w-installing=' in base


def test_look_choices_change_the_page_without_a_reload(tmp_path):
    v, c = client(tmp_path, "Lina")
    page = c.get("/settings").text
    assert page.count("data-look") >= 12  # 3 modes, 2 dark looks, 7 colors
    assert 'name="accent"' in page and 'data-autosubmit' not in page.split('id="look"')[1].split('id="g-study"')[0]
    # saving works the same as before
    c.post("/settings/colors", data={"accent": "mint"})
    c.post("/settings/look", data={"theme": "dark", "dark_style": "black"})
    page = c.get("/").text
    assert 'data-theme="dark"' in page and "data-black" in page and 'data-accent="mint"' in page


def test_the_linux_window_keeps_scrollbars_thin_and_on_the_right():
    from inpace import window
    assert "gtk-overlay-scrolling" in window.LINUX_HELPER
    css = (ROOT / "inpace" / "static" / "style.css").read_text(encoding="utf-8")
    assert 'html.wk-gtk[dir="rtl"] { direction: ltr; }' in css and 'html.wk-gtk[dir="rtl"] body { direction: rtl; }' in css
    assert 'classList.add("wk-gtk")' in (ROOT / "inpace" / "templates" / "base.html").read_text(encoding="utf-8")


def test_the_page_script_can_run_twice():
    js = (ROOT / "inpace" / "static" / "app.js").read_text(encoding="utf-8")
    body = js[js.index("(function inpaceApp() {"):]
    assert body.rstrip().endswith("})();")  # everything inside one function: no "already declared" on a second run
