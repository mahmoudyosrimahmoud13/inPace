"""The website's Arabic home page (/inPace/ar/) is made from the English one when the site is published."""
import json
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _mod():
    spec = importlib.util.spec_from_file_location("site_ar", ROOT / "packaging/site_ar.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_arabic_page_is_its_own_page(tmp_path):
    import shutil
    site = tmp_path / "site"
    shutil.copytree(ROOT / "site", site)
    _mod().main([str(site)])
    ar = (site / "ar/index.html").read_text(encoding="utf-8")
    assert '<html lang="ar" dir="rtl" data-ar-page>' in ar
    assert '<link rel="canonical" href="https://mahmoudyosrimahmoud13.github.io/inPace/ar/">' in ar
    assert 'hreflang="en"' in ar and 'hreflang="ar"' in ar and 'og:locale" content="ar_AR"' in ar
    assert 'src="../assets/shots/home-ar.jpg"' in ar and 'href="../style.css' in ar and 'src="../lang.js' in ar
    assert 'href="#download"' in ar                     # links inside the page stay inside the page
    assert 'lang = "ar";' in ar
    for path in ("assets/favicon-48.png", "assets/icon-192.png", "assets/apple-touch-icon.png"):
        assert (site / path).exists()


def test_english_page_tells_search_engines_about_both():
    en = (ROOT / "site/index.html").read_text(encoding="utf-8")
    assert 'hreflang="ar" href="https://mahmoudyosrimahmoud13.github.io/inPace/ar/"' in en
    assert '"@type": "WebSite", "name": "inPace"' in en
    assert len(en.split("<title>")[1].split("</title>")[0]) <= 65
    sitemap = (ROOT / "site/sitemap.xml").read_text(encoding="utf-8")
    assert "/inPace/ar/</loc>" in sitemap
    wf = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "packaging/site_ar.py site" in wf


def test_download_counter_never_goes_back(tmp_path):
    spec = importlib.util.spec_from_file_location("download_count", ROOT / "packaging/download_count.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    f = tmp_path / "downloads.json"
    pages = {1: [{"tag_name": "v1.0.0", "assets": [{"download_count": 40}, {"download_count": 2}]},
                 {"tag_name": "v1.1.0", "assets": [{"download_count": 10}]}]}
    m.main([str(f)], fetch=lambda url: pages.get(int(url.rsplit("=", 1)[1]), []))
    assert json.loads(f.read_text())["total"] == 52
    # v1.0.0 deleted, v1.1.0 grew, v1.2.0 is new: the old count stays, the total only goes up
    pages[1] = [{"tag_name": "v1.1.0", "assets": [{"download_count": 15}]}, {"tag_name": "v1.2.0", "assets": [{"download_count": 3}]}]
    d = m.main([str(f)], fetch=lambda url: pages.get(int(url.rsplit("=", 1)[1]), []))
    assert d["releases"] == {"v1.0.0": 42, "v1.1.0": 15, "v1.2.0": 3} and d["total"] == 60
    # more than 100 releases: every page is read
    pages[1] = [{"tag_name": f"v0.{i}", "assets": [{"download_count": 1}]} for i in range(100)]
    pages[2] = [{"tag_name": "v9.9", "assets": [{"download_count": 1}]}]
    d = m.main([str(f)], fetch=lambda url: pages.get(int(url.rsplit("=", 1)[1]), []))
    assert d["total"] == 60 + 101
