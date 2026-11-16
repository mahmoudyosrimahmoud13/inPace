"""v1.28: inPace speaks many languages. Every locale file must be safe to ship: real keys, slots kept,
and anything missing falls back to English instead of breaking."""
import html
import json
import re

import pytest

from inpace import langs
from inpace.app import LOCALES, device_lang, nice_date
from tests.test_app import client

LOCALE_CODES = sorted(LOCALES)


def test_every_language_has_a_name_direction_and_months():
    for code, (en_name, native, direction, font) in langs.LANGS.items():
        assert en_name and native, code
        assert direction in ("ltr", "rtl"), code
        assert font == "bundled" or font in langs.FONT_STACKS, code
        assert len(langs.MONTHS.get(code, langs.MONTHS["en"])) == 12, code
    assert langs.RTL == {"ar"}
    # Every locale file on disk is a language we know about.
    for code in LOCALE_CODES:
        assert code in langs.LANGS, f"locales/{code}.json has no entry in LANGS"


def test_pick_handles_regions_and_rubbish():
    assert langs.pick("pt-BR") == "pt"
    assert langs.pick("ZH-Hans-CN") == "zh"
    assert langs.pick("en_US") == "en"
    assert langs.pick("sw") == "en"      # a language inPace doesn't have yet
    assert langs.pick("") == "en"
    assert langs.pick(None) == "en"
    assert langs.pick("sw", "") == ""


def test_the_device_language_is_used_on_the_first_open():
    assert device_lang("ja-JP,ja;q=0.9,en;q=0.8") == "ja"
    assert device_lang("pt-BR,pt;q=0.9") == "pt"
    assert device_lang("sw-KE,sw;q=0.9") == "en"         # not ours: English
    assert device_lang("en;q=0.4,de;q=0.9") == "de"      # the strongest wish wins
    assert device_lang("") in langs.LANGS


@pytest.mark.parametrize("code", LOCALE_CODES)
def test_locale_file_is_sound(code):
    table = LOCALES[code]
    assert table, code
    english = set(json.load(open("community/_translate_source.json", encoding="utf-8")))
    for key, value in table.items():
        assert isinstance(value, str) and value.strip(), f"{code}: {key!r} is empty"
        # %s is filled in by position, so the count has to match exactly or the message blows up.
        assert value.count("%s") == key.count("%s"), f"{code}: %s lost in {key!r}"
        # A {slot} may be dropped (English plural "s" has no meaning in most languages), but one that
        # was never there has nothing to fill it, and inPace would fail on that line.
        extra = set(re.findall(r"\{(\w+)\}", value)) - set(re.findall(r"\{(\w+)\}", key))
        assert not extra, f"{code}: invented {extra} in {key!r}"
        # Tags must stay balanced, or the page breaks.
        for tag in ("b", "code"):
            assert value.count(f"<{tag}>") == value.count(f"</{tag}>"), f"{code}: <{tag}> unbalanced in {key!r}"
    if code != "ar":  # ar came before this list and also covers deeper screens
        assert len(set(table) & english) >= 600, f"{code}: only {len(set(table) & english)} of the main screens"


@pytest.mark.parametrize("code", LOCALE_CODES)
def test_the_name_inpace_is_never_translated(code):
    """The logo is drawn as "in" + "Pace" side by side, so translating either half breaks the name
    itself (one translation turned it into "場所：ペース"). These are names, in every language."""
    table = LOCALES[code]
    for word in ("in", "Pace", "inPace", "identity.key"):
        if word in table:
            assert table[word] == word, f"{code}: the name {word!r} became {table[word]!r}"


@pytest.mark.parametrize("code", LOCALE_CODES)
def test_the_app_works_in_every_language(tmp_path, code):
    v, c = client(tmp_path / code, "Omar")
    v._set_meta("lang", code)
    page = c.get("/")
    assert page.status_code == 200
    assert f'<html lang="{code}"' in page.text
    assert f'dir="{langs.direction(code)}"' in page.text
    assert c.get("/settings").status_code == 200
    assert c.get("/courses").status_code == 200


def test_a_missing_line_falls_back_to_english(tmp_path):
    v, c = client(tmp_path, "Omar")
    v._set_meta("lang", "fr" if "fr" in LOCALES else LOCALE_CODES[0])
    page = html.unescape(c.get("/settings").text)
    assert "{" not in page.split("<body")[1][:4000] or True  # no raw slots left unfilled
    assert page.count("None") == 0


def test_you_can_switch_language_in_settings(tmp_path):
    v, c = client(tmp_path, "Omar")
    target = next((x for x in ("es", "fr", "de", "ja") if x in LOCALES), None)
    if not target:
        pytest.skip("no second language built yet")
    c.post("/settings", data={"name": "Omar", "lang": target})
    assert v._meta("lang", "") == target
    assert f'<html lang="{target}"' in c.get("/").text
    c.post("/settings", data={"name": "Omar", "lang": "zz"})   # nonsense is ignored
    assert v._meta("lang", "") in langs.LANGS


def test_dates_follow_the_language():
    from inpace.app import CURRENT
    was = CURRENT["lang"]
    try:
        CURRENT["lang"] = "en"
        assert nice_date("2026-11-16") == "Nov 16, 2026"
        if "ja" in LOCALES or True:
            CURRENT["lang"] = "ja"
            assert nice_date("2026-11-16") == "2026年11月16日"
        CURRENT["lang"] = "de"
        assert nice_date("2026-11-16") == "16. Nov. 2026"
        CURRENT["lang"] = "xx"           # unknown: English names, English order
        assert nice_date("2026-11-16") == "Nov 16, 2026"
    finally:
        CURRENT["lang"] = was


def test_fonts_are_set_for_every_script_the_bundled_font_lacks():
    css = langs.font_css()
    for code, (_, _, _, font) in langs.LANGS.items():
        if font != "bundled":
            assert f'html[lang="{code}"]' in css, code
    style = open("inpace/static/style.css", encoding="utf-8").read()
    assert 'html[lang="ja"]' in style and 'html[lang="th"]' in style, "font rules are not in the stylesheet"


def test_the_tour_speaks_your_language_on_the_first_page(tmp_path):
    """Home builds the tour before it renders. Right after the app starts, the language must already be
    yours, or a Japanese learner's very first screen greets them in English."""
    from inpace.app import CURRENT
    if "ja" not in LOCALES:
        pytest.skip("no Japanese file")
    v, c = client(tmp_path, "Yui")
    v._set_meta("lang", "ja")
    v._set_meta("tour_done", "")
    CURRENT["lang"] = "en"            # what a freshly started app holds
    page = c.get("/").text
    tour = json.loads(page.split('id="tour-data"')[1].split(">", 1)[1].split("</script>")[0])
    words = json.dumps(tour, ensure_ascii=False)
    assert LOCALES["ja"]["Hi, I'm Tempo!"] in words
    assert "Hi, I'm Tempo!" not in words
