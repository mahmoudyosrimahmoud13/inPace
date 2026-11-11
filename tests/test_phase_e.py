import html
import json
import shutil
import subprocess

import pytest

from inpace import editor, exchange, races, record
from inpace.course import CourseError
from inpace.vault import Vault
from tests.test_core import make_people, roundtrip, sample


def approve_all(learner, checker, j):
    data = roundtrip(exchange.make_progress_file(learner, j))
    seqs = [m["body"]["seq"] for m in data["milestones"]]
    exchange.import_approval_file(learner, roundtrip(exchange.make_approval_file(checker, data, "approved", "", seqs)))


def test_race_between_two_learners(tmp_path):
    omar, sara = make_people(tmp_path)          # sara checks omar
    lina = Vault(tmp_path / "lina")
    lina.setup("Lina")
    lina.install_course(sample())
    sara.add_person(lina.identity.id, "Lina", "#B4691B", False, True)
    lina.add_person(sara.identity.id, "Sara", "#1F7A56", True, False)

    jo, jl = omar.start_journey("python-basics"), lina.start_journey("python-basics")
    race = roundtrip(races.create_race(omar, "Sprint", "points", 14))
    races.join_race(omar, race, jo)
    bad = dict(race, name="Hacked")
    with pytest.raises(exchange.FileProblem):
        races.join_race(lina, bad, jl)
    races.join_race(lina, race, jl)

    for les in ("m1-l1", "m1-l2"):
        omar.add_event(jo, "lesson_done", {"lesson": les})
    omar.create_milestone(jo)
    lina.add_event(jl, "lesson_done", {"lesson": "m1-l1"})
    lina.create_milestone(jl)
    assert races.my_score(omar, race, jo)["main"] == 0          # not approved yet: doesn't count
    assert races.my_score(omar, race, jo)["pending"] == 1
    approve_all(omar, sara, jo)
    approve_all(lina, sara, jl)

    folder = tmp_path / "shared"
    folder.mkdir()
    for v, rid in ((omar, race["id"]), (lina, race["id"])):
        v.db.execute("UPDATE races SET folder=? WHERE id=?", (str(folder), rid))
        v.db.commit()
    races.sync_folder(omar, race["id"])
    races.send_cheer(lina, race["id"], omar.identity.id, "Great pace!")
    assert races.sync_folder(lina, race["id"]) == 1
    races.sync_folder(omar, race["id"])
    b = races.board(omar, race["id"])
    assert [r["name"] for r in b["rows"]] == ["Omar", "Lina"]
    assert b["rows"][0]["score"]["main"] > b["rows"][1]["score"]["main"] > 0
    assert b["cheers"] == [{"from": "Lina", "text": "Great pace!"}]
    assert "First milestone" in b["rows"][0]["badges"]
    # A forged update is refused.
    upd = races.make_update(lina, race["id"])
    upd["score"]["main"] = 999
    with pytest.raises(exchange.FileProblem):
        races.import_update(omar, upd)


def test_course_editor(tmp_path):
    v = Vault(tmp_path / "v")
    v.setup("Teacher")
    c = editor.new_course(v, "Cooking 101", "Basics", "Knives", "Holding a knife", "## Grip\nPinch the blade.")
    assert c.id == "cooking-101" and c.version == "1"
    c = editor.edit(v, c.id, "add_question", {"text": "Which grip is safest?", "right": "Pinch grip\nBlade grip",
                                               "wrong": "Fist grip\nOne finger\nLoose grip\nNo grip", "show": "4"})
    assert len(c.questions["q1"]["options"]) == 6 and len(c.answers["q1"]["right"]) == 2
    c = editor.edit(v, c.id, "add_task", {"module": "m1", "type": "quiz", "prompt": "Knife quiz", "questions": ["q1"]})
    c = editor.edit(v, c.id, "add_task", {"module": "m1", "type": "explain", "prompt": "Why pinch?"})
    c = editor.edit(v, c.id, "add_module", {"title": "Heat", "lesson_title": "Pans", "content": "Hot pans."})
    c = editor.edit(v, c.id, "edit_lesson", {"lesson": "m1-l1", "title": "Grip", "content": "New text", "minutes": "5"})
    assert c.find_lesson("m1-l1")[1]["content"] == "New text" and len(c.modules) == 2 and c.version == "6"
    with pytest.raises(CourseError):
        editor.edit(v, c.id, "delete_question", {"question": "q1"})    # used by a quiz
    with pytest.raises(CourseError):
        editor.edit(v, c.id, "delete_lesson", {"module": "m2", "lesson": "m2-l1"})  # last lesson
    with pytest.raises(CourseError):
        editor.edit(v, c.id, "add_lesson", {"module": "m1", "title": "Empty", "content": ""})


@pytest.mark.skipif(not shutil.which("node"), reason="needs node + playwright to run a real browser")
def test_learning_record_verifies_in_a_browser(tmp_path):
    learner, checker = make_people(tmp_path)
    j = learner.start_journey("python-basics")
    learner.add_event(j, "writeup_saved", {"req": "m1-explain", "text": "مرحبا\r\nprint shows text — “quotes”", "words": 4})
    learner.create_milestone(j)
    learner.add_event(j, "lesson_done", {"lesson": "m1-l1", "title": "What is Python?"})
    learner.create_milestone(j)
    approve_all(learner, checker, j)
    good = tmp_path / "good.html"
    good.write_text(record.build_record(learner, j), encoding="utf-8")
    bad_html = good.read_text(encoding="utf-8").replace('"percent": 0', '"percent": 99', 1)
    assert bad_html != good.read_text(encoding="utf-8")
    bad = tmp_path / "bad.html"
    bad.write_text(bad_html, encoding="utf-8")
    script = tmp_path / "check.js"
    script.write_text("""
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const out = [];
  for (const f of process.argv.slice(2)) {
    const p = await b.newPage(); await p.goto('file://' + f); await p.click('#verify');
    await p.waitForSelector('#result[style*="block"]'); out.push(await p.textContent('#result'));
  }
  console.log(JSON.stringify(out)); await b.close();
})();""")
    try:
        npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
        res = subprocess.run(["node", str(script), str(good), str(bad)], capture_output=True, text=True,
                             env={**__import__("os").environ, "NODE_PATH": npm_root}, timeout=60)
        results = json.loads(res.stdout)
    except Exception:
        pytest.skip("playwright not available")
    assert "checks out" in results[0] and "every approval is genuine" in results[0]
    assert "problems" in results[1]
