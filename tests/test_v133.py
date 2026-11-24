"""v1.33: sprints (a short, intensive run of a roadmap: a day for each course, tasks you tick, a log and a report
for your checker), adding a roadmap from a file or pasted text, and making a sprint with AI."""
import datetime as dt
import json

import pytest
from starlette.testclient import TestClient

from inpace import library, roadmaps
from inpace.app import SAMPLES, create_app
from inpace.course import course_to_pack, files_from_folder, load_course
from inpace.vault import Vault



def lib_index() -> dict:
    """A library list like the real one: two sample courses, and one roadmap (as in test_v124)."""
    courses = []
    for cid in ("python-basics", "fastapi"):
        c = load_course(files_from_folder(SAMPLES / cid))
        courses.append({"id": c.id, "title": c.title, "description": c.description, "language": c.language,
                        "hash": c.hash, "modules": len(c.modules), "lessons": c.lesson_count, "minutes": 120,
                        "tags": ["python"], "author": {"name": "inPace", "verified": True},
                        "pack": library.SITE + f"packs/{cid}.zip"})
    rms = [{"id": "python-web", "title": "Python for the web", "description": "From your first line to an API.",
            "language": "en", "author": {"name": "inPace", "verified": True}, "tags": ["python"],
            "steps": [{"course": "python-basics", "note": "Start here."}, {"course": "fastapi"}], "minutes": 240,
            "hash": "aaa"}]
    return {"inpace": "library", "v": 1, "courses": courses, "roadmaps": rms}

SPRINT = """
id: ml-sprint
title: "ML sprint: 7 days"
description: A test sprint.
language: en
author: Mahmoud Yosri
sprint: {days: 7, hours: 12}
steps:
  - course: python-basics
    day: 1
    note: 'Day 1: the basics.'
    tasks:
      - Modules 1-3
      - The quiz
  - course: fastapi
    day: 2-3
    tasks: [Build the API, Tests over 80%]
  - course: not-anywhere
    optional: true
"""


@pytest.fixture
def app(tmp_path, monkeypatch):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    (v.home / "library.json").write_text(json.dumps(lib_index()), encoding="utf-8")
    monkeypatch.setattr(library, "download", lambda e: course_to_pack(load_course(files_from_folder(SAMPLES / e["id"])), True))
    return v, c


# ---- the roadmap format --------------------------------------------------------------------------------------

def test_a_sprint_roadmap_keeps_its_days_and_tasks():
    rm = roadmaps.parse(SPRINT, "link")
    assert rm["sprint"] == {"days": 7, "hours": 12}
    assert rm["steps"][0]["day"] == 1 and rm["steps"][0]["tasks"] == ["Modules 1-3", "The quiz"]
    assert rm["steps"][1]["day"] == "2-3"
    again = roadmaps.parse(roadmaps.to_yaml(rm), "link")  # the file you download reads back the same
    assert roadmaps.fingerprint(again) == roadmaps.fingerprint(rm)
    shared = roadmaps.parse(roadmaps.share_data(rm, False), "link")  # and so does a link
    assert shared["sprint"] == rm["sprint"] and shared["steps"][1]["tasks"] == ["Build the API", "Tests over 80%"]


def test_old_roadmaps_keep_their_fingerprint():
    rm = roadmaps.parse({"title": "T", "steps": [{"course": "a", "note": "n"}, {"course": "b", "optional": True}]})
    core = {"title": "T", "description": "", "steps": [{"course": "a", "note": "n"}, {"course": "b", "optional": True}]}
    import hashlib
    assert roadmaps.fingerprint(rm) == hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:16]


def test_a_day_out_of_the_sprint_is_a_clear_problem():
    with pytest.raises(roadmaps.RoadmapError) as e:
        roadmaps.parse({"title": "T", "sprint": {"days": 3}, "steps": [{"course": "a", "day": 5}]})
    assert "from 1 to 3" in str(e.value)


