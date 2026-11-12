# Changelog

## v1.15.2

- **Fixed on phones: the "⋯" menu of the last courses went under the tab bar,** so items like Delete couldn't be reached. On phones the menu now opens as a panel just above the tab bar, scrolls if it's long, and closes when you tap outside it. Only one menu is open at a time, and Escape closes it on a computer.

## v1.15.1

- **Fixed: the tests failed on Python 3.10** (and the app wouldn't start on it) because of one line in the Office preview code that only newer Python understands. A new test now checks every file for this.
- **Next module, one tap.** When you finish a module, its page says what's next and has **Start the next module**. No more going back to My courses and opening the course again.
- **Back makes sense inside a course.** Next lesson, Previous, module tasks and the next module replace the page instead of piling up, so Back takes you to the course page and then My courses, not back through every lesson. Same on computers and phones.
- **A Continue button on the course page,** to the next lesson or the module tasks.
- **My courses is simpler:** one card per course with its picture, name, a progress bar and the next lesson. Tap the card to continue; Edit, share and delete are under **⋯**. The search box shows from 4 courses, and sample courses are folded away at the bottom.
- **Phones:** the course trail fits the screen. Lesson names no longer run off the side, which also pushed the tab bar out of place.


## v1.15.0

- **Turn a book into a course.** Add a course, then **A book (PDF)**. inPace reads the chapters and sections from the book's bookmarks: each chapter becomes a part of the course and each section a lesson that opens **only its own pages**. Long chapters are split into shorter lessons, the cover and contents start in "Left out", and a book with no bookmarks is split every 12 pages. You can rename, move and leave out parts before you add it.
- **Parts of a PDF in any lesson.** A lesson can show pages 5 to 7 of a PDF instead of the whole file (`media: book.pdf#pages=5-7`). The reader remembers your page in each part.
- **Word, PowerPoint and Excel files open inside lessons** (.docx, .pptx, .xlsx): a light, read-only preview with headings, lists, tables, pictures, slides in order and each sheet as a table, plus a button to open the file in its own app. It all runs inside inPace, with nothing sent anywhere. Old formats (.doc, .ppt, .xls) still need saving as the new ones or as PDF.
- **AI courses from your own book or files.** On the AI page, attach a book or some files. They become part of the course, and the prompt now tells the AI each file, the book's pages and its chapters, so the AI makes lessons that open the right pages.
- **A tour of inPace:** a new sample course with one of everything: video, audio, pictures, code, an interactive page, part of a book, slides, a Word file, a spreadsheet, tasks and a quiz.
- **Updates:** fixed a problem where a computer could see a new version before its download was ready, count it as a failed update and wait a whole day. Now it says the update is on its way and checks again in an hour.
- **Android builds are sturdier:** the build tries once more after a hiccup, has more time, and adds the APK to the release only after the release is ready. Reading PDFs uses pypdf, which is pure Python, so it works on phones too.

## v1.14.0

- **Reminders and alarms.** Pick a time and the days you study (or Every day, Weekdays, Weekends). Each reminder is a notification or an **alarm that rings until you stop it or snooze it for 10 minutes**. They tell you the next lesson, and tapping one opens inPace right there.
- **They work while inPace is closed,** on Windows (Task Scheduler), Mac (launchd), Linux (systemd or cron) and Android (Android's own notifications, also on the lock screen).
- **Tempo's notifications**, each one can be turned off: Tempo misses you after 7 days away (you choose 1 to 14), your weekly goal is at risk, questions are ready for review, and a finished module needs a milestone. They come in the evening, at most one of each kind a day.
- **Welcome back:** after 3 days or more away, Tempo says so on Home.
- **Try it:** send a test notification or ring a test alarm from the Reminders page.
- Fixed: the Add a course page named a button that's really called "Edit as one file".

## v1.13.2

- Fixed: copying a course's files into inPace could say "done" a moment before it had finished. (A test on Mac caught this and stopped v1.13.1.)
- Android: fixed the build that sometimes failed while downloading Python ("Unable to determine the current character"). The downloads for each kind of phone wrote the same file at the same time; now they run one after another.
- The computer's sidebar now matches the phone: the same icons at the same size, and the page you're on is highlighted in yellow. The course library has its own icon (it used to share one with People).
- On Android, this is the first version with everything from v1.13.0: the easy **Add a course** page, sorting messy folders, and the tab bar at the bottom.

## v1.13.1

- Not released: a test failed on Mac. Everything it had is in v1.13.2.

## v1.13.0

- **Add a course, the easy way.** One **Add a course** page with every way in: a folder, some files, a course file, the library, AI, or simple forms. Writing YAML and Markdown yourself is still there, under Advanced.
- **Messy folders get sorted for you.** inPace groups files by the week, lecture or chapter numbers in their names (English and Arabic), or by kind (videos, slides, notes), and keeps a neat folder's sub-folders as sections.
- **The organizer:** rename sections and lessons, drag files between sections (or "Move to" and arrows on a phone), add and remove sections, and leave files out. Word and PowerPoint files are listed with a tip to save them as PDF.
- **Ask AI to sort it:** directly with an AI key, or copy and paste with any AI chat. The AI only sees file names.
- **You choose where files live:** leave them where they are (the default, no extra space) or copy them into inPace, with the size and free space shown first. Copying runs in the background with a progress bar.
- **Phones:** a tab bar at the bottom (Home, Courses, Add, Milestones, More) that always shows where you are, the page name in the top bar, less crowded pages, and bigger buttons and fields.
- Fixed: the Settings page was wider than a phone screen.

## v1.12.3

- Restoring a backup no longer closes inPace (on the computer or the phone). It restores and takes you to the home page.
- Android: the "Quit inPace" button is hidden on phones (close the app like any other).
- Android: a new app icon (made with IconKitchen) that fits round and rounded-square icons, plus a themed icon for Android 13+. The desktop app and website keep their icon.
- Release pages list the Android download next to Windows, Mac and Linux.

## v1.12.2

- **inPace for Android** (in `mobile/`, built with Flutter): the full app on your phone, with downloads you can send or save, Android's file and folder pickers, voice notes, full-screen videos, the share sheet, inPace links, and the back button. Download `inPace-android-arm64-v8a.apk` from this release or the website (Android 7 or newer).
- The app's top bar now fits phone screens.

## v1.12.0

- **Course library:** a new **Course library** page in the sidebar. Browse free courses other learners shared, search them, and add one with a click. inPace checks each course against the library's list before installing it, and offers newer versions through the normal update flow.
- **Publish your own course:** **More → Publish to the library…** makes a course file signed with your inPace key and opens the library's submission form with your details filled in. A bot checks it and opens a pull request. Only your key can publish updates to your course.
- **Send a course as a link:** **More → Send a link…**. A course from the library goes as a short link, and your friend lands on it in their Course library. Courses that aren't in the library can still be sent as files.
- **Download links for big courses:** add where to download a course's videos (Google Drive, Dropbox, MEGA, archive.org…) in **Edit → Course details**. Learners see **Get this course's videos**, download them, and choose the folder. Big videos stay out of the library file automatically.
- **Website:** the home page now shows the latest version, its release notes, how many times inPace was downloaded, and a visit counter (GoatCounter, no cookies).
- The library lives at [https://github.com/mahmoudyosrimahmoud13/inpace-library](https://github.com/mahmoudyosrimahmoud13/inpace-library). The built-in Python and FastAPI courses are its first courses.

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
