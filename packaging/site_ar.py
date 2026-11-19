"""Makes the Arabic home page of the website (site/ar/index.html) from the English one, when the site is published.

The home page has English and Arabic in it, and shows one of them. Search engines list one address per language,
so Arabic gets its own address: /inPace/ar/. This copies the page, makes Arabic the language it opens in, gives it
Arabic search titles, and points its links one folder up. Nothing to keep in step by hand.

    python packaging/site_ar.py [site folder]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BASE = "https://mahmoudyosrimahmoud13.github.io/inPace/"
TITLE = "inPace · تطبيق تعلّم مجاني ومفتوح المصدر مع دورات مجانية"
DESCRIPTION = ("inPace تطبيق تعلّم مجاني ومفتوح المصدر لويندوز وماك ولينكس وأندرويد. دورات ومسارات تعلّم مجانية بالعربية "
               "والإنجليزية، فيديوهات وكود واختبارات، صانع دورات بالذكاء الاصطناعي، ومحطات موقّعة. بلا حساب، ويعمل بدون إنترنت.")
OG_TITLE = "inPace · تعلّم على راحتك. وأثبت أنك التزمت."
OG_DESCRIPTION = "تطبيق تعلّم مجاني ومفتوح المصدر مع مكتبة دورات مجانية يصنعها المتعلمون. ويندوز وماك ولينكس وأندرويد."


def _up(url: str) -> str:
    """A link from the English page, seen from one folder down."""
    if not url or url.startswith(("#", "http:", "https:", "//", "/", "mailto:", "data:", "../", "javascript:")):
        return url
    return "../" + url


def make(html: str) -> str:
    def sub(pattern: str, repl: str, text: str) -> str:
        out, n = re.subn(pattern, repl, text, count=1)
        if not n:
            raise SystemExit(f"site_ar: couldn't find {pattern!r} in index.html")
        return out

    html = sub(r'<html lang="en" dir="ltr">', '<html lang="ar" dir="rtl" data-ar-page>', html)
    html = sub(r"<title>[^<]*</title>", f"<title>{TITLE}</title>", html)
    html = sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{DESCRIPTION}">', html)
    html = sub(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{OG_TITLE}">', html)
    html = sub(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{OG_DESCRIPTION}">', html)
    html = sub(r'<meta name="twitter:title" content="[^"]*">', f'<meta name="twitter:title" content="{OG_TITLE}">', html)
    html = sub(r'<meta name="twitter:description" content="[^"]*">', f'<meta name="twitter:description" content="{OG_DESCRIPTION}">', html)
    html = sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{BASE}ar/">', html)
    html = sub(r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{BASE}ar/">', html)
    html = sub(r'<meta property="og:locale" content="en_US">\s*<meta property="og:locale:alternate" content="ar_AR">',
               '<meta property="og:locale" content="ar_AR">\n<meta property="og:locale:alternate" content="en_US">', html)
    # It opens in Arabic, whatever language the browser or an earlier visit chose.
    html = sub(r'(\n\s*)document\.documentElement\.lang = lang;', r'\1lang = "ar";\1document.documentElement.lang = lang;', html)
    # Links to the site's own files and pages are one folder up now.
    html = re.sub(r'\b(src|href)="([^"]*)"', lambda m: f'{m.group(1)}="{_up(m.group(2))}"', html)
    return html


def main(argv: list[str]) -> None:
    site = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent / "site"
    out = site / "ar" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(make((site / "index.html").read_text(encoding="utf-8")), encoding="utf-8")
    print("made", out)


if __name__ == "__main__":
    main(sys.argv[1:])
