"""Light, view-only previews of Word (.docx), PowerPoint (.pptx) and Excel (.xlsx) files.

These files are zip folders of XML. inPace reads the text, headings, lists, tables, slides and pictures with
Python's own zipfile and XML tools, so it needs no extra libraries and works the same on Android. It doesn't try
to look exactly like Office: for that, "Open the file" opens it in the app you have.
"""
from __future__ import annotations

import base64
import html
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
R_ID = "{%s}id" % NS["r"]
R_EMBED = "{%s}embed" % NS["r"]
MAX_PART = 30_000_000      # never read a part bigger than this (a broken or hostile file)
MAX_PICTURE = 2_000_000    # pictures bigger than this are left out of the preview
MAX_PICTURES = 40
MAX_ROWS, MAX_COLS = 500, 40
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".bmp": "image/bmp", ".svg": "image/svg+xml"}
e = html.escape


class OfficeProblem(Exception):
    pass


class _Doc:
    def __init__(self, path: Path):
        try:
            self.z = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError):
            raise OfficeProblem("This file couldn't be opened. It may be damaged, or saved in an older Office format.")
        self.pictures = 0

    def xml(self, name: str):
        try:
            info = self.z.getinfo(name)
        except KeyError:
            return None
        if info.file_size > MAX_PART:
            raise OfficeProblem("This file is too big to preview.")
        data = self.z.read(name)
        if b"<!DOCTYPE" in data[:2000] or b"<!ENTITY" in data[:5000]:
            raise OfficeProblem("This file couldn't be opened safely.")
        try:
            return ET.fromstring(data)
        except ET.ParseError:
            raise OfficeProblem("This file couldn't be read. It may be damaged.")

    def rels(self, part: str) -> dict[str, str]:
        """Relationship id -> target path, for a part like word/document.xml."""
        folder, name = part.rsplit("/", 1) if "/" in part else ("", part)
        root = self.xml(f"{folder}/_rels/{name}.rels" if folder else f"_rels/{name}.rels")
        out = {}
        for r in (root if root is not None else []):
            target = r.get("Target", "")
            if r.get("TargetMode") == "External":
                continue
            parts = (folder.split("/") if folder and not target.startswith("/") else []) + target.lstrip("/").split("/")
            clean: list[str] = []
            for p in parts:
                if p == "..":
                    if clean:
                        clean.pop()
                elif p and p != ".":
                    clean.append(p)
            out[r.get("Id", "")] = "/".join(clean)
        return out

    def picture(self, name: str, alt: str = "") -> str:
        ext = Path(name).suffix.lower()
        if ext not in IMAGE_TYPES or ext == ".svg" or self.pictures >= MAX_PICTURES:
            return ""
        try:
            info = self.z.getinfo(name)
        except KeyError:
            return ""
        if info.file_size > MAX_PICTURE:
            return ""
        self.pictures += 1
        data = base64.b64encode(self.z.read(name)).decode()
        return f'<img src="data:{IMAGE_TYPES[ext]};base64,{data}" alt="{e(alt)}" loading="lazy">'


# ---- Word ----------------------------------------------------------------------------------------------------

def _w(tag: str) -> str:
    return "{%s}%s" % (NS["w"], tag)


def _runs(d: _Doc, p, rels: dict) -> str:
    out = []
    for node in p.iter():
        if node.tag == _w("r"):
            text = "".join((t.text or "") if t.tag == _w("t") else "\t" if t.tag == _w("tab") else "\n" if t.tag in (_w("br"), _w("cr")) else ""
                           for t in node)
            if not text:
                continue
            rpr = node.find("w:rPr", NS)
            s = e(text).replace("\n", "<br>")
            if rpr is not None:
                if rpr.find("w:b", NS) is not None and rpr.find("w:b", NS).get(_w("val"), "true") not in ("0", "false"):
                    s = f"<b>{s}</b>"
                if rpr.find("w:i", NS) is not None and rpr.find("w:i", NS).get(_w("val"), "true") not in ("0", "false"):
                    s = f"<i>{s}</i>"
                if rpr.find("w:u", NS) is not None and rpr.find("w:u", NS).get(_w("val"), "single") != "none":
                    s = f"<u>{s}</u>"
            out.append(s)
        elif node.tag == "{%s}blip" % NS["a"]:
            target = rels.get(node.get(R_EMBED, ""))
            if target:
                out.append(d.picture(target))
    return "".join(out)


