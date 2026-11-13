"""Tempo, the inPace turtle. Slow and steady wins the race.

Drawn as inline SVG in the app's comic-book style: thick black outlines, flat colours and one
soft shadow tone. Tempo is a small traveller: a round green shell with the inPace trail on it,
a scalloped yellow rim, a big friendly head on a real neck, and a pink scarf that blows behind him.
No image files, works offline, sharp at any size.

The parts are separate functions, so the garden island can reuse Tempo's head at a bigger scale.
"""
from __future__ import annotations

import itertools
import math

from markupsafe import Markup

MOODS = ("happy", "cheer", "sleepy", "think", "proud", "oops", "wave", "read", "water", "sad", "love")

INK = "#111111"
SHELL = "#25A06C"
SHELL_DARK = "#17774C"
SHELL_SHADE = "#1C8A5B"
SHELL_LIGHT = "#6FD3A0"
RIM = "#FFD43B"
RIM_DARK = "#D9A90F"
SKIN = "#A8E2B8"
SKIN_DARK = "#7CC796"
SKIN_FAR = "#8DD0A3"
BELLY = "#F6E7A8"
SCARF = "#E6007E"
SCARF_DARK = "#A8005C"
CHEEK = "#FF8FA8"
SKY = "#7FB0F0"

_ids = itertools.count(1)


def _o(w: float = 3.2) -> str:
    return f'stroke="{INK}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"'


O = _o(3.2)
O2 = _o(2.2)


