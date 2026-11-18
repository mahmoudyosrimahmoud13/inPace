"""1.29: the Linux window tries several ways of drawing and remembers the one that works;
a second Linux download carries its own engine (Qt WebEngine)."""
import json
import sys
from pathlib import Path

from inpace import updater, window


def test_remembers_and_orders(tmp_path):
    assert window.remembered(tmp_path) == {}
    assert window._order(window.GTK_MODES, tmp_path) == ["gpu", "safe", "soft"]
    window.remember(tmp_path, "safe")
    assert json.loads((tmp_path / "window.json").read_text())["way"] == "safe"
    assert window._order(window.GTK_MODES, tmp_path) == ["safe", "gpu", "soft"]
    window.forget(tmp_path)
    assert window.remembered(tmp_path) == {}


def test_broken_memory_file_is_ignored(tmp_path):
    (tmp_path / "window.json").write_text("not json")
    assert window.remembered(tmp_path) == {}
    assert window._order(window.QT_MODES, tmp_path) == ["qt", "qt-soft"]


def test_mode_env():
    assert "WEBKIT_DISABLE_DMABUF_RENDERER" not in window._mode_env("gpu") or \
        __import__("os").environ.get("WEBKIT_DISABLE_DMABUF_RENDERER")
    assert window._mode_env("safe")["WEBKIT_DISABLE_COMPOSITING_MODE"] == "1"
    assert window._mode_env("soft")["LIBGL_ALWAYS_SOFTWARE"] == "1"


def test_helper_knows_modes_and_blank_check():
    h = window.LINUX_HELPER
    assert 'mode != "gpu"' in h and "NOPAINT" in h and "messageHandlers" not in h
    assert "messageHandlers.inpace" in window.splash_html()
    assert window._FAILED[6] == "the window stayed blank"


def test_helper_failure_reason(tmp_path):
    why = window._run_helper([sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(6)"],
                             {}, tmp_path, "test")
    assert why.startswith("the window stayed blank") and "boom" in why
    assert window._run_helper([sys.executable, "-c", "print('READY')"], {}, tmp_path, "test") == "closed"


def test_on_ready_called(tmp_path):
    seen = []
    window._run_helper([sys.executable, "-c", "print('READY', flush=True)"], {}, tmp_path, "t",
                       on_ready=lambda: seen.append(1))
    assert seen == [1]


def test_qt_env(monkeypatch):
    from inpace import qtwindow
    monkeypatch.setattr(qtwindow, "userns_restricted", lambda: True)
    env = qtwindow.prepare_env({}, "qt")
    assert env["QTWEBENGINE_DISABLE_SANDBOX"] == "1" and env["QT_QPA_PLATFORM"] == "wayland;xcb"
    env = qtwindow.prepare_env({}, "qt-soft")
    assert "--disable-gpu" in env["QTWEBENGINE_CHROMIUM_FLAGS"]


def test_full_download_updates_to_full(tmp_path, monkeypatch):
    exe = tmp_path / "inPace" / "inPace"
    exe.parent.mkdir()
    exe.write_text("")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "linux")
    assert updater.install_kind() == "folder"
    (exe.parent / updater.FULL_MARK).write_text("")
    assert updater.install_kind() == "folder-full"
    assert updater.ASSETS["folder-full"] == "inPace-linux-full.tar.gz"
    assert updater.ASSETS["deb-full"] == "inPace-linux-full.deb"


def test_release_and_site_list_both_linux_downloads():
    root = Path(__file__).resolve().parent.parent
    wf = (root / ".github/workflows/release.yml").read_text()
    assert "inPace-linux-full.deb" in wf and "--full" in wf and "WANT=qt" in wf
    site = (root / "site/index.html").read_text()
    assert site.count("inPace-linux-full") == 2
