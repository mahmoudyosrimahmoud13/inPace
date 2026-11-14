"""v1.25.2: the first open speaks the device's language and lets you pick one; the tour works on phones."""
import html

from starlette.testclient import TestClient

from inpace import app as app_mod
from inpace.app import create_app, device_lang
from inpace.vault import Vault


def test_device_lang_reads_the_accept_language_header():
    assert device_lang("ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7") == "ar"
    assert device_lang("en-US,en;q=0.9,ar;q=0.8") == "en"
    assert device_lang("fr-FR,fr;q=0.9,ar;q=0.5,en;q=0.4") == "ar"   # the best one inPace speaks
    assert device_lang("ar;q=0.3, en;q=0.9") == "en"
    assert device_lang("ar,en") == "ar"


def test_device_lang_falls_back_to_the_computer(monkeypatch):
    monkeypatch.setenv("LC_ALL", "ar_EG.UTF-8")
    assert device_lang("") == "ar" and device_lang("fr-FR") == "ar"
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    assert device_lang(None) == "en"


def test_first_open_speaks_the_device_language_and_lets_you_pick(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    page = html.unescape(c.get("/setup", headers={"Accept-Language": "ar-EG,ar;q=0.9,en;q=0.8"}).text)
    assert 'dir="rtl"' in page and "أهلًا بك في inPace" in page and 'href="/setup?lang=en"' in page
    page = html.unescape(c.get("/setup", headers={"Accept-Language": "en-US"}).text)
    assert 'dir="ltr"' in page and "Welcome to inPace" in page
    # pick Arabic on an English device: the page switches and stays Arabic
    c.get("/setup?lang=ar", headers={"Accept-Language": "en-US"})
    page = html.unescape(c.get("/setup", headers={"Accept-Language": "en-US"}).text)
    assert 'dir="rtl"' in page and 'name="lang" value="ar"' in page
    c.post("/setup", data={"name": "Mona", "lang": "ar"}, headers={"Accept-Language": "en-US"})
    assert v.is_set_up and v._meta("lang") == "ar"
    assert 'dir="rtl"' in c.get("/").text
    assert c.get("/setup", follow_redirects=False).headers["location"] == "/"   # no second setup


def test_setup_without_a_pick_saves_the_device_language(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Omar"}, headers={"Accept-Language": "ar"})
    assert v._meta("lang") == "ar"


def test_the_tour_points_inside_the_more_sheet_on_phones(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "lang": "en"})
    page = c.get("/?tour=1").text
    for href in ("/people", "/races", "/open", "/settings", "/island"):
        assert f'.more-sheet a[href=\\"{href}\\"]' in page or f".more-sheet a[href=\\u0022{href}\\u0022]" in page or f'.more-sheet a[href=\\"{href}' in page, href
    assert "[data-more-open]" not in page.split('id="tour-data"')[1].split("</script>")[0]
