# Changelog

## v1.25.0

- **Optional lessons.** A course can now mark a lesson as an extra (further reading, a long video, a bonus exercise) that the module doesn't wait for.
  - On the lesson, an **Optional** label and a **Skip it** button sit at the top, before the text. **Done, next lesson** still works if you read it.
  - The module finishes without its optional lessons, and they don't count in the lessons total or the percent. Reading one still shows it as done.
  - **Continue** shows each optional lesson once, in its place. Once you've opened it and moved on, Continue goes to the next lesson you need.
  - The trail draws optional lessons as dashed stones, the module page lists them apart, and the lesson dots and the course outline mark them.
  - Every way to make a course has it: an **Optional lesson** tick box in the lesson editor, in **Add a lesson** and in the drag-and-drop builder, and `optional: true` in the course file and **Edit as one file**. A module needs at least one lesson that isn't optional.
  - **Make a course with AI** now tells the AI to put only extras in optional lessons.
  - The course library marks optional lessons in each course's outline. Older versions of inPace treat them as normal lessons.
- **Notes on lessons.** Select a sentence in a lesson and a **Take a note** button appears next to it. Press it, write your thought (or nothing), and save: the page stays where you are.
  - Sentences you took notes on are highlighted in the lesson, and **Show in the lesson** takes you back to one.
  - Each lesson ends with **Your notes**: edit or delete them there, or write a note without selecting anything.
  - **Your notes** on the course page lists all of them in the course's order, and **Download as a file (.md)** saves them to keep or print.
  - Notes are private: they stay on this device and in your backups, and are never sent with milestones or shared courses.
- **A better PDF reader.**
  - A zoom list: fit to width, fit to page, or 50% to 400%, with the zoom shown as you change it.
  - Zoom with **Ctrl + mouse wheel** or a touchpad pinch (around the pointer), with **two fingers** on a phone, or with **+**, **−** and **0** on the keyboard. Zooming keeps the spot you were reading in place, and pages no longer go blank while they're drawn sharp again.
  - **Rotate** for scanned pages that are sideways, and **night mode** for dark pages at night.
  - Page buttons gray out on the first and last page, **Home** and **End** jump there, and "fit" zooms fit again when the window changes size.
  - Each PDF remembers its zoom and rotation; night mode is remembered for all of them.
  - Long books at a big zoom use much less memory: only the pages near the screen keep a drawn picture.
- **Pictures and charts open big.** Click a picture in a lesson, or the small button in its corner: it fills the screen. Zoom with the buttons, the mouse wheel, **+** and **−**, or two fingers; drag to look around; double-click or double-tap to zoom in or fit again; rotate; **←** and **→** go to the lesson's other pictures; **Escape** closes it.
- **Settings has a gear icon** now, instead of one that looked like the sun (and like the light and dark switch).
- New Arabic translations for everything above.

## v1.24.0

- **Roadmaps: several courses in order, toward one goal.** "Become a data analyst", "Maths for machine learning", "English from A1 to B1": a roadmap says which courses to take, in what order, and why each one comes where it does.
  - **Roadmaps** is a new place in the sidebar (and under More on phones). It shows the roadmaps you're on, how far you are in each, and the next course.
  - Each roadmap's page is the path itself: every course with its picture, your note, how long it is and your progress, and one button for what's next (**Continue**, **Start** or **Add the course**).
  - **Home** shows the roadmaps you're on under your courses, and every course card and course page says when a course is step 2 of a roadmap.