def test_courses_without_a_day_are_spread_by_length():
    rm = roadmaps.parse({"title": "T", "steps": [{"course": "a"}, {"course": "b"}, {"course": "x", "optional": True},
                                                 {"course": "c"}]})
    plan = roadmaps.auto_plan(rm, {"a": 600, "b": 60, "c": 60}, 4)
    assert plan["a"][0] == 1 and plan["c"][1] == 4  # the long course takes the first days, the last ends on day 4
    assert plan["x"] == plan["b"]  # an optional course goes with the one before it
    assert all(1 <= d <= 4 for r in plan.values() for d in r)


def test_a_plan_made_for_7_days_is_squeezed_into_fewer():
    rm = roadmaps.parse(SPRINT, "link")
    plan = roadmaps.auto_plan(rm, {}, 4)
    assert plan["python-basics"] == [1, 1] and max(plan["fastapi"]) <= 4


# ---- running a sprint ----------------------------------------------------------------------------------------

def _status(rm, finished=()):
    steps = [{**s, "n": i + 1, "state": "done" if s["course"] in finished else "start", "optional": bool(s.get("optional")),
              "title": s["course"], "minutes": 60} for i, s in enumerate(rm["steps"])]
    return {"steps": steps}


def test_ticks_count_and_are_logged_with_their_time():
    rm = roadmaps.start_sprint(roadmaps.parse(SPRINT, "link"), {}, 7, 12, "2026-11-25")
    rm = roadmaps.tick(rm, "python-basics", 0, True, at="2026-11-25T09:00:00")
    rm = roadmaps.tick(rm, "python-basics", 0, True, at="2026-11-25T09:01:00")  # ticking twice changes nothing
    rm = roadmaps.tick(rm, "python-basics", 9, True)  # no such task
    rm = roadmaps.parse(rm, "link")  # survives saving
    assert rm["sprint_run"]["ticks"] == {"python-basics": [0]}
    assert rm["sprint_run"]["log"] == [["2026-11-25T09:00:00", "python-basics", 0, 1]]
    sp = roadmaps.sprint_status(rm, _status(rm), dt.date(2026, 11, 26))
    assert sp["day"] == 2 and [s["course"] for s in sp["today"]] == ["fastapi", "not-anywhere"]  # optional rides along
    assert [s["course"] for s in sp["late"]] == ["python-basics"]  # 1 of its 2 tasks, and day 1 is over
    assert sp["strip"][0]["state"] == "late" and sp["strip"][1]["state"] == "today" and sp["strip"][0]["ticks"] == 1
    assert sp["percent"] == 25 and sp["active_days"] == 1


def test_a_finished_course_counts_as_proven():
    rm = roadmaps.start_sprint(roadmaps.parse(SPRINT, "link"), {}, 7, 12, "2026-11-25")
    sp = roadmaps.sprint_status(rm, _status(rm, finished={"python-basics"}), dt.date(2026, 11, 26))
    first = sp["steps"][0]
    assert first["sprint_done"] and first["proven"] and sp["late"] == []
    text = roadmaps.report(rm, sp, "Mona")
    assert "Course finished in inPace" in text and "Not started" in text and "| 2-3 | fastapi |" in text


def test_you_can_change_the_days_and_tasks_and_share_your_version():
    rm = roadmaps.start_sprint(roadmaps.parse(SPRINT, "link"), {}, 7, 12, "2026-11-25")
    rm = roadmaps.tick(rm, "fastapi", 1, True)
    rm = roadmaps.customize(rm, 5, 10, {"fastapi": "4"}, {"fastapi": ["Only the API"], "python-basics": ["Modules 1-3", "The quiz"]})
    run = roadmaps.parse(rm, "link")["sprint_run"]
    assert run["days"] == 5 and run["plan"]["fastapi"] == [4, 4]
    assert run["tasks"] == {"fastapi": ["Only the API"]}  # unchanged tasks aren't stored as your own
    assert "fastapi" not in run["ticks"]  # task 2 is gone, so is its tick
    plan = roadmaps.parse(roadmaps.to_yaml(roadmaps.as_plan(rm)), "link")
    assert plan["sprint"] == {"days": 5, "hours": 10} and plan["steps"][1] == {**plan["steps"][1], "day": 4, "tasks": ["Only the API"]}
    assert "sprint_run" not in plan
    with pytest.raises(roadmaps.RoadmapError):
        roadmaps.customize(rm, 5, 10, {"fastapi": "9"}, {})


