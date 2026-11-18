"""Keep the installed app up to date: check GitHub for a newer release, download it, check it, install it.

Only the installed apps update themselves (Windows, Mac, the Linux .deb and the Linux folder).
Running from the code folder (`python -m inpace`) updates with `git pull` instead.

How each one installs:
  Windows      the new inPace.exe takes the place of the old one (the old one is renamed, then removed later)
  Mac          the new inPace.app takes the place of the old one
  Linux .deb   `pkexec apt-get install` (your computer asks for your password, as for any install)
  Linux folder the new inPace file takes the place of the old one
Every download is checked against SHA256SUMS from the same release before anything is replaced.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from . import __version__

REPO = "mahmoudyosrimahmoud13/inpace"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_EVERY = 20 * 3600
ASSETS = {"deb": "inPace-linux.deb", "folder": "inPace-linux.tar.gz", "windows": "inPace-setup.exe",
          "mac": "inPace-mac.dmg",
          # The Linux download "with its own engine" (Qt WebEngine inside): it updates to the same kind
          "deb-full": "inPace-linux-full.deb", "folder-full": "inPace-linux-full.tar.gz",
          "appimage": "inPace-linux.AppImage", "appimage-full": "inPace-linux-full.AppImage"}
FULL_MARK = "inpace-full"  # a file next to the program in the "with its own engine" download


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_kind() -> str:
    """source, deb, folder, appimage (each also "-full"), windows, mac or android."""
    if os.environ.get("INPACE_MOBILE") == "android":
        return "android"
    if not is_frozen():
        return "source"
    exe = Path(sys.executable).resolve()
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    if os.environ.get("APPIMAGE"):  # running from an AppImage: that one file is what gets updated
        kind = "appimage"
    else:
        kind = "deb" if str(exe).startswith("/opt/inpace/") else "folder"
    return kind + "-full" if (exe.parent / FULL_MARK).exists() else kind


def version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def newer(latest: str, current: str = __version__) -> bool:
    return version_tuple(latest) > version_tuple(current)


def _get(url: str, timeout: float = 15):
    req = urllib.request.Request(url, headers={"User-Agent": f"inPace/{__version__}",
                                               "Accept": "application/vnd.github+json"})
    from .net import urlopen
    return urlopen(req, timeout=timeout)


def check() -> dict | None:
    """The newest release, if it's newer than this one: {version, page, assets: {name: url}}."""
    with _get(API) as r:
        data = json.loads(r.read().decode("utf-8"))
    tag = str(data.get("tag_name") or "")
    if not tag or data.get("draft") or data.get("prerelease") or not newer(tag):
        return None
    return {"version": tag.lstrip("v"), "page": data.get("html_url", ""),
            "assets": {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}}


def _download(url: str, dest: Path) -> None:
    with _get(url, timeout=60) as r, open(dest, "wb") as out:
        shutil.copyfileobj(r, out, 1024 * 1024)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class NotReady(RuntimeError):
    """The new release is still being put together (its files arrive a few minutes apart)."""


def download(release: dict, kind: str, folder: Path) -> Path:
    """Download this computer's file from the release and make sure it's exactly what was published."""
    name = ASSETS.get(kind, "")
    if not name or name not in release["assets"] or "SHA256SUMS" not in release["assets"]:
        raise NotReady("This release doesn't have a download for this computer yet.")
    folder.mkdir(parents=True, exist_ok=True)
    sums = folder / "SHA256SUMS"
    _download(release["assets"]["SHA256SUMS"], sums)
    expected = None
    for line in sums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            expected = parts[0].lower()
    if not expected:
        raise RuntimeError("The release's checksum list doesn't mention this download.")
    dest = folder / name
    _download(release["assets"][name], dest)
    if _sha256(dest) != expected:
        dest.unlink(missing_ok=True)
        raise RuntimeError("The download didn't match the published checksum, so it wasn't installed.")
    return dest


# ---------- installing -------------------------------------------------------

def _swap_file(new: Path, current: Path) -> None:
    """Put a new program file where the running one is. Works while it's running on Windows, Mac and Linux."""
    old = current.with_name(current.stem + ".old" + current.suffix)
    if old.exists():
        old.unlink()
    current.rename(old)
    shutil.move(str(new), str(current))
    current.chmod(0o755)


