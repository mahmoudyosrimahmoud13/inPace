"""v1.14: reminders, alarms and Tempo's notifications (the logic, the pages, the scheduler files, the job)."""
import html
import json
import plistlib
import re
import sys
from datetime import datetime, timedelta, timezone

from inpace import notifier, pace, reminders
from inpace.exam import build_exam
from inpace.links import start_path
from tests.test_app import client

UTC = timezone.utc


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _learner(tmp_path):
    v, c = client(tmp_path, "Layla")
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    jid = v.journeys()[0]["id"]
    return v, c, jid


def _finish_module_1(v, c, jid):
    for les in ("m1-l1", "m1-l2"):
        c.post(f"/learn/{jid}/lesson/{les}/done", data={})
    c.post(f"/learn/{jid}/task/m1-practical/evidence", files={"file": ("hello.py", b"print(1)")})
    c.post(f"/learn/{jid}/task/m1-explain/writeup", data={"text": "print shows things on the screen " * 10})
    r = c.get(f"/learn/{jid}/task/m1-quiz/quiz")
    seed = re.search(r'name="seed" value="([0-9a-f]+)"', r.text).group(1)
    course = v.get_course("python-basics")
    exam = build_exam(course, ["q1", "q2", "q3"], seed)
    ans = {q["id"]: next(ch["id"] for ch in q["choices"] if ch["id"] in course.answers[q["id"]]["right"]) for q in exam}
    c.post(f"/learn/{jid}/task/m1-quiz/quiz", data={"seed": seed, **ans})


def test_add_change_and_delete_reminders(tmp_path):
    v, c = client(tmp_path, "Layla")
    page = html.unescape(c.get("/reminders").text)
    assert "No reminders yet" in page and "Tempo misses you" in page
    r = c.post("/reminders", data={"action": "add", "time": "19:30", "days": ["0", "2", "4"], "kind": "alarm",
                                   "label": "FastAPI after dinner"}, follow_redirects=True)
    page = html.unescape(r.text)
    assert "Reminder added." in page and "19:30" in page and "FastAPI after dinner" in page and "Mon, Wed, Fri" in page
    rid = reminders.load(v)["items"][0]["id"]
    c.post("/reminders", data={"action": "add", "time": "07:00", "days": ["5", "6"], "kind": "notify"})
    assert [x["time"] for x in reminders.load(v)["items"]] == ["07:00", "19:30"]
    assert "Weekends" in html.unescape(c.get("/reminders").text)
    c.post("/reminders", data={"action": "toggle", "id": rid})
    assert reminders.find(v, rid)["on"] is False
    c.post("/reminders", data={"action": "delete", "id": rid})
    assert reminders.find(v, rid) is None
    # Bad input is refused politely.
    assert "Choose at least one day" in html.unescape(c.post("/reminders", data={"action": "add", "time": "19:00"},
                                                              follow_redirects=True).text)
    assert "Choose a time" in html.unescape(c.post("/reminders", data={"action": "add", "time": "25:99", "days": ["1"]},
                                                   follow_redirects=True).text)
    c.post("/reminders", data={"action": "auto", "miss": "1", "review": "1", "miss_days": "5"})
    d = reminders.load(v)
    assert d["auto"] == {"miss": True, "goal": False, "review": True, "milestone": False} and d["miss_days"] == 5


def test_reminder_says_what_to_study_next(tmp_path):
    v, c, jid = _learner(tmp_path)
    msg = reminders.reminder_message(v, {"label": ""})
    assert msg["title"] == "Time to study" and "“What is Python?”" in msg["body"] and "Python Basics" in msg["body"]
    assert msg["url"] == f"/learn/{jid}/lesson/m1-l1"
    v._set_meta("lang", "ar")
    reminders.use_language(v)
    assert reminders.reminder_message(v, {"label": ""})["title"] == "وقت المذاكرة"
    v._set_meta("lang", "en")
    reminders.use_language(v)


def test_tempo_misses_you_twice_then_stops(tmp_path):
    v, c, jid = _learner(tmp_path)
    seen = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
    v._set_meta("last_seen", _iso(seen))
    evening = datetime(2026, 11, 8, 19, 0)
    assert reminders.due_now(v, evening, seen + timedelta(days=6)) == []
    first = reminders.due_now(v, evening, seen + timedelta(days=7, hours=9))
    assert first[0]["title"] == "Tempo misses you" and "It's been 7 days" in first[0]["body"]
    reminders.mark_sent(v, first[0])
    assert not [x for x in reminders.due_now(v, evening, seen + timedelta(days=9)) if x["log"][0] == "miss"]
    second = [x for x in reminders.due_now(v, evening, seen + timedelta(days=14, hours=9)) if x["log"][0] == "miss"]
    assert second and "14 days" in second[0]["body"]
    reminders.mark_sent(v, second[0])
    assert not [x for x in reminders.due_now(v, evening, seen + timedelta(days=30)) if x["log"][0] == "miss"]
    # Only in the evening.
    v._set_meta("notify_log", "")
    assert reminders.due_now(v, datetime(2026, 11, 8, 9, 0), seen + timedelta(days=8)) == []


