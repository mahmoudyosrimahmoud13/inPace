"""Open inPace in its own app window, not a browser tab.

Tried in this order, first one that works wins:
  1. pywebview (bundled in the Windows and Mac apps)
  2. Linux "with its own engine" download: a Qt WebEngine window (qtwindow.py)
  3. Linux: a small GTK + WebKit window run by the system's Python
     (the .deb installs what it needs: python3-gi and gir1.2-webkit2-4.1).
     It tries normal drawing, then two safer ways, each giving up after a few seconds if the window stays
     blank. The way that works is saved in window.json in the data folder and tried first next time.
  4. Edge, Chrome, Chromium or Brave in "app mode": a plain window with no tabs or address bar
If none works, the caller opens a normal browser tab.

Each opener blocks until the window is closed, then returns True.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

_children: list[subprocess.Popen] = []


def close_children() -> None:
    """Close any window process we started (used by Settings > Quit)."""
    for p in _children:
        try:
            p.terminate()
        except Exception:
            pass


def _clean_env() -> dict:
    """The packaged app points LD_LIBRARY_PATH at its own libraries; give other programs the system ones."""
    env = os.environ.copy()
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
    elif getattr(sys, "frozen", False):
        env.pop("LD_LIBRARY_PATH", None)
    for k in ("PYTHONHOME", "PYTHONPATH", "GI_TYPELIB_PATH", "GDK_PIXBUF_MODULE_FILE", "GTK_PATH", "GIO_MODULE_DIR"):
        env.pop(k, None)
    return env


# ---------- 1. pywebview ----------

def _pywebview(url: str) -> bool:
    try:
        import webview  # type: ignore
    except Exception:
        return False
    if sys.platform.startswith("linux"):
        return False  # on Linux the GTK helper below is more reliable than a bundled GTK
    try:
        try:
            webview.settings["ALLOW_DOWNLOADS"] = True  # exports, backups and records save to Downloads
            webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        except Exception:
            pass
        win = webview.create_window("inPace", url, width=1280, height=860, min_size=(420, 600))
        if sys.platform == "darwin":
            # Mac sends inpace:// links to the running app; show them in this window.
            from .links import mac_listen
            base = url.split("/", 3)
            base = "/".join(base[:3]) + "/"
            listen = lambda: mac_listen(lambda path: win.load_url(base + path))  # noqa: E731
            listen()
            webview.start(listen)
        else:
            webview.start()
        return True
    except Exception as e:
        print(f"pywebview window failed: {e}")
        return False


# ---------- 2. Linux GTK + WebKit helper ----------

LINUX_HELPER = r'''
import os, sys
try:
    import gi
    gi.require_version("Gtk", "3.0")
    for _v in ("4.1", "4.0"):
        try:
            gi.require_version("WebKit2", _v); break
        except ValueError:
            pass
    from gi.repository import Gtk, GLib, WebKit2
except Exception as e:
    print("NOGTK", e, flush=True); sys.exit(3)

url, parent = sys.argv[1], int(sys.argv[2])
splash = sys.argv[3] if len(sys.argv) > 3 else ""
mode = sys.argv[4] if len(sys.argv) > 4 else "safe"   # gpu, safe or soft (see _linux_gtk)
GLib.set_prgname("inpace"); GLib.set_application_name("inPace")

win = Gtk.Window(title="inPace")
win.set_default_size(1280, 860)
win.set_size_request(420, 520)
icon = "/usr/share/icons/hicolor/256x256/apps/inpace.png"
if os.path.exists(icon):
    win.set_icon_from_file(icon)
else:
    win.set_icon_name("inpace")

view = WebKit2.WebView()
s = view.get_settings()
s.set_enable_developer_extras(False)
s.set_javascript_can_access_clipboard(True)
for _name in ("set_enable_media_stream", "set_enable_mediasource", "set_enable_encrypted_media",
              "set_enable_fullscreen", "set_media_playback_requires_user_gesture"):
    try:
        getattr(s, _name)(_name != "set_media_playback_requires_user_gesture")
    except Exception:
        pass
if mode != "gpu":
    try:  # draw on the CPU: avoids blank windows with some graphics drivers
        s.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.NEVER)
    except Exception:
        pass

# The loading screen tells us when it has really drawn a frame. A window that stays gray never sends this,
# so we can give up on this way of drawing after a few seconds instead of leaving people staring at gray.
painted_signal = False
try:
    _ucm = view.get_user_content_manager()
    _ucm.register_script_message_handler("inpace")
    _ucm.connect("script-message-received::inpace", lambda *a: on_painted())
    painted_signal = True
except Exception:
    pass

def outside(uri):
    return not uri.startswith(("http://127.0.0.1", "about:", "data:", "blob:"))

def open_outside(uri):
    try:
        Gtk.show_uri_on_window(win, uri, Gtk.get_current_event_time())
    except Exception:
        os.system("xdg-open '%s' >/dev/null 2>&1 &" % uri.replace("'", ""))

def on_policy(v, decision, kind):
    T = WebKit2.PolicyDecisionType
    if kind in (T.NAVIGATION_ACTION, T.NEW_WINDOW_ACTION):
        action = decision.get_navigation_action()
        uri = action.get_request().get_uri()
        clicked = action.get_navigation_type() in (WebKit2.NavigationType.LINK_CLICKED, WebKit2.NavigationType.FORM_SUBMITTED)
        # Videos from YouTube or Vimeo load inside the lesson; only links you click open in your browser.
        if outside(uri) and (clicked or kind == T.NEW_WINDOW_ACTION):
            decision.ignore(); open_outside(uri); return True
        if kind == T.NEW_WINDOW_ACTION:
            decision.ignore(); v.load_uri(uri); return True
    elif kind == T.RESPONSE:
        resp = decision.get_response()
        cd = ""
        try:
            h = resp.get_http_headers()
            cd = (h.get_one("Content-Disposition") or "") if h else ""
        except Exception:
            pass
        if "attachment" in cd.lower() or not decision.is_mime_type_supported():
            decision.download(); return True
    return False

def downloads_dir():
    try:
        d = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
    except Exception:
        d = None
    d = d or os.path.expanduser("~/Downloads")
    os.makedirs(d, exist_ok=True)
    return d

def toast(text):
    js = "window.inpaceToast ? inpaceToast(%r) : null" % text
    try:
        view.evaluate_javascript(js, -1, None, None, None, None, None)
    except Exception:
        try: view.run_javascript(js, None, None, None)
        except Exception: pass

def on_download(ctx, dl):
    def decide(d, name):
        base, ext = os.path.splitext(os.path.basename(name or "inpace-file"))
        folder = downloads_dir(); path = os.path.join(folder, base + ext); n = 1
        while os.path.exists(path):
            n += 1; path = os.path.join(folder, "%s (%d)%s" % (base, n, ext))
        d.set_destination(GLib.filename_to_uri(path, None)); d._path = path
        return True
    dl.connect("decide-destination", decide)
    dl.connect("finished", lambda d: toast("Saved to Downloads: " + os.path.basename(getattr(d, "_path", ""))))

def on_permission(v, request):
    # The microphone is only used when you press "Record a voice note".
    if isinstance(request, (getattr(WebKit2, "UserMediaPermissionRequest", ()), )) or \
            type(request).__name__ in ("UserMediaPermissionRequest", "MediaKeySystemPermissionRequest"):
        request.allow(); return True
    request.deny(); return True

view.connect("permission-request", on_permission)
view.connect("decide-policy", on_policy)
view.get_context().connect("download-started", on_download)
view.connect("create", lambda v, a: (open_outside(a.get_request().get_uri()) if outside(a.get_request().get_uri()) else v.load_uri(a.get_request().get_uri())) and None)

def parent_alive():
    try:
        os.kill(parent, 0)
        if os.getppid() == parent:
            return True
    except OSError:
        pass
    Gtk.main_quit(); return False

GLib.timeout_add_seconds(1, parent_alive)
win.connect("destroy", Gtk.main_quit)
win.add(view)
state = {"ready": False, "splash": bool(splash), "painted": False}
if splash:  # show "Opening inPace..." at once; the app's page replaces it when it's ready to draw
    view.load_html(splash, "about:blank")
else:
    state["painted"] = True
    view.load_uri(url)

def on_painted():
    if state["painted"]:
        return
    state["painted"] = True
    print("PAINTED", flush=True)
    if state["splash"]:
        state["splash"] = False
        view.load_uri(url)

def on_load(v, event):
    if state["splash"]:
        if event == WebKit2.LoadEvent.FINISHED and not painted_signal:
            on_painted()
        return
    # "Ready" as soon as the page starts showing: waiting for every picture to finish loading made a slow
    # first start look like a broken window, and inPace then moved to a browser window.
    if event in (WebKit2.LoadEvent.COMMITTED, WebKit2.LoadEvent.FINISHED) and not state["ready"]:
        state["ready"] = True
        print("READY", flush=True)

def on_crash(v, reason=None):
    # The page's helper process stopped (a WebKit crash, or it ran out of memory). Load the page again in this
    # same window instead of giving up: before, inPace closed the window and reopened in the browser.
    import time
    now = time.time()
    state["crashes"] = [t for t in state.get("crashes", []) if now - t < 60] + [now]
    print("CRASH", getattr(reason, "value_nick", reason), flush=True)
    if not state["ready"] or len(state["crashes"]) >= 3:  # crashed before showing anything, or keeps crashing:
        os._exit(4)                                        # try another way of drawing right away
    GLib.timeout_add(400, lambda: (v.reload(), False)[1])

def no_paint():
    if not state["painted"]:
        print("NOPAINT", flush=True)
        os._exit(6)
    return False

def too_slow():
    if not state["ready"]:
        print("SLOW", flush=True)
        os._exit(5)
    return False

def on_failed(v, event, uri, error):
    # The app's server may still be starting (the window now opens at the same time): try again shortly.
    if not state["ready"] and uri.startswith("http://127.0.0.1") and state.setdefault("tries", 0) < 100:
        state["tries"] += 1
        GLib.timeout_add(250, lambda: (v.load_uri(url), False)[1])
        return True
    return False

view.connect("load-changed", on_load)
view.connect("load-failed", on_failed)
view.connect("web-process-terminated", on_crash)
GLib.timeout_add_seconds(int(os.environ.get("INPACE_PAINT_WAIT", "4")), no_paint)
GLib.timeout_add_seconds(60, too_slow)
win.show_all()
Gtk.main()
'''


def _log(home: Path | None, line: str) -> None:
    print(line)
    if home:
        try:
            with open(home / "window.log", "a", encoding="utf-8") as f:
                import time
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")
        except OSError:
            pass


def splash_html() -> str:
    """What the window shows while inPace's first page loads: Tempo, a moving bar, in both languages."""
    try:
        from .mascot import mascot
        tempo = str(mascot("read", 150, "Tempo"))
    except Exception:
        tempo = ""
    return ("<!doctype html><html><head><meta charset='utf-8'><style>"
            "html,body{margin:0;height:100%;background:#F7F3EA;color:#111;font:600 18px system-ui,sans-serif}"
            "@media (prefers-color-scheme:dark){html,body{background:#12110E;color:#F2EDE2}}"
            "body{display:grid;place-items:center}.b{display:flex;flex-direction:column;align-items:center;gap:14px}"
            ".bar{width:220px;height:10px;border:2.5px solid currentColor;overflow:hidden}"
            ".bar i{display:block;width:40%;height:100%;background:#FFD43B;animation:m 1.1s ease-in-out infinite}"
            "@keyframes m{0%{transform:translateX(-100%)}100%{transform:translateX(250%)}}"
            "@media (prefers-reduced-motion:reduce){.bar i{animation:none;width:100%}}"
            "small{font-weight:500;opacity:.75}</style></head><body><div class='b'>" + tempo +
            "<div>Opening inPace…</div><div class='bar'><i></i></div><small dir='rtl'>جارٍ فتح inPace…</small>"
            "</div><script>requestAnimationFrame(function(){requestAnimationFrame(function(){"
            "try{window.webkit.messageHandlers.inpace.postMessage('painted')}catch(e){}})})</script>"
            "</body></html>")