- **Make your own roadmap from the courses there are.** Type a goal and press **Suggest courses**: inPace picks the matching courses from your courses and the library, keeps one language, keeps a series together, and puts the basics first and the advanced courses last. Then move courses up and down, add a note to each, mark some optional, and save. You can also make your own version of any library roadmap.
- **Roadmaps in the library.** The course library has a new **Roadmaps** tab with 10 roadmaps to start with. **Follow this roadmap** saves it; you add each course when you get to it, so nothing big downloads up front. A library course's page says which roadmaps it's on.
- **Share and publish roadmaps.** A library roadmap goes as a short link. One you made goes as a link that holds the whole roadmap (it's only the course list and your notes), or as a file. **Publish it to the library** opens the form on GitHub with your roadmap already filled in, and a bot checks that all its courses are in the library.
- **Voyages, a new mode on Tempo's island.** Every roadmap you follow is a voyage: each course is a port with a lighthouse, and the end is a harbour with a chest. Tempo's boat sails to the next port as you go.
  - Finish a course on a roadmap and its lighthouse lights up: **10 shells**. Finish the whole roadmap and the harbour's chest is yours: **100 shells**.
  - **A new friend, Nawras the seagull,** flies to the island when you finish your first course on a roadmap.
  - The island page has two views now, **The island** and **Voyages**, and every roadmap's page shows its voyage.
- **The website and the library site show roadmaps** as a new-in-1.24 feature: roadmap cards and pages, how many roadmaps there are, and a note that following one needs inPace 1.24 or newer. Older versions of inPace ignore roadmaps and keep working as before.
- In Arabic, roadmaps are called مسارات التعلّم, and every new page is translated.

## v1.23.0

- **Faster pages, most of all on phones.**
  - The window now keeps inPace's own files (styles, script, fonts, icons) instead of asking Python for them again on every page. Before, each page change, and each Back, meant about seven requests to Python; now it's one.
  - **My courses** opened slowly because the sample courses were read from disk on every visit. They're read once now (on a computer the page went from about 80 ms to about 5 ms; on a phone the difference is much bigger).
- **The phone app starts faster from the second start on.** After the app is up, it quietly copies its pure-Python libraries out of the app's zip into your inPace folder and compiles them there; later starts use that copy instead of compiling every library again. Python also keeps compiled copies of inPace's own code. It's all plain Python in `main.py` (the app's packaging is unchanged from 1.22.2), and it's safe to lose: after an update a new copy is made, and if the copy ever can't be used it's thrown away and the app starts the old way. **Settings → Where your data lives → Show details** shows how long the last start took.
- **It moves like an app, on phones and computers.**
  - **Tabs:** going between the main places (Home, My courses, Add, Milestones, the island, Races, the library, People, Reminders, Settings) swaps the page instead of stacking it. Tapping the place you're on scrolls to the top and brings its numbers up to date.
  - **Back** closes what's open first (the More sheet, a menu, full screen). On a main place it goes Home; on Home the phone's Back leaves the app. Everywhere else it goes one page back, or up to the page it belongs to. The phone's Back button, the button at the top left and Alt+← all work the same way.
  - **Direction:** opening something slides it in from the side, Back slides it back the other way, and tabs and saved forms fade (mirrored in Arabic; off when your system asks for less motion).
  - A thin bar shows at the top when a page takes more than a moment.
  - Buttons, tabs and menus no longer act like web page text: a long press or right click doesn't select them or open a "copy link" menu, links and pictures don't drag out, and the page doesn't stretch when you scroll past its end. Lessons, code and anything you type still select and copy as before.
- **Pages update in place.** When you come back to inPace after a while, Home and the course page ask Python for the page again and change only the parts that are different (a progress bar, the next lesson, the path), like a Flutter screen rebuilding only the widgets whose data changed. Nothing blinks, you stay where you were on the page, and open sections stay open.

## v1.22.2

- **Fixed for real: the phone app starts again.** 1.21 to 1.22.1 packed the app's Python code in compiled-only form to start faster, and on phones Python couldn't start with it. The phone app is now packed exactly like 1.20, which works. It starts about a second slower than 1.21 was meant to, and it starts.
- **If the phone app can't start, it now says why.** Python writes the reason to a file in the app's folder, and the "inPace could not start" screen shows it (and it scrolls), instead of only "took too long". It also waits up to two minutes, because a phone right after an update can be slow.

## v1.22.1

- **Fixed: the phone app didn't start in 1.21 and 1.22** ("inPace could not start: inPace took too long to start"). The faster build ships Python's code already compiled and removed the plain `main.py` file, but the app still asked to start `main.py`, so Python never started. The app now starts whichever file is there, and the build keeps the plain files too. Your courses and progress were never touched: update and it opens as before.

## v1.22.0

