"""Drawings for Tempo's island: 14 kinds of plants and 8 animal friends.

Same comic-book style as Tempo: thick black outlines, flat colours, one shade and one shine.
Every plant is drawn in a 120 x 160 box with its foot at (60, 150). Every friend is drawn in an
80 x 80 box standing on y = 76. The functions return SVG pieces (no <svg> around them), so the
island can place, size and stack them freely.
"""
from __future__ import annotations

import math

INK = "#111111"


def _o(w: float = 3) -> str:
    return f'stroke="{INK}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"'


O = _o(3)
O2 = _o(2)


def _crown(circles, fill, shade=(), shine=(), shade_fill=None, shine_fill="#fff", shine_op=".45") -> str:
    """Overlapping circles with one outline around them all: ink first (wider), colour on top."""
    ink = "".join(f'<circle cx="{x}" cy="{y}" r="{r + 3}" fill="{INK}"/>' for x, y, r in circles)
    body = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/>' for x, y, r in circles)
    sh = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{shade_fill}"/>' for x, y, r in shade) if shade_fill else ""
    hi = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{shine_fill}" opacity="{shine_op}"/>' for x, y, r in shine)
    return ink + body + sh + hi


def _tube(d: str, fill: str, w: float) -> str:
    """A rounded stem or branch with an outline."""
    return (f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{w + 6}" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="{d}" fill="none" stroke="{fill}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>')


def _trunk(x0: float, x1: float, top: float, fill: str = "#8B5A2B", dark: str = "#6B4220") -> str:
    """A trunk that is wider at the foot, with a little root flare."""
    return (f'<path d="M{60 - x0 - 6} 150 Q{60 - x0} 146 {60 - x0} 136 L{60 - x1} {top} H{60 + x1} L{60 + x0} 136 '
            f'Q{60 + x0} 146 {60 + x0 + 6} 150 Z" fill="{fill}" {O}/>'
            f'<path d="M{60 + x1 - 3} {top + 8} L{60 + x0 - 4} 140" stroke="{dark}" stroke-width="3" stroke-linecap="round"/>')


def _spark(x: float, y: float, r: float, fill: str = "#fff") -> str:
    return (f'<path d="M{x} {y - r} Q{x + r * .22} {y - r * .22} {x + r} {y} Q{x + r * .22} {y + r * .22} {x} {y + r} '
            f'Q{x - r * .22} {y + r * .22} {x - r} {y} Q{x - r * .22} {y - r * .22} {x} {y - r} Z" fill="{fill}" {O2}/>')


def _flower5(x: float, y: float, r: float, petal: str, mid: str = "#FFD43B") -> str:
    out = ""
    for i in range(5):
        a = -math.pi / 2 + i * 2 * math.pi / 5
        out += f'<circle cx="{x + r * math.cos(a):.1f}" cy="{y + r * math.sin(a):.1f}" r="{r * .72:.1f}" fill="{petal}" {O2}/>'
    return out + f'<circle cx="{x}" cy="{y}" r="{r * .55:.1f}" fill="{mid}" {O2}/>'


# ---- plants ------------------------------------------------------------------------------------------

def oak(bloom: bool) -> str:
    s = (_trunk(9, 7, 92)
         + _tube("M60 104 L44 88 M61 98 L76 84", "#8B5A2B", 5)
         + _crown([(60, 64, 32), (32, 80, 22), (88, 80, 22), (42, 52, 22), (78, 50, 22), (60, 36, 20)], "#4CAF50",
                  shade=[(46, 90, 12), (74, 92, 12), (60, 82, 14)], shade_fill="#3B8F3F",
                  shine=[(44, 46, 9), (62, 30, 6), (80, 46, 5)]))
    if bloom:
        for x, y in ((40, 84), (82, 82), (62, 96), (52, 62)):
            s += (f'<ellipse cx="{x}" cy="{y + 3}" rx="4.6" ry="5.6" fill="#B87333" {O2}/>'
                  f'<path d="M{x - 5} {y} q5 -6 10 0 z" fill="#7A4A1E" {O2}/>')
    return s


def pine(bloom: bool) -> str:
    s = _trunk(6, 5, 124, "#7A4A1E", "#5A3416")
    for (w, top, bot) in ((44, 88, 134), (36, 58, 104), (28, 26, 74)):
        s += (f'<path d="M{60 - w} {bot} Q60 {bot + 7} {60 + w} {bot} L60 {top} Z" fill="#2E7D4F" {O}/>'
              f'<path d="M60 {top + 6} L{60 - w + 10} {bot - 2} Q{60 - w / 2} {bot + 2} 60 {bot + 3} Z" fill="#43A06A" opacity=".9"/>')
    if bloom:
        for x, y in ((40, 124), (78, 98), (50, 70)):
            s += (f'<ellipse cx="{x}" cy="{y}" rx="4.4" ry="6.4" fill="#9C6B3C" {O2}/>'
                  f'<path d="M{x - 3} {y - 2} h6 M{x - 3} {y + 2} h6" stroke="#6B4220" stroke-width="1.6"/>')
        s += _spark(60, 22, 8, "#FFD43B")
    return s


def sunflower(bloom: bool) -> str:
    def head(x, y, r):
        out = ""
        for i in range(14):
            a = i * 2 * math.pi / 14
            px, py = x + r * 1.15 * math.cos(a), y + r * 1.15 * math.sin(a)
            out += (f'<ellipse cx="{px:.1f}" cy="{py:.1f}" rx="{r * .42:.1f}" ry="{r * .8:.1f}" fill="#FFD43B" {O2} '
                    f'transform="rotate({math.degrees(a) + 90:.0f} {px:.1f} {py:.1f})"/>')
        out += f'<circle cx="{x}" cy="{y}" r="{r}" fill="#7A4A1E" {O}/>'
        for i in range(7):
            a = i * 2 * math.pi / 7
            out += f'<circle cx="{x + r * .5 * math.cos(a):.1f}" cy="{y + r * .5 * math.sin(a):.1f}" r="1.6" fill="#4A2A10"/>'
        return out
    s = _tube("M60 150 Q56 110 60 56", "#4CAF50", 6)
    s += (f'<path d="M58 118 Q36 112 30 98 Q46 96 58 112 Z" fill="#5CC46E" {O}/>'
          f'<path d="M60 96 Q82 92 90 78 Q72 76 60 90 Z" fill="#5CC46E" {O}/>')
    if bloom:
        s += _tube("M59 128 Q80 118 88 96", "#4CAF50", 4) + head(88, 92, 9)
    return s + head(60, 46, 15)


def cactus(bloom: bool) -> str:
    g, ink = "#4CAF7A", INK
    s = ""
    for d, w in (("M60 146 V52", 26), ("M48 112 H34 V82", 14), ("M72 100 H88 V68", 14)):
        s += f'<path d="{d}" fill="none" stroke="{ink}" stroke-width="{w + 6}" stroke-linecap="round" stroke-linejoin="round"/>'
    for d, w in (("M60 146 V52", 26), ("M48 112 H34 V82", 14), ("M72 100 H88 V68", 14)):
        s += f'<path d="{d}" fill="none" stroke="{g}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>'
    s += ('<path d="M54 60 V140 M66 60 V140" stroke="#2F8A58" stroke-width="2.4" stroke-linecap="round"/>'
          '<path d="M52 58 q2 -6 6 -8" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".5"/>')
    for x, y in ((50, 72), (70, 80), (50, 100), (70, 118), (34, 92), (88, 78), (58, 130)):
        s += f'<path d="M{x - 2} {y} l-3 -2 M{x + 2} {y} l3 -2" stroke="{ink}" stroke-width="1.4" stroke-linecap="round"/>'
    if bloom:
        s += _flower5(60, 42, 6, "#F06292") + _flower5(88, 60, 4.4, "#FF8FA8")
    return s


def cherry(bloom: bool) -> str:
    s = (_trunk(8, 6, 96, "#5B3A29", "#3E271B")
         + _tube("M60 108 L40 92 M61 100 L82 86 M60 98 V84", "#5B3A29", 4)
         + _crown([(60, 62, 28), (30, 76, 22), (90, 74, 22), (42, 48, 20), (80, 46, 20), (60, 34, 17)], "#F6A5C0",
                  shade=[(44, 86, 11), (76, 86, 11)], shade_fill="#E584A7",
                  shine=[(46, 44, 8), (64, 30, 5)]))
    for x, y in ((36, 66), (56, 54), (78, 62), (66, 78), (48, 76), (88, 74), (60, 40)):
        s += _flower5(x, y, 2.6, "#fff", "#E6007E")
    if bloom:
        for x, y, a in ((20, 112, 30), (96, 118, -20), (34, 134, 60), (84, 140, 10), (104, 96, 45)):
            s += f'<ellipse cx="{x}" cy="{y}" rx="4" ry="2.4" fill="#F6A5C0" {O2} transform="rotate({a} {x} {y})"/>'
    return s


def lemon(bloom: bool) -> str:
    s = (_trunk(8, 6, 100)
         + _crown([(60, 66, 34), (34, 80, 18), (86, 80, 18), (60, 40, 20)], "#3E9A4B",
                  shade=[(52, 88, 14), (74, 86, 12)], shade_fill="#2F7D3B", shine=[(46, 52, 9)]))
    spots = [(42, 72), (76, 62), (62, 88)] + ([(32, 88), (86, 86), (54, 50), (84, 44)] if bloom else [])
    for x, y in spots:
        s += (f'<ellipse cx="{x}" cy="{y}" rx="6.4" ry="5.2" fill="#FFE14D" {O2}/>'
              f'<circle cx="{x - 2}" cy="{y - 1.6}" r="1.4" fill="#fff" opacity=".7"/>')
    if bloom:
        for x, y in ((50, 34), (70, 32), (96, 70)):
            s += _flower5(x, y, 2.6, "#fff")
    return s


def lavender(bloom: bool) -> str:
    s = (f'<path d="M30 150 Q36 128 50 136 Q56 126 66 136 Q78 124 90 150 Z" fill="#8FB27A" {O}/>')
    stems = [(-30, 70), (-18, 50), (-8, 38), (4, 30), (14, 44), (24, 56), (34, 74)]
    if bloom:
        stems += [(-24, 86), (30, 92)]
    for dx, top in stems:
        x = 60 + dx
        s += f'<path d="M{60 + dx * .3:.1f} 140 Q{x - dx * .2:.1f} {(140 + top) / 2:.0f} {x} {top + 24}" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>'
        s += f'<path d="M{60 + dx * .3:.1f} 140 Q{x - dx * .2:.1f} {(140 + top) / 2:.0f} {x} {top + 24}" fill="none" stroke="#6E9A5A" stroke-width="2.4" stroke-linecap="round"/>'
        for k in range(5):
            y = top + k * 6
            s += f'<ellipse cx="{x + (1.5 if k % 2 else -1.5)}" cy="{y}" rx="4" ry="4.6" fill="{"#9B6BD6" if k % 2 else "#B48BE8"}" {O2}/>'
    if bloom:
        for x, y, c in ((98, 40, "#F48FB1"), (22, 58, "#FFD43B")):
            s += (f'<path d="M{x} {y} q-9 -10 -12 -1 q2 7 12 1 z M{x} {y} q9 -10 12 -1 q-2 7 -12 1 z" fill="{c}" {O2}/>'
                  f'<path d="M{x} {y - 4} v8" stroke="{INK}" stroke-width="2.4" stroke-linecap="round"/>')
    return s


def bamboo(bloom: bool) -> str:
    s = ""
    stalks = [(44, 40), (62, 22), (80, 48)] + ([(30, 96)] if bloom else [])
    for x, top in stalks:
        s += f'<rect x="{x - 6}" y="{top}" width="12" height="{150 - top}" rx="6" fill="#7CC24A" {O}/>'
        y = top + 20
        while y < 146:
            s += f'<path d="M{x - 6} {y} h12" stroke="{INK}" stroke-width="2.2"/><path d="M{x - 3} {y - 8} v-6" stroke="#B8E58F" stroke-width="2.4" stroke-linecap="round"/>'
            y += 22
        for k, side in enumerate((-1, 1, -1)):
            ly = top + 12 + k * 26
            if ly > 130:
                break
            lx = x + side * 6
            s += (f'<path d="M{lx} {ly} q{side * 14} -10 {side * 26} -4 q{side * -12} 8 {side * -26} 4 z" fill="#5FAF3D" {O2}/>')
    return s


def palm(bloom: bool) -> str:
    s = _tube("M58 150 Q54 104 66 58", "#B07D45", 13)
    for y in range(70, 146, 12):
        x = 58 + (150 - y) * 0.03 + (5 if y < 100 else 0)
        s += f'<path d="M{x - 6:.0f} {y} l6 4 l6 -4" fill="none" stroke="#7A5428" stroke-width="2" stroke-linecap="round"/>'
    fronds = ["M66 56 Q40 40 16 58", "M66 56 Q44 26 24 30", "M66 56 Q66 22 54 12", "M66 56 Q86 24 104 30",
              "M66 56 Q94 40 112 60", "M66 56 Q86 60 96 84", "M66 56 Q44 62 34 84"]
    for d in fronds:
        s += _tube(d, "#3E9A4B", 7) + f'<path d="{d}" fill="none" stroke="#2F7D3B" stroke-width="1.6"/>'
    dates = [(58, 70), (74, 72)] + ([(50, 66), (82, 66), (66, 76)] if bloom else [])
    for x, y in dates:
        for dx, dy in ((0, 0), (5, 3), (-5, 3), (0, 6)):
            s += f'<ellipse cx="{x + dx}" cy="{y + dy}" rx="3" ry="3.8" fill="#D9792B" {O2}/>'
    return s + f'<circle cx="66" cy="56" r="6" fill="#3E9A4B" {O2}/>'


def olive(bloom: bool) -> str:
    s = (f'<path d="M44 150 Q50 128 46 112 Q42 98 54 92 L60 94 Q70 98 68 112 Q66 124 76 150 Z" fill="#8D7B68" {O}/>'
         f'<path d="M52 140 Q56 124 52 112 M64 104 q4 10 2 22" fill="none" stroke="#6B5D4E" stroke-width="2.4" stroke-linecap="round"/>'
         + _tube("M54 96 L36 82 M64 96 L84 80", "#8D7B68", 5)
         + _crown([(60, 68, 26), (30, 74, 20), (90, 72, 20), (44, 54, 18), (78, 54, 18), (60, 46, 16)], "#9BB87A",
                  shade=[(44, 80, 10), (76, 80, 10)], shade_fill="#7E9C62", shine=[(46, 50, 7), (64, 42, 5)], shine_op=".55"))
    for x, y in ((34, 70), (52, 74), (70, 62), (88, 70), (60, 86)) + (((42, 56), (80, 54), (26, 82)) if bloom else ()):
        s += f'<ellipse cx="{x}" cy="{y}" rx="3.2" ry="4.2" fill="#4B3B5A" {O2}/>'
    return s


def lotus(bloom: bool) -> str:
    s = (f'<ellipse cx="60" cy="140" rx="52" ry="12" fill="#5BB7E0" {O}/>'
         f'<path d="M24 138 q10 -4 20 0 M70 144 q10 -4 20 0" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity=".8"/>'
         f'<path d="M22 136 a14 6 0 1 0 22 -4 l-10 3 z" fill="#4CAF50" {O2}/>'
         f'<path d="M80 142 a14 6 0 1 0 20 -6 l-10 4 z" fill="#4CAF50" {O2}/>')

    def flower(x, y, r):
        out = ""
        for a in (-60, 60, -30, 30, 0):
            out += (f'<path d="M{x} {y} Q{x - r * .5} {y - r * .7} {x} {y - r * 1.4} Q{x + r * .5} {y - r * .7} {x} {y} Z" '
                    f'fill="{"#F48FB1" if abs(a) > 40 else "#F8BBD0"}" {O2} transform="rotate({a} {x} {y})"/>')
        return out + f'<ellipse cx="{x}" cy="{y - 2}" rx="{r * .32:.1f}" ry="{r * .2:.1f}" fill="#FFD43B" {O2}/>'
    s += _tube("M60 138 Q58 118 60 100", "#4CAF50", 4) + flower(60, 104, 26)
    if bloom:
        s += _tube("M84 140 Q90 124 88 110", "#4CAF50", 3) + flower(88, 114, 15)
    else:
        s += (_tube("M84 140 Q90 128 88 118", "#4CAF50", 3) +
              f'<path d="M88 118 Q82 108 88 98 Q94 108 88 118 Z" fill="#F8BBD0" {O2}/>')
    return s


def maple(bloom: bool) -> str:
    s = (_trunk(8, 6, 96, "#6B4220", "#4A2C14")
         + _tube("M60 106 L42 88 M61 100 L80 86", "#6B4220", 4)
         + _crown([(60, 62, 30), (32, 78, 21), (88, 78, 21), (42, 48, 20), (78, 46, 20), (60, 32, 18)], "#F08A24",
                  shade=[(40, 84, 13), (78, 70, 14), (60, 50, 10)], shade_fill="#D9452B", shine=[(46, 42, 8), (68, 30, 5)],
                  shine_fill="#FFD43B", shine_op=".7"))
    if bloom:
        for x, y, a in ((18, 120, 20), (100, 112, -30), (30, 140, 50), (92, 138, 0)):
            s += (f'<path d="M{x} {y - 6} l2 4 4 -1 -2 4 4 2 -4 2 1 4 -5 -2 -5 2 1 -4 -4 -2 4 -2 -2 -4 4 1 z" '
                  f'fill="#D9452B" {O2} transform="rotate({a} {x} {y})"/>')
    return s


def baobab(bloom: bool) -> str:
    s = (f'<path d="M26 150 Q34 140 34 112 Q34 86 44 74 H76 Q86 86 86 112 Q86 140 94 150 Z" fill="#B08A6A" {O}/>'
         f'<path d="M48 82 Q44 110 46 142 M72 84 Q76 112 74 140 M60 90 V138" fill="none" stroke="#8C6A4E" stroke-width="2.4" stroke-linecap="round"/>'
         f'<path d="M40 100 q6 -16 2 -26" fill="none" stroke="#D8B898" stroke-width="3" stroke-linecap="round" opacity=".8"/>'
         + _tube("M48 76 L30 58 M56 74 L50 48 M64 74 L72 48 M72 76 L92 58", "#B08A6A", 6))
    s += _crown([(28, 52, 11), (50, 42, 12), (72, 42, 12), (94, 52, 11), (61, 36, 9)], "#6DAE4F",
                shine=[(48, 38, 4), (70, 38, 4)])
    if bloom:
        for x, y in ((28, 66), (52, 58), (74, 58), (94, 66)):
            s += (f'<path d="M{x} {y - 6} v6" stroke="{INK}" stroke-width="1.6"/>' + _flower5(x, y + 3, 3, "#fff"))
    return s


def golden(bloom: bool) -> str:
    s = (_trunk(9, 7, 94, "#5B3A29", "#3E271B")
         + _tube("M60 104 L42 88 M61 98 L78 84", "#5B3A29", 5)
         + _crown([(60, 62, 32), (32, 78, 22), (88, 78, 22), (42, 50, 21), (78, 48, 21), (60, 34, 19)], "#FFD43B",
                  shade=[(44, 88, 13), (76, 88, 13), (60, 78, 12)], shade_fill="#F2A900",
                  shine=[(44, 44, 9), (64, 28, 6)]))
    for x, y, r in ((26, 40, 6), (98, 52, 7), (60, 14, 6)) + (((14, 92, 5), (108, 100, 5), (82, 24, 4)) if bloom else ()):
        s += _spark(x, y, r)
    return s


# ---- the order matters: it's the order in the collection -----------------------------------------------
PLANTS = {
    "sunflower": sunflower, "oak": oak, "pine": pine, "cactus": cactus, "cherry": cherry, "lemon": lemon,
    "lavender": lavender, "bamboo": bamboo, "palm": palm, "olive": olive, "lotus": lotus, "maple": maple,
    "baobab": baobab, "golden": golden,
}

LEAF = {"sunflower": "#5CC46E", "oak": "#4CAF50", "pine": "#2E7D4F", "cactus": "#4CAF7A", "cherry": "#F6A5C0",
        "lemon": "#3E9A4B", "lavender": "#9B6BD6", "bamboo": "#7CC24A", "palm": "#3E9A4B", "olive": "#9BB87A",
        "lotus": "#F48FB1", "maple": "#F08A24", "baobab": "#6DAE4F", "golden": "#FFD43B"}


def seed() -> str:
    return (f'<path d="M30 150 Q60 128 90 150 Z" fill="#8B5A2B" {O}/>'
            f'<ellipse cx="60" cy="138" rx="6" ry="8" fill="#D9A15A" {O2} transform="rotate(20 60 138)"/>'
            f'<path d="M58 134 q2 -2 4 -1" stroke="#fff" stroke-width="1.6" stroke-linecap="round" opacity=".7"/>')


def sprout(kind: str, g: float) -> str:
    """A sprout between seed and plant; g goes 0..1."""
    h = 14 + 30 * g
    leaf = LEAF.get(kind, "#5CC46E")
    top = 146 - h
    return (f'<path d="M34 150 Q60 136 86 150 Z" fill="#8B5A2B" {O}/>'
            + _tube(f"M60 148 Q58 {148 - h / 2:.0f} 60 {top:.0f}", "#5CC46E", 3.6)
            + f'<path d="M60 {top + 2:.0f} q-16 -10 -24 2 q12 8 24 -2 z" fill="{leaf}" {O2}/>'
            + f'<path d="M60 {top:.0f} q12 -14 24 -6 q-8 12 -24 6 z" fill="{leaf}" {O2}/>')


def plant(kind: str, growth: float = 1.0, bloom: bool = False) -> str:
    """A plant at a stage of growth: seed, sprout, then the plant getting bigger."""
    if growth < 0.12:
        return seed()
    if growth < 0.35:
        return sprout(kind, (growth - 0.12) / 0.23)
    s = 0.45 + 0.55 * (growth - 0.35) / 0.65
    draw = PLANTS.get(kind, oak)
    return f'<g transform="translate({60 - 60 * s:.2f} {150 - 150 * s:.2f}) scale({s:.3f})">{draw(bloom and growth >= 1)}</g>'


def wilted() -> str:
    """Kept for old data only: inPace never lets a plant die."""
    return sprout("oak", 0.3)


# ---- friends ----------------------------------------------------------------------------------------

def _eye(x: float, y: float, r: float = 4.2) -> str:
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" {O2}/><circle cx="{x + .8}" cy="{y + .6}" r="{r * .55:.1f}" fill="{INK}"/>'
            f'<circle cx="{x + 1.8}" cy="{y - .8}" r="1.1" fill="#fff"/>')


