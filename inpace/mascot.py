"""Tempo, the inPace turtle. Slow and steady wins the race.

Drawn as inline SVG in the app's comic-book style: thick black outlines, flat colours,
a yellow shell rim, the inPace logo on the shell, and a pink travelling scarf.
No image files, works offline, sharp at any size.
"""
from __future__ import annotations

import math

from markupsafe import Markup

MOODS = ("happy", "cheer", "sleepy", "think", "proud", "oops", "wave")

INK = "#111111"
SHELL = "#23A36E"
SHELL_DARK = "#167A50"
SHELL_LIGHT = "#5CC995"
RIM = "#FFD43B"
RIM_DARK = "#D9A90F"
SKIN = "#9FDDB4"
SKIN_DARK = "#6FBF8C"
SCARF = "#E6007E"
SCARF_DARK = "#A8005C"
CHEEK = "#FF8FA8"
O = f'stroke="{INK}" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round"'
O2 = f'stroke="{INK}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"'


def _leg(x: float, y: float) -> str:
    """A stubby leg with three toes."""
    return (f'<path d="M{x-10} {y-12} q0 14 -2 16 q12 4 24 0 q-2 -2 -2 -16 z" fill="{SKIN}" {O}/>'
            f'<path d="M{x-7} {y+3} v-3 M{x+1} {y+4} v-4 M{x+9} {y+3} v-3" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>')


def _arm_up() -> str:
    """Front leg raised in a wave, drawn in front of the head."""
    return (f'<path d="M146 98 q8 -16 17 -30 q4 -6 9 -2 q4 4 1 9 q-8 16 -16 30 z" fill="{SKIN}" {O}/>'
            f'<path d="M165 66 l-1 -5 M170 66 l2 -4 M174 70 l3 -2" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>')


def _eyes(mood: str) -> str:
    lx, rx, y = 132, 147, 50
    if mood == "sleepy":
        return (f'<path d="M{lx-6} {y+1} q6 5 12 0" fill="none" {O2}/><path d="M{rx-6} {y+1} q6 5 12 0" fill="none" {O2}/>'
                f'<path d="M{lx-7} {y-6} l5 2 M{rx+7} {y-6} l-5 2" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>')
    if mood in ("cheer", "proud"):
        return (f'<path d="M{lx-6} {y+2} q6 -8 12 0" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>'
                f'<path d="M{rx-6} {y+2} q6 -8 12 0" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>')
    look = {"think": (2, -2), "oops": (0, 1)}.get(mood, (1, 0))
    brows = {
        "think": f'<path d="M{lx-6} {y-11} l11 -2" {O2}/><path d="M{rx-5} {y-14} q6 -3 11 1" fill="none" {O2}/>',
        "oops": f'<path d="M{lx-6} {y-10} l10 -4" {O2}/><path d="M{rx-4} {y-14} l10 4" {O2}/>',
    }.get(mood, f'<path d="M{lx-5} {y-12} q5 -3 10 0" fill="none" {O2}/><path d="M{rx-5} {y-12} q5 -3 10 0" fill="none" {O2}/>')
    eye = ""
    for cx in (lx, rx):
        eye += (f'<ellipse cx="{cx}" cy="{y}" rx="6.2" ry="7.4" fill="#fff" {O2}/>'
                f'<circle cx="{cx + look[0]}" cy="{y + 1 + look[1]}" r="3.6" fill="{INK}"/>'
                f'<circle cx="{cx + look[0] + 1.4}" cy="{y - 0.6 + look[1]}" r="1.3" fill="#fff"/>')
    return eye + brows


def _mouth(mood: str) -> str:
    return {
        "happy": f'<path d="M134 62 q6 6 12 0" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round"/>',
        "wave": f'<path d="M133 61 q7 9 14 0 z" fill="{INK}"/><path d="M136 65 q4 3 8 0" fill="#FF6B7D"/>',
        "cheer": f'<path d="M132 60 q8 13 16 0 z" fill="{INK}" {O2}/><path d="M135.5 65.5 q4.5 4 9 0" fill="#FF6B7D"/>',
        "proud": f'<path d="M133 61 q7 7 14 0" fill="none" stroke="{INK}" stroke-width="2.8" stroke-linecap="round"/>',
        "sleepy": f'<ellipse cx="140" cy="63" rx="2.6" ry="2.2" fill="{INK}"/>',
        "think": f'<path d="M135 63 q5 -2 10 1" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round"/>',
        "oops": f'<path d="M134 65 q6 -6 12 0" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round"/>',
    }[mood]