def test_library_updates_keep_your_sprint(app):
    v, c = app
    c.post("/roadmaps/python-web/follow")
    c.post("/roadmaps/python-web/sprint", data={"action": "start", "days": "3", "hours": "4", "start": "2026-11-25"})
    rm = roadmaps.get(v.home, "python-web")
    rm = roadmaps.tick(rm, "fastapi", 0, True)
    roadmaps.save(v.home, rm)
    idx = lib_index()
    idx["roadmaps"][0].update(description="Changed.", hash="bbb")
    assert roadmaps.sync_library(v.home, idx) == ["python-web"]
    after = roadmaps.get(v.home, "python-web")
    assert after["description"] == "Changed." and after["sprint_run"]["ticks"] == {"fastapi": [0]}


# ---- the app -------------------------------------------------------------------------------------------------

def test_add_a_roadmap_file_from_the_roadmaps_page(app):
    v, c = app
    page = c.get("/roadmaps").text
    assert "Add a roadmap file" in page and 'action="/roadmaps/import"' in page and 'href="/sprints"' in page
    r = c.post("/roadmaps/import", files={"file": ("ml.roadmap.yaml", SPRINT.encode(), "text/yaml")})
    assert r.status_code == 200 and "ML sprint: 7 days" in r.text and "Follow this roadmap" in r.text
    assert "A 7-day sprint" in r.text and "Build the API" in r.text
    r = c.post("/roadmaps/import", data={"text": "```yaml\n" + SPRINT + "\n```"})  # pasted, even with the fences
    assert "ML sprint: 7 days" in r.text
    r = c.post("/roadmaps/import", data={"text": "title: x\n"}, follow_redirects=False)
    assert r.status_code == 303 and "err=" in r.headers["location"]
    assert "A roadmap file" in c.get("/add").text and ".roadmap.yaml" in c.get("/open").text


def test_follow_start_tick_change_and_report(app):
    v, c = app
    r = c.post("/roadmaps/import", data={"text": SPRINT})
    data = r.text.split('name="data" value="')[1].split('"')[0]
    import html
    c.post("/roadmaps/shared", data={"data": html.unescape(data)})
    page = c.get("/roadmaps/ml-sprint").text
    assert "This roadmap is a sprint plan. Start it?" in page
    today = dt.date.today()
    c.post("/roadmaps/ml-sprint/sprint", data={"action": "start", "days": "7", "hours": "12", "start": today.isoformat()})
    page = c.get("/roadmaps/ml-sprint").text
    assert "Sprint · day 1 of 7" in page and "Modules 1-3" in page and "Change the plan" in page
    c.post("/roadmaps/ml-sprint/sprint/tick", data={"course": "python-basics", "i": "0", "on": "1"})
    assert roadmaps.get(v.home, "ml-sprint")["sprint_run"]["ticks"] == {"python-basics": [0]}
    r = c.post("/roadmaps/ml-sprint/sprint", data={"action": "plan", "days": "7", "hours": "12", "day_1": "1",
                                                     "tasks_1": "Modules 1-3\nThe quiz\nA mini project", "day_2": "2-3",
                                                     "tasks_2": "Build the API\nTests over 80%", "day_3": "", "tasks_3": ""})
    assert roadmaps.get(v.home, "ml-sprint")["sprint_run"]["tasks"] == {"python-basics": ["Modules 1-3", "The quiz", "A mini project"]}
    assert "A mini project" in c.get("/roadmaps/ml-sprint").text
    rep = c.get("/roadmaps/ml-sprint/sprint/report")
    assert rep.status_code == 200 and "# Sprint report: ML sprint: 7 days" in rep.text and "Ticked by the learner" in rep.text
    f = c.get("/roadmaps/ml-sprint/file?plan=1")
    assert "A mini project" in f.text and "sprint:" in f.text and "ticks" not in f.text
    home = c.get("/").text
    assert "Sprint · day 1 of 7" in home
    c.post("/roadmaps/ml-sprint/sprint", data={"action": "stop"})
    assert "sprint_run" not in roadmaps.get(v.home, "ml-sprint")


