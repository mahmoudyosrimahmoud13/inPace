"""Turn media in lessons into players: videos, audio, web pages, PDFs, pictures and online videos.

In a lesson, media is written like a picture in Markdown:

    ![Intro video](media/intro.mp4)
    ![Pronunciation](media/word.mp3)
    ![Try it](sims/pendulum.html)
    ![](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

A YouTube or Vimeo link alone on a line also becomes a player. A lesson can also have one main
`media:` item, shown at the top. Online videos load only when the person presses play.
"""
from __future__ import annotations

import html
import json
import re
from typing import Callable
from urllib.parse import quote, unquote

from .course import embed_id, is_url, local_ref, media_kind, page_range, youtube_playlist, youtube_segment

Tr = Callable[[str], str]

_IMG = re.compile(r'<img src="([^"]*)" alt="([^"]*)"\s*/?>')
_LONE_LINK = re.compile(r'<p(?: dir="\w+")?>\s*<a href="([^"]+)">([^<]*)</a>\s*</p>')  # paragraphs carry their direction
_LONE_URL = re.compile(r'<p(?: dir="\w+")?>\s*(https?://[^\s<]+)\s*</p>')
_LINK = re.compile(r'<a href="([^"]+)">')


def media_url(course_id: str, rel: str) -> str:
    return f"/m/{quote(course_id)}/{quote(rel)}"


class CourseFiles:
    """What the lesson page needs to know about a course's files on this computer.
    Calling it answers "is this file here?"; find() says where; resume() is where you stopped watching."""

    def __init__(self, find: Callable, resume: Callable[[str], float] = lambda key: 0.0, speed: float = 1.0,
                 yt_local: Callable[[str], str | None] = lambda vid: None,
                 yt_list: Callable[[str], list] = lambda plist: [], book: str = "", book_link: str = "",
                 yt_save: Callable[[str, str], dict | None] = lambda vid, plist: None,
                 parts: dict | None = None, subs: Callable[[str], list] = lambda media: [], sub_action: str = "",
                 open_action: str = "", system: str = ""):
        self.find = find
        self.resume = resume
        self.speed = speed
        self.yt_local = yt_local  # video id -> address of its copy on this computer (downloaded or your own file)
        self.yt_list = yt_list    # playlist id -> [{"id", "title", "url"}] of the videos that are on this computer
        self.book = book            # the course's book, which each learner gets themselves (not shared with it)
        self.book_link = book_link  # where to show inPace your copy
        self.yt_save = yt_save      # (video id, playlist id) -> what the "Download this video" button needs, or None
        self.parts = parts or {}    # video id -> [(start, end, lesson id)]: a long YouTube video cut into lessons
        self.subs = subs            # a video (path in the course, or "yt:ID") -> [{"label", "src", "lang"}] subtitles
        self.sub_action = sub_action    # where "Add a subtitle file" sends it
        self.open_action = open_action  # where "Open in your video player" asks (empty on phones)
        self.system = system            # "linux", "windows", "mac", "android": for the "can't play" help

    def __call__(self, rel: str) -> bool:
        return self.find(rel) is not None


CODE_LIMIT = 300_000
SKIP_DIRS = {"node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build", ".idea", ".vscode"}


def _lexer_name(name: str) -> str:
    from pygments.lexers import get_lexer_for_filename
    from pygments.util import ClassNotFound
    low = name.lower()
    if low.startswith("dockerfile"):
        return "docker"
    try:
        return get_lexer_for_filename(name).aliases[0]
    except (ClassNotFound, IndexError):
        return "text"