def test_goal_review_and_milestone_nudges(tmp_path):
    v, c, jid = _learner(tmp_path)
    c.post(f"/learn/{jid}/do/commit", data={"per_week": "2"})
    since = reminders._parse(pace.commitment(v.events(jid))["since"])
    v._set_meta("last_seen", _iso(since + timedelta(days=6)))
    near_end = since + timedelta(days=5, hours=12)
    items = reminders.due_now(v, datetime(2026, 1, 1, 19, 0), near_end)
    assert any(x["title"] == "Your weekly goal" and "2 milestones this week and saved 0" in x["body"] for x in items)
    early = reminders.due_now(v, datetime(2026, 1, 1, 19, 0), since + timedelta(days=1))
    assert not any(x["title"] == "Your weekly goal" for x in early)
    # A finished module without a milestone, and questions to review.
    _finish_module_1(v, c, jid)
    pace.update_cards(v, "python-basics", {"q1": False}, today=datetime.now(UTC).date() - timedelta(days=3))
    v._set_meta("notify_log", "")
    titles = [x["title"] for x in reminders.due_now(v, datetime.now().replace(hour=19), datetime.now(UTC))]
    assert "Save your milestone" in titles or "Time for a quick review" in titles
    plan = reminders.plan(v)
    keys = {a["key"] for a in plan["auto"]}
    assert {"miss7", "miss14", "goal", "review", "milestone"} <= keys
    ms = next(a for a in plan["auto"] if a["key"] == "milestone")
    assert "You finished “Your first Python”" in ms["body"]
    c.post(f"/milestones/{jid}/save")
    assert "milestone" not in {a["key"] for a in reminders.plan(v)["auto"]}


def test_plan_for_the_android_app(tmp_path):
    v, c, jid = _learner(tmp_path)
    c.post("/reminders", data={"action": "add", "time": "20:15", "days": ["0", "1", "2", "3", "4", "5", "6"], "kind": "notify"})
    c.post("/reminders", data={"action": "add", "time": "06:00", "days": ["1"], "kind": "alarm", "label": "Gym then study"})
    c.post("/reminders", data={"action": "toggle", "id": reminders.load(v)["items"][0]["id"]})  # the 06:00 one is off
    plan = c.get("/reminders/plan.json").json()
    assert [(r["time"], r["kind"]) for r in plan["reminders"]] == [("20:15", "notify")]
    assert plan["reminders"][0]["url"] == f"/learn/{jid}/lesson/m1-l1" and plan["evening"] == "18:30"
    assert plan["labels"]["snooze"] == "Snooze 10 min" and plan["test"]["title"].startswith("Test")
    seen = reminders._parse(v._meta("last_seen"))
    miss = next(a for a in plan["auto"] if a["key"] == "miss7")
    assert reminders._parse(miss["after"]) == seen + timedelta(days=7)
    c.post("/reminders", data={"action": "auto", "miss_days": "7"})  # everything automatic off
    assert c.get("/reminders/plan.json").json()["auto"] == []


def test_welcome_back_after_a_long_break(tmp_path):
    v, c, jid = _learner(tmp_path)
    v._set_meta("last_seen", _iso(datetime.now(UTC) - timedelta(days=9)))
    page = html.unescape(c.get("/").text)
    assert "Welcome back! It's been 9 days." in page
    assert "Welcome back" not in html.unescape(c.get("/").text)  # only once
    assert "Want a reminder to study?" in html.unescape(c.get("/").text)


def test_the_scheduler_job(tmp_path, monkeypatch):
    v, c, jid = _learner(tmp_path)
    shown = []
    monkeypatch.setattr(notifier, "notify", lambda title, body, path="/", home=None: shown.append(("notify", title, body, path)) or True)
    monkeypatch.setattr(notifier, "alarm", lambda title, body, path, labels, home=None: shown.append(("alarm", title, labels["snooze"])))
    today = datetime.now().weekday()
    c.post("/reminders", data={"action": "add", "time": "19:00", "days": [str(today)], "kind": "alarm", "label": "Study!"})
    c.post("/reminders", data={"action": "add", "time": "20:00", "days": [str((today + 1) % 7)], "kind": "notify"})
    alarm, other = sorted(reminders.load(v)["items"], key=lambda r: r["time"])
    reminders.run_job(v, alarm["id"], False)
    assert shown == [("alarm", "Study!", "Snooze 10 min")]
    reminders.run_job(v, other["id"], False)  # not today: stays quiet
    reminders.run_job(v, "nope", False)
    assert len(shown) == 1
    reminders.run_job(v, "test", False)
    assert shown[-1][0] == "notify" and shown[-1][1].startswith("Test")
    # The hourly check marks what it showed, so it isn't shown twice.
    v._set_meta("last_seen", _iso(datetime.now(UTC) - timedelta(days=8)))
    monkeypatch.setattr(reminders, "due_now", lambda v_: [{"title": "Tempo misses you", "body": "b", "url": "/",
                                                           "log": ("miss", {"since": "x", "count": 1})}])
    reminders.run_job(v, None, True)
    assert shown[-1][1] == "Tempo misses you" and json.loads(v._meta("notify_log"))["miss"]["count"] == 1


