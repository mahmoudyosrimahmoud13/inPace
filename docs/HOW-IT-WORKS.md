# How inPace works

inPace runs on your own computer or Android phone with no server, no account and no cloud. This page explains what happens when you use it, in plain words.

- **Using the app?** The [guide](https://mahmoudyosrimahmoud13.github.io/inPace/guide.html) shows every feature step by step.
- **Want the exact file formats?** See [SPEC.md](../SPEC.md).

---

## The short version

- **inPace is a small website that only lives on your computer.** When you open it, it starts a tiny web server that only your own computer can reach (`127.0.0.1`). It shows that server's pages in its own app window.
- **The Android app is the same inPace.** It carries Python inside it and runs the very same server on the phone. A full-screen Flutter window shows its pages. See [section 12](#12-on-android).
- **Everything is saved in one folder** on your computer, called your data folder.
- **Your progress is signed.** Each milestone is signed with a key that only your computer has, and it's linked to the milestone before it. If anyone changes the history later, the signatures stop matching.
- **People check each other by swapping links or files.** You send your progress as a link (or a file). Your checker's inPace checks the signatures, and they send back a small approval the same way. Nothing goes through us.

---

## 1. Opening the app

When you double-click inPace:

1. **It closes any copy that's already running** with the same data folder, even an older version. So you never end up with two copies, or an old copy left running after an update.
2. **It starts the local server** on a local port. The port is saved in `running.json` in your data folder.
3. **It opens the app window.** It tries these in order and uses the first one that works:
   - **Windows and Mac:** the system's own web view (through pywebview).
   - **Linux:** a GTK + WebKit window. It draws with the CPU, so it doesn't turn black or spin up the fans on graphics drivers that don't cooperate.
   - **Anywhere:** Chrome or Edge in "app mode", which is a window with no tabs or address bar.
   - **Last resort:** a normal browser tab.

   To force one, set `INPACE_WINDOW`. To see which one would be picked, run `inpace --which-window`.
4. **It checks for updates once a day,** but only if you said yes the first time. Details are in [section 10](#10-updates).

---

## 2. Your data folder

By default this is `Documents/inPace`. You can pick another with `inpace --home <folder>` or the `INPACE_HOME` setting.

```text
inPace/
  identity.key      your private signing key (never leaves this folder unless you make a backup)
  vault.db          your history: events, milestones, people, settings (SQLite)
  courses/<id>/     each installed course: course.yaml, lessons, questions, answers
  media/<id>/       small files that came inside a course pack or that you added in the editor
  evidence/         every file you uploaded as proof, named by its fingerprint (SHA-256)
  course_history/   older versions of courses you edited, for Undo (the last 30)
  pending/<id>/     a newer copy of a course, waiting for you to choose what to do with it
  outbox/           progress files, cards and replies you made, ready to send
  received_files/   files a learner sent you when you asked to see their work
  updates/          downloaded app updates
  running.json      which port the running copy uses
```

- **History is append-only.** inPace never edits or deletes past events in `vault.db`. It only adds new ones. That's what makes the history trustworthy.
- **Backups** (Settings → Backups) put this whole folder into one password-protected file that you can restore on any computer.

---

## 3. Courses

A course is plain text: a `course.yaml` file with modules, lessons and tasks, plus lesson text in Markdown.

**Ways a course gets in** (all from the **Add a course** page):
- **A course file** someone shared (`.lpack`, `.zip` or `.yaml`).
- **A folder** of course material (videos, slides as PDF, notes, code). inPace makes a first guess, then shows the **organizer**:
  - A neat folder: each sub-folder is a section.
  - A messy folder: files are grouped by the week, lecture or chapter numbers in their names ("Lecture 3", "lec3", "W03", "محاضرة 3"). Files without a number go to "General" at the top. With no numbers at all, files are grouped by kind (videos, slides and PDFs, notes).
  - In the organizer you rename sections and lessons, drag files between sections (or use **Move to** and the arrows on a phone), add or remove sections, and leave files out.
  - **Ask AI to sort it:** the AI sees only the file names. With an AI key in Settings inPace asks it directly; without one you copy the request into any AI chat and paste the answer back. Files the AI forgets go to "Not sorted yet", and file names it makes up are ignored.
  - **Where the files live:** leave them where they are (the default: no extra space, and inPace only remembers where the folder is), or copy them into inPace (`media/<id>/`). Copying shows the size and the free space first, runs in the background, and the course works from the original folder until it finishes.
  - Word, PowerPoint and Excel files can't be shown inside inPace, so the organizer lists them and suggests saving them as PDF.
- **Some files you pick.** They're copied into inPace (`drafts/` first, then `media/<id>/`) and sorted in the same organizer. Handy on a phone.
- **A list of links,** one per line. A line starting with `#` starts a new module.
- **With AI.** inPace writes a prompt for a topic, a book, a playlist, a course you're taking, a project, your notes or an exam. You paste it into any AI chat and paste the answer back.
- **By hand,** in the course builder.

**Course pictures.** `image:` in `course.yaml` points to a picture next to the course. A picture added in the builder is saved as `media/<id>/cover.*`. A folder course uses a `cover`, `folder`, `poster`, `thumbnail` or `course` picture at the top of the folder. The picture goes inside the course file when you share it.

**Finding the files.** For each lesson file, inPace looks in this order:
1. The exact path, if the course gives a full path.
2. The course's own small files in `media/<id>/`.
3. The folder you pointed it to.

If a folder was moved or renamed, inPace also tries shorter and shorter endings of the path, so it usually still finds the files. If it can't, it asks you where the folder is now.

**Updating a course:**
- **A newer copy arrives.** When you open a course file you already have, but with different content, inPace keeps the new copy aside in `pending/`. It shows you what was added and what was removed, and you choose:
  - **Update my course:** your progress is kept, matched by lesson.
  - **Add it as a separate course:** you get two courses.
  - **Keep mine as it is.**

  If you change your mind, the old version is saved, so **Undo** in the builder brings it back.
- **Folder courses:** **Refresh from its folder** looks in the folder again. New videos become new lessons. Your edits, tasks and progress stay as they are.

**Deleting a course:**
- inPace removes the course and its own small files.
- Your signed milestones for that course are hidden, not erased, because your checker may already have them.
- Adding the course again later starts fresh.
- Your own video folders are never touched.

---

## 4. Lessons and media

Every file is served by the local server under `/m/<course>/<path>`. That keeps working when the course folder is somewhere else on your computer.

| Kind | What you see |
|---|---|
| Video | inPace's own player. It saves your position every few seconds, so you continue from the same second, even after you close the app. |
| Audio | A simple player that also remembers your position. |
| PDF | The built-in PDF reader ([pdf.js](https://mozilla.github.io/pdf.js/), bundled, works offline). It has page buttons, zoom, fit to width and full screen, and it remembers your page. |
| Code | Coloured code with a Copy button. A project folder shows all its code files. |
| Web page (HTML) | Runs in a locked box (a sandbox), so it can't touch the rest of the app. |
| YouTube, Vimeo | Loads only when you press play, using YouTube's privacy-enhanced mode (youtube-nocookie). Nothing is fetched before you press play. |
| Other links | A normal link that opens in your browser. |

---

## 5. Tasks, quizzes and review

Each module ends with tasks:
- **Practical task:** upload your work or record a voice note.
- **Explain task:** write the idea in your own words.
- **Quiz.**

**Uploaded files** are saved in `evidence/` under their SHA-256 fingerprint. Only the fingerprint goes into your history. If your checker asks to see a file later, their inPace checks that the file matches the fingerprint you signed back then.

**Quizzes are fair:**
- Each question has several right answers and several wrong ones.
- Each time, the quiz shows one right answer mixed with wrong ones, in a new order.
- Courses shared with learners leave out `answers.yaml`. Practice quizzes are then off, but checkers can still use the answers.

**Daily review** brings old questions back after 1, 3, 7, 14 and 30 days.

---

## 6. Milestones and checking

**What's in a milestone:**
- A short summary of what you did since the last one: lessons, tasks, scores and file fingerprints.
- The fingerprint of the milestone before it.
- Your signature, made with your key (Ed25519, through PyNaCl).

Because of the link and the signature, nobody can change one milestone without breaking every milestone after it.

**The checking loop:**

1. You and your checker connect with a **friend link**. You send it on Telegram, WhatsApp or email in one click. They tap it, inPace adds you, and one more tap sends their link back to you. Pasting the link, or swapping contact-card files, works too.
2. You **save a milestone**.
3. You **send your progress link**, or a progress file if it's too big for a link (see [section 8](#8-links-opening-inpace-from-other-apps)).
4. **Your checker's inPace checks every signature and link.** It warns them if anything changed since they last looked.
5. They **approve, ask a question, or flag a problem.** Their reply is a small signed file that you open in inPace.

**Extras checkers can use:**
- **Verified exams:** your checker's app builds an exam from a random seed and keeps the answers. You take it once, and their app grades it.
- **Asking to see your work:** you send a file pack, and their app accepts each file only if it matches a fingerprint you signed.
- **Races** with friends: only approved milestones count.
- **Learning record:** one web page that checks its own signatures in the browser.

---

## 7. Getting around

- **Search:** press **Ctrl+K** or **/** anywhere. Type a few letters to jump to any lesson, course, task, person or page. **My courses** also has a search box that filters your courses by title, description, module or lesson name.
- **Phones and narrow windows:** the sidebar becomes a tab bar at the bottom: Home, Courses, Add, Milestones, and More (races, the library, people, open a file, settings, dark mode). The top bar shows the page you're on.
- **Continue:** the sidebar card takes you back to the lesson you were last on.
- **Course outline:** shown on every lesson. Jump to any lesson, with ✓ marks on the ones you finished.
- **Back and forward:** the app window has no browser buttons, so inPace has its own at the top left. **Alt+← / Alt+→** and the side buttons on a mouse work too.
- **N / P:** next and previous lesson.
- **Colors and dark mode:** Settings → Colors has seven color profiles, each with light and dark shades. The moon button switches dark mode.
- **English and Arabic:** the whole app, right to left in Arabic.
- **The welcome tour:** Tempo the turtle shows you around the first time. You can replay it from Settings.

## 8. Links: opening inPace from other apps

Friend invites, progress, replies, race invites and race updates can all travel as a link. You can send them in any chat or email.

**What a link looks like:** `https://mahmoudyosrimahmoud13.github.io/inPace/open#…`
- Everything after `#` is the inPace data, compressed (zlib, then base64).
- Browsers never send the part after `#` to the website, so GitHub never sees it.
- The link carries the same signed data a file would, so checking works exactly the same.

**What happens when someone taps it:**
1. The inPace website opens. It reads the link inside the browser and says what it is, for example "Layla wants to add you on inPace".
2. **Open in inPace** opens `inpace://open/…`. That starts inPace, or restarts it, straight on the right screen.
3. If inPace isn't installed, the same page shows the download for that computer.
4. If nothing opens, they can copy the link and paste it into **People → Add a friend** or **Open a file**.

**How the computer knows `inpace://` links belong to inPace:**

| Computer | How |
|---|---|
| Windows | inPace adds a per-user registry entry on every start. No admin rights needed. |
| Mac | Declared in the app's `Info.plist`. Links reach the running app as Apple events. |
| Ubuntu / Debian (`.deb`) | Declared in the installed `inpace.desktop`. |
| Other Linux and running from source | inPace writes `~/.local/share/applications/inpace-link.desktop`, unless another app already handles these links. |

**Only what's new:**
- A checker who replied about milestone N already has the whole history up to N.
- So a progress link only carries the milestones after the last one **all** your checkers have replied to, and it skips the course outline.
- The checker's app joins the new part to the copy it already has, then checks the **whole** history as usual. Nothing is taken on trust.
- If their copy is missing, inPace asks for the full progress file.

**Too big:** a link is offered only up to 3,500 characters, which fits in a Telegram message. Above that, inPace says so and you send the file instead.

**Privacy:** a link sent in a chat app passes through that app, just like a file would.

---

## 9. The course library

The [course library](https://github.com/mahmoudyosrimahmoud13/inpace-library) is a separate public GitHub repository. GitHub stores the courses, checks them and
publishes them, so there's still no inPace server.

**Adding a course from the library:**
- **Course library** in the app downloads `library.json` from the library's GitHub Pages site. It only goes online
  when you open that page, and it keeps a copy for an hour.
- **Add** downloads the course file and checks its SHA-256 against the list before installing it.
- A newer version goes through the normal update flow (section 3), so your progress is kept.

**Publishing a course:**
1. **More → Publish to the library** makes a `.zip` with the course (with answers), its small files such as the
   cover picture, and `inpace-author.json`.
2. That file is the author's name and key, signed together with the course's fingerprint. Change one letter of the
   course and the signature stops matching.
3. The submission form on GitHub opens with the details filled in. The author attaches the file and submits.
4. A GitHub Action checks it:
   - The course loads and the signature matches.
   - It's under 20 MB, a license was chosen, and both promises were ticked.
   - If the id already exists, it must be signed by the same key. That's how only the author can update a course.
5. If it passes, the bot opens a pull request. A maintainer merges it, and another Action rebuilds `library.json`,
   the course files and the library page.

**Sharing a library course:** **More → Send a link** makes an inPace link that only holds the course id, title and
author. The person who taps it lands on that course in their own Course library and adds it from there. If the
course isn't in the library, the page offers to publish it or send the file.

**Big videos:** a course can list `downloads:` in `course.yaml` (title, link, size). Learners see **Get this
course's videos**, download them, and choose the folder. The lessons' relative paths then find every file.

---

## 10. Updates

The first time you open inPace, it asks if it may keep itself up to date.

**If you say yes:**
1. Once a day, it checks the latest GitHub release.
2. It downloads the file for your computer.
3. It checks the file against the release's `SHA256SUMS`.
4. It installs the update:

| Install | How it updates |
|---|---|
| Windows | Swaps `inPace.exe` and keeps the old one as `.old`. |
| Mac | Replaces the app in Applications. |
| Ubuntu / Debian (`.deb`) | Installs the new package. Linux asks for your password once. |
| Other Linux (`.tar.gz`) | Swaps the app folder. |
| Run from source | Asks you to `git pull`. |
| Android | Doesn't update itself. Settings points to the website: download the new APK and tap **Update**. |

**If you say no,** Settings → Updates still shows you when a new version is out.

---

## 11. When inPace goes online

Only for things you turn on or press:
- The update check.
- Opening the **Course library**, adding a course from it, or loading course pictures there.
- Opening an online video you pressed play on.
- Looking up YouTube titles when you paste links, if you tick that box.
- A share button you click for Telegram, WhatsApp or email. That opens that app with your message ready.
- Opening an inPace link shows the inPace website first. The data after `#` stays in your browser.

**The AI course maker** never sends anything by itself. You copy the prompt and paste it yourself.

---

## 12. On Android

The phone app is the full inPace, not a smaller copy. The same Python code, pages and data format run on the phone.

**How it starts**
1. The app is a small [Flutter](https://flutter.dev) shell (`mobile/`). It has Python 3.12 and inPace's libraries inside it (through [serious_python](https://pub.dev/packages/serious_python)).
2. It picks a free port and starts inPace's server on `127.0.0.1`, exactly like on a computer. Only the phone itself can reach it.
3. It waits until the server answers (`/ping`), showing a start screen meanwhile, then shows the pages full screen in a web view.
4. The pages know they're on a phone (`INPACE_MOBILE=android`), so they hide things that only make sense on a computer, like the update bar and the **Quit** button.

**Your data** lives in the app's private storage, in an `inPace` folder with the same layout as [section 2](#2-your-data-folder). Other apps can't read it. Uninstalling the app deletes it, so make a backup first.

**What the Flutter shell adds,** because there's no browser around the pages:

| You do | On the phone |
|---|---|
| Tap a link to a website, Telegram, WhatsApp or email | Opens in that app |
| Open an `inpace://` link from another app | inPace opens on that screen (friend links, progress, course links) |
| Download a file inPace made (progress, course file, backup, contact card) | A menu: **Send it** (the share sheet) or **Save it on this phone** |
| Press **Add a file** or **Some files I pick** | Android's file picker. The files are copied into inPace. |
| Press **Choose folder** | Android's folder picker. The first time, Android asks for "All files access", which inPace needs to read videos where they are. It only reads the folders you choose. |
| Record a voice note | Asks for the microphone the first time |
| Play a video full screen, or press the back button | Works as you'd expect. Back goes back inside inPace. |
| Press **More apps…** to share | Android's share sheet |

**The layout** is the same pages as on a computer. On narrow screens the sidebar becomes a tab bar at the bottom (Home, Courses, Add, Milestones, More), and buttons and fields get bigger.

**Updates and the signing key.** Every APK is signed with the same inPace release key, so a new version installs over the old one and keeps your data. Android refuses an update signed with a different key. The key lives in the repository's GitHub secrets (`ANDROID_KEYSTORE_BASE64` and `ANDROID_KEYSTORE_PASSWORD`). Tag builds stop if it's missing.

**Phone and computer** don't sync by themselves. Your signing key and history move with a backup: make one in Settings on one device and restore it on the other.

**How it's built** (`.github/workflows/android.yml`, on every version tag or by hand):
1. `flutter create` makes the Android project fresh. It isn't kept in git.
2. `mobile/tools/prepare_android.py` adjusts it: the app name, permissions, `inpace://` links, the minimum Android version (7), the signing key, and the plugins' Android SDK. It also makes the Python downloads run one at a time, because running them together corrupted a shared download file.
3. The icon comes from `mobile/icon/res` (made with IconKitchen).
4. `serious_python` packages Python, PyNaCl and inPace itself (`mobile/app/src`).
5. `flutter build apk` makes `inPace-android-arm64-v8a.apk` for 64-bit phones, which is nearly every Android phone from the last 7 years. It's attached to the GitHub release.

To build it on your own computer you need Flutter, Java 21 and the Android SDK, then run `bash mobile/build_android.sh`.

---

## 13. For developers: where the code is

```text
inpace/
  __main__.py     starts everything: single copy, server, window, update thread
  app.py          all pages and routes (Starlette)
  window.py       the app window (pywebview, GTK/WebKit helper, Chrome/Edge app mode)
  vault.py        the data folder, SQLite history, courses, media lookup
  course.py       reading and checking course files, folders to courses, media kinds
  editor.py       the course builder: changes, Undo history, YAML in and out
  media.py        players and viewers for each kind of lesson file
  identity.py     keys and signatures (Ed25519)
  canon.py        the exact byte form that gets signed and fingerprinted
  exchange.py     progress, approval, card and pack files, and links that carry them
  links.py        opening inPace from inpace:// links on each kind of computer
  library.py      the course library: signed course files, the list, downloads
  checks.py       what the checker sees: verifying a learner's history and files
  exam.py         quizzes and verified exams from a seed
  pace.py         weekly goals, streaks, breaks, finish dates
  races.py        races between friends
  record.py       the shareable learning record page
  ai.py           AI prompts for each kind of source
  updater.py      update check, download, verify, install
  integrations.py native folder picker, AI connections and other small OS helpers
  organize.py     sorting a neat or messy folder into a course plan, AI sorting, copying files in
  templates/      pages (Jinja)
  static/         CSS, JavaScript, fonts, icons, pdf.js
  locales/ar.json Arabic text
packaging/        PyInstaller builds for Windows, Mac, .deb and .tar.gz
mobile/           the Android app: Flutter shell (lib/main.dart), build script, icon, project fixes
site/             the website (GitHub Pages)
tests/            pytest, run on Windows, Mac and Linux on every push
```

**Releases:** push a tag like `v1.10.0`. GitHub runs the tests, builds the apps, checks that each one starts, writes `SHA256SUMS` and publishes the release. A second workflow builds the Android APK and adds it to the same release. The website deploys from `site/` on every push to main.
