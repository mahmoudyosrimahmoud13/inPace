"""The app window of the Linux "with its own engine" download (inPace-linux-full).

It uses Qt WebEngine (Chromium), which ships inside that download, so the window works the same on every
Linux, whatever WebKit version the system has. window.py starts it as a separate process:

    inPace --qt-window URL PARENT_PID SPLASH_HTML MODE

and reads what it prints, just like the GTK window: PAINTED, READY, CRASH. Exit codes match the GTK helper
(3 Qt missing, 4 crashed, 5 too slow, 6 stayed blank).
MODE is "qt" (normal, with the graphics card) or "qt-soft" (no graphics card).
"""
from __future__ import annotations

import os
import sys


def available() -> bool:
    try:
        import PySide6.QtWebEngineWidgets  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def userns_restricted() -> bool:
    """Ubuntu 24.04 and newer (also Zorin 18, Pop!_OS 24.04) block the sandbox Chromium normally uses."""
    try:
        with open("/proc/sys/kernel/apparmor_restrict_unprivileged_userns") as f:
            return f.read().strip() == "1"
    except OSError:
        return False


def prepare_env(env: dict, mode: str) -> dict:
    flags = env.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
    if mode == "qt-soft":
        flags += ["--disable-gpu", "--disable-gpu-compositing"]
        env["QT_QUICK_BACKEND"] = "software"
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
    if userns_restricted() or mode == "qt-soft" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        # Without it Chromium can't start its page process there. inPace only shows its own local pages and
        # the YouTube or Vimeo players inside lessons, and links you click open in your normal browser.
        env["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
    env["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(dict.fromkeys(flags))
    env.setdefault("QT_QPA_PLATFORM", "wayland;xcb")
    return env


def main(argv: list[str]) -> None:
    url, parent = argv[0], int(argv[1])
    splash = argv[2] if len(argv) > 2 else ""
    mode = argv[3] if len(argv) > 3 else "qt"
    prepare_env(os.environ, mode)  # type: ignore[arg-type]
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QDesktopServices, QIcon
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWidgets import QApplication
    except Exception as e:
        print("NOGTK", e, flush=True)
        sys.exit(3)

    app = QApplication(["inpace"])
    app.setApplicationName("inpace")  # matches StartupWMClass=inpace in inpace.desktop
    app.setDesktopFileName("inpace")  # taskbar icon and grouping come from inpace.desktop
    for icon in ("/usr/share/icons/hicolor/256x256/apps/inpace.png",
                 os.path.join(os.path.dirname(sys.executable), "icon.png")):
        if os.path.exists(icon):
            app.setWindowIcon(QIcon(icon))
            break

    state = {"ready": False, "painted": not splash, "splash": bool(splash), "crashes": []}

    def outside(u: str) -> bool:
        return not u.startswith(("http://127.0.0.1", "about:", "data:", "blob:"))

    class Page(QWebEnginePage):
        def acceptNavigationRequest(self, qurl, kind, main_frame):  # noqa: N802 (Qt's name)
            u = qurl.toString()
            if outside(u) and kind == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                QDesktopServices.openUrl(qurl)
                return False
            return super().acceptNavigationRequest(qurl, kind, main_frame)

        def createWindow(self, kind):  # noqa: N802  links that ask for a new window open in the browser
            helper = QWebEnginePage(self)
            helper.urlChanged.connect(lambda q: (QDesktopServices.openUrl(q) if outside(q.toString())
                                                 else view.load(q), helper.deleteLater()))
            return helper

        def featurePermissionRequested(self, origin, feature):  # noqa: N802  microphone for voice notes
            self.setFeaturePermission(origin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)

    profile = QWebEngineProfile.defaultProfile()

    def on_download(item):
        from pathlib import Path
        folder = Path.home() / "Downloads"
        folder.mkdir(exist_ok=True)
        name = item.downloadFileName() or "inpace-file"
        base, ext = os.path.splitext(name)
        path, n = folder / name, 1
        while path.exists():
            n += 1
            path = folder / f"{base} ({n}){ext}"
        item.setDownloadDirectory(str(folder))
        item.setDownloadFileName(path.name)
        item.accept()
        item.isFinishedChanged.connect(lambda: view.page().runJavaScript(
            "window.inpaceToast && inpaceToast(%r)" % ("Saved to Downloads: " + path.name)))

    profile.downloadRequested.connect(on_download)

    view = QWebEngineView()
    page = Page(profile, view)
    view.setPage(page)
    st = page.settings()
    st.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
    st.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
    st.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
    page.fullScreenRequested.connect(lambda r: (r.accept(), view.showFullScreen() if r.toggleOn() else view.showNormal()))
    view.setWindowTitle("inPace")
    view.resize(1280, 860)
    view.setMinimumSize(420, 520)

    def painted():
        if not state["painted"]:
            state["painted"] = True
            print("PAINTED", flush=True)
        if state["splash"]:
            state["splash"] = False
            view.load(QUrl(url))

    tries = {"n": 0}

    def on_loaded(ok: bool):
        if state["splash"]:
            # Wait for the loading screen's first frame before moving on (Qt draws the frame just after this).
            QTimer.singleShot(50, painted)
            return
        if ok and not state["ready"]:
            state["ready"] = True
            print("READY", flush=True)
        elif not ok and not state["ready"] and tries["n"] < 100:  # the app's server is still starting
            tries["n"] += 1
            QTimer.singleShot(250, lambda: view.load(QUrl(url)))

    page.loadFinished.connect(on_loaded)

    def on_crash(status, code):
        import time
        now = time.time()
        state["crashes"] = [t for t in state["crashes"] if now - t < 60] + [now]
        print("CRASH", int(code), flush=True)
        if not state["ready"] or len(state["crashes"]) >= 3:
            os._exit(4)
        QTimer.singleShot(400, view.reload)

    page.renderProcessTerminated.connect(on_crash)

    def checks():
        try:
            os.kill(parent, 0)
        except OSError:
            app.quit()

    alive = QTimer()
    alive.timeout.connect(checks)
    alive.start(1000)

    def no_paint():
        if not state["painted"]:
            print("NOPAINT", flush=True)
            os._exit(6)

    def too_slow():
        if not state["ready"]:
            print("SLOW", flush=True)
            os._exit(5)

    QTimer.singleShot(int(os.environ.get("INPACE_PAINT_WAIT", "8")) * 1000, no_paint)
    QTimer.singleShot(60_000, too_slow)
    if splash:
        view.setHtml(splash, QUrl("about:blank"))
    else:
        view.load(QUrl(url))
    view.show()
    app.exec()
    sys.exit(0)
