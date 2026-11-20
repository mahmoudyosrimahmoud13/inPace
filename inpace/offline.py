"""Watch YouTube lessons offline.

Two ways to get a course's YouTube videos onto this computer:

1. Download them with yt-dlp (free and open source). inPace fetches yt-dlp itself the first time, keeps it in
   <home>/tools/, checks it against the checksums yt-dlp publishes, and updates it when you press "Update now",
   or by itself once a day if you chose that in Settings. YouTube changes often, and an old yt-dlp stops working,
   so updates matter.
2. Point inPace to a folder where you already have the videos. inPace matches each file to its lesson video even
   when the names are a bit different: it compares the words (Arabic and English, typos, numbering, quality tags),
   the lesson numbers, the video's YouTube id when the file name has it, and the length of the video.

Either way, lessons then play the file on this computer, still only their own piece of a long video, and continue
from the second you stopped at (the same place as on YouTube).

What inPace remembers (in its database, under "meta"):
    ytfile:<course>:<video id>   full path of the file for that video
    ytlist:<course>:<playlist>   the playlist's videos, as JSON [{"id", "title"}]
    yttitle:<video id>           the video's YouTube title and length, as JSON, to match files later
    ytdlp_updates                "auto" or "manual"
    ytdlp_quality                highest video height to download: 360, 480, 720, 1080 or "best"
    ytdlp_folder                 where downloads go: "downloads" (default), "videos", "inpace" or "custom"
    ytdlp_folder_path            the folder for "custom"
    ytdlp_base:<course>          this course only: the folder to save in (instead of the Settings choice)
    ytdlp_dirname:<course>       this course only: the name of its own folder (the course name by default)
    ytdl:<course>:<video id>     "1" when inPace downloaded that file itself (only those can be deleted from inPace)

By default videos go to your Downloads folder, in inPace/<course name>/, so you can find them, play them in any
player, or move them. On Android that's the phone's Download/inPace folder.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import sys
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

RELEASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
VIDEO_EXT = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".3gp", ".ts"}
QUALITIES = ("360", "480", "720", "1080", "best")
MB_PER_HOUR = {"360": 150, "480": 300, "720": 600, "1080": 1200, "best": 1200}  # rough, with sound
KEEP_FREE = 300 * 1024 * 1024  # never fill the disk completely: stop when less than this is left
_LOCK = threading.Lock()
JOBS: dict[str, dict] = {}  # course id -> what its download is doing now (for the progress bar)

# How downloads share the connection (v1.30.14), chosen on the Downloads page:
#   dl_parallel   how many videos download at the same time, across all courses (1 to 5, 2 by default)
#   dl_rate       a speed limit for all of them together ("0" = none, or a value from RATES)
PARALLEL = (1, 2, 3, 4, 5)
RATES = {"0": 0, "500k": 500 * 1024, "1m": 1024 ** 2, "2m": 2 * 1024 ** 2, "5m": 5 * 1024 ** 2, "10m": 10 * 1024 ** 2}
SETTINGS = {"parallel": 2, "rate": 0}


class _Slots:
    """The places for videos downloading right now, shared by every course. The number can change while
    downloads run: more places start waiting videos at once; fewer let the running ones finish first."""
    def __init__(self) -> None:
        self.cv = threading.Condition()
        self.busy = 0

    def take(self, give_up) -> bool:
        with self.cv:
            while self.busy >= SETTINGS["parallel"]:
                if give_up():
                    return False
                self.cv.wait(0.4)
            self.busy += 1
            return True

    def give(self) -> None:
        with self.cv:
            self.busy = max(0, self.busy - 1)
            self.cv.notify_all()

    def wake(self) -> None:
        with self.cv:
            self.cv.notify_all()


SLOTS = _Slots()


def load_settings(vault) -> dict:
    try:
        n = int(vault._meta("dl_parallel", "2") or 2)
    except ValueError:
        n = 2
    rate = vault._meta("dl_rate", "0") or "0"
    SETTINGS["parallel"] = n if n in PARALLEL else 2
    SETTINGS["rate"] = RATES.get(rate, 0)
    SETTINGS["rate_key"] = rate if rate in RATES else "0"
    SLOTS.wake()
    return dict(SETTINGS)


def save_settings(vault, parallel=None, rate=None) -> dict:
    if parallel is not None and str(parallel).isdigit() and int(parallel) in PARALLEL:
        vault._set_meta("dl_parallel", str(int(parallel)))
    if rate is not None and str(rate) in RATES:
        vault._set_meta("dl_rate", str(rate))
    return load_settings(vault)


# ---------------------------------------------------------------------------------------------------------------
# Which YouTube videos a course uses
# ---------------------------------------------------------------------------------------------------------------
def course_videos(course) -> list[dict]:
    """Every YouTube video and playlist the course's lessons use, in course order.
    [{"kind": "video", "id": ..., "lessons": [titles], "index": n} or {"kind": "playlist", ...}]"""
    from .course import embed_id, media_kind, youtube_playlist
    out: dict[tuple, dict] = {}
    link = re.compile(r"https?://[^\s)\]>\"']+")
    for m in course.modules:
        for les in m["lessons"]:
            refs = [les.get("media") or ""] + link.findall(les.get("content") or "")
            for ref in refs:
                if media_kind(ref) != "youtube":
                    continue
                vid, plist = embed_id(ref), youtube_playlist(ref)
                key = ("video", vid) if vid else ("playlist", plist) if plist else None
                if not key:
                    continue
                item = out.setdefault(key, {"kind": key[0], "id": key[1], "lessons": [], "index": len(out) + 1})
                if les["title"] not in item["lessons"]:
                    item["lessons"].append(les["title"])
    return list(out.values())


def watch_url(item: dict) -> str:
    if item["kind"] == "playlist":
        return f"https://www.youtube.com/playlist?list={item['id']}"
    return f"https://www.youtube.com/watch?v={item['id']}"


def local_file(vault, course_id: str, vid: str) -> Path | None:
    """The file for this video, if it's there and inPace may read it (on Android, a file in Download that another
    copy of the app made can be there but locked; then the lesson simply plays from YouTube)."""
    p = vault._meta(f"ytfile:{course_id}:{vid}", "") or ""
    if not p or not Path(p).is_file():
        return None
    try:
        with open(p, "rb"):
            pass
    except OSError:
        return None
    return Path(p)


def set_local_file(vault, course_id: str, vid: str, path: Path | str | None, downloaded: bool = False) -> None:
    vault._set_meta(f"ytfile:{course_id}:{vid}", str(path) if path else "")
    vault._set_meta(f"ytdl:{course_id}:{vid}", "1" if path and downloaded else "")


# ---------------------------------------------------------------------------------------------------------------
# Where downloads go
# ---------------------------------------------------------------------------------------------------------------
FOLDERS = ("downloads", "videos", "inpace", "custom")


def on_android() -> bool:
    return os.environ.get("INPACE_MOBILE") == "android" or hasattr(sys, "getandroidapilevel")


def _android_storage() -> Path:
    return Path(os.environ.get("INPACE_STORAGE") or os.environ.get("EXTERNAL_STORAGE") or "/storage/emulated/0")


def _xdg_dir(name: str) -> Path | None:
    """Linux: the folder the desktop calls Downloads or Videos (it can be translated, like ~/Téléchargements)."""
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "user-dirs.dirs"
    try:
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"XDG_{name}_DIR="):
                value = line.split("=", 1)[1].strip().strip('"').replace("$HOME", str(Path.home()))
                return Path(value)
    except OSError:
        pass
    return None


def system_folder(kind: str) -> Path:
    """The person's Downloads or Videos folder on this computer or phone."""
    if on_android():
        return _android_storage() / ("Download" if kind == "downloads" else "Movies")
    home = Path.home()
    if kind == "downloads":
        return (sys.platform.startswith("linux") and _xdg_dir("DOWNLOAD")) or home / "Downloads"
    if sys.platform == "darwin":
        return home / "Movies"
    return (sys.platform.startswith("linux") and _xdg_dir("VIDEOS")) or home / "Videos"


