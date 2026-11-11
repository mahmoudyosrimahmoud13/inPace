import html
import copy
import io
import json
import zipfile

import pytest

from inpace import checks, exchange
from inpace.vault import Vault
from tests.test_core import make_people, roundtrip, sample


def progress_with(learner, j):
    learner.create_milestone(j)
    return roundtrip(exchange.make_progress_file(learner, j))


def test_verified_exam_round_trip(tmp_path):
    learner, checker = make_people(tmp_path)
    checker.install_course(sample())
    j = learner.start_journey("python-basics")
    learner.add_event(j, "lesson_done", {"lesson": "m1-l1"})
    data = progress_with(learner, j)
    checker.store_received(data)

    pid = checks.add_private_question(checker, "python-basics", "Who is your checker?", "Sara", ["Omar", "Nobody"])
    exam = roundtrip(checks.make_exam(checker, data, checker.get_course("python-basics"), "m2-quiz", [pid], True))
    assert len(exam["questions"]) == 3 + 1 + 1  # quiz + surprise + private
    assert any(q.get("note") == "From an earlier module" for q in exam["questions"])
    # The exam itself carries no answers.
    assert "right" not in json.dumps(exam) and "key" not in exam

    # Tampered exam is refused.
    bad = copy.deepcopy(exam)
    bad["pass"] = 0
    with pytest.raises(exchange.FileProblem):
        checks.import_exam(learner, bad)
    checks.import_exam(learner, exam)
    assert checks.my_exams(learner, j)[0]["taken"] is False

    # Learner answers everything with the first choice; the checker grades.
    answers = {q["id"]: q["choices"][0]["id"] for q in exam["questions"]}
    learner.add_event(j, "exam_taken", {"exam": exam["id"], "req": "m2-quiz", "task": exam["task"],
                                        "checker": exam["checker"]["id"], "answers": answers})
    assert checks.my_exams(learner, j)[0]["taken"] is True
    data2 = progress_with(learner, j)
    ev = [e for m in data2["milestones"] for e in m["body"]["events"] if e["type"] == "exam_taken"][0]
    graded = checks.grade_exam_event(checker, ev["data"])
    assert graded["total"] == 5 and 0 <= graded["score"] <= 5

    # Results + a file request travel back in the signed reply.
    extras = checks.sign_extras(checker, data2["learner"]["id"], j,
                                [{k: graded[k] for k in ("exam", "score", "total", "percent", "passed")}], [])
    approval = roundtrip(exchange.make_approval_file(checker, data2, "approved", "", [2], extras))
    res = exchange.import_approval_file(learner, approval)
    assert res["results"] == 1
    assert checks.my_exams(learner, j)[0]["result"]["score"] == graded["score"]

    # Learner can't change their score in the reply.
    approval["extras"]["exam_results"][0]["score"] = 99
    with pytest.raises(exchange.FileProblem):
        exchange.import_approval_file(learner, approval)


def test_file_request_and_pack(tmp_path):
    learner, checker = make_people(tmp_path)
    j = learner.start_journey("python-basics")
    sha = learner.save_evidence(j, "m1-practical", "hello.py", b"print('hi')", task="Write a program")
    data = progress_with(learner, j)
    checker.store_received(data)
    extras = checks.sign_extras(checker, learner.identity.id, j, [], [{"sha256": sha, "name": "hello.py"}])
    exchange.import_approval_file(learner, roundtrip(exchange.make_approval_file(checker, data, "question", "Send it", [1], extras)))
    assert checks.requests_for(learner, j)[0]["sha256"] == sha

    pack = checks.make_file_pack(learner, j)
    assert checks.is_file_pack(pack)
    res = checks.import_file_pack(checker, pack)
    assert res["count"] == 1
    assert checks.received_file(checker, sha) == (b"print('hi')", "hello.py")

    # A swapped file is caught.
    zf = zipfile.ZipFile(io.BytesIO(pack))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z2:
        for n in zf.namelist():
            z2.writestr(n, b"evil" if n.startswith("files/") else zf.read(n))
    with pytest.raises(exchange.FileProblem):
        checks.import_file_pack(checker, out.getvalue())


def test_similar_writeups_and_course_differences(tmp_path):
    learner, checker = make_people(tmp_path)
    other = Vault(tmp_path / "lina")
    other.setup("Lina")
    other.install_course(sample())
    checker.add_person(other.identity.id, "Lina", "#B4691B", False, True)
    text = "print shows text on the screen so the person can see results of the program right away"
    for v in (learner, other):
        j = v.start_journey("python-basics")
        v.add_event(j, "writeup_saved", {"req": "m1-explain", "task": "Explain print", "text": text, "words": 17})
        checker.store_received(progress_with(v, j))
    data = checker.received(learner.identity.id)[0]["data"]
    warn = checks.similar_writeups(checker, data)
    assert warn and "100% the same as Lina" in warn[0]

    # Checker's copy of the course differs from the learner's.
    changed = sample()
    changed.modules[1]["requires"] = changed.modules[1]["requires"][:2]
    changed.hash = "different"
    diffs = checks.outline_differences(changed, data["outline"], data["journey"]["course"]["hash"])
    assert any("Only in their copy" in d and "quiz" in d for d in diffs)
