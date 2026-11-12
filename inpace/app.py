"""The local web app. Runs only on this computer (127.0.0.1)."""
from __future__ import annotations

import json
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from markdown_it import MarkdownIt
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.background import BackgroundTask
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import ai, checks, editor, encourage, exchange, integrations, library, pace, races, record, updater
from .mascot import mascot
from .canon import now_utc, short
from .course import (HTML_EXT, MAX_MEDIA_PACK_BYTES, Course, CourseError, course_from_folder, course_to_pack,
                     files_from_folder, files_from_zip, load_course, media_in_zip, strip_fences, write_pack_with_media)
from . import media as media_mod
from .exam import NoAnswers, build_exam, grade, new_seed
from .vault import COLORS, Vault, display_name

HERE = Path(__file__).parent
mimetypes.add_type("text/javascript", ".mjs")  # the PDF reader's scripts
SAMPLES = HERE / "sample_courses"
MEANINGFUL = {"lesson_done", "evidence_added", "writeup_saved", "quiz_taken", "exam_taken", "reflection_saved",
              "review_done", "commitment_set", "pause_started", "pause_ended"}

def _highlight(code: str, lang: str, attrs: str) -> str:
    """Colour code blocks on this computer (no internet needed)."""
    from html import escape
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound
    if not lang:
        return escape(code)
    try:
        lexer = get_lexer_by_name(lang)
    except ClassNotFound:
        return escape(code)
    return highlight(code, lexer, HtmlFormatter(nowrap=True))


md = MarkdownIt("commonmark", {"html": False, "linkify": False, "highlight": _highlight}).enable("table")
env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                  extensions=["jinja2.ext.i18n"])
LOCALES = {"ar": json.loads((HERE / "locales" / "ar.json").read_text(encoding="utf-8"))}
CURRENT = {"lang": "en"}


def _patterns(table: dict) -> list:
    """Keys with {name} slots, like "Added {name}.", also translate messages built at run time."""
    out = []
    for key, val in table.items():
        if "{" in key and "}" in key:
            rx = re.escape(key)
            seen: set = set()

            def slot(m, seen=seen):
                name = m.group(1)
                if name in seen:
                    return f"(?P={name})"
                seen.add(name)
                return f"(?P<{name}>.+?)"
            rx = re.sub(r"\\\{(\w+)\\\}", slot, rx)
            out.append((len(re.sub(r"\{\w+\}", "", key)), re.compile(rx + r"\Z", re.S), val))
    out.sort(key=lambda x: -x[0])  # most specific first
    return [(rx, val) for _, rx, val in out]


PATTERNS = {lang: _patterns(t) for lang, t in LOCALES.items()}


def gettext(text: str) -> str:
    table = LOCALES.get(CURRENT["lang"])
    if not table or not text:
        return text
    hit = table.get(text)
    if hit is not None:
        return hit
    for rx, val in PATTERNS[CURRENT["lang"]]:
        m = rx.match(text)
        if m:
            parts = {}
            for k, v in m.groupdict().items():
                core = v.strip()
                tr = gettext(core) if core != text and any(c.isalpha() for c in core) else core
                parts[k] = v[: len(v) - len(v.lstrip())] + tr + v[len(v.rstrip()):]
            try:
                return val.format(**parts)
            except (KeyError, IndexError):
                return text
    return text


env.install_gettext_callables(gettext, lambda s, p, n: gettext(s if n == 1 else p), newstyle=False)
env.globals["_"] = gettext
env.globals["mascot"] = mascot


def say(msg: str, values: list | tuple = ()) -> str:
    text = gettext(msg)
    try:
        return text % tuple(values) if values else text.replace("%%", "%")
    except (TypeError, ValueError):
        return msg % tuple(values) if values else msg


env.globals["say"] = say
env.filters["short"] = short
# Color profiles for the whole app: (name, main colour, second colour) for the Settings preview.
ACCENTS = {
    "": ("Sunny", "#FFD43B", "#E6007E"),
    "ocean": ("Ocean", "#4DB8FF", "#FF6B35"),
    "mint": ("Mint", "#46D99A", "#7C3AED"),
    "rose": ("Rose", "#FF8FB1", "#2563EB"),
    "grape": ("Grape", "#B79CFF", "#F59E0B"),
    "nile": ("Nile", "#F4A259", "#0E7C86"),
    "mono": ("Ink", "#D4D4D4", "#111111"),
}

MONTHS = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
          "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر",
                 "نوفمبر", "ديسمبر"]}


def nice_date(s: str | None) -> str:
    """2026-11-11 -> "Nov 11, 2026" or "11 نوفمبر 2026"."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s or "")
    if not m:
        return (s or "")[:10]
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if CURRENT["lang"] == "ar":
        return f"{d} {MONTHS['ar'][mo - 1]} {y}"
    return f"{MONTHS['en'][mo - 1]} {d}, {y}"


def tr_lines(text: str | None) -> str:
    """A message can be several sentences joined by new lines; translate each one."""
    return " ".join(gettext(x) for x in (text or "").split("\n") if x)


def t(text: str, **values) -> str:
    """Translate a sentence with {name} slots, then fill them in."""
    out = gettext(text)
    try:
        return out.format(**values)
    except (KeyError, IndexError, ValueError):
        return text.format(**values)


env.filters["date"] = nice_date
env.globals["T"] = t
env.globals["ACCENTS"] = ACCENTS
env.globals["display_name"] = display_name


def avatar(p: dict, size: int = 36) -> Markup:
    color = p.get("color") or "#3A506B"
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        color = "#3A506B"
    letter = (display_name(p) or "?")[:1].upper()
    return Markup('<span class="avatar" style="--c: {}; --s: {}px" aria-hidden="true">{}</span>').format(
        color, int(size), letter)


env.globals["avatar"] = avatar

_ICONS = {
    "back": '<path d="M15 5l-7 7 7 7"/>',
    "forward": '<path d="M9 5l7 7-7 7"/>',
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
    "book": '<path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H20v15H5.5A1.5 1.5 0 0 0 4 19.5z"/><path d="M4 19.5A1.5 1.5 0 0 0 5.5 21H20"/>',
    "flag": '<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/>',
    "open": '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M4 17v3h16v-3"/>',
    "upload": '<path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 17v3h16v-3"/>',
    "pen": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    "quiz": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6"/><path d="M12 17h.01"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "shield": '<path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    "send": '<path d="M21 3 10 14"/><path d="M21 3 14 21l-4-7-7-4z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "moon": '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/>',
    "file": '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5"/>',
    "arrow": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    "up": '<path d="m6 15 6-6 6 6"/>',
    "down": '<path d="m6 9 6 6 6-6"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    "play": '<path d="M7 4.5v15l13-7.5z"/>',
    "code": '<path d="m8 7-5 5 5 5"/><path d="m16 7 5 5-5 5"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
}


def icon(name: str, size: int = 20) -> Markup:
    return Markup(
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f'{_ICONS.get(name, "")}</svg>')


env.globals["icon"] = icon


def cover(c, big: bool = False, sample: bool = False) -> Markup:
    """The course's picture, or a coloured tile with its first letter when it has none."""
    cls = "cover big" if big else "cover"
    img = (c.extra or {}).get("image")
    if img:
        base = "/sample-file" if sample else "/m"
        return Markup('<img class="{}" src="{}/{}/{}" alt="" loading="lazy">').format(cls, base, quote(c.id), quote(img))
    hue = sum(ord(ch) for ch in c.id) % 360
    letter = (c.title.strip()[:1] or "?").upper()
    return Markup('<span class="{} blank" style="--hue:{}" aria-hidden="true">{}</span>').format(cls, hue, letter)


env.globals["cover"] = cover


def filesize(n) -> str:
    n = float(n or 0)
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


env.filters["filesize"] = filesize
from .course import media_kind as _media_kind
env.globals["media_kind"] = _media_kind
env.globals["on_phone"] = lambda: os.environ.get("INPACE_MOBILE") == "android"
env.globals["TASK_LABEL"] = {"practical": "Your work", "explain": "Explain it", "quiz": "Quiz"}
env.globals["TASK_ICON"] = {"practical": "upload", "explain": "pen", "quiz": "quiz"}


def _drop_title(content: str, title: str) -> str:
    """The page already shows the lesson title, so skip a first heading that repeats it."""
    lines = content.lstrip().splitlines()
    if lines and lines[0].startswith("#") and lines[0].lstrip("#").strip().lower() == title.strip().lower():
        return "\n".join(lines[1:])
    return content