def safe_name(text: str, limit: int = 80) -> str:
    """A folder name that works on Windows, Mac, Linux and Android."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", text or "").strip(" .")
    name = re.sub(r"\s+", " ", name)[:limit].strip(" .")
    return name or "Course"


def default_base(vault) -> Path | None:
    """The folder chosen in Settings (None means inPace's own hidden folder)."""
    choice = vault._meta("ytdlp_folder", "downloads") or "downloads"
    if choice == "inpace":
        return None
    if choice == "custom" and (vault._meta("ytdlp_folder_path", "") or "").strip():
        return Path(vault._meta("ytdlp_folder_path", "")).expanduser()
    return system_folder("videos" if choice == "videos" else "downloads") / "inPace"


def folder_name(vault, course) -> str:
    return safe_name(vault._meta(f"ytdlp_dirname:{course.id}", "") or course.title)


def download_folder(vault, course) -> Path:
    """Where this course's videos are saved: the course's own choice, else the one in Settings,
    in a folder named after the course (or the name the person gave it)."""
    own = (vault._meta(f"ytdlp_base:{course.id}", "") or "").strip()
    base = Path(own).expanduser() if own else default_base(vault)
    if base is None and not (vault._meta(f"ytdlp_dirname:{course.id}", "") or ""):
        return vault.media_dir(course.id) / "videos"
    return (base or vault.media_dir(course.id)) / folder_name(vault, course)


def _writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".inpace-check.mp4"  # a video name: Android's Movies folder only takes media files
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def playlist_items(vault, course_id: str, plist: str) -> list[dict]:
    try:
        return json.loads(vault._meta(f"ytlist:{course_id}:{plist}", "") or "[]")
    except ValueError:
        return []


def video_info(vault, vid: str) -> dict:
    try:
        return json.loads(vault._meta(f"yttitle:{vid}", "") or "{}")
    except ValueError:
        return {}


def status(vault, course) -> dict:
    """How many of the course's videos are on this computer."""
    items = course_videos(course)
    total = have = 0
    for it in items:
        if it["kind"] == "video":
            total += 1
            have += bool(local_file(vault, course.id, it["id"]))
        else:
            vids = playlist_items(vault, course.id, it["id"])
            if not vids:
                total += 1  # we don't know its videos yet
            for v in vids:
                total += 1
                have += bool(local_file(vault, course.id, v["id"]))
    folder = download_folder(vault, course)
    return {"items": items, "total": total, "have": have, "job": JOBS.get(course.id),
            "free": free_space(folder), "need": space_needed(vault, course) if have < total else {},
            "folder": str(folder), "folder_name": folder_name(vault, course),
            "own_base": vault._meta(f"ytdlp_base:{course.id}", "") or "",
            "default_base": str(default_base(vault) or vault.media_dir(course.id))}


def free_space(folder: Path) -> int:
    """Free bytes on the drive where this folder is (or would be). -1 if unknown."""
    p = Path(folder)
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        return shutil.disk_usage(p).free
    except OSError:
        return -1


def _video_seconds(vault, course, it: dict, guess: bool = True) -> float:
    """How long a video is: from YouTube when we know it, else from its lessons' minutes, else a guess
    (0 when guess is False and nothing is known)."""
    info = video_info(vault, it["id"])
    if info.get("duration"):
        return float(info["duration"])
    minutes = sum(int(les.get("minutes") or 0) for m in course.modules for les in m["lessons"]
                  if les["title"] in it.get("lessons", []))
    return minutes * 60.0 if minutes else (15 * 60.0 if guess else 0.0)


def item_size(vault, course, it: dict, quality: str, guess: bool = True) -> int:
    """Roughly how many bytes one lesson's video (or playlist) still needs at this quality."""
    mb = MB_PER_HOUR.get(quality if quality in MB_PER_HOUR else "720", 600)
    if it["kind"] == "video":
        if local_file(vault, course.id, it["id"]):
            return 0
        seconds = _video_seconds(vault, course, it, guess)
    else:
        vids = playlist_items(vault, course.id, it["id"])
        if not vids:
            seconds = 5 * 15 * 60.0 if guess else 0.0
        else:
            seconds = 0.0
            for v in vids:
                if not local_file(vault, course.id, v["id"]):
                    dur = float(video_info(vault, v["id"]).get("duration") or 0)
                    seconds += dur or (15 * 60.0 if guess else 0.0)
    return int(seconds / 3600 * mb * 1024 * 1024)


_WHY = (
    (("Unable to connect", "Network is unreachable", "getaddrinfo", "timed out", "Temporary failure in name resolution",
      "Tunnel connection failed", "Connection refused", "Connection reset", "No address associated", "Failed to resolve"),
     "No internet connection, or YouTube can't be reached right now. Try again when you're online."),
    (("Video unavailable", "Private video", "has been removed", "is not available", "account associated with this video"),
     "YouTube says this video isn't available anymore."),
    (("Sign in to confirm", "not a bot"),
     "YouTube asked to check that you're not a robot. Try again later, or update yt-dlp in Settings."),
)


def plain_why(why: str) -> str:
    """Why a video didn't download, in plain words for the common cases (else yt-dlp's own short message)."""
    for needles, text in _WHY:
        if any(n.lower() in (why or "").lower() for n in needles):
            return text
    return (why or "")[:160]


def video_state(vault, course, vid: str = "", plist: str = "") -> dict:
    """What a lesson's download button shows: "saved", "downloading" (with percent), "waiting" (other videos
    first), "failed" (with why) or "none"."""
    job = JOBS.get(course.id) or {}
    running = job.get("state") == "running"
    pending = {it.get("id") for it in job.get("pending", [])}
    if vid:
        if local_file(vault, course.id, vid):
            return {"state": "saved"}
        act = (job.get("active") or {}).get(vid) if running else None
        if act:
            return {"state": "downloading", "percent": act.get("percent") or 0.0}
        if running and job.get("current") == vid:
            return {"state": "downloading", "percent": job.get("percent") or 0.0}
        if running and (vid in job.get("queue", []) or vid in pending or job.get("want_all")):
            return {"state": "waiting"}
        fail = next((f for f in job.get("failed", []) if f.get("id") == vid), None)
        if fail:
            return {"state": "failed", "why": plain_why(fail.get("why", ""))}
        if job.get("state") == "failed" and vid in job.get("asked", []):  # the whole download stopped
            return {"state": "failed", "why": plain_why(job.get("error", ""))}
        return {"state": "none"}
    items = playlist_items(vault, course.id, plist)
    have = sum(1 for v in items if local_file(vault, course.id, v["id"]))
    out = {"have": have, "total": len(items)}
    if items and have >= len(items):
        return {"state": "saved", **out}
    if running and (plist in job.get("lists", []) or plist in pending or job.get("want_all")):
        act = job.get("active") or {}
        mine = [act[v["id"]] for v in items if v["id"] in act]
        now = job.get("current")
        busy = bool(mine) or bool(now and any(v["id"] == now for v in items))
        pct = (mine[0].get("percent") or 0.0) if mine else (job.get("percent") or 0.0) if busy else 0.0
        return {"state": "downloading" if busy else "waiting", "percent": pct, **out}
    if job.get("state") == "failed" and plist in job.get("asked", []):
        return {"state": "failed", "why": plain_why(job.get("error", "")), **out}
    return {"state": "none", **out}


def space_needed(vault, course) -> dict:
    """Roughly how many bytes the videos not on this computer yet need, for each quality."""
    seconds = 0.0
    for it in course_videos(course):
        if it["kind"] == "video":
            if not local_file(vault, course.id, it["id"]):
                seconds += _video_seconds(vault, course, it)
        else:
            vids = playlist_items(vault, course.id, it["id"]) or [{"id": ""}] * 5
            for v in vids:
                if not (v["id"] and local_file(vault, course.id, v["id"])):
                    seconds += float(video_info(vault, v["id"]).get("duration") or 15 * 60) if v["id"] else 15 * 60
    return {q: int(seconds / 3600 * mb * 1024 * 1024) for q, mb in MB_PER_HOUR.items()}


def nice_size(n: int) -> str:
    if n < 0:
        return "?"
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB"
    return f"{max(1, round(n / 1024 ** 2))} MB"


def forget(vault, course, delete_downloads: bool = False) -> int:
    """Stop using the files for this course. With delete_downloads, also delete the ones inPace downloaded
    (only files inside inPace's own folder; your own folders are never touched). Returns how many were deleted."""
    gone = 0
    inside = (vault.media_dir(course.id) / "videos").resolve()
    folders = set()
    vids = set()
    for it in course_videos(course):
        if it["kind"] == "video":
            vids.add(it["id"])
        else:
            vids |= {v["id"] for v in playlist_items(vault, course.id, it["id"])}
    for vid in vids:
        p = local_file(vault, course.id, vid)
        if p and delete_downloads:
            mine = (vault._meta(f"ytdl:{course.id}:{vid}", "") or "") == "1"
            if not mine:
                try:
                    p.resolve().relative_to(inside)  # downloaded by an older inPace, into its own folder
                    mine = True
                except (ValueError, OSError):
                    pass
            if mine:
                try:
                    p.unlink()
                    gone += 1
                    folders.add(p.parent)
                except OSError:
                    pass
        set_local_file(vault, course.id, vid, None)
    for f in folders:  # the course's folder in Downloads goes too, if nothing else is in it
        try:
            f.rmdir()
        except OSError:
            pass
    return gone


# ---------------------------------------------------------------------------------------------------------------
# yt-dlp: get it, update it, load it
# ---------------------------------------------------------------------------------------------------------------
def tool_path(home: Path) -> Path:
    return Path(home) / "tools" / "yt-dlp.zip"


def _purge(zp: Path | None = None) -> None:
    """Forget the loaded yt-dlp, so the next download loads the copy on disk now (after an update)."""
    for name in [n for n in sys.modules if n == "yt_dlp" or n.startswith(("yt_dlp.", "yt_dlp_ejs"))]:
        del sys.modules[name]
    if zp is not None:  # Python also remembers what was inside the old zip file
        sys.path_importer_cache.pop(str(zp), None)
        import zipimport
        getattr(zipimport, "_zip_directory_cache", {}).pop(str(zp), None)


def load(home: Path):
    """The yt_dlp module: inPace's own copy first (it's the one we keep up to date), else one installed with pip."""
    zp = tool_path(home)
    if zp.is_file():
        if str(zp) not in sys.path:
            _purge(zp)
            sys.path.insert(0, str(zp))
        import yt_dlp
        return yt_dlp
    try:
        import yt_dlp
        return yt_dlp
    except ImportError:
        return None


def version(home: Path) -> str:
    """The yt-dlp version inPace has, or '' if it has none yet."""
    zp = tool_path(home)
    if zp.is_file():
        import zipfile
        try:
            with zipfile.ZipFile(zp) as z:
                m = re.search(r"__version__\s*=\s*'([^']+)'", z.read("yt_dlp/version.py").decode("utf-8", "replace"))
                return m.group(1) if m else "?"
        except (OSError, KeyError, zipfile.BadZipFile):
            return ""
    try:
        from yt_dlp.version import __version__
        return __version__
    except ImportError:
        return ""


def _get(url: str, timeout: float = 60) -> bytes:
    import urllib.request
    from .net import urlopen
    with urlopen(urllib.request.Request(url, headers={"User-Agent": "inPace"}), timeout=timeout) as r:
        return r.read()


class ToolProblem(Exception):
    pass


def update_tool(home: Path, fetch=_get) -> tuple[bool, str]:
    """Get the newest yt-dlp if it's newer than ours. Returns (changed, version).
    The download is checked against yt-dlp's published SHA-256 checksums before it replaces the old copy."""
    with _LOCK:
        if any(j.get("state") == "running" for j in JOBS.values()):
            raise ToolProblem("Wait until the video downloads finish, then update.")
        try:
            sums = fetch(RELEASE + "SHA2-256SUMS", 30).decode("utf-8", "replace")
        except Exception:
            raise ToolProblem("inPace couldn't reach GitHub to get yt-dlp. Check your internet and try again.")
        want = next((ln.split()[0].lower() for ln in sums.splitlines()
                     if len(ln.split()) == 2 and ln.split()[1].lstrip("*") == "yt-dlp"), "")
        if not re.fullmatch(r"[0-9a-f]{64}", want):
            raise ToolProblem("yt-dlp's checksum list couldn't be read. Try again later.")
        zp = tool_path(home)
        if zp.is_file() and hashlib.sha256(zp.read_bytes()).hexdigest() == want:
            return False, version(home)
        try:
            data = fetch(RELEASE + "yt-dlp", 120)
        except Exception:
            raise ToolProblem("The yt-dlp download didn't finish. Check your internet and try again.")
        if hashlib.sha256(data).hexdigest() != want:
            raise ToolProblem("The yt-dlp download didn't match its published checksum, so inPace didn't use it.")
        zp.parent.mkdir(parents=True, exist_ok=True)
        tmp = zp.with_suffix(".new")
        tmp.write_bytes(data)
        os.replace(tmp, zp)
        if str(zp) in sys.path:
            sys.path.remove(str(zp))
        _purge(zp)  # the next download uses the new copy
        return True, version(home)


def auto_update(vault) -> None:
    """Called in the background: once a day, if the person chose automatic updates and has the tool already."""
    if (vault._meta("ytdlp_updates", "auto") or "auto") != "auto" or not tool_path(vault.home).is_file():
        return
    last = float(vault._meta("ytdlp_checked", "0") or 0)
    if time.time() - last < 20 * 3600:
        return
    vault._set_meta("ytdlp_checked", str(time.time()))
    try:
        update_tool(vault.home)
    except Exception:
        pass


def start_auto_updates(home: Path) -> None:
    """Look for a new yt-dlp once an hour in the background; auto_update() decides if it's time (once a day)."""
    def loop() -> None:
        time.sleep(60)  # let the app start first
        while True:
            try:
                from .vault import Vault
                v = Vault(home)
                try:
                    if v.is_set_up:
                        auto_update(v)
                finally:
                    v.db.close()
            except Exception:
                pass
            time.sleep(3600)

    threading.Thread(target=loop, daemon=True).start()


def _js_runtimes() -> dict:
    """YouTube now needs a JavaScript runtime for some videos. yt-dlp uses one if this computer has it."""
    return {name: {} for name in ("deno", "node", "bun", "quickjs") if shutil.which(name)} or {"deno": {}}


def _format(quality: str) -> tuple[str, bool]:
    """The format to ask yt-dlp for. Without ffmpeg only single-file formats work (mostly up to 720p)."""
    q = quality if quality in QUALITIES else "720"
    if q == "best":
        if shutil.which("ffmpeg"):
            return "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b", True
        return "b[vcodec!=none][acodec!=none]/b", False
    if shutil.which("ffmpeg"):
        return (f"bv*[height<={q}][ext=mp4]+ba[ext=m4a]/b[height<={q}][ext=mp4]/bv*[height<={q}]+ba/b[height<={q}]/b", True)
    return (f"b[height<={q}][ext=mp4][vcodec!=none][acodec!=none]/b[height<={q}][vcodec!=none][acodec!=none]/b", False)


# ---------------------------------------------------------------------------------------------------------------
# The ad blocker: yt-dlp finds the plain video file, and inPace's own player plays it. YouTube's ads never load.
# ---------------------------------------------------------------------------------------------------------------
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
# Ways to play a video without YouTube's player, best first. YouTube now gives most videos only as separate picture
# and sound files, so the second way (inPace plays the two together) is the one that usually works.
ONE_FILE = "18/b[ext=mp4][vcodec!=none][acodec!=none][protocol^=http]/b[vcodec!=none][acodec!=none][protocol^=http]"
TWO_FILES = ("bv*[ext=mp4][vcodec^=avc1][height<={q}][protocol^=http]+ba[ext=m4a][protocol^=http]"
             "/bv*[height<={q}][protocol^=http]+ba[protocol^=http]")
PHONE_STREAM = "b[protocol*=m3u8][vcodec!=none][acodec!=none]"
# If YouTube gives the usual app nothing usable, ask again as other YouTube apps (TV, iPhone, the phone website...).
OTHER_CLIENTS = (None, ["tv", "web_safari", "ios", "mweb", "android_vr"])
_STREAMS: dict[str, tuple[float, dict]] = {}
_FETCHING = threading.Lock()


def _pick(info: dict) -> dict:
    """What the player needs from yt-dlp's answer: one file, two files (picture + sound), or a phone stream."""
    pair = info.get("requested_formats") or []
    if len(pair) == 2:
        vid = next((f for f in pair if f.get("vcodec") not in (None, "none")), None)
        aud = next((f for f in pair if f is not vid and f.get("acodec") not in (None, "none")), None)
        if vid and aud and str(vid.get("url", "")).startswith("https://") and str(aud.get("url", "")).startswith("https://"):
            return {"video": vid["url"], "audio": aud["url"], "height": int(vid.get("height") or 0)}
        return {}
    url = str(info.get("url") or "")
    if not url.startswith("https://"):
        return {}
    out = {"url": url, "height": int(info.get("height") or 0)}
    if "m3u8" in str(info.get("protocol") or ""):
        out["hls"] = True
    return out


def stream(home: Path, vid: str, load_fn=None, hls: bool = False, quality: str = "720", sized: bool = False) -> dict:
    """How to play one video without ads: {url} (one file), {video, audio} (two files played together),
    {url, hls} (a phone stream), or {why} in plain words. Each answer is kept 4 hours (YouTube's links last
    about 6). The first time, yt-dlp itself is fetched first.
    sized: the quality menu asked for this quality, so the picture at that size comes first (the one-file
    version is only 360p); the one file is the fallback."""
    if not VIDEO_ID.fullmatch(vid or ""):
        return {"why": "This isn't a YouTube video."}
    q = quality if quality in ("360", "480", "720", "1080") else "720"
    key = f"{vid}:{q}:{int(hls)}:{int(sized)}"
    hit = _STREAMS.get(key)
    if hit and time.time() - hit[0] < 4 * 3600:
        return hit[1]
    loader = load_fn or load
    yt_dlp = loader(home)
    if yt_dlp is None and load_fn is None:
        with _FETCHING:
            try:
                update_tool(home)
            except Exception as e:
                return {"why": str(e) or "inPace couldn't get yt-dlp. Check your internet and try again."}
        yt_dlp = loader(home)
    if yt_dlp is None:
        return {"why": "inPace couldn't get yt-dlp. Check your internet and try again."}
    spec = (TWO_FILES.format(q=q) + "/" + ONE_FILE) if sized else (ONE_FILE + "/" + TWO_FILES.format(q=q))
    spec += ("/" + PHONE_STREAM) if hls else ""
    why = ""
    for clients in OTHER_CLIENTS:
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
                "format": spec, "socket_timeout": 15, "js_runtimes": _js_runtimes()}
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        except Exception as e:
            why = _short(e)
            continue
        out = _pick(info or {})
        if out:
            _STREAMS[key] = (time.time(), out)
            return out
        why = why or "YouTube didn't give a file that plays here."
    return {"why": why or "YouTube didn't give a file that plays here."}


