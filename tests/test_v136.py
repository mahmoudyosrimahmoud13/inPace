"""v1.36: the sprint strip. A countdown to the end of today's sprint window at the top of every page: it follows
the clock (nothing pauses it), comes back after a restart, and goes away only when the sprint is stopped. The
focus timer is separate and still works."""
import datetime as dt
import json

import pytest
from starlette.testclient import TestClient

from inpace import roadmaps
from inpace.app import create_app
from inpace.vault import Vault

RM = {"id": "ml", "title": "ML sprint", "steps": [{"course": "python-basics"}, {"course": "fastapi"}]}
at = dt.datetime


def _run(start="2026-11-25", hour=12, end=0, hours=12, days=7):
    rm = roadmaps.start_sprint(roadmaps.parse(RM, "mine"), {}, days, hours, start, hour, end)
    return roadmaps.parse(rm, "mine")["sprint_run"]


def test_the_window_from_noon_to_midnight_is_12_hours():
    run = _run()
    w = roadmaps.sprint_window(run, at(2026, 11, 25, 15, 0))
    assert w["state"] == "open" and w["day"] == 1
    assert w["start"] == at(2026, 11, 25, 12) and w["end"] == at(2026, 11, 26, 0) and w["next"] == at(2026, 11, 26, 12)
    w = roadmaps.sprint_window(run, at(2026, 11, 26, 3, 0))  # 3 am: still day 1, the window is closed
    assert w["state"] == "closed" and w["day"] == 1
    assert roadmaps.sprint_window(run, at(2026, 11, 25, 11, 0))["state"] == "before"
    assert roadmaps.sprint_window(run, at(2026, 12, 1, 13, 0))["state"] == "open"  # day 7
    assert roadmaps.sprint_window(run, at(2026, 12, 2, 1, 0))["state"] == "done"
    assert roadmaps.sprint_window(run, at(2026, 12, 2, 12, 0)) is None  # over: no strip


def test_without_an_end_hour_the_window_is_the_hours_a_day():
    run = _run(hour=16, end=None, hours=12)
    assert "end" not in run
    w = roadmaps.sprint_window(run, at(2026, 11, 25, 17))
    assert w["end"] == at(2026, 11, 26, 4)  # 4 pm to 4 am


def test_you_can_move_the_end_of_the_window_later():
    rm = roadmaps.start_sprint(roadmaps.parse(RM, "mine"), {}, 7, 12, "2026-11-25", 12, 0)
    rm = roadmaps.customize(rm, 7, 12, {}, {}, 22)
    assert roadmaps.parse(rm, "mine")["sprint_run"]["end"] == 22
    rm = roadmaps.customize(rm, 7, 12, {}, {}, None)
    assert "end" not in roadmaps.parse(rm, "mine")["sprint_run"]
    rm = roadmaps.customize(rm, 7, 12, {}, {})  # not asked: kept as it was
    assert "end" not in rm["sprint_run"]


@pytest.fixture
def app(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    return v, c


def test_the_strip_shows_on_every_page_until_the_sprint_is_stopped(app):
    v, c = app
    now = dt.datetime.now()
    rm = roadmaps.start_sprint(roadmaps.parse(RM, "mine"), {}, 7, 12, now.date().isoformat(), now.hour, (now.hour + 2) % 24)
    roadmaps.save(v.home, rm)
    for path in ("/", "/courses", "/settings", "/library"):
        page = c.get(path).text
        assert "data-sprint-strip" in page and "ML sprint" in page and "Day 1 of 7" in page, path
    page = c.get("/").text
    assert "sprint-strip open" in page and "--ss-hours: 2" in page and "tempo-read" in page
    d = c.get("/sprint-bar.json").json()
    assert d["state"] == "open" and d["end"] - d["start"] == 2 * 3600 * 1000
    # the focus timer still works beside it
    c.post("/timer/start", data={"minutes": "25"})
    assert c.get("/timer.json").json()["on"] and "data-sprint-strip" in c.get("/").text
    # "restart": a new app on the same data folder shows it again
    c2 = TestClient(create_app(Vault(v.home)))
    assert "data-sprint-strip" in c2.get("/").text
    c.post("/roadmaps/ml/sprint", data={"action": "stop"})
    assert "data-sprint-strip" not in c.get("/").text and c.get("/sprint-bar.json").json() == {}


def test_the_start_form_takes_the_window(app):
    v, c = app
    roadmaps.save(v.home, roadmaps.parse(RM, "mine"))
    page = c.get("/roadmaps/ml").text
    assert 'name="end_time"' in page and "and ends at" in page
    c.post("/roadmaps/ml/sprint", data={"action": "start", "days": "7", "hours": "12",
                                         "start": dt.date.today().isoformat(), "start_time": "12:00", "end_time": "00:00"})
    run = roadmaps.get(v.home, "ml")["sprint_run"]
    assert run["hour"] == 12 and run["end"] == 0
    c.post("/roadmaps/ml/sprint", data={"action": "plan", "days": "7", "hours": "12", "end_time": "22:00",
                                         "day_1": "", "day_2": ""})
    assert roadmaps.get(v.home, "ml")["sprint_run"]["end"] == 22
