"""v1.38: fast on phones. Courses and progress are kept between starts, settings and journeys are read once per
page, and any write (by any copy of the vault in this process) makes every kept copy read again."""
import pickle

from inpace import vault as vault_mod
from inpace.vault import Vault
from tests.test_app import client
from tests.test_v111 import _lesson


def test_a_parsed_course_is_kept_on_disk_and_dropped_when_its_files_change(tmp_path):
    v, c = client(tmp_path, "Mona")
    c.post("/courses/sample/python-basics")
    cache = v.home / "cache" / "courses" / "python-basics.pickle"
    assert cache.exists()
    stamp, course = pickle.load(open(cache, "rb"))
    assert course.id == "python-basics"
    # a fresh vault reads the pickle, not the YAML
    v2 = Vault(v.home)
    assert v2.get_course("python-basics").title == course.title
    # the course file changes: the pickle is stale and gets replaced
    yaml = v.home / "courses" / "python-basics" / "course.yaml"
    yaml.write_text(yaml.read_text(encoding="utf-8").replace("title: Python Basics", "title: Python Basics 2"), encoding="utf-8")
    import os
    os.utime(yaml, (os.stat(yaml).st_atime, os.stat(yaml).st_mtime + 5))
    v3 = Vault(v.home)
    assert v3.get_course("python-basics").title == "Python Basics 2"
    assert pickle.load(open(cache, "rb"))[1].title == "Python Basics 2"


def test_progress_is_kept_in_the_database_between_starts(tmp_path):
    v, c = client(tmp_path, "Mona")
    c.post("/courses/sample/python-basics")
    c.post("/courses/python-basics/start")
    jid = v.journeys()[0]["id"]
    _lesson(c, v, jid, "m1-l1")
    p = v.progress(jid)
    assert p["lessons_done"] == 1
    row = v.db.execute("SELECT key FROM progress_cache WHERE journey=?", (jid,)).fetchone()
    assert row is not None
    v2 = Vault(v.home)  # a new start: the kept copy is used, and it's the same
    calls = []
    orig = v2._progress_uncached
    v2._progress_uncached = lambda *a: calls.append(1) or orig(*a)
    p2 = v2.progress(jid)
    assert p2["lessons_done"] == 1 and p2["course"].id == "python-basics" and not calls
    _lesson(c, v, jid, "m1-l2")  # a new event: worked out again
    assert Vault(v.home).progress(jid)["lessons_done"] == 2


def test_settings_and_journeys_are_read_once_until_something_is_written(tmp_path):
    v, c = client(tmp_path, "Mona")
    v._set_meta("lang", "en")
    assert v._meta("lang") == "en"
    other = Vault(v.home)  # another copy, like the download worker's
    other._set_meta("lang", "ar")
    assert v._meta("lang") == "ar"  # the write moved the counter: read again
    c.post("/courses/sample/python-basics")
    assert v.journey_for_course("python-basics") is None
    c.post("/courses/python-basics/start")
    assert v.journey_for_course("python-basics")
    jid = v.journey_for_course("python-basics")
    assert v.journey(jid)["course_id"] == "python-basics"
    v.archive_course("python-basics")
    assert v.journey_for_course("python-basics") is None


def test_a_direct_commit_also_moves_the_counter(tmp_path):
    v = Vault(tmp_path / "h")
    before = vault_mod._GEN[0]
    v.db.execute("INSERT OR REPLACE INTO meta VALUES ('x', '1')")
    v.db.commit()
    assert vault_mod._GEN[0] > before


def test_the_database_uses_a_write_ahead_log_and_backups_still_restore(tmp_path):
    v, c = client(tmp_path, "Mona")
    assert v.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    c.post("/courses/sample/python-basics")
    from inpace import pace
    data = pace.make_backup(v, "secret1")
    home2 = tmp_path / "other"
    v2 = Vault(home2)
    (home2 / "vault.db-wal").write_bytes(b"stale")
    pace.restore_backup(v2, data, "secret1")
    assert not (home2 / "vault.db-wal").exists() or (home2 / "vault.db-wal").read_bytes() != b"stale"
    v3 = Vault(home2)
    assert v3._meta("name") == "Mona" and v3.get_course("python-basics")
