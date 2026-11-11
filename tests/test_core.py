import json
from pathlib import Path

import pytest

from inpace import exchange
from inpace.canon import canonical_bytes, fingerprint
from inpace.course import CourseError, course_to_pack, files_from_folder, files_from_zip, load_course, strip_fences
from inpace.exam import build_exam, grade
from inpace.vault import Vault

SAMPLE = Path(__file__).parent.parent / "inpace" / "sample_courses" / "python-basics"


def sample():
    return load_course(files_from_folder(SAMPLE))


# ---- canonical form -------------------------------------------------------

def test_canonical_is_stable_across_key_order_and_line_endings():
    a = {"b": "x\r\ny", "a": [1, {"z": 1, "y": 2}]}
    b = {"a": [1, {"y": 2, "z": 1}], "b": "x\ny"}
    assert canonical_bytes(a) == canonical_bytes(b)
    assert canonical_bytes(a) == b'{"a":[1,{"y":2,"z":1}],"b":"x\\ny"}'


def test_test_vector():
    # Fixed vector from SPEC.md; any implementation must produce this.
    assert fingerprint({"hello": "world", "n": 1, "text": "سلام\r\nline"}) == \
        "264cd6a7c837006cdde548835d210b64cd64d1837e2400a46a3d6ba01cb95a47"


def test_floats_rejected():
    with pytest.raises(TypeError):
        canonical_bytes({"x": 1.5})


# ---- courses ------------------------------------------------------------------

def test_sample_course_loads_and_hash_ignores_answers():
    c = sample()
    assert c.title == "Python Basics" and c.lesson_count == 4
    no_answers = load_course(files_from_zip(course_to_pack(c, include_answers=False)))
    assert no_answers.answers is None
    assert no_answers.hash == c.hash


def test_pack_roundtrip_keeps_answers():
    c = sample()
    again = load_course(files_from_zip(course_to_pack(c, include_answers=True)))
    assert again.answers == c.answers and again.hash == c.hash


def test_friendly_errors():
    with pytest.raises(CourseError) as e:
        load_course({"course.yaml": "title: X\nmodules:\n  - title: A\n    requires:\n      - type: dance\n"})
    text = " ".join(e.value.problems)
    assert "has no lessons" in text and "practical, explain or quiz" in text


def test_ai_single_file_with_fences():
    reply = """Sure! Here is your course:
```yaml
title: Cooking
modules:
  - title: Basics
    lessons:
      - title: Knives
        content: "## Knives\\nHold it like this."
    requires:
      - type: quiz
        questions: [q1]
questions:
  q1:
    text: Which is a knife?
    right: [Chef knife, Paring knife]
    wrong: [Spoon, Fork, Whisk, Ladle]
```
Enjoy!"""
    c = load_course({"course.yaml": strip_fences(reply)})
    assert c.id == "cooking" and len(c.questions["q1"]["options"]) == 6
    # Option ids don't reveal which are right.
    assert sorted(c.questions["q1"]["options"]) == list(c.questions["q1"]["options"])


# ---- exams ------------------------------------------------------------------

def test_exam_one_right_answer_and_reproducible():
    c = sample()
    qids = ["q1", "q2", "q3"]
    e1 = build_exam(c, qids, "seed-1")
    assert e1 == build_exam(c, qids, "seed-1")
    for item in e1:
        right = set(c.answers[item["id"]]["right"])
        assert len(item["choices"]) == 4
        assert sum(1 for ch in item["choices"] if ch["id"] in right) == 1
    seeds = {json.dumps(build_exam(c, qids, f"s{i}")) for i in range(20)}
    assert len(seeds) > 5  # different seeds give different exams


def test_grading():
    c = sample()
    exam = build_exam(c, ["q1", "q2"], "x")
    picks = {it["id"]: next(ch["id"] for ch in it["choices"] if ch["id"] in c.answers[it["id"]]["right"]) for it in exam}
    assert grade(c, exam, picks)["percent"] == 100
    assert grade(c, exam, {})["percent"] == 0


# ---- the full two-person loop ----------------------------------------------

def make_people(tmp_path):
    learner, checker = Vault(tmp_path / "learner"), Vault(tmp_path / "checker")
    learner.setup("Omar")
    checker.setup("Sara")
    learner_card = exchange.make_contact_card(learner)
    checker_card = exchange.make_contact_card(checker)
    exchange.check_contact_card(learner_card)
    learner.add_person(checker_card["id"], "Sara", checker_card["color"], checks_me=True, i_check=False)
    checker.add_person(learner_card["id"], "Omar", learner_card["color"], checks_me=False, i_check=True)
    learner.install_course(sample())
    return learner, checker