def docx_html(path: Path) -> str:
    d = _Doc(Path(path))
    body = d.xml("word/document.xml")
    if body is None:
        raise OfficeProblem("This doesn't look like a Word document.")
    rels = d.rels("word/document.xml")
    out: list[str] = []
    in_list = False

    def para(p) -> None:
        nonlocal in_list
        ppr = p.find("w:pPr", NS)
        style = ""
        is_list = False
        if ppr is not None:
            st = ppr.find("w:pStyle", NS)
            style = (st.get(_w("val"), "") if st is not None else "").lower()
            is_list = ppr.find("w:numPr", NS) is not None or "list" in style
        content = _runs(d, p, rels)
        if is_list:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{content}</li>")
            return
        if in_list:
            out.append("</ul>")
            in_list = False
        if not content.strip():
            return
        m = re.match(r"(heading|title|subtitle)\s*(\d)?", style)
        if m:
            level = 1 if m.group(1) == "title" else 2 if m.group(1) == "subtitle" else min(int(m.group(2) or 1) + 1, 6)
            out.append(f"<h{level}>{content}</h{level}>")
        else:
            out.append(f"<p>{content}</p>")

    def table(t) -> None:
        rows = []
        for tr in t.findall("w:tr", NS)[:MAX_ROWS]:
            cells = []
            for tc in tr.findall("w:tc", NS)[:MAX_COLS]:
                cells.append("<td>" + "<br>".join(_runs(d, p, rels) for p in tc.findall("w:p", NS)) + "</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        out.append('<div class="office-table"><table>' + "".join(rows) + "</table></div>")

    for node in body.find("w:body", NS) if body.find("w:body", NS) is not None else []:
        if node.tag == _w("p"):
            para(node)
        elif node.tag == _w("tbl"):
            if in_list:
                out.append("</ul>")
                in_list = False
            table(node)
    if in_list:
        out.append("</ul>")
    return "".join(out) or '<p class="muted">(empty)</p>'


# ---- PowerPoint ------------------------------------------------------------------------------------------------

def _a(tag: str) -> str:
    return "{%s}%s" % (NS["a"], tag)


def pptx_html(path: Path) -> str:
    d = _Doc(Path(path))
    pres = d.xml("ppt/presentation.xml")
    if pres is None:
        raise OfficeProblem("This doesn't look like a PowerPoint file.")
    prel = d.rels("ppt/presentation.xml")
    slides = [prel[s.get(R_ID)] for s in pres.iterfind("p:sldIdLst/p:sldId", NS) if s.get(R_ID) in prel]
    out = []
    for n, part in enumerate(slides[:300], start=1):
        root = d.xml(part)
        if root is None:
            continue
        rels = d.rels(part)
        title, blocks = "", []
        for sp in root.iter():
            if sp.tag == "{%s}sp" % NS["p"]:
                ph = sp.find(".//p:nvPr/p:ph", NS)
                is_title = ph is not None and ph.get("type") in ("title", "ctrTitle")
                paras = []
                for p in sp.iterfind(".//a:p", NS):
                    text = "".join((t.text or "") for t in p.iter(_a("t"))).strip()
                    if not text:
                        continue
                    ppr = p.find("a:pPr", NS)
                    level = int(ppr.get("lvl", "0")) if ppr is not None and (ppr.get("lvl") or "0").isdigit() else 0
                    paras.append((level, text))
                if is_title and paras and not title:
                    title = " ".join(t for _, t in paras)
                elif paras:
                    items = "".join(f'<li class="lvl{min(lvl, 4)}">{e(t)}</li>' for lvl, t in paras)
                    blocks.append(f"<ul>{items}</ul>")
            elif sp.tag == "{%s}pic" % NS["p"]:
                blip = sp.find(".//a:blip", NS)
                target = rels.get(blip.get(R_EMBED, "")) if blip is not None else None
                if target:
                    blocks.append(d.picture(target, title))
        out.append(f'<section class="office-slide"><p class="office-slide-n">{n}</p>'
                   + (f"<h3>{e(title)}</h3>" if title else "") + "".join(blocks) + "</section>")
    return "".join(out) or '<p class="muted">(no slides)</p>'


# ---- Excel -----------------------------------------------------------------------------------------------------

def _s(tag: str) -> str:
    return "{%s}%s" % (NS["s"], tag)


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref or "A").group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _col_name(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def xlsx_html(path: Path) -> str:
    d = _Doc(Path(path))
    wb = d.xml("xl/workbook.xml")
    if wb is None:
        raise OfficeProblem("This doesn't look like an Excel file.")
    wrel = d.rels("xl/workbook.xml")
    shared = []
    sst = d.xml("xl/sharedStrings.xml")
    if sst is not None:
        for si in sst.iterfind("s:si", NS):
            shared.append("".join((t.text or "") for t in si.iter(_s("t"))))
    sheets = [(s.get("name", "Sheet"), wrel.get(s.get(R_ID), "")) for s in wb.iterfind("s:sheets/s:sheet", NS)]
    out = []
    for i, (name, part) in enumerate(sheets[:30]):
        root = d.xml(part) if part else None
        if root is None:
            continue
        grid: dict[int, dict[int, str]] = {}
        width = 0
        cut = False
        for r_i, row in enumerate(root.iterfind("s:sheetData/s:row", NS)):
            rnum = int(row.get("r", r_i + 1)) - 1
            if rnum >= MAX_ROWS:
                cut = True
                break
            for c in row.iterfind("s:c", NS):
                col = _col(c.get("r", "A"))
                if col >= MAX_COLS:
                    cut = True
                    continue
                t, v = c.get("t", "n"), c.find("s:v", NS)
                if t == "s" and v is not None and (v.text or "").isdigit():
                    val = shared[int(v.text)] if int(v.text) < len(shared) else ""
                elif t == "inlineStr":
                    val = "".join((x.text or "") for x in c.iter(_s("t")))
                elif t == "b":
                    val = "TRUE" if (v.text if v is not None else "") == "1" else "FALSE"
                else:
                    val = v.text if v is not None and v.text else ""
                    if t == "n" and re.fullmatch(r"-?\d+\.\d{10,}", val):
                        val = f"{float(val):.6g}"  # 0.30000000000000004 -> 0.3
                if val != "":
                    grid.setdefault(rnum, {})[col] = val
                    width = max(width, col + 1)
        if not grid:
            body = '<p class="muted small">(empty)</p>'
        else:
            head = "<tr><th></th>" + "".join(f"<th>{_col_name(c)}</th>" for c in range(width)) + "</tr>"
            rows = []
            for r in range(max(grid) + 1):
                cells = grid.get(r, {})
                rows.append(f"<tr><th>{r + 1}</th>" + "".join(
                    f'<td{" class=num" if re.fullmatch(r"-?[0-9.,%]+", cells.get(c, "")) else ""}>{e(cells.get(c, ""))}</td>'
                    for c in range(width)) + "</tr>")
            body = '<div class="office-table"><table>' + head + "".join(rows) + "</table></div>"
            if cut:
                body += f'<p class="muted small">Showing the first {MAX_ROWS} rows and {MAX_COLS} columns.</p>'
        out.append(f'<details class="office-sheet"{" open" if i == 0 else ""}><summary>{e(name)}</summary>{body}</details>')
    return "".join(out) or '<p class="muted">(no sheets)</p>'


# ---- one entry point, with a small cache -------------------------------------------------------------------------

_CACHE: dict[tuple[str, float], str] = {}


def preview(path: Path) -> str:
    """HTML for a .docx, .pptx or .xlsx file. Raises OfficeProblem with a message for people."""
    path = Path(path)
    key = (str(path), path.stat().st_mtime)
    if key in _CACHE:
        return _CACHE[key]
    ext = path.suffix.lower()
    if ext == ".docx":
        out = docx_html(path)
    elif ext == ".pptx":
        out = pptx_html(path)
    elif ext in (".xlsx", ".xlsm"):
        out = xlsx_html(path)
    else:
        raise OfficeProblem("inPace can show .docx, .pptx and .xlsx files.")
    if len(_CACHE) > 20:
        _CACHE.clear()
    _CACHE[key] = out
    return out