def code_block(path, name: str, url: str, t: Tr) -> str:
    """A code file, coloured, with the usual Copy button (added by app.js)."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    e = html.escape
    try:
        size = path.stat().st_size
        if size > CODE_LIMIT:
            return (f'<p class="note">{e(t("This file is too big to show here."))} '
                    f'<a href="{url}?view=1" target="_blank" rel="noopener">{e(t("Open it"))}</a></p>')
        raw = path.read_bytes()
        if b"\x00" in raw[:4096]:
            return f'<p class="note"><a href="{url}" target="_blank" rel="noopener">{e(name)}</a></p>'
        text = raw.decode("utf-8", errors="replace")
    except OSError:
        return ""
    lang = _lexer_name(name)
    if name.lower().endswith(".ipynb"):
        text = _notebook_text(text)
        lang = "python"
    body = highlight(text, get_lexer_by_name(lang), HtmlFormatter(nowrap=True)) if lang != "text" else e(text)
    return f'<pre dir="ltr"><code class="language-{e(lang)}">{body}</code></pre>'


def open_buttons(files, rel: str, url: str, t: Tr, folder: bool = False) -> str:
    """"Open it" for a code file or a project folder.

    On a computer it opens in your own app (VS Code, Jupyter, your editor) and "Show in folder" opens the
    folder it's in. On a phone, or if that fails, the file shows as plain text in a new tab."""
    e = html.escape
    action = getattr(files, "open_action", "") if files else ""
    if not action:
        return "" if folder else f'<a href="{url}?view=1" target="_blank" rel="noopener">{e(t("Open it"))}</a>'
    data = f'data-open-file="{e(action)}" data-media="{e(rel)}"'
    if folder:
        return (f'<span class="open-btns"><button type="button" class="linkish" {data} data-reveal>'
                f'{e(t("Open the folder"))}</button></span>')
    return (f'<span class="open-btns"><button type="button" class="linkish" {data} data-view="{e(url)}?view=1">'
            f'{e(t("Open it"))}</button><button type="button" class="linkish" {data} data-reveal>'
            f'{e(t("Show in folder"))}</button></span>')


def _notebook_text(text: str) -> str:
    """The code cells of a Jupyter notebook, one after another."""
    import json
    try:
        cells = json.loads(text).get("cells", [])
    except (ValueError, AttributeError):
        return text
    out = []
    for c in cells:
        src = "".join(c.get("source", []))
        out.append(src if c.get("cell_type") == "code" else "\n".join("# " + x for x in src.splitlines()))
    return "\n\n".join(out)


def folder_view(course_id: str, rel: str, folder, t: Tr, course_files=None) -> str:
    """A project folder from the course: every code file, coloured, one under the other (first one open)."""
    files = []
    for p in sorted(folder.rglob("*"), key=lambda p: str(p.relative_to(folder)).lower()):
        parts = p.relative_to(folder).parts
        if p.is_file() and not any(x in SKIP_DIRS or x.startswith(".") for x in parts[:-1]) \
                and media_kind(p.name) in ("code", "html", "image", "pdf"):
            files.append(p)
        if len(files) >= 80:
            break
    if not files:
        return f'<p class="note">{html.escape(t("This folder has no code files."))}</p>'
    items = []
    for i, p in enumerate(files):
        sub = p.relative_to(folder).as_posix()
        url = media_url(course_id, f"{rel.rstrip('/')}/{sub}")
        if media_kind(p.name) == "code":
            head = open_buttons(course_files, f"{rel.rstrip('/')}/{sub}", url, t) \
                if course_files and course_files.open_action else ""
            inner = (f'<div class="code-file-head" dir="ltr"><span></span>{head}</div>' if head else "") \
                + code_block(p, p.name, url, t)
        else:
            inner = f'<p><a href="{url}" target="_blank" rel="noopener">{html.escape(t("Open it"))}</a></p>'
        items.append(f'<details class="code-file"{" open" if i == 0 else ""}><summary dir="ltr">{html.escape(sub)}</summary>{inner}</details>')
    top = open_buttons(course_files, rel.rstrip("/") + "/", "", t, folder=True)
    top = f'<div class="code-file-head" dir="ltr"><span></span>{top}</div>' if top else ""
    return f'{top}<div class="code-folder">{"".join(items)}</div>'


