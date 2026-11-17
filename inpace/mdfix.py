"""Small additions to the lesson Markdown, so lessons written the GitHub way look right:
bare links become clickable, task lists get checkboxes, "> [!NOTE]" boxes get a style,
and footnotes ([^1] ... [^1]: the note) work. No extra packages: plain markdown-it rules."""
from __future__ import annotations

import html
import re

from markdown_it.token import Token

URL = re.compile(r"""https?://[^\s<>"'`]+[^\s<>"'`.,;:!?)\]}]""")
TASK = re.compile(r"^\[([ xX])\]\s+")
CALLOUT = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*", re.I)
FENCE = re.compile(r"(?ms)^(```|~~~).*?^\1[^\n]*$")
FN_DEF = re.compile(r"(?m)^\[\^([^\]\s]+)\]:[ \t]*(.*(?:\n(?:[ \t]{2,}|\t).*)*)")
FN_REF = re.compile(r"\[\^([^\]\s]+)\](?!:)")
MARK = "⁣fn{}⁣"


def install(md) -> None:
    md.enable("strikethrough")
    md.core.ruler.push("bare_links", _bare_links)
    md.core.ruler.push("task_lists", _task_lists)
    md.core.ruler.push("callouts", _callouts)


def _bare_links(state) -> None:
    for tok in state.tokens:
        if tok.type != "inline" or not tok.children:
            continue
        out, inside = [], 0
        for ch in tok.children:
            if ch.type == "link_open":
                inside += 1
            elif ch.type == "link_close":
                inside -= 1
            if ch.type != "text" or inside or "http" not in ch.content:
                out.append(ch)
                continue
            pos = 0
            for m in URL.finditer(ch.content):
                if m.start() > pos:
                    out.append(_text(ch.content[pos:m.start()]))
                a = Token("link_open", "a", 1)
                a.attrSet("href", m.group(0))
                out += [a, _text(m.group(0)), Token("link_close", "a", -1)]
                pos = m.end()
            if pos < len(ch.content):
                out.append(_text(ch.content[pos:]))
        tok.children = out


def _task_lists(state) -> None:
    toks = state.tokens
    for i, tok in enumerate(toks):
        if tok.type != "inline" or i < 2 or toks[i - 2].type != "list_item_open" or not tok.children:
            continue
        first = tok.children[0]
        m = TASK.match(first.content) if first.type == "text" else None
        if not m:
            continue
        first.content = first.content[m.end():]
        box = Token("html_inline", "", 0)
        box.content = f'<input type="checkbox" disabled{" checked" if m.group(1) != " " else ""}> '
        tok.children.insert(0, box)
        toks[i - 2].attrSet("class", "task-item")


def _callouts(state) -> None:
    toks = state.tokens
    for i, tok in enumerate(toks):
        if tok.type != "blockquote_open" or i + 2 >= len(toks) or toks[i + 2].type != "inline":
            continue
        inline = toks[i + 2]
        kids = inline.children or []
        m = CALLOUT.match(kids[0].content) if kids and kids[0].type == "text" else None
        if not m:
            continue
        kind = m.group(1).lower()
        kids[0].content = kids[0].content[m.end():]
        if not kids[0].content and len(kids) > 1 and kids[1].type in ("softbreak", "hardbreak"):
            del kids[1]
        title = Token("html_inline", "", 0)
        title.content = f'<b class="callout-title">{kind.capitalize()}</b> '
        kids.insert(0, title)
        tok.attrSet("class", f"callout callout-{kind}")


def _text(s: str) -> Token:
    t = Token("text", "", 0)
    t.content = s
    return t


def render(md, src: str) -> str:
    """md.render plus footnotes: [^x] in the text, "[^x]: the note" anywhere. Code blocks are left alone."""
    if "[^" not in src:
        return md.render(src)
    keep: list[str] = []

    def hide(m):
        keep.append(m.group(0))
        return f"⁢code{len(keep) - 1}⁢"
    body = FENCE.sub(hide, src)
    notes: dict[str, str] = {}

    def take(m):
        notes[m.group(1)] = re.sub(r"\n[ \t]+", " ", m.group(2)).strip()
        return ""
    body = FN_DEF.sub(take, body)
    if not notes:
        return md.render(src)
    order: list[str] = []

    def ref(m):
        key = m.group(1)
        if key not in notes:
            return m.group(0)
        if key not in order:
            order.append(key)
        return MARK.format(order.index(key) + 1)
    body = FN_REF.sub(ref, body)
    body = re.sub("⁢code(\\d+)⁢", lambda m: keep[int(m.group(1))], body)
    out = md.render(body)
    for n, key in enumerate(order, 1):
        out = out.replace(MARK.format(n), f'<sup class="fn"><a href="#fn-{n}" id="fnref-{n}">{n}</a></sup>')
    items = "".join(f'<li id="fn-{n}" dir="auto">{md.renderInline(notes[k])} <a href="#fnref-{n}" class="fn-back" '
                    f'aria-label="{html.escape("back")}">↩</a></li>' for n, k in enumerate(order, 1))
    return out + (f'<section class="footnotes"><ol>{items}</ol></section>' if items else "")
