"""Highlights and notes saved inside the PDF itself, the way GNOME's PDF reader (Evince) and other readers do.

Each mark is a standard PDF annotation (Highlight, Underline, StrikeOut, Squiggly, or a Text note) with its author,
date, comment and color, and with its own drawing (an appearance stream) so every PDF reader shows it the same way.
Changes are appended to the end of the file (an incremental update), like Evince saves: the rest of the file stays
byte for byte as it was, and the marks already in it keep their object numbers, which is how the reader points at
one of them to change or remove it ("12R" in pdf.js is object 12).

Marks made in another reader are shown and can be edited here too, and marks made here open in any other reader.

A copy of the marks made here is also kept in inPace (a "sidecar"), so a course update that replaces a PDF file
doesn't lose them: missing marks are written back the next time the PDF opens (``restore``).
"""
from __future__ import annotations

import os
import re
import time
import uuid
from pathlib import Path

KINDS = {"highlight": "/Highlight", "underline": "/Underline", "strike": "/StrikeOut", "squiggly": "/Squiggly"}
NOTE_SIZE = 20.0
MAX_TEXT = 20_000


class NoteError(Exception):
    pass


def _color(hex_color: str) -> list[float]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", (hex_color or "").strip())
    h = m.group(1) if m else "ffd84d"
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)]


def _hex(rgb) -> str:
    try:
        return "#" + "".join(f"{max(0, min(255, round(float(c) * 255))):02x}" for c in list(rgb)[:3])
    except (TypeError, ValueError):
        return "#ffd84d"


def _pdf_date(t: float | None = None) -> str:
    return time.strftime("D:%Y%m%d%H%M%SZ", time.gmtime(t or time.time()))


def _clean_quads(quads) -> list[float]:
    """Groups of 8 numbers (x1 y1 x2 y2 x3 y3 x4 y4: top-left, top-right, bottom-left, bottom-right), as PDF wants."""
    try:
        q = [float(x) for x in quads]
    except (TypeError, ValueError):
        raise NoteError("bad quads")
    if not q or len(q) % 8 or len(q) > 8 * 400 or any(abs(x) > 1e6 for x in q):
        raise NoteError("bad quads")
    return [round(x, 3) for x in q]


def _bounds(quads: list[float], pad: float = 1.0) -> list[float]:
    xs, ys = quads[0::2], quads[1::2]
    return [round(min(xs) - pad, 3), round(min(ys) - pad, 3), round(max(xs) + pad, 3), round(max(ys) + pad, 3)]


def _markup_drawing(kind: str, quads: list[float], rgb: list[float]) -> bytes:
    """The PDF drawing commands for a text mark: a filled box (highlight), or a line under, through or wavy under."""
    r, g, b = rgb
    ops = []
    for i in range(0, len(quads), 8):
        x1, y1, x2, y2, x3, y3, x4, y4 = quads[i:i + 8]
        left, right = min(x1, x3), max(x2, x4)
        top, bottom = max(y1, y2), min(y3, y4)
        h = max(top - bottom, 1.0)
        if kind == "highlight":
            ops.append(f"{left:.2f} {bottom:.2f} {right - left:.2f} {h:.2f} re f")
        elif kind == "underline":
            y = bottom + h * 0.06
            ops.append(f"{max(h * 0.07, 0.6):.2f} w {left:.2f} {y:.2f} m {right:.2f} {y:.2f} l S")
        elif kind == "strike":
            y = bottom + h * 0.45
            ops.append(f"{max(h * 0.07, 0.6):.2f} w {left:.2f} {y:.2f} m {right:.2f} {y:.2f} l S")
        else:  # squiggly: a zig-zag under the text
            step, amp, y = max(h / 6, 1.2), max(h / 14, 0.6), bottom + h * 0.06
            pts, x, up = [f"{left:.2f} {y:.2f} m"], left, True
            while x < right:
                x = min(x + step, right)
                pts.append(f"{x:.2f} {y + (amp if up else -amp):.2f} l")
                up = not up
            ops.append(f"{max(h * 0.05, 0.5):.2f} w " + " ".join(pts) + " S")
    paint = f"{r} {g} {b} rg" if kind == "highlight" else f"{r} {g} {b} RG"
    if kind == "highlight":
        return f"q /GS0 gs {paint} {' '.join(ops)} Q".encode()
    return f"q {paint} {' '.join(ops)} Q".encode()


