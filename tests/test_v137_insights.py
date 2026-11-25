"""v1.37: the Insights page: focus per day, lessons, best hours, courses, and sprints against their plan."""
import datetime as dt
import json

from inpace import focus, insights, roadmaps
from tests.test_app import client
from tests.test_v111 import _lesson
from tests.test_v135 import SPRINT


def test_study_counts_focus_lessons_streak_and_best_hour(tmp_path):
    v, c = client(tmp_path, "Mona")
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    jid = v.journeys()[0]["id"]
    _lesson(c, v, jid, "m1-l1")
    today = dt.date.today().isoformat()
    v._set_meta(focus.DAYS_KEY, json.dumps({f"{today}T09": 1800, f"{today}T16": 3600,
                                            (dt.date.today() - dt.timedelta(days=1)).isoformat() + "T16": 600}))
    st = insights.study(v)
    assert st["focus"][-1] == 90 and st["focus"][-2] == 10
    assert st["lessons"][-1] == 1 and st["streak"] == 2
    assert st["top_hour"] == 16 and st["hours"][16] == 70
    assert st["this_week"]["focus"] == 100 and st["courses"][0]["done"] == 1
    assert st["active_days"] == 2


def test_the_page_draws_the_charts_and_the_sprint(tmp_path):
    v, c = client(tmp_path, "Mona")
    r = c.get("/insights")
    assert r.status_code == 200 and "Nothing to show yet" in r.text
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    jid = v.journeys()[0]["id"]
    _lesson(c, v, jid, "m1-l1")
    rm = roadmaps.parse({**SPRINT, "id": "ml-sprint"}, "mine")
    rm = roadmaps.start_sprint(rm, {}, 7, 12, dt.date.today().isoformat())
    roadmaps.save(v.home, rm)
    c.post("/roadmaps/ml-sprint/sprint/tick", data={"course": "python-basics", "i": "0", "on": "1"})
    r = c.get("/insights")
    assert r.status_code == 200
    assert 'class="chart"' in r.text and "Lessons finished per day" in r.text
    assert "ML sprint" in r.text and 'class="ch-done"' in r.text and "worked on 1 of 1 days" in r.text
    assert 'href="/insights"' in r.text  # in the menu


def test_sprint_plan_against_ticks():
    run = {"start": dt.date.today().isoformat(), "days": 3, "hours": 2, "hour": 0, "plan": {"a": [1, 1], "b": [2, 3]},
           "ticks": {"a": [0]}, "log": [[dt.datetime.now().isoformat(), "a", 0, True]], "tasks": {}}
    rm = {"id": "s", "title": "S", "steps": [{"course": "a"}, {"course": "b"}], "sprint_run": run}
    sp = {"running": True, "day": 1, "days": 3, "percent": 33, "focus_goal": 120,
          "steps": [{"course": "a", "units": 1, "optional": False, "range": [1, 1]},
                    {"course": "b", "units": 2, "optional": False, "range": [2, 3]}],
          "strip": [{"d": 1, "ticks": 1, "focus": 30}, {"d": 2, "ticks": 0, "focus": 0}, {"d": 3, "ticks": 0, "focus": 0}]}
    a = insights.sprint(rm, sp)
    assert a["expected"] == [1, 1, 3] and a["done"] == [1] and a["on_track"] and a["worked"] == 1
    svg = insights.lines(a["expected"], a["done"], "t", ["1", "2", "3"])
    assert 'class="ch-plan"' in svg and 'class="ch-done"' in svg
    assert 'class="ch-goal"' in insights.bars(a["focus"], ["1", "2", "3"], "t", " min", goal=120, mark=0)
    assert insights.sprint(rm, {"running": False}) is None
