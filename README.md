<p align="center"><img src="inpace/static/icon.svg" width="88" alt="inPace logo"></p>

<h1 align="center">inPace</h1>
<p align="center"><b>Learn at your pace. Prove you kept it.</b><br>
A free, open-source app that helps you follow a course and lets someone you trust check that you're really keeping up. Everything stays on your computer.</p>

---

## What it does

- **Follow a course step by step.** Lessons, then tasks: upload your work, explain it in your own words, take a quiz. The next module unlocks when you finish.
- **Save milestones.** Each milestone is signed by you and linked to the one before it, so your history can't be quietly rewritten.
- **Get checked by someone you trust.** Send your progress file to a friend, parent or mentor. They open it in their own inPace, see what you did, and approve it. They don't need to know the subject.
- **Check others too.** Anyone can be a learner and a checker at the same time. Study buddies check each other.
- **Make courses with AI.** Describe a topic, copy the prompt into any AI chat, paste the answer back. inPace checks it and turns it into a course.
- **Fair quizzes.** Each question has several right answers and several wrong ones. Every quiz shows one right answer mixed with wrong ones, in a new random order each time.
- **Private by design.** No accounts, no internet, no tracking. Files only leave your computer when you send them yourself.

## Try it

You need **Python 3.10 or newer** ([download it here](https://www.python.org/downloads/)). On Windows, tick "Add Python to PATH" when installing.

```bash
pip install git+https://github.com/mahmoudyosrimahmoud13/inpace.git
inpace
```

Your browser opens inPace. Keep the black terminal window open while you use it. Close it to stop.

**Try both sides on one computer:** open a second terminal and run

```bash
inpace --home ~/inpace-checker
```

That starts a second, separate person (in a new browser tab), so you can play learner and checker.

## How the checking works

1. You and your checker swap **contact cards** (People → Download my contact card).
2. You learn, then **save a milestone** and **download your progress file**.
3. You send it to your checker any way you like: WhatsApp, email, USB.
4. Your checker opens it. inPace tells them if anything was changed since they last checked.
5. They approve (or ask a question, or flag a problem) and send back a small reply file.
6. You open the reply. Done.

## What it proves, and what it doesn't

We want to be honest about this.

- **It proves:** the steps of the course were followed in order, the work you added exists, and your history wasn't changed after your checker saw it.
- **It doesn't prove:** that every minute was real study, or that you truly learned. No app can.
- **Quizzes:** in this version they are practice quizzes. Courses shared publicly come with their answers, so a determined person could look them up. The strongest proof is your own work and your own explanations, which your checker reads.

## Courses

A course is a `.lpack` file (a zip) with:

```text
course.yaml      the modules, lessons and tasks
lessons/*.md     lesson text (Markdown)
questions.yaml   the questions and all possible answers
answers.yaml     which answers are right (left out when sharing with learners)
```

See [SPEC.md](SPEC.md) for the full format. A sample course, *Python Basics*, is built in.

## For developers

```bash
git clone git@github.com:mahmoudyosrimahmoud13/inpace.git
cd inpace
pip install -e ".[test]"
pytest
```

Built with Python, Starlette, Jinja, SQLite and PyNaCl (Ed25519 signatures). No JavaScript framework, no build step. Tests run on Windows, macOS and Linux on every push.

**Roadmap:** verified exams sent by the checker, a course editor, Arabic and right-to-left layout, pace races with friends, encrypted backups, an offline verifier page, and one-click installers.

## License

MIT. Free to use, change and share.