def _smile(x: float, y: float, w: float = 5) -> str:
    return f'<path d="M{x - w} {y} Q{x} {y + w * .9} {x + w} {y}" fill="none" stroke="{INK}" stroke-width="2.2" stroke-linecap="round"/>'


def _cheek(x: float, y: float) -> str:
    return f'<ellipse cx="{x}" cy="{y}" rx="3.4" ry="2.2" fill="#FF8FA8" opacity=".85"/>'


def snail() -> str:
    return (f'<path d="M4 76 Q4 64 18 64 H56 Q64 64 64 56" fill="#C9E58A" {O}/>'
            f'<path d="M4 76 H60 Q66 76 66 70 V56" fill="#C9E58A" {O}/>'
            f'<circle cx="64" cy="48" r="11" fill="#C9E58A" {O}/>'
            f'<path d="M60 38 L56 24 M68 38 L72 24" {O2}/><circle cx="56" cy="23" r="3.4" fill="{INK}"/><circle cx="72" cy="23" r="3.4" fill="{INK}"/>'
            f'<circle cx="55" cy="22" r="1" fill="#fff"/><circle cx="71" cy="22" r="1" fill="#fff"/>'
            + _smile(64, 51, 4) + _cheek(58, 52) + _cheek(70, 52)
            + f'<circle cx="34" cy="46" r="22" fill="#F2A65A" {O}/>'
            f'<path d="M34 46 m-2 0 a4 4 0 1 1 6 2 a9 9 0 1 1 -12 -6 a14 14 0 1 1 16 20" fill="none" stroke="#B5651D" stroke-width="3" stroke-linecap="round"/>'
            f'<path d="M20 34 q6 -8 14 -9" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".5"/>')