# ---------------------------------------------------------------------------------------------------------------
# Subtitles for YouTube lessons: which languages a video has, and their text (WebVTT)
# ---------------------------------------------------------------------------------------------------------------
_SUBS: dict[str, tuple[float, dict]] = {}


def subtitles(home: Path, vid: str, ui_lang: str = "en", load_fn=None) -> dict:
    """The subtitles a YouTube video has: {"tracks": [{"lang", "name", "auto", "url"}]} or {"why"}.
    The ones its maker added come first. YouTube's automatic ones: the video's own language, plus that
    language translated into the app's language and English. Kept 4 hours, like stream()."""
    if not VIDEO_ID.fullmatch(vid or ""):
        return {"why": "This isn't a YouTube video."}
    key = f"{vid}:{ui_lang}"
    hit = _SUBS.get(key)
    if hit and time.time() - hit[0] < 4 * 3600:
        return hit[1]
    yt_dlp = (load_fn or load)(home)
    if yt_dlp is None and load_fn is None:
        with _FETCHING:
            try:
                update_tool(home)
            except Exception:
                pass
        yt_dlp = load(home)
    if yt_dlp is None:
        return {"why": "inPace couldn't get yt-dlp. Check your internet and try again."}
    info, why = None, ""
    for clients in OTHER_CLIENTS:
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True, "socket_timeout": 15,
                "js_runtimes": _js_runtimes()}
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False, process=False)
            if info:
                break
        except Exception as e:
            why = _short(e)
    if not info:
        return {"why": why or "YouTube didn't answer."}
    out = {"tracks": pick_subtitles(info, ui_lang)}
    _SUBS[key] = (time.time(), out)
    return out