def _clock(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def srt_to_vtt(data: bytes) -> str:
    """A subtitle file as WebVTT, the kind players read. SRT just needs a header and dots in its times.
    Old Arabic files are often in Windows-1256, not UTF-8: both work."""
    for enc in ("utf-8-sig", "utf-16", "cp1256", "latin-1"):
        try:
            text = data.decode(enc)
            if enc == "utf-16" and not data[:2] in (b"\xff\xfe", b"\xfe\xff"):
                continue
            break
        except UnicodeDecodeError:
            continue
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    if text.lstrip().startswith("WEBVTT"):
        return text
    text = re.sub(r"(\d{1,2}:\d{2}:\d{2}),(\d{1,3})", r"\1.\2", text)
    return "WEBVTT\n\n" + text.strip() + "\n"


SUB_LANGS = {"ar": "العربية", "ara": "العربية", "arabic": "العربية", "en": "English", "eng": "English",
             "english": "English", "fr": "Français", "de": "Deutsch", "es": "Español", "tr": "Türkçe"}


def sibling_subs(video) -> list[tuple[str, str, Path]]:
    """Subtitle files next to a video: "Lesson 1.srt", "Lesson 1.ar.srt", "Lesson 1.English.vtt".
    -> [(label, language code, path)]"""
    from .course import SUB_EXT
    out = []
    try:
        items = sorted(video.parent.iterdir())
    except OSError:
        return []
    stem = video.stem.lower()
    for f in items:
        name = f.name.lower()
        if f.suffix.lower() not in SUB_EXT or not f.is_file() or not name.startswith(stem):
            continue
        rest = f.name[len(video.stem):-len(f.suffix)].strip(" ._-")
        if rest and not name.startswith(stem + ".") and not name.startswith(stem + "_"):
            continue
        lang = rest.lower() if rest.lower() in SUB_LANGS else ""
        out.append((SUB_LANGS.get(rest.lower(), rest) or "Subtitles", lang[:2], f))
        if len(out) >= 10:
            break
    return out


def video_player(url: str, key: str, resume: float, speed: float, t: Tr, start: int = 0, end: int | None = None,
                 tracks: list | None = None, media: str = "", files: "CourseFiles | None" = None, name: str = "") -> str:
    """Our own video player: big play button, speed, +-10 s, full screen, keyboard keys, and it remembers
    the second you stopped at. Without JavaScript it's a normal video with the browser's controls.
    start and end make it play only one piece of the file (a lesson cut from a long video)."""
    e = html.escape
    labels = player_labels(t, name)
    data = " ".join(f'data-l-{k}="{e(v)}"' for k, v in labels.items())
    return _video_player_html(url, key, resume, speed, t, start, end, tracks, media, files, name, data)


def player_labels(t: Tr, name: str = "") -> dict:
    """Every word inPace's video player shows, for files and YouTube alike."""
    return {"play": t("Play"), "pause": t("Pause"), "back": t("Back 10 seconds"), "fwd": t("Forward 10 seconds"),
              "mute": t("Mute"), "unmute": t("Sound on"), "speed": t("Speed"), "full": t("Full screen"),
              "pip": t("Picture in picture"), "restart": t("Start over"),
              "miniback": t("Back to the lesson"), "miniclose": t("Close the video"),
              "miniout": t("Pop out: a small window on top of your other apps"), "minidrag": t("Drag to move the video"),
              "ended": t("Finished! Mark the lesson as done below."),
              "cc": t("Subtitles"), "ccoff": t("Off"), "ccadd": t("Add a subtitle file (.srt or .vtt)…"),
              "ccsaved": t("Subtitles added."), "ccbad": t("That isn't a subtitle file. Choose a .srt or .vtt file."),
              "failtitle": t("This video can't play here."), "failopen": t("Open in your video player"),
              "failagain": t("Try again"), "failcopy": t("Copy"), "failcopied": t("Copied"),
              "failformat": t("Its format ({ext}) doesn't play in this window. MP4 videos play everywhere: convert it with a free tool like HandBrake, or open it in your own player.").format(ext=(name.rsplit(".", 1)[-1].upper() if "." in name else "?")),
              "faillinux": t("Your computer is missing the video support the app window needs. Install it once, then restart inPace:"),
              "failnopic": t("Only the sound plays: the video inside uses a format (like H.265) this window can't show."),
              "failphone": t("Your phone can't play this format. MP4 videos play everywhere: convert it with a free tool like HandBrake.")}


def _video_player_html(url, key, resume, speed, t, start, end, tracks, media, files, name, data) -> str:
    e = html.escape
    if resume and (resume < start or (end and resume >= end - 5)):
        resume = 0.0
    hint = ""
    if resume > start + 5:
        hint = (f'<p class="resume-hint small muted">{e(t("You stopped at {time}. It continues from there.").format(time=_clock(resume)))} '
                f'<button type="button" class="link" data-restart>{e(t("Start over"))}</button></p>')
    frag = f"#t={start}" + (f",{end}" if end else "") if (start or end) else ""
    extra = ""
    if files is not None:
        if files.sub_action and media:
            extra += f' data-sub-action="{e(files.sub_action)}" data-media="{e(media)}"'
        if files.open_action and media and not media.startswith("yt:"):
            extra += f' data-open-action="{e(files.open_action)}"'
        if files.system:
            extra += f' data-system="{e(files.system)}"'
    if name:
        extra += f' data-ext="{e(name.rsplit(".", 1)[-1].lower() if "." in name else "")}"'
    tags = "".join(f'<track kind="subtitles" src="{e(tr["src"])}" label="{e(tr["label"])}"'
                   + (f' srclang="{e(tr["lang"])}"' if tr.get("lang") else "") + ">" for tr in (tracks or []))
    return (f'<div class="player" tabindex="0" data-player data-key="{e(key)}" data-resume="{resume:.1f}" data-speed="{speed:g}" '
            f'data-start="{start}" data-end="{end or 0}" {data}{extra}>'
            f'<video controls preload="metadata" playsinline src="{url}{frag}">{tags}</video></div>{hint}')


def youtube_player(course_id: str, ref: str, cap: str, exists: Callable[[str], bool], t: Tr) -> str:
    """A YouTube video, a piece of one (t=... and end=... in the link), or a playlist.
    It loads only when you press play, and it continues from where you stopped (saved on this computer)."""
    e = html.escape
    vid, plist = embed_id(ref), youtube_playlist(ref)
    start, end = youtube_segment(ref)
    files = exists if isinstance(exists, CourseFiles) else None
    if vid:
        src = (f"https://www.youtube-nocookie.com/embed/{vid}?autoplay=1&rel=0&enablejsapi=1"
               "&controls=0&playsinline=1&modestbranding=1&iv_load_policy=3&fs=0&disablekb=1")  # inPace's own bar
        watch = f"https://www.youtube.com/watch?v={vid}" + (f"&t={start}s" if start else "")
        key = f"{course_id}|yt:{vid}:{start}-{end or ''}"
    else:
        src = f"https://www.youtube-nocookie.com/embed/videoseries?list={plist}&autoplay=1&rel=0&enablejsapi=1"
        watch = f"https://www.youtube.com/playlist?list={plist}"
        key = f"{course_id}|ytlist:{plist}"
    resume = files.resume(key) if files else 0.0
    if files and vid and files.yt_local(vid):
        return _offline_youtube(files.yt_local(vid), key, resume, files.speed, start, end, watch, cap, t, vid, files)
    save = save_button(files.yt_save(vid, "" if vid else plist), vid, "" if vid else plist, t) if files else ""
    if files and plist and files.yt_list(plist):
        return _offline_playlist(course_id, files, files.yt_list(plist), watch, cap, t, save)
    if resume and (resume < start or (end and resume >= end - 5)):
        resume = 0.0
    part = part_label(vid, start, end, files, t) if vid else ""
    hint = ""
    if resume > start + 5:
        hint = (f'<span class="small resume-hint">{e(t("You stopped at {time}. It continues from there.").format(time=_clock(resume)))} '
                f'<button type="button" class="link" data-yt-restart>{e(t("Start over"))}</button></span>')
    labels = {**player_labels(t), "piece": t("This part"), "quality": t("Quality"), "auto": t("Auto"),
              "qwait": t("The other qualities show here once the video plays."),
              "qget": t("Getting {q}…"), "qfail": t("{q} isn't available here right now, so YouTube picks the quality."),
              "qnote": t("Auto: YouTube picks. Any other quality plays in inPace's own player."),
              "ccyt": t("Subtitles (YouTube)"),
              "ccfinding": t("Finding subtitles…"), "ccnone": t("This video has no subtitles."), "ad": t("Ad: the lesson starts after it"),
              "err": t("YouTube won't play this video inside inPace."), "open": t("Watch it on YouTube"),
              "slow": t("Not playing? Watch it on YouTube instead."),
              "finding": t("Getting the video without ads…"),
              "noads": t("No ads."), "hd": t("Sharper on YouTube")}
    data = " ".join(f'data-l-{k}="{e(v)}"' for k, v in labels.items())
    speed = f' data-speed="{files.speed:g}"' if files and getattr(files, "speed", None) else ""
    from . import ytrules
    rules = ytrules.current()
    speed += f' data-yt-rules="{e(json.dumps(rules))}"'
    play = f'<button type="button" class="btn primary play">▶ {e(t("Play video"))}</button>'
    if vid and rules["ad_block"]:  # two choices in the video's place: YouTube's player, or inPace's own with no ads
        play = (f'<div class="yt-choices">'
                f'<button type="button" class="yt-choice play"><span class="yt-choice-icon">{_PLAY_ICON}</span>'
                f'<b>{e(t("Play on YouTube"))}</b><small>{e(t("Faster, more qualities"))}</small></button>'
                f'<button type="button" class="yt-choice" data-yt-noads="/yt-stream/{e(vid)}" '
                f'data-l-busy="{e(t("Getting it without ads…"))}" data-l-fail="{e(t("No ad-free copy right now."))}">'
                f'<span class="yt-choice-icon">{_NOADS_ICON}</span>'
                f'<b>{e(t("Play without ads"))}</b><small>{e(t("Can take a little longer"))}</small></button></div>'
                f'<p class="small yt-choice-note" data-yt-noads-note hidden></p>')
    if not rules["own_controls"]:  # switched off from the website: YouTube's own player and buttons
        src = src.replace("&controls=0", "").replace("&fs=0", "").replace("&disablekb=1", "")
    return (f'<figure class="media embed">{part}<div class="embed-box" data-embed="{e(src)}" data-yt-key="{e(key)}" '
            f'data-yt-id="{e(vid or "")}"{speed} '
            f'data-start="{start}" data-end="{end or 0}" data-resume="{resume:.1f}" data-watch="{e(watch)}" {data}>'
            f'{play}{hint}'
            + ('' if 'yt-choices' in play else f'<span class="small">{e(t("From {site}. It loads from the internet when you press play.").format(site="YouTube"))}</span>')
            + f'<a class="small" href="{e(watch)}" target="_blank" rel="noopener">{e(t("Open on {site}").format(site="YouTube"))}</a>'
            f'</div>{save}{cap}</figure>')


_PLAY_ICON = '<svg width="34" height="34" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" fill="currentColor"/></svg>'
_NOADS_ICON = ('<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
               'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/>'
               '<path d="m5.6 5.6 12.8 12.8"/><path d="M10 9v6l5-3z" fill="currentColor" stroke="none"/></svg>')

_DOWNLOAD_ICON = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
                  'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v12"/>'
                  '<path d="m7 11 5 5 5-5"/><path d="M4 17v3h16v-3"/></svg>')


