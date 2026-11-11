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

from .course import embed_id, is_url, local_ref, media_kind

Tr = Callable[[str], str]

_IMG = re.compile(r'<img src="([^"]*)" alt="([^"]*)"\s*/?>')
_LONE_LINK = re.compile(r'<p>\s*<a href="([^"]+)">([^<]*)</a>\s*</p>')
_LONE_URL = re.compile(r'<p>\s*(https?://[^\s<]+)\s*</p>')
_LINK = re.compile(r'<a href="([^"]+)">')


def media_url(course_id: str, rel: str) -> str:
    return f"/m/{quote(course_id)}/{quote(rel)}"


def player(course_id: str, ref: str, label: str, exists: Callable[[str], bool], t: Tr) -> str:
    """HTML for one media item. ref is a web link or a path inside the course."""
    ref = html.unescape(ref).strip()
    if not is_url(ref):
        ref = unquote(ref)  # Markdown writes spaces in paths as %20
    kind = media_kind(ref)
    e = html.escape
    cap = f"<figcaption>{e(label)}</figcaption>" if label else ""

    if kind in ("youtube", "vimeo"):
        vid = embed_id(ref)
        src = (f"https://www.youtube-nocookie.com/embed/{vid}?autoplay=1&rel=0" if kind == "youtube"
               else f"https://player.vimeo.com/video/{vid}?autoplay=1")
        site = "YouTube" if kind == "youtube" else "Vimeo"
        return (f'<figure class="media embed"><div class="embed-box" data-embed="{e(src)}">'
                f'<button type="button" class="btn primary play">▶ {e(t("Play video"))}</button>'
                f'<span class="small">{e(t("From {site}. It loads from the internet when you press play.").format(site=site))}</span>'
                f'<a class="small" href="{e(ref)}" target="_blank" rel="noopener">{e(t("Open on {site}").format(site=site))}</a>'
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
    if not exists(rel):
        return (f'<div class="note warn media-missing"><b>{e(t("inPace can not find this file:"))}</b> '
                f'<code dir="ltr">{e(rel)}</code><br><span class="small">'
                f'{e(t("Did the course files move? Choose the folder where they are now."))}</span>'
                f'<form method="post" action="/courses/{e(course_id)}/media-folder" class="row pick-row">'
                f'<input name="folder" id="mf-{abs(hash(rel))}" dir="ltr" required placeholder="{e(t("Full path of the course folder"))}">'
                f'<button type="button" class="btn" data-pick-folder="#mf-{abs(hash(rel))}">{e(t("Choose folder"))}</button>'
                f'<button class="btn primary">{e(t("Use this folder"))}</button></form></div>')
    url = media_url(course_id, rel)
    if kind == "video":
        body = f'<video controls preload="metadata" src="{url}"></video>'
    elif kind == "audio":
        body = f'<audio controls preload="metadata" src="{url}"></audio>'
    elif kind == "image":
        body = f'<img src="{url}" alt="{e(label)}" loading="lazy">'
    elif kind == "html":
        body = (f'<div class="frame-wrap"><iframe sandbox="allow-scripts" src="{url}" loading="lazy" title="{e(label or rel)}"></iframe></div>'
                f'<button type="button" class="btn small-btn" data-fullscreen>{e(t("Full screen"))}</button>')
    else:  # pdf
        body = (f'<div class="frame-wrap tall"><iframe src="{url}" loading="lazy" title="{e(label or rel)}"></iframe></div>'
                f'<a class="small" href="{url}" target="_blank" rel="noopener">{e(t("Open the PDF"))}</a>')
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
        refs.add(lesson["media"])
    for m in re.finditer(r"!\[[^\]]*\]\(\s*(?:<([^>]+)>|([^)\s]+))", lesson.get("content", "")):
        rel = local_ref(m.group(1) or m.group(2))
        if rel and media_kind(rel):
            refs.add(rel)
    return refs
