"""The languages inPace speaks.

Add a language by writing locales/<code>.json and adding a line to LANGS. Anything a file doesn't
translate falls back to English, so a half-finished language still works.

`font` says which letters the bundled font (Readex Pro) can draw:
  "bundled"  Latin and Arabic: the font that ships with inPace
  a name     that script needs the fonts already on the computer (CJK, Thai, Devanagari,
             Cyrillic, and Latin letters Readex doesn't have, like Vietnamese and Turkish)
"""
from __future__ import annotations

# code: (English name, the name in that language, direction, font)
LANGS: dict[str, tuple[str, str, str, str]] = {
    "en": ("English", "English", "ltr", "bundled"),
    "ar": ("Arabic", "العربية", "rtl", "bundled"),
    "es": ("Spanish", "Español", "ltr", "bundled"),
    "fr": ("French", "Français", "ltr", "bundled"),
    "de": ("German", "Deutsch", "ltr", "bundled"),
    "pt": ("Portuguese", "Português", "ltr", "bundled"),
    "id": ("Indonesian", "Bahasa Indonesia", "ltr", "bundled"),
    "tr": ("Turkish", "Türkçe", "ltr", "latin-plus"),
    "vi": ("Vietnamese", "Tiếng Việt", "ltr", "latin-plus"),
    "ru": ("Russian", "Русский", "ltr", "cyrillic"),
    "hi": ("Hindi", "हिन्दी", "ltr", "devanagari"),
    "th": ("Thai", "ไทย", "ltr", "thai"),
    "ja": ("Japanese", "日本語", "ltr", "japanese"),
    "zh": ("Chinese (Simplified)", "简体中文", "ltr", "chinese"),
}

RTL = {code for code, (_, _, d, _) in LANGS.items() if d == "rtl"}

# Short month names. English is the fallback for any language that isn't here.
MONTHS: dict[str, list[str]] = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    "fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
    "de": ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."],
    "pt": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
    "id": ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"],
    "tr": ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"],
    "vi": ["Th1", "Th2", "Th3", "Th4", "Th5", "Th6", "Th7", "Th8", "Th9", "Th10", "Th11", "Th12"],
    "ru": ["янв.", "февр.", "март", "апр.", "май", "июнь", "июль", "авг.", "сент.", "окт.", "нояб.", "дек."],
    "hi": ["जन", "फ़र", "मार्च", "अप्रै", "मई", "जून", "जुल", "अग", "सित", "अक्तू", "नव", "दिस"],
    "th": ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."],
    "ja": ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
    "zh": ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
}

# How a date is written. {d} day, {m} month name, {y} year.
DATE_ORDER: dict[str, str] = {
    "en": "{m} {d}, {y}",
    "ar": "{d} {m} {y}", "es": "{d} {m} {y}", "fr": "{d} {m} {y}", "de": "{d}. {m} {y}",
    "pt": "{d} {m} {y}", "id": "{d} {m} {y}", "tr": "{d} {m} {y}", "vi": "{d} {m} {y}",
    "ru": "{d} {m} {y}", "hi": "{d} {m} {y}", "th": "{d} {m} {y}",
    "ja": "{y}年{m}{d}日", "zh": "{y}年{m}{d}日",
}

# Fonts already on Windows, Mac, Linux and Android, for the letters the bundled font doesn't have.
# Nothing is downloaded: inPace still works with no internet.
FONT_STACKS: dict[str, str] = {
    "latin-plus": '"Segoe UI", system-ui, -apple-system, Roboto, "Noto Sans", sans-serif',
    "cyrillic": '"Segoe UI", system-ui, -apple-system, Roboto, "Noto Sans", sans-serif',
    "devanagari": '"Nirmala UI", "Noto Sans Devanagari", "Kohinoor Devanagari", "Mangal", system-ui, sans-serif',
    "thai": '"Leelawadee UI", "Noto Sans Thai", "Thonburi", "Sarabun", system-ui, sans-serif',
    "japanese": '"Yu Gothic UI", "Hiragino Sans", "Noto Sans JP", Meiryo, system-ui, sans-serif',
    "chinese": '"Microsoft YaHei UI", "PingFang SC", "Noto Sans SC", "Source Han Sans SC", system-ui, sans-serif',
}


def known(code: str | None) -> bool:
    return (code or "") in LANGS


def pick(code: str | None, fallback: str = "en") -> str:
    """The language to use for a code that may be empty, unknown, or a full tag like "pt-BR"."""
    code = (code or "").strip().lower().replace("_", "-")
    if code in LANGS:
        return code
    short = code.split("-")[0]
    return short if short in LANGS else fallback


def direction(code: str) -> str:
    return "rtl" if code in RTL else "ltr"


def native(code: str) -> str:
    return LANGS[code][1] if code in LANGS else code


def font_css() -> str:
    """One CSS rule per language that needs the computer's own fonts."""
    lines = []
    for code, (_, _, _, font) in LANGS.items():
        stack = FONT_STACKS.get(font)
        if stack:
            lines.append(f'html[lang="{code}"] {{ --sans: {stack}; --serif: {stack}; }}')
    return "\n".join(lines)