def sparrow() -> str:
    return (f'<path d="M14 50 L2 38 L6 54 Z" fill="#8A5A34" {O2}/>'
            f'<ellipse cx="38" cy="50" rx="26" ry="22" fill="#B07A4A" {O}/>'
            f'<path d="M30 70 Q42 58 58 64 Q56 72 38 72 Z" fill="#F6E2C0" {O2}/>'
            f'<path d="M20 48 Q34 40 44 54 Q30 62 20 48 Z" fill="#8A5A34" {O2}/>'
            f'<path d="M62 42 L74 46 L62 50 Z" fill="#FF9F1C" {O2}/>'
            + _eye(54, 40, 4) + _cheek(56, 50)
            + f'<path d="M32 72 v5 M44 72 v5" stroke="#FF9F1C" stroke-width="2.6" stroke-linecap="round"/>'
            f'<path d="M30 30 q6 -6 14 -4" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" opacity=".45"/>')


def frog() -> str:
    return (f'<ellipse cx="40" cy="56" rx="30" ry="20" fill="#6CC24A" {O}/>'
            f'<ellipse cx="40" cy="64" rx="18" ry="10" fill="#C9EBA8"/>'
            f'<circle cx="26" cy="34" r="10" fill="#6CC24A" {O}/><circle cx="54" cy="34" r="10" fill="#6CC24A" {O}/>'
            + _eye(26, 33, 6) + _eye(54, 33, 6)
            + f'<path d="M24 54 Q40 66 56 54" fill="none" stroke="{INK}" stroke-width="2.4" stroke-linecap="round"/>'
            + _cheek(20, 52) + _cheek(60, 52)
            + f'<path d="M14 72 q6 -8 14 -2 M66 72 q-6 -8 -14 -2" fill="#6CC24A" {O2}/>')