def _note_drawing(rgb: list[float]) -> bytes:
    """A small speech-bubble note icon, NOTE_SIZE wide, for readers that draw a note's own appearance."""
    r, g, b = rgb
    s = NOTE_SIZE
    return (f"q {r} {g} {b} rg 0.2 0.2 0.2 RG 1 w 1 {s * 0.25:.1f} {s - 2:.1f} {s * 0.7:.1f} re B "
            f"{s * 0.25:.1f} {s * 0.25:.1f} m {s * 0.2:.1f} 1 l {s * 0.45:.1f} {s * 0.25:.1f} l f "
            f"0.2 0.2 0.2 RG 1.2 w 4 {s * 0.7:.1f} m {s - 4:.1f} {s * 0.7:.1f} l S 4 {s * 0.5:.1f} m {s - 6:.1f} {s * 0.5:.1f} l S Q").encode()


class _Update:
    """One incremental update: only the objects that change or are new get written, after the end of the file,
    with a cross-reference stream that points back to the previous one (/Prev). The original bytes stay as
    they are, so this is fast even for big books, and other readers see a normal, valid PDF."""

    def __init__(self, path: Path):
        from pypdf import PdfReader
        self.path = path
        try:
            self.r = PdfReader(str(path))
        except Exception as e:
            raise NoteError(f"can't open: {e}")
        if self.r.is_encrypted:
            raise NoteError("encrypted")
        self.next = int(self.r.trailer.get("/Size", 0))
        self.objs: dict[int, tuple[int, object]] = {}

    def page(self, n: int):
        if not 1 <= n <= len(self.r.pages):
            raise NoteError("bad page")
        return self.r.pages[n - 1]

    def new(self, obj):
        from pypdf.generic import IndirectObject
        num, self.next = self.next, self.next + 1
        self.objs[num] = (0, obj)
        return IndirectObject(num, 0, self.r)

    def changed(self, ref, obj) -> None:
        self.objs[ref.idnum] = (ref.generation, obj)

    def annots(self, page_obj):
        """The page's list of annotations, ready to change (and marked as changed)."""
        from pypdf.generic import ArrayObject, NameObject
        raw = page_obj.get("/Annots")
        if raw is None:
            arr = ArrayObject()
            page_obj[NameObject("/Annots")] = arr
            self.changed(page_obj.indirect_reference, page_obj)
        elif hasattr(raw, "idnum"):
            arr = raw.get_object()
            self.changed(raw, arr)
        else:
            arr = raw
            self.changed(page_obj.indirect_reference, page_obj)
        return arr

    def save(self) -> None:
        import io
        import struct
        import zlib
        from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, StreamObject
        data = self.path.read_bytes()
        m = list(re.finditer(rb"startxref\s+(\d+)", data[-4096:]))
        if not m:
            raise NoteError("no startxref")
        prev = int(m[-1].group(1))
        size0 = len(data)
        out = io.BytesIO()
        if not data.endswith(b"\n"):
            out.write(b"\n")
        offsets: dict[int, tuple[int, int]] = {}
        for num in sorted(self.objs):
            gen, obj = self.objs[num]
            offsets[num] = (size0 + out.tell(), gen)
            out.write(f"{num} {gen} obj\n".encode())
            obj.write_to_stream(out)
            out.write(b"\nendobj\n")
        xref_num = self.next
        xref_at = size0 + out.tell()
        offsets[xref_num] = (xref_at, 0)
        nums = sorted(offsets)
        index, rows, run_start, last = [], b"", None, None
        for n in nums:
            if run_start is None or n != last + 1:
                if run_start is not None:
                    index += [run_start, last - run_start + 1]
                run_start = n
            last = n
            off, gen = offsets[n]
            rows += struct.pack(">BIH", 1, off, gen)
        index += [run_start, last - run_start + 1]
        x = StreamObject()
        x[NameObject("/Type")] = NameObject("/XRef")
        x[NameObject("/Size")] = NumberObject(max(xref_num + 1, int(self.r.trailer.get("/Size", 0))))
        x[NameObject("/W")] = ArrayObject([NumberObject(1), NumberObject(4), NumberObject(2)])
        x[NameObject("/Index")] = ArrayObject([NumberObject(v) for v in index])
        x[NameObject("/Prev")] = NumberObject(prev)
        for key in ("/Root", "/Info", "/ID"):
            if key in self.r.trailer:
                x[NameObject(key)] = self.r.trailer.raw_get(key)
        x[NameObject("/Filter")] = NameObject("/FlateDecode")
        x._data = zlib.compress(rows)
        out.write(f"{xref_num} 0 obj\n".encode())
        x.write_to_stream(out)
        out.write(f"\nendobj\nstartxref\n{xref_at}\n%%EOF\n".encode())
        with open(self.path, "r+b") as f:
            f.seek(size0)
            try:
                f.write(out.getvalue())
                f.flush()
                os.fsync(f.fileno())
            except Exception:
                f.truncate(size0)
                raise


