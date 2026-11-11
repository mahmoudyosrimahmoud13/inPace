<p align="center"><img src="inpace/static/icon.svg" width="88" alt="inPace logo"></p>

<h1 align="center">inPace</h1>
<p align="center"><b>Learn at your pace. Prove you kept it.</b><br>
A free, open-source app that helps you follow a course and lets someone you trust check that you're really keeping up. Everything stays on your computer.</p>
<p align="center"><a href="https://mahmoudyosrimahmoud13.github.io/inPace/"><b>Website</b></a> · <a href="https://github.com/mahmoudyosrimahmoud13/inpace/releases/latest"><b>Download</b></a></p>

---

## What it does

**Learn**
- **Follow a course step by step.** Lessons, then tasks: upload your work, explain it in your own words, take a quiz. The next module unlocks when you finish.
- **Make courses four ways:** with any AI chat (copy, paste), with simple forms, by opening a course file someone shared, or from a folder of videos you already have (nothing is copied).
- **Videos, audio, web pages and more.** Lessons play videos and audio, show PDFs, run interactive pages safely, and play YouTube or Vimeo links (only when you press play). Record a voice note as proof for a task.
- **Fair quizzes.** Each question has several right and wrong answers. Every quiz shows one right answer mixed with wrong ones, in a new order each time.
- **Daily review.** Old questions come back over days and weeks so they stick.

**Stay on track**
- **Milestones.** Each one is signed by you and linked to the one before it, so your history can't be quietly rewritten.
- **A checker you trust.** Send your progress file to a friend, parent or mentor. They see what you did and approve it. They don't need to know the subject.
- **Weekly goals and breaks.** Set a pace, see your streak and finish date. Planned breaks don't count against you.
- **Pace races.** Race friends. Only approved milestones count, so it stays fair.

**Proof that holds up**
- **Verified exams.** Your checker's app makes the exam and keeps the answers. You take it once, offline, and their app grades it.
- **See the real work.** Checkers can ask for any file you added, and inPace confirms it's the original.
- **Learning record.** One web page you can share or link from a résumé. Anyone can click "Verify" to check it.

**Yours**
- **Private by design.** No accounts, no internet, no tracking. Files only leave your computer when you send them.
- **English and Arabic** (Arabic in beta), light and dark mode, and small screens too.
- **Encrypted backups** you can restore on any computer.

## Download

Go to the [Releases page](https://github.com/mahmoudyosrimahmoud13/inpace/releases/latest) and download the file for your computer:

- **Windows:** `inPace-windows.zip`. Unzip it, then double-click `inPace.exe`.
- **Mac:** `inPace-mac.dmg`. Open it and drag inPace into Applications.
- **Ubuntu / Debian:** `inPace-linux.deb`. Double-click it to install (or run `sudo apt install ./inPace-linux.deb`), then open inPace from your apps.
- **Other Linux:** `inPace-linux.tar.gz`. Unpack it and run `inPace`.

inPace opens in its own window. Everything stays on your computer.

(Using the plain Linux `.tar.gz`? For the app window, install `python3-gi` and `gir1.2-webkit2-4.1` once: `sudo apt install python3-gi gir1.2-webkit2-4.1`. Without them, inPace opens in Chrome or Edge as an app window, or in a browser tab.)

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

## Changing checkers or computers

- **New checker:** just add them. They see your full history the first time they open your progress file.
- **New computer:** make a backup (Settings → Backups), then restore it on the new computer. Your key and history move with it.
- **Lost everything without a backup:** start again with a new setup. Your old checker can still see what they approved before.

## Courses

A course is a `.lpack` file (a zip) with:

```text
course.yaml      the modules, lessons and tasks
lessons/*.md     lesson text (Markdown)
questions.yaml   the questions and all possible answers
answers.yaml     which answers are right (left out when sharing with learners)
```

See [SPEC.md](SPEC.md) for the full format. A sample course, *Python Basics*, is built in. More free courses are in the [community course library](community-courses).

## For developers

```bash
git clone git@github.com:mahmoudyosrimahmoud13/inpace.git
cd inpace
pip install -e ".[test]"
pytest
```

Built with Python, Starlette, Jinja, SQLite and PyNaCl (Ed25519 signatures). No JavaScript framework, no build step. Tests run on Windows, macOS and Linux on every push.

**Making a release:** push a version tag (`git tag v0.2.0` then `git push --tags`). GitHub tests everything, builds the Windows, Mac and Linux apps, checks that each one starts, and attaches them to a new release.

**Translations:** interface text lives in `inpace/locales/`. Add a language by copying `ar.json`.

## License

MIT. Free to use, change and share.