def test_edit_keeps_the_sprint(app):
    v, c = app
    rm = roadmaps.parse(SPRINT, "mine")
    rm = roadmaps.start_sprint(rm, {}, 7, 12, "2026-11-25")
    roadmaps.save(v.home, rm)
    c.post("/roadmaps/ml-sprint/edit", data={"title": "ML sprint: 7 days", "description": "x", "language": "en",
                                               "steps": json.dumps([{"course": "python-basics"}, {"course": "fastapi"}])})
    after = roadmaps.get(v.home, "ml-sprint")
    assert after["sprint"]["days"] == 7 and after["steps"][1]["tasks"] == ["Build the API", "Tests over 80%"]
    assert after["sprint_run"]["start"] == "2026-11-25"


def test_make_a_sprint_with_ai(app):
    v, c = app
    page = c.get("/roadmaps/ai").text
    assert "Make a sprint with AI" in page and 'name="goal"' in page
    r = c.post("/roadmaps/ai", data={"action": "prompt", "goal": "Get hired as an ML engineer", "days": "7", "hours": "12",
                                       "know": "Python", "notes": "", "language": "English"})
    assert "- fastapi:" in r.text and "sprint: {days: 7, hours: 12}" in r.text and "Copy prompt" in r.text
    r = c.post("/roadmaps/ai", data={"action": "check", "reply": "Here you go:\n```yaml\n" + SPRINT + "```\nGood luck!"})
    assert "ML sprint: 7 days" in r.text and "Follow this roadmap" in r.text
    r = c.post("/roadmaps/ai", data={"action": "check", "reply": "title: Broken\nsteps: []"})
    assert "A few things need fixing" in r.text


def test_the_ai_prompt_lists_only_real_courses():
    p = roadmaps.ai_prompt("Data", 5, 3, [{"id": "a-1", "title": "A", "lessons": 4, "minutes": 90}])
    assert "- a-1: A, 4 lessons, 1.5 h" in p and "5 days" in p and "Every day from 1 to 5" in p


def test_make_a_sprint_yourself_first_ai_is_one_way(app):
    v, c = app
    assert c.get("/roadmaps/new-sprint", follow_redirects=False).headers["location"] == "/sprints"
    hub = c.get("/sprints").text
    assert "Make it yourself" in hub and 'href="/roadmaps/new?sprint=1"' in hub and 'href="/roadmaps/ai"' in hub
    assert hub.index("Make it yourself") < hub.index("With AI")  # making it yourself comes first
    maker = c.get("/roadmaps/new?sprint=1").text
    assert "Make a sprint" in maker and 'name="sprint_days"' in maker and "Save and plan the days" in maker
    r = c.post("/roadmaps/new", data={"title": "My week", "description": "", "language": "en", "tags": "",
                                       "steps": json.dumps([{"course": "python-basics"}, {"course": "fastapi"}]),
                                       "sprint_days": "5", "sprint_hours": "6", "sprint_start": "2026-11-25"},
               follow_redirects=False)
    assert r.status_code == 303 and "plan=1" in r.headers["location"]
    rm = roadmaps.get(v.home, "my-week")
    assert rm["sprint"] == {"days": 5, "hours": 6} and rm["sprint_run"]["start"] == "2026-11-25"
    assert set(rm["sprint_run"]["plan"]) == {"python-basics", "fastapi"}
    page = c.get("/roadmaps/my-week?plan=1").text
    assert 'id="plan" open' in page and 'name="tasks_1"' in page
    # editing it later keeps the sprint, and the form can change its length
    c.post("/roadmaps/my-week/edit", data={"title": "My week", "description": "", "language": "en", "tags": "",
                                             "steps": json.dumps([{"course": "python-basics"}, {"course": "fastapi"}]),
                                             "sprint_days": "6", "sprint_hours": "6"})
    after = roadmaps.get(v.home, "my-week")
    assert after["sprint"]["days"] == 6 and after["sprint_run"]["start"] == "2026-11-25"
    assert 'href="/sprints"' in c.get("/roadmaps/ai").text
    hub = c.get("/sprints").text  # your sprints are listed on top
    assert "My week" in hub and hub.index("My week") < hub.index("Make it yourself")