def install(kind: str, file: Path) -> str:
    """Install the downloaded file. Returns 'installed' (restart to use it) or raises."""
    exe = Path(sys.executable).resolve()
    work = Path(tempfile.mkdtemp(prefix="inpace-update-"))
    try:
        if kind == "windows":
            raise RuntimeError("On Windows the installer does the update: use run_windows_installer.")
        elif kind == "folder":
            with tarfile.open(file) as tf:
                member = tf.getmember("inPace/inPace")
                member.name = "inPace"
                try:
                    tf.extract(member, work, filter="data")
                except TypeError:  # older Python without extraction filters
                    tf.extract(member, work)
            _swap_file(work / "inPace", exe)
        elif kind in ("appimage", "appimage-full"):
            target = Path(os.environ["APPIMAGE"])
            new = target.with_name(target.name + ".new")
            shutil.copy2(file, new)
            new.chmod(0o755)
            old = target.with_name(target.name + ".old")
            old.unlink(missing_ok=True)
            target.rename(old)
            new.rename(target)
        elif kind == "folder-full":
            # The whole folder changes (program and engine): unpack next to it, then swap the two folders.
            here = exe.parent
            with tarfile.open(file) as tf:
                try:
                    tf.extractall(work, filter="data")
                except TypeError:
                    tf.extractall(work)
            fresh = work / "inPace"
            if not (fresh / "inPace").exists() or not (fresh / FULL_MARK).exists():
                raise RuntimeError("The download doesn't look like inPace with its own engine.")
            new = here.with_name(here.name + ".new")
            old = here.with_name(here.name + ".old")
            shutil.rmtree(new, ignore_errors=True)
            shutil.rmtree(old, ignore_errors=True)
            shutil.move(str(fresh), str(new))
            here.rename(old)
            new.rename(here)
        elif kind == "mac":
            app = exe.parents[2]  # .../inPace.app/Contents/MacOS/inPace
            mnt = work / "mnt"
            mnt.mkdir()
            subprocess.run(["hdiutil", "attach", str(file), "-nobrowse", "-readonly", "-mountpoint", str(mnt)],
                           check=True, capture_output=True)
            try:
                fresh = app.with_name("inPace.new.app")
                shutil.rmtree(fresh, ignore_errors=True)
                subprocess.run(["ditto", str(mnt / "inPace.app"), str(fresh)], check=True, capture_output=True)
                old = app.with_name("inPace.old.app")
                shutil.rmtree(old, ignore_errors=True)
                app.rename(old)
                fresh.rename(app)
            finally:
                subprocess.run(["hdiutil", "detach", str(mnt), "-quiet"], capture_output=True)
        elif kind in ("deb", "deb-full"):
            if not shutil.which("pkexec"):
                raise RuntimeError("This computer can't ask for your password here. Install the downloaded .deb by double-clicking it.")
            r = subprocess.run(["pkexec", "apt-get", "install", "-y", "--allow-downgrades", str(file)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError("The install was cancelled or didn't finish.")
        else:
            raise RuntimeError("This copy of inPace updates with git pull.")
        return "installed"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_windows_installer(file: Path) -> None:
    """Start inPace-setup.exe silently (it closes this copy, installs, and opens inPace again), then leave."""
    flags = 0x00000008 | 0x00000200  # detached, new process group: it keeps running after inPace closes
    subprocess.Popen([str(file), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/RELAUNCH=1"],
                     creationflags=flags, close_fds=True)
    time.sleep(0.3)
    from .window import close_children
    close_children()
    os._exit(0)


def clean_old_copies() -> None:
    """Remove what's left of the previous version after an update."""
    if not is_frozen():
        return
    exe = Path(sys.executable).resolve()
    for p in (exe.with_name(exe.stem + ".old" + exe.suffix),):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
    if sys.platform == "darwin":
        shutil.rmtree(exe.parents[2].with_name("inPace.old.app"), ignore_errors=True)
    if os.environ.get("APPIMAGE"):
        target = Path(os.environ["APPIMAGE"])
        target.with_name(target.name + ".old").unlink(missing_ok=True)
    elif (exe.parent / FULL_MARK).exists() and not str(exe).startswith("/opt/"):
        shutil.rmtree(exe.parent.with_name(exe.parent.name + ".old"), ignore_errors=True)


def restart() -> None:
    """Start the (new) app again, then leave. The new copy takes over the window and the data folder."""
    exe = Path(sys.executable).resolve()
    if install_kind() == "mac":
        subprocess.Popen(["open", "-n", str(exe.parents[2])])
    elif os.environ.get("APPIMAGE"):  # start the new AppImage file, not the old one's unpacked program
        subprocess.Popen([os.environ["APPIMAGE"], *sys.argv[1:]], start_new_session=True)
    else:
        kw = {"start_new_session": True} if os.name != "nt" else {"creationflags": 0x00000008 | 0x00000200}
        subprocess.Popen([str(exe), *sys.argv[1:]], **kw)
    time.sleep(0.3)
    from .window import close_children
    close_children()
    os._exit(0)


# ---------- "a new version is out": for every copy, phones and code folders too -------------------------

NEWS_EVERY = 12 * 3600
ANDROID_APK = "inPace-android-arm64-v8a.apk"


def latest() -> dict:
    """The newest published release, newer or not: {version, page, notes, assets}."""
    with _get(API) as r:
        data = json.loads(r.read().decode("utf-8"))
    tag = str(data.get("tag_name") or "")
    if not tag or data.get("draft") or data.get("prerelease"):
        return {}
    return {"version": tag.lstrip("v"), "page": str(data.get("html_url") or ""),
            "notes": str(data.get("body") or "")[:4000],
            "assets": {a["name"]: a["browser_download_url"] for a in data.get("assets", [])
                       if isinstance(a, dict) and a.get("name") and a.get("browser_download_url")}}


def check_news(vault, force: bool = False) -> dict:
    """Look on GitHub for the newest release at most twice a day, and remember it (update_news). Any problem
    (offline, GitHub busy) is quiet: the app just doesn't show the news until the next look."""
    last = int(vault._meta("update_news_checked", "0") or 0)
    if not force and time.time() - last < NEWS_EVERY:
        return news(vault, any_version=True)
    vault._set_meta("update_news_checked", str(int(time.time())))
    try:
        rel = latest()
    except Exception:
        return news(vault, any_version=True)
    if rel:
        vault._set_meta("update_news", json.dumps(rel))
    return rel


def news(vault, any_version: bool = False) -> dict:
    """The newest release we know of, if it's newer than this copy (or always, with any_version)."""
    try:
        rel = json.loads(vault._meta("update_news", "{}") or "{}")
    except ValueError:
        return {}
    if not isinstance(rel, dict) or not rel.get("version"):
        return {}
    return rel if any_version or newer(rel["version"]) else {}


# ---------- the whole thing, as one step for the app ------------------------

def run(vault, force: bool = False) -> dict:
    """Check, download and (when no password is needed) install. Saves what happened for the app to show."""
    kind = install_kind()
    status = {"state": "none", "checked": int(time.time())}
    if kind in ("source", "android"):  # git pull / the website: nothing to install from here
        return status
    last = int(vault._meta("update_checked", "0") or 0)
    if not force and time.time() - last < CHECK_EVERY:
        return json.loads(vault._meta("update_status", "{}") or "{}") or status
    vault._set_meta("update_checked", str(int(time.time())))
    try:
        rel = check()
        if not rel:
            status = {"state": "current", "checked": int(time.time())}
        else:
            file = download(rel, kind, vault.home / "updates")
            if kind in ("deb", "deb-full", "windows"):  # installed by its installer, when you press "Install and restart"
                status = {"state": "ready", "version": rel["version"], "file": str(file)}
            else:
                install(kind, file)
                status = {"state": "installed", "version": rel["version"]}
    except NotReady:
        # A new version is being published right now: look again in an hour instead of tomorrow.
        status = {"state": "waiting", "checked": int(time.time())}
        vault._set_meta("update_checked", str(int(time.time() - CHECK_EVERY + 3600)))
    except Exception as e:  # never let an update problem get in the way of learning
        status = {"state": "failed", "error": str(e)[:200], "checked": int(time.time())}
    vault._set_meta("update_status", json.dumps(status))
    return status