def bee() -> str:
    return (f'<ellipse cx="30" cy="22" rx="12" ry="9" fill="#EAF6FB" {O2} opacity=".95"/>'
            f'<ellipse cx="48" cy="20" rx="12" ry="9" fill="#EAF6FB" {O2} opacity=".95"/>'
            f'<path d="M66 50 l10 2 l-10 3" fill="{INK}"/>'
            f'<ellipse cx="40" cy="48" rx="26" ry="20" fill="#FFD43B" {O}/>'
            f'<path d="M34 29 Q28 48 34 67 M46 29 Q52 48 46 67" fill="none" stroke="{INK}" stroke-width="6"/>'
            f'<circle cx="22" cy="44" r="13" fill="#FFD43B" {O}/>'
            + _eye(18, 41, 4) + _smile(19, 50, 3.6) + _cheek(27, 48)
            + f'<path d="M14 32 Q8 20 4 22 M20 31 Q20 18 14 16" fill="none" {O2}/>')


def owl() -> str:
    return (f'<path d="M14 24 L20 8 L28 20 Z M66 24 L60 8 L52 20 Z" fill="#8C7A6B" {O}/>'
            f'<ellipse cx="40" cy="46" rx="28" ry="30" fill="#8C7A6B" {O}/>'
            f'<ellipse cx="40" cy="58" rx="16" ry="16" fill="#E8DCCB"/>'
            f'<path d="M32 54 l3 3 3 -3 M42 54 l3 3 3 -3 M37 62 l3 3 3 -3" fill="none" stroke="#B9A48C" stroke-width="2" stroke-linecap="round"/>'
            f'<circle cx="28" cy="36" r="11" fill="#fff" {O2}/><circle cx="52" cy="36" r="11" fill="#fff" {O2}/>'
            f'<circle cx="29" cy="37" r="5" fill="{INK}"/><circle cx="51" cy="37" r="5" fill="{INK}"/>'
            f'<circle cx="31" cy="35" r="1.6" fill="#fff"/><circle cx="53" cy="35" r="1.6" fill="#fff"/>'
            f'<circle cx="28" cy="36" r="12.5" fill="none" stroke="{INK}" stroke-width="2.4"/>'
            f'<circle cx="52" cy="36" r="12.5" fill="none" stroke="{INK}" stroke-width="2.4"/>'
            f'<path d="M40 36 h0" {O2}/>'
            f'<path d="M36 44 L40 50 L44 44 Z" fill="#FF9F1C" {O2}/>'
            f'<path d="M26 76 v-4 M32 76 v-4 M48 76 v-4 M54 76 v-4" stroke="#FF9F1C" stroke-width="2.6" stroke-linecap="round"/>')