def _appearance(up: "_Update", rect: list[float], drawing: bytes, multiply: bool):
    from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, NumberObject, StreamObject
    stream = StreamObject()
    stream[NameObject("/Type")] = NameObject("/XObject")
    stream[NameObject("/Subtype")] = NameObject("/Form")
    stream[NameObject("/BBox")] = ArrayObject([FloatObject(v) for v in rect])
    if multiply:  # highlights darken the text under them instead of covering it
        gs = DictionaryObject({NameObject("/Type"): NameObject("/ExtGState"), NameObject("/BM"): NameObject("/Multiply"),
                               NameObject("/CA"): NumberObject(1), NameObject("/ca"): FloatObject(0.6)})
        stream[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/ExtGState"): DictionaryObject({NameObject("/GS0"): gs})})
    stream.set_data(drawing)
    return up.new(stream)


def _build(up: "_Update", mark: dict, page_obj):
    """The annotation dictionary for one mark (see ``add``), as a new object; returns its reference."""
    from pypdf.generic import (ArrayObject, BooleanObject, DictionaryObject, FloatObject, NameObject, NumberObject,
                               TextStringObject)
    rgb = _color(mark.get("color", ""))
    kind = mark["kind"]
    d = DictionaryObject()
    d[NameObject("/Type")] = NameObject("/Annot")
    if kind == "note":
        x, y = (float(v) for v in mark["point"])
        rect = [round(x, 3), round(y - NOTE_SIZE, 3), round(x + NOTE_SIZE, 3), round(y, 3)]
        d[NameObject("/Subtype")] = NameObject("/Text")
        d[NameObject("/Name")] = NameObject("/Comment")
        d[NameObject("/Open")] = BooleanObject(False)
        ap = _appearance(up, [0, 0, NOTE_SIZE, NOTE_SIZE], _note_drawing(rgb), False)
    else:
        quads = _clean_quads(mark["quads"])
        rect = _bounds(quads)
        d[NameObject("/Subtype")] = NameObject(KINDS[kind])
        d[NameObject("/QuadPoints")] = ArrayObject([FloatObject(v) for v in quads])
        ap = _appearance(up, rect, _markup_drawing(kind, quads, rgb), kind == "highlight")
    d[NameObject("/Rect")] = ArrayObject([FloatObject(v) for v in rect])
    d[NameObject("/C")] = ArrayObject([FloatObject(v) for v in rgb])
    d[NameObject("/F")] = NumberObject(4)  # print it too
    d[NameObject("/T")] = TextStringObject(str(mark.get("author") or "")[:200])
    d[NameObject("/Contents")] = TextStringObject(str(mark.get("text") or "")[:MAX_TEXT])
    d[NameObject("/M")] = TextStringObject(mark.get("date") or _pdf_date())
    d[NameObject("/CreationDate")] = TextStringObject(mark.get("created") or mark.get("date") or _pdf_date())
    d[NameObject("/NM")] = TextStringObject(mark["nm"])
    if kind == "highlight":
        d[NameObject("/CA")] = FloatObject(0.6)
    d[NameObject("/AP")] = DictionaryObject({NameObject("/N"): ap})
    if page_obj.indirect_reference is not None:
        d[NameObject("/P")] = page_obj.indirect_reference
    return up.new(d)


def add(path: Path, page: int, mark: dict) -> dict:
    """Add one mark to page ``page`` (1 = first). ``mark``: kind (highlight, underline, strike, squiggly, note),
    quads (PDF points, 8 per line of text) or point ([x, y] of a note's top-left corner), color ("#rrggbb"),
    text (the comment), author. Returns the mark as saved, with its object id ("12R") and unique name (nm)."""
    kind = mark.get("kind")
    if kind not in KINDS and kind != "note":
        raise NoteError("bad kind")
    if kind == "note":
        try:
            pt = [float(v) for v in mark.get("point") or []]
        except (TypeError, ValueError):
            raise NoteError("bad point")
        if len(pt) != 2 or any(abs(v) > 1e6 for v in pt):
            raise NoteError("bad point")
        mark = {**mark, "point": pt}
    else:
        mark = {**mark, "quads": _clean_quads(mark.get("quads"))}
    mark = {**mark, "nm": mark.get("nm") or f"inpace-{uuid.uuid4()}", "date": mark.get("date") or _pdf_date()}
    up = _Update(path)
    p = up.page(page)
    ref = _build(up, mark, p)
    up.annots(p).append(ref)
    up.save()
    saved = {k: v for k, v in mark.items() if k in ("kind", "quads", "point", "color", "text", "author", "nm", "date")}
    saved["page"] = page
    saved["id"] = f"{ref.idnum}R"
    return saved


def _find(up: "_Update", page: int, ann_id: str):
    m = re.fullmatch(r"(\d+)R", ann_id or "")
    if not m:
        raise NoteError("bad id")
    num = int(m.group(1))
    p = up.page(page)
    for i, ref in enumerate(list(p.get("/Annots") or [])):
        if getattr(ref, "idnum", None) == num:
            return p, i, ref
    raise NoteError("not found")


def _kind_of(subtype: str) -> str:
    return {v: k for k, v in KINDS.items()}.get(subtype, "note" if subtype == "/Text" else "")


def edit(path: Path, page: int, ann_id: str, text: str | None = None, color: str | None = None) -> dict:
    """Change a mark's comment and/or color (any reader's mark). Its drawing is made again in the new color."""
    from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, TextStringObject
    up = _Update(path)
    _, _, ref = _find(up, page, ann_id)
    a = ref.get_object()
    kind = _kind_of(str(a.get("/Subtype")))
    if text is not None:
        a[NameObject("/Contents")] = TextStringObject(str(text)[:MAX_TEXT])
    if color is not None and kind:
        rgb = _color(color)
        a[NameObject("/C")] = ArrayObject([FloatObject(v) for v in rgb])
        if kind == "note":
            ap = _appearance(up, [0, 0, NOTE_SIZE, NOTE_SIZE], _note_drawing(rgb), False)
        else:
            quads = _clean_quads(a.get("/QuadPoints") or [])
            ap = _appearance(up, _bounds(quads), _markup_drawing(kind, quads, rgb), kind == "highlight")
        a[NameObject("/AP")] = DictionaryObject({NameObject("/N"): ap})
    a[NameObject("/M")] = TextStringObject(_pdf_date())
    up.changed(ref, a)
    up.save()
    return describe(a, page, ann_id)


def remove(path: Path, page: int, ann_id: str) -> str:
    """Take a mark off the page (and its pop-up, if it has one). Returns its unique name, if it had one."""
    up = _Update(path)
    p, i, ref = _find(up, page, ann_id)
    a = ref.get_object()
    popup = getattr(a.get("/Popup"), "idnum", None) if a.get("/Popup") is not None else None
    arr = up.annots(p)
    del arr[i]
    if popup is not None:
        for j, r in enumerate(list(arr)):
            if getattr(r, "idnum", None) == popup:
                del arr[j]
                break
    up.save()
    return str(a.get("/NM") or "")


def describe(a, page: int, ann_id: str = "") -> dict:
    """One annotation as plain data (for the sidecar and the reader)."""
    kind = _kind_of(str(a.get("/Subtype")))
    out = {"page": page, "kind": kind, "nm": str(a.get("/NM") or ""), "text": str(a.get("/Contents") or ""),
           "author": str(a.get("/T") or ""), "color": _hex(a.get("/C") or [1, 0.85, 0.3]), "date": str(a.get("/M") or "")}
    if ann_id:
        out["id"] = ann_id
    if kind == "note":
        r = [float(v) for v in a.get("/Rect") or [0, 0, 0, 0]]
        out["point"] = [round(r[0], 3), round(max(r[1], r[3]), 3)]
    elif kind:
        out["quads"] = [round(float(v), 3) for v in a.get("/QuadPoints") or []]
    return out


def marks(path: Path) -> list[dict]:
    """Every text mark and note in the PDF, from any reader."""
    from pypdf import PdfReader
    out = []
    try:
        r = PdfReader(str(path))
        for n, p in enumerate(r.pages, 1):
            for ref in p.get("/Annots") or []:
                try:
                    a = ref.get_object()
                except Exception:
                    continue
                if _kind_of(str(a.get("/Subtype"))):
                    out.append(describe(a, n, f"{getattr(ref, 'idnum', 0)}R"))
    except Exception:
        return []
    return out


def restore(path: Path, saved: list[dict]) -> int:
    """Write back marks kept in inPace that the file no longer has (a course update replaced it). Returns how many."""
    have = {m["nm"] for m in marks(path) if m.get("nm")}
    missing = [m for m in saved if m.get("nm") and m["nm"] not in have and m.get("kind")]
    if not missing:
        return 0
    up = _Update(path)
    done = 0
    for m in missing:
        try:
            p = up.page(int(m.get("page") or 0))
            if m["kind"] == "note":
                m = {**m, "point": [float(v) for v in m["point"]]}
            ref = _build(up, m, p)
            up.annots(p).append(ref)
            done += 1
        except (NoteError, KeyError, TypeError, ValueError):
            continue
    if done:
        up.save()
    return done