- **A download button under every YouTube video.** Each lesson with a YouTube video now has **Download this video** right under it, with roughly how big it is (once inPace knows the video's length). Press it and the video downloads in the background while you keep learning. The button shows how far along it is, says **Saved on this device** when it's done, and **Play the saved copy** switches the lesson to the copy, which then plays without internet. Lessons with a YouTube playlist get **Download these videos**.
  - Pressing several lessons' buttons, or downloading the whole course while one video downloads, adds to the same download instead of starting over.
  - If a video doesn't download, the reason is right under it in plain words (no internet, or YouTube says the video isn't available), with **Try again**.
  - Each video gets the same space check as the whole course, and uses the quality you chose for that course.
- **A small "Download for offline" button at the top of the course page,** right under **Continue**. One tap downloads all the course's videos in the quality you used before for that course (720p unless you chose another), and shows the size. While it runs, it turns into **Downloading videos 3 / 10**; when everything is saved, it says **Videos saved for offline**. The full **Watch offline** box stays at the bottom of the page, with quality, folder and your own videos; **Options** next to the button opens it.

## v1.21.0

- **Optional tasks.** A course maker can mark a module's upload or write-up as optional: the module opens the next one without it, while the quiz (or any task not marked optional) is still needed. Optional tasks say **Optional**, come after the required ones under their own heading, can still be done, and don't count against your progress. In the editor, tick **Optional** on any task. It works both ways with older versions: courses without it are exactly the same as before, and an older inPace simply treats an optional task as required. The four Maths for ML courses use it: the quiz finishes each module.
- **Easier to find your way.**
  - **Home** puts **Continue** first: the course you worked on last is at the top, its next lesson right under its name, and the numbers below. Other courses fold their details away under **Details and options**, so the page stays short. The reminder tip moved below your courses.
  - **The course page** shows your learning path right away. The module you're on is open; finished and locked modules fold into one line each (tap to see their lessons). **Watch offline** moved below the path and folds into one line that shows how many videos you have; it opens by itself while videos download.
  - **Lessons** start right under their title; the full course outline moved below the lesson.
  - **New here?** Home and My courses now lead to the free course library first, then to making your own, then to the samples.
  - **Settings** has links at the top to jump to each part (your turtle, colors, reminders, videos, AI, backups, updates, your data).
  - On phones, the **Add** button next to a sample course no longer squeezes into one letter per line.