def _star(x: float, y: float, r: float, fill: str) -> str:
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.46
        pts.append(f"{x + rr * math.cos(a):.1f},{y - rr * math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}" {O2}/>'


def _heart(x: float, y: float, s: float, fill: str = SCARF) -> str:
    return (f'<path d="M{x} {y + 6 * s} C{x - 9 * s} {y} {x - 6 * s} {y - 7 * s} {x} {y - 3 * s} '
            f'C{x + 6 * s} {y - 7 * s} {x + 9 * s} {y} {x} {y + 6 * s} Z" fill="{fill}" {O2}/>')


# ---- body ------------------------------------------------------------------------------------------

def _leg(x: float, far: bool = False) -> str:
    """A round stubby leg with a pale foot pad and three little nails."""
    fill = SKIN_FAR if far else SKIN
    y0, w = 98, 13
    return (f'<path d="M{x - w + 1} {y0} C{x - w} {y0 + 14} {x - w - 2} {y0 + 22} {x - w} {y0 + 26} Q{x} {y0 + 31} {x + w} {y0 + 26} '
            f'C{x + w + 2} {y0 + 22} {x + w} {y0 + 14} {x + w - 1} {y0} Z" fill="{fill}" {O}/>'
            f'<path d="M{x - 7} {y0 + 12} q2 4 0 8" fill="none" stroke="{SKIN_DARK}" stroke-width="2.2" stroke-linecap="round"/>'
            f'<path d="M{x - 6} {y0 + 28} l-.5 -3 M{x} {y0 + 28.8} v-3.4 M{x + 6} {y0 + 28} l.5 -3" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>')


def _tail() -> str:
    return f'<path d="M30 98 Q16 100 4 92 Q16 88 30 86 Z" fill="{SKIN}" {O}/>'


def _shell(uid: str, sprout: bool = False) -> str:
    dome = "M22 98 C20 52 52 24 88 24 C124 24 154 52 152 98 Z"
    clip = f"tempo-shell-{uid}"
    out = [f'<clipPath id="{clip}"><path d="{dome}"/></clipPath>',
           f'<path d="{dome}" fill="{SHELL}"/>',
           f'<g clip-path="url(#{clip})">'
           # a soft shadow on the lower half, and a shine on the upper left
           f'<ellipse cx="96" cy="106" rx="80" ry="26" fill="{SHELL_SHADE}"/>'
           f'<path d="M34 72 C38 50 56 36 76 32" fill="none" stroke="{SHELL_LIGHT}" stroke-width="7" stroke-linecap="round" opacity=".85"/>'
           f'<circle cx="32" cy="84" r="3" fill="{SHELL_LIGHT}" opacity=".85"/>'
           # the scutes: one big middle plate and the plates around it
           f'<path d="M66 62 L76 44 H100 L110 62 L100 80 H76 Z" fill="none" stroke="{SHELL_DARK}" stroke-width="3" stroke-linejoin="round"/>'
           f'<path d="M76 44 L68 22 M100 44 L108 22 M66 62 H18 M110 62 H156 M76 80 L64 104 M100 80 L112 104" '
           f'fill="none" stroke="{SHELL_DARK}" stroke-width="3" stroke-linecap="round"/>'
           f'</g>',
           f'<path d="{dome}" fill="none" {O}/>',
           # the inPace trail, like a badge on the middle plate
           f'<path d="M79 71 L88 62 L98 53" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round"/>'
           f'<circle cx="79" cy="71" r="3.6" fill="#fff" {O2}/><circle cx="88" cy="62" r="3.6" fill="#fff" {O2}/>'
           f'<circle cx="98" cy="53" r="4.6" fill="{SCARF}" {O2}/>']
    if sprout:
        out.append(f'<path d="M88 25 q-1 -8 2 -14" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>'
                   f'<path d="M88 25 q-1 -8 2 -14" fill="none" stroke="#3FAE5A" stroke-width="2.4" stroke-linecap="round"/>'
                   f'<path d="M90 13 q-12 -8 -18 2 q10 6 18 -2 z" fill="#5CC46E" {O2}/>'
                   f'<path d="M90 11 q8 -12 18 -6 q-6 10 -18 6 z" fill="#5CC46E" {O2}/>')
    return "".join(out)


def _rim() -> str:
    """The yellow rim under the shell, with round scallops."""
    d = "M16 92 H158 V100"
    x = 158
    for _ in range(7):
        d += f" Q{x - 10.3} {111} {x - 20.6} {100}"
        x -= 20
    d += " Z"
    seams = "".join(f'<path d="M{158 - 20.6 * i:.1f} 96 V100" stroke="{RIM_DARK}" stroke-width="2.4" stroke-linecap="round"/>'
                    for i in range(1, 7))
    return f'<path d="{d}" fill="{RIM}" {O}/>' + seams


def _neck(head_x: float = 0) -> str:
    path = "M138 98 C140 88 146 80 156 72"
    return (f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="27" stroke-linecap="round"/>'
            f'<path d="{path}" fill="none" stroke="{SKIN}" stroke-width="20.6" stroke-linecap="round"/>'
            f'<path d="M136 96 q4 -10 10 -16" fill="none" stroke="{SKIN_DARK}" stroke-width="2.4" stroke-linecap="round"/>')


# ---- head ------------------------------------------------------------------------------------------

HEAD = "M144 52 C144 32 158 22 172 22 C188 22 198 34 198 50 C198 66 188 76 172 76 C158 76 144 70 144 52 Z"
EYES = ((163, 46), (183, 45))


def _eyes(mood: str) -> str:
    (lx, ly), (rx, ry) = EYES
    happy_arc = lambda x, y: (f'<path d="M{x - 6} {y + 2} Q{x} {y - 7} {x + 6} {y + 2}" fill="none" '
                              f'stroke="{INK}" stroke-width="3.2" stroke-linecap="round"/>')
    if mood in ("cheer", "proud", "water"):
        return happy_arc(lx, ly) + happy_arc(rx, ry)
    if mood == "sleepy":
        return "".join(f'<path d="M{x - 6} {y} Q{x} {y + 6} {x + 6} {y}" fill="none" {O2}/>' for x, y in EYES)
    if mood == "love":
        return _heart(lx, ly, 0.9) + _heart(rx, ry, 1.0)
    look = {"think": (-1.5, -3), "oops": (0, 1), "read": (1.5, 3), "sad": (0, 2.5)}.get(mood, (1.5, 0))
    out = ""
    for (x, y), r in zip(EYES, (7, 7.6)):
        out += (f'<ellipse cx="{x}" cy="{y}" rx="{r - 0.6}" ry="{r + 1.2}" fill="#fff" {O2}/>'
                f'<circle cx="{x + look[0]}" cy="{y + 1 + look[1]}" r="{r * 0.6:.1f}" fill="{INK}"/>'
                f'<circle cx="{x + look[0] + 1.6}" cy="{y - 1.4 + look[1]}" r="1.6" fill="#fff"/>')
    if mood == "read":  # eyelids half down, looking at the page
        out += "".join(f'<path d="M{x - 7} {y - 3} Q{x} {y - 8} {x + 7} {y - 3}" fill="{SKIN}" {O2}/>' for x, y in EYES)
    return out


def _brows(mood: str) -> str:
    (lx, ly), (rx, ry) = EYES
    if mood == "think":
        return (f'<path d="M{lx - 6} {ly - 13} L{lx + 5} {ly - 14}" {O2}/>'
                f'<path d="M{rx - 6} {ry - 16} Q{rx} {ry - 20} {rx + 6} {ry - 15}" fill="none" {O2}/>')
    if mood in ("oops", "sad"):
        return (f'<path d="M{lx - 6} {ly - 11} L{lx + 5} {ly - 15}" {O2}/>'
                f'<path d="M{rx - 5} {ry - 15} L{rx + 6} {ry - 11}" {O2}/>')
    if mood in ("happy", "wave", "read"):
        return "".join(f'<path d="M{x - 5} {y - 14} Q{x} {y - 17} {x + 5} {y - 14}" fill="none" {O2}/>' for x, y in EYES)
    return ""


def _mouth(mood: str) -> str:
    x, y = 176, 62
    return {
        "happy": f'<path d="M{x - 6} {y} Q{x} {y + 7} {x + 6} {y}" fill="none" stroke="{INK}" stroke-width="2.8" stroke-linecap="round"/>',
        "wave": f'<path d="M{x - 7} {y - 1} Q{x} {y + 11} {x + 7} {y - 1} Z" fill="{INK}" {O2}/><path d="M{x - 4} {y + 4} q4 3 8 0" fill="#FF6B7D"/>',
        "cheer": f'<path d="M{x - 8} {y - 2} Q{x} {y + 13} {x + 8} {y - 2} Z" fill="{INK}" {O2}/><path d="M{x - 4.5} {y + 5} q4.5 3.5 9 0" fill="#FF6B7D"/>',
        "proud": f'<path d="M{x - 7} {y} Q{x} {y + 7} {x + 7} {y}" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>',
        "water": f'<path d="M{x - 6} {y} Q{x} {y + 7} {x + 6} {y}" fill="none" stroke="{INK}" stroke-width="2.8" stroke-linecap="round"/>',
        "love": f'<path d="M{x - 6} {y} Q{x} {y + 8} {x + 6} {y}" fill="none" stroke="{INK}" stroke-width="2.8" stroke-linecap="round"/>',
        "sleepy": f'<ellipse cx="{x}" cy="{y + 2}" rx="2.8" ry="2.4" fill="{INK}"/>',
        "think": f'<path d="M{x - 5} {y + 2} Q{x} {y} {x + 6} {y + 3}" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round"/>',
        "oops": f'<path d="M{x - 7} {y + 3} q3.5 -4 7 0 q3.5 4 7 0" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round"/>',
        "read": f'<path d="M{x - 4} {y + 1} Q{x} {y + 4} {x + 4} {y + 1}" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round"/>',
        "sad": f'<path d="M{x - 6} {y + 5} Q{x} {y - 1} {x + 6} {y + 5}" fill="none" stroke="{INK}" stroke-width="2.8" stroke-linecap="round"/>',
    }[mood]


def head(mood: str = "happy") -> str:
    """Tempo's head, in the 200 x 144 drawing's coordinates (centre about 172, 49)."""
    cheeks = "" if mood in ("sad",) else (f'<ellipse cx="159" cy="59" rx="5" ry="3.4" fill="{CHEEK}" opacity=".8"/>'
                                         f'<ellipse cx="192" cy="58" rx="4.2" ry="3.2" fill="{CHEEK}" opacity=".8"/>')
    return (f'<path d="{HEAD}" fill="{SKIN}" {O}/>'
            f'<path d="M150 40 C154 30 162 26 170 26" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" opacity=".55"/>'
            f'<circle cx="196" cy="47" r="1.2" fill="{INK}"/>'
            f'{cheeks}{_eyes(mood)}{_brows(mood)}{_mouth(mood)}')


def scarf() -> str:
    """The pink travelling scarf around the neck, its ends blowing back over the shell."""
    return (f'<path d="M150 88 C140 86 132 82 124 84 C118 86 114 82 112 78 C112 88 120 94 130 92 C138 91 144 94 151 92 Z" fill="{SCARF}" {O}/>'
            f'<path d="M124 85 C120 87 116 85 114 82" fill="none" stroke="{SCARF_DARK}" stroke-width="2.4" stroke-linecap="round"/>'
            f'<path d="M144 72 Q158 82 176 74 L178 84 Q158 94 142 82 Z" fill="{SCARF}" {O}/>'
            f'<circle cx="152" cy="80" r="1.6" fill="#fff"/><circle cx="162" cy="83" r="1.6" fill="#fff"/><circle cx="171" cy="80" r="1.6" fill="#fff"/>'
            f'<circle cx="134" cy="88" r="1.5" fill="#fff"/><circle cx="122" cy="88" r="1.3" fill="#fff"/>'
            f'<ellipse cx="149" cy="86" rx="6" ry="5" fill="{SCARF}" {O2}/>')


def _arm_up(motion: bool = True) -> str:
    """The front leg raised in a wave."""
    path = "M150 98 C170 96 196 88 206 62"
    lines = (f'<path d="M213 46 q4 -4 3 -10 M218 58 q5 -2 6 -7" fill="none" stroke="{INK}" stroke-width="2.2" stroke-linecap="round"/>'
             if motion else "")
    return (f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="20" stroke-linecap="round"/>'
            f'<path d="{path}" fill="none" stroke="{SKIN}" stroke-width="13.6" stroke-linecap="round"/>'
            f'<path d="M201 56 l-3 -3 M206 54 l0 -4 M211 57 l3 -3" stroke="{INK}" stroke-width="2.2" stroke-linecap="round"/>'
            + lines)


def _book() -> str:
    """An open book held up in front of Tempo."""
    return (f'<path d="M146 98 C156 98 166 96 172 92" fill="none" stroke="{INK}" stroke-width="18" stroke-linecap="round"/>'
            f'<path d="M146 98 C156 98 166 96 172 92" fill="none" stroke="{SKIN}" stroke-width="11.6" stroke-linecap="round"/>'
            f'<path d="M160 96 L178 82 L204 88 L186 104 Z" fill="{SKY}" {O}/>'
            f'<path d="M164 93 L179 81 L200 86 L184 99 Z" fill="#fff" {O2}/>'
            f'<path d="M179 81 L184 99" {O2}/>'
            f'<path d="M168 92 l8 -6 M171 95 l8 -6 M186 87 l8 2 M185 91 l8 2" stroke="#9AA6B8" stroke-width="1.6" stroke-linecap="round"/>')


def _can() -> str:
    """A yellow watering can, pouring."""
    return (f'<path d="M140 100 C148 96 154 92 158 86" fill="none" stroke="{INK}" stroke-width="18" stroke-linecap="round"/>'
            f'<path d="M140 100 C148 96 154 92 158 86" fill="none" stroke="{SKIN}" stroke-width="11.6" stroke-linecap="round"/>'
            f'<path d="M156 78 h22 l-2 22 h-18 z" fill="{RIM}" {O}/>'
            f'<path d="M160 78 q8 -10 16 0" fill="none" {O}/>'
            f'<path d="M178 86 L192 76 l3 4 L180 92" fill="{RIM}" {O}/>'
            f'<path d="M160 84 h14" stroke="{RIM_DARK}" stroke-width="2.4" stroke-linecap="round"/>'
            f'<path d="M196 84 q2 6 0 8 q-2 -2 0 -8 z M200 90 q2 6 0 8 q-2 -2 0 -8 z M194 96 q2 5 0 7 q-2 -2 0 -7 z" fill="#8EC5FF" stroke="{INK}" stroke-width="1.4"/>')


def _extras(mood: str) -> str:
    if mood == "sleepy":
        z = 'font-family="system-ui,sans-serif" font-weight="900" fill="#fff" paint-order="stroke"'
        return (f'<text x="186" y="20" font-size="16" {z} {O2}>z</text>'
                f'<text x="196" y="8" font-size="11" {z} {O2}>z</text>')
    if mood == "cheer":
        return _star(24, 18, 9, RIM) + _star(128, 12, 6, SKY) + _star(10, 52, 5, SCARF)
    if mood == "proud":
        return (f'<path d="M146 88 l-4 12 h12 l-2 -12" fill="{SKY}" {O2}/>'
                f'<circle cx="149" cy="104" r="9" fill="{RIM}" {O}/>' + _star(149, 104, 5.4, "#fff"))
    if mood == "think":
        return (f'<circle cx="138" cy="20" r="2.6" fill="#fff" {O2}/><circle cx="130" cy="10" r="3.6" fill="#fff" {O2}/>'
                f'<text x="140" y="16" font-family="system-ui,sans-serif" font-weight="900" font-size="18" fill="#fff" {O2} paint-order="stroke">?</text>')
    if mood == "oops":
        return f'<path d="M150 30 q5 8 0 12 q-5 -4 0 -12 z" fill="#8EC5FF" {O2}/>'
    if mood == "sad":
        return f'<path d="M190 56 q4 7 0 10 q-4 -3 0 -10 z" fill="#8EC5FF" {O2}/>'
    if mood == "love":
        return _heart(196, 16, 1.1) + _heart(140, 12, 0.8, "#FF8FA8")
    return ""


def mascot(mood: str = "happy", size: int = 96, label: str = "Tempo the turtle") -> Markup:
    if mood not in MOODS:
        mood = "happy"
    uid = f"{mood}{next(_ids)}"
    arm = mood in ("wave", "cheer")
    holds = mood in ("read", "water")
    front = ""
    if arm:
        front = _arm_up(mood == "wave")
    elif mood == "read":
        front = _book()
    elif mood == "water":
        front = _can()
    svg = f'''<svg class="tempo tempo-{mood}" width="{int(size)}" height="{int(size * 0.721)}" viewBox="-6 -12 226 163" role="img" aria-label="{label}">
<ellipse cx="92" cy="130" rx="76" ry="6" fill="#000" opacity=".14"/>
{_tail()}{_leg(60, far=True)}{_leg(140, far=True) if not (arm or holds) else ""}
{_neck()}
{_rim()}{_shell(uid, sprout=mood == "water")}
{_leg(44)}{_leg(118)}
{scarf()}
{head(mood)}
{front}
{_extras(mood)}
</svg>'''
    return Markup(svg)
