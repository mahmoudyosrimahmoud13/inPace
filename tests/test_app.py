"""Two people, two vaults, the whole loop through the real web pages."""
import json
import re

from starlette.testclient import TestClient

from inpace.app import create_app
from inpace.vault import Vault


def client(tmp_path, name):
    v = Vault(tmp_path / name)
    c = TestClient(create_app(v))
    r = c.post("/setup", data={"name": name, "color": "#1F7A56"})
    assert r.status_code == 200 and f"Hi {name}" in r.text
    return v, c


def upload(c, filename, data):
    return c.post("/open", files={"file": (filename, data)})


def test_everything(tmp_path):
    lv, learner = client(tmp_path, "Omar")
    cv, checker = client(tmp_path, "Sara")

    # Every page loads.
    for path in ["/", "/courses", "/milestones", "/people", "/open", "/ai", "/settings"]:
        assert learner.get(path).status_code == 200, path

    # Swap contact cards.
    omar_card = learner.get("/people/card").content
    sara_card = checker.get("/people/card").content
    r = upload(learner, "sara.inpace", sara_card)
    assert "How are you connected?" in r.text
    card_json = re.search(r'<textarea name="card" hidden>(.*?)</textarea>', r.text, re.S).group(1)
    import html
    learner.post("/people/add", data={"card": html.unescape(card_json), "relationship": "checks_me"})
    assert lv.my_checkers()[0]["name"] == "Sara"

    # Learner adds the sample course and starts it.
    learner.post("/courses/sample/python-basics")
    r = learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    assert "Your first Python" in r.text

    # Lessons, locked module, tasks.
    assert learner.get(f"/learn/{jid}/lesson/m2-l1").url.path == f"/learn/{jid}"  # locked
    r = learner.get(f"/learn/{jid}/lesson/m1-l1")
    assert "What is Python?" in r.text and "<script" not in r.text.split('class="prose"')[1].split("</article>")[0]
    learner.post(f"/learn/{jid}/lesson/m1-l1/done", data={"next": "m1-l2"})
    learner.post(f"/learn/{jid}/lesson/m1-l2/done", data={})
    learner.post(f"/learn/{jid}/task/m1-practical/evidence", files={"file": ("hello.py", b"print('Omar', 7*6)")})
    learner.post(f"/learn/{jid}/task/m1-explain/writeup", data={"text": "print shows things on the screen " * 8})

    # Quiz: read the page, answer everything correctly using the course answers.
    r = learner.get(f"/learn/{jid}/task/m1-quiz/quiz")
    seed = re.search(r'name="seed" value="([0-9a-f]+)"', r.text).group(1)
    course = lv.get_course("python-basics")
    from inpace.exam import build_exam
    exam = build_exam(course, ["q1", "q2", "q3"], seed)
    answers = {q["id"]: next(c["id"] for c in q["choices"] if c["id"] in course.answers[q["id"]]["right"]) for q in exam}
    r = learner.post(f"/learn/{jid}/task/m1-quiz/quiz", data={"seed": seed, **answers})
    assert "You passed" in r.text
    assert lv.progress(jid)["modules"][0]["status"] == "done"
    r = learner.get(f"/learn/{jid}/module/m1")
    assert "Module done" in r.text and "hello.py" in r.text

    # Milestone + progress file.
    r = learner.post(f"/milestones/{jid}/save")
    assert "Milestone 1 saved" in r.text
    progress = learner.get(f"/milestones/{jid}/export")
    assert progress.headers["content-disposition"].startswith("attachment")

    # Checker opens the progress file from someone unknown -> adds them -> reviews.
    r = upload(checker, "omar.inpace", progress.content)
    assert "You don't check Omar" in r.text
    pj = re.search(r'<textarea name="progress" hidden>(.*?)</textarea>', r.text, re.S).group(1)
    r = checker.post("/people/add-learner", data={"progress": html.unescape(pj), "nickname": "Omar (cousin)"})
    assert "Nothing was changed since you last checked" in r.text
    assert "hello.py" in r.text and "Omar (cousin)" in r.text
    assert "What is Python?" in r.text  # names show even though the checker doesn't have the course

    # Approve -> reply file.
    learner_id = lv.identity.id
    r = checker.post(f"/review/{learner_id}/{jid}", data={"decision": "approved", "note": "Great start!"})
    reply_name = re.search(r'href="/outbox/([^"]+)"', r.text).group(1)
    reply = checker.get(f"/outbox/{reply_name}").content

    # Learner opens the reply.
    r = upload(learner, "reply.inpace", reply)
    assert "Sara approved 1 milestone" in r.text and "Great start!" in r.text
    assert "Approved by Sara" in learner.get("/").text

    # ---- Phase C through the screens -------------------------------------
    # Checker gets the course with answers, makes a verified exam with a private question.
    upload(checker, "course.lpack", learner.get("/courses/python-basics/export?answers=1").content)
    r = checker.get(f"/review/{learner_id}/{jid}")
    assert "Send a verified exam" in r.text
    checker.post(f"/review/{learner_id}/{jid}/exam/m2-quiz",
                 data={"action": "add_question", "text": "What did you print?", "right": "My name", "wrong": "A cat\nNothing"})
    r = checker.get(f"/review/{learner_id}/{jid}/exam/m2-quiz")
    pid = re.search(r'name="private" value="([^"]+)"', r.text).group(1)
    r = checker.post(f"/review/{learner_id}/{jid}/exam/m2-quiz", data={"action": "make", "surprise": "1", "private": pid})
    exam_name = re.search(r'href="/outbox/([^"]+)"', r.text).group(1)
    exam_file = checker.get(f"/outbox/{exam_name}").content

    # Learner opens it, takes it once.
    r = upload(learner, "exam.inpace", exam_file)
    assert "Verified exam" in r.text and "won't see the answers" in r.text
    exam = json.loads(exam_file)
    r = learner.post(f"/learn/{jid}/exam/{exam['id']}", data={q["id"]: q["choices"][0]["id"] for q in exam["questions"]})
    assert "Answers saved" in r.text
    assert "already took" in learner.get(f"/learn/{jid}/exam/{exam['id']}").text
    learner.post(f"/milestones/{jid}/save")
    r = upload(checker, "omar2.inpace", learner.get(f"/milestones/{jid}/export").content)
    assert "Verified exam" in r.text and re.search(r"\d of 5 \(\d+%\)", r.text)

    # Checker asks for hello.py and approves; learner gets the score and the request.
    sha = re.search(r'name="request" value="([0-9a-f]{64})\|', r.text).group(1)
    r = checker.post(f"/review/{learner_id}/{jid}", data={"decision": "approved", "request": f"{sha}|hello.py"})
    reply_name = re.search(r'href="/outbox/([^"]+)"', r.text).group(1)
    r = upload(learner, "reply2.inpace", checker.get(f"/outbox/{reply_name}").content)
    assert "Your exam score is in" in r.text and "asked to see 1 file" in r.text
    assert "Download file pack" in learner.get("/milestones").text
    pack_resp = learner.get(f"/milestones/{jid}/files")
    assert "Download file pack" not in learner.get("/milestones").text  # request cleared once sent
    r = upload(checker, "files.zip", pack_resp.content)
    assert "Got 1 file(s)" in r.text and f'href="/files/{sha}"' in r.text
    assert checker.get(f"/files/{sha}").content == b"print('Omar', 7*6)"

    # AI course maker: prompt + paste + save.
    r = learner.post("/ai", data={"action": "prompt", "topic": "Budgeting", "level": "beginner", "weeks": "2",
                                  "hours": "2", "language": "English"})
    assert "Budgeting" in r.text and "Copy prompt" in r.text
    reply_text = """```yaml
title: Budgeting
modules:
  - title: Basics
    lessons:
      - title: Why budget
        content: "## Why budget\\nKnow where money goes."
    requires:
      - type: quiz
        questions: [q1]
questions:
  q1:
    text: What is a budget?
    right: [A plan for your money, A spending plan]
    wrong: [A bank, A loan, A tax, A bill]
```"""
    r = learner.post("/ai", data={"action": "check", "reply": reply_text})
    assert "Preview" in r.text and "Why budget" in r.text
    r = learner.post("/ai", data={"action": "save", "reply": reply_text})
    assert "Saved “Budgeting”" in r.text

    # Bad AI answer gives plain-language problems.
    r = learner.post("/ai", data={"action": "check", "reply": "title: X\nmodules: []"})
    assert "at least one module" in r.text

    # A single .yaml course file through "Open a file".
    yaml_course = reply_text.replace("Budgeting", "Saving money").encode()
    r = upload(checker, "saving.yaml", yaml_course)
    assert "Added the course “Saving money”" in r.text
    r = upload(checker, "split.yaml", b"title: Split\nmodules:\n  - title: A\n    lessons:\n      - file: lessons/a.md\n")
    assert "Put course.yaml and the lessons folder together in a zip" in r.text

    # Course export without answers, re-import elsewhere.
    pack = learner.get("/courses/python-basics/export").content
    r = upload(checker, "course.lpack", pack)
    assert "Added the course" in r.text and cv.get_course("python-basics").has_answers  # kept the answers it had
    _, third = client(tmp_path, "Lina")
    assert "practice quizzes are off" in upload(third, "course.lpack", pack).text