def butterfly() -> str:
    return (f'<path d="M40 40 Q18 8 8 26 Q4 42 40 44 Z" fill="#F48FB1" {O}/>'
            f'<path d="M40 40 Q62 8 72 26 Q76 42 40 44 Z" fill="#B48BE8" {O}/>'
            f'<path d="M40 46 Q20 70 14 58 Q12 48 40 46 Z" fill="#B48BE8" {O}/>'
            f'<path d="M40 46 Q60 70 66 58 Q68 48 40 46 Z" fill="#F48FB1" {O}/>'
            f'<circle cx="20" cy="26" r="4" fill="#fff" {O2}/><circle cx="60" cy="26" r="4" fill="#fff" {O2}/>'
            f'<ellipse cx="40" cy="48" rx="5" ry="16" fill="#3B2A4A" {O2}/>'
            f'<circle cx="40" cy="30" r="7" fill="#3B2A4A" {O2}/>'
            f'<circle cx="38" cy="29" r="1.5" fill="#fff"/><circle cx="43" cy="29" r="1.5" fill="#fff"/>'
            f'<path d="M37 24 Q32 12 28 12 M43 24 Q48 12 52 12" fill="none" {O2}/>')


def hare() -> str:
    return (f'<path d="M28 30 Q20 2 28 4 Q36 6 36 30 Z" fill="#E8E2D8" {O}/><path d="M28 26 Q24 10 28 10 Q32 12 32 26 Z" fill="#FFB3C6"/>'
            f'<path d="M44 30 Q46 2 54 6 Q60 10 50 32 Z" fill="#E8E2D8" {O}/><path d="M47 28 Q50 12 53 12 Q55 14 49 28 Z" fill="#FFB3C6"/>'
            f'<ellipse cx="38" cy="62" rx="24" ry="15" fill="#E8E2D8" {O}/>'
            f'<circle cx="16" cy="58" r="6" fill="#fff" {O2}/>'
            f'<circle cx="44" cy="42" r="15" fill="#E8E2D8" {O}/>'
            f'<path d="M30 34 Q44 26 58 34" fill="none" stroke="#E6007E" stroke-width="5" stroke-linecap="round"/>'
            + _eye(48, 41, 4) + _cheek(52, 49)
            + f'<path d="M56 46 q2 1 3 0" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>' + _smile(52, 50, 3)
            + f'<ellipse cx="54" cy="74" rx="8" ry="3.6" fill="#E8E2D8" {O2}/><ellipse cx="26" cy="74" rx="8" ry="3.6" fill="#E8E2D8" {O2}/>')