def part_label(vid: str, start: int, end: int | None, files, t: Tr) -> str:
    """The line above a lesson that plays only part of a long video: which part, and which minutes."""
    if not (start or end):
        return ""
    e = html.escape
    pieces = (files.parts.get(vid) if files is not None else None) or []
    n = next((i for i, (a, b, _) in enumerate(pieces, 1) if a == start and b == end), 0)
    if end:
        span = t("Plays {a} to {b} ({n} min) of the full video.").format(a=_clock(start), b=_clock(end),
                                                                         n=max(1, round((end - start) / 60)))
    else:
        span = t("Plays from {a} to the end of the full video.").format(a=_clock(start))
    head = t("Part {n} of {total}").format(n=n, total=len(pieces)) if n and len(pieces) > 1 else t("Part of a longer video")
    full = f"https://www.youtube.com/watch?v={vid}"
    when = f"{_clock(start)}–{_clock(end)}" if end else f"{_clock(start)}–"
    return (f'<p class="video-part" title="{e(span)}"><span class="vp-icon" aria-hidden="true">✂</span><b>{e(head)}</b>'
            f'<span class="vp-when" dir="ltr">{e(when)}</span><span class="sr-only">{e(span)}</span>'
            f'<a href="{e(full)}" target="_blank" rel="noopener" title="{e(t("Watch the full video"))}">{e(t("Full video"))}</a></p>')