def test_phase_d_screens(tmp_path):
    lv, learner = client(tmp_path, "Omar")
    learner.post("/courses/sample/python-basics")
    learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    assert "Weekly goal" not in learner.get("/").text and "Set a weekly goal" in learner.get("/").text
    r = learner.post(f"/learn/{jid}/do/commit", data={"per_week": "3"})
    assert "Your goal: 3 milestones a week" in r.text and "0 / 3" in r.text
    r = learner.post(f"/learn/{jid}/do/pause", data={"reason": "exams"})
    assert "On a break" in r.text and "I'm back" in r.text
    r = learner.post(f"/learn/{jid}/do/resume")
    assert "Welcome back" in r.text
    r = learner.post(f"/learn/{jid}/do/reflect", data={"learned": "print", "hard": "", "next": "lists"})
    assert "Reflection saved" in r.text
    # A practice quiz fills the review deck; wrong answers are due tomorrow, not today.
    for l in ("m1-l1", "m1-l2"):
        learner.post(f"/learn/{jid}/lesson/{l}/done", data={})
    r = learner.get(f"/learn/{jid}/task/m1-quiz/quiz")
    seed = re.search(r'name="seed" value="([0-9a-f]+)"', r.text).group(1)
    learner.post(f"/learn/{jid}/task/m1-quiz/quiz", data={"seed": seed})
    from inpace import pace
    assert pace.card_count(lv, "python-basics") == 3
    # Backup download works and needs a password.
    assert "at least 6" in learner.post("/settings/backup", data={"password": "123"}).text
    b = learner.post("/settings/backup", data={"password": "longpassword"})
    assert b.content.startswith(b"INPACEBK1")


