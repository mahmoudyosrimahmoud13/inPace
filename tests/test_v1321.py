"""v1.32.1: "Open it" on a code file or notebook opens it in your own app (VS Code, Jupyter, your editor) instead of
showing raw text, and "Show in folder" opens the folder it's in. Phones keep the plain-text view."""
from pathlib import Path

import pytest

import inpace.app as app_mod
from inpace import media
from inpace.app import open_on_desktop


class Files:
    def __init__(self, action):
        self.open_action = action


def tr(s):
    return s


def test_computers_get_open_and_show_in_folder():
    out = media.open_buttons(Files("/courses/c1/open-media"), "files/lab/p01.ipynb", "/m/c1/files/lab/p01.ipynb", tr)
    assert 'data-open-file="/courses/c1/open-media"' in out and 'data-media="files/lab/p01.ipynb"' in out
    assert "Open it" in out and "Show in folder" in out and "data-reveal" in out
    assert 'data-view="/m/c1/files/lab/p01.ipynb?view=1"' in out  # the plain-text view, if opening fails


def test_phones_keep_the_plain_text_view():
    out = media.open_buttons(Files(""), "files/a.py", "/m/c1/files/a.py", tr)
    assert out.startswith("<a ") and "?view=1" in out and "Show in folder" not in out
    assert media.open_buttons(Files(""), "files/", "", tr, folder=True) == ""


def test_a_project_folder_has_open_the_folder_and_a_button_per_file(tmp_path):
    (tmp_path / "lab").mkdir()
    (tmp_path / "lab" / "p01.py").write_text("print(1)\n")
    (tmp_path / "lab" / "p02.ipynb").write_text('{"cells": []}')
    out = media.folder_view("c1", "files/lab/", tmp_path / "lab", tr, Files("/courses/c1/open-media"))
    assert "Open the folder" in out and 'data-media="files/lab/"' in out
    assert 'data-media="files/lab/p01.py"' in out and 'data-media="files/lab/p02.ipynb"' in out
    assert "Open it" not in media.folder_view("c1", "files/lab/", tmp_path / "lab", tr)  # old callers: unchanged


@pytest.fixture
def launched(monkeypatch):
    got = []
    monkeypatch.setattr(app_mod.subprocess, "Popen", lambda args, **k: got.append(args))
    monkeypatch.setattr(app_mod.subprocess, "run", lambda args, **k: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(app_mod.shutil, "which", lambda name: None)
    return got


def _on(monkeypatch, platform):
    monkeypatch.setattr(app_mod.sys, "platform", platform)


def test_code_goes_to_vs_code_when_it_is_installed(tmp_path, monkeypatch, launched):
    _on(monkeypatch, "linux")
    nb = tmp_path / "p01.ipynb"
    nb.write_text("{}")
    monkeypatch.setattr(app_mod.shutil, "which", lambda name: "/usr/bin/code" if name == "code" else None)
    open_on_desktop(nb)
    assert launched == [["/usr/bin/code", str(nb)]]


def test_a_notebook_opens_in_its_own_app(tmp_path, monkeypatch, launched):
    _on(monkeypatch, "linux")
    nb = tmp_path / "p01.ipynb"
    nb.write_text("{}")
    open_on_desktop(nb)
    assert launched == [["xdg-open", str(nb)]]


def test_a_script_is_never_run(tmp_path, monkeypatch, launched):
    py = tmp_path / "p01.py"
    py.write_text("print(1)")
    _on(monkeypatch, "darwin")
    open_on_desktop(py)
    assert launched[-1] == ["open", "-t", str(py)]  # the text editor, not Python
    _on(monkeypatch, "win32")
    verbs = []
    monkeypatch.setattr(app_mod.os, "startfile", lambda p, *v: verbs.append(v), raising=False)
    open_on_desktop(py)
    assert verbs == [("edit",)]  # Windows' "Edit", never "Open" (which runs it)
    _on(monkeypatch, "linux")
    launched.clear()
    desk = tmp_path / "x.desktop"
    desk.write_text("[Desktop Entry]")
    open_on_desktop(desk)
    assert launched == [["xdg-open", str(tmp_path)]]  # only its folder


def test_show_in_folder_on_each_system(tmp_path, monkeypatch, launched):
    f = tmp_path / "p01.py"
    f.write_text("")
    _on(monkeypatch, "darwin")
    open_on_desktop(f, reveal=True)
    assert launched[-1] == ["open", "-R", str(f)]
    _on(monkeypatch, "win32")
    open_on_desktop(f, reveal=True)
    assert launched[-1] == f'explorer /select,"{f}"'
    _on(monkeypatch, "linux")
    open_on_desktop(f, reveal=True)  # no file manager answered: the folder opens
    assert launched[-1] == ["xdg-open", str(tmp_path)]


def test_the_route_shows_a_course_file_in_its_folder(tmp_path, monkeypatch, launched):
    from tests.test_v127 import _folder_lesson
    _on(monkeypatch, "linux")
    v, c, course, jid = _folder_lesson(tmp_path)
    r = c.post(f"/courses/{course.id}/open-media", data={"media": "01 Intro/01 - Welcome.mp4", "reveal": "1"})
    assert r.json() == {"ok": True} and launched[-1][0] == "xdg-open" and launched[-1][1].endswith("01 Intro")
    assert c.post(f"/courses/{course.id}/open-media", data={"media": "../../etc/passwd", "reveal": "1"}).status_code == 404