def save_button(info: dict | None, vid: str, plist: str, t: Tr) -> str:
    """The small "Download this video" button under a YouTube lesson, so it plays without internet next time.
    It shows how the download is going; without JavaScript it's a plain form that comes back to the lesson."""
    if not info or info.get("state") == "saved":
        return ""
    e = html.escape
    state = info.get("state", "none")
    labels = {"downloading": t("Downloading this video… {percent}"), "waiting": t("In the download list, after the videos before it."),
              "saved": t("Saved on this device."), "play": t("Play the saved copy"),
              "failed": t("It didn't download."), "again": t("Try again"), "offline": t("inPace isn't answering. Try again in a moment."),
              "starting": t("Starting…")}
    data = " ".join(f'data-l-{k}="{e(v)}"' for k, v in labels.items())
    busy = state in ("downloading", "waiting")
    if vid:
        label = t("Download this video")
    elif info.get("have"):
        label = t("Download the rest of these videos")
    else:
        label = t("Download these videos")
    if state == "downloading":
        note = labels["downloading"].format(percent=f'{round(info.get("percent") or 0)}%')
    elif state == "waiting":
        note = labels["waiting"]
    elif state == "failed":
        note = f'{labels["failed"]} {info.get("why", "")}'.strip()
    else:
        note = ""  # the size is on the button; the rest is its tooltip
    tip = (t("About {size}. Then it plays without internet.").format(size=info["size"]) if info.get("size")
           else t("Then it plays without internet."))
    if state not in ("failed",) and info.get("size"):
        label = t("{label} · {size}").format(label=t("Download") if vid else label, size=info["size"])
    spin = '<span class="spin" aria-hidden="true"></span>' if busy else ""
    count = ""
    if plist and info.get("total"):
        count = f' <span class="small muted" dir="ltr">{info.get("have", 0)} / {info["total"]}</span>'
    return (f'<form method="post" action="{e(info["action"])}" class="yt-save" data-yt-save="{e(info["status"])}" '
            f'data-state="{e(state)}" {data}>'
            f'<input type="hidden" name="vid" value="{e(vid)}"><input type="hidden" name="list" value="{e(plist)}">'
            f'<button class="btn small" title="{e(tip)}"{" hidden" if busy else ""}>{_DOWNLOAD_ICON}'
            f'<span>{e(t("Try again") if state == "failed" else label)}</span></button>{count}'
            f'<span class="small {"muted" if not busy else ""} yt-save-note" data-yt-save-note dir="auto">'
            f'{spin}{e(note)}</span>'
            f'</form>')


