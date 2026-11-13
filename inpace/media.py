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
                 yt_list: Callable[[str], list] = lambda plist: [], book: str = "", book_link: str = ""):
        self.find = find
        self.resume = resume
        self.speed = speed
        self.yt_local = yt_local  # video id -> address of its copy on this computer (downloaded or your own file)
        self.yt_list = yt_list    # playlist id -> [{"id", "title", "url"}] of the videos that are on this computer
        self.book = book            # the course's book, which each learner gets themselves (not shared with it)
        self.book_link = book_link  # where to show inPace your copy

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


def folder_view(course_id: str, rel: str, folder, t: Tr) -> str:
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
            inner = code_block(p, p.name, url, t)
        else:
            inner = f'<p><a href="{url}" target="_blank" rel="noopener">{html.escape(t("Open it"))}</a></p>'
        items.append(f'<details class="code-file"{" open" if i == 0 else ""}><summary dir="ltr">{html.escape(sub)}</summary>{inner}</details>')
    return f'<div class="code-folder">{"".join(items)}</div>'


def _clock(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def video_player(url: str, key: str, resume: float, speed: float, t: Tr, start: int = 0, end: int | None = None) -> str:
    """Our own video player: big play button, speed, +-10 s, full screen, keyboard keys, and it remembers
    the second you stopped at. Without JavaScript it's a normal video with the browser's controls.
    start and end make it play only one piece of the file (a lesson cut from a long video)."""
    e = html.escape
    labels = {"play": t("Play"), "pause": t("Pause"), "back": t("Back 10 seconds"), "fwd": t("Forward 10 seconds"),
              "mute": t("Mute"), "unmute": t("Sound on"), "speed": t("Speed"), "full": t("Full screen"),
              "pip": t("Picture in picture"), "restart": t("Start over"),
              "ended": t("Finished! Mark the lesson as done below.")}
    data = " ".join(f'data-l-{k}="{e(v)}"' for k, v in labels.items())
    if resume and (resume < start or (end and resume >= end - 5)):
        resume = 0.0
    hint = ""
    if resume > start + 5:
        hint = (f'<p class="resume-hint small muted">{e(t("You stopped at {time}. It continues from there.").format(time=_clock(resume)))} '
                f'<button type="button" class="link" data-restart>{e(t("Start over"))}</button></p>')
    frag = f"#t={start}" + (f",{end}" if end else "") if (start or end) else ""
    return (f'<div class="player" tabindex="0" data-player data-key="{e(key)}" data-resume="{resume:.1f}" data-speed="{speed:g}" '
            f'data-start="{start}" data-end="{end or 0}" {data}>'
            f'<video controls preload="metadata" playsinline src="{url}{frag}"></video></div>{hint}')


def youtube_player(course_id: str, ref: str, cap: str, exists: Callable[[str], bool], t: Tr) -> str:
    """A YouTube video, a piece of one (t=... and end=... in the link), or a playlist.
    It loads only when you press play, and it continues from where you stopped (saved on this computer)."""
    e = html.escape
    vid, plist = embed_id(ref), youtube_playlist(ref)
    start, end = youtube_segment(ref)
    files = exists if isinstance(exists, CourseFiles) else None
    if vid:
        src = f"https://www.youtube-nocookie.com/embed/{vid}?autoplay=1&rel=0&enablejsapi=1"
        watch = f"https://www.youtube.com/watch?v={vid}" + (f"&t={start}s" if start else "")
        key = f"{course_id}|yt:{vid}:{start}-{end or ''}"
    else:
        src = f"https://www.youtube-nocookie.com/embed/videoseries?list={plist}&autoplay=1&rel=0&enablejsapi=1"
        watch = f"https://www.youtube.com/playlist?list={plist}"
        key = f"{course_id}|ytlist:{plist}"
    resume = files.resume(key) if files else 0.0
    if files and vid and files.yt_local(vid):
        return _offline_youtube(files.yt_local(vid), key, resume, files.speed, start, end, watch, cap, t)
    if files and plist and files.yt_list(plist):
        return _offline_playlist(course_id, files, files.yt_list(plist), watch, cap, t)
    if resume and (resume < start or (end and resume >= end - 5)):
        resume = 0.0
    piece = ""
    if vid and (start or end):
        piece = (f'<span class="small yt-piece">{e(t("This lesson is the part from {a} to {b}.").format(a=_clock(start), b=_clock(end)))}</span>'
                 if end else f'<span class="small yt-piece">{e(t("This lesson starts at {a}.").format(a=_clock(start)))}</span>')
    hint = ""
    if resume > start + 5:
        hint = (f'<span class="small resume-hint">{e(t("You stopped at {time}. It continues from there.").format(time=_clock(resume)))} '
                f'<button type="button" class="link" data-yt-restart>{e(t("Start over"))}</button></span>')
    return (f'<figure class="media embed"><div class="embed-box" data-embed="{e(src)}" data-yt-key="{e(key)}" '
            f'data-start="{start}" data-end="{end or 0}" data-resume="{resume:.1f}">'
            f'<button type="button" class="btn primary play">▶ {e(t("Play video"))}</button>{piece}{hint}'
            f'<span class="small">{e(t("From {site}. It loads from the internet when you press play.").format(site="YouTube"))}</span>'
            f'<a class="small" href="{e(watch)}" target="_blank" rel="noopener">{e(t("Open on {site}").format(site="YouTube"))}</a>'
            f'</div>{cap}</figure>')


def _offline_youtube(url: str, key: str, resume: float, speed: float, start: int, end: int | None, watch: str,
                     cap: str, t: Tr) -> str:
    """A YouTube lesson playing the copy on this computer: no internet needed, same piece, same saved place."""
    e = html.escape
    piece = ""
    if start or end:
        piece = (t("This lesson is the part from {a} to {b}.").format(a=_clock(start), b=_clock(end)) if end
                 else t("This lesson starts at {a}.").format(a=_clock(start)))
        piece = f'{e(piece)} '
    return (f'<figure class="media video offline-yt">{video_player(url, key, resume, speed, t, start, end)}'
            f'<p class="small muted">{piece}{e(t("Playing the copy on this computer."))} '
            f'<a href="{e(watch)}" target="_blank" rel="noopener">{e(t("Watch on YouTube instead"))}</a></p>{cap}</figure>')


def _offline_playlist(course_id: str, files: CourseFiles, items: list, watch: str, cap: str, t: Tr) -> str:
    """A playlist lesson with its videos on this computer: one player per video, the first one open."""
    e = html.escape
    parts = []
    for i, it in enumerate(items):
        key = f"{course_id}|yt:{it['id']}:0-"
        body = video_player(it["url"], key, files.resume(key), files.speed, t)
        parts.append(f'<details class="code-file"{" open" if i == 0 else ""}><summary dir="auto">{i + 1}. {e(it["title"])}</summary>{body}</details>')
    return (f'<figure class="media video offline-yt"><div class="code-folder">{"".join(parts)}</div>'
            f'<p class="small muted">{e(t("Playing the copies on this computer."))} '
            f'<a href="{e(watch)}" target="_blank" rel="noopener">{e(t("Watch on YouTube instead"))}</a></p>{cap}</figure>')


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
        body = video_player(url, key, files.resume(key) if files else 0.0, files.speed if files else 1.0, t)
    elif kind == "audio":
        resume = files.resume(key) if files else 0.0
        body = f'<audio controls preload="metadata" src="{url}" data-remember data-key="{e(key)}" data-resume="{resume:.1f}"></audio>'
    elif kind in ("code", "folder"):
        path = files.find(rel) if files else None
        name = rel.rstrip("/").rsplit("/", 1)[-1]
        if not path:
            body = f'<p><a href="{url}?view=1" target="_blank" rel="noopener">{e(name)}</a></p>'
        elif kind == "folder":
            body = folder_view(course_id, rel, path, t)
        else:
            body = (f'<div class="code-file-head" dir="ltr"><span>{e(name)}</span>'
                    f'<a href="{url}?view=1" target="_blank" rel="noopener">{e(t("Open it"))}</a></div>' + code_block(path, name, url, t))
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