def test_scheduler_files_for_each_computer(tmp_path, monkeypatch):
    items = [{"name": "reminder-ab12cd34", "args": ["--remind", "ab12cd34"], "time": "19:05", "days": [0, 2, 6]},
             {"name": "reminder-ffffffff", "args": ["--remind", "ffffffff"], "time": "07:00", "days": list(range(7))},
             {"name": "check", "args": ["--check-reminders"], "hourly": True}]
    cmd = ["/opt/inpace/inPace", "--home", "/home/me/My Courses"]
    units = notifier.linux_units(items, cmd)
    assert "OnCalendar=Mon,Wed,Sun *-*-* 19:05:00" in units["inpace-reminder-ab12cd34.timer"]
    assert "OnCalendar=*-*-* 07:00:00" in units["inpace-reminder-ffffffff.timer"]
    assert "OnCalendar=hourly" in units["inpace-check.timer"]
    assert 'ExecStart=/opt/inpace/inPace --home "/home/me/My Courses" --remind ab12cd34' in units["inpace-reminder-ab12cd34.service"]
    cron = notifier.cron_lines(items, cmd)
    assert cron[0].startswith("5 19 * * 1,3,0 ") and cron[0].endswith("'/home/me/My Courses' --remind ab12cd34")
    assert cron[1].startswith("0 7 * * * ") and cron[2].startswith("0 * * * * ")
    plists = notifier.mac_plists(items, cmd)
    p = plistlib.loads(plists["org.inpace.reminder-ab12cd34.plist"])
    assert p["ProgramArguments"] == cmd + ["--remind", "ab12cd34"]
    assert p["StartCalendarInterval"] == [{"Weekday": 1, "Hour": 19, "Minute": 5}, {"Weekday": 3, "Hour": 19, "Minute": 5},
                                          {"Weekday": 0, "Hour": 19, "Minute": 5}]
    assert plistlib.loads(plists["org.inpace.check.plist"])["StartInterval"] == 3600
    tasks = notifier.windows_tasks(items, [r"C:\Users\Me\inPace\inPace.exe"])
    assert tasks[0][tasks[0].index("/D") + 1] == "MON,WED,SUN" and tasks[0][tasks[0].index("/ST") + 1] == "19:05"
    assert "DAILY" in tasks[1] and "HOURLY" in tasks[2] and tasks[0][4] == r"inPace\reminder-ab12cd34"
    xml = notifier.windows_toast_xml('Next: "Lists" & more', "<b>", "inpace://go/learn/x", alarm=True)
    assert 'scenario="alarm"' in xml and "&amp; more" in xml and "&lt;b&gt;" in xml and "Looping.Alarm" in xml
    # In tests (and on Android) the real scheduler is never touched.
    v, c = client(tmp_path, "Omar")
    assert notifier.sync(v, force=True) == "off"


def test_notification_links_open_pages(tmp_path):
    assert start_path("inpace://go/learn/abc/lesson/m1-l2") == "learn/abc/lesson/m1-l2"
    assert start_path("inpace://go//evil.example") == "" and start_path("inpace://go/../x") == ""
    assert notifier.go_link("/learn/x") == "inpace://go/learn/x"


def test_cli_job_never_starts_the_app(tmp_path, monkeypatch):
    import inpace.__main__ as main_mod
    calls = []
    monkeypatch.setattr(reminders, "run_job", lambda v, remind, check: calls.append((remind, check)))
    monkeypatch.setattr(main_mod, "_stop_old_copy", lambda home: (_ for _ in ()).throw(AssertionError("stopped the app")))
    monkeypatch.setattr(sys, "argv", ["inpace", "--home", str(tmp_path / "x"), "--remind", "ab12cd34"])
    main_mod.main()
    monkeypatch.setattr(sys, "argv", ["inpace", "--home", str(tmp_path / "x"), "--check-reminders"])
    main_mod.main()
    assert calls == [("ab12cd34", False), (None, True)]
