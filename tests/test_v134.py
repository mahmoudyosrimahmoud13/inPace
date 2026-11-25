"""v1.34: host mode. You turn it on in Settings; people on your network sign in through a door, and each gets
their own inPace (a separate program with its own data folder) behind it. Pages that would act on the host
computer are off for them."""
import json
import os
import socket
import time

import pytest
from starlette.testclient import TestClient

from inpace import hosting
from inpace.app import SAMPLES, create_app
from inpace.course import files_from_folder, load_course
from inpace.vault import Vault


@pytest.fixture
def owner(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mahmoud", "color": "#1F7A56"})
    yield v, c
    hosting.DOOR.stop()


# ---- accounts ------------------------------------------------------------------------------------------------

def test_accounts_are_checked_and_passwords_are_never_kept(tmp_path):
    home = tmp_path / "me"
    with pytest.raises(hosting.AccountProblem, match="8 characters"):
        hosting.add_user(home, "sara", "Sara", "short")
    with pytest.raises(hosting.AccountProblem, match="username"):
        hosting.add_user(home, "Sa ra!", "Sara", "a good password")
    with pytest.raises(hosting.AccountProblem, match="username as the password"):
        hosting.add_user(home, "saraaaaa", "Sara", "SARAAAAA")
    hosting.add_user(home, "sara", "Sara", "tea and books")
    with pytest.raises(hosting.AccountProblem, match="already"):
        hosting.add_user(home, "sara", "Sara", "another one!")
    with pytest.raises(hosting.AccountProblem, match="their own password"):
        hosting.add_user(home, "omar", "Omar", "tea and books")
    raw = (home / "hosted" / "users.json").read_text(encoding="utf-8")
    assert "tea and books" not in raw and '"hash"' in raw
    assert hosting.check_login(home, "sara", "tea and books") and hosting.check_login(home, "SARA ", "tea and books")
    assert not hosting.check_login(home, "sara", "tea and book") and not hosting.check_login(home, "nobody", "x")
    v = Vault(hosting.user_home(home, "sara"))  # their own inPace, set up and ready
    assert v.is_set_up and v.me["name"] == "Sara"
    v.db.close()  # (Windows can't delete a database that is still open)
    hosting.set_password(home, "sara", "milk and books")
    assert hosting.check_login(home, "sara", "milk and books") and not hosting.check_login(home, "sara", "tea and books")
    hosting.remove_user(home, "sara")
    assert not hosting.user_home(home, "sara").exists() and "sara" not in hosting.load_users(home)


def test_a_username_can_never_reach_outside_the_homes_folder(tmp_path):
    for bad in ("../me", "..", "a/b", "", "x" * 40):
        with pytest.raises(hosting.AccountProblem):
            hosting.user_home(tmp_path, bad)


def test_give_a_course_links_its_files(owner):
    v, c = owner
    c.post("/courses/sample/python-basics")
    (v.media_dir("python-basics")).mkdir(parents=True, exist_ok=True)
    (v.media_dir("python-basics") / "clip.mp4").write_bytes(b"video" * 1000)
    hosting.add_user(v.home, "sara", "Sara", "tea and books")
    assert hosting.give_course(v, "python-basics", ["sara", "nobody"]) == 1
    sv = Vault(hosting.user_home(v.home, "sara"))
    assert sv.get_course("python-basics") is not None
    got = sv.media_dir("python-basics") / "clip.mp4"
    assert got.read_bytes() == b"video" * 1000
    assert os.stat(got).st_ino == os.stat(v.media_dir("python-basics") / "clip.mp4").st_ino  # linked, not copied


def test_blocked_pages_are_the_ones_that_touch_the_host():
    for p in ("/pick-folder", "/add/folder", "/courses/x/open-media", "/courses/x/media-folder", "/quit",
              "/updates/install", "/window/popout", "/settings/host", "/settings/ai", "/pdf/open-outside",
              "/codenote/open", "/courses/x/offline/download", "/downloads/open/x", "/reminders/test",
              "/learn/j/task/r/git", "/settings/delete-everything", "/settings/restore"):
        assert hosting.blocked(p), p
    for p in ("/", "/courses", "/learn/j/lesson/l", "/library", "/settings", "/m/c/a.mp4", "/sprints",
              "/timer/start", "/roadmaps/x", "/milestones", "/open"):
        assert not hosting.blocked(p), p


def test_public_networks_are_spotted():
    assert hosting.network_looks_public(["41.32.10.5"])
    assert hosting.network_looks_public([])
    assert not hosting.network_looks_public(["192.168.1.20"])
    assert not hosting.network_looks_public(["10.0.0.4", "41.32.10.5"])


# ---- inside one person's inPace ------------------------------------------------------------------------------

@pytest.fixture
def guest(tmp_path, monkeypatch):
    monkeypatch.setenv("INPACE_HOSTED", "1")
    monkeypatch.setenv("INPACE_HOST_TOKEN", "secret-token")
    monkeypatch.setenv("INPACE_HOST_NAME", "Mahmoud")
    v = Vault(tmp_path / "sara")
    v.setup("Sara", "#1F7A56")
    return v, TestClient(create_app(v))


def test_a_shared_inpace_only_answers_the_door(guest):
    v, c = guest
    assert c.get("/").status_code == 403
    assert c.get("/", headers={"x-inpace-host": "wrong"}).status_code == 403
    ok = c.get("/courses", headers={"x-inpace-host": "secret-token"})
    assert ok.status_code == 200 and "Mahmoud’s inPace" in ok.text and "/host-logout" in ok.text


def test_pages_that_act_on_the_host_are_off_for_people_who_sign_in(guest):
    v, c = guest
    h = {"x-inpace-host": "secret-token"}
    r = c.post("/pick-folder", headers={**h, "x-inpace-fetch": "1"})
    assert r.status_code == 403 and "only works on the computer that runs inPace" in r.json()["error"]
    r = c.post("/quit", headers={**h, "referer": "http://x/settings"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/settings?err=")
    page = c.get("/settings", headers=h).text
    assert 'action="/quit"' not in page and "/settings/host" not in page and 'id="ai"' not in page
    from inpace import notifier
    assert notifier.notify("x", "y") is False  # nothing pops up on the host computer


def test_progress_from_a_shared_inpace_says_so_inside_the_signature(guest):
    v, c = guest
    h = {"x-inpace-host": "secret-token"}
    c.post("/courses/sample/python-basics", headers=h)
    jid = v.start_journey("python-basics")
    course = v.get_course("python-basics")
    v.record(jid, "lesson_done", {"lesson": course.modules[0]["lessons"][0]["id"]}) if hasattr(v, "record") else None
    ms = v.create_milestone(jid)
    if ms is None:
        pytest.skip("no event to make a milestone from")
    body = v.milestones(jid)[-1]["body"]
    assert body["server"] == {"name": "Mahmoud"}
    from inpace import exchange
    assert exchange.make_progress_file(v, jid)["server"]["name"] == "Mahmoud"


# ---- the owner's Settings -----------------------------------------------------------------------------------

def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_settings_turn_host_mode_on_only_after_the_warnings(owner):
    v, c = owner
    page = c.get("/settings").text
    assert 'href="/settings/host"' in page and "Host mode" in page
    page = c.get("/settings/host").text
    for words in ("Anyone on this network can reach the sign-in page", "never on café, airport or hotel Wi-Fi",
                  "stay on and awake", "signed by this server", "Videos are sent from this computer",
                  "isn't ready to be reached from the internet", "I'm on a network I trust"):
        assert words in page, words
    r = c.post("/settings/host", data={"action": "on", "trust": "1", "port": "8780"}, follow_redirects=False)
    assert "err=" in r.headers["location"] and not hosting.DOOR.running
    port = _free_port()
    c.post("/settings/host", data={"action": "on", "trust": "1", "stored": "1", "port": str(port)})
    assert hosting.DOOR.running and v._meta("host_on") == "1"
    page = c.get("/courses").text
    assert "Host mode is on." in page and f":{port}" in page
    r = c.post("/settings/host", data={"action": "add", "name": "Sara", "username": "sara", "password": "short"},
               follow_redirects=False)
    assert "8%20characters" in r.headers["location"] or "8 characters" in r.headers["location"]
    c.post("/settings/host", data={"action": "add", "name": "Sara", "username": "sara", "password": "tea and books"})
    assert "sara" in c.get("/settings/host").text
    c.post("/settings/host", data={"action": "off"})
    assert not hosting.DOOR.running and v._meta("host_on") == ""
    assert "Host mode is on." not in c.get("/courses").text


def test_no_host_mode_on_a_phone(owner, monkeypatch):
    v, c = owner
    monkeypatch.setenv("INPACE_MOBILE", "1")
    r = c.get("/settings/host", follow_redirects=False)
    assert r.status_code == 303


# ---- the door, for real: sign in, your own inPace starts, pages pass through ----------------------------------

def test_the_door_end_to_end(owner):
    v, c = owner
    hosting.add_user(v.home, "sara", "Sara", "tea and books")
    door = hosting.DOOR
    door.home, door.port, door.owner_name, door.token = v.home, 0, "Mahmoud", "t0ken-for-the-test"
    d = TestClient(hosting.door_app(door), base_url="http://192.168.1.30:8780")
    r = d.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/host-login"
    page = d.get("/host-login").text
    assert "Mahmoud's inPace" in page and "the person who runs it can see it" in page
    assert d.post("/host-login", data={"username": "sara", "password": "nope nope"}).status_code == 401
    r = d.post("/host-login", data={"username": "sara", "password": "tea and books"}, follow_redirects=False)
    assert r.status_code == 303 and hosting.COOKIE in r.headers.get("set-cookie", "")
    assert "HttpOnly" in r.headers["set-cookie"] and "samesite=strict" in r.headers["set-cookie"].lower()
    c.post("/courses/sample/python-basics")
    v.media_dir("python-basics").mkdir(parents=True, exist_ok=True)
    (v.media_dir("python-basics") / "clip.mp4").write_bytes(bytes(range(256)) * 400)
    hosting.give_course(v, "python-basics", ["sara"])
    try:
        part = d.get("/m/python-basics/clip.mp4", headers={"range": "bytes=10-19"})  # seeking in a video
        assert part.status_code == 206 and part.content == bytes(range(10, 20))
        page = d.get("/courses")
        assert page.status_code == 200 and "Mahmoud’s inPace" in page.text  # Sara's own inPace, through the door
        assert "Sara" in d.get("/settings").text
        r = d.post("/pick-folder", headers={"x-inpace-fetch": "1"})
        assert r.status_code == 403
        w = door.workers["sara"]
        assert w["proc"].poll() is None
        with socket.socket() as s:  # it listens on this computer only
            assert s.connect_ex(("127.0.0.1", w["port"])) == 0
        import urllib.request
        import urllib.error
        with pytest.raises(urllib.error.HTTPError) as e:  # and only answers the door
            urllib.request.urlopen(f"http://127.0.0.1:{w['port']}/courses", timeout=5)
        assert e.value.code == 403
        d.get("/host-logout")
        r = d.get("/courses", headers={"accept": "text/html"}, follow_redirects=False)
        assert r.headers["location"] == "/host-login"
    finally:
        door.stop_worker("sara")


def test_the_door_slows_down_guessing(owner):
    v, c = owner
    hosting.add_user(v.home, "sara", "Sara", "tea and books")
    door = hosting.Door()
    door.home, door.owner_name = v.home, "Mahmoud"
    d = TestClient(hosting.door_app(door))
    for _ in range(hosting.TRIES):
        d.post("/host-login", data={"username": "sara", "password": "wrong guess"})
    r = d.post("/host-login", data={"username": "sara", "password": "tea and books"})
    assert r.status_code == 429 and "Too many tries" in r.text


def test_the_door_speaks_arabic(owner):
    v, c = owner
    door = hosting.Door()
    door.home, door.owner_name = v.home, "محمود"
    d = TestClient(hosting.door_app(door))
    page = d.get("/host-login", headers={"accept-language": "ar-EG,ar;q=0.9"}).text
    assert 'dir="rtl"' in page and "سجّل الدخول" in page


def test_a_persons_inpace_stops_when_the_door_is_gone(tmp_path):
    import subprocess
    import sys
    home = tmp_path / "me"
    hosting.add_user(home, "sara", "Sara", "tea and books")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed = s.getsockname()[1]  # a door that isn't there
    port = _free_port()
    door = hosting.DOOR
    door.token, door.owner_name, door.port = "tok", "Mahmoud", closed
    cmd, env = hosting._command(hosting.user_home(home, "sara"), port)
    env["INPACE_DOOR_CHECK"] = "0.2"
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert proc.wait(timeout=30) == 0
    finally:
        if proc.poll() is None:
            proc.kill()


def test_a_folder_still_in_use_is_moved_aside_and_deleted_later(tmp_path, monkeypatch):
    home = tmp_path / "me"
    hosting.add_user(home, "sara", "Sara", "tea and books")
    real = hosting.shutil.rmtree
    calls = {"n": 0}

    def locked(path, ignore_errors=False, **k):  # like Windows with a file still open
        calls["n"] += 1
        if calls["n"] <= 20:
            return None
        return real(path, ignore_errors=ignore_errors, **k)
    monkeypatch.setattr(hosting.shutil, "rmtree", locked)
    monkeypatch.setattr(hosting.time, "sleep", lambda s: None)
    hosting.remove_user(home, "sara")
    assert not hosting.user_home(home, "sara").exists() and "sara" not in hosting.load_users(home)
    moved = list((home / "hosted" / "removed").iterdir())
    assert len(moved) == 1
    hosting.clean_removed(home)  # later, when nothing holds it
    assert not any((home / "hosted" / "removed").iterdir())