def test_one_button_runs_the_whole_sprint_day_with_breaks(app):
    from inpace import focus
    v, c = app
    today = dt.date.today().isoformat()
    rm = roadmaps.start_sprint(roadmaps.parse(SPRINT, "mine"), {}, 7, 2, today)  # 2 hours a day
    roadmaps.save(v.home, rm)
    page = c.get("/roadmaps/ml-sprint").text
    assert 'id="sprint-timer"' in page and "Focus today:" in page and "goal 2 h" in page
    # opening the sprint puts its timer on screen by itself: ready, paused, counting nothing
    ready = focus.live(v)
    assert ready["on"] and ready["state"] == "paused" and ready.get("ready") and ready["sprint"]["block"] == 1
    assert "Your sprint timer is ready" in page and 'action="/timer/resume"' in page and "Start today's sprint" in page
    assert "Ready: press play" in page  # the floating timer's words
    c.get("/courses")  # leaving the sprint takes a timer you never started away again
    assert focus._load(v) is None
    c.post("/timer/stop")
    c.post("/timer/sprint", data={"rid": "ml-sprint", "rhythm": "50-10", "label": "Sprint day 1"})
    d = focus._load(v)
    assert d["goal"] == 50 * 60 and d["chain"]["phase"] == "focus" and d["chain"]["target"] == 7200
    assert "Focus block 1" in c.get("/roadmaps/ml-sprint").text

    def later(minutes):  # pretend the current block started that many minutes ago
        d = focus._load(v)
        d["run_from"] -= minutes * 60
        focus._save(v, d)

    later(50.2)  # the focus block ends: it's banked, and a break starts by itself
    live = focus.live(v)
    assert live["on"] and live["sprint"]["phase"] == "break" and live["switched"] == "break" and live["label"] == "Break"
    assert focus.today_seconds(v) == 3000
    assert focus.day_totals(v)[today] == 3000  # the break isn't counted
    assert "Break · 10 min left" in c.get("/roadmaps/ml-sprint").text
    later(10.1)  # the break ends: block 2 starts by itself
    live = focus.live(v)
    assert live["sprint"] == {"phase": "focus", "block": 2, "rid": "ml-sprint"} and live["goal"] == 50 * 60
    later(50.1)
    focus.live(v)  # block 2 done (100 min), break
    later(10.1)
    live = focus.live(v)
    assert live["goal"] == 20 * 60  # only 20 minutes left to reach 2 hours
    later(20.1)
    live = focus.live(v)
    assert not live["on"] and live.get("sprint_day_done") and focus.today_seconds(v) == 7200
    page = c.get("/roadmaps/ml-sprint").text
    assert "Focus today: <b>2 h 0 min</b>" in page and "Go on with today's sprint" in page
    assert "120 of 120 min focused today" in c.get("/").text
    rep = c.get("/roadmaps/ml-sprint/sprint/report").text
    assert "Focus timer (goal 2 h a day): day 1: 2 h 0 min" in rep


def test_time_away_after_a_break_is_never_counted(app):
    from inpace import focus
    v, c = app
    rm = roadmaps.start_sprint(roadmaps.parse(SPRINT, "mine"), {}, 7, 8, dt.date.today().isoformat())
    roadmaps.save(v.home, rm)
    focus.start_sprint(v, "ml-sprint", "Day 1", 8 * 3600, 25, 5)
    d = focus._load(v)
    d["run_from"] -= 3 * 3600  # you started a block and left for three hours
    focus._save(v, d)
    live = focus.live(v)
    assert live["state"] == "paused" and live["sprint"]["block"] == 2  # block 2 waits for you
    assert focus.today_seconds(v) == 25 * 60  # only the one block counts
    c.post("/timer/resume")
    assert focus._load(v)["state"] == "running"
    focus.start_sprint(v, "ml-sprint", "Day 1", 8 * 3600, 25, 5)
    d = focus._load(v)
    d["run_from"] -= 26 * 60
    focus._save(v, d)
    focus.live(v)  # now on a break
    before = focus.today_seconds(v)
    d = focus._load(v)
    d["run_from"] -= 3 * 60
    focus._save(v, d)
    c.post("/timer/stop")  # stopping during a break adds nothing
    assert focus.today_seconds(v) == before and focus._load(v) is None


