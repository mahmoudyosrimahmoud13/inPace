"""v1.23: faster (the window keeps inPace's own files, sample courses are read once, the phone keeps compiled
libraries), and it moves like an app (tabs, Back, pages that update in place)."""
import html
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from starlette.testclient import TestClient

import inpace.app as app_mod
from inpace.app import create_app
from inpace.vault import Vault

ROOT = Path(__file__).resolve().parent.parent


def client(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    return v, c


def test_the_window_keeps_inpaces_own_files(tmp_path):
    v, c = client(tmp_path)
    page = c.get("/")
    assert page.headers["cache-control"] == "no-store"  # pages are always fresh
    import re
    css = re.search(r'href="(/static/style\.css\?v=\d+)"', page.text).group(1)
    js = re.search(r'src="(/static/app\.js\?v=\d+)"', page.text).group(1)
    for url in (css, js):
        assert c.get(url).headers["cache-control"] == "public, max-age=31536000, immutable"
    assert c.get("/static/icon.svg").headers["cache-control"] == "public, max-age=86400"


def test_sample_courses_are_read_once(tmp_path, monkeypatch):
    v, c = client(tmp_path)
    app_mod._SAMPLE_CACHE.clear()
    calls = []
    real = app_mod.load_course
    monkeypatch.setattr(app_mod, "load_course", lambda files: calls.append(1) or real(files))
    first = c.get("/courses").text
    n = len(calls)
    assert n >= 1 and "python-basics" in first
    assert c.get("/courses").status_code == 200 and len(calls) == n
    # Adding a sample still works, and it leaves the list of samples.
    c.post("/courses/sample/python-basics")
    assert 'action="/courses/sample/python-basics"' not in c.get("/courses").text
    assert 'action="/courses/sample/fastapi"' in c.get("/courses").text


def test_pages_that_update_in_place_are_marked(tmp_path):
    v, c = client(tmp_path)
    c.post("/courses/sample/python-basics")
    jid = c.post("/courses/python-basics/start", follow_redirects=False).headers["location"].rsplit("/", 1)[-1]
    for url in ("/", f"/learn/{jid}"):
        page = html.unescape(c.get(url).text)
        assert page.count('id="live-page" data-live') == 1
    assert 'id="live-page"' not in c.get("/settings").text  # pages with forms and players load whole
    script = (ROOT / "inpace" / "static" / "app.js").read_text(encoding="utf-8")
    assert "window.inpaceBack" in script and "window.inpaceRefresh" in script
    assert "pagereveal" in (ROOT / "inpace" / "templates" / "base.html").read_text(encoding="utf-8")


PHONE = '''
import os, sys, runpy, threading, time, urllib.request
home, libs, port, src = sys.argv[1:5]
sys.path[:0] = [libs]
os.environ.update(INPACE_HOME=home, INPACE_PORT=port, INPACE_LIBS_WAIT="0")
def stop():
    for _ in range(600):
        time.sleep(0.05)
        done = any(os.path.isfile(os.path.join(home, "cache", "libs", d, ".ok"))
                   for d in (os.listdir(os.path.join(home, "cache", "libs")) if os.path.isdir(os.path.join(home, "cache", "libs")) else []))
        try:
            up = urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=1).status == 200
        except Exception:
            up = False
        if up and (done or os.environ.get("NO_WAIT")):
            import fakelib
            print("FAKELIB", fakelib.__file__, flush=True)
            os._exit(0)
    os._exit(3)
threading.Thread(target=stop, daemon=True).start()
sys.argv = ["main.py"]
runpy.run_path(src, run_name="__main__")
'''


def _free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_phone_start_keeps_compiled_libraries(tmp_path):
    """The phone's start file, run here with a stand-in library zip: the first start reads the zip and makes a
    compiled copy, the next start uses the copy, and a broken copy is thrown away without stopping the app."""
    main = (ROOT / "mobile" / "app" / "src" / "main.py").read_text(encoding="utf-8")
    main = main.replace('PURE = ("uvicorn",', 'PURE = ("fakelib", "uvicorn",')  # a stand-in library we control
    src = tmp_path / "main.py"
    src.write_text(main, encoding="utf-8")
    libs = tmp_path / "sitepackages.zip"
    with zipfile.ZipFile(libs, "w") as z:
        z.writestr("fakelib/__init__.py", "VALUE = 1\n")
        z.writestr("fakelib/data.txt", "kept")
    runner = tmp_path / "runner.py"
    runner.write_text(PHONE, encoding="utf-8")
    home = tmp_path / "home"
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}

    def start(**more):
        r = subprocess.run([sys.executable, str(runner), str(home), str(libs), str(_free_port()), str(src)],
                           env={**env, **more}, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout

    assert f"FAKELIB {libs}" in start()  # first start: from the zip, and the copy gets made
    copies = [d for d in (home / "cache" / "libs").iterdir() if (d / ".ok").is_file()]
    assert len(copies) == 1 and (copies[0] / "fakelib" / "data.txt").read_text() == "kept"
    assert list((copies[0] / "fakelib").glob("__pycache__/*.pyc"))  # already compiled
    assert f"FAKELIB {copies[0]}" in start(NO_WAIT="1")  # next start: from the compiled copy
    # A copy that can't be imported is dropped, and the app starts from the zip.
    (copies[0] / "uvicorn").mkdir()
    (copies[0] / "uvicorn" / "__init__.py").write_text("this is ( not python\n")
    out = start(NO_WAIT="1")
    assert f"FAKELIB {libs}" in out and not (home / "start-error.txt").exists()