def _offline_youtube(url: str, key: str, resume: float, speed: float, start: int, end: int | None, watch: str,
                     cap: str, t: Tr, vid: str = "", files=None) -> str:
    """A YouTube lesson playing the copy on this computer: no internet needed, same piece, same saved place."""
    e = html.escape
    media = f"yt:{vid}" if vid else ""
    tracks = files.subs(media) if files is not None and media else []
    return (f'<figure class="media video offline-yt">{part_label(vid, start, end, files, t)}'
            f'{video_player(url, key, resume, speed, t, start, end, tracks, media, files, "video.mp4")}'
            f'<p class="small muted">{e(t("Playing the copy on this computer."))} '
            f'<a href="{e(watch)}" target="_blank" rel="noopener">{e(t("Watch on YouTube instead"))}</a></p>{cap}</figure>')


def _offline_playlist(course_id: str, files: CourseFiles, items: list, watch: str, cap: str, t: Tr, save: str = "") -> str:
    """A playlist lesson with its videos on this computer: one player per video, the first one open."""
    e = html.escape
    parts = []
    for i, it in enumerate(items):
        key = f"{course_id}|yt:{it['id']}:0-"
        body = video_player(it["url"], key, files.resume(key), files.speed, t)
        parts.append(f'<details class="code-file"{" open" if i == 0 else ""}><summary dir="auto">{i + 1}. {e(it["title"])}</summary>{body}</details>')
    return (f'<figure class="media video offline-yt"><div class="code-folder">{"".join(parts)}</div>'
            f'<p class="small muted">{e(t("Playing the copies on this computer."))} '
            f'<a href="{e(watch)}" target="_blank" rel="noopener">{e(t("Watch on YouTube instead"))}</a></p>{save}{cap}</figure>')


