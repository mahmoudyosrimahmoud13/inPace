"""Tempo, the inPace turtle. Slow and steady wins the race.

Drawn as inline SVG so it stays sharp, works offline and needs no image files.
Its shell carries the inPace logo: three milestones joined by a line.
"""
from __future__ import annotations

from markupsafe import Markup

MOODS = ("happy", "cheer", "sleepy", "think", "proud", "oops", "wave")

SHELL = "#1F7A56"
SHELL_DARK = "#17603F"
SKIN = "#8FD3A8"
SKIN_DARK = "#6DBB8B"
INK = "#15191F"
CHEEK = "#F4A6A6"


def _eyes(mood: str) -> str:
    if mood == "sleepy":
        return ('<path d="M95 44 q4 3 8 0" stroke="{i}" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
                '<path d="M107 44 q4 3 8 0" stroke="{i}" stroke-width="2.2" fill="none" stroke-linecap="round"/>')
    if mood in ("cheer", "proud"):
        return ('<path d="M95 45 q4 -5 8 0" stroke="{i}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
                '<path d="M107 45 q4 -5 8 0" stroke="{i}" stroke-width="2.4" fill="none" stroke-linecap="round"/>')
    if mood == "think":
        return ('<circle cx="99" cy="43" r="3.2" fill="{i}"/><circle cx="100.2" cy="41.8" r="1" fill="#fff"/>'
                '<path d="M107 43 h7" stroke="{i}" stroke-width="2.4" stroke-linecap="round"/>')
    return ('<circle cx="99" cy="43" r="3.4" fill="{i}"/><circle cx="111" cy="43" r="3.4" fill="{i}"/>'
            '<circle cx="100.3" cy="41.7" r="1.1" fill="#fff"/><circle cx="112.3" cy="41.7" r="1.1" fill="#fff"/>')


def _mouth(mood: str) -> str:
    return {
        "happy": '<path d="M101 51 q4 4 8 0" stroke="{i}" stroke-width="2.2" fill="none" stroke-linecap="round"/>',
        "wave": '<path d="M101 51 q4 4 8 0" stroke="{i}" stroke-width="2.2" fill="none" stroke-linecap="round"/>',
        "cheer": '<path d="M100 50 q5 8 10 0 z" fill="{i}"/><path d="M102.5 53.5 q2.5 2 5 0" fill="#E86A6A"/>',
        "proud": '<path d="M100 50 q5 7 10 0" stroke="{i}" stroke-width="2.4" fill="none" stroke-linecap="round"/>',
        "sleepy": '<ellipse cx="105" cy="52" rx="2" ry="1.6" fill="{i}"/>',
        "think": '<path d="M101 52 h7" stroke="{i}" stroke-width="2.2" stroke-linecap="round"/>',
        "oops": '<path d="M101 53 q4 -4 8 0" stroke="{i}" stroke-width="2.2" fill="none" stroke-linecap="round"/>',
    }[mood]


def _extras(mood: str) -> str:
    if mood == "sleepy":
        return ('<text x="116" y="24" font-family="system-ui" font-weight="800" font-size="11" fill="#7FA6D6">z</text>'
                '<text x="123" y="14" font-family="system-ui" font-weight="800" font-size="8" fill="#7FA6D6">z</text>')
    if mood == "cheer":
        return ('<path d="M18 10 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" fill="#F2B84B"/>'
                '<path d="M120 8 l1.5 3.5 3.5 1.5 -3.5 1.5 -1.5 3.5 -1.5 -3.5 -3.5 -1.5 3.5 -1.5z" fill="#F2B84B"/>'
                '<path d="M8 40 l1.2 2.8 2.8 1.2 -2.8 1.2 -1.2 2.8 -1.2 -2.8 -2.8 -1.2 2.8 -1.2z" fill="#7FB0F0"/>')
    if mood == "proud":
        return ('<circle cx="60" cy="14" r="8" fill="#F2B84B"/><path d="M60 9 l1.6 3.3 3.6 .5 -2.6 2.5 .6 3.6 -3.2 -1.7 '
                '-3.2 1.7 .6 -3.6 -2.6 -2.5 3.6 -.5z" fill="#fff"/>')
    if mood == "think":
        return '<text x="117" y="24" font-family="system-ui" font-weight="800" font-size="16" fill="#7FA6D6">?</text>'
    if mood == "oops":
        return '<path d="M118 30 q2 4 0 6 q-2 -2 0 -6z" fill="#7FB0F0"/>'
    return ""


def _arm(mood: str) -> str:
    # Front leg: waves or cheers when happy, rests otherwise.
    if mood in ("cheer", "wave"):
        return f'<ellipse cx="124" cy="60" rx="5" ry="10" transform="rotate(-30 124 60)" fill="{SKIN}" stroke="{SKIN_DARK}" stroke-width="1.5"/>'
    return ""


def mascot(mood: str = "happy", size: int = 96, label: str = "Tempo the turtle") -> Markup:
    if mood not in MOODS:
        mood = "happy"
    eyes, mouth = _eyes(mood).replace("{i}", INK), _mouth(mood).replace("{i}", INK)
    svg = f'''<svg class="tempo tempo-{mood}" width="{int(size)}" height="{int(size * 0.8)}" viewBox="0 0 138 104" role="img" aria-label="{label}">
<ellipse cx="62" cy="96" rx="44" ry="5" fill="currentColor" opacity=".08"/>
<ellipse cx="32" cy="84" rx="8" ry="6" fill="{SKIN_DARK}"/>
<ellipse cx="84" cy="84" rx="8" ry="6" fill="{SKIN_DARK}"/>
<path d="M12 70 q-8 -2 -6 4 q6 3 12 0z" fill="{SKIN}"/>
<path d="M14 72 Q16 26 58 22 Q98 24 100 70 Z" fill="{SHELL}"/>
<path d="M14 72 Q16 26 58 22 Q98 24 100 70" fill="none" stroke="{SHELL_DARK}" stroke-width="3"/>
<path d="M10 70 h94 q4 0 4 4 v1 q0 4 -4 4 h-94 q-4 0 -4 -4 v-1 q0 -4 4 -4z" fill="{SKIN_DARK}"/>
<line x1="36" y1="58" x2="78" y2="36" stroke="#fff" stroke-width="3.2" stroke-linecap="round" opacity=".95"/>
<circle cx="36" cy="58" r="6.5" fill="#fff"/><circle cx="57" cy="47" r="6.5" fill="#fff"/><circle cx="78" cy="36" r="7.5" fill="#9FF0C8"/>
<path d="M92 66 q-4 -10 2 -18" stroke="{SKIN}" stroke-width="12" fill="none" stroke-linecap="round"/>
<circle cx="105" cy="46" r="17" fill="{SKIN}"/>
<circle cx="95" cy="50" r="2.6" fill="{CHEEK}" opacity=".8"/><circle cx="116" cy="50" r="2.6" fill="{CHEEK}" opacity=".8"/>
{eyes}{mouth}{_arm(mood)}{_extras(mood)}
</svg>'''
    return Markup(svg)
