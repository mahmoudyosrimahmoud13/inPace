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

def test_one_island_with_its_own_name(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    _plant(v, journey=jid)
    _plant(v)
    c.post("/island/name", data={"title": "Home Reef"})
    isle = garden.island(v, "en")
    assert isle["title"] == "Home Reef" and len(isle["plants"]) == 2  # trips for a course and for anything else
    page = html.unescape(c.get("/island").text)
    assert "Home Reef" in page and "isle-fleet" not in page and "carries the island for" not in page


def test_shells_buy_things_for_the_island(tmp_path):
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
    look = garden.looks(v, "")
    assert look["theme"] == "beach" and look["decor"] == ["lanterns"]
    c.post("/island/look", data={"kind": "decor", "key": "lanterns"})  # take it away again
    assert garden.looks(v, "")["decor"] == []
    garden.set_look(v, "", "water", "lagoon")  # not bought: nothing changes
    assert garden.looks(v, "")["water"] == "sea"
    page = html.unescape(c.get("/island").text)
    assert "Decorate Tempo's Island" in page and "Sandy beach" in page and "On this island" in page


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
    assert "trip" not in keys  # the phone's trip notification schedules "your plant is ready" itself
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


# ---- the focus trip in a notification ------------------------------------------------------------------

def test_the_phone_gets_the_trip_for_its_countdown(tmp_path, monkeypatch):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    assert c.get("/island/live.json").json() == {"trip": None}
    assert 'id="inpace-trip"' not in c.get("/").text  # only the phone app gets it
    c.post("/island/start", data={"kind": "oak", "minutes": "25", "mode": "anywhere", "journey": jid})
    live = c.get("/island/live.json").json()["trip"]
    assert live["state"] == "running" and live["title"] == "Focus trip: Oak"
    assert abs(live["ends_ms"] / 1000 - (time.time() + 25 * 60)) < 5
    assert live["done_title"] == "Your Oak is ready!" and "phone" not in live["mode"]
    monkeypatch.setenv("INPACE_MOBILE", "android")
    page = c.get("/").text
    data = json.loads(page.split('<script type="application/json" id="inpace-trip">')[1].split("</script>")[0])
    assert data["id"] == live["id"] and data["state"] == "running"
    c.post("/island/rest")
    page = c.get("/").text
    assert '<script type="application/json" id="inpace-trip">null</script>' in page  # resting: the countdown goes away
    v._set_meta("lang", "ar")
    c.post("/island/start", data={})
    assert c.get("/island/live.json").json()["trip"]["title"] == "رحلة تركيز: البلوط"


def test_the_computer_says_when_the_trip_is_done(tmp_path, monkeypatch):
    from inpace import notifier
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    rang = []
    monkeypatch.setattr(notifier, "notify", lambda title, body, path="/", home=None, picture="": rang.append((title, picture)) or True)
    monkeypatch.setenv("INPACE_TEST_TRIP_TIMER", "1")
    c.post("/island/start", data={"kind": "oak", "minutes": "10", "mode": "anywhere", "journey": jid})
    v.db.execute("UPDATE garden SET banked=598 WHERE state='running'")
    v.db.commit()
    c.get("/")  # any page sets the timer for the trip's last second
    for _ in range(40):
        if rang:
            break
        time.sleep(0.2)
    assert rang == [("Your Oak is ready!", "tempo_cheer")]
    assert reminders.trip_done_now(v) is None  # said once


# ---- courses pay off, once each -----------------------------------------------------------------------

def _finish_lessons(v, c, jid, n):
    lessons = [les["id"] for m in v.get_course(v.journey(jid)["course_id"]).modules for les in m["lessons"]]
    for lid in lessons[:n]:
        c.post(f"/learn/{jid}/lesson/{lid}/done", data={})
    return lessons


def test_courses_give_chests_and_count_once(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    before = garden.earned(garden.stats(v))
    lessons = _finish_lessons(v, c, jid, 3)
    row = garden.course_rewards(v)[0]
    assert row["title"] == "Python Basics" and row["lessons"] == 3 and row["percent"] > 0
    assert garden.earned(garden.stats(v)) > before
    opened = [ch["at"] for ch in row["chests"] if ch["open"]]
    assert all(row["percent"] >= at for at in opened)
    # restart the course: the same lessons again don't pay twice
    v.db.execute("UPDATE journeys SET archived=1 WHERE id=?", (jid,))
    v.db.commit()
    jid2 = v.start_journey(v.journey(jid)["course_id"])
    _finish_lessons(v, c, jid2, 3)
    assert garden.stats(v)["lessons"] == 3 and len(garden.course_rewards(v)) == 1


def test_a_chest_opens_and_says_so(tmp_path, monkeypatch):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    real = v.progress
    monkeypatch.setattr(v, "progress", lambda j: {**real(j), "percent": 55})
    row = garden.course_rewards(v)[0]
    assert [ch["open"] for ch in row["chests"]] == [True, True, False] and row["chest_shells"] == 30
    assert row["next"] == {"at": 75, "shells": 30}
    news = garden.news(v)
    assert {n["key"] for n in news if n["kind"] == "chest"} == {"chest:python-basics:25", "chest:python-basics:50"}
    page = html.unescape(c.get("/").text)  # the news pop-up was used up by news() above; Home shows the course's shells
    assert "shells from this course" in page and "Next chest at 75%: 30 shells" in page
    # chests stay open even if the course grows and the percent drops
    monkeypatch.setattr(v, "progress", lambda j: {**real(j), "percent": 10})
    assert garden.course_rewards(v)[0]["chest_shells"] == 30
    monkeypatch.setattr(v, "progress", lambda j: {**real(j), "percent": 100, "finished": True})
    st = garden.stats(v)
    assert st["courses"] == 1 and "isle-trophy" in garden.island_svg([], set(), 1, trophies=st["courses"])


# ---- sharing the island --------------------------------------------------------------------------------

def test_friends_see_your_island(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    _plant(v, "oak")
    c.post("/island/name", data={"title": "Omar's Reef"})
    card = exchange.make_contact_card(v)
    assert card["island"]["title"] == "Omar's Reef" and card["island"]["plants"][0]["kind"] == "oak"
    exchange.check_contact_card(card)  # still a valid card
    from tests.test_app import client as mk
    v2, c2 = mk(tmp_path / "friend", "Sara")
    c2.post("/people/add", data={"card": json.dumps(card), "relationship": "checks_me"})
    assert "See their island" in c2.get("/people").text
    page = html.unescape(c2.get(f"/people/{card['id']}/island").text)
    assert "Omar's Reef" in page and "island-art" in page
    garden.set_on(v2, True)
    assert "Your friends' islands" in html.unescape(c2.get("/island").text)
    # junk in a shared island is dropped, never drawn
    junk = garden.clean_snapshot({"v": 1, "title": "<b>x</b>" * 20, "plants": [{"kind": "<script>", "goal": 5, "state": "grown"}],
                                  "friends": ["owl", "dragon"], "look": {"theme": "lava", "decor": ["lighthouse", "bomb"]}})
    assert junk["plants"] == [] and junk["friends"] == ["owl"] and junk["look"]["theme"] == "meadow"
    assert junk["look"]["decor"] == ["lighthouse"] and len(junk["title"]) <= 30


def test_you_can_keep_your_island_private(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    c.post("/island/sharing", data={"on": "0"})
    assert "island" not in exchange.make_contact_card(v)
    assert "Your island is private." in html.unescape(c.get("/island").text)
    c.post("/island/sharing", data={"on": "1"})
    assert "island" in exchange.make_contact_card(v)
    garden.set_on(v, False)
    assert "island" not in exchange.make_contact_card(v)  # no island when reward mode is off


def test_progress_files_update_the_island_your_checker_sees(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    _plant(v, "pine")
    data = exchange.make_progress_file(v, jid)
    assert data["island"]["plants"][0]["kind"] == "pine"


def test_share_a_picture_of_your_island(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    _plant(v, "oak")
    r = c.get("/island/share.svg")
    assert r.headers["content-type"].startswith("image/svg+xml") and "island-art" in r.text and "Tempo's Island" in html.unescape(r.text)
    assert "data-share-island" in c.get("/island").text
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    r = c.post("/island/share.png", data={"png": "data:image/png;base64," + base64.b64encode(png).decode()})
    assert r.content == png and "Island.png" in r.headers["content-disposition"]


# ---- a change always shows right away ------------------------------------------------------------------

def test_messages_go_before_the_section_so_the_page_loads_again(tmp_path):
    v, c, jid = _python(tmp_path)
    r = c.post("/settings/colors", data={"accent": "mint"}, headers={"X-InPace-Nav": "1"})
    go = r.json()["go"]
    assert go == "/settings?ok=Colors%20saved.#colors"  # not "/settings#colors?ok=…", which only scrolls
    garden.set_on(v, True)
    for _ in range(3):
        _plant(v, goal=90)
    r = c.post("/island/buy", data={"kind": "theme", "key": "beach"}, headers={"X-InPace-Nav": "1"})
    assert r.json()["go"].startswith("/island?ok=") and r.json()["go"].endswith("#shop")
    r = c.post("/island/buy", data={"kind": "decor", "key": "lighthouse"}, follow_redirects=False)
    assert "#shop" in r.headers["location"] and r.headers["location"].index("?") < r.headers["location"].index("#")
    js = open("inpace/static/app.js", encoding="utf-8").read()
    assert "goFresh(data.go)" in js and "location.reload()" in js


def test_diagrams_have_zoom_and_full_screen():
    js = open("inpace/static/app.js", encoding="utf-8").read()
    for part in ('data-z="in"', 'data-z="out"', 'data-z="fit"', 'data-z="full"', "requestFullscreen", "pinch"):
        assert part in js
