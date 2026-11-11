from datetime import datetime, timedelta, timezone

import pytest

from inpace import pace
from inpace.vault import Vault
from tests.test_core import make_people, sample


def ev(t, typ, **data):
    return {"type": typ, "at": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "data": data}


def test_weeks_met_missed_paused_and_streak():
    s = datetime(2026, 10, 1, tzinfo=timezone.utc)
    events = [ev(s, "commitment_set", per_week=1),
              ev(s + timedelta(days=15), "pause_started", reason="exams"),
              ev(s + timedelta(days=20), "pause_ended")]
    ms = [(s + timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ") for d in (1, 8, 22, 29)]
    w = pace.weeks(events, ms, now=s + timedelta(days=36))
    assert [x["state"] for x in w["weeks"]] == ["met", "met", "paused", "met", "met", "now"]
    assert w["streak"] == 4 and w["missed"] == 0  # a break doesn't break the streak
    w2 = pace.weeks(events, ms[:1], now=s + timedelta(days=36))
    assert w2["missed"] >= 1 and w2["streak"] == 0


def test_forecast():
    now = datetime(2026, 11, 11, tzinfo=timezone.utc)
    assert pace.forecast("2026-11-01T00:00:00Z", 50, now=now) == "Nov 21, 2026"
    assert pace.forecast("2026-11-01T00:00:00Z", 0, now=now) is None


def test_leitner_boxes(tmp_path):
    v = Vault(tmp_path / "v")
    v.setup("A")
    today = datetime(2026, 11, 11).date()
    pace.update_cards(v, "c", {"q1": True, "q2": False}, today)
    assert pace.due_cards(v, "c", today) == []
    assert pace.due_cards(v, "c", today + timedelta(days=1)) == ["q2"]   # wrong: back tomorrow
    assert "q1" in pace.due_cards(v, "c", today + timedelta(days=7))    # right: later


def test_backup_round_trip(tmp_path):
    learner, _ = make_people(tmp_path)
    j = learner.start_journey("python-basics")
    learner.add_event(j, "lesson_done", {"lesson": "m1-l1"})
    learner.create_milestone(j)
    data = pace.make_backup(learner, "secret123")
    with pytest.raises(ValueError):
        pace.open_backup(data, "wrong-pass")
    fresh = Vault(tmp_path / "restored")
    pace.restore_backup(fresh, data, "secret123")
    again = Vault(tmp_path / "restored")
    assert again.me["name"] == "Omar" and again.identity.id == learner.identity.id
    assert len(again.milestones(j)) == 1 and again.get_course("python-basics")