def roundtrip(data):
    return exchange.read_inpace_file(exchange.dump(data))


def test_full_loop_and_tamper_detection(tmp_path):
    learner, checker = make_people(tmp_path)
    j = learner.start_journey("python-basics")
    learner.add_event(j, "lesson_done", {"lesson": "m1-l1"})
    m1 = learner.create_milestone(j)
    assert m1["body"]["seq"] == 1 and learner.create_milestone(j) is None

    # Learner -> checker
    progress = roundtrip(exchange.make_progress_file(learner, j))
    rep = exchange.review_progress(checker, progress)
    assert rep["history_ok"] and len(rep["new"]) == 1

    # Checker approves -> learner imports
    approval = roundtrip(exchange.make_approval_file(checker, progress, "approved", "Good start", [1]))
    res = exchange.import_approval_file(learner, approval)
    assert res["count"] == 1 and learner.milestones(j)[0]["approvals"][0]["decision"] == "approved"

    # More work, second milestone
    learner.add_event(j, "lesson_done", {"lesson": "m1-l2"})
    learner.create_milestone(j)
    progress2 = roundtrip(exchange.make_progress_file(learner, j))
    rep2 = exchange.review_progress(checker, progress2)
    assert rep2["history_ok"] and [m["body"]["seq"] for m in rep2["new"]] == [2]

    # Tamper 1: edit milestone 1 without fixing the fingerprint
    bad = json.loads(json.dumps(progress2))
    bad["milestones"][0]["body"]["summary"]["percent"] = 99
    assert not exchange.review_progress(checker, bad)["history_ok"]

    # Tamper 2: rewrite the whole history and re-sign it with the learner's own key.
    # Chain looks valid, but the checker's receipt catches it.
    forged = json.loads(json.dumps(progress2))
    b1 = forged["milestones"][0]["body"]
    b1["summary"]["percent"] = 99
    h1 = fingerprint(b1)
    forged["milestones"][0].update(hash=h1, sig=learner.identity.sign({"kind": "milestone", "hash": h1}))
    b2 = forged["milestones"][1]["body"]
    b2["prev"] = h1
    h2 = fingerprint(b2)
    forged["milestones"][1].update(hash=h2, sig=learner.identity.sign({"kind": "milestone", "hash": h2}))
    assert exchange.check_chain(forged["milestones"]) == []  # chain alone can't tell
    rep3 = exchange.review_progress(checker, forged)
    assert not rep3["history_ok"]
    assert any("changed after you reviewed it" in p for p in rep3["problems"])


def test_forged_approval_rejected(tmp_path):
    learner, checker = make_people(tmp_path)
    j = learner.start_journey("python-basics")
    learner.add_event(j, "lesson_done", {"lesson": "m1-l1"})
    learner.create_milestone(j)
    progress = roundtrip(exchange.make_progress_file(learner, j))
    approval = roundtrip(exchange.make_approval_file(checker, progress, "flag", "Missing work", [1]))
    approval["decisions"][0]["decision"] = "approved"  # learner tries to flip a flag
    with pytest.raises(exchange.FileProblem):
        exchange.import_approval_file(learner, approval)


def test_events_are_append_only(tmp_path):
    learner, _ = make_people(tmp_path)
    j = learner.start_journey("python-basics")
    learner.add_event(j, "lesson_done", {"lesson": "m1-l1"})
    learner.create_milestone(j)
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        learner.db.execute("UPDATE events SET type='x'")
    with pytest.raises(sqlite3.DatabaseError):
        learner.db.execute("DELETE FROM milestones")


def test_gating_and_progress(tmp_path):
    learner, _ = make_people(tmp_path)
    j = learner.start_journey("python-basics")
    p = learner.progress(j)
    assert [m["status"] for m in p["modules"]] == ["open", "locked"]
    for les in ("m1-l1", "m1-l2"):
        learner.add_event(j, "lesson_done", {"lesson": les})
    learner.save_evidence(j, "m1-practical", "hello.py", b"print('Omar', 7*6)")
    learner.add_event(j, "writeup_saved", {"req": "m1-explain", "text": "word " * 40, "words": 40})
    learner.add_event(j, "quiz_taken", {"req": "m1-quiz", "percent": 100, "score": 3, "total": 3,
                                         "mode": "practice", "seed": "s", "answers": {}})
    p = learner.progress(j)
    assert [m["status"] for m in p["modules"]] == ["done", "open"]
    assert p["next"]["id"] == "m2-l1"