def test_a_plain_timer_still_counts_toward_the_day(app):
    from inpace import focus
    v, c = app
    c.post("/timer/start", data={"minutes": "25"})
    d = focus._load(v)
    d["run_from"] -= 20 * 60
    focus._save(v, d)
    c.post("/timer/stop")
    assert 1190 <= focus.today_seconds(v) <= 1260


def test_sprints_have_their_own_place_in_the_menu(app):
    v, c = app
    for path in ("/", "/sprints", "/roadmaps"):
        page = c.get(path).text
        assert page.count('href="/sprints"') >= 2  # the sidebar, and the phone's More menu
    side = c.get("/sprints").text
    assert 'href="/sprints" class="on"' in side and 'href="/roadmaps" class=""' in side
    assert 'href="/sprints" class="on"' in c.get("/roadmaps/new?sprint=1").text
    assert 'href="/roadmaps" class="on"' in c.get("/roadmaps").text


def test_the_sprint_timer_shows_up_on_todays_courses_and_stays_away_once_stopped(app):
    from inpace import focus
    v, c = app
    c.post("/roadmaps/python-web/follow")
    c.post("/roadmaps/python-web/add/python-basics")
    c.post("/roadmaps/python-web/sprint", data={"action": "start", "days": "2", "hours": "3",
                                                  "start": dt.date.today().isoformat()})
    plan = roadmaps.get(v.home, "python-web")["sprint_run"]["plan"]
    jid = v.journey_for_course("python-basics") or c.post("/roadmaps/python-web/start/python-basics") and v.journey_for_course("python-basics")
    if plan["python-basics"][0] == 1:
        c.get(f"/learn/{jid}")
        d = focus._load(v)
        assert d and d.get("ready") and d["chain"]["rid"] == "python-web" and d["label"].startswith("Sprint day 1")
        c.post("/timer/stop")  # you don't want it today
        c.get(f"/learn/{jid}")
        assert focus._load(v) is None and focus.stopped_today(v, "python-web")


def test_the_phone_notification_knows_the_sprint(app, monkeypatch):
    from inpace import focus
    import inpace.app as app_mod
    v, c = app
    rm = roadmaps.start_sprint(roadmaps.parse(SPRINT, "mine"), {}, 7, 4, dt.date.today().isoformat())
    roadmaps.save(v.home, rm)
    focus.start_sprint(v, "ml-sprint", "Sprint day 1: Python", 4 * 3600, 50, 10)
    monkeypatch.setenv("INPACE_MOBILE", "1")
    page = c.get("/courses").text
    data = json.loads(page.split('id="inpace-trip">')[1].split("</script>")[0])
    assert data["title"] == "Sprint · focus block 1" and data["url"] == "/roadmaps/ml-sprint#sprint"
    assert data["done_title"] == "Break time" and data["next"][0]["title"] == "Back to focus"
    assert data["next"][0]["at_ms"] - data["ends_ms"] == 10 * 60 * 1000


