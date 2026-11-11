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
- **Verified exams.** Your checker's app makes an exam and keeps the answers. You take it offline, once, and their app grades it. Checkers can add their own private questions and a surprise question from an earlier module.
- **See the real work.** Your checker can ask for any file you added, and inPace confirms it's exactly the file from your milestones.
- **Extra checks.** Warns a checker when two learners' answers are nearly the same, or when someone's copy of the course is different.
- **Private by design.** No accounts, no internet, no tracking. Files only leave your computer when you send them yourself.

## Download

Go to the [Releases page](https://github.com/mahmoudyosrimahmoud13/inpace/releases/latest) and download the file for your computer:

- **Windows:** `inPace-windows.zip`. Unzip it, then double-click `inPace.exe`.
- **Mac:** `inPace-mac.dmg`. Open it and drag inPace into Applications.
- **Linux:** `inPace-linux.tar.gz`. Unpack it and run `inPace`.

inPace opens in its own window. Everything stays on your computer.

> The apps aren't signed yet. **Windows** may show "Windows protected your PC": click *More info*, then *Run anyway*.
> **Mac** may say it can't be opened: right-click inPace, choose *Open*, then *Open* again.

**With Python instead** (3.10 or newer): `pip install git+https://github.com/mahmoudyosrimahmoud13/inpace.git`, then run `inpace`.

**Try both sides on one computer:** run a second copy with its own data folder, `inpace --home ~/inpace-checker`, so you can play learner and checker.

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
- **Quizzes:** practice quizzes are for learning. Public courses come with their answers, so a determined person could look them up. **Verified exams** are stronger, and a checker's **private questions** can't be looked up at all. The strongest proof is still your own work and explanations, which your checker reads.

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

**Making a release:** push a version tag (`git tag v0.2.0` then `git push --tags`). GitHub tests everything, builds the Windows, Mac and Linux apps, checks that each one starts, and attaches them to a new release.

**Roadmap:** commitments and pace forecasts, pace races with friends, a course editor, the full app in Arabic, encrypted backups, and a shareable learning record.

## License

MIT. Free to use, change and share.
