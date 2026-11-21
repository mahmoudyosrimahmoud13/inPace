"""v1.31.3: text you can read on every background (light, dark, AMOLED, every accent), app windows whose own
background follows the page (no white flashes), and a library that is light to scroll."""
import ast
import re
from pathlib import Path

import pytest

from inpace import window

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "inpace" / "static" / "style.css").read_text(encoding="utf-8")
JS = (ROOT / "inpace" / "static" / "app.js").read_text(encoding="utf-8")
ACCENTS = ["ocean", "mint", "rose", "grape", "nile", "mono"]


# ---- reading the theme tokens out of style.css -------------------------------------------------------------------
def _rules():
    text = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        yield " ".join(m.group(1).split()), m.group(2)


def _block(selector):
    out = {}
    for sel, body in _rules():
        if sel == selector:
            out.update({k: v.strip() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", body)})
    return out


BASE, DARK = _block(":root"), _block(":root[data-theme=dark]")
BLACK = _block(":root[data-black][data-theme=dark]")
ACC_LIGHT = {a: _block(f":root[data-accent={a}]") for a in ACCENTS}
ACC_DARK = {a: _block(f":root[data-theme=dark][data-accent={a}]") for a in ACCENTS}
LOOKS = [(look, acc) for look in ("light", "dark", "amoled") for acc in [""] + ACCENTS]


def tokens(look, acc):
    t = dict(BASE)
    if look != "light":
        t.update(DARK)
    if look == "amoled":
        t.update(BLACK)
    if acc:
        t.update(ACC_LIGHT[acc])
        if look != "light":
            t.update(ACC_DARK[acc])
    return t


def resolve(value, t, depth=0):
    value = value.strip()
    m = re.fullmatch(r"var\((--[\w-]+)\)", value)
    if m and depth < 10:
        return resolve(t[m.group(1)], t, depth + 1)
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def contrast(a, b):
    def lum(c):
        f = [(v / 255) / 12.92 if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# ---- 1. text on colored backgrounds ----------------------------------------------------------------------------
PAIRS = {"--sky": "--sky-ink", "--pink": "--pink-ink", "--black": "--black-ink", "--good": "--good-ink", "--bad": "--bad-ink"}


@pytest.mark.parametrize("bg,ink", sorted(PAIRS.items()))
def test_every_background_has_a_text_color_that_reads_in_every_look(bg, ink):
    for look, acc in LOOKS:
        t = tokens(look, acc)
        assert contrast(resolve(t[bg], t), resolve(t[ink], t)) >= 4.5, (bg, look, acc or "default")
    t = tokens("dark", "")
    assert contrast(resolve(t["--sky"], t), resolve(t["--sky-muted"], t)) >= 4.5


def test_rules_use_the_pair_never_a_fixed_color():
    """Any rule that paints one of these backgrounds and sets a text color must read in all 21 looks."""
    checked = 0
    for sel, body in _rules():
        bg = re.search(r"background(?:-color)?\s*:\s*var\((--sky|--pink|--black|--good|--bad)\)\s*(?:;|$)", body)
        color = re.search(r"(?:^|;)\s*color\s*:\s*(var\(--[\w-]+\)|#[0-9a-fA-F]{3,6})", body)
        if not (bg and color) or sel.startswith(":root"):
            continue
        checked += 1
        for look, acc in LOOKS:
            t = tokens(look, acc)
            ratio = contrast(resolve(f"var({bg.group(1)})", t), resolve(color.group(1), t))
            assert ratio >= 4.5, f"{sel}: {ratio:.2f} in {look}/{acc or 'default'}"
    assert checked >= 15


def test_the_rules_people_reported():
    assert re.search(r"\.rm-chip \{[^}]*background: var\(--sky\); color: var\(--sky-ink\)", CSS)  # next to the course
    assert ".rm-strip .small.muted { color: var(--sky-muted); }" in CSS
    assert ".lib-on-rm a { color: var(--sky-ink);" in CSS
    assert ".chip.bad { background: var(--pink); color: var(--pink-ink); }" in CSS


def test_locked_things_dont_fade_their_words():
    assert ".trail-module.locked .trail { opacity" not in CSS
    assert ".outline-list li.locked { color: var(--muted); }" in CSS
    assert ".outline-list li.locked { opacity" not in CSS


def test_a_new_page_appears_only_after_the_old_one_is_gone():
    pairs = [("", ""), ('html[data-nav="forward"]', 'html[data-nav="forward"]'), ('html[data-nav="back"]', 'html[data-nav="back"]'),
             ('html[data-nav="fade"]', 'html[data-nav="fade"]')]
    for old_sel, new_sel in pairs:
        old = re.search(re.escape(old_sel) + r"::view-transition-old\(root\) \{ animation: (\d+)ms", CSS)
        new = re.search(re.escape(new_sel) + r"::view-transition-new\(root\) \{ animation: \d+ms [^;]*? (\d+)ms both", CSS)
        assert old and new, old_sel
        assert int(new.group(1)) >= int(old.group(1)), old_sel


# ---- 2. the window behind the page -----------------------------------------------------------------------------
def test_start_color_follows_the_settings(monkeypatch):
    monkeypatch.setattr(window, "device_dark", lambda: False)
    assert window.start_background("light") == window.LIGHT_BG == "#F7F3EA"
    assert window.start_background("dark") == window.DARK_BG == "#12110E"
    assert window.start_background("dark", black=True) == window.BLACK_BG == "#000000"
    assert window.start_background("") == window.LIGHT_BG
    monkeypatch.setattr(window, "device_dark", lambda: True)  # "like the device", and the device is dark
    assert window.start_background("") == window.DARK_BG
    assert window.start_background("light") == window.LIGHT_BG


def test_page_colors_match_the_css():
    assert BASE["--bg"] == window.LIGHT_BG and DARK["--bg"] == window.DARK_BG and BLACK["--bg"] in ("#000", "#000000")


def test_the_linux_window_starts_in_the_color_and_follows_the_page(monkeypatch):
    ast.parse(window.LINUX_HELPER)
    h = window.LINUX_HELPER
    assert "set_background_color" in h and 'text.startswith("bg:")' in h and "sys.argv[5]" in h
    got = {}

    def fake_run(cmd, env, home, name, on_ready=None):
        got["cmd"] = cmd
        return "closed"
    monkeypatch.setattr(window, "_run_helper", fake_run)
    monkeypatch.setattr(window.sys, "platform", "linux")
    monkeypatch.setattr(window.os.path, "exists", lambda p: True)
    assert window._linux_gtk("http://127.0.0.1:1/", None, "#12110E")
    assert got["cmd"][-1] == "#12110E" and "background:#12110E" in got["cmd"][-3]
    window._linux_gtk("http://127.0.0.1:1/", None, "not a color")
    assert got["cmd"][-1] == ""


def test_loading_screen_colors():
    assert "html,body{background:#12110E;color:#F2EDE2}" in window.splash_html("#12110E")
    assert "prefers-color-scheme:dark" not in window.splash_html("#12110E")
    plain = window.splash_html()
    assert "prefers-color-scheme:dark" in plain and "messageHandlers.inpace" in plain


def test_qt_and_pywebview_follow_the_page():
    qt = (ROOT / "inpace" / "qtwindow.py").read_text(encoding="utf-8")
    assert "def javaScriptConsoleMessage" in qt and '"inpace-shell bg:"' in qt and "setBackgroundColor" in qt
    api = window._ShellApi()
    assert api.background("#12110E") is False  # no window yet
    api.win = object()
    assert api.background("red") is False and api.background("#12110E") is False  # not a color / no native window
    src = (ROOT / "inpace" / "window.py").read_text(encoding="utf-8")
    assert "background_color=bg if _hex_ok(bg) else LIGHT_BG, js_api=api" in src
    main = (ROOT / "inpace" / "__main__.py").read_text(encoding="utf-8")
    assert "start_background(" in main and "open_window(url, vault.home, bg)" in main


def test_the_page_tells_every_kind_of_window():
    part = JS[JS.index("// ---- The app window's background (v1.31.3)"):]
    part = part[:part.index("})();") + 5]
    assert 'messageHandlers.inpace.postMessage("bg:" + hex)' in part          # Linux GTK window
    assert 'JSON.stringify({ type: "bg", color: hex })' in part                 # Android app
    assert "pywebview.api.background(hex)" in part                              # Windows and Mac
    assert 'console.info("inpace-shell bg:" + hex)' in part                     # Linux Qt window
    assert 'attributeFilter: ["data-theme", "data-black", "data-accent"]' in part and "prefers-color-scheme: dark" in part


def test_the_android_app_follows_the_page():
    dart = (ROOT / "mobile" / "lib" / "main.dart").read_text(encoding="utf-8")
    assert "case 'bg':" in dart and "void _setBg(String hex" in dart and "..setBackgroundColor(_bg)" in dart
    assert "backgroundColor: _bg," in dart and "AnnotatedRegion<SystemUiOverlayStyle>" in dart
    assert "window-bg.txt" in dart  # opens in the last color next time
    assert dart.count("0xFFF7F3EA") == 1  # only the first color before the page says anything
    # the extra AnnotatedRegion wrapper is closed again
    build = dart[dart.index("final web = _web!;"):dart.index("class Splash extends")]
    assert build.count("(") == build.count(")")


# ---- 3. a library that is light to scroll ----------------------------------------------------------------------
def test_library_cards_are_only_drawn_near_the_screen(tmp_path):
    assert ".lib-card { content-visibility: auto; contain-intrinsic-size: auto 32rem; }" in CSS
    lib = (ROOT / "inpace" / "templates" / "library.html").read_text(encoding="utf-8")
    assert 'alt="" loading="lazy" decoding="async">' in lib