def crab() -> str:
    return (f'<path d="M12 34 Q4 24 12 16 Q18 22 16 28 Q22 24 22 18 Q30 26 22 36 Z" fill="#F2603C" {O}/>'
            f'<path d="M68 34 Q76 24 68 16 Q62 22 64 28 Q58 24 58 18 Q50 26 58 36 Z" fill="#F2603C" {O}/>'
            f'<path d="M22 50 L16 38 M58 50 L64 38" {O}/>'
            f'<path d="M18 64 l-10 8 M22 68 l-8 10 M62 64 l10 8 M58 68 l8 10" {O}/>'
            f'<ellipse cx="40" cy="56" rx="26" ry="17" fill="#F2603C" {O}/>'
            f'<path d="M24 50 q8 -6 18 -6" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" opacity=".5"/>'
            f'<path d="M34 40 V30 M46 40 V30" {O2}/>' + _eye(34, 28, 4) + _eye(46, 28, 4)
            + _smile(40, 58, 6) + _cheek(28, 58) + _cheek(52, 58)
            + f'<circle cx="62" cy="70" r="6" fill="#FFD43B" {O2}/><path d="M62 67 v6" stroke="#D9A90F" stroke-width="2" stroke-linecap="round"/>')


FRIEND_ART = {"snail": snail, "sparrow": sparrow, "frog": frog, "bee": bee, "owl": owl,
              "butterfly": butterfly, "hare": hare, "crab": crab}
