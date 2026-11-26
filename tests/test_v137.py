"""v1.37: backups with a progress bar and a known size, restore that starts inPace again, the Linux restart fix."""
import json
import os

import pytest
from starlette.testclient import TestClient

from inpace import pace, progress, updater
from inpace.app import create_app
from inpace.vault import Vault


@pytest.fixture
def app(tmp_path):
    v = Vault(tmp_path / "me")
    c = TestClient(create_app(v))
    c.post("/setup", data={"name": "Mona", "color": "#1F7A56"})
    c.post("/courses/sample/python-basics")
    return v, c


def test_backup_shows_its_size_and_is_downloaded_from_the_page(app):
    v, c = app
    page = c.get("/settings").text
    assert "Everything to back up: about" in page and 'action="/settings/backup" class="row" data-progress' in page
    assert "Backup ready" not in page
    r = c.post("/settings/backup", data={"password": "secret123", "progress": "tok123"}, follow_redirects=False)
    assert r.status_code == 303 and "Backup%20ready" in r.headers["location"] and "MB" in r.headers["location"]
    st = progress.get("tok123")
    assert st["label"] == "Making the backup" and st["got"] == st["size"] > 0
    page = c.get("/settings").text
    assert "Backup ready" in page and 'href="/settings/backup/file"' in page
    f = c.get("/settings/backup/file")
    assert f.status_code == 200 and f.content.startswith(pace.BACKUP_MAGIC) and ".inpace-backup" in f.headers["content-disposition"]
    assert pace.open_backup(f.content, "secret123")
    assert not any("backups/" in n for n in pace.open_backup(f.content, "secret123").namelist())  # not itself inside
    c.post("/settings/backup/delete")
    assert "Backup ready" not in c.get("/settings").text
    r = c.post("/settings/backup", data={"password": "abc"}, follow_redirects=False)
    assert "6%20characters" in r.headers["location"] or "6 characters" in r.headers["location"]


def test_restore_has_progress_and_starts_inpace_again(app, monkeypatch):
    v, c = app
    data = pace.make_backup(v, "secret123")
    restarted = []
    monkeypatch.setattr(updater, "restart", lambda: restarted.append(1))
    import threading
    calls = []
    monkeypatch.setattr(threading, "Timer", lambda wait, fn: calls.append((wait, fn)) or type("T", (), {"start": lambda self: fn()})())
    r = c.post("/settings/restore", files={"file": ("b.inpace-backup", data)}, data={"password": "wrong!!", "progress": "tok900000"},
               follow_redirects=False)
    assert r.status_code == 303 and "Wrong%20password" in r.headers["location"] and progress.get("tok900000")["state"] == "failed"
    r = c.post("/settings/restore", files={"file": ("b.inpace-backup", data)}, data={"password": "secret123", "progress": "tok100000"})
    assert r.status_code == 200 and "Restarting inPace" in r.text and "Backup restored" in r.text and "/ping" in r.text
    assert progress.get("tok100000")["of"] > 1 and restarted == [1]


def test_a_new_copy_starts_with_a_clean_environment(monkeypatch):
    monkeypatch.setenv("_MEIPASS2", "/tmp/_MEI123")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI123")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib")
    env = updater.restart_env()
    assert "_MEIPASS2" not in env and env["LD_LIBRARY_PATH"] == "/usr/lib" and "LD_LIBRARY_PATH_ORIG" not in env
    monkeypatch.setattr(updater, "is_frozen", lambda: False)
    cmd = updater.restart_command()
    assert cmd[1:3] == ["-m", "inpace"]


def test_the_sprint_card_shows_the_window_with_its_end(app):
    import datetime as dt
    from inpace import roadmaps
    v, c = app
    rm = roadmaps.parse({"id": "win-sprint", "title": "W", "steps": [{"course": "python-basics"}], "sprint": {"days": 3, "hours": 8}}, "mine")
    roadmaps.save(v.home, roadmaps.start_sprint(rm, {}, 3, 8, dt.date.today().isoformat(), 9, end=23))
    page = c.get("/roadmaps/win-sprint").text
    assert "each day runs 09:00 to 23:00" in page and "days run 09:00 to 09:00" not in page