# Ways the GTK window can draw, tried in this order the first time. The one that works is remembered.
#   gpu   WebKit's normal drawing, with the graphics card (fastest, and what new WebKit versions expect)
#   safe  no graphics card: the fix for blank windows with some drivers (NVIDIA, VMs) on older WebKit
#   soft  like safe, and also software OpenGL for everything (last try before the browser window)
GTK_MODES = ("gpu", "safe", "soft")
_FAILED = {3: "GTK or WebKit isn't installed", 4: "the page engine crashed", 5: "the page took too long",
           6: "the window stayed blank"}


def _mode_env(mode: str) -> dict:
    env = _clean_env()
    if mode in ("safe", "soft"):
        env.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
        env.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")
    if mode == "soft":
        env.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    return env


def _memory_file(home: Path | None) -> Path | None:
    return (home / "window.json") if home else None


def remembered(home: Path | None) -> dict:
    """What worked last time: {"version": "1.29.0", "way": "gpu" | "safe" | "soft" | "qt" | "qt-soft" | "app"}."""
    f = _memory_file(home)
    try:
        import json
        data = json.loads(f.read_text(encoding="utf-8")) if f else {}
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def remember(home: Path | None, way: str) -> None:
    f = _memory_file(home)
    if not f or remembered(home).get("way") == way:
        return
    try:
        import json
        from . import __version__
        f.write_text(json.dumps({"version": __version__, "way": way}), encoding="utf-8")
    except OSError:
        pass