def test_phase_e_screens(tmp_path):
    lv, learner = client(tmp_path, "Omar")
    learner.post("/courses/sample/python-basics")
    learner.post("/courses/python-basics/start")
    jid = lv.journeys()[0]["id"]
    assert "Start a race" in learner.get("/races").text
    r = learner.post("/races/new", data={"name": "Sprint", "kind": "points", "days": "14", "journey": jid})
    assert "Race created" in r.text and "Omar (you)" in r.text
    rid = lv.db.execute("SELECT id FROM races").fetchone()["id"]
    invite = learner.get(f"/races/{rid}/invite").content
    _, lina = client(tmp_path, "Lina")
    lina.post("/courses/sample/python-basics")
    lina.post("/courses/python-basics/start")
    r = upload(lina, "invite.inpace", invite)
    assert "Join the race" in r.text
    race_json = re.search(r'<textarea name="race" hidden>(.*?)</textarea>', r.text, re.S).group(1)
    import html as _h
    lj = re.search(r'<option value="([0-9a-f]+)"', r.text).group(1)
    r = lina.post("/races/join", data={"race": _h.unescape(race_json), "journey": lj})
    assert "You joined" in r.text
    r = upload(learner, "u.inpace", lina.get(f"/races/{rid}/update").content)
    assert "Got Lina" in r.text and "Lina" in r.text

    # Learning record and course editor pages.
    for l in ("m1-l1",):
        learner.post(f"/learn/{jid}/lesson/{l}/done", data={})
    learner.post(f"/milestones/{jid}/save")
    rec = learner.get(f"/milestones/{jid}/record")
    assert rec.headers["content-type"].startswith("text/html") and b"Verify this record" in rec.content
    r = learner.post("/edit/new", data={"title": "Baking", "module_title": "Bread", "lesson_title": "Flour",
                                         "content": "Use strong flour."})
    assert "Course created" in r.text and "Question bank" in r.text
    r = learner.post("/edit/baking", data={"action": "add_question", "text": "Best flour?", "right": "Strong flour",
                                            "wrong": "Sand\nSugar\nSalt"})
    assert "Saved" in r.text and "Best flour?" in r.text
    assert "Edit lesson" in learner.get("/edit/baking/lesson/m1-l1").text


def test_arabic_interface(tmp_path):
    lv, c = client(tmp_path, "Omar")
    c.post("/settings", data={"name": "Omar", "color": "#1F7A56", "lang": "ar"})
    r = c.get("/")
    assert 'dir="rtl"' in r.text and "الرئيسية" in r.text and "أهلًا Omar" in r.text
    c.post("/settings", data={"name": "Omar", "color": "#1F7A56", "lang": "en"})
    assert 'dir="ltr"' in c.get("/").text