- **Smoother, still fast.** Going to another page fades through instead of blinking (the top bar, the menu and the phone's tab bar stay still), sections like "Show details" slide open, and cards give a little when you press them. Only fading and moving are animated, so phones stay smooth, and it's all off if your system is set to reduce motion. Older browsers just work as before.
- **The phone app starts much faster.**
  - Python's code now ships already compiled. Before, the phone compiled every library again on every start, because Python can't save compiled copies inside the app's zip files (about 1 to 2 seconds on a mid-range phone).
  - Pages are drawn from templates that are compiled once and kept in your inPace folder, so the first page after a start is ready almost at once (it took about 0.1 s on a computer and much longer on a phone).
  - The lesson renderer loads only when a lesson needs it, the page view starts while Python starts, the app checks whether Python is ready every 50 ms instead of every 300 ms, and notifications get ready in the background instead of before the first screen.
  - **Settings → Where your data lives → Show details** shows how long the last start took on your phone.
- **A splash screen with Tempo.** The phone app opens on Tempo waving above the inPace logo, on yellow, with a spinner while it gets ready, then fades into your first page with no white flash. Android 12 and newer show Tempo in a circle with the logo below.

## v1.20.0

- **Courses that read a book you get yourself.** Some great books are free to read but not to share. A course can now be built on such a book without carrying it: each lesson opens the right pages of *your own copy*. The course page has a box, **This course reads a book you get yourself**, with a link to get the book and three ways to show inPace where it is:
  - **Find it for me** looks in your Downloads, Documents and Desktop folders (on a phone: Download, Documents and Books), a couple of folders deep.
  - **Choose folder** searches a folder you pick, or type the path of the file itself.
  - The file can have **any name**: inPace recognizes the book by the title saved inside the PDF and by its number of pages. If the page count is different, it warns you that it may be another edition (so lessons could open the wrong pages), and you can keep it or get the right one.
  - A lesson that needs the book before you've shown inPace where it is says so, with the pages it will open and a button that takes you to the box.
  - inPace remembers your copy for that course. Sharing the course never includes the book.
- **For course makers:** add `book_info` (title, link and number of pages) next to `book:` in `course.yaml`. See SPEC.md.
- **Four new courses in the library: Maths for Machine Learning 1 to 4,** on the free book *Mathematics for Machine Learning* (Deisenroth, Faisal, Ong): linear algebra and geometry, matrix decompositions and vector calculus, probability and optimization, and regression, PCA, Gaussian mixtures and SVMs. They use the new book box, and add notes, 3Blue1Brown videos, interactive explorers, exercises with instant feedback and charts.
- **The website shows how many courses the library has,** next to the download button and in the menu. It reads the number from the library itself, so it goes up by itself when a course is added.

## v1.19.1

- **Tests that pass on every machine.** The new offline-video tests no longer depend on the computer they run on: they don't use the real disk space, wait longer for background downloads on slow machines, build the stand-in downloader the way real zip apps are built, and clean up after themselves so they can run in any order.
- **The guide, the website and How it works** now explain watching YouTube lessons offline: downloading in the quality you choose, where the videos are saved, matching videos you already have, the space check, and that sharing and backups never carry the videos.

## v1.19.0

- **Watch YouTube lessons offline.** A course with YouTube videos now has a **Watch offline** box on its page.
  - **Saved where you can find them.** Videos go to your **Downloads** folder, in **inPace/<course name>** (on Android: the phone's Download/inPace folder), so you can open them in any player or move them. In **Settings → Video downloads** choose Downloads (the default), your Videos folder, inPace's own folder, or any folder. Each course can also have its own folder and its own folder name (the course name by default), right from **Saving to** on the course page. If the phone or computer doesn't allow a folder, the videos are kept in inPace's folder and the course page says so.
  - **Choose the video quality** next to the download button: 360p, 480p, 720p, 1080p or **Best available** (the sharpest quality that plays everywhere, usually 1080p). Each course remembers its choice, and the box shows roughly how much space an hour of video takes in each quality.
  - **Download the videos** saves them on this computer, in the background, with a progress bar. You can keep learning while it runs, stop it any time, and **Download the rest** later picks up where it stopped. Playlists work too.
  - **I already have these videos:** choose the folder they're in and inPace works out which file is which video, even when the names are different: other numbering, quality tags like (720p), underscores, small typos, Arabic spelled two ways, or the lesson's name on its folder instead of the file. It also uses the YouTube id when the file name has it, and the video's length. You see every match, marked Sure or Please check, and can change any of them before saving. Nothing is moved or copied.
  - Lessons then play the copy on this computer, with inPace's own player: still only their own part of a long video (it stops at the end of the part), and from the second you stopped at, the same place as on YouTube. **Watch on YouTube instead** is one tap away, and if a file is deleted the lesson simply goes back to YouTube.
  - **Play from YouTube again** forgets the files without touching them. **Delete downloaded videos** frees the space (only the files inPace downloaded itself; videos you already had are never touched).
- **Space checked first.** The quality list shows roughly how much space the videos still need in each quality, next to the free space where they're saved. If it won't fit, the course page warns you and the download doesn't start (unless you tick **Download anyway**). If the disk fills up during a download anyway, inPace stops, keeps the videos that finished, removes the half-downloaded piece, and tells you.
- **Videos and big files never travel when you share.** Sharing a course "with its small files" now carries only PDFs, slides, pictures and code under 25 MB; videos, audio and big files stay on your computer, and the other person gets them from YouTube, the course's download links or their own folder. Downloaded YouTube videos are never part of a shared course. Backups leave out downloaded videos, the downloader, and files over 50 MB, so they stay small.
- **yt-dlp, kept up to date.** Downloads use yt-dlp, the free open-source downloader. inPace gets it from its official GitHub releases the first time (about 3 MB), checks it against the published checksums, and keeps it in your inPace folder. In **Settings → Video downloads**, choose **Automatically, once a day** (the default, because YouTube changes often and an old yt-dlp stops working) or **Only when I press Update now**, and the quality for new downloads. It works on Android too.

## v1.18.0

- **Build a course on one page.** New **Build it myself** (on Add a course, and **Edit** on every course): parts and lessons on one page. Add a YouTube or web link, files from your device (or drag them in), or a text lesson with one button; drag lessons and parts to reorder them (or use the arrows on a phone); write notes under any video. It saves by itself as you go, keeps everyone's progress and your tasks and quizzes, and the old step-by-step forms and text mode are still there.
- **A course from links, made easy.** New **Links: YouTube, Udemy or any website** on Add a course. Paste your links one per line. Under a long YouTube video, paste its chapter times (from the video's description) and each chapter becomes its own lesson. Udemy and other sites open on their own site, and you still tick them off in inPace.
- **YouTube remembers where you stopped.** A YouTube lesson can be one piece of a long video (it starts and stops at that piece), and it continues from the second you stopped at. Playlist links work too. The play box shows its dark background again (it was white, so its text was hard to read).
- **Folders on My courses.** Make folders like "Programming languages" or "Networks", move courses into them from a course's **More** menu (or pick one when you add a course), rename or delete them. Deleting a folder keeps its courses.
- **The course library works on Android.** Python inside the phone app had no list of trusted certificates, so every secure download failed and the library looked offline. inPace now ships the standard list (certifi) and uses it on phones, and anywhere the system's own check fails. Updates and YouTube titles were fixed by the same change.
- **Course pictures show whole.** The picture at the top of a course and on My courses was cut into a thin strip; now it keeps its shape, next to the course title.

## v1.17.1

- **A better course library.** The library is now a grid of big course covers, with the hours of lessons, modules and language on each card. Buttons for the most common topics (python, machine learning, flutter...) narrow the list in one tap, next to the search box.
- **Look inside a course before adding it.** **See what's inside** opens a page with every module and lesson, how long each takes, which lessons have slides or video, the tasks at the end of each module (a practical task, an answer in your own words, a quiz and how many questions), and one lesson you can read in full. Add the course from there when you're ready. The library website has the same page for every course.

## v1.17.0

- **One island for everything, with your name on it.** All focus trips grow on Tempo's island, whatever you're studying. The separate turtle and island for each course are gone, so there's one place to look after. Tap **Rename** above the island to name it. A flag with the name can stand on it too.
- **Your courses pay off.** Lessons, modules and finished courses give shells. Each course also hides treasure chests at 25%, 50% and 75% (10, 20 and 30 shells), and a finished course puts a golden trophy on your island. The island page lists every course with its chests and what it gave you, and Home shows the next chest under each course. A course counts once: starting it again, removing and adding it back, or having the same course installed twice never pays twice, and chests stay open even if a course later gets longer.
- **Share your island.** If the island is on, your contact card, progress files and reviews carry a small copy of it (what's drawn and a few numbers, nothing else). The people you add see **See their island** on the People page, and their islands appear on yours, each carried by their own turtle. **Share my island** makes a square picture of it to send anywhere. You can keep it private in Island settings.
- **The villain is real now.** The Fog of Someday (بكرة in the Arabic world) gets a face, and it comes closer the longer you stay away: far on the horizon after 2 days, closer after 4, at your shore after 7, and on your island after 10, arms around your plants. It talks to you, Tempo answers, and a danger meter shows how close it is.
  - After 10 days away your plants start to wilt, one more every 2 days. A wilting plant dies 14 days later. Every focus trip you finish waters two of them, and your animal friends (who flee into the fog) come back after your next trip.
  - Dead plants stay grey on the island until you clear them. They still count for everything you unlocked.
  - Two new story beats: **The Fog Has a Face** and **What the Fog Took**.
  - Hard week? Turn on **Gentle sea** in Island settings: the fog still comes, but it never takes your plants.
- **Shells and a shop.** Everything you learn earns shells (focus minutes, lessons, reviews, modules, milestones, approvals, finished courses). Spend them per island on ground (beach, blossom, autumn, desert, snow), skies (balloons and lanterns, starry nights, northern lights), seas (turquoise, lagoon, deep ocean) and things to put on it: a flag, rocks, a bench, a campfire, lanterns, a well, a hut, a windmill and a lighthouse in the sea. Up to 4 things on each island.
- **A sky that follows your real clock.** Dawn, morning, day, sunset, dusk and night, with the sun and moon moving across the sky, and sunrise and sunset moving with the seasons. The same sky is behind Tempo on the focus trip. At night the lanterns, campfire, hut and lighthouse glow.
- **More life on the island:** snow in winter, petals in spring and falling leaves in autumn; a daily visitor in the sea (a dolphin, a whale, gulls, a jellyfish or a little boat) on days you study; clouds and balloons drift, the aurora breathes, and a star falls now and then. Motion stops if your system asks for less motion.
- **Tempo in your notifications.** Notifications now show Tempo's face (happy, sad, proud, reading...) on Android, Windows and Linux. New island notifications: your focus trip is done (at the exact minute), the villain reached your shore, your plants are wilting, and a plant dies tomorrow. Turn them off under Reminders, like the others.
- **Your focus trip in a notification.** On Android, a running trip shows Tempo and a live countdown in the notifications. Android keeps it counting while you use other apps, and even if inPace is closed. When the time is up it goes away and "Your plant is ready!" rings at that exact second. In "Phone down" mode, leaving the trip screen pauses it and the notification says your sprout is waiting. On a computer, inPace says "Your plant is ready!" the minute the trip ends while the app is open, even minimized, and the window title shows the countdown.
- **Make your own turtle.** On the first page (and in Settings) you make a turtle instead of picking a colour: shell, scarf, skin and something to wear (a cap, a beanie, a bow, glasses, headphones, a flower, a graduation cap, or a crown or wizard hat from the island shop). Your turtle replaces the coloured letter everywhere, travels on your contact card so the people you add see it, and sails in its own colours on their sea chart. **Save a picture of my turtle** makes a square picture to share anywhere.
- **Diagrams in lessons.** Write a diagram as text in a code block marked `mermaid` (flowcharts, sequence diagrams, timelines, mind maps and more) and inPace draws it, in light or dark mode, with Arabic or English labels. It works offline. Each diagram has zoom out, zoom in, Fit and Full screen; drag to move around a zoomed diagram, pinch with two fingers on a phone, or hold Ctrl and use the mouse wheel. Escape closes full screen. The tour course has one, and courses made with AI can use them too.
- **Changes show right away.** Picking a new colour profile, buying or using something in the island shop, and other buttons that bring you back to the same page now update the screen at once, with their message. Before, the page only scrolled and you had to reload it by hand.
- **Arabic and English mixed in one lesson read right.** Each paragraph, heading, list item, quote and table cell now goes the way its own words go, so an English line in an Arabic course is left to right, an Arabic line that starts with an English word is still right to left, and bullets and punctuation land on the correct side. Code is always left to right. Same in the Arabic and English versions of the app.
- **Phones keep the right time.** The Android app tells inPace your real time zone, so mornings, nights and reminders match the clock on your phone.

## v1.16.0

- **Tempo's island (reward mode).** Optional, off until you turn it on. Tempo carries a little island on his shell:
  - **Focus trips:** pick a plant and 10 to 90 minutes. While you study, Tempo swims and the plant grows on his back; when the time is up, it joins the island. Bigger trips grow bigger plants, and an hour or more grows fruit or flowers. "Study anywhere" or "Phone down" (time only counts while the screen is open).
  - **Nothing dies.** Rest any time: the sprout keeps its minutes for next time.
  - **14 plants and 8 animal friends,** each drawn by hand in the app's style. Friends come from learning: Zoon the snail (first lesson), Kiko the sparrow, Fofo the frog (reviews), Zizi the bee (milestones), Boomy the owl (a checker's approval), Farfoura the butterfly, Arnoob the hare (races) and Kaboria the crab (a finished course).
  - **A turtle for every course,** with its own colors, name and island. Your friends' turtles sail the same sea.
  - **An adventure in 10 chapters,** against the Fog of Someday, toward the Far Shore. Two worlds: the Sea of Things to Learn, or Alexandria and the Great Green Sea (Teta Lulua, the Pharos, the Library of Alexandria), in English or Arabic.
  - **Your pace is the weather:** mist after 2 days away, thick fog after 4 (friends sleep, the story waits), and the fog lifts when you come back. Keep a weekly goal for fair winds; a checker's approval makes the island bloom for a week.
- **A new Tempo.** Redrawn from scratch: a real neck, a big friendly head, round legs, a scalloped rim, a scarf that blows behind him, and new moods (reading, watering, sad, in love).
- **Back makes sense everywhere.** Pages are never kept in the cache, so going back after changing the language or colors shows the new ones. Quiz results are their own page, so Back or reload never shows or resends your old answers. One-off pages (a sent quiz, a finished trip) are skipped by Back. Settings, quizzes and uploads replace the page instead of piling up.

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