def forget(home: Path | None) -> None:
    f = _memory_file(home)
    if f:
        try:
            f.unlink()
        except OSError:
            pass


def _order(modes: tuple[str, ...], home: Path | None) -> list[str]:
    last = remembered(home).get("way")
    return ([last] if last in modes else []) + [m for m in modes if m != last]


def _run_helper(cmd: list[str], env: dict, home: Path | None, name: str, on_ready=None) -> str:
    """Start one window and wait until it closes. Returns "closed" when it showed inPace (or the person closed
    it before that), otherwise the reason it failed. on_ready runs as soon as inPace shows in it."""
    try:
        p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        return f"couldn't start ({e})"
    _children.append(p)
    ready = threading.Event()
    errors: list[str] = []

    def watch_out():
        assert p.stdout
        for line in p.stdout:
            if line.startswith("READY"):
                ready.set()
                if on_ready:
                    on_ready()
            elif line.startswith("NOGTK"):
                _log(home, "App window needs: sudo apt install python3-gi gir1.2-webkit2-4.1 (" + line.strip() + ")")
            elif line.startswith("CRASH") and ready.is_set():
                _log(home, f"App window ({name}): {line.strip()} (reloading the page)")
        ready.set()  # stream closed

    def watch_err():
        assert p.stderr
        for line in p.stderr:  # WebKit and Qt say why they can't draw here; keep the last few lines for the log
            line = line.strip()
            if line:
                errors.append(line[:300])
                del errors[:-6]

    threading.Thread(target=watch_out, daemon=True).start()
    threading.Thread(target=watch_err, daemon=True).start()
    ready.wait(75)
    if p.poll() is None and not ready.is_set():
        p.kill()
    code = p.wait()
    if code in (0, -15):
        return "closed"
    why = _FAILED.get(code, f"it stopped (code {code})")
    if errors:
        why += " | " + " / ".join(errors)
    return why