def pick_subtitles(info: dict, ui_lang: str = "en") -> list[dict]:
    def vtt(formats):
        for f in formats or []:
            if f.get("ext") == "vtt" and f.get("url"):
                return f
        return None
    tracks, seen = [], set()
    for lang, formats in (info.get("subtitles") or {}).items():
        if lang == "live_chat":
            continue
        f = vtt(formats)
        if f and lang not in seen:
            seen.add(lang)
            tracks.append({"lang": lang, "name": f.get("name") or lang, "auto": False, "url": f["url"]})
    auto = info.get("automatic_captions") or {}
    orig = next((k for k in auto if k.endswith("-orig")), None) or (info.get("language") if info.get("language") in auto else None)
    base = (orig or "").replace("-orig", "")
    wanted = [k for k in (orig, ui_lang, "en") if k]
    for lang in wanted:
        clean = lang.replace("-orig", "")
        if clean in seen or lang not in auto:
            continue
        f = vtt(auto[lang])
        if not f:
            continue
        seen.add(clean)
        tracks.append({"lang": clean, "name": (f.get("name") or clean).replace(" (Original)", ""), "auto": True,
                       "translated": bool(base) and clean != base, "from": base if base and clean != base else "",
                       "url": f["url"]})
    return tracks


def subtitle_text(home: Path, vid: str, lang: str, ui_lang: str = "en", fetch=None) -> str:
    """One subtitle track's WebVTT text, fetched for the page (YouTube's links don't work from inside the app)."""
    found = subtitles(home, vid, ui_lang)
    track = next((t for t in found.get("tracks", []) if t["lang"] == lang), None)
    if not track:
        return ""
    if fetch is None:
        from .net import urlopen
        import urllib.request
        with urlopen(urllib.request.Request(track["url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as r:
            return r.read().decode("utf-8", "replace")
    return fetch(track["url"])


# ---------------------------------------------------------------------------------------------------------------
# Downloading a course's videos (in the background)
# ---------------------------------------------------------------------------------------------------------------
class Stopped(Exception):
    pass


class NoSpace(Exception):
    pass


def start_download(vault, course, open_vault=None, quality: str = "", only: list[dict] | None = None) -> dict:
    """Start downloading in the background: all of the course's videos, or only some (only = items from
    course_videos, like the video under one lesson). Asking again while it runs adds to the same download,
    so pressing several lessons' buttons, or "download all" after one, just makes the list longer.
    Returns the job (it changes as it goes)."""
    with _LOCK:
        job = JOBS.get(course.id)
        if job and job["state"] == "running":
            if only is None:
                if not job.get("all"):
                    job["want_all"] = True
            else:
                for it in only:
                    if it["id"] not in job["asked"]:
                        job["asked"].append(it["id"])
                    if it["id"] not in job["queue"] and all(p["id"] != it["id"] for p in job["pending"]):
                        job["pending"].append(it)
            return job
        before = JOBS.get(course.id) or {}
        job = {"state": "running", "done": 0, "total": 0, "title": "", "percent": 0.0, "error": "", "stop": False,
               "active": {}, "saved": 0, "bytes": 0, "course_title": getattr(course, "title", ""),
               "completed": list(before.get("completed") or [])[-200:],
               "failed": [], "started": time.time(), "quality": quality if quality in QUALITIES else "",
               "pending": list(only or []), "want_all": only is None, "all": False, "queue": [], "lists": [],
               "current": "", "asked": [it["id"] for it in only or []]}
        JOBS[course.id] = job
    load_settings(vault)
    home = vault.home
    opener = open_vault or (lambda: type(vault)(home))
    threading.Thread(target=_run, args=(opener, course, job), daemon=True).start()
    return job


def _run(opener, course, job) -> None:
    v = opener()  # its own database connection: this runs next to the app
    out_dir = None
    try:
        if not tool_path(v.home).is_file() and load(v.home) is None:
            job["title"] = "Getting yt-dlp…"
            update_tool(v.home)
        yt_dlp = load(v.home)
        if yt_dlp is None:
            raise ToolProblem("yt-dlp couldn't be loaded.")
        quality = job.get("quality") or v._meta("ytdlp_quality", "720") or "720"
        fmt, merge = _format(quality)
        out_dir = download_folder(v, course)
        if not _writable(out_dir):
            job["note"] = ("inPace couldn't save to {folder}, so the videos are kept in inPace's own folder. "
                           "Choose another folder in Settings, or allow inPace to use your files.")
            job["note_folder"] = str(out_dir)
            out_dir = v.media_dir(course.id) / "videos"
            out_dir.mkdir(parents=True, exist_ok=True)
        job["folder"] = str(out_dir)

        opts = {"format": fmt, "outtmpl": str(out_dir / "%(title).120B [%(id)s].%(ext)s"), "quiet": True,
                "no_warnings": True, "noprogress": True, "progress_hooks": [], "continuedl": True,
                "noplaylist": True, "windowsfilenames": True, "retries": 5, "fragment_retries": 5,
                "js_runtimes": _js_runtimes(), "remote_components": set(), "logger": _Quiet()}
        if merge:
            opts["merge_output_format"] = "mp4"
        if on_android() and "Movies" in out_dir.parts:
            opts["nopart"] = True  # Android's Movies folder refuses files that aren't media, like "video.mp4.part"
        todo: list[tuple[str, str]] = []  # (video id, title), each video once, in the order asked
        seen: set[str] = set()

        def add(vid: str, title: str) -> None:
            job.setdefault("titles", {})[vid] = title
            if vid not in seen:
                seen.add(vid)
                todo.append((vid, title))
                job["queue"].append(vid)
                if vid not in job["asked"]:
                    job["asked"].append(vid)
            job["total"] = len(todo)

        def expand(items: list[dict], flat) -> None:
            """Turn lessons' videos and playlists into the list of single videos to download."""
            for it in items:
                if job["stop"]:
                    raise Stopped()
                if it["kind"] == "video":
                    add(it["id"], it.get("title") or (it["lessons"][0] if it.get("lessons") else it["id"]))
                    continue
                job["title"] = "Reading the playlist…"
                info = flat.extract_info(watch_url(it), download=False) or {}
                entries = [{"id": e["id"], "title": e.get("title") or e["id"]}
                           for e in (info.get("entries") or []) if e and e.get("id")]
                v._set_meta(f"ytlist:{course.id}:{it['id']}", json.dumps(entries, ensure_ascii=False))
                for e in (info.get("entries") or []):
                    if e and e.get("id"):
                        _remember_info(v, e)
                if it["id"] not in job["lists"]:
                    job["lists"].append(it["id"])
                if it["id"] not in job["asked"]:
                    job["asked"].append(it["id"])
                for e in entries:
                    add(e["id"], e["title"])
                job["title"] = ""

        # Several videos at once (Downloads page: "at the same time"), each in its own thread with its own
        # yt-dlp. Only this thread touches the database; the workers hand back what they got.
        import queue as _queue
        results: _queue.Queue = _queue.Queue()
        running: dict[str, threading.Thread] = {}
        trouble = {"space": False}

        def worker(vid: str, title: str) -> None:
            if not SLOTS.take(lambda: job["stop"]):
                results.put(("stopped", vid, title, None))
                return
            now = {"title": title, "percent": 0.0, "speed": 0, "eta": None, "got": 0, "size": 0}
            job["active"][vid] = now
            _sync_current(job)
            checked = [0.0]

            def hook(d: dict) -> None:
                if job["stop"] or vid in job.get("skip", ()):
                    raise Stopped()
                if time.time() - checked[0] > 2:  # look at the free space every couple of seconds
                    checked[0] = time.time()
                    free = free_space(out_dir)
                    if 0 <= free < KEEP_FREE:
                        raise NoSpace()
                if d.get("status") == "downloading":
                    got, size = d.get("downloaded_bytes") or 0, d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    now.update(percent=round(100 * got / size, 1) if size else 0.0, got=got, size=size,
                               speed=int(d.get("speed") or 0), eta=d.get("eta"))
                    _sync_current(job)

            mine = {**opts, "progress_hooks": [hook]}
            if SETTINGS["rate"]:  # the limit is for all downloads together
                mine["ratelimit"] = max(64 * 1024, SETTINGS["rate"] // max(1, SETTINGS["parallel"]))
            try:
                with yt_dlp.YoutubeDL(mine) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True) or {}
                results.put(("ok", vid, title, {**info, "_size": now.get("size") or now.get("got") or 0}))
            except Stopped:
                results.put(("stopped", vid, title, None))
            except NoSpace:
                results.put(("space", vid, title, None))
            except Exception as e:
                if "NoSpace" in repr(e) or "No space left" in str(e):
                    results.put(("space", vid, title, None))
                elif "Stopped" in type(e).__name__ or "Stopped" in repr(e) or job["stop"]:
                    results.put(("stopped", vid, title, None))
                else:
                    results.put(("failed", vid, title, _short(e)))
            finally:
                job["active"].pop(vid, None)
                _sync_current(job)
                SLOTS.give()

        def finish(kind: str, vid: str, title: str, info) -> None:
            running.pop(vid, None)
            if vid in job["queue"]:
                job["queue"].remove(vid)
            if kind == "ok":
                _remember_info(v, info)
                path = _downloaded_path(info)
                if path:
                    set_local_file(v, course.id, vid, path, downloaded=True)
                    job["saved"] += 1
                    try:
                        size = path.stat().st_size
                    except OSError:
                        size = 0
                    job["bytes"] += size
                    job.setdefault("completed", []).append({"id": vid, "title": title, "size": size, "at": time.time()})
                job["done"] += 1
            elif kind == "failed":
                job["failed"].append({"id": vid, "title": title, "why": info})
                job["done"] += 1
            elif kind == "space":
                trouble["space"] = True
                job["stop"] = True
            elif kind == "stopped" and vid in job.get("skip", ()) and not job["stop"]:
                job["total"] = max(0, job["total"] - 1)  # cancelled on its own: it's not part of this download now

        i = 0
        with yt_dlp.YoutubeDL({**opts, "extract_flat": "in_playlist", "skip_download": True}) as flat:
            while True:
                if not job["stop"]:
                    with _LOCK:  # what was asked for while this ran (more lessons, or the whole course)
                        asked, job["pending"] = job["pending"], []
                        whole = bool(job.get("want_all"))
                        if whole:
                            job["want_all"], job["all"] = False, True
                        if not asked and not whole and i >= len(todo) and not running:
                            job["state"] = "done" if not job["failed"] else "partly"
                            break
                    if whole:
                        expand(course_videos(course), flat)
                    if asked:
                        expand(asked, flat)
                    # start as many as there are places for (waiting ones wait for a place in their thread)
                    while i < len(todo) and len(running) < SETTINGS["parallel"]:
                        with _LOCK:  # "Download next": a waiting video moves to the front
                            for want in job.get("first") or []:
                                k = next((n for n in range(i, len(todo)) if todo[n][0] == want), None)
                                if k is not None:
                                    todo.insert(i, todo.pop(k))
                            job["first"] = []
                            job["queue"][:] = [x for x, _ in todo[i:]] + [x for x in job["queue"] if x in running]
                        vid, title = todo[i]
                        i += 1
                        if vid in job.setdefault("skip", set()):  # cancelled while it waited
                            job["total"] = max(0, job["total"] - 1)
                            if vid in job["queue"]:
                                job["queue"].remove(vid)
                            continue
                        if local_file(v, course.id, vid):
                            job["done"] += 1
                            if vid in job["queue"]:
                                job["queue"].remove(vid)
                            continue
                        t = threading.Thread(target=worker, args=(vid, title), daemon=True)
                        running[vid] = t
                        t.start()
                elif not running:
                    if trouble["space"]:
                        raise NoSpace()
                    raise Stopped()
                try:
                    finish(*results.get(timeout=0.3))
                except _queue.Empty:
                    pass
    except Stopped:
        job["state"] = "stopped"
    except NoSpace:
        job["state"], job["error"] = "failed", ("The disk is almost full, so inPace stopped downloading. The videos that "
                                               "finished are kept. Free some space or choose another folder, then "
                                               "press Download the rest.")
        _clean_partial(out_dir)
    except ToolProblem as e:
        job["state"], job["error"] = "failed", str(e)
    except Exception as e:
        job["state"], job["error"] = "failed", _short(e)
    finally:
        job["title"], job["percent"], job["current"] = "", 0.0, ""
        job["active"] = {}
        job["finished"] = time.time()
        try:
            _tell_done(v, job)
        except Exception:
            pass
        try:
            v.db.close()
        except Exception:
            pass


def _sync_current(job: dict) -> None:
    """The older single-video fields (current, title, percent) follow the first video downloading now."""
    act = dict(job.get("active") or {})
    if act:
        vid, a = next(iter(act.items()))
        job["current"], job["title"], job["percent"] = vid, a.get("title", ""), a.get("percent", 0.0)
    else:
        job["current"], job["percent"] = "", 0.0


def again_items(job: dict, failed_only: bool = False) -> list[dict] | None:
    """What to ask for to carry on a stopped or failed download (None: the whole course again)."""
    titles = job.get("titles") or {}
    if failed_only:
        return [{"kind": "video", "id": f["id"], "title": f.get("title", ""), "lessons": [f.get("title", "")]}
                for f in job.get("failed") or []]
    if job.get("all") or job.get("want_all"):
        return None
    lists = set(job.get("lists") or [])
    out = []
    for x in job.get("asked") or []:
        kind = "playlist" if x in lists else "video"
        out.append({"kind": kind, "id": x, "title": titles.get(x, ""), "lessons": [titles.get(x, x)]})
    return out


def _tell_done(v, job: dict) -> None:
    """On a computer: one notification when a course's downloads end (Android shows its own, with progress)."""
    if on_android() or not job.get("saved") or job.get("state") == "stopped" or "pytest" in sys.modules:
        return
    if any(j.get("state") == "running" for j in JOBS.values() if j is not job):
        return  # one notification at the end of everything
    from . import notifier
    n = sum(j.get("saved", 0) for j in JOBS.values())
    t = TRANSLATE[0]
    notifier.notify(t("Downloads finished"), t("{n} videos are ready to watch offline.").replace("{n}", str(n)) if n != 1
                    else t("1 video is ready to watch offline."), "/downloads", v.home)


TRANSLATE = [lambda text: text]  # the app puts its translator here


def overview(vault=None) -> dict:
    """Every course's download, for the Downloads page, the progress pill and the phone's notification."""
    courses, speed, active_n, waiting_n = [], 0, 0, 0
    got_all = size_all = 0.0
    for cid, job in list(JOBS.items()):
        act = [{"id": vid, **a} for vid, a in list((job.get("active") or {}).items())]
        running = job.get("state") == "running"
        total = int(job.get("total") or 0)
        done = int(job.get("done") or 0)
        part = sum((a.get("percent") or 0) / 100 for a in act)
        percent = round(100 * (done + part) / total, 1) if total else 0.0
        waiting = len([x for x in (job.get("queue") or []) if x not in {a["id"] for a in act} and x not in (job.get("skip") or ())]) \
            + len(job.get("pending") or [])
        if running:
            speed += sum(int(a.get("speed") or 0) for a in act)
            active_n += len(act)
            waiting_n += waiting
            got_all += done + part
            size_all += total
        titles = job.get("titles") or {}
        now_ids = {a["id"] for a in act}
        skip = set(job.get("skip") or ())
        wait_list = [{"id": vid, "title": titles.get(vid, vid)} for vid in list(job.get("queue") or [])
                     if vid not in now_ids and vid not in skip]
        wait_list += [{"id": it.get("id"), "title": it.get("title") or (it.get("lessons") or [it.get("id")])[0]}
                      for it in list(job.get("pending") or [])]
        if running and job.get("want_all"):
            wait_list.append({"id": "", "title": ""})  # the rest of the course: listed once it's read
        courses.append({"course": cid, "title": job.get("course_title") or cid, "state": job.get("state"),
                        "waiting_list": wait_list if running else [],
                        "completed": list(job.get("completed") or []),
                        "done": done, "total": total, "percent": percent, "active": act, "waiting": waiting,
                        "failed": list(job.get("failed") or []), "error": job.get("error", ""),
                        "note": job.get("title", "") if not act else "", "saved": job.get("saved", 0),
                        "bytes": job.get("bytes", 0), "finished": job.get("finished", 0), "all": bool(job.get("all"))})
    running = [c for c in courses if c["state"] == "running"]
    return {"running": bool(running), "courses": courses, "speed": speed, "active": active_n, "waiting": waiting_n,
            "percent": round(100 * got_all / size_all, 1) if size_all else 0.0,
            "parallel": SETTINGS["parallel"], "rate": SETTINGS.get("rate_key", "0")}


def on_device(vault) -> list[dict]:
    """The videos on this device, course by course: how many, how much space, and where."""
    out = []
    for c in vault.courses():
        items = course_videos(c)
        if not items:
            continue
        vids = []
        for it in items:
            if it["kind"] == "video":
                vids.append((it["id"], it.get("lessons", [""])[0] if it.get("lessons") else it["id"]))
            else:
                vids += [(x["id"], x.get("title", x["id"])) for x in playlist_items(vault, c.id, it["id"])]
        files, size, mine = [], 0, 0
        for vid, title in vids:
            p = local_file(vault, c.id, vid)
            if not p:
                continue
            try:
                n = p.stat().st_size
            except OSError:
                n = 0
            size += n
            mine += (vault._meta(f"ytdl:{c.id}:{vid}", "") or "") == "1"
            files.append({"id": vid, "title": title, "path": str(p), "size": n})
        if files:
            out.append({"course": c, "files": files, "size": size, "count": len(files), "total": len(vids),
                        "downloaded": mine, "folder": str(Path(files[0]["path"]).parent)})
    return out


def _clean_partial(folder) -> None:
    """Remove half-downloaded pieces (.part files) so they don't keep using the space."""
    try:
        for p in Path(folder).glob("*.part"):
            p.unlink()
    except (OSError, TypeError):
        pass


class _Quiet:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def _short(e: Exception) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "").strip()
    return (text.splitlines() or [type(e).__name__])[0][:240]


def _remember_info(v, info: dict) -> None:
    vid = info.get("id")
    if vid and info.get("title"):
        v._set_meta(f"yttitle:{vid}", json.dumps({"title": info["title"][:200], "duration": info.get("duration") or 0},
                                                 ensure_ascii=False))


def _downloaded_path(info: dict) -> Path | None:
    for d in info.get("requested_downloads") or []:
        p = d.get("filepath") or d.get("filename")
        if p and Path(p).is_file():
            return Path(p)
    p = info.get("filepath") or info.get("_filename")
    return Path(p) if p and Path(p).is_file() else None


def cancel_video(course_id: str, vid: str) -> None:
    """Take one video out of a running download (it stops if it's downloading)."""
    job = JOBS.get(course_id)
    if not job or job.get("state") != "running":
        return
    with _LOCK:
        job.setdefault("skip", set()).add(vid)
        job["pending"] = [it for it in job.get("pending") or [] if it.get("id") != vid]


def download_next(course_id: str, vid: str) -> None:
    """Move a waiting video to the front of its course's list."""
    job = JOBS.get(course_id)
    if job and job.get("state") == "running":
        with _LOCK:
            job.setdefault("first", []).append(vid)


def stop(course_id: str) -> None:
    job = JOBS.get(course_id)
    if job and job["state"] == "running":
        job["stop"] = True


def look_up_titles(vault, course) -> None:
    """Ask YouTube (through yt-dlp) for each video's title and length, so files can be matched better.
    Quick: it reads the video pages without downloading anything. Fails quietly when offline."""
    yt_dlp = load(vault.home)
    if yt_dlp is None:
        return
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": "in_playlist",
            "logger": _Quiet(), "js_runtimes": _js_runtimes(), "socket_timeout": 10}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            for it in course_videos(course)[:60]:
                if it["kind"] == "video" and video_info(vault, it["id"]).get("title"):
                    continue
                try:
                    info = ydl.extract_info(watch_url(it), download=False, process=it["kind"] == "playlist") or {}
                except Exception:
                    continue
                if it["kind"] == "playlist":
                    entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
                    vault._set_meta(f"ytlist:{course.id}:{it['id']}", json.dumps(
                        [{"id": e["id"], "title": e.get("title") or e["id"]} for e in entries], ensure_ascii=False))
                    for e in entries:
                        _remember_info(vault, e)
                else:
                    _remember_info(vault, info)
    except Exception:
        pass


# ---------------------------------------------------------------------------------------------------------------
# Matching files you already have to the lesson videos
# ---------------------------------------------------------------------------------------------------------------
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DIACRITICS = re.compile(r"[ً-ٰٟـ]")  # harakat, dagger alef, tatweel
_JUNK = {"1080p", "720p", "480p", "360p", "240p", "2160p", "1440p", "4k", "8k", "hd", "fhd", "uhd", "sd", "hq",
         "x264", "x265", "h264", "h265", "hevc", "avc", "aac", "webrip", "webdl", "web", "dl", "bluray", "mp4", "mkv",
         "webm", "yt", "youtube", "official", "full", "copy", "final", "new", "the", "a", "an", "and", "of", "to",
         "in", "for", "with", "on", "و", "في", "من", "الى", "على", "مع", "عن", "ال"}
_NUM_WORDS = r"(?:lesson|lecture|lec|part|pt|episode|ep|video|vid|chapter|ch|module|session|day|class|unit|" \
             r"درس|الدرس|محاضره|المحاضره|حلقه|الحلقه|جزء|الجزء|فيديو|الفيديو|يوم|اليوم)"
_LEAD_NUM = re.compile(rf"^\s*(?:{_NUM_WORDS}\s*)?(\d{{1,3}})(?!\d)(?:\s*(?:of|/)\s*\d+)?\s*[-_.):|\]]*\s*")
_ANY_NUM = re.compile(rf"\b{_NUM_WORDS}\s*(\d{{1,3}})\b")
_YT_ID = re.compile(r"(?<![A-Za-z0-9_-])([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])")


def normalize(text: str) -> str:
    """Lower case, one kind of each Arabic letter, no accents or marks, words split on any separator."""
    t = unicodedata.normalize("NFKC", text or "").translate(_ARABIC_DIGITS).lower()
    t = _DIACRITICS.sub("", t)
    t = re.sub("[أإآٱ]", "ا", t).replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c) or "؀" <= c <= "ۿ")
    t = t.replace("&", " and ").replace("+", " plus ")
    t = re.sub(r"[\[\](){}]", " ", t)
    t = re.sub(r"[_\-–—.,:;|/\\'\"!?#~*@%^=<>`’‘“”،؛؟]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _number(text: str) -> int | None:
    t = normalize(text)
    m = _LEAD_NUM.match(t) or _ANY_NUM.search(t)
    return int(m.group(1)) if m else None


def _tokens(text: str) -> list[str]:
    t = normalize(text)
    t = _LEAD_NUM.sub("", t, count=1)
    words = []
    for w in t.split():
        if w in _JUNK:
            continue
        if len(w) > 3 and w.startswith("ال") and "؀" <= w[2] <= "ۿ":
            w = w[2:]  # "الحاويات" and "حاويات" are the same word
        words.append(w)
    return words


def _same_word(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4 or a.isdigit() or b.isdigit():
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.84  # small typos: "analytcs" and "analytics"


def text_score(a: str, b: str) -> float:
    """How alike two names are, from 0 to 1, after cleaning both the same way."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    hits = sum(1 for w in ta if any(_same_word(w, x) for x in tb))
    hits_b = sum(1 for w in tb if any(_same_word(w, x) for x in ta))
    contain = max(hits / len(ta), hits_b / len(tb))
    dice = (hits + hits_b) / (len(ta) + len(tb))
    seq = SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    if not hits:  # no word in common: letters alike count for little ("kubernetesbasics" still scores)
        return 0.6 * seq if seq >= 0.8 else 0.0
    return max(seq, 0.55 * dice + 0.45 * contain)


def mp4_seconds(path: Path) -> float:
    """The length of an MP4/MOV/M4V file, read from its header (no extra tools needed). 0 if unknown."""
    try:
        with open(path, "rb") as f:
            end = path.stat().st_size

            def boxes(start: int, stop: int):
                pos = start
                while pos + 8 <= stop:
                    f.seek(pos)
                    head = f.read(16)
                    if len(head) < 8:
                        return
                    size, kind = struct.unpack(">I4s", head[:8])
                    hdr = 8
                    if size == 1:
                        size, hdr = struct.unpack(">Q", head[8:16])[0], 16
                    elif size == 0:
                        size = stop - pos
                    if size < hdr:
                        return
                    yield kind, pos + hdr, pos + size
                    pos += size

            for kind, s, e in boxes(0, end):
                if kind == b"moov":
                    for k2, s2, e2 in boxes(s, e):
                        if k2 == b"mvhd":
                            f.seek(s2)
                            data = f.read(32)
                            if data[0] == 1:
                                scale, dur = struct.unpack(">IQ", data[20:32])
                            else:
                                scale, dur = struct.unpack(">II", data[12:20])
                            return dur / scale if scale else 0.0
    except (OSError, struct.error, IndexError):
        pass
    return 0.0


def file_seconds(path: Path) -> float:
    if path.suffix.lower() in (".mp4", ".m4v", ".mov", ".3gp"):
        s = mp4_seconds(path)
        if s:
            return s
    probe = shutil.which("ffprobe")
    if probe:
        import subprocess
        try:
            out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                 capture_output=True, text=True, timeout=8).stdout.strip()
            return float(out or 0)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return 0.0


def video_files(folder: Path, limit: int = 3000) -> list[Path]:
    out = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__"))
        if len(Path(root).relative_to(folder).parts) > 5:
            dirs[:] = []
        for name in sorted(files):
            if Path(name).suffix.lower() in VIDEO_EXT and not name.startswith("."):
                out.append(Path(root) / name)
                if len(out) >= limit:
                    return out
    return out


def score(target: dict, path: Path, seconds: float) -> tuple[float, str]:
    """How sure we are that this file is this video (0 to 1), and the main reason, in plain words."""
    stem = path.stem
    if target.get("id") and target["id"] in {m.group(1) for m in _YT_ID.finditer(stem)}:
        return 1.0, "The file name has the video's YouTube id."
    names = [n for n in target.get("names", []) if n]
    text = max((text_score(stem, n) for n in names), default=0.0)
    # A folder named after the lesson counts too ("03 - Docker/video.mp4").
    text = max(text, max((text_score(path.parent.name, n) * 0.9 for n in names), default=0.0)) \
        if path.parent.name else text
    s, why = text, "The names are alike."
    num = _number(stem)
    if num is not None and target.get("index"):
        if num == target["index"]:
            s += 0.15
        elif text < 0.95:
            s -= 0.08
    want = target.get("seconds") or 0
    if want and seconds:
        gap = abs(want - seconds) / max(want, 1)
        if gap <= 0.02 or abs(want - seconds) <= 3:
            s += 0.25
            why = "The names are alike and the length matches." if text >= 0.45 else "The length matches."
        elif gap > 0.15:
            s -= 0.25
    return max(0.0, min(1.0, s)), why


def match(targets: list[dict], files: list[Path], seconds=file_seconds) -> list[dict]:
    """Pair each target video with the file that fits it best, without using a file twice.
    targets: [{"key", "id", "names": [...], "index": n, "seconds": length or 0}]
    Returns [{"key", "file" (Path or None), "score", "why", "sure": "yes" | "check" | "no"}] in target order."""
    lengths = {}
    need_len = any(t.get("seconds") for t in targets)
    for f in files:
        lengths[f] = seconds(f) if need_len else 0.0
    pairs = []
    for ti, t in enumerate(targets):
        for f in files:
            sc, why = score(t, f, lengths[f])
            if sc >= 0.3:
                pairs.append((sc, ti, f, why))
    pairs.sort(key=lambda p: (-p[0], p[1], str(p[2])))
    used_t, used_f, got = set(), set(), {}
    for sc, ti, f, why in pairs:
        if ti in used_t or f in used_f:
            continue
        used_t.add(ti)
        used_f.add(f)
        got[ti] = (f, sc, why)
    # With exactly one video left and one file left, and the order agrees, take it (common: "video.mp4").
    left_t = [i for i in range(len(targets)) if i not in got]
    left_f = [f for f in files if f not in used_f]
    if len(left_t) == 1 and len(left_f) == 1:
        got[left_t[0]] = (left_f[0], 0.4, "It's the only file left.")
    out = []
    for i, t in enumerate(targets):
        f, sc, why = got.get(i, (None, 0.0, ""))
        sure = "yes" if sc >= 0.62 else "check" if f else "no"
        out.append({"key": t["key"], "file": f, "score": round(sc, 2), "why": why, "sure": sure})
    return out


def targets_for(vault, course) -> list[dict]:
    """What to look for: every video of the course, with every name we know for it."""
    out = []
    n = 0
    for it in course_videos(course):
        if it["kind"] == "video":
            n += 1
            info = video_info(vault, it["id"])
            names = [info.get("title", "")] + it["lessons"]
            if len(it["lessons"]) > 1 or len(course_videos(course)) == 1:
                names.append(course.title)  # one long video cut into lessons is often named like the course
            label = info.get("title") or (it["lessons"][0] if len(it["lessons"]) == 1 else "")
            out.append({"key": it["id"], "id": it["id"], "names": names, "index": n,
                        "seconds": info.get("duration") or 0, "label": label, "lessons": it["lessons"]})
        else:
            for k, e in enumerate(playlist_items(vault, course.id, it["id"]), start=1):
                n += 1
                info = video_info(vault, e["id"])
                out.append({"key": e["id"], "id": e["id"], "names": [e.get("title", ""), info.get("title", "")],
                            "index": k, "seconds": info.get("duration") or 0, "label": e.get("title") or e["id"]})
    return out
