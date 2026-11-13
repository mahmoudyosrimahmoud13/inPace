"""v1.16: Back that makes sense (no stale pages), the new Tempo, and Tempo's island (reward mode with a story)."""
import html
import json
import time

from inpace import garden, island_story
from inpace.mascot import MOODS, mascot
from tests.test_app import client


def _python(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    return v, c, v.journey_for_course("python-basics")


def test_pages_are_never_cached_and_forms_can_replace_the_page(tmp_path):
    v, c, jid = _python(tmp_path)
    r = c.get(f"/learn/{jid}")
    assert r.headers["cache-control"] == "no-store"
    r = c.post("/settings", data={"name": "Omar", "lang": "ar"}, headers={"X-InPace-Nav": "1"})
    assert r.status_code == 200 and r.json()["go"].startswith("/settings")
    assert v._meta("lang") == "ar"
    r = c.post("/settings", data={"name": "Omar", "lang": "en"}, follow_redirects=False)
    assert r.status_code == 303  # without the header it's a normal redirect


def test_quiz_result_is_its_own_page_so_back_never_resends_answers(tmp_path):
    v, c, jid = _python(tmp_path)
    for les in v.get_course("python-basics").modules[0]["lessons"]:
        c.post(f"/learn/{jid}/lesson/{les['id']}/done", data={})
    page = c.get(f"/learn/{jid}/task/m1-quiz/quiz").text
    assert 'name="inpace-dispose"' in page and "data-nav-form" in page
    import re
    seed = re.search(r'name="seed" value="([0-9a-f]+)"', page).group(1)
    r = c.post(f"/learn/{jid}/task/m1-quiz/quiz", data={"seed": seed}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith(f"/learn/{jid}/task/m1-quiz/quiz/result")
    result = html.unescape(c.get(r.headers["location"]).text)
    assert "0 of 3" in result and 'name="inpace-dispose"' in result


def test_new_tempo_draws_every_mood_with_its_own_ids():
    a, b = str(mascot("happy")), str(mascot("happy"))
    assert 'clipPath id="tempo-shell-happy' in a and a != b  # two Tempos on one page don't share ids
    for mood in MOODS:
        assert f"tempo-{mood}" in str(mascot(mood, 80))


def test_island_is_off_until_you_turn_it_on(tmp_path):
    v, c, jid = _python(tmp_path)
    page = html.unescape(c.get("/island").text)
    assert "Turn on Tempo's island" in page and "The Slowest Turtle" in page
    c.post("/island/mode", data={"on": "1"})
    page = html.unescape(c.get("/island").text)
    assert "Start a focus trip" in page and "Tempo's logbook" in page and "Clear sea today" in page


def test_a_trip_grows_a_plant_and_resting_keeps_the_minutes(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    c.post("/island/start", data={"kind": "sunflower", "minutes": "10", "mode": "anywhere", "journey": jid})
    trip = garden.active(v)
    assert trip["state"] == "running" and trip["goal"] == 10 and trip["journey"] == jid
    v.db.execute("UPDATE garden SET run_from=? WHERE id=?", (time.time() - 240, trip["id"]))
    c.post("/island/rest")
    rested = garden.active(v)
    assert rested["state"] == "resting" and 230 < rested["banked"] < 260
    c.post("/island/start", data={})  # carry on with the same sprout
    assert garden.active(v)["id"] == trip["id"] and garden.active(v)["state"] == "running"
    v.db.execute("UPDATE garden SET banked=600 WHERE id=?", (trip["id"],))
    page = html.unescape(c.get("/island/trip").text)
    assert "joined the island" in page
    assert len(garden.grown(v)) == 1 and garden.active(v) is None
    # it grows on the course's own turtle, not on Tempo
    fleet = garden.turtles(v, "universal", "en")
    assert fleet[0]["tempo"] and not fleet[0]["plants"]
    assert [t for t in fleet if t["id"] == jid][0]["plants"]


def test_phone_down_mode_pauses_while_away(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    c.post("/island/start", data={"kind": "oak", "minutes": "25", "mode": "phone"})
    c.post("/island/pause")
    assert garden.active(v)["state"] == "paused"
    r = c.post("/island/resume").json()
    assert r["state"] == "running" and not r["grown"]


def test_learning_unlocks_friends_and_plants(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    assert garden.unlocked(v)["plants"] == {"sunflower", "oak"} and not garden.unlocked(v)["friends"]
    page = html.unescape(c.post(f"/learn/{jid}/lesson/m1-l1/done", data={}).text)  # lands on the next lesson
    assert "New on your island!" in page and "Zoon the snail moved in." in page
    assert "New on your island!" not in html.unescape(c.get("/").text)  # only once
    assert "snail" in garden.unlocked(v)["friends"]


def test_the_weather_is_your_pace_and_the_story_waits_in_fog(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    now = time.time()
    assert garden.weather(v, now=now)["fog"] == 0
    assert garden.weather(v, now=now + 3 * 86400)["fog"] == 1
    assert garden.weather(v, now=now + 5 * 86400)["fog"] == 2
    assert garden.weather(v, now=now + 9 * 86400)["fog"] == 3
    st = garden.stats(v)
    st["plants"] = 6
    tale = garden.story_state(v, st, {"fog": 2, "days": 5, "fair": False}, "en")
    assert [c["key"] for c in tale["chapters"]] == []  # thick fog: nothing new opens
    tale = garden.story_state(v, st, {"fog": 0, "days": 0, "fair": True}, "en")
    keys = [c["key"] for c in tale["chapters"]]
    assert keys[:4] == ["c1", "c2", "c3", "c4"] and "fog_lifts" in keys and "fair_winds" in keys
    st["plants"] = 35  # the big fight also needs a few days in a row
    tale = garden.story_state(v, st, {"fog": 0, "days": 0, "fair": False}, "en")
    assert "c8" not in [c["key"] for c in tale["chapters"]]


def test_two_story_worlds_in_two_languages():
    uni = island_story.chapter("c6", "universal", "en")
    arab = island_story.chapter("c6", "arab", "en")
    assert "Lighthouse of Real" in " ".join(uni["paras"]) and "Pharos of Alexandria" in " ".join(arab["paras"])
    ar = island_story.chapter("c1", "arab", "ar")
    assert "تيتا لؤلؤة" in " ".join(ar["paras"]) and "الإسكندرية" in " ".join(ar["paras"])
    assert island_story.world_for("", "ar") == "arab" and island_story.world_for("universal", "ar") == "universal"
    for key, *_ in island_story.CHAPTERS:
        for w in island_story.WORLDS:
            for lang in ("en", "ar"):
                assert "{" not in " ".join(island_story.chapter(key, w, lang)["paras"])


def test_island_page_shows_fleet_chart_and_rename(tmp_path):
    v, c, jid = _python(tmp_path)
    garden.set_on(v, True)
    page = html.unescape(c.get("/island").text)
    assert "isle-fleet" in page and "sea-chart" in page
    c.post("/island/name", data={"t": jid, "name": "Shelly"})
    assert json.loads(v._meta("island_names"))[jid] == "Shelly"
    assert "Shelly carries the island for Python Basics" in html.unescape(c.get(f"/island?t={jid}").text)