def _linux_gtk(url: str, home: Path | None = None) -> bool:
    if not sys.platform.startswith("linux"):
        return False
    py = shutil.which("python3", path="/usr/bin:/bin") or "/usr/bin/python3"
    if not os.path.exists(py):
        return False
    splash = splash_html()
    for mode in _order(GTK_MODES, home):
        why = _run_helper([py, "-I", "-c", LINUX_HELPER, url, str(os.getpid()), splash, mode],
                          _mode_env(mode), home, f"gtk-{mode}", on_ready=lambda m=mode: remember(home, m))
        if why == "closed":
            return True
        _log(home, f"App window, {mode} drawing: {why}")
        if why.startswith("GTK or WebKit isn't installed"):
            break
    return False


# ---------- 2b. Linux "with its own engine" download: Qt WebEngine ----------

QT_MODES = ("qt", "qt-soft")


def _qt_cmd() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--qt-window"]
    return [sys.executable, "-m", "inpace", "--qt-window"]


def _linux_qt(url: str, home: Path | None = None) -> bool:
    if not sys.platform.startswith("linux"):
        return False
    from .qtwindow import available, prepare_env
    if not available():
        return False
    splash = splash_html()
    for mode in _order(QT_MODES, home):
        env = prepare_env(os.environ.copy(), mode)  # the bundled engine wants the bundle's own libraries
        why = _run_helper(_qt_cmd() + [url, str(os.getpid()), splash, mode], env, home, mode,
                          on_ready=lambda m=mode: remember(home, m))
        if why == "closed":
            return True
        _log(home, f"App window, {mode}: {why}")
    return False


# ---------- 3. A Chromium-family browser in app mode ----------

