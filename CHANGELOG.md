# Changelog

## v1.11.1

- **New sample course: FastAPI, from first API to production.** 12 modules and 35 lessons with code: parameters and validation, responses and errors, dependency injection, SQLAlchemy and Alembic, passwords and JWT logins, async and background work, testing, project structure and settings, WebSockets and streaming, pagination and caching, Docker and monitoring, and a final portfolio project. Every module ends with a practical task, an explain task and a quiz. It's also in the community course library.
- **Fixed the Linux release build:** the app window check now refreshes the package list before installing, so it no longer fails when GitHub's machine has an old list.
- Includes everything from v1.11.0 (its release build didn't finish).

## v1.11.0

- **Links instead of codes and files:**
  - Your friend link, progress, replies, race invites and race updates are now links you can send in any chat or email.
  - Tapping one opens the inPace website, which says what it is ("Layla wants to add you on inPace") and opens inPace straight on the right screen.
  - No inPace yet? The same page offers the download for that computer.
- **Open from any app:** inPace now handles `inpace://` links on Windows, Mac and Linux, so a link in Telegram, WhatsApp, email or the browser opens the app.
- **Connected both ways in one tap:** after you add someone, inPace offers **Send your link back**, with the same share buttons.
- **More ways to share:** Telegram, WhatsApp, **Email**, Copy, and **More apps…** (the system share menu) where the window supports it.
- **Small progress links:**
  - The link only carries the milestones your checkers haven't seen yet.
  - Their app joins it to the history it already has and checks the whole history, as always.
  - If it's ever too big for a link, inPace offers the file instead.
- **Easier back and forth:**
  - **Back and forward buttons** at the top left of every page.
  - **Alt+← / Alt+→** and the mouse side buttons also go back and forward.
  - **N / P** now go to the next and previous lesson (they used to be Alt+→ / Alt+←).
- **Search your courses:** a search box on My courses finds a course by its title, description, modules or lesson names. Each started course also shows how much is done.
- **Course pictures:** add a picture to any course (Edit → Course details → Add a picture). It shows on My courses and at the top of the course, and goes along when you share the course. A folder course picks up a `cover.jpg` (or `folder.jpg`, `poster.png`…) by itself. Courses without a picture get a coloured tile with their first letter. The sample Python courses now come with a picture.
- Old `inpace:` codes and files still work.

## Docs (after v1.10.0)

- **New: [How inPace works](docs/HOW-IT-WORKS.md)**, a plain-words explanation of the app window, the data folder, courses and media, updating and deleting courses, milestones and checking, updates, and when inPace goes online, plus a map of the code.
- **README** lists every current feature and links to it. **SPEC.md** now describes course updates and deleting a course.
- **Website:** a "What happens behind the scenes" block, new sections for the PDF reader, search, course updates and colors, and three new guide chapters (Find your way, Update or delete a course, Make it yours) with new screenshots.

## v1.10.0

- **Delete any course:** My courses → More → Delete course. A course you've started asks you to tick a box first, because your progress in it goes too. Progress files you already sent stay with your checker, and video folders on your computer are never touched.
- **Update courses:**
  - Open a newer copy of a course you already have, and inPace shows what changed and asks: update and keep my progress, add it as a separate course, or keep mine. Undo in the editor brings the old version back.
  - Folder courses get **Refresh from its folder**: new videos become new lessons, and everything you did stays.
- **Easier to get around:**
  - **Search and jump:** press Ctrl+K (or /), or click Search in the top bar, to jump to any course, lesson, task, person or page.
  - **Continue:** the side bar always shows the lesson you were last on.
  - **Course outline:** every lesson has a Course outline you can open to jump anywhere in the course.
  - Alt+→ and Alt+← go to the next and previous lesson.
- **Color profiles:** Settings → Colors: Sunny, Ocean, Mint, Rose, Grape, Nile or Ink. They change the whole app, in light and dark mode.
- **A built-in PDF reader:** PDFs open inside inPace in every app window (including Linux, which couldn't show them before), offline, with page buttons, zoom, fit to width and full screen. It remembers the page you stopped on.
- **Fixed:** "No answers included" no longer shows on courses that have no quizzes.

## v1.9.0

- **Meet Tempo's tour:** the first time you open inPace, Tempo shows you around in about a minute, pointing at each part of the app. Watch it again any time from Settings → Show the tour again.
- **AI courses from more places:** besides a topic, the AI course maker can now start from a book (chapter by chapter, telling you what to read), a YouTube playlist (each video becomes a lesson), a course you're taking on Udemy or Coursera, a project to build, your own notes or a syllabus, or an exam.
- **An easier course builder:**
  - Start a new course with just a title, or paste a list of YouTube links or video files and get one lesson for each. A line starting with `#` starts a new module, and inPace can fetch the video titles from YouTube if you tick the box.
  - Move modules, lessons and tasks up and down, and move a lesson to another module.
  - Change tasks and quiz questions after you make them.
  - Add many videos to a module at once.
  - Write lessons with a toolbar (headings, bold, lists, code, links, videos) and a live Preview tab.
  - **Undo** any change, one step at a time.
  - **Edit as one file:** the whole course as text, checked before it's saved.
- **New guide on the website:** a step-by-step guide to everything inPace does, in English and Arabic.

## v1.8.1

- **Fixed:** the big play button now disappears while the video plays, and comes back when you pause.
- **Fixed:** keyboard keys (Space, K, J, L, F, M) keep working after you click the video.

## v1.8.0

- **A new video player:** a big play button, a bar you can drag to jump around, back and forward 10 seconds, volume, speed (0.5× to 2×), picture in picture and full screen. It works with the keyboard too: Space or K to play and pause, J and L for 10 seconds, the arrow keys for 5 seconds and volume, F for full screen, M to mute.
- **It remembers where you stopped:** open a video again and it continues from the second you left, even after closing inPace. Watch to the end and it starts from the beginning next time. Your speed is remembered too. Audio lessons continue where you stopped as well.
- **Code files in courses:** code files (Python, JavaScript, Dockerfile, YAML, SQL, notebooks and many more) show in lessons with colours and a Copy button. A project folder inside a course becomes one lesson that shows all of its files, skipping clutter like node_modules.

## v1.7.0

- **Automatic updates:** the installed app can now keep itself up to date. The first time you open it, it asks once. If you say yes, it checks once a day, downloads the new version, checks it against the release's published checksums, and installs it. Then it asks you to restart. With the Ubuntu / Debian package, your computer asks for your password to install, as with any app. You can turn this on or off any time in Settings, or press "Check now".
- **Fixed:** in Arabic, the AI course prompt and pasted course text were shown right to left, which jumbled the English. They're now always left to right.

## v1.6.0

- **Videos, audio, web pages and more in lessons:** lessons can now play videos and audio, show PDFs and pictures, and run interactive web pages (simulations, mini games) in a sealed box with no internet and no access to your data.
- **YouTube and Vimeo:** paste a link and it becomes a player. It only connects to the internet when you press play.
- **Use a folder you already have:** on My courses, choose a folder of videos you've downloaded. Each sub-folder becomes a module and each video a lesson. Nothing is copied, so even a 60 GB course adds in seconds.
- **Files stay where they are:** a course only points to its files. If they move, or the course came from someone else, inPace asks you to choose the folder where they are now, with your computer's own "choose folder" window.
- **Share with or without files:** share a course as before, or as one file that carries its videos (for small courses).
- **Voice notes as proof:** record a voice note right on a task, or add a video. Your checker can play it back.
- **Editor:** add a YouTube link, a file path or a small file to any lesson.
- Every old way to add a course still works the same: .lpack, .zip, .yaml, the AI course maker and the editor.

## v1.5.1

- **New website:** mahmoudyosrimahmoud13.github.io/inPace, in English and Arabic, with download buttons that always point to the newest version.
- **Fixed a blank app window on some Linux computers** (and the busy fans that came with it). The window now draws without the graphics card. If it still can't show the page within 20 seconds, inPace closes it and opens in Edge or Chrome as an app window instead.
- **No more leftover copies:** starting inPace closes any copy that's already running with your data, including after an update, so you always get the newest version.
- **Choose the window yourself if you ever need to:** start inPace with `INPACE_WINDOW=app` (Edge or Chrome window) or `INPACE_WINDOW=browser` (a normal tab).

## v1.5.0

- **Its own window everywhere:** inPace now opens as a real app window on Windows, Mac and Linux, not a browser tab. Downloads (progress files, backups, records) save to your Downloads folder. Closing the window closes inPace.
- **Friend codes:** your contact card is now a short code you can paste into any chat. Send it with one click on **Telegram** or **WhatsApp**. Your friend pastes it into inPace → People, and you're connected. Race invites and race updates work the same way.
- **Light or dark, your choice:** a new button in the top bar switches between light and dark mode, and inPace remembers it.
- **Full Arabic:** every message, error, notice and page title is now in Arabic, plus the learning record page and dates (like "11 نوفمبر 2026"). There's also a new Arabic sample course: أساسيات بايثون.
- **Fixed:** the Settings page showed page code in the window title.

## v1.4.0

- **Tempo, redrawn:** a detailed comic-style turtle with a plated shell, a yellow rim, the inPace logo on the shell, expressive eyes and eyebrows, little toes, and a polka-dot travelling scarf.
- **Ubuntu / Debian package:** download the `.deb`, double-click to install, and open inPace from your apps menu.
- **New logo:** a comic-style yellow tile with a bold outline, a hard shadow and a pink final milestone. Used in the app, the browser tab and the Windows, Mac and Linux app icons.
- **Calmer dark mode:** a softer gold instead of bright yellow. Big panels go dark with gold outlines, so nothing glares.
- **Polish:** numbered lesson boxes, square timeline markers, and page titles that end with a period.

## v1.2.0

- **New look:** a bold comic-book style with thick outlines, hard shadows, sunny yellow panels and a cream header. Inspired by Basha Media.
- **Your course is a trail:** each lesson is a stepping stone on a map, and Tempo stands where you are.
- **New font:** Readex Pro, made for both Arabic and English, so both languages look their best.
- **Big footer** with the inPace wordmark and Tempo.

## v1.1.0

- **Meet Tempo:** a friendly turtle who cheers you on. Slow and steady wins the race. Tempo greets you with a message that fits where you are: starting out, close to finishing a module, on a streak, on a break, or done with the course.
- **Celebrations:** finishing a module, passing a quiz, saving a milestone or getting approved now shows a small celebration with confetti.
- **Code highlighting:** code in lessons is now colour-coded, shows its language, and has a Copy button. Works offline.
- **Kinder results:** missed a quiz? Tempo reminds you that every mistake now is one you won't make later.

## v1.0.0

**Keep going**
- **Weekly goal:** choose how many milestones a week you'll save. Home shows this week's count and how many weeks in a row you've kept it.
- **Breaks:** take a planned break. Weeks on a break don't count as missed, and your streak survives.
- **Finish date:** see roughly when you'll finish at your current pace.
- **Quick reflection:** three short questions after studying. Your checker sees them.
- **Daily review:** questions you've answered come back over days and weeks, so you remember them.
- **Backups:** one file with everything, locked with a password. Restore it on any computer.

**Fun and sharing**
- **Pace races:** race friends by weeks on pace or by course progress. Only approved milestones count. Includes a race track, badges, cheers, and an automatic shared-folder option.
- **Learning record:** a single web page you can share. Anyone can open it and click "Verify" to check it, offline.
- **Course editor:** make and change courses with simple forms, no code.

**Reach**
- **Arabic interface (beta):** switch the language in Settings. The whole layout flips right-to-left.
- **People by course:** checkers with several learners see them grouped by course.
- **AI inside the app (optional):** connect Ollama on your computer, or a Claude or OpenAI key, and inPace makes the course for you.
- **Git projects as proof:** add a project's commit history as your work.
- **Community course library:** free courses shared by learners, in the `community-courses` folder.

## v0.2.0

- New design with real fonts, proper dark mode and phone layout.
- Opens in its own window. One-click apps for Windows, Mac and Linux.
- Verified exams from your checker, with private and surprise questions.
- Checkers can ask for any work file and inPace confirms it's the original.
- Warnings for nearly identical answers and for different course copies.

## v0.1.0

- First release: courses, lessons, tasks, practice quizzes, milestones, and checker approvals.