def _star(x: float, y: float, r: float, fill: str) -> str:
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append(f"{x + rr * math.cos(a):.1f},{y - rr * math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}" {O2}/>'


def _extras(mood: str) -> str:
    if mood == "sleepy":
        return (f'<text x="158" y="28" font-family="system-ui,sans-serif" font-weight="900" font-size="15" fill="#fff" {O2} paint-order="stroke">z</text>'
                f'<text x="167" y="14" font-family="system-ui,sans-serif" font-weight="900" font-size="11" fill="#fff" {O2} paint-order="stroke">z</text>')
    if mood == "cheer":
        return _star(16, 18, 9, RIM) + _star(118, 12, 6, "#7FB0F0") + _star(6, 52, 5, SCARF)
    if mood == "proud":
        return (f'<path d="M62 4 l-6 14 h12 z" fill="{SCARF}" {O2}/><path d="M86 4 l6 14 h-12 z" fill="#7FB0F0" {O2}/>'
                f'<circle cx="74" cy="18" r="10" fill="{RIM}" {O}/>' + _star(74, 18, 6, "#fff"))
    if mood == "think":
        return f'<text x="160" y="28" font-family="system-ui,sans-serif" font-weight="900" font-size="22" fill="#fff" {O2} paint-order="stroke">?</text>'
    if mood == "oops":
        return f'<path d="M162 34 q4 7 0 10 q-4 -3 0 -10 z" fill="#8EC5FF" {O2}/>'
    return ""


def mascot(mood: str = "happy", size: int = 96, label: str = "Tempo the turtle") -> Markup:
    if mood not in MOODS:
        mood = "happy"
    raised = mood in ("wave", "cheer")
    svg = f'''<svg class="tempo tempo-{mood}" width="{int(size)}" height="{int(size * 0.72)}" viewBox="0 0 178 128" role="img" aria-label="{label}">
<ellipse cx="80" cy="120" rx="64" ry="5.5" fill="#000" opacity=".14"/>
<path d="M14 92 l-11 3 q4 7 15 3 z" fill="{SKIN}" {O}/>
{_leg(34, 106)}{_leg(98, 106)}{_leg(120, 108) if raised else ""}
<path d="M122 86 q-2 -16 8 -28" fill="none" stroke="{INK}" stroke-width="20" stroke-linecap="round"/>
<path d="M122 86 q-2 -16 8 -28" fill="none" stroke="{SKIN}" stroke-width="13.6" stroke-linecap="round"/>
<path d="M12 90 C12 44 40 22 68 22 C98 22 126 44 126 90 Z" fill="{SHELL}" {O}/>
<path d="M30 86 C30 52 48 36 68 36 C90 36 108 52 108 86" fill="none" stroke="{SHELL_DARK}" stroke-width="2.6"/>
<path d="M48 40 L40 62 M88 40 L96 62 M40 62 L30 86 M96 62 L108 86 M40 62 H96 M68 62 V88" fill="none" stroke="{SHELL_DARK}" stroke-width="2.6" stroke-linecap="round"/>
<path d="M24 58 C26 42 40 30 56 27" fill="none" stroke="{SHELL_LIGHT}" stroke-width="5" stroke-linecap="round" opacity=".9"/>
<circle cx="22" cy="68" r="2.6" fill="{SHELL_LIGHT}"/>
<line x1="52" y1="56" x2="84" y2="40" stroke="{INK}" stroke-width="3.2" stroke-linecap="round"/>
<circle cx="52" cy="56" r="5.2" fill="#fff" {O2}/><circle cx="68" cy="48" r="5.2" fill="#fff" {O2}/><circle cx="84" cy="40" r="6" fill="{SCARF}" {O2}/>
<path d="M6 88 H132 q5 0 5 5 v4 q0 5 -5 5 H6 q-5 0 -5 -5 v-4 q0 -5 5 -5 z" fill="{RIM}" {O}/>
<path d="M24 89 v11 M44 89 v11 M64 89 v11 M84 89 v11 M104 89 v11" stroke="{RIM_DARK}" stroke-width="2.4" stroke-linecap="round"/>
<circle cx="139" cy="52" r="24" fill="{SKIN}" {O}/>
<path d="M124 36 q8 -8 20 -6" fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" opacity=".55"/>
<circle cx="126" cy="61" r="4" fill="{CHEEK}" opacity=".75"/><circle cx="153" cy="61" r="4" fill="{CHEEK}" opacity=".75"/>
{_eyes(mood)}{_mouth(mood)}
<path d="M128 82 q-6 8 -10 18 l7 2 q3 -9 6 -16 z" fill="{SCARF}" {O}/>
<path d="M131 82 q5 8 6 18 l-7 1 q-1 -9 -3 -15 z" fill="{SCARF_DARK}" {O}/>
<path d="M114 71 q14 8 32 -1 l2 9 q-18 9 -36 1 z" fill="{SCARF}" {O}/>
<circle cx="120" cy="77" r="1.5" fill="#fff"/><circle cx="130" cy="79" r="1.5" fill="#fff"/><circle cx="140" cy="76" r="1.5" fill="#fff"/>
<circle cx="122" cy="94" r="1.3" fill="#fff"/>
<ellipse cx="129.5" cy="82" rx="5" ry="4.2" fill="{SCARF}" {O2}/>
{_arm_up() if raised else _leg(132, 110)}
{_extras(mood)}
</svg>'''
    return Markup(svg)