def test_another_timer_waits_until_the_sprint_timer_is_stopped(app):
    from inpace import focus, garden
    v, c = app
    rm = roadmaps.start_sprint(roadmaps.parse(SPRINT, "mine"), {}, 7, 4, dt.date.today().isoformat())
    roadmaps.save(v.home, rm)
    c.post("/timer/sprint", data={"rid": "ml-sprint", "rhythm": "25-5"})
    sprint_id = focus._load(v)["id"]
    r = c.post("/timer/start", data={"minutes": "10"}, headers={"x-inpace-fetch": "1", "accept": "application/json"})
    assert "Stop the sprint timer first" in r.json()["error"] and r.json()["sprint"]["rid"] == "ml-sprint"
    assert focus._load(v)["id"] == sprint_id  # the sprint timer is untouched
    r = c.post("/timer/start", data={"minutes": "10"}, follow_redirects=False)
    assert r.status_code == 303 and "err=" in r.headers["location"]
    assert "data-ft-sprint-note" in c.get("/courses").text
    c.post("/timer/stop")
    c.post("/timer/start", data={"minutes": "10"})
    assert focus._load(v)["goal"] == 600 and not focus._load(v).get("chain")
    # and the other way round: a running timer has to be stopped before the sprint timer starts
    r = c.post("/timer/sprint", data={"rid": "ml-sprint", "rhythm": "25-5"}, follow_redirects=False)
    assert "err=" in r.headers["location"] and not focus._load(v).get("chain")
    with pytest.raises(focus.Busy):
        focus.start_sprint(v, "ml-sprint", "x", 3600)


def test_a_sprint_that_starts_at_4_pm_runs_4_pm_to_4_pm(app):
    v, c = app
    rm = roadmaps.start_sprint(roadmaps.parse(SPRINT, "mine"), {}, 7, 12, "2026-11-24", hour=16)
    run = roadmaps.parse(rm, "mine")["sprint_run"]
    assert run["hour"] == 16
    at = dt.datetime
    assert roadmaps.sprint_day(run, at(2026, 11, 24, 16, 5)) == 1
    assert roadmaps.sprint_day(run, at(2026, 11, 25, 2, 0)) == 1  # 2 am is still the first day
    assert roadmaps.sprint_day(run, at(2026, 11, 25, 16, 0)) == 2
    assert roadmaps.sprint_day(run, at(2026, 11, 24, 15, 0)) == 0  # not started yet
    assert roadmaps.day_start(run, 2) == at(2026, 11, 25, 16, 0)
    focus_hours = {"2026-11-24T17": 3000, "2026-11-24T23": 3000, "2026-11-25T02": 1800, "2026-11-25T17": 600}
    rm = roadmaps.tick(rm, "python-basics", 0, True, at="2026-11-25T03:10:00")
    sp = roadmaps.sprint_status(rm, _status(rm), at(2026, 11, 25, 3, 30), focus_hours)
    assert sp["day"] == 1 and sp["focus_today"] == 130 and sp["strip"][0]["focus"] == 130
    assert sp["strip"][1]["focus"] == 10 and sp["strip"][0]["ticks"] == 1
    assert "at 16:00 (each day runs 16:00 to 16:00)" in roadmaps.report(rm, sp)
    # through the app: the start form takes the time
    roadmaps.save(v.home, roadmaps.parse(SPRINT, "mine"))
    c.post("/roadmaps/ml-sprint/sprint", data={"action": "start", "days": "7", "hours": "12",
                                                 "start": dt.date.today().isoformat(), "start_time": "16:00"})
    assert roadmaps.get(v.home, "ml-sprint")["sprint_run"]["hour"] == 16
    assert 'name="start_time"' in c.get("/roadmaps/new?sprint=1").text.replace("sprint_start_time", "start_time")


def test_the_sprint_timer_counts_the_whole_sprint_day_even_past_midnight(app):
    from inpace import focus
    import time as _time
    v, c = app
    day_from = _time.time() - 10 * 3600  # the sprint day started 10 hours ago (say, 4 pm yesterday)
    old_hour = _time.strftime("%Y-%m-%dT%H", _time.localtime(day_from + 3600))
    v._set_meta(focus.DAYS_KEY, json.dumps({old_hour: 3 * 3600}))  # 3 hours focused before midnight
    focus.start_sprint(v, "ml-sprint", "Day 1", 4 * 3600, 90, 15, day_from=day_from)
    assert focus._load(v)["goal"] == 60 * 60  # only 1 hour left of the 4-hour goal