def player(course_id: str, ref: str, label: str, exists: Callable[[str], bool], t: Tr) -> str:
    """HTML for one media item. ref is a web link or a path inside the course."""
    ref = html.unescape(ref).strip()
    if not is_url(ref):
        ref = unquote(ref)  # Markdown writes spaces in paths as %20
    pages = None
    if not is_url(ref):
        ref, pages = page_range(ref)
    kind = media_kind(ref)
    e = html.escape
    cap = f"<figcaption>{e(label)}</figcaption>" if label else ""

    if kind == "youtube":
        return youtube_player(course_id, ref, cap, exists, t)
    if kind == "vimeo":
        vid = embed_id(ref)
        src = f"https://player.vimeo.com/video/{vid}?autoplay=1"
        return (f'<figure class="media embed"><div class="embed-box" data-embed="{e(src)}">'
                f'<button type="button" class="btn primary play">▶ {e(t("Play video"))}</button>'
                f'<span class="small">{e(t("From {site}. It loads from the internet when you press play.").format(site="Vimeo"))}</span>'
                f'<a class="small" href="{e(ref)}" target="_blank" rel="noopener">{e(t("Open on {site}").format(site="Vimeo"))}</a>'
                f'</div>{cap}</figure>')

    if is_url(ref):
        if kind in ("video", "audio"):
            tag = "video" if kind == "video" else "audio"
            return (f'<figure class="media embed"><div class="embed-box" data-embed-{tag}="{e(ref)}">'
                    f'<button type="button" class="btn primary play">▶ {e(t("Play"))}</button>'
                    f'<span class="small">{e(t("It loads from the internet when you press play."))}</span></div>{cap}</figure>')
        if kind == "image":
            return f'<figure class="media"><a href="{e(ref)}" target="_blank" rel="noopener">{e(label or ref)}</a></figure>'
        return (f'<p class="link-card"><a href="{e(ref)}" target="_blank" rel="noopener">'
                f'<b>{e(label or ref)}</b><span class="small muted" dir="ltr">{e(ref)}</span></a></p>')

    rel = local_ref(ref)
    if not rel or not kind:
        return f'<p class="note warn">{e(t("This media can not be shown: {name}").format(name=ref))}</p>'
    files = exists if isinstance(exists, CourseFiles) else None
    if not exists(rel) and files and files.book and rel == files.book:
        where = t("Pages {a} to {b}").format(a=pages[0], b=pages[1]) if pages else ""
        return (f'<div class="note warn media-missing"><b>{e(t("This lesson reads your own copy of the course book."))}</b> '
                f'{e(where)}<br><a class="btn" href="{e(files.book_link)}">{e(t("Show inPace where your book is"))}</a></div>')
    if not exists(rel):
        return (f'<div class="note warn media-missing"><b>{e(t("inPace can not find this file:"))}</b> '
                f'<code dir="ltr">{e(rel)}</code><br><span class="small">'
                f'{e(t("Did the course files move? Choose the folder where they are now."))}</span>'
                f'<form method="post" action="/courses/{e(course_id)}/media-folder" class="row pick-row">'
                f'<input name="folder" id="mf-{abs(hash(rel))}" dir="ltr" required placeholder="{e(t("Full path of the course folder"))}">'
                f'<button type="button" class="btn" data-pick-folder="#mf-{abs(hash(rel))}">{e(t("Choose folder"))}</button>'
                f'<button class="btn primary">{e(t("Use this folder"))}</button></form></div>')
    url = media_url(course_id, rel)
    files = exists if isinstance(exists, CourseFiles) else None
    key = f"{course_id}|{rel}"
    if kind == "video":
        body = video_player(url, key, files.resume(key) if files else 0.0, files.speed if files else 1.0, t,
                            tracks=files.subs(rel) if files else [], media=rel, files=files, name=rel.rsplit("/", 1)[-1])
    elif kind == "audio":
        resume = files.resume(key) if files else 0.0
        body = f'<audio controls preload="metadata" src="{url}" data-remember data-key="{e(key)}" data-resume="{resume:.1f}"></audio>'
    elif kind in ("code", "folder"):
        path = files.find(rel) if files else None
        name = rel.rstrip("/").rsplit("/", 1)[-1]
        if not path:
            body = f'<p><a href="{url}?view=1" target="_blank" rel="noopener">{e(name)}</a></p>'
        elif kind == "folder":
            body = folder_view(course_id, rel, path, t, files)
        else:
            body = (f'<div class="code-file-head" dir="ltr"><span>{e(name)}</span>'
                    f'{open_buttons(files, rel, url, t)}</div>' + code_block(path, name, url, t))
    elif kind == "office":  # Word, PowerPoint, Excel: a light preview, and the file to open in its own app
        path = files.find(rel) if files else None
        name = rel.rsplit("/", 1)[-1]
        try:
            from .office import OfficeProblem, preview
        except Exception:  # no XML parser in this Python: offer the file only
            OfficeProblem, preview = ValueError, None
        try:
            inner = preview(path) if path and preview else ""
        except OfficeProblem as ex:
            inner = f'<p class="note warn">{e(t(str(ex)))}</p>'
        except Exception:
            msg = t("This file couldn't be read. It may be damaged.")
            inner = f'<p class="note warn">{e(msg)}</p>'
        ext = name.rsplit(".", 1)[-1].lower()
        body = (f'<div class="office-head" dir="ltr"><span>{e(name)}</span>'
                f'<a href="{url}" download="{e(name)}">{e(t("Download to open it in its own app"))}</a></div>'
                f'<div class="office office-{e(ext)}">{inner}</div>')
    elif kind == "image":
        body = f'<img src="{url}" alt="{e(label)}" loading="lazy">'
    elif kind == "html":
        body = (f'<div class="frame-wrap"><iframe sandbox="allow-scripts" src="{url}" loading="lazy" title="{e(label or rel)}"></iframe></div>'
                f'<button type="button" class="btn small-btn" data-fullscreen>{e(t("Full screen"))}</button>')
    else:  # pdf: inPace's own reader (works in every app window, remembers your page)
        name = rel.rstrip("/").rsplit("/", 1)[-1]
        if pages:  # only part of the book; each part remembers its own page
            key += f"#{pages[0]}-{pages[1]}"
            where = t("Page {a}").format(a=pages[0]) if pages[0] == pages[1] else t("Pages {a} to {b}").format(a=pages[0], b=pages[1])
            cap = cap or f'<figcaption>{e(where)}</figcaption>'
        q = f"src={quote(url, safe='')}&key={quote(key, safe='')}&name={quote(name, safe='')}"
        if pages:
            q += f"&from={pages[0]}&to={pages[1]}"
        body = (f'<div class="frame-wrap tall"><iframe src="/pdf?{q}" loading="lazy" title="{e(label or name)}" allowfullscreen></iframe></div>'
                f'<a class="small" href="/pdf?{q}&full=1">{e(t("Open the PDF on its own page"))}</a>')
    return f'<figure class="media {kind}">{body}{cap}</figure>'