def create_app(vault: Vault) -> Starlette:
    V = vault

    # ---- helpers -------------------------------------------------------------
    def page(name: str, request: Request, **ctx) -> HTMLResponse:
        CURRENT["lang"] = (V._meta("lang", "en") or "en") if V.is_set_up else "en"
        base = {"request": request, "msg": tr_lines(request.query_params.get("ok")) or None,
                "err": tr_lines(request.query_params.get("err")) or None, "lang": CURRENT["lang"],
                "theme": (V._meta("theme", "") or "") if V.is_set_up else "",
                "accent": (V._meta("accent", "") or "") if V.is_set_up else "",
                "update": _update_info() if V.is_set_up else None,
                "yay": encourage.CELEBRATE.get(request.query_params.get("yay", ""))}
        if V.is_set_up:
            base["me"] = V.me
            base["checking"] = [
                {**p, "waiting": V.waiting_count(p["id"])} for p in V.people() if p["i_check"]
            ]
            base["active_path"] = request.url.path
            base["resume"] = _last_lesson()
        base.update(ctx)
        return HTMLResponse(env.get_template(name).render(**base))

    def _last_lesson() -> dict | None:
        """The lesson you opened last, for the "Continue" button in the side bar."""
        row = V.db.execute(
            "SELECT e.journey, e.data FROM events e JOIN journeys j ON j.id = e.journey "
            "WHERE e.type = 'lesson_opened' AND j.archived = 0 ORDER BY e.seq DESC LIMIT 1").fetchone()
        if not row:
            return None
        j = V.journey(row["journey"])
        c = V.get_course(j["course_id"]) if j else None
        found = c.find_lesson(json.loads(row["data"]).get("lesson", "")) if c else None
        if not found:
            return None
        return {"url": f"/learn/{j['id']}/lesson/{found[1]['id']}", "lesson": found[1]["title"], "course": c.title}

    async def nav_index(request: Request):
        """Everything you can jump to from the search box (Ctrl+K)."""
        items = [{"t": say(n), "u": u, "k": say("Page")} for n, u in (
            ("Home", "/"), ("My courses", "/courses"), ("Milestones", "/milestones"), ("Races", "/races"),
            ("Make a course with AI", "/ai"), ("Make one by hand", "/edit/new"), ("People", "/people"),
            ("Open a file", "/open"), ("Settings", "/settings"), ("Show the tour again", "/?tour=1"))]
        for c in V.courses():
            jid = V.journey_for_course(c.id)
            items.append({"t": c.title, "u": f"/learn/{jid}" if jid else "/courses", "k": say("Course")})
            items.append({"t": t("Edit {name}", name=c.title), "u": f"/edit/{c.id}", "k": say("Edit")})
            if jid:
                for m in c.modules:
                    for les in m["lessons"]:
                        items.append({"t": les["title"], "u": f"/learn/{jid}/lesson/{les['id']}",
                                      "k": f"{c.title} › {m['title']}"})
                    if m["requires"]:
                        items.append({"t": t("{name} tasks", name=m["title"]), "u": f"/learn/{jid}/module/{m['id']}",
                                      "k": c.title})
        for p in V.people():
            items.append({"t": display_name(p), "u": "/people", "k": say("Person")})
        return JSONResponse(items[:3000])

    async def set_accent(request: Request):
        form = await request.form()
        accent = str(form.get("accent", ""))
        V._set_meta("accent", accent if accent in ACCENTS else "")
        return go("/settings#colors", ok="Colors saved.")

    def go(url: str, ok: str | None = None, err: str | None = None, yay: str | None = None) -> RedirectResponse:
        if yay:
            url = (url.split("#")[0] + ("&" if "?" in url else "?") + "yay=" + yay +
                   ("#" + url.split("#")[1] if "#" in url else ""))
        if ok:
            url += ("&" if "?" in url else "?") + "ok=" + quote(ok)
        if err:
            url += ("&" if "?" in url else "?") + "err=" + quote(err)
        return RedirectResponse(url, status_code=303)

    def download(data: bytes, filename: str, mime: str = "application/octet-stream") -> Response:
        safe = re.sub(r"[^\w .,()-]+", "", filename, flags=re.UNICODE).strip() or "file"
        return Response(data, media_type=mime, headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(safe)}"})

    def journey_or_404(jid: str):
        j = V.journey(jid)
        if not j or not V.get_course(j["course_id"]):
            return None
        return j

    def has_new(jid: str) -> bool:
        return any(e["type"] in MEANINGFUL for e in V.events(jid, V.last_event_in_milestones(jid)))

    def journey_card(j: dict) -> dict:
        prog = V.progress(j["id"])
        ms = V.milestones(j["id"])
        last_ok = next((a for m in reversed(ms) for a in m["approvals"] if a["decision"] == "approved"), None)
        waiting = [m for m in ms if not any(a["decision"] == "approved" for a in m["approvals"])]
        exams = checks.my_exams(V, j["id"])
        evs = V.events(j["id"])
        card: dict
        wk = pace.weeks(evs, [m["body"]["created_at"] for m in ms])
        packed_at = V._meta(f"pack:{j['id']}", "") or ""
        card = {"journey": j, "progress": prog, "milestones": ms, "last_ok": last_ok, "waiting": waiting,
                "has_new": has_new(j["id"]), "chain_problems": V.check_my_chain(j["id"]),
                "exams_waiting": [x for x in exams if not x["taken"]],
                "requests": [r for r in checks.requests_for(V, j["id"]) if r["at"] > packed_at],
                "pace": wk, "paused": pace.is_paused(evs),
                "forecast": pace.forecast(j["started_at"], prog["percent"]),
                "due": len(pace.due_cards(V, j["course_id"])) if prog["course"].has_answers else 0}
        card["tempo"] = encourage.greeting(card)
        return card

    # ---- setup ---------------------------------------------------------------
    async def setup(request: Request):
        if request.method == "POST":
            form = await request.form()
            name = str(form.get("name", "")).strip()
            if not name:
                return page("setup.html", request, colors=COLORS, error="Please type your name.")
            V.setup(name, str(form.get("color", COLORS[0])))
            return go("/", ok=f"Welcome, {name}! Pick a course to start.")
        return page("setup.html", request, colors=COLORS)

    async def home(request: Request):
        if not V.is_set_up:
            return go("/setup")
        pending = V._meta("pending_link", "") or ""
        if pending:
            return go("/link?d=" + pending)
        cards = [journey_card(j) for j in V.journeys()]
        show_tour = request.query_params.get("tour") == "1" or not V._meta("tour_done", "")
        return page("home.html", request, cards=cards, checkers=V.my_checkers(), courses=V.courses(),
                    tour=_tour_steps() if show_tour else None)

    def _tour_steps() -> list:
        """Tempo's welcome tour. Each step points at something on the screen (or nothing, for the middle of the screen)."""
        steps = [
            (None, "wave", "Hi, I'm Tempo!", "I'll show you around inPace. It takes about a minute. Slow and steady, like me."),
            ('.side a[href="/courses"]', "happy", "Your courses", "Everything you're learning lives here. Add a course from a file, a folder of videos you already have, a list of YouTube links, or try a sample course."),
            ('.side a[href="/ai"]', "think", "Make a course", "Build your own course with simple forms, or let any AI chat write one from a topic, a book, a YouTube playlist, an exam, or your own notes."),
            ('.side a[href="/milestones"]', "proud", "Milestones", "When you finish part of a course, save a milestone. It's a signed snapshot of your progress that nobody can quietly change."),
            ('.side a[href="/people"]', "cheer", "Your checker", "Learning sticks when someone has your back. Add a friend, a parent or a mentor. Send them your milestone and they approve it. Swap friend codes on Telegram or WhatsApp."),
            ('.side a[href="/races"]', "cheer", "Races", "Race your friends to keep each other going. Only approved milestones count, so it stays fair."),
            (".side-bottom a", "think", "Open a file", "Anything someone sends you, like a course, a friend code or your checker's reply, opens here."),
            (".theme-toggle", "sleepy", "Light or dark", "Studying late? Switch to dark mode here."),
            ('.side a[href="/settings"]', "happy", "Settings", "Language, backups and updates live here. You can also watch this tour again from here any time."),
            (None, "proud", "You're all set!", "Start with a course and take the first step today. I'll be on your Home page, cheering you on."),
        ]
        return [{"target": tgt, "mood": mood, "title": say(title), "text": say(text)} for tgt, mood, title, text in steps]

    async def tour_done(request: Request):
        V._set_meta("tour_done", now_utc())
        return Response(status_code=204)

    async def tour_again(request: Request):
        V._set_meta("tour_done", "")
        return go("/?tour=1")

    # ---- courses ---------------------------------------------------------------
    async def courses(request: Request):
        installed = V.courses()
        have = {c.id for c in installed}
        samples = []
        for p in sorted(SAMPLES.iterdir()):
            if p.is_dir() and p.name not in have:
                try:
                    samples.append(load_course(files_from_folder(p)))
                except CourseError:
                    pass
        lang = V._meta("lang", "en") or "en"
        samples.sort(key=lambda c: c.language != lang)  # courses in your language first
        rows = []
        for c in installed:
            jid = V.journey_for_course(c.id)
            words = [c.title, c.description] + [m["title"] for m in c.modules] + \
                    [les["title"] for m in c.modules for les in m["lessons"]]
            rows.append({"course": c, "journey": jid,
                         "percent": V.progress(jid)["percent"] if jid else None,
                         "search": " ".join(w for w in words if w).lower(),
                         "has_files": any(media_mod.media_refs(les) for m in c.modules for les in m["lessons"]),
                         "media_root": V.media_root(c.id)})
        return page("courses.html", request, rows=rows, samples=samples)

    # ---- the course library ---------------------------------------------------
    async def library_page(request: Request):
        """Courses other people shared in the inPace library. Only goes online when you open this page."""
        from starlette.concurrency import run_in_threadpool
        try:
            index = await run_in_threadpool(library.load_index, V.home, request.query_params.get("refresh") == "1")
        except library.LibraryProblem as e:
            return page("library.html", request, problem=str(e), entries=[], index={})
        entries = []
        for e in index.get("courses", []):
            local = V.get_course(str(e.get("id", "")))
            state = "add" if not local else ("have" if local.hash == e.get("hash") else "update")
            words = " ".join(str(x) for x in [e.get("id"), e.get("title"), e.get("description"), e.get("author", {}).get("name"),
                                                " ".join(e.get("tags") or [])] if x).lower()
            entries.append({**e, "state": state, "search": words})
        show = str(request.query_params.get("show", ""))
        if show and not any(e.get("id") == show for e in entries):
            # A friend's link to a course we don't have in our list yet: look again.
            if request.query_params.get("refresh") != "1":
                return go("/library?refresh=1&show=" + quote(show))
            return page("library.html", request, entries=entries, index=index, problem=None, report_url=library.REPORT_URL,
                        site=library.SITE, show="", missing=True)
        return page("library.html", request, entries=entries, index=index, problem=None,
                    report_url=library.REPORT_URL, site=library.SITE, show=show)

    async def library_add(request: Request):
        from starlette.concurrency import run_in_threadpool
        cid = request.path_params["cid"]
        try:
            index = await run_in_threadpool(library.load_index, V.home)
            entry = library.find(index, cid)
            if not entry:
                return go("/library", err="That course isn't in the library anymore.")
            data = await run_in_threadpool(library.download, entry)
        except library.LibraryProblem as e:
            return go("/library", err=str(e))
        import io as _io
        return _install_pack(request, _io.BytesIO(data), f"{cid}.zip")

    async def share_course(request: Request):
        """Send a course to someone. If it's in the library, a small link that adds it from there."""
        cid = request.path_params["cid"]
        c = V.get_course(cid)
        if not c:
            return go("/courses", err="That course isn't installed.")
        entry = library.find(library.cached_index(V.home), cid)
        share = None
        if entry:
            share = exchange.share_links(say("Try this course on inPace 🐢 Tap the link to add it:"),
                                         library.share_data(entry), say("A course for you on inPace"))
        return page("share_course.html", request, c=c, entry=entry, share=share,
                    same=bool(entry and entry.get("hash") == c.hash))

    async def publish_course(request: Request):
        cid = request.path_params["cid"]
        c = V.get_course(cid)
        if not c:
            return go("/courses", err="That course isn't installed.")
        files = _course_files(c)
        size = sum(p.stat().st_size for p in files.values())
        img = c.extra.get("image")
        big = {k: p for k, p in files.items() if k != img}
        return page("publish.html", request, c=c, submit_url=library.submit_url(c),
                    too_big=size > library.MAX_COURSE_BYTES and not c.extra.get("downloads"),
                    needs_downloads=bool(big) and not c.extra.get("downloads"),
                    big_size=sum(p.stat().st_size for p in big.values()),
                    has_answers=bool(c.has_answers), repo=library.REPO)

    async def publish_file(request: Request):
        cid = request.path_params["cid"]
        c = V.get_course(cid)
        if not c:
            return go("/courses", err="That course isn't installed.")
        media = _course_files(c)
        if sum(p.stat().st_size for p in media.values()) > library.MAX_COURSE_BYTES:
            # Too big to carry: keep only the picture; learners get the rest from the download links.
            img = c.extra.get("image")
            media = {img: media[img]} if img in media else {}
        try:
            data = library.make_submission(V.identity, V.me["name"], c, media)
        except library.LibraryProblem as e:
            return go(f"/courses/{cid}/publish", err=str(e))
        return download(data, f"{c.title} - for the inPace library.zip", "application/zip")

    async def sample_file(request: Request):
        """The picture of a sample course you haven't added yet."""
        cid, rel = request.path_params["cid"], request.path_params["path"]
        root = (SAMPLES / cid / "files").resolve()
        try:
            p = (root / rel).resolve()
            p.relative_to(root)
        except (ValueError, OSError):
            return Response("Not found", status_code=404)
        if not p.is_file() or _media_kind(p.name) != "image":
            return Response("Not found", status_code=404)
        return FileResponse(p, headers={"X-Content-Type-Options": "nosniff"})

    async def add_sample(request: Request):
        cid = request.path_params["cid"]
        folder = SAMPLES / cid
        if not folder.is_dir():
            return go("/courses", err="That sample course wasn't found.")
        c = V.install_course(load_course(files_from_folder(folder)))
        files = folder / "files"  # the course picture and any other files that come with it
        if files.is_dir():
            import shutil
            dest = V.media_dir(c.id)
            for f in files.rglob("*"):
                if f.is_file():
                    target = dest / f.relative_to(files)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(f, target)
        return go("/courses", ok=f"Added “{c.title}”. Press Start when you're ready.")

    async def start_course(request: Request):
        cid = request.path_params["cid"]
        if not V.get_course(cid):
            return go("/courses", err="That course isn't installed.")
        jid = V.start_journey(cid)
        return go(f"/learn/{jid}")

    async def export_course(request: Request):
        c = V.get_course(request.path_params["cid"])
        if not c:
            return go("/courses", err="That course isn't installed.")
        with_answers = request.query_params.get("answers") == "1"
        suffix = " (with answers)" if with_answers else ""
        if request.query_params.get("files") == "1":
            files = _course_files(c)
            total = sum(p.stat().st_size for p in files.values())
            if total > MAX_MEDIA_PACK_BYTES:
                return go("/courses", err="This course's files are too big to put in one file. Share the course without files, and send the folder another way.")
            import tempfile
            fd, tmp = tempfile.mkstemp(suffix=".lpack")
            import os as _os
            _os.close(fd)
            write_pack_with_media(c, with_answers, files, Path(tmp))
            safe = re.sub(r"[^\w .,()-]+", "", f"{c.title}{suffix} (with files).lpack", flags=re.UNICODE).strip()
            return FileResponse(tmp, filename=safe, media_type="application/zip",
                                background=BackgroundTask(lambda: Path(tmp).unlink(missing_ok=True)))
        img = c.extra.get("image")
        cov = V.find_media(c.id, img) if img else None
        if cov and cov.is_file():
            # The course picture always goes along: it's small, and the course looks right for the next person.
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "c.lpack"
                write_pack_with_media(c, with_answers, {img: cov}, out)
                return download(out.read_bytes(), f"{c.title}{suffix}.lpack")
        return download(course_to_pack(c, with_answers), f"{c.title}{suffix}.lpack")

    def _course_files_view(cid: str):
        def resume(key: str) -> float:
            try:
                return float(V._meta(f"pos:{key}", "0") or 0)
            except ValueError:
                return 0.0
        try:
            speed = float(V._meta("video_speed", "1") or 1)
        except ValueError:
            speed = 1.0
        return media_mod.CourseFiles(lambda r: V.find_media(cid, r), resume, speed)

    async def pdf_reader(request: Request):
        """inPace's own PDF reader (pdf.js, bundled), so PDFs open in every app window, offline."""
        src = request.query_params.get("src", "")
        if not src.startswith(("/m/", "/evidence/", "/files/")):
            return Response("Not found", status_code=404)
        key = request.query_params.get("key", "")[:600]
        try:
            start = int(float(V._meta(f"pos:{key}", "0") or 0)) if key else 0
        except ValueError:
            start = 0
        CURRENT["lang"] = V._meta("lang", "en") or "en"
        return page("pdf_viewer.html", request, src=src, key=key, start=max(start, 1),
                    file_name=request.query_params.get("name", "PDF")[:200], standalone=request.query_params.get("full") == "1")

    async def media_position(request: Request):
        """The video player reports where you are every few seconds, so it can continue from there next time."""
        form = await request.form()
        key = str(form.get("key", ""))[:600]
        try:
            t = max(0.0, float(form.get("t") or 0))
            d = float(form.get("d") or 0)
        except ValueError:
            return Response(status_code=400)
        if form.get("speed"):
            try:
                V._set_meta("video_speed", str(min(3.0, max(0.25, float(form.get("speed"))))))
            except ValueError:
                pass
        if key and "|" in key:
            # Near the end counts as finished: next time it starts from the beginning.
            done = d > 0 and t > d - max(10.0, d * 0.03)
            V._set_meta(f"pos:{key}", "0" if done else f"{t:.1f}")
        return Response(status_code=204)

    def _course_files(c: Course) -> dict:
        """Every file of the course that's on this computer, by its path inside the course."""
        out = {}
        for m in c.modules:
            for les in m["lessons"]:
                for ref in media_mod.media_refs(les):
                    p = V.find_media(c.id, ref)
                    if p and p.is_dir():
                        for f in p.rglob("*"):
                            if f.is_file() and not any(x in media_mod.SKIP_DIRS or x.startswith(".")
                                                       for x in f.relative_to(p).parts):
                                out[(ref.rstrip("/") + "/" + f.relative_to(p).as_posix()).lstrip("/").replace(":", "")] = f
                    elif p:
                        out[ref.lstrip("/").replace(":", "")] = p
        img = c.extra.get("image")
        cov = V.find_media(c.id, img) if img else None
        if cov and cov.is_file():
            out[img] = cov
        return out

    async def media_file(request: Request):
        """A course's video, audio, page or picture, straight from where it lives on this computer."""
        p = V.find_media(request.path_params["cid"], request.path_params["path"])
        if not p or p.is_dir():
            return Response("Not found", status_code=404)
        headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"}
        if p.suffix.lower() in HTML_EXT + (".svg",):
            # Pages run sealed off: their own scripts work, but they can't reach inPace, your data, or the internet.
            headers["Content-Security-Policy"] = (
                "sandbox allow-scripts allow-popups; default-src 'self' http://127.0.0.1:* 'unsafe-inline' "
                "'unsafe-eval' data: blob:; connect-src 'none'; form-action 'none'")
        if request.query_params.get("view") == "1" and p.stat().st_size < 5_000_000:
            # "Open it" for a code file: show it as plain text instead of running or downloading it.
            return Response(p.read_bytes(), media_type="text/plain; charset=utf-8", headers=headers)
        return FileResponse(p, headers=headers)

    async def course_from_folder_route(request: Request):
        form = await request.form()
        folder = str(form.get("folder", "")).strip().strip('"')
        if not folder:
            return go("/courses", err="Choose a folder first.")
        try:
            c = course_from_folder(Path(folder).expanduser(), str(form.get("title", "")))
        except CourseError as e:
            return go("/courses", err=e.problems[0])
        base, n = c.id, 1
        while V.get_course(c.id):
            n += 1
            c.id = f"{base}-{n}"
        V.set_media_root(c.id, str(Path(folder).expanduser()))
        V.install_course(c)
        return go("/courses", ok=f"Added “{c.title}” from your folder. The files stay where they are.")

    async def set_media_folder(request: Request):
        cid = request.path_params["cid"]
        c = V.get_course(cid)
        form = await request.form()
        back = request.headers.get("referer") or "/courses"
        if not back.startswith(("http://127.0.0.1", "http://localhost", "/")):
            back = "/courses"
        if not c:
            return go("/courses", err="That course isn't installed.")
        folder = str(form.get("folder", "")).strip().strip('"')
        if not folder or not Path(folder).expanduser().is_dir():
            return RedirectResponse(_with_msg(back, err="That folder wasn't found. Copy its full path and paste it here."), 303)
        V.set_media_root(cid, folder)
        left = V.missing_media(c)
        if left:
            return RedirectResponse(_with_msg(back, err=f"Found the folder, but {len(left)} file(s) are still missing."), 303)
        return RedirectResponse(_with_msg(back, ok="Found all the course files."), 303)

    def _with_msg(url: str, ok: str = "", err: str = "") -> str:
        from urllib.parse import urlsplit
        u = urlsplit(url)
        path = u.path or "/"
        if u.query:
            keep = "&".join(x for x in u.query.split("&") if not x.startswith(("ok=", "err=", "yay=")))
            path += ("?" + keep) if keep else ""
        return go(path, ok=ok or None, err=err or None).headers["location"]

    async def pick_folder_route(request: Request):
        title = say("Choose the course folder")
        import anyio
        folder = await anyio.to_thread.run_sync(lambda: integrations.pick_folder(title))
        return JSONResponse({"folder": folder})

    async def remove_course(request: Request):
        """Delete a course. A started course needs a tick in the box first, because its progress goes too."""
        cid = request.path_params["cid"]
        c = V.get_course(cid)
        if not c:
            return go("/courses", err="That course isn't installed.")
        jid = V.journey_for_course(cid)
        if request.method == "GET":
            info = None
            if jid:
                prog = V.progress(jid)
                info = {"percent": prog["percent"], "milestones": len(V.milestones(jid))}
            return page("delete_course.html", request, c=c, info=info)
        form = await request.form()
        if jid and form.get("sure") != "1":
            return go(f"/courses/{cid}/remove", err="Tick the box to confirm.")
        import shutil
        shutil.rmtree(V.home / "course_history" / cid, ignore_errors=True)
        if jid:
            V.archive_course(cid)
        else:
            V.delete_course(cid)
        return go("/courses", ok=f"Deleted “{c.title}”.")

    # ---- updating a course to a newer version ---------------------------------
    def _pending(cid: str) -> Path:
        return V.home / "pending" / cid

    def _hold_update(new: Course, media_zip=None):
        """A newer copy of a course you already have arrived. Keep it aside and ask what to do."""
        import shutil
        from .course import save_course_folder
        pend = _pending(new.id)
        shutil.rmtree(pend, ignore_errors=True)
        save_course_folder(new, pend / "course")
        if media_zip is not None:
            zf, inside = media_zip
            for info, rel in inside:
                target = (pend / "files" / rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
        return go(f"/courses/{new.id}/update")

    def _outline_lines(c: Course) -> list:
        out = []
        for m in c.modules:
            out.append(("module", m["title"], ""))
            out += [("lesson", les["title"], m["title"]) for les in m["lessons"]]
        return out

    async def course_update(request: Request):
        cid = request.path_params["cid"]
        cur = V.get_course(cid)
        pend = _pending(cid)
        if not cur or not (pend / "course" / "course.yaml").exists():
            return go("/courses", err="There's no update waiting for this course.")
        new = load_course(files_from_folder(pend / "course"))
        if request.method == "GET":
            a, b = _outline_lines(cur), _outline_lines(new)
            added = [x for x in b if x not in a]
            removed = [x for x in a if x not in b]
            jid = V.journey_for_course(cid)
            return page("update_course.html", request, cur=cur, new=new, added=added[:40], removed=removed[:40],
                        same=(cur.hash == new.hash), started=bool(jid))
        import shutil
        form = await request.form()
        choice = form.get("choice")
        if choice == "cancel":
            shutil.rmtree(pend, ignore_errors=True)
            return go("/courses", ok="Kept your course as it was.")
        if choice == "separate":
            base, n = new.id, 1
            while V.get_course(new.id):
                n += 1
                new.id = f"{base}-{n}"
        else:
            new.extra.update({k: v for k, v in cur.extra.items() if k not in new.extra})
            # The version before is kept, so Undo in the editor can bring it back.
            editor.save(V, new)
        if choice == "separate":
            V.install_course(new)
        files = pend / "files"
        if files.exists():
            dest = V.media_dir(new.id)
            dest.mkdir(parents=True, exist_ok=True)
            for f in files.rglob("*"):
                if f.is_file():
                    target = dest / f.relative_to(files)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(target))
        shutil.rmtree(pend, ignore_errors=True)
        if choice == "separate":
            return go("/courses", ok=f"Added “{new.title}” as a separate course.")
        return go("/courses", ok=f"Updated “{new.title}”. Your progress is kept.")

    async def refresh_from_folder(request: Request):
        """Look in the course's folder again: new videos become new lessons, everything you did stays."""
        cid = request.path_params["cid"]
        cur = V.get_course(cid)
        root = V.media_root(cid)
        if not cur or not root:
            return go("/courses", err="This course isn't linked to a folder.")
        try:
            fresh = course_from_folder(root, cur.title)
        except CourseError as e:
            return go("/courses", err=e.problems[0])
        merged, added = _merge_folder(cur, fresh)
        if not added:
            return go(_back(request), ok="Nothing new in the folder. Your course is up to date.")
        editor.bump(merged)
        editor.save(V, merged)
        return go(_back(request), ok=f"Added {added} new lesson(s) from the folder.")

    def _merge_folder(cur: Course, fresh: Course):
        """Keep every existing module and lesson (with your edits, tasks and ids); add what's new."""
        import copy
        merged = copy.deepcopy(cur)
        have = {les.get("media") for m in merged.modules for les in m["lessons"] if les.get("media")}
        ids = editor.all_ids(merged)
        added = 0
        for fm in fresh.modules:
            new_lessons = [les for les in fm["lessons"] if les.get("media") and les["media"] not in have]
            if not new_lessons:
                continue
            target = next((m for m in merged.modules if m["title"] == fm["title"]), None)
            if target is None:
                mid = editor._unique("m", ids)
                ids.add(mid)
                target = {"id": mid, "title": fm["title"], "lessons": [], "requires": []}
                merged.modules.append(target)
            for les in new_lessons:
                lid = editor._unique(f"{target['id']}-l", ids)
                ids.add(lid)
                target["lessons"].append({**les, "id": lid})
                added += 1
        merged.extra["media_index"] = {**cur.extra.get("media_index", {}), **fresh.extra.get("media_index", {})}
        return merged, added

    # ---- AI course maker -----------------------------------------------------
    def _titled_videos(text: str) -> str:
        out = []
        for line in text.splitlines()[:200]:
            line = line.strip()
            if not line:
                continue
            if "|" not in line and line.startswith("http"):
                title = editor.youtube_title(line)
                line = f"{title} | {line}" if title else line
            out.append(line)
        return "\n".join(out)

    async def ai_page(request: Request):
        ctx: dict = {"step": 1, "form": {}}
        if request.method == "POST":
            form = await request.form()
            action = form.get("action")
            ctx["form"] = dict(form)
            if action == "auto":
                from starlette.concurrency import run_in_threadpool
                prompt = str(form.get("prompt", ""))
                try:
                    reply = await run_in_threadpool(integrations.ask_ai, V, prompt)
                except RuntimeError as e:
                    ctx.update(step=2, prompt=prompt, ai_error=str(e))
                    return page("ai.html", request, ai=integrations.ai_settings(V), providers=integrations.PROVIDERS, **ctx)
                action, form = "check", {"reply": reply}
                ctx["form"] = {}
            if action == "prompt":
                extra = {k: str(form.get(k, "")) for k in ("book_title", "book_author", "chapters", "material", "exam",
                                                           "playlist", "videos", "course_name", "platform",
                                                           "course_outline", "project")}
                if form.get("source") == "playlist" and extra["videos"].strip() and form.get("fetch_titles"):
                    # Fill in missing video titles from YouTube (only because you ticked the box: this goes online).
                    from starlette.concurrency import run_in_threadpool
                    extra["videos"] = await run_in_threadpool(_titled_videos, extra["videos"])
                ctx["prompt"] = ai.build_prompt(str(form.get("topic", "")), str(form.get("level", "beginner")),
                                                int(form.get("weeks") or 4), int(form.get("hours") or 3),
                                                str(form.get("language", "English")), str(form.get("notes", "")),
                                                source=str(form.get("source", "topic")), **extra)
                ctx["step"] = 2
            elif action in ("check", "save"):
                text = strip_fences(str(form.get("reply", "")))
                ctx["step"] = 3
                ctx["reply"] = form.get("reply", "")
                try:
                    course = load_course({"course.yaml": text})
                except CourseError as e:
                    ctx["problems"] = e.problems
                else:
                    if action == "save":
                        if V.get_course(course.id):
                            course.id = f"{course.id}-{now_utc()[:10]}"
                        V.install_course(course)
                        return go("/courses", ok=f"Saved “{course.title}”. It's ready to start.")
                    ctx["preview"] = course
        return page("ai.html", request, ai=integrations.ai_settings(V), providers=integrations.PROVIDERS, **ctx)

    # ---- learning ----------------------------------------------------------------
    async def course_overview(request: Request):
        j = journey_or_404(request.path_params["jid"])
        if not j:
            return go("/", err="That course wasn't found.")
        course = V.get_course(j["course_id"])
        return page("course.html", request, j=j, prog=V.progress(j["id"]),
                    missing=V.missing_media(course) if course else [],
                    media_root=V.media_root(j["course_id"]) if course else None)

    def _module_state(prog: dict, module_id: str) -> dict | None:
        return next((m for m in prog["modules"] if m["id"] == module_id), None)

    def _module_done(jid: str, mid: str) -> bool:
        m = _module_state(V.progress(jid), mid)
        return bool(m and m["status"] == "done")

    async def lesson(request: Request):
        j = journey_or_404(request.path_params["jid"])
        if not j:
            return go("/", err="That course wasn't found.")
        course = V.get_course(j["course_id"])
        found = course.find_lesson(request.path_params["lid"])
        if not found:
            return go(f"/learn/{j['id']}", err="That lesson wasn't found.")
        module, les = found
        prog = V.progress(j["id"])
        mstate = _module_state(prog, module["id"])
        if mstate["status"] == "locked":
            return go(f"/learn/{j['id']}", err="Finish the module before this one first.")
        V.add_event(j["id"], "lesson_opened", {"lesson": les["id"]})
        idx = [x["id"] for x in module["lessons"]].index(les["id"])
        lstate = mstate["lessons"][idx]
        nxt = module["lessons"][idx + 1]["id"] if idx + 1 < len(module["lessons"]) else None
        prv = module["lessons"][idx - 1]["id"] if idx > 0 else None
        return page("lesson.html", request, j=j, course=course, module=module, mstate=mstate, lesson=les,
                    lstate=lstate, html=media_mod.lesson_html(course.id, les, md.render(_drop_title(les["content"], les["title"])),
                                                       _course_files_view(course.id), gettext),
                    next_id=nxt, prev_id=prv,
                    has_answers=course.has_answers, prog=prog)

    async def module_page(request: Request):
        j = journey_or_404(request.path_params["jid"])
        if not j:
            return go("/", err="That course wasn't found.")
        course = V.get_course(j["course_id"])
        module = next((m for m in course.modules if m["id"] == request.path_params["mid"]), None)
        if not module:
            return go(f"/learn/{j['id']}", err="That module wasn't found.")
        prog = V.progress(j["id"])
        mstate = _module_state(prog, module["id"])
        if mstate["status"] == "locked":
            return go(f"/learn/{j['id']}", err="Finish the module before this one first.")
        exams = [x for x in checks.my_exams(V, j["id"]) if course.find_requirement(x["exam"]["req"]) and
                 course.find_requirement(x["exam"]["req"])[0]["id"] == module["id"]]
        return page("module.html", request, j=j, course=course, module=module, mstate=mstate,
                    has_answers=course.has_answers, exams=exams)

    async def take_exam(request: Request):
        j = journey_or_404(request.path_params["jid"])
        exam = checks.get_my_exam(V, request.path_params["eid"]) if j else None
        if not exam or exam["journey"] != j["id"]:
            return go("/", err="That exam wasn't found.")
        course = V.get_course(j["course_id"])
        found = course.find_requirement(exam["req"])
        module = found[0] if found else {"id": "", "title": exam["task"], "lessons": []}
        checker_name = display_name(V.person(exam["checker"]["id"]))
        if any(e["type"] == "exam_taken" and e["data"]["exam"] == exam["id"] for e in V.events(j["id"])):
            return go(f"/learn/{j['id']}/module/{module['id']}", err="You already took this exam.")
        if request.method == "POST":
            form = await request.form()
            answers = {q["id"]: str(form.get(q["id"], "")) for q in exam["questions"]}
            V.add_event(j["id"], "exam_taken", {"exam": exam["id"], "req": exam["req"], "task": exam["task"],
                                                "checker": exam["checker"]["id"], "answers": answers})
            return page("quiz_result.html", request, j=j, module=module, verified=True, checker_name=checker_name,
                        yay=encourage.CELEBRATE["exam"])
        return page("quiz.html", request, j=j, module=module, req={"pass": exam["pass"]}, exam=exam["questions"],
                    seed="", verified=True, checker_name=checker_name)

    async def journey_action(request: Request):
        jid, action = request.path_params["jid"], request.path_params["action"]
        if not journey_or_404(jid):
            return go("/", err="That course wasn't found.")
        form = await request.form()
        back = str(form.get("back") or "/")
        if not back.startswith("/"):
            back = "/"
        evs = V.events(jid)
        if action == "commit":
            n = max(1, min(int(form.get("per_week") or 2), 14))
            V.add_event(jid, "commitment_set", {"per_week": n})
            return go(back, ok=f"Your goal: {n} milestone{'s' if n > 1 else ''} a week. Your checker will see it.", yay="goal")
        if action == "pause" and not pace.is_paused(evs):
            V.add_event(jid, "pause_started", {"reason": str(form.get("reason", "")).strip()[:200]})
            return go(back, ok="You're on a break. Weeks on a break don't count as missed.")
        if action == "resume" and pace.is_paused(evs):
            V.add_event(jid, "pause_ended", {})
            return go(back, yay="back")
        if action == "reflect":
            data = {k: str(form.get(k, "")).strip()[:2000] for k in ("learned", "hard", "next")}
            if not any(data.values()):
                return go(back, err="Write at least one answer.")
            V.add_event(jid, "reflection_saved", data)
            return go(back, ok="Reflection saved.")
        return go(back)

    async def practice(request: Request):
        j = journey_or_404(request.path_params["jid"])
        if not j:
            return go("/", err="That course wasn't found.")
        course = V.get_course(j["course_id"])
        if request.method == "GET":
            due = pace.due_cards(V, course.id)[:10]
            if not due:
                return go("/", ok="Nothing to review today. Come back tomorrow.")
            seed = new_seed()
            exam = build_exam(course, due, seed)
            return page("quiz.html", request, j=j, course=course, module={"id": "", "title": "Review"},
                        req={"pass": 0}, exam=exam, seed=seed, review=True, qids=",".join(due))
        form = await request.form()
        seed, qids = str(form.get("seed", "")), [q for q in str(form.get("qids", "")).split(",") if q in course.questions]
        exam = build_exam(course, qids, seed)
        result = grade(course, exam, {it["id"]: str(form.get(it["id"], "")) for it in exam})
        pace.update_cards(V, course.id, {it["id"]: d["ok"] for it, d in zip(exam, result["details"])})
        V.add_event(j["id"], "review_done", {"count": result["total"], "right": result["score"]})
        return page("quiz_result.html", request, j=j, module={"id": "", "title": "Review", "lessons": []},
                    req={"pass": 0, "id": ""}, result=result, passed=True, review=True)

    async def lesson_done(request: Request):
        jid, lid = request.path_params["jid"], request.path_params["lid"]
        j = journey_or_404(jid)
        course = V.get_course(j["course_id"]) if j else None
        found = course.find_lesson(lid) if course else None
        if not found:
            return go("/", err="That lesson wasn't found.")
        was_done = _module_done(jid, found[0]["id"])
        if not any(e["type"] == "lesson_done" and e["data"]["lesson"] == lid for e in V.events(jid)):
            V.add_event(jid, "lesson_done", {"lesson": lid, "title": found[1]["title"]})
        if not was_done and _module_done(jid, found[0]["id"]):
            return go(f"/learn/{jid}/module/{found[0]['id']}", yay="module")
        form = await request.form()
        target = form.get("next")
        if target:
            return go(f"/learn/{jid}/lesson/{target}", yay="lesson")
        return go(f"/learn/{jid}/module/{found[0]['id']}", ok="All lessons read. Now the tasks.")

    async def _req_ctx(request: Request):
        j = journey_or_404(request.path_params["jid"])
        if not j:
            return None, None, None, None
        course = V.get_course(j["course_id"])
        found = course.find_requirement(request.path_params["rid"])
        if not found:
            return j, course, None, None
        return j, course, found[0], found[1]

    async def add_evidence(request: Request):
        j, course, module, req = await _req_ctx(request)
        if not req:
            return go("/", err="That task wasn't found.")
        form = await request.form()
        up = form.get("file")
        back = f"/learn/{j['id']}/module/{module['id']}#task-{req['id']}"
        if not up or not getattr(up, "filename", ""):
            return go(back, err="Choose a file first.")
        data = await up.read()
        if not data:
            return go(back, err="That file is empty.")
        if len(data) > 100 * 1024 * 1024:
            return go(back, err="That file is over 100 MB. Try a smaller file or a screenshot.")
        was_done = _module_done(j["id"], module["id"])
        V.save_evidence(j["id"], req["id"], up.filename, data, task=req["prompt"])
        if not was_done and _module_done(j["id"], module["id"]):
            return go(back, yay="module")
        return go(back, ok=f"Saved “{up.filename}” as your work.")

    async def add_git(request: Request):
        j, course, module, req = await _req_ctx(request)
        if not req:
            return go("/", err="That task wasn't found.")
        form = await request.form()
        back = f"/learn/{j['id']}/module/{module['id']}#task-{req['id']}"
        try:
            name, data = integrations.git_summary(str(form.get("folder", "")))
        except RuntimeError as e:
            return go(back, err=str(e))
        V.save_evidence(j["id"], req["id"], name, data, task=req["prompt"])
        return go(back, ok="Saved your Git project's history as proof.")

    async def save_writeup(request: Request):
        j, course, module, req = await _req_ctx(request)
        if not req:
            return go("/", err="That task wasn't found.")
        form = await request.form()
        text = str(form.get("text", "")).strip()
        words = len(text.split())
        back = f"/learn/{j['id']}/module/{module['id']}#task-{req['id']}"
        if not text:
            return go(back, err="Write something first.")
        was_done = _module_done(j["id"], module["id"])
        V.add_event(j["id"], "writeup_saved", {"req": req["id"], "task": req["prompt"], "text": text, "words": words})
        if not was_done and _module_done(j["id"], module["id"]):
            return go(back, yay="module")
        need = req.get("min_words", 40)
        if words < need:
            return go(back, ok=f"Saved. You have {words} words; this needs at least {need} to count.")
        return go(back, ok="Saved your explanation.")

    async def quiz(request: Request):
        j, course, module, req = await _req_ctx(request)
        if not req or req["type"] != "quiz":
            return go("/", err="That quiz wasn't found.")
        if request.method == "GET":
            seed = new_seed()
            try:
                exam = build_exam(course, req["questions"], seed)
            except NoAnswers:
                return go(f"/learn/{j['id']}/module/{module['id']}",
                          err="This course came without answers, so practice quizzes aren't available. "
                              "Ask whoever shared it for the version with answers.")
            return page("quiz.html", request, j=j, course=course, module=module, req=req, exam=exam, seed=seed)
        form = await request.form()
        seed = str(form.get("seed", ""))
        exam = build_exam(course, req["questions"], seed)
        picked = {item["id"]: str(form.get(item["id"], "")) for item in exam}
        result = grade(course, exam, picked)
        passed = result["percent"] >= req.get("pass", 70)
        pace.update_cards(V, course.id, {d_id: d["ok"] for d_id, d in zip([it["id"] for it in exam], result["details"])})
        V.add_event(j["id"], "quiz_taken", {"req": req["id"], "task": module["title"], "mode": "practice",
                                            "seed": seed, "answers": picked,
                                            "score": result["score"], "total": result["total"],
                                            "percent": result["percent"], "passed": passed})
        done_now = _module_done(j["id"], module["id"])
        return page("quiz_result.html", request, j=j, module=module, req=req, result=result, passed=passed,
                    yay=encourage.CELEBRATE["module" if (passed and done_now) else "quiz"] if passed else None)

    # ---- milestones -----------------------------------------------------------
    async def milestones(request: Request):
        cards = [journey_card(j) for j in V.journeys()]
        for c in cards:
            c["send"] = None
            if c["milestones"]:
                jid = c["journey"]["id"]
                since = exchange.checkers_have(V, jid)
                sh = exchange.share_links(say("My progress on inPace 🐢 Tap the link to check it:"),
                                          exchange.make_progress_file(V, jid, since), say("My progress on inPace"))
                if sh["fits"]:
                    c["send"] = sh
        return page("milestones.html", request, cards=cards, checkers=V.my_checkers())

    async def save_milestone(request: Request):
        jid = request.path_params["jid"]
        if not journey_or_404(jid):
            return go("/milestones", err="That course wasn't found.")
        if not has_new(jid):
            return go("/milestones", err="Nothing new to save yet. Finish a lesson or task first.")
        m = V.create_milestone(jid)
        return go("/milestones", yay="milestone")

    async def export_progress(request: Request):
        jid = request.path_params["jid"]
        j = journey_or_404(jid)
        if not j:
            return go("/milestones", err="That course wasn't found.")
        if not V.milestones(jid):
            return go("/milestones", err="Save a milestone first.")
        data = exchange.make_progress_file(V, jid)
        title = data["journey"]["course"]["title"]
        return download(exchange.dump(data), f"{V.me['name']} - {title} - {now_utc()[:10]}.inpace", "application/json")

    async def file_pack(request: Request):
        jid = request.path_params["jid"]
        try:
            data = checks.make_file_pack(V, jid)
        except exchange.FileProblem as e:
            return go("/milestones", err=str(e))
        V._set_meta(f"pack:{jid}", now_utc())
        return download(data, f"{V.me['name']} - requested files - {now_utc()[:10]}.zip", "application/zip")

    async def learning_record(request: Request):
        jid = request.path_params["jid"]
        if not journey_or_404(jid) or not V.milestones(jid):
            return go("/milestones", err="Save a milestone first.")
        j = V.journey(jid)
        title = V.get_course(j["course_id"]).title
        CURRENT["lang"] = V._meta("lang", "en") or "en"
        return download(record.build_record(V, jid, gettext, CURRENT["lang"], MONTHS[CURRENT["lang"]]).encode("utf-8"), f"{V.me['name']} - {title} - learning record.html",
                        "text/html")

    # ---- races ------------------------------------------------------------------
    async def races_page(request: Request):
        rows = []
        for r in races.my_races(V):
            b = races.board(V, r["id"])
            rows.append({"r": r, "b": b})
        return page("races.html", request, rows=rows, kinds=races.KINDS, journeys=[
            {**j, "title": (V.get_course(j["course_id"]).title if V.get_course(j["course_id"]) else j["course_id"])}
            for j in V.journeys()])

    async def race_new(request: Request):
        form = await request.form()
        try:
            race = races.create_race(V, str(form.get("name", "")), str(form.get("kind", "")), int(form.get("days") or 14))
            races.join_race(V, race, str(form.get("journey", "")), str(form.get("folder", "")))
        except (ValueError, exchange.FileProblem) as e:
            return go("/races", err=str(e))
        return go(f"/races/{race['id']}", ok="Race created. Send the invite to your friends.")

    async def race_join(request: Request):
        form = await request.form()
        import json as _json
        try:
            race = _json.loads(str(form.get("race", "")))
            races.join_race(V, race, str(form.get("journey", "")), str(form.get("folder", "")))
        except (ValueError, exchange.FileProblem) as e:
            return go("/races", err=str(e))
        return go(f"/races/{race['id']}", ok=f"You joined “{race['name']}”.")

    async def race_page(request: Request):
        rid = request.path_params["rid"]
        r = races.get_race(V, rid)
        if not r:
            return go("/races", err="That race wasn't found.")
        sync_msg = None
        if r["folder"]:
            try:
                n = races.sync_folder(V, rid)
                sync_msg = f"Shared folder synced · {n} other racer{'s' if n != 1 else ''}"
            except exchange.FileProblem as e:
                sync_msg = str(e)
        b = races.board(V, rid)
        invite = exchange.share_links(say("Join my race on inPace 🐢 Tap the link:"),
                                      races.get_race(V, rid)["race"], say("Join my race on inPace"))
        try:
            update = exchange.share_links(say("My inPace race update. Tap the link:"),
                                          races.make_update(V, rid), say("My inPace race update"))
        except Exception:
            update = None
        return page("race.html", request, b=b, rid=rid, sync_msg=sync_msg, cheers=races.CHEERS,
                    invite=invite, update=update)

    async def race_action(request: Request):
        rid, action = request.path_params["rid"], request.path_params["action"]
        r = races.get_race(V, rid)
        if not r:
            return go("/races", err="That race wasn't found.")
        if action == "invite":
            return download(exchange.dump(r["race"]), f"Race invite - {r['race']['name']}.inpace", "application/json")
        if action == "update":
            return download(exchange.dump(races.make_update(V, rid)),
                            f"Race update - {V.me['name']} - {now_utc()[:10]}.inpace", "application/json")
        form = await request.form()
        if action == "cheer":
            races.send_cheer(V, rid, str(form.get("to", "")), str(form.get("text", "")))
            return go(f"/races/{rid}", ok="Cheer added. It goes out with your next update.")
        if action == "folder":
            V.db.execute("UPDATE races SET folder=? WHERE id=?", (str(form.get("folder", "")).strip(), rid))
            V.db.commit()
            return go(f"/races/{rid}", ok="Saved.")
        if action == "leave":
            races.leave_race(V, rid)
            return go("/races", ok="You left the race.")
        return go(f"/races/{rid}")

    # ---- course editor ---------------------------------------------------------
    async def edit_new(request: Request):
        if request.method == "POST":
            f = await request.form()
            try:
                links = str(f.get("links", "")) if f.get("start") == "links" else ""
                if f.get("start") == "links" and not links.strip():
                    raise CourseError(["Paste at least one link or file path."])
                from starlette.concurrency import run_in_threadpool
                c = await run_in_threadpool(
                    editor.new_course, V, str(f.get("title", "")), str(f.get("description", "")),
                    str(f.get("module_title", "")), str(f.get("lesson_title", "")), str(f.get("content", "")),
                    links, str(f.get("language", "en")), bool(f.get("fetch_titles")))
            except CourseError as e:
                return page("edit_new.html", request, problems=e.problems, form=dict(f))
            return go(f"/edit/{c.id}", ok="Course created. Add more lessons, tasks and questions.")
        return page("edit_new.html", request, form={})

    async def edit_course(request: Request):
        cid = request.path_params["cid"]
        c = V.get_course(cid)
        if not c:
            return go("/courses", err="That course isn't installed.")
        if request.method == "POST":
            f = await request.form()
            data = {k: str(v) for k, v in f.items()}
            data["questions"] = [str(x) for x in f.getlist("questions")]
            try:
                if data.get("action") == "undo":
                    editor.undo(V, cid)
                    return go(f"/edit/{cid}", ok="Undone. The course is back to how it was before your last change.")
                if data.get("action") in ("add_links", "add_lesson") and data.get("fetch_titles"):
                    from starlette.concurrency import run_in_threadpool
                    await run_in_threadpool(editor.edit, V, cid, data["action"], data)
                else:
                    editor.edit(V, cid, data.get("action", ""), data)
            except CourseError as e:
                return page("edit_course.html", request, c=c, problems=e.problems, started=bool(V.journey_for_course(cid)),
                            can_undo=editor.can_undo(V, cid), journey=V.journey_for_course(cid))
            anchor = f"#{data['module']}" if data.get("module") else ""
            return go(f"/edit/{cid}{anchor}", ok="Saved.")
        return page("edit_course.html", request, c=c, started=bool(V.journey_for_course(cid)),
                    can_undo=editor.can_undo(V, cid), journey=V.journey_for_course(cid))

    async def edit_yaml(request: Request):
        cid = request.path_params["cid"]
        c = V.get_course(cid)
        if not c:
            return go("/courses", err="That course isn't installed.")
        if request.method == "POST":
            text = str((await request.form()).get("yaml", ""))
            try:
                editor.save_yaml(V, cid, text)
            except CourseError as e:
                return page("edit_yaml.html", request, c=c, text=text, problems=e.problems)
            return go(f"/edit/{cid}", ok="Saved.")
        return page("edit_yaml.html", request, c=c, text=editor.course_to_yaml(c))

    async def lesson_preview(request: Request):
        """What the lesson will look like, for the Preview tab in the lesson editor."""
        cid = request.path_params["cid"]
        f = await request.form()
        les = {"title": str(f.get("title", "")), "content": str(f.get("content", "")), "media": str(f.get("media", "")).strip()}
        body = md.render(_drop_title(les["content"], les["title"]))
        return HTMLResponse(media_mod.lesson_html(cid, les, body, _course_files_view(cid), gettext))

    async def edit_lesson_media(request: Request):
        cid, lid = request.path_params["cid"], request.path_params["lid"]
        c = V.get_course(cid)
        if not c or not c.find_lesson(lid):
            return go(f"/edit/{cid}", err="That lesson wasn't found.")
        form = await request.form()
        back = f"/edit/{cid}/lesson/{lid}"
        label = str(form.get("label", "")).strip()
        ref = (str(form.get("ref", "")).strip() or str(form.get("ref_path", "")).strip()).strip('"')
        up = form.get("file")
        if up is not None and getattr(up, "filename", ""):
            # A small file added here is kept with the course, so it travels when you share it with files.
            name = re.sub(r"[^\w .()-]+", "", Path(up.filename).name, flags=re.UNICODE).strip() or "file"
            dest = V.media_dir(cid) / "media"
            dest.mkdir(parents=True, exist_ok=True)
            import shutil
            with open(dest / name, "wb") as out:
                shutil.copyfileobj(up.file, out, 1024 * 1024)
            ref = f"media/{name}"
        if not ref:
            return go(back, err="Add a file, a link or a path first.")
        from .course import is_url, local_ref, media_kind
        if not is_url(ref) and not (local_ref(ref) and media_kind(ref)):
            return go(back, err="That isn't a video, audio, web page, PDF or picture inPace can show.")
        try:
            editor.edit(V, cid, "add_media", {"lesson": lid, "ref": ref, "label": label})
        except CourseError as e:
            return go(back, err=e.problems[0])
        return go(back, ok="Added to the lesson.")

    async def edit_course_image(request: Request):
        """Add, change or remove the course's cover picture. It's saved with the course's own files."""
        cid = request.path_params["cid"]
        c = V.get_course(cid)
        if not c:
            return go("/courses", err="That course isn't installed.")
        form = await request.form()
        folder = V.media_dir(cid)
        if form.get("remove"):
            old = c.extra.pop("image", None)
            if old and old.startswith("cover.") and (folder / old).exists():
                (folder / old).unlink()
            editor.save(V, c)
            return go(f"/edit/{cid}", ok="Removed the picture.")
        up = form.get("image")
        if not up or not getattr(up, "filename", ""):
            return go(f"/edit/{cid}", err="Choose a picture first.")
        ext = Path(up.filename).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            return go(f"/edit/{cid}", err="Choose a JPG, PNG, WebP or GIF picture.")
        data = await up.read()
        if len(data) > 8 * 1024 * 1024:
            return go(f"/edit/{cid}", err="That picture is too big. Choose one under 8 MB.")
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("cover.*"):
            old.unlink()
        (folder / f"cover{ext}").write_bytes(data)
        c.extra["image"] = f"cover{ext}"
        editor.save(V, c)
        return go(f"/edit/{cid}", ok="Saved the picture.")

    async def edit_lesson(request: Request):
        cid, lid = request.path_params["cid"], request.path_params["lid"]
        c = V.get_course(cid)
        found = c.find_lesson(lid) if c else None
        if not found:
            return go(f"/edit/{cid}", err="That lesson wasn't found.")
        return page("edit_lesson.html", request, c=c, module=found[0], lesson=found[1])

    # ---- people ---------------------------------------------------------------
    async def people(request: Request):
        rows = []
        for p in V.people():
            rows.append({**p, "waiting": V.waiting_count(p["id"]) if p["i_check"] else 0,
                         "journeys": V.received(p["id"]) if p["i_check"] else []})
        by_course: dict[str, list] = {}
        for p in rows:
            for r in p["journeys"]:
                by_course.setdefault(r["course"], []).append({"person": p, "rec": r,
                                                              "percent": (r["data"]["milestones"][-1]["body"]["summary"]["percent"]
                                                                          if r["data"]["milestones"] else 0)})
        share = exchange.share_links(say("Add me on inPace 🐢 Tap the link:"), exchange.make_contact_card(V),
                                     say("Add me on inPace"))
        added = V.person(str(request.query_params.get("added", "")))
        return page("people.html", request, people=rows, by_course=by_course, share=share, added=added)

    async def my_card(request: Request):
        return download(exchange.dump(exchange.make_contact_card(V)), f"{V.me['name']} - contact card.inpace",
                        "application/json")

    async def add_person(request: Request):
        form = await request.form()
        import json as _json
        try:
            card = _json.loads(str(form.get("card", "")))
            exchange.check_contact_card(card)
        except (ValueError, exchange.FileProblem):
            return go("/people", err="That contact card couldn't be read. Ask for a new one.")
        if card["id"] == V.identity.id:
            return go("/people", err="That's your own contact card.")
        rel = form.get("relationship")
        checks_me = rel in ("checks_me", "buddies")
        i_check = rel in ("i_check", "buddies")
        if not (checks_me or i_check):
            return go("/people", err="Choose how you're connected.")
        V.add_person(card["id"], card["name"], card["color"], checks_me, i_check)
        nick = str(form.get("nickname", "")).strip()
        if nick:
            p = V.person(card["id"])
            V.set_roles(card["id"], bool(p["checks_me"]), bool(p["i_check"]), nick)
        nxt = str(form.get("then", ""))
        if nxt.startswith("/review/") or nxt == "/open":
            return go(nxt, ok=f"Added {card['name']}.")
        return go(f"/people?added={card['id']}", ok=f"Added {card['name']}.")

    async def edit_person(request: Request):
        pid = request.path_params["pid"]
        form = await request.form()
        if form.get("remove"):
            V.remove_person(pid)
            return go("/people", ok="Removed.")
        V.set_roles(pid, bool(form.get("checks_me")), bool(form.get("i_check")), str(form.get("nickname", "")))
        return go("/people", ok="Saved.")

    # ---- one place to open any file ------------------------------------------
    def _install_pack(request: Request, fileobj, fname: str):
        import shutil
        import zipfile
        try:
            zf = zipfile.ZipFile(fileobj)
            c = load_course(files_from_zip(fileobj))
        except zipfile.BadZipFile:
            return go("/open", err="This doesn't look like a course file.")
        except CourseError as e:
            return page("open.html", request, problems=e.problems, filename=fname)
        inside = media_in_zip(zf)
        existing = V.get_course(c.id)
        if existing and existing.hash != c.hash:
            return _hold_update(c, (zf, inside) if inside else None)
        c = V.install_course(c)
        if inside:
            dest = V.media_dir(c.id).resolve()
            for info, rel in inside:
                target = (dest / rel).resolve()
                try:
                    target.relative_to(dest)
                except ValueError:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
        lines = [f"Added the course “{c.title}”."]
        if c.questions and not c.has_answers:
            lines.append("It came without answers, so practice quizzes are off.")
        if not inside and V.missing_media(c):
            lines.append("Its videos and other files aren't inside. Choose their folder on the course page.")
        return go("/courses", ok="\n".join(lines))

    async def open_link(request: Request):
        """inPace was opened from a link (inpace://open/...). Hand the data to Open, like a pasted code."""
        body = exchange.link_body("inpace:" + str(request.query_params.get("d", "")))
        if not body:
            return go("/", err="That link is cut off or damaged. Copy the whole message again.")
        if not V.is_set_up:
            V._set_meta("pending_link", body)  # opened before setup: come back to it right after
            return go("/setup")
        V._set_meta("pending_link", "")
        return page("link.html", request, code="inpace:" + body)

    async def open_file(request: Request):
        if request.method == "GET":
            return page("open.html", request)
        form = await request.form()
        back = "/people" if form.get("from") == "people" else "/open"
        if form.get("code") is not None:
            try:
                raw = exchange.dump(exchange.from_code(str(form.get("code"))))
                fname = "code.inpace"
            except exchange.FileProblem as e:
                return go(back, err=str(e))
        else:
            up = form.get("file")
            if not up or not getattr(up, "filename", ""):
                return go("/open", err="Choose a file first.")
            fname = up.filename
            up.file.seek(0, 2)
            size = up.file.tell()
            up.file.seek(0)
            if size > 40 * 1024 * 1024 and up.file.read(2) == b"PK":
                up.file.seek(0)  # a big course pack that carries its own videos: read it from disk, not memory
                return _install_pack(request, up.file, fname)
            up.file.seek(0)
            raw = await up.read()
        if raw[:2] == b"PK" and checks.is_file_pack(raw):
            try:
                res = checks.import_file_pack(V, raw)
            except (exchange.FileProblem, KeyError, ValueError) as e:
                return go("/open", err=str(e) if isinstance(e, exchange.FileProblem) else "This file pack is damaged.")
            return go(f"/review/{res['learner']}/{res['journey']}", ok=f"Got {res['count']} file(s) from {res['name']}.")
        if raw[:2] == b"PK":  # a course pack (zip)
            import io as _io
            return _install_pack(request, _io.BytesIO(raw), fname)
        if fname.lower().endswith((".yaml", ".yml")) or not raw.lstrip()[:1] == b"{":
            # A single-file course (the all-in-one format, e.g. saved from an AI chat).
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                return go("/open", err="This file isn't text inPace can read.")
            try:
                course = load_course({"course.yaml": strip_fences(text)})
            except CourseError as e:
                hint = []
                if any("is missing" in p and "lessons/" in p for p in e.problems):
                    hint = ["This course keeps its lessons in separate files. Put course.yaml and the lessons "
                            "folder together in a zip file, then open the zip."]
                return page("open.html", request, problems=hint + e.problems, filename=fname)
            existing = V.get_course(course.id)
            if existing and existing.hash != course.hash:
                return _hold_update(course)
            c = V.install_course(course)
            extra = "" if c.has_answers else " It has no answers, so practice quizzes are off."
            return go("/courses", ok=f"Added the course “{c.title}”.{extra}")
        try:
            data = exchange.read_inpace_file(raw)
        except exchange.FileProblem as e:
            return go("/open", err=str(e))
        kind = data["inpace"]
        try:
            if kind == "contact":
                exchange.check_contact_card(data)
                if data["id"] == V.identity.id:
                    return go("/open", err="That's your own contact card. Send it to the other person instead.")
                import json as _json
                return page("add_person.html", request, card=data, card_json=_json.dumps(data),
                            existing=V.person(data["id"]), then="/people")
            if kind == "progress":
                data = exchange.complete_progress(V, data)
                learner = data["learner"]["id"]
                if learner == V.identity.id:
                    return go("/open", err="That's your own progress file. Send it to your checker.")
                p = V.person(learner)
                if not p or not p["i_check"]:
                    import json as _json
                    card = {"id": learner, "name": data["learner"]["name"], "color": data["learner"]["color"]}
                    V.store_received(data)
                    return page("add_person.html", request, card=card, card_json=None, from_progress=True,
                                progress_json=_json.dumps(data), existing=p,
                                then=f"/review/{learner}/{data['journey']['id']}")
                V.store_received(data)
                return go(f"/review/{learner}/{data['journey']['id']}")
            if kind == "library-course":
                return go("/library?show=" + quote(str(data.get("id", ""))))
            if kind == "race":
                races.check_race(data)
                if races.get_race(V, data["id"]):
                    return go(f"/races/{data['id']}")
                import json as _json
                js = [{**j, "title": V.get_course(j["course_id"]).title} for j in V.journeys() if V.get_course(j["course_id"])]
                return page("join_race.html", request, race=data, race_json=_json.dumps(data), journeys=js,
                            kinds=races.KINDS)
            if kind == "race_update":
                name = races.import_update(V, data)
                return go(f"/races/{data['race']}", ok=f"Got {name}'s race update.")
            if kind == "exam":
                res = checks.import_exam(V, data)
                return go(f"/learn/{data['journey']}/exam/{data['id']}",
                          ok=f"{res['name']} sent you a verified exam for “{res['task']}”.")
            if kind == "approval":
                res = exchange.import_approval_file(V, data)
                first = {"approved": "{a} approved {b} milestone(s).", "question": "{a} has a question about {b} milestone(s).",
                         "flag": "{a} flagged {b} milestone(s)."}[res["decision"]]
                lines = [first.format(a=res["name"], b=res["count"])]
                if res["note"]:
                    lines.append(f"Note: “{res['note']}”")
                if res.get("results"):
                    lines.append("Your exam score is in.")
                if res.get("requests"):
                    lines.append(f"They asked to see {res['requests']} file(s).")
                return go("/milestones", ok="\n".join(lines),
                          yay="approved" if res["decision"] == "approved" else None)
        except exchange.FileProblem as e:
            return go("/open", err=str(e))
        except (KeyError, TypeError, ValueError):
            return go("/open", err="This file is damaged or from a newer version of inPace.")
        return go("/open", err="inPace doesn't know this kind of file yet.")

    async def add_person_from_progress(request: Request):
        """Checker adds an unknown learner straight from their progress file."""
        form = await request.form()
        import json as _json
        try:
            data = _json.loads(str(form.get("progress", "")))
            learner = data["learner"]
        except (ValueError, KeyError):
            return go("/open", err="Something went wrong. Open the file again.")
        V.add_person(learner["id"], learner["name"], learner["color"], False, True)
        nick = str(form.get("nickname", "")).strip()
        if nick:
            V.set_roles(learner["id"], False, True, nick)
        return go(f"/review/{learner['id']}/{data['journey']['id']}", ok=f"Added {learner['name']}.")

    # ---- reviewing someone ------------------------------------------------------
    async def review(request: Request):
        lid, jid = request.path_params["learner"], request.path_params["journey"]
        rec = V.received_one(lid, jid)
        person = V.person(lid)
        if not rec or not person:
            return go("/people", err="Open their progress file first.")
        if request.method == "POST":
            form = await request.form()
            decision = str(form.get("decision"))
            if decision not in ("approved", "question", "flag"):
                return go(f"/review/{lid}/{jid}", err="Choose approve, question or flag.")
            report = exchange.review_progress(V, rec["data"])
            if decision == "approved" and not report["history_ok"]:
                return go(f"/review/{lid}/{jid}", err="You can't approve while there's a problem with the history.")
            seqs = [m["body"]["seq"] for m in report["new"]] or [m["body"]["seq"] for m in report["milestones"][-1:]]
            note = str(form.get("note", ""))
            # Grade any verified exams in the new milestones, and add file requests.
            results = []
            for m in report["new"]:
                for e in m["body"]["events"]:
                    if e["type"] == "exam_taken":
                        g = checks.grade_exam_event(V, e["data"])
                        if g:
                            results.append({k: g[k] for k in ("exam", "score", "total", "percent", "passed")})
            known = checks.evidence_in(rec["data"])
            requests = []
            for item in form.getlist("request"):
                sha, _, name = str(item).partition("|")
                if sha in known:
                    requests.append({"sha256": sha, "name": known[sha]["name"]})
            extras = checks.sign_extras(V, lid, jid, results, requests) if (results or requests) else None
            approval = exchange.make_approval_file(V, rec["data"], decision, note, seqs, extras)
            out = V.home / "outbox"
            out.mkdir(exist_ok=True)
            fname = f"For {display_name(person)} - {decision} - {now_utc()[:10]}.inpace"
            fname = re.sub(r"[^\w .,()-]+", "", fname)
            (out / fname).write_bytes(exchange.dump(approval))
            return go(f"/review/{lid}/{jid}?file={quote(fname)}", ok="Done! Now send the reply file back.")
        report = exchange.review_progress(V, rec["data"])
        course = V.get_course(rec["data"]["journey"]["course"]["id"])
        # Resolve lesson and task names from our own copy of the course, if we have it.
        names = {}
        if course:
            for m in course.modules:
                for les in m["lessons"]:
                    names[les["id"]] = les["title"]
                for r in m["requires"]:
                    names[r["id"]] = r["prompt"]
        graded = {}
        for m in report["milestones"]:
            for e in m["body"]["events"]:
                if e["type"] == "exam_taken":
                    g = checks.grade_exam_event(V, e["data"])
                    if g:
                        graded[e["data"]["exam"]] = g
        quizzes = []
        if course:
            for m in course.modules:
                for r in m["requires"]:
                    if r["type"] == "quiz":
                        quizzes.append({"id": r["id"], "module": m["title"]})
        diffs = checks.outline_differences(course, rec["data"].get("outline"),
                                           rec["data"]["journey"]["course"]["hash"]) if course else []
        all_events = [e for m in report["milestones"] for e in m["body"]["events"]]
        weekly = pace.weeks(all_events, [m["body"]["created_at"] for m in report["milestones"]])
        reply_file = request.query_params.get("file")
        reply_share = None
        if reply_file and (V.home / "outbox" / Path(reply_file).name).exists():
            try:
                sh = exchange.share_links(say("My reply on inPace 🐢 Tap the link to open it:"),
                                          exchange.read_inpace_file((V.home / "outbox" / Path(reply_file).name).read_bytes()),
                                          say("My reply on inPace"))
                reply_share = sh if sh["fits"] else None
            except exchange.FileProblem:
                pass
        return page("review.html", request, person=person, rec=rec, report=report, names=names, weekly=weekly,
                    reply_file=reply_file, reply_share=reply_share, receipts=V.receipts(lid, jid),
                    graded=graded, have_files=checks.has_received_files(V), course=course, quizzes=quizzes,
                    sent=checks.sent_exams(V, lid, jid), course_diffs=diffs,
                    similar=checks.similar_writeups(V, rec["data"]), all_files=checks.evidence_in(rec["data"]))

    async def make_exam_page(request: Request):
        lid, jid, rid = request.path_params["learner"], request.path_params["journey"], request.path_params["rid"]
        rec, person = V.received_one(lid, jid), V.person(lid)
        if not rec or not person:
            return go("/people", err="Open their progress file first.")
        course = V.get_course(rec["data"]["journey"]["course"]["id"])
        found = course.find_requirement(rid) if course else None
        if not found or found[1]["type"] != "quiz":
            return go(f"/review/{lid}/{jid}", err="That quiz wasn't found in your copy of the course.")
        module, req = found
        ctx = dict(person=person, journey=jid, module=module, req=req,
                   has_earlier=bool(checks.earlier_quiz_questions(course, rid)))
        if request.method == "POST":
            form = await request.form()
            if form.get("action") == "add_question":
                try:
                    checks.add_private_question(V, course.id, str(form.get("text", "")), str(form.get("right", "")),
                                                str(form.get("wrong", "")).splitlines())
                except ValueError as e:
                    return go(f"/review/{lid}/{jid}/exam/{rid}", err=str(e))
                return go(f"/review/{lid}/{jid}/exam/{rid}", ok="Question saved. It's ticked for this exam.")
            try:
                exam = checks.make_exam(V, rec["data"], course, rid, [str(x) for x in form.getlist("private")],
                                        bool(form.get("surprise")))
            except exchange.FileProblem as e:
                return go(f"/review/{lid}/{jid}", err=str(e))
            out = V.home / "outbox"
            out.mkdir(exist_ok=True)
            fname = re.sub(r"[^\w .,()-]+", "", f"Exam for {display_name(person)} - {module['title']} - {now_utc()[:10]}.inpace")
            (out / fname).write_bytes(exchange.dump(exam))
            return page("make_exam.html", request, exam_file=fname, **ctx)
        return page("make_exam.html", request, private=checks.private_questions(V, course.id), **ctx)

    async def my_evidence(request: Request):
        """Play back your own saved work (a voice note or video) right on the task page."""
        sha = request.path_params["sha"]
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            return Response("Not found", status_code=404)
        p = V.home / "evidence" / sha[:2] / sha
        if not p.exists():
            return Response("Not found", status_code=404)
        name = Path(request.query_params.get("name") or "file").name
        import mimetypes
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if not mime.startswith(("audio/", "video/", "image/")):
            return download(p.read_bytes(), name)
        return FileResponse(p, media_type=mime, headers={"X-Content-Type-Options": "nosniff"})

    async def received_file(request: Request):
        got = checks.received_file(V, request.path_params["sha"])
        if not got:
            return go("/people", err="That file isn't here.")
        if request.query_params.get("play") == "1":
            import mimetypes
            mime = mimetypes.guess_type(got[1])[0] or ""
            if mime.startswith(("audio/", "video/")):
                return Response(got[0], media_type=mime, headers={"X-Content-Type-Options": "nosniff"})
        return download(got[0], got[1])

    async def outbox(request: Request):
        name = Path(request.path_params["name"]).name
        p = V.home / "outbox" / name
        if not p.exists():
            return go("/people", err="That file is gone. Review again to make a new one.")
        return download(p.read_bytes(), name, "application/json")

    async def backup(request: Request):
        form = await request.form()
        try:
            data = pace.make_backup(V, str(form.get("password", "")))
        except ValueError as e:
            return go("/settings", err=str(e))
        return download(data, f"inPace backup - {V.me['name']} - {now_utc()[:10]}.inpace-backup")

    async def restore(request: Request):
        form = await request.form()
        up = form.get("file")
        if not up or not getattr(up, "filename", ""):
            return go("/settings", err="Choose your backup file first.")
        raw = await up.read()
        try:
            pace.open_backup(raw, str(form.get("password", "")))
        except ValueError as e:
            return go("/settings", err=str(e))
        except Exception:
            return go("/settings", err="This backup couldn't be read.")
        pace.restore_backup(V, raw, str(form.get("password", "")))
        # Reopen the restored data right away (closing inPace instead looked like a crash).
        V.__init__(V.home)
        return go("/", ok="Backup restored.")

    async def ai_settings(request: Request):
        form = await request.form()
        integrations.save_ai_settings(V, str(form.get("provider", "")), str(form.get("model", "")),
                                      str(form.get("base_url", "")), str(form.get("key", "")))
        return go("/settings#ai", ok="AI settings saved.")

    async def settings(request: Request):
        if request.method == "POST":
            form = await request.form()
            V.rename(str(form.get("name", "")).strip() or V.me["name"], str(form.get("color", COLORS[0])))
            V._set_meta("lang", "ar" if form.get("lang") == "ar" else "en")
            return go("/settings", ok="Saved.")
        return page("settings.html", request, colors=COLORS, home=str(V.home), ai=integrations.ai_settings(V),
                    providers=integrations.PROVIDERS, models=integrations.DEFAULT_MODELS)

    async def ping(request: Request):
        """Lets a newly started inPace find and replace an older one using the same data folder."""
        from . import __version__
        return JSONResponse({"app": "inpace", "version": __version__, "home": str(V.home.resolve())})

    def _update_info() -> dict:
        kind = updater.install_kind()
        try:
            status = json.loads(V._meta("update_status", "{}") or "{}")
        except ValueError:
            status = {}
        if status.get("version") and not updater.newer(status["version"]):
            status = {}  # already running that version
        return {"kind": kind, "setting": V._meta("updates", "") or "", "status": status,
                "version": updater.__version__}

    async def update_setting(request: Request):
        form = await request.form()
        choice = "auto" if form.get("choice") == "auto" else "off"
        V._set_meta("updates", choice)
        if choice == "auto" and updater.install_kind() not in ("source", "android"):
            import threading
            threading.Thread(target=updater.run, args=(V,), kwargs={"force": True}, daemon=True).start()
            return go(_back(request), ok="Automatic updates are on. inPace checks once a day.")
        return go(_back(request), ok="Automatic updates are off. You can turn them on in Settings.")

    def _back(request: Request) -> str:
        from urllib.parse import urlsplit
        ref = urlsplit(request.headers.get("referer") or "/")
        return ref.path if ref.path.startswith("/") else "/"

    async def update_check(request: Request):
        import anyio
        status = await anyio.to_thread.run_sync(lambda: updater.run(V, force=True))
        msg = {"current": ("ok", "You have the newest version."),
               "installed": ("ok", "The new version is installed. Restart inPace to use it."),
               "ready": ("ok", "The new version is downloaded and ready to install."),
               "none": ("ok", "This copy runs from its code folder. Update it with git pull."),
               }.get(status.get("state"), ("err", "Couldn't check for updates right now. Are you online?"))
        return go("/settings#updates", **{msg[0]: msg[1]})

    async def update_install(request: Request):
        import anyio
        status = json.loads(V._meta("update_status", "{}") or "{}")
        if status.get("state") != "ready" or not status.get("file"):
            return go(_back(request), err="There's no update waiting to be installed.")
        try:
            await anyio.to_thread.run_sync(lambda: updater.install("deb", Path(status["file"])))
        except Exception as e:
            return go(_back(request), err=str(e))
        V._set_meta("update_status", json.dumps({"state": "installed", "version": status.get("version", "")}))
        return _restarting()

    async def update_restart(request: Request):
        return _restarting()

    def _restarting():
        import threading
        threading.Timer(0.6, updater.restart).start()
        return HTMLResponse('<!doctype html><meta charset="utf-8"><title>inPace</title>'
                            '<body style="font-family:system-ui;padding:3rem;background:#F7F3EA;color:#111">'
                            '<h1>Restarting inPace…</h1><p>The new version opens in a moment.</p></body>')

    async def set_theme(request: Request):
        form = await request.form()
        theme = str(form.get("theme", ""))
        if V.is_set_up:
            V._set_meta("theme", theme if theme in ("light", "dark") else "")
        return Response(status_code=204)

    async def quit_app(request: Request):
        import os
        import threading
        from .window import close_children
        threading.Timer(0.6, lambda: (close_children(), os._exit(0))).start()
        return HTMLResponse('<!doctype html><meta charset="utf-8"><title>inPace stopped</title>'
                            '<body style="font-family:system-ui;padding:3rem;background:#F7F7F4;color:#15191F">'
                            '<h1>inPace has stopped</h1><p>You can close this tab. Open inPace again any time.</p></body>')

    def needs_setup(handler):
        async def wrapped(request: Request):
            if not V.is_set_up:
                return go("/setup")
            return await handler(request)
        return wrapped

    routes = [
        Route("/setup", setup, methods=["GET", "POST"]),
        Route("/", needs_setup(home)),
        Route("/courses", needs_setup(courses)),
        Route("/courses/sample/{cid}", needs_setup(add_sample), methods=["POST"]),
        Route("/courses/from-folder", needs_setup(course_from_folder_route), methods=["POST"]),
        Route("/courses/{cid}/media-folder", needs_setup(set_media_folder), methods=["POST"]),
        Route("/pick-folder", needs_setup(pick_folder_route), methods=["POST"]),
        Route("/m/{cid}/{path:path}", needs_setup(media_file)),
        Route("/sample-file/{cid}/{path:path}", needs_setup(sample_file)),
        Route("/library", needs_setup(library_page)),
        Route("/library/{cid}/add", needs_setup(library_add), methods=["POST"]),
        Route("/courses/{cid}/publish", needs_setup(publish_course)),
        Route("/courses/{cid}/share", needs_setup(share_course)),
        Route("/courses/{cid}/publish/file", needs_setup(publish_file)),
        Route("/media-pos", needs_setup(media_position), methods=["POST"]),
        Route("/pdf", needs_setup(pdf_reader)),
        Route("/nav.json", needs_setup(nav_index)),
        Route("/settings/colors", needs_setup(set_accent), methods=["POST"]),
        Route("/evidence/{sha}", needs_setup(my_evidence)),
        Route("/courses/{cid}/start", needs_setup(start_course), methods=["POST"]),
        Route("/courses/{cid}/export", needs_setup(export_course)),
        Route("/courses/{cid}/remove", needs_setup(remove_course), methods=["GET", "POST"]),
        Route("/courses/{cid}/update", needs_setup(course_update), methods=["GET", "POST"]),
        Route("/courses/{cid}/refresh", needs_setup(refresh_from_folder), methods=["POST"]),
        Route("/ai", needs_setup(ai_page), methods=["GET", "POST"]),
        Route("/learn/{jid}", needs_setup(course_overview)),
        Route("/learn/{jid}/lesson/{lid}", needs_setup(lesson)),
        Route("/learn/{jid}/module/{mid}", needs_setup(module_page)),
        Route("/learn/{jid}/exam/{eid}", needs_setup(take_exam), methods=["GET", "POST"]),
        Route("/learn/{jid}/do/{action}", needs_setup(journey_action), methods=["POST"]),
        Route("/learn/{jid}/practice", needs_setup(practice), methods=["GET", "POST"]),
        Route("/learn/{jid}/lesson/{lid}/done", needs_setup(lesson_done), methods=["POST"]),
        Route("/learn/{jid}/task/{rid}/evidence", needs_setup(add_evidence), methods=["POST"]),
        Route("/learn/{jid}/task/{rid}/git", needs_setup(add_git), methods=["POST"]),
        Route("/learn/{jid}/task/{rid}/writeup", needs_setup(save_writeup), methods=["POST"]),
        Route("/learn/{jid}/task/{rid}/quiz", needs_setup(quiz), methods=["GET", "POST"]),
        Route("/milestones", needs_setup(milestones)),
        Route("/milestones/{jid}/save", needs_setup(save_milestone), methods=["POST"]),
        Route("/milestones/{jid}/export", needs_setup(export_progress)),
        Route("/milestones/{jid}/files", needs_setup(file_pack)),
        Route("/milestones/{jid}/record", needs_setup(learning_record)),
        Route("/races", needs_setup(races_page)),
        Route("/races/new", needs_setup(race_new), methods=["POST"]),
        Route("/races/join", needs_setup(race_join), methods=["POST"]),
        Route("/races/{rid}", needs_setup(race_page)),
        Route("/races/{rid}/{action}", needs_setup(race_action), methods=["GET", "POST"]),
        Route("/edit/new", needs_setup(edit_new), methods=["GET", "POST"]),
        Route("/edit/{cid}", needs_setup(edit_course), methods=["GET", "POST"]),
        Route("/edit/{cid}/lesson/{lid}", needs_setup(edit_lesson)),
        Route("/edit/{cid}/lesson/{lid}/media", needs_setup(edit_lesson_media), methods=["POST"]),
        Route("/edit/{cid}/image", needs_setup(edit_course_image), methods=["POST"]),
        Route("/edit/{cid}/yaml", needs_setup(edit_yaml), methods=["GET", "POST"]),
        Route("/edit/{cid}/preview", needs_setup(lesson_preview), methods=["POST"]),
        Route("/people", needs_setup(people)),
        Route("/people/card", needs_setup(my_card)),
        Route("/people/add", needs_setup(add_person), methods=["POST"]),
        Route("/link", open_link),
        Route("/people/add-learner", needs_setup(add_person_from_progress), methods=["POST"]),
        Route("/people/{pid}", needs_setup(edit_person), methods=["POST"]),
        Route("/open", needs_setup(open_file), methods=["GET", "POST"]),
        Route("/review/{learner}/{journey}", needs_setup(review), methods=["GET", "POST"]),
        Route("/review/{learner}/{journey}/exam/{rid}", needs_setup(make_exam_page), methods=["GET", "POST"]),
        Route("/files/{sha}", needs_setup(received_file)),
        Route("/outbox/{name}", needs_setup(outbox)),
        Route("/settings", needs_setup(settings), methods=["GET", "POST"]),
        Route("/quit", quit_app, methods=["POST"]),
        Route("/theme", set_theme, methods=["POST"]),
        Route("/tour/done", needs_setup(tour_done), methods=["POST"]),
        Route("/tour/again", needs_setup(tour_again), methods=["POST"]),
        Route("/ping", ping),
        Route("/updates/setting", needs_setup(update_setting), methods=["POST"]),
        Route("/updates/check", needs_setup(update_check), methods=["POST"]),
        Route("/updates/install", needs_setup(update_install), methods=["POST"]),
        Route("/updates/restart", needs_setup(update_restart), methods=["POST"]),
        Route("/settings/ai", needs_setup(ai_settings), methods=["POST"]),
        Route("/settings/backup", needs_setup(backup), methods=["POST"]),
        Route("/settings/restore", needs_setup(restore), methods=["POST"]),
        Mount("/static", StaticFiles(directory=HERE / "static"), name="static"),
    ]
    return Starlette(routes=routes)
