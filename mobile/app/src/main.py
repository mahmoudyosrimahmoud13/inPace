"""inPace on Android: start the same inPace web app the desktop uses, for the Flutter shell to show.

The Flutter side passes INPACE_HOME (a private folder of the app) and INPACE_PORT, then opens
http://127.0.0.1:<port>/ in a web view once /ping answers. If anything fails while starting, the reason is
written to <INPACE_HOME>/start-error.txt and the app's error screen shows it.

Starting fast (v1.23). On a phone, Python reads its libraries from a zip file and has to compile every one of them
again on each start, which is most of the waiting. Two things avoid that, both plain Python and both safe to lose:

1. Python may keep compiled copies of inPace's own code (the runner turns that off; we turn it back on).
2. After the app is up, a background thread copies the pure-Python libraries out of the zip into
   <INPACE_HOME>/cache/libs/<stamp>/ and compiles them there. The next start imports them from that folder,
   already compiled. The stamp is the zip's size and date, so an app update makes a new copy. If importing from
   the copy ever fails, the copy is thrown away and the libraries are imported from the zip as before.
"""
import os
import sys
import traceback

os.environ.setdefault("INPACE_MOBILE", "android")  # no desktop window, no desktop updater
sys.dont_write_bytecode = False

home = os.environ.get("INPACE_HOME") or os.path.join(os.getcwd(), "inPace")
port = int(os.environ.get("INPACE_PORT", "8765"))

# Libraries with no compiled (native) parts. The others (PyNaCl, PyYAML, MarkupSafe, cffi) stay in the zip,
# where the phone's own loader finds their native parts.
PURE = ("uvicorn", "starlette", "jinja2", "click", "h11", "anyio", "idna", "markdown_it", "mdurl", "pygments",
        "pypdf", "multipart", "python_multipart", "certifi", "typing_extensions.py")


def _libs_zip():
    return next((p for p in sys.path if p.endswith("sitepackages.zip") and os.path.isfile(p)), None)


def _libs_copy(zip_path):
    st = os.stat(zip_path)
    return os.path.join(home, "cache", "libs", f"{st.st_size}-{int(st.st_mtime)}")


def use_fast_libs():
    """Put the compiled copy of the libraries first, if a complete one is there. Returns its folder or None."""
    try:
        zp = _libs_zip()
        if not zp:
            return None
        copy = _libs_copy(zp)
        if not os.path.isfile(os.path.join(copy, ".ok")):
            return None
        sys.path.insert(sys.path.index(zp), copy)
        return copy
    except Exception:
        return None


def drop_fast_libs(copy, before):
    """Importing from the copy failed: forget it and everything half-imported, so the zip is used instead."""
    try:
        os.remove(os.path.join(copy, ".ok"))
    except OSError:
        pass
    while copy in sys.path:
        sys.path.remove(copy)
    for name in [n for n in sys.modules if n not in before]:
        del sys.modules[name]
    import importlib
    importlib.invalidate_caches()


def make_fast_libs(wait=12.0):
    """In the background, a little at a time: copy the pure-Python libraries out of the zip and compile them."""
    import threading

    def work():
        import py_compile
        import shutil
        import time
        import zipfile
        tmp = ""
        try:
            time.sleep(wait)  # let the first pages load first
            zp = _libs_zip()
            if not zp:
                return
            copy = _libs_copy(zp)
            root = os.path.dirname(copy)
            if os.path.isfile(os.path.join(copy, ".ok")):
                return
            tmp = copy + ".tmp"
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.rmtree(copy, ignore_errors=True)
            os.makedirs(tmp, exist_ok=True)
            sources = []
            with zipfile.ZipFile(zp) as z:
                for info in z.infolist():
                    name = info.filename
                    top = name.split("/", 1)[0]
                    if top not in PURE or info.is_dir() or "__pycache__" in name or ".." in name or name.endswith(".pyc"):
                        continue
                    if name.endswith((".so", ".soref", ".pyd")):
                        raise RuntimeError("native part in a pure library: " + name)
                    target = os.path.join(tmp, *name.split("/"))
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with z.open(info) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    if name.endswith(".py"):
                        sources.append(target)
                    time.sleep(0.002)
            if not sources:
                raise RuntimeError("no libraries found in the zip")
            for path in sources:
                try:
                    py_compile.compile(path, doraise=True, quiet=1)
                except Exception:
                    pass  # Python compiles that one itself when it's first used
                time.sleep(0.005)
            os.rename(tmp, copy)
            with open(os.path.join(copy, ".ok"), "w") as f:
                f.write("ok")
            for other in os.listdir(root):  # copies made for older versions of the app
                if os.path.join(root, other) != copy:
                    shutil.rmtree(os.path.join(root, other), ignore_errors=True)
        except Exception:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    threading.Thread(target=work, daemon=True, name="inpace-fast-libs").start()


def load():
    import uvicorn

    from inpace.app import create_app
    from inpace.offline import start_auto_updates
    from inpace.vault import Vault
    return uvicorn, create_app, start_auto_updates, Vault


try:
    before = set(sys.modules)
    fast = use_fast_libs()
    try:
        uvicorn, create_app, start_auto_updates, Vault = load()
    except Exception:
        if not fast:
            raise
        drop_fast_libs(fast, before)
        uvicorn, create_app, start_auto_updates, Vault = load()

    start_auto_updates(home)  # yt-dlp for offline YouTube lessons: a new copy once a day, if you chose that
    app = create_app(Vault(home))
    make_fast_libs(float(os.environ.get("INPACE_LIBS_WAIT", "12")))

    # h11 and asyncio are pure Python, so they work everywhere (uvloop and httptools need compiled parts).
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", loop="asyncio", http="h11")
except BaseException:
    try:
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, "start-error.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
    except Exception:
        pass
    raise
