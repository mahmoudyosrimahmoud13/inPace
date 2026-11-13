"""v1.17: island names, a real villain (plants wilt and die), shells and a shop, a real-clock sky,
Tempo in notifications, and your own turtle instead of a coloured letter."""
import base64
import html
import json
import os
import time
from datetime import datetime, timezone

import pytest

from inpace import clock, exchange, garden, island_story, mascot, reminders
from tests.test_app import client


def _python(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    return v, c, v.journey_for_course("python-basics")


def _plant(v, kind="oak", journey="", ended=None, goal=25):
    import uuid
    ended = ended or time.time()
    v.db.execute("INSERT INTO garden (id, kind, goal, banked, mode, journey, state, started, ended) VALUES (?,?,?,?,?,?,?,?,?)",
                 (uuid.uuid4().hex[:12], kind, goal, goal * 60, "anywhere", journey, "grown", ended - goal * 60, ended))
    v.db.commit()


# ---- the real clock -----------------------------------------------------------------------------------

@pytest.mark.skipif(not hasattr(time, "tzset"), reason="Windows can't change the time zone this way (and doesn't need to)")
def test_the_phone_tells_python_its_real_time_zone():
    old = os.environ.get("TZ")
    try:
        assert clock.use_offset("120") in (True, False)  # True unless this machine is already at UTC+2
        assert clock.offset_now() == 120
        clock.from_cookie(b"lang=ar; tz=-300")
        assert clock.offset_now() == -300
        assert not clock.use_offset("nonsense") and not clock.use_offset(99999)
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def test_the_sky_follows_the_clock_and_the_seasons():
    day = lambda h, m=0, month=11: garden.sky_at(datetime(2026, month, 13, h, m))
    assert day(2)["phase"] == "night" and day(2)["night"] and day(2)["body"]["kind"] == "moon"
    assert day(13)["phase"] == "day" and day(13)["body"]["kind"] == "sun" and day(13)["stars"] == 0
    assert day(9)["body"]["x"] < day(13)["body"]["x"] < day(16)["body"]["x"]  # the sun crosses the sky
    assert day(16, 30)["phase"] in ("sunset", "dusk")
    assert day(19, month=6)["phase"] != "night" and day(19, month=12)["phase"] == "night"  # long June days
    rise, sets = garden.sun_times(datetime(2026, 12, 21).date())
    assert 6.5 < rise < 7.5 and 16.5 < sets < 17.5
    assert "sky-night" in garden.island_svg([], set(), 1, hour=23) and "sky-day" in garden.island_svg([], set(), 1, hour=13)


# ---- the villain is a real threat ----------------------------------------------------------------------

def test_plants_wilt_then_die_and_a_trip_waters_them(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    for k in ("oak", "pine", "tulip"):
        _plant(v, k)
    now = time.time()
    garden.decay(v, now=now)
    assert all(p["state"] == "grown" for p in garden.on_island(v))
    rot = garden.decay(v, now=now + 9 * 86400)
    assert rot["wilted"] == 0 and rot["next_wilt"]
    rot = garden.decay(v, now=now + 13 * 86400)  # day 10 and day 12: two plants wilt
    assert rot["wilted"] == 2 and v._meta("island_fled")
    assert garden.weather(v, now=now + 13 * 86400)["threat"] == 4
    rot = garden.decay(v, now=now + 25 * 86400)  # 14 days after wilting, the first one dies
    assert rot["dead"] >= 1 and v._meta("island_lost_any")
    assert len(garden.grown(v)) == 3  # it still counts for what you unlocked
    # a finished trip waters two wilting plants and brings the friends back
    v.db.execute("UPDATE garden SET state='wilted', dead_at=NULL WHERE state='dead'")
    v.db.commit()
    garden.start(v, "sunflower", 10, "anywhere", jid)
    v.db.execute("UPDATE garden SET banked=600 WHERE state='running'")
    v.db.commit()
    done = garden.check(v)
    assert done["watered"] == 2 and not v._meta("island_fled")
    assert garden.clear_dead(v) == 0


def test_gentle_sea_never_takes_plants(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    _plant(v)
    c.post("/island/gentle", data={"on": "1"})
    assert garden.gentle(v)
    rot = garden.decay(v, now=time.time() + 40 * 86400)
    assert rot["wilted"] == rot["dead"] == 0
    assert garden.threat(30, True) == 3 and garden.threat(30) == 4 and garden.threat(1) == 0


def test_the_island_page_shows_the_villain_and_what_it_took(tmp_path, monkeypatch):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    _plant(v, journey=jid)
    away = time.time() - 12 * 86400
    v._set_meta("island_last_seen", str(away))
    monkeypatch.setattr(garden, "last_active", lambda v_: away)
    page = html.unescape(c.get(f"/island?t={jid}").text)
    assert "The Fog of Someday" in page and "On your island" in page and "is wilting" in page
    assert "The Fog Has a Face" in page  # the villain interlude opens the first time it gets close
    assert 'class="isle-villain' in page
    v.db.execute("UPDATE garden SET state='dead' WHERE journey=?", (jid,))
    v.db.commit()
    page = html.unescape(c.get(f"/island?t={jid}").text)
    assert "1 plant here was taken by the fog." in page
    c.post("/island/clear", data={"t": jid})
    assert not [p for p in garden.on_island(v) if p["state"] == "dead"]


def test_villain_lines_fit_the_world_and_language():
    assert island_story.taunt(1, "arab", "en")["villain"].startswith("Bokra.")
    assert island_story.taunt(3, "universal", "ar", 2)["villain"] == "أنا على شاطئك الآن. بعد يومين تصير نباتاتك لي."
    assert island_story.villain_name("arab", "ar") == "ضباب بكرة"
    for key in ("villain", "loss"):
        for w in island_story.WORLDS:
            for lang in ("en", "ar"):
                assert "{" not in " ".join(island_story.chapter(key, w, lang)["paras"])


# ---- names, shells and the shop ------------------------------------------------------------------------

def test_name_each_island(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    c.post("/island/name", data={"t": jid, "title": "Python Point", "name": "Shelly"})
    c.post("/island/name", data={"t": "", "title": "Home Reef"})
    fleet = garden.turtles(v, "universal", "en")
    assert fleet[0]["title"] == "Home Reef" and [t for t in fleet if t["id"] == jid][0]["title"] == "Python Point"
    page = html.unescape(c.get(f"/island?t={jid}").text)
    assert "Python Point" in page and "Shelly carries the island for Python Basics." in page


def test_shells_buy_things_for_each_island(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    st = garden.stats(v)
    assert garden.wallet(v, st)["balance"] == garden.earned(st)
    assert garden.buy(v, "decor", "lighthouse", st) == "Not enough shells yet. Study a little more and come back."
    assert garden.buy(v, "decor", "spaceship", st) == "That isn't in the shop."
    for _ in range(5):
        _plant(v, goal=90)  # 5 x 18 shells
    c.post("/island/buy", data={"t": jid, "kind": "decor", "key": "lanterns"})
    c.post("/island/buy", data={"t": jid, "kind": "theme", "key": "beach"})
    w = garden.wallet(v, garden.stats(v))
    assert {"decor:lanterns", "theme:beach"} <= w["owned"] and w["spent"] == 35 + 40
    look = garden.looks(v, jid)
    assert look["theme"] == "beach" and look["decor"] == ["lanterns"]
    assert garden.looks(v, "")["theme"] == "meadow"  # every island has its own look
    c.post("/island/look", data={"t": jid, "kind": "decor", "key": "lanterns"})  # take it away again
    assert garden.looks(v, jid)["decor"] == []
    garden.set_look(v, jid, "water", "lagoon")  # not bought: nothing changes
    assert garden.looks(v, jid)["water"] == "sea"
    page = html.unescape(c.get(f"/island?t={jid}").text)
    assert "Decorate Python Basics" in page and "Sandy beach" in page and "On this island" in page


def test_island_art_draws_looks_visitors_seasons_and_states():
    plants = [{"kind": "oak", "goal": 25, "state": "grown"}, {"kind": "pine", "goal": 25, "state": "wilted"},
              {"kind": "tulip", "goal": 25, "state": "dead"}]
    svg = garden.island_svg(plants, {"owl"}, 1, hour=12, villain=4, season_now="winter", visitor="dolphin",
                            look={"theme": "snow", "sky": "balloons", "water": "deep", "decor": ["flag", "lighthouse"]},
                            title="My <Island>")
    assert "isle-plant wilted" in svg and "isle-plant dead" in svg and "isle-villain attack" in svg
    assert "isle-visitor-dolphin" in svg and "isle-season" in svg and "isle-balloon" in svg
    assert "My &lt;Island&gt;" in svg and "<Island>" not in svg
    assert 'data-friend="owl"' in garden.island_svg([], {"owl"}, 1) and 'data-friend="owl"' not in garden.island_svg([], {"owl"}, 1, fled=True)


# ---- Tempo in notifications ----------------------------------------------------------------------------

def test_island_notifications_carry_tempo(tmp_path):
    v, c, jid = _python(tmp_path)
    assert not [a for a in reminders.plan(v)["auto"] if a["key"] in ("villain", "wilt")]
    garden.set_on(v, True)
    _plant(v)
    garden.start(v, "oak", 25, "anywhere", jid)
    plan = reminders.plan(v)
    keys = {a["key"].split(":")[0]: a for a in plan["auto"]}
    assert keys["trip"]["exact"] and keys["trip"]["picture"] == "tempo_cheer"
    assert keys["villain"]["picture"] == "villain" and "at your shore" in keys["villain"]["title"]
    assert keys["wilt"]["picture"] == "villain" and keys["dying"]["picture"] == "tempo_sad"
    assert all(a.get("picture") for a in plan["auto"])
    for a in plan["auto"]:
        assert os.path.exists(f"inpace/static/notify/{a['picture']}.png")
        assert os.path.exists(f"mobile/icon/res/drawable-nodpi/{a['picture']}.png")
    reminders.set_auto(v, {k: k != "island" for k in reminders.AUTO_KINDS}, 7)
    assert not [a for a in reminders.plan(v)["auto"] if a["key"].startswith(("trip", "villain"))]


def test_computer_shows_the_villain_once_in_the_evening(tmp_path, monkeypatch):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    _plant(v)
    away = time.time() - 8 * 86400
    monkeypatch.setattr(garden, "last_active", lambda v_: away)
    evening = datetime.now().replace(hour=19)
    items = reminders.due_now(v, now_local=evening)
    villain = [i for i in items if i["log"][0] == "island_villain"]
    assert villain and villain[0]["picture"] == "villain"
    reminders.mark_sent(v, villain[0])
    assert not [i for i in reminders.due_now(v, now_local=evening) if i["log"][0] == "island_villain"]
    assert reminders.due_now(v, now_local=evening.replace(hour=9)) == []


def test_windows_and_linux_get_tempos_face(monkeypatch):
    from inpace import notifier
    xml = notifier.windows_toast_xml("t", "b", "inpace://go/", image=notifier._icon_png("tempo_cheer"))
    assert 'placement="appLogoOverride"' in xml and "tempo_cheer.png" in xml
    assert notifier._icon_png("../../etc/passwd").endswith("icon-256.png")


# ---- your own turtle -----------------------------------------------------------------------------------

def test_first_run_makes_your_turtle(tmp_path):
    from starlette.testclient import TestClient
    from inpace.app import create_app
    from inpace.vault import Vault
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    page = c.get("/setup").text
    assert "data-turtle-maker" in page and 'name="acc" value="crown"' in page
    c.post("/setup", data={"name": "Mona", "shell": "3", "scarf": "1", "skin": "2", "acc": "crown"})
    me = v.me
    assert me["avatar"] == {"shell": 3, "scarf": 1, "skin": 2, "acc": "none"}  # the crown costs shells
    assert me["color"] == "#7A4FA0"  # your colour follows the shell
    assert 'class="avatar turtle"' in c.get("/").text


def test_your_turtle_travels_on_your_contact_card(tmp_path):
    v, c, jid = _python(tmp_path)
    c.post("/settings/turtle", data={"shell": "1", "scarf": "4", "skin": "0", "acc": "glasses"})
    card = exchange.make_contact_card(v)
    assert card["avatar"]["acc"] == "glasses"
    exchange.check_contact_card(card)  # the turtle isn't signed, so older versions still accept the card
    from tests.test_app import client as mk
    v2, c2 = mk(tmp_path / "friend", "Sara")
    r = c2.post("/people/add", data={"card": json.dumps(card), "relationship": "checks_me"})
    friend = v2.person(card["id"])
    assert json.loads(friend["avatar"])["shell"] == 1
    assert 'class="avatar turtle"' in c2.get("/people").text
    card["avatar"] = {"shell": 99, "acc": "<script>"}  # junk becomes a plain turtle
    assert mascot.clean_avatar(card["avatar"]) == {"shell": 0, "scarf": 0, "skin": 0, "acc": "none"}


def test_share_a_picture_of_your_turtle(tmp_path):
    v, c, jid = _python(tmp_path)
    c.post("/settings/turtle", data={"shell": "5", "scarf": "0", "skin": "1", "acc": "cap"})
    r = c.get("/me/turtle.svg")
    assert r.headers["content-type"].startswith("image/svg+xml") and "Omar" in r.text and "attachment" in r.headers["content-disposition"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    r = c.post("/me/turtle.png", data={"png": "data:image/png;base64," + base64.b64encode(png).decode()})
    assert r.content == png and "my%20turtle.png" in r.headers["content-disposition"]
    r = c.post("/me/turtle.png", data={"png": "data:text/html;base64,PGI+"}, follow_redirects=False)
    assert r.status_code == 303


def test_hats_from_the_shop(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    for _ in range(5):
        _plant(v, goal=90)
    c.post("/settings/turtle", data={"acc": "crown"})
    assert v.me["avatar"]["acc"] == "none"
    c.post("/island/buy", data={"kind": "accessory", "key": "crown"})
    c.post("/settings/turtle", data={"acc": "crown"})
    assert v.me["avatar"]["acc"] == "crown"


def test_home_shows_the_island(tmp_path, monkeypatch):
    v, c, jid = _python(tmp_path)
    assert "isle-home" not in c.get("/").text  # nothing until the island is on
    garden.set_on(v, True)
    _plant(v, journey=jid)
    page = html.unescape(c.get("/").text)
    assert "isle-home" in page and "Chapter" in page and "Start a focus trip" in page and "shells" in page
    assert "New chapter" not in page  # Home only reads; chapters open on the island page
    monkeypatch.setattr(garden, "last_active", lambda v_: time.time() - 8 * 86400)
    page = html.unescape(c.get("/").text)
    assert "The Fog of Someday:" in page and "I'm at your shore now" in page


def test_tempo_shows_in_the_test_notification(tmp_path, monkeypatch):
    from inpace import notifier
    v, c, jid = _python(tmp_path)
    sent = []
    monkeypatch.setattr(notifier, "notify", lambda title, body, path="/", home=None, picture="": sent.append(picture) or True)
    c.post("/reminders/test", data={"kind": "notify"})
    assert sent == ["tempo_wave"]
    page = c.get("/reminders").text
    assert '/static/notify/tempo_wave.png' in page and "notif-preview" in page
    assert reminders.plan(v)["test"]["picture"] == "tempo_wave"  # the Android test notification too