def lesson_html(course_id: str, lesson: dict, rendered: str, exists: Callable[[str], bool], t: Tr) -> str:
    """The lesson's main media (if any) on top, then its text with media turned into players."""

    def img(m: re.Match) -> str:
        src, alt = m.group(1), m.group(2)
        kind = media_kind(html.unescape(src))
        if not kind or (kind == "image" and is_url(html.unescape(src))):
            return m.group(0)  # an ordinary picture from the web stays a picture link
        return player(course_id, src, html.unescape(alt), exists, t)

    def lone(m: re.Match) -> str:
        href = html.unescape(m.group(1))
        label = html.unescape(m.group(2)) if m.lastindex and m.lastindex >= 2 else ""
        if media_kind(href) in ("youtube", "vimeo"):
            return player(course_id, href, "" if label == href else label, exists, t)
        return m.group(0)

    def link(m: re.Match) -> str:
        href = html.unescape(m.group(1))
        if is_url(href):
            return f'<a href="{html.escape(href)}" target="_blank" rel="noopener">'
        rel = local_ref(unquote(href.split("#")[0]))
        if rel and media_kind(rel):
            return f'<a href="{media_url(course_id, rel)}" target="_blank" rel="noopener">'
        return m.group(0)

    out = _IMG.sub(img, rendered)
    out = _LONE_LINK.sub(lone, out)
    out = _LONE_URL.sub(lone, out)
    out = _LINK.sub(link, out)
    if lesson.get("media"):
        out = player(course_id, lesson["media"], "", exists, t) + out
    return out


def media_refs(lesson: dict) -> set[str]:
    """Paths of the course's own files that a lesson uses."""
    refs = set()
    if lesson.get("media") and not is_url(lesson["media"]):
        refs.add(page_range(lesson["media"])[0])  # "book.pdf#pages=3-9" uses the file book.pdf
    for m in re.finditer(r"!\[[^\]]*\]\(\s*(?:<([^>]+)>|([^)\s]+))", lesson.get("content", "")):
        rel = local_ref(m.group(1) or m.group(2))
        if rel and media_kind(rel):
            refs.add(rel)
    return refs
