"""v1.35: the person who checks on you follows your sprints. Every progress file carries the sprints its course
is part of, signed with your key; the checker sees one short line per sprint, with the details folded away."""
import datetime as dt
import html
import json

from inpace import exchange, roadmaps
from tests.test_app import upload
from tests.test_v111 import _connect, _lesson

SPRINT = {"title": "ML sprint", "steps": [{"course": "python-basics", "day": 1, "tasks": ["Modules 1-2", "The quiz"]},
                                          {"course": "fastapi", "day": "2-3"}],
          "sprint": {"days": 7, "hours": 12}}


def _sprint(lv, start=None, hour=0):
    rm = roadmaps.parse({**SPRINT, "id": "ml-sprint"}, "mine")
    rm = roadmaps.start_sprint(rm, {}, 7, 12, start or dt.date.today().isoformat(), hour)
    roadmaps.save(lv.home, rm)
    return rm


def test_a_progress_file_carries_the_sprints_of_its_course_signed(tmp_path):
    lv, learner, cv, checker = _connect(tmp_path)
    learner.post("/courses/sample/python-basics")
    learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    _sprint(lv)
    learner.post("/roadmaps/ml-sprint/sprint/tick", data={"course": "python-basics", "i": "0", "on": "1"})
    _lesson(learner, lv, jid, "m1-l1")
    data = exchange.make_progress_file(lv, jid)
    assert len(data["sprints"]) == 1
    snap = data["sprints"][0]
    assert snap["body"]["title"] == "ML sprint" and snap["body"]["steps"][0]["done"] == [0]
    assert snap["body"]["ticks"][0][1] == "python-basics"
    assert exchange.check_sprint(snap, lv.identity.id)
    # Changing anything breaks the signature
    bad = json.loads(json.dumps(snap))
    bad["body"]["steps"][0]["proven"] = True
    assert not exchange.check_sprint(bad, lv.identity.id)
    assert not exchange.check_sprint(snap, cv.identity.id)  # and it's only valid as theirs


def test_a_sprint_without_this_course_stays_out(tmp_path):
    lv, learner, cv, checker = _connect(tmp_path)
    learner.post("/courses/sample/python-basics")
    learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    rm = roadmaps.parse({"id": "other", "title": "Other", "steps": [{"course": "fastapi"}]}, "mine")
    roadmaps.save(lv.home, roadmaps.start_sprint(rm, {}, 3, 2, dt.date.today().isoformat()))
    _lesson(learner, lv, jid, "m1-l1")
    assert "sprints" not in exchange.make_progress_file(lv, jid)


def test_the_checker_sees_one_short_line_and_the_details_folded(tmp_path):
    lv, learner, cv, checker = _connect(tmp_path)
    learner.post("/courses/sample/python-basics")
    learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    start = (dt.date.today() - dt.timedelta(days=2)).isoformat()  # day 3: day 1's course is late
    _sprint(lv, start)
    learner.post("/roadmaps/ml-sprint/sprint/tick", data={"course": "python-basics", "i": "0", "on": "1"})
    _lesson(learner, lv, jid, "m1-l1")
    r = upload(checker, "omar.inpace", learner.get(f"/milestones/{jid}/export").content)
    page = html.unescape(r.text)
    assert "ML sprint" in page and "Sprint · day 3 of 7" in page and "1 late" in page
    assert '<details class="card sp-review"' in r.text and "<details class=\"card sp-review\" id=\"sprint-ml-sprint\" open" not in r.text
    assert "0 of 2 courses finished in inPace (proven)" in page and "When they ticked" in page
    assert "Not signed by them" not in page


def test_a_changed_sprint_is_flagged(tmp_path):
    lv, learner, cv, checker = _connect(tmp_path)
    learner.post("/courses/sample/python-basics")
    learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    _sprint(lv)
    _lesson(learner, lv, jid, "m1-l1")
    data = json.loads(learner.get(f"/milestones/{jid}/export").content)
    data["sprints"][0]["body"]["steps"][0]["proven"] = True  # someone made it look better
    r = upload(checker, "omar.inpace", json.dumps(data).encode())
    page = html.unescape(r.text)
    assert "Not signed by them" in page and "Don't trust what it says" in page


def test_the_view_counts_proven_and_late():
    snap = {"body": {"kind": "sprint", "learner": "x", "id": "s", "title": "S", "start": "2026-11-20", "hour": 16,
                     "days": 3, "hours": 2, "made_at": "2026-11-22T20:00:00Z",
                     "steps": [{"course": "a", "title": "A", "range": [1, 1], "tasks": [], "done": [], "units": 1, "proven": True},
                               {"course": "b", "title": "B", "range": [2, 2], "tasks": ["x", "y"], "done": [0], "units": 2, "proven": False},
                               {"course": "c", "title": "C", "range": [3, 3], "tasks": [], "done": [], "units": 1, "proven": False}],
                     "ticks": [["2026-11-21T02:10:00", "b", 0]], "focus": {"1": 90, "2": 30}}, "hash": "h", "sig": "s"}
    v = exchange.sprint_view(snap, "x")
    assert not v["ok"] and v["proven"] == 1 and v["need"] == 3 and v["percent"] == 50
    assert v["per_day"] == {1: ["02:10"]}  # 2 am on Nov 21 still counts as day 1 of a 4 pm sprint
    assert v["focus_total"] == 120 and v["strip"][0]["focus"] == 90
