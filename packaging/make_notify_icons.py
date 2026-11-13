"""Draw Tempo (and the villain) as small pictures for notifications.

Notifications can't show SVG, so this makes PNGs:
  inpace/static/notify/<name>.png              for Windows and Linux notifications (128 px)
  mobile/icon/res/drawable-nodpi/<name>.png    the big picture in Android notifications (192 px)

Run it after changing how Tempo looks:  python packaging/make_notify_icons.py
(needs Playwright with Chromium: pip install playwright && playwright install chromium)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from inpace import garden_art, mascot  # noqa: E402

MOODS = ("happy", "cheer", "wave", "oops", "sad", "read", "sleepy", "proud")


def pictures() -> dict[str, str]:
    """name -> an SVG drawn inside a round badge, so it looks right on any notification."""
    out = {}
    for mood in MOODS:
        out[f"tempo_{mood}"] = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                                f'<defs><clipPath id="c"><circle cx="50" cy="50" r="46.5"/></clipPath></defs>'
                                f'<circle cx="50" cy="50" r="48" fill="#CDE8F2"/>'
                                f'<g clip-path="url(#c)"><svg x="4" y="6" width="92" height="92" viewBox="132 12 80 80">{mascot.scarf()}{mascot.head(mood)}</svg></g>'
                                f'<circle cx="50" cy="50" r="48" fill="none" stroke="#111" stroke-width="3"/></svg>')
    out["villain"] = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                      '<circle cx="50" cy="50" r="48" fill="#262B3A" stroke="#111" stroke-width="3"/>'
                      f'<svg x="8" y="12" width="84" height="76" viewBox="0 0 160 140">{garden_art.villain(3)}</svg></svg>')
    return out


def main() -> None:
    from playwright.sync_api import sync_playwright
    targets = [(ROOT / "inpace" / "static" / "notify", 128), (ROOT / "mobile" / "icon" / "res" / "drawable-nodpi", 192)]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for name, svg in pictures().items():
            for folder, size in targets:
                folder.mkdir(parents=True, exist_ok=True)
                page.set_viewport_size({"width": size, "height": size})
                page.set_content(f'<html><body style="margin:0;background:transparent">'
                                 f'<div style="width:{size}px;height:{size}px">{svg.replace("<svg ", f"<svg width={size} height={size} ", 1)}</div></body></html>')
                page.screenshot(path=str(folder / f"{name}.png"), omit_background=True)
        browser.close()
    print("Done.")


if __name__ == "__main__":
    main()