def _app_mode_browsers() -> list[str]:
    found: list[str] = []
    names = ["microsoft-edge", "msedge", "google-chrome", "google-chrome-stable", "chromium",
             "chromium-browser", "brave-browser", "brave"]
    for n in names:
        p = shutil.which(n)
        if p:
            found.append(p)
    if sys.platform == "win32":
        for base in (os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", ""),
                     os.environ.get("LOCALAPPDATA", "")):
            for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                        r"BraveSoftware\Brave-Browser\Application\brave.exe"):
                p = Path(base) / rel
                if base and p.exists():
                    found.append(str(p))
    elif sys.platform == "darwin":
        for app, exe in (("Google Chrome", "Google Chrome"), ("Microsoft Edge", "Microsoft Edge"),
                         ("Chromium", "Chromium"), ("Brave Browser", "Brave Browser")):
            for root in ("/Applications", str(Path.home() / "Applications")):
                p = Path(root) / f"{app}.app" / "Contents" / "MacOS" / exe
                if p.exists():
                    found.append(str(p))
    return list(dict.fromkeys(found))


def _app_mode(url: str, home: Path) -> bool:
    if sys.platform.startswith("linux") and _app_mode_browsers():
        remember(home, "app")
    for exe in _app_mode_browsers():
        profile = home / "window"
        profile.mkdir(parents=True, exist_ok=True)
        try:
            p = subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run",
                                  "--no-default-browser-check", "--window-size=1280,860"],
                                 env=_clean_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            continue
        _children.append(p)
        p.wait()
        return True
    return False


def which() -> str:
    """Which window inPace would use here (for checks; opens nothing)."""
    if not sys.platform.startswith("linux"):
        try:
            import webview  # type: ignore  # noqa: F401
            if sys.platform == "win32":
                import clr  # type: ignore  # noqa: F401  (pythonnet, needed for the Edge window)
            elif sys.platform == "darwin":
                import WebKit  # type: ignore  # noqa: F401
            return "pywebview"
        except Exception as e:
            print(f"pywebview not usable: {e}", file=sys.stderr)
    if sys.platform.startswith("linux"):
        if (Path(sys.executable).parent / "inpace-full").exists() or not getattr(sys, "frozen", False):
            try:  # the "with its own engine" download: say why its engine can't load, if it can't
                import PySide6.QtWebEngineWidgets  # type: ignore  # noqa: F401
                return "qt"
            except Exception as e:
                if getattr(sys, "frozen", False):
                    print(f"Qt window not usable: {e}", file=sys.stderr)
        py = "/usr/bin/python3"
        if os.path.exists(py):
            r = subprocess.run([py, "-I", "-c", "import gi; gi.require_version('Gtk','3.0');"
                                "from gi.repository import Gtk;\n"
                                "try:\n gi.require_version('WebKit2','4.1')\nexcept ValueError:\n gi.require_version('WebKit2','4.0')\n"
                                "from gi.repository import WebKit2"],
                               env=_clean_env(), capture_output=True)
            if r.returncode == 0:
                return "gtk"
    if _app_mode_browsers():
        return "app-mode browser"
    return "browser tab"


def open_window(url: str, home: Path) -> bool:
    """Show inPace in a window and wait until it's closed. False means: use a browser tab."""
    choice = os.environ.get("INPACE_WINDOW", "").lower()  # qt, gtk, app, pywebview, browser or reset
    if choice == "reset":  # forget what worked before and try every way again
        forget(home)
        choice = ""
    if choice == "browser":
        return False
    if choice == "app":
        return _app_mode(url, home)
    if choice == "gtk":
        return _linux_gtk(url, home) or _app_mode(url, home)
    if choice == "qt":
        return _linux_qt(url, home) or _app_mode(url, home)
    if not sys.platform.startswith("linux"):
        return _pywebview(url) or _app_mode(url, home)

    # Linux. If no app window worked last time, go straight to the browser window: no waiting at every start.
    # After an update inPace tries its own window again, since the update may have fixed it.
    from . import __version__
    last = remembered(home)
    if last.get("way") == "app" and last.get("version") == __version__ and _app_mode(url, home):
        return True
    if _linux_qt(url, home) or _linux_gtk(url, home):
        return True
    if _app_mode(url, home):
        if _app_mode_browsers():
            _log(home, "Using the browser's app window. To try inPace's own window again: INPACE_WINDOW=reset inpace")
        return True
    return False
