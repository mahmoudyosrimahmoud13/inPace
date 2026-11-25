# Changelog

## v1.36.0

- **The sprint strip.** While a sprint runs, a strip at the top of every page counts down today's sprint window: pick when each day starts and ends (12:00 to 00:00 is a 12-hour window) and it shows the hours, minutes and seconds left. It follows the clock, so nothing pauses it, it's back after you restart inPace, and it goes away only when you stop the sprint. Your focus timer is separate and works as before.
- **Its look.** A black band with the time in a yellow block, a mark for every hour along the track, and Tempo walking it as the day goes by. In the last half hour the time pulses; when the window closes the strip turns grey, Tempo sleeps, and it counts down to the next day's window. Tap it to open the sprint.
- **Set the window.** "Each day starts at ... and ends at ..." when you start or make a sprint, and "Each day ends at" in Change the plan for a sprint that's already running. Without an end time, the window is as long as your hours a day.

## v1.35.0

- **The person who checks on you follows your sprints.** Every progress file you send now carries the sprints its course is part of, signed with your key: the plan, what you ticked and when, which courses are finished in inPace (proven) and which are only ticked, what's late, and the focus time of each day. Nothing new to send or remember.
- **Short for the checker.** On the review page each sprint is one line, "ML sprint · day 3 of 7 · 45% of the plan ticked · 1 late", and opens to the day strip, a small table of the courses, and when the ticks were made. A sprint changed after the learner made it is flagged "Not signed by them".

## v1.34.1

- **Removing an account on Windows deletes its folder.** Windows can't delete a file that's still open, so removing someone right after they used inPace could leave their folder behind. inPace now tries for a few seconds, and if a file is still in use, it moves the folder aside so the account is gone at once, then finishes deleting it the next time host mode starts or you make an account.

## v1.34.0

### Host mode: share inPace with people on your network

- **Settings → Sharing → Host mode.** Off unless you turn it on (computers only, not phones). Turning it on shows what it means first: anyone on the network can reach the sign-in page (so never on café, airport or hotel Wi-Fi), the computer has to stay on, everyone's progress is kept on it, videos are sent from it, and it isn't ready for the internet. You tick two boxes, pick a port (8780) and it starts. A bar on every page says it's on, with the address people use.
- **An account for each person.** You make the accounts (name, username, password: 8 characters or more, a different one for each person). Passwords are kept as scrypt hashes, never as they are. Change a password or remove an account (and its progress) any time.
- **Each person gets their own inPace.** People sign in from any browser on the network (phones too) at `http://<your computer>:8780`, and get their own inPace: their own courses, progress, keys and settings, kept apart from yours and from each other's. Each runs as its own program that only this computer can reach, started when they sign in and stopped after 30 minutes without a page, or when you quit inPace.
- **Give your courses.** Give a course to one person or to everyone. Its videos and files are linked, not copied, when your disk allows it, so a big course takes no extra space, and a course that plays videos from a folder on your computer plays them for them too.
- **Safe by default.** Anything that would act on your computer is off for people who sign in: opening files in your apps, Show in folder, folders on your computer, YouTube downloads, updates, alarms, the AI settings and Quit. Nothing they do pops up on your screen. Sign-in is limited to 10 tries in 10 minutes from one address, sessions end after 12 hours without a page, and the sign-in cookie can't be used by other sites.
- **Honest proof.** Milestones made in a shared inPace carry "signed by a server" inside what's signed, and a checker reviewing them sees: "Signed by a server. The person who runs it could have changed it."

## v1.33.0

### Sprints: a short, intensive run of a roadmap

- **Make a sprint.** Roadmaps → **Make a sprint** offers three ways: **make it yourself** (the roadmap maker with the days, hours and start date; save, then give each course its day and tasks), **with AI**, or **from a file**. Any roadmap you already follow can also be run as a sprint.
- **Sprints have their own place in the menu.** **Sprints** in the sidebar (and in the phone's More menu) lists your sprints, with the day, today's courses, what's late and your focus time, and the ways to make a new one.
- **A sprint day can start at any hour.** Pick **Each day starts at** when you start a sprint: start at 4 pm and every sprint day runs from 4 pm to 4 pm, so work after midnight still counts for the day you started it (the timer, the ticks, Focus today and the report all follow it). Focus time is now kept by the hour for this.
- **One timer for the whole sprint day.** **Start today's sprint** runs the focus timer in blocks with breaks between them (50 + 10, 25 + 5 or 90 + 15 minutes) until you reach the day's hours. The next block and the next break start by themselves, with a chime and a message. Breaks never count as focus. If you were away long after a break ended, the next block waits for you, paused, so time you weren't there is never counted.
- **It shows up by itself.** Open your sprint, or a lesson from one of today's courses, and the sprint timer appears on screen, ready and paused: press play to start. Leave the sprint without starting it and it goes away. Stop it, and it stays away for the rest of the day.
- **One timer at a time.** While the sprint timer is on, other timers and focus trips can't start: stop the sprint timer first (the Start a timer sheet says so). A running timer also has to be stopped before the sprint timer starts.
- **On Android, in the notification too.** The phone's notification shows "Sprint · focus block 2" or "Sprint · break" with its countdown, Pause, Go on and Stop, says "Break time" when a block ends, and schedules "Back to focus" for the end of the break, even when inPace is closed. (Needs the new Android app.)
- **Focus time is counted.** The timer now keeps a total for each day. The sprint card shows **Focus today** against your hours goal, Home shows minutes focused today, and the report for your checker lists the hours timed on each sprint day.
- **Run any roadmap as a sprint.** On a roadmap you follow, press **Run it as a sprint**, choose the days, the hours a day and the start date. Each course gets a day (or a few days): the roadmap's own days when it has them, otherwise inPace spreads the courses by how long each one is. The sprint card shows **day 3 of 7**, a strip of the days (done, late, today), **Today** with its courses and tasks, and **Still to do from earlier days**. Home shows your sprint at the top.
- **Tasks you tick.** A sprint step can have tasks, like "Projects 1 to 5" or "Push the repo". In a sprint a course counts as done when you tick all its tasks, so you can take just the parts of a course you need. Finishing the course in inPace ticks them all.
- **Your plan, your way.** **Change the plan** lets you move any course to another day and rewrite its tasks, one per line. Only your copy changes, and a library update to the roadmap keeps your sprint.
- **Honest by design, like the rest of inPace.** Every tick is logged with its time. The **sprint report for your checker** (a short Markdown file) shows each course as **proven** (finished in inPace: lessons, tasks and quizzes done) or **ticked by you**, which days you worked, and what's late, so the person who checks on you can tell the difference.
- **Share a sprint.** **Share my plan as a file** saves your sprint, with your days and tasks, as a `.roadmap.yaml` anyone can add. Your ticks stay with you.
- **Make a sprint with AI** (one of the ways to make one): type your goal, the days and hours, and what you already know. inPace writes a prompt that lists every course you can use (yours and the library's), so the AI only picks courses that exist. Paste it into any AI chat, or press **Make it for me** if you set up an AI in Settings, then paste the answer back. You see the plan before you follow it.
- **The format.** A roadmap file can have `sprint: {days: 7, hours: 12}` and, on each step, `day: 2` (or `day: 4-5`) and a `tasks:` list. Older inPace versions read these files as plain roadmaps.

### Add a roadmap from a file

- **Roadmaps → Add a roadmap file.** Choose a `.yaml` roadmap someone sent you (or paste its text), see it, then press **Follow**, the same way you add a course file. It's also on the **Add** page and on **Open a file**.

## v1.32.3

- **See what needs updating.** The Library's update button now opens an **Updates** page that checks the library right then and lists every course of yours with a newer version (old and new version, lesson count and size, with its own Update button) and every roadmap you follow that changed, with **Update everything** at the top. It also says when the library was last published, so if an update you expect isn't listed yet, you can see the library hasn't published it yet, and check again.
- **A calmer library.** The update button is now a small button next to the Courses and Roadmaps tabs, with a number when updates are waiting, instead of a large box. A course's page shows its main button right under the title, then the description; the author, licence and tags share one quiet line, the note about videos is a short line, and "Report a problem" moved to the bottom.

## v1.32.2

- **Update everything, with one button.** The Library page has an **Update everything** button: every course you added from the library that has a newer version is downloaded and updated (your progress is kept, and the version before stays for Undo, like updating one course), and every library roadmap you follow is brought up to date, in one go. It tells you how many of your courses have newer versions before you press it. Courses you haven't added aren't downloaded, and courses that didn't come from the library are never touched.
- **Roadmaps you follow from the library update themselves, all at once.** When the library changes a roadmap (a new course, a better order, a course taken out), every library roadmap you follow now changes with it the next time inPace reads the library list: on Home, on the Roadmaps and Library pages, and in the twice-daily background check. There's no "update" button to press on each one anymore. Your progress stays, because it lives in your courses, and so does the date you started following. Roadmaps you made yourself, or got in a link, are never changed, and a roadmap that leaves the library stays as you had it.

## v1.32.1

- **"Open it" on a code file or notebook opens it in your own app.** It showed the raw file as text, so a notebook was a wall of JSON. Now, on computers, it opens in VS Code when you have it, and otherwise in the app your computer uses for that file (Jupyter, your editor). **Show in folder** next to it opens the folder with the file selected, and a project folder has **Open the folder** at the top. On phones, "Open it" still shows the file as text.
- **A script from a course never runs by itself.** Files that would run when opened (.py on Windows, .command on a Mac, .bat, .sh, .desktop and the like) open in your editor instead, or only their folder is shown. This also covers "Open in your video player".

## v1.32.0

### A PDF reader like GNOME's (Evince), and highlights saved in the PDF itself

- **Highlight, underline, strike out and comment.** Select text in a PDF and a small bar appears: four highlight colors, underline, strike out, a wavy underline, a highlight with a comment, and Copy. **Add a note** puts a sticky note anywhere on a page. Click any mark to read or change its comment and color, or delete it. Ctrl+Z undoes the last mark.
- **Saved inside the PDF, the way Evince saves.** Marks are standard PDF annotations (with your name, the date and their own drawing), added to the end of the file like Evince does, so the rest of the file stays exactly as it was. The same file shows your marks in Evince, Okular, Adobe Reader or a browser, and marks you made in those readers show in inPace, where you can edit them too. **Open in your PDF app** (in the ⋯ menu, on computers) opens the same file in your usual reader. Saving a mark takes under half a second, even in a 700-page book. inPace also keeps its own copy of your marks, so a course update that replaces a PDF doesn't lose them.
- **Side panel (F9):** the book's table of contents, page thumbnails, all your highlights and notes, and bookmarks (Ctrl+D) for pages you come back to.
- **Find (Ctrl+F):** searches every page as you type, highlights the results on the page, and steps through them with Enter and Shift+Enter, with Match case and Whole words.
- **Select and copy text**, and **links inside the PDF work**: a table of contents entry or a reference jumps to its page, and web links open in your browser. **Alt+← and Alt+→** go back and forward after a jump, like a browser.
- **Page layouts:** continuous or one page at a time, two pages side by side (odd pages on the left or right), rotate left or right, and **presentation mode (F5)**: one page fills the screen, and a click, the arrows or Space turn the pages.
- **Properties** (title, author, dates, PDF version, page size, file size), **Print** (Ctrl+P, pages from and to) and **Save a copy** (Ctrl+S), with your marks.
- **Evince's keyboard shortcuts**, where they exist: F9, Ctrl+F, F3, Ctrl+L, Ctrl+D, Ctrl+I (night mode), Ctrl+P, Ctrl+S, F5, F11, W and F to fit, C and D for the layouts, Ctrl+← and Ctrl+→ to rotate. Press ? for the list.
- A lesson that shows part of a book keeps everything inside its pages: search, contents and links stay within them.
- Marks can only be written to course files, and only by inPace's own page (other websites can't send them).

### Fixes

- **The Downloads page no longer opens a black page.** Clicking a course there while its download was still running opened a page that doesn't exist, and the app window showed a black screen you couldn't leave. It now opens the course, and any page that doesn't exist takes you home.

## v1.31.3

- **No more white flashes, on every device.** Every app window (Linux, Windows, Mac and Android) has its own color under the page. It was white (cream on Android), and it showed for a moment between pages and wherever a long page wasn't drawn yet while you scrolled fast, so in dark mode the course library could turn white. Now the window starts in your page's color and follows the page whenever the look changes: the light/dark button, Settings, AMOLED black, or your device switching to dark. The loading screen opens in the same color, and on Android the status bar icons stay readable on a dark page.
- **The course library scrolls smoothly.** It has about a hundred cards with big cover pictures. Cards out of view aren't drawn until you scroll near them, and pictures are prepared off the main thread.
- **Text you couldn't read is readable again.** Some labels had a fixed dark color on a background that turns dark in dark mode, so they disappeared: the roadmap chip next to a course ("Course 1 of 2 on …"), the roadmap strip on Home, "Practical task" tags and "On these roadmaps" in the library, the Voyages tab, and with some accent colors, badges, "Problem" chips, flags and the recording button. Every colored background now comes with a text color made for it, in light, dark and AMOLED and with every accent. Checked on every page in all of them.
- Locked parts of the course map and the lesson outline look locked through their stones and color, without fading the words, so you can still read what's coming. The Telegram button is a shade deeper so its white text reads.
- Going to another page is a clean fade: the new page appears once the old one is gone, instead of the two showing on top of each other for a moment on slower computers.

## v1.31.2

- **Long buttons show their progress, and the app stays usable.** Updating inPace, adding a course or a whole roadmap, getting or updating yt-dlp, and "Make it for me" with AI used to hold the whole page until they finished, with no sign of life (on Linux part of the page could even turn white). Now they run in the background and their button fills up and says what's happening: "Downloading inPace 1.31.2 · 45% · 40 / 90 MB", "Downloading 2/5 · 45%", "Installing… your computer may ask for your password". Work with no steps to count shows moving stripes. Sending big files (a course file, videos, a backup) shows the upload the same way, and any other button that takes a moment shows a small spinner.
- **Light, dark and colors always respond.** After using the light/dark button at the top, picking the same mode in Settings did nothing the second time, because the choices on the page still showed the old mode. Now the button and every choice in Settings stay in step, change the page right away and save in the background, with no reload. The same goes for AMOLED black and the colors.
- **Parts of a page that update in place keep working.** Buttons and fields in a part of the page that was just updated (after saving something) now always respond, and your name and turtle at the top update with them.
- **No more white bar in Arabic on Linux.** The Linux window put the page's scrollbar on the left in Arabic, drawn as a wide light gutter on some systems. It now stays on the right like in English, and scrollbars are thin and only show while you scroll.
- Under the hood: one shared way to report progress (`progress.py`), page helpers that listen once for the whole page, and a page script that can safely run again.

## v1.31.1

- **"Open a file" has its own icon.** It used the same arrow as Download, so the two looked alike in the menu. It's an open folder now.

## v1.31.0

### Works with CodeNote

inPace teaches; [CodeNote](https://mahmoudyosrimahmoud13.github.io/code_note/), a free code notebook app, is the lab. They stay two separate apps.

- **Practice in CodeNote.** On a lesson with code, and on a practical task, a button on each code block (next to Copy) sends the lesson to CodeNote (with the task, for a practical task), so you can run its code and do the task there. It only shows when CodeNote is on your device (CodeNote 1.10 or newer). Installed CodeNote while inPace is open? Come back to the window and the button is there. A very long lesson goes as a .md file instead, which CodeNote opens.
- **Your CodeNote work as proof.** In CodeNote, **Export for inPace** makes a file (an .html report, an .ipynb notebook or a .codenote file). Attach it to the practical task like any other file. HTML reports can be previewed right on the task, and on your checker's review page, safely: nothing in them runs.
- **Back to inPace.** CodeNote's "Back to inPace" opens the same lesson in inPace. If the course isn't on your device, inPace opens it in the course library, or says plainly that it isn't installed.
- Old courses, milestones and progress files work as before. People on an older inPace can still read your progress; CodeNote files show as normal files for them.

## v1.30.17

- **Downloading a video the first time works, and says what it's doing.** inPace downloads YouTube videos with yt-dlp, a free tool it gets the first time. That first download stopped with "Wait until the video downloads finish, then update" (it was waiting for itself). Now inPace checks that yt-dlp is here before every download and every "Play without ads": if it isn't, it gets it first ("Getting yt-dlp, the free tool that downloads YouTube videos (first time only)…"), and if it can't, it says so in plain words: what yt-dlp is, what went wrong (for example no internet) and what to do. A damaged copy is replaced by a fresh one by itself.
- **The Downloads page shows yt-dlp's status**, with Get yt-dlp now (or Update yt-dlp) right there.

## v1.30.16

- **Backups never fail because of a busy file.** On Windows, making a backup could stop with "Permission denied" when inPace happened to be preparing a page in the background at that moment (that file is locked while it's written). Backups now leave out inPace's cache (it's made again by itself) and any half-written file, and skip a file that's locked instead of failing. Everything that matters (your progress, courses, milestones) is in the backup as before.

## v1.30.15

- **New: Downloads, in the menu.** Every video download in one place, like a download manager:
  - Tabs for All, Downloading, Waiting, Failed and Finished, with how many are in each.
  - Each video shows its progress, size, speed and time left.
  - Buttons for everything you'd expect: Pause and Resume (a course, or all), Cancel one video, Download next (moves a waiting video to the front), Retry (one video, or every failed one) and Clear finished. A failed video says why.
  - "On this device" lists the videos you have, course by course, with their size and folder. Open the folder (on a computer), or delete one video or a whole course's videos (only files inPace downloaded; your own files are never touched).
  - The Downloads item in the menu shows how many videos are left.
- **Choose how videos download:** how many at the same time (1 to 5, 2 by default), a speed limit for all downloads together (so the rest of your internet stays usable), and the quality. Several videos now really download side by side.
- **Progress in the notifications.** On Android, a notification shows the progress bar, the video and the speed, with Stop all, and Android lets the downloads finish while you're in another app. When they're done, it says how many videos are ready (and how many didn't download). On a computer, one notification says when everything is done.
- **Adding a course or a whole roadmap shows its progress.** The button fills up as the course downloads ("Downloading 2/5 · 45% · 3.1 / 7 MB"), then says it's adding it, so the app never looks frozen. Course downloads show on the Downloads page and in the phone's notification too.
- **Progress when sending files.** Opening a course file, adding videos or a book, or restoring a backup: the button fills up as the files go. Any other button that takes a moment shows a small spinner.

## v1.30.14

- **Download a whole roadmap with one click.** A roadmap from the library now has "Download all N courses" right under "Follow this roadmap": one click follows it and puts every course on your device, ready even offline. On a roadmap you already follow, the button sits at the top too, and offers the courses that aren't on your device yet ("Download the remaining 3 courses"), with their size. You still start each course when you get to it.

## v1.30.13

- **Buttons don't reload the page anymore.** Turning a reminder on or off, adding or deleting one, saving a setting, and the buttons on My courses, the island, roadmaps, modules, races and People now update only the part of the page that changed. You stay exactly where you were, nothing flashes, and the message ("Saved.") shows as a small notice at the bottom. If a change touches something that can't be updated in place (a new language or theme, a video, a part with its own buttons), the page loads as before, so nothing can break.
- **Smoother on phones.** Diagrams were the biggest freeze: every lesson with a diagram loaded a 3 MB drawing tool and drew everything again, which locked a phone for a second or more. Now a diagram is kept on the device once drawn and shows instantly next time, and a new one is only drawn when you scroll near it. inPace also prepares every page in the background a few seconds after it starts, so the first visit to each page doesn't wait.

## v1.30.12

- **Videos follow one clear set of rules, so they can't get mixed up.** Before, if a lesson video was in the mini player and you opened another course and played its video, both videos stayed loaded: the new one didn't shrink when you left its lesson, and on Android the floating window showed a black screen (it was showing the old, hidden video). Now:
  1. One video plays at a time. Starting a video pauses the one that was playing.
  2. Videos only play in the main page. Pressing play on a lesson you opened while the mini player was showing closes the mini player, opens that lesson as the main page and starts its video there. So it shrinks into the mini player and floats over other apps like any lesson video.
  3. The mini player, Android's floating window and the system's media controls all follow that one video.
  4. The mini player never covers a menu, sheet or dialog.
- **Reminders: "Other…" for your own schedule.** Next to Every day, Weekdays and Weekends, "Other…" lets a reminder repeat every 2 to 60 days, starting on a day you pick. For example every 2 days for a lighter pace, or every 7 days for a weekly review. It works on computers and on Android.

## v1.30.11

- **The mini player goes away when you start another video.** On phones, starting a video from another lesson or course paused the one in the mini player but left it on screen. Now it closes as soon as you press play on the new video.
- **The mini player no longer covers menus.** On phones it sat on top of the More sheet and other menus and dialogs. It now hides while one is open and comes back when you close it.
- **YouTube videos keep inPace's player.** On a busy phone (for example with the mini player open) a new video's YouTube player could take a few seconds too long to answer, so inPace switched to YouTube's own player with its title, buttons and chapter bar. inPace now keeps asking until YouTube answers.
- **Scrollbars match inPace's colors.** They're thin and quiet in light, dark and AMOLED black. On Linux this also removes the white bar at the window's edge (on the left in Arabic), which was the system's light scrollbar.

## v1.30.10

- **Android: the app starts again on phones where it stopped at "inPace could not start".** On some phones (a Nothing Phone, issue #2) it showed a Java error, ClassNotFoundException "Landroid/content/Context;". A part the app uses to find its own folder had moved to a new way of talking to Android that fails on those phones. The app now uses the earlier version of that part, which works everywhere. Thanks to pix3latedtr3 for the detailed report.

## v1.30.9

- **Mac: the mouse wheel scrolls again.** On recent macOS, pages scrolled with the trackpad but not with a mouse wheel. A setting that stops phones from bouncing when you pull down a page also made Safari's engine (which the Mac app uses) ignore mouse wheels. It now only applies on touch screens. Thanks to k on Discord for reporting it.

## v1.30.8

- **The quality and subtitle menus fit small video players.** On phones the quality list was taller than the video, so the top of it was cut off. Now the sizes sit in two columns under Auto, the note only shows when there's room (otherwise it's the menu's tooltip), and a long subtitle list scrolls inside the video instead of being cut.

## v1.30.7

- **Phones on their side and mid-size windows use the whole width.** Between 761 and 860 pixels wide (most phones turned sideways), every page was squeezed into a narrow strip on one side, with an empty space where the side menu used to be. The side menu is hidden at that size, and now its space goes with it.
- **New: AMOLED black.** Settings → Light or dark has the mode (like my device, light, dark) and how dark mode looks: warm dark, as before, or AMOLED black, with fully black backgrounds. It's easier on the eyes at night and saves battery on OLED phone screens. The light/dark button at the top keeps your choice.

## v1.30.6

- **Choosing a quality now really changes it.** YouTube's player inside apps ignores quality requests, and on phones it ignored inPace's size trick too. Now the menu has Auto (YouTube picks, as before) and the sizes the video has (1080p, 720p, 480p, 360p). Picking a size gets the video at that size and plays it in inPace's own player from the same second; YouTube keeps playing until it's ready. Auto takes you back to YouTube's player. Your choice is remembered for the next lessons. If a size can't be had on your device, it says so and YouTube keeps playing.
- **CC really switches subtitles, and Off turns them off.** Subtitles YouTube had switched on by itself stayed on whatever you picked. Now YouTube's own subtitles stay off until you pick one. When inPace can't get a language's text, YouTube shows that language itself. When inPace can't read the list at all, the menu offers YouTube's subtitles, then lists its languages.
- **Phone: YouTube no longer stops for good after the floating window.** Coming back from the floating window rebuilt the page's view, which stopped YouTube and could leave the page laid out at the floating window's small size. The view now stays as it is, the page lays itself out again, and a video that was playing keeps playing.
- **A YouTube video that doesn't answer Play loads again at the same second and plays.**

## v1.30.5

- **YouTube's own screen never shows in the floating window.** When a video was paused there, YouTube's title, logo, play button and suggested videos showed through. Now the video's still picture covers them whenever it isn't playing, as on the lesson page.
- **The quality menu shows the qualities the video really has.** It used to always list 1080p to 360p. Now it lists what YouTube offers for that video (once it starts playing), the button shows the quality that's really playing, and a quality the video doesn't have falls back to the best one below it.
- **CC works for YouTube lessons and lists the languages.** The CC button only switched YouTube's captions on and off. Now it lists the video's subtitles: the ones its maker added, and YouTube's automatic ones in the video's language, your app language and English. The one you pick shows over the video in inPace's style (YouTube's captions stay off). The last language you chose comes back next time.

## v1.30.4

- **Phone media controls show the course's picture.** The notification shade and lock screen showed inPace's logo; now they show the course's cover (or the YouTube video's picture when the course has none).
- **The floating video is only the video, filling the whole window.** It still had a black strip on some phones: the video was trapped in the size of the page around it, and the app kept room for the phone's status bars while floating. Both are fixed, for YouTube and saved videos.
- **The timer no longer floats.** It was squeezed into the floating window over the video, or floated on its own half cut off. Now, when you leave the app, the timer is in your notifications, with Pause and Stop; inside the app it's the bar at the top. Only a playing video floats.
- **Settings no longer slides sideways on phones.** The three timer looks had hidden buttons as wide as the screen, which made the page wider than the phone and cut off the top bar and the tabs.
- "+5" reads the right way round in Arabic.

## v1.30.3

- **Phone: lesson videos in Android's media controls, like YouTube.** The notification shade and lock screen show the lesson, the course and its picture, with play/pause, 10 seconds back and forward, and previous/next lesson. The floating window gets play/pause from it too.
- **Phone: the floating window is all video.** The video filled only the top of it, with a black strip below; now it fills the whole window, for YouTube and for saved videos.
- **Tempo asks nicely before notifications.** On the phone, Tempo explains what notifications are for (the timer, video controls, your study reminders) before Android's own question. "Maybe later" is fine: it asks again at most once a week, or when you start a timer or a video.

## v1.30.2

- **The pop-out window shows the video, filling the whole window at any size.** The timer bar shows under it only while a timer is running, and there's no "Start a timer" button there any more.
- **Lesson videos in your computer's media controls.** While a video plays, the media center (Windows, Linux) or Control Center (Mac) and the keyboard's media keys show the lesson and course, with play/pause, 10 seconds back and forward, and previous/next lesson.
- **Phone: Pause, Go on and Stop on the timer's notification.**
- **Tempo's island: the focus trip has the same Pause, +5 min and Stop buttons.** Every change is the trip's own: +5 min makes the plant grow for the longer time, Pause holds it until you press Go on (coming back to the screen no longer restarts a trip you paused), and Stop rests the sprout with every minute kept. The floating timer and the trip are the same timer.

## v1.30.1

- **The focus timer is its own thing.** Pausing a video no longer pauses the timer: only you pause or stop it. Its only link is the optional plant on Tempo's island. (The "pause with the video" option is gone.)
- **YouTube videos show at once when you press play again.** inPace kept YouTube's still picture over the video for 2.5 seconds every time it started, to hide YouTube's title. That's only needed the very first time; after a pause the video now shows right away.

## v1.30.0

- **Floating focus timer.** Press the new timer button at the top of any page and pick 10 to 90 minutes. The timer stays in a corner of every page, with three clear buttons: Pause or Go on, +5 min, and Stop.
  - Drag it anywhere. Drag its corner to make it bigger or smaller. inPace remembers both.
  - Three looks to pick from in Settings: a small pill, a card with Tempo and a progress bar, or a round dial.
  - It works without Tempo's island. If the island is on, you can also tick "grow a plant" and the timer becomes a focus trip.
  - It can pause by itself when the lesson video pauses, and go on when it plays again (on by default, in Settings).
  - On a computer, inPace tells you when the time is up even if it's minimized. On the phone, the timer is a bar under the top bar, and it counts down in the notification.
- **Mini player.** Leave a lesson while its video plays, and the video moves to a corner and keeps playing while you use the rest of inPace, like YouTube. Tap it, or press Back, to return to the lesson at the same second. Drag it to any corner. On the phone it sits above the bottom tabs.
- **Pop-out window.** A new button on the video player opens a small inPace window that stays above your other apps, with the video and the timer. "Back to inPace" carries on in the main window from the same second. Works in the Windows, Mac and Linux app windows. In a browser, Chrome and Edge use their picture-in-picture window.
- **Android: floating over other apps.** Leave inPace while a video plays or a timer runs, and it keeps floating in a small window over your other apps, showing the video and the timer in the look you picked.
- **Settings in clear groups:** You and the look, Studying, Videos, AI, Your data, and The app, with links at the top.
- The side menu's "Continue" box no longer cuts off long lesson titles.

## v1.29.2

- Same as v1.29.0 (below), with fixes to how the downloads are built. The Linux download with its own engine is now built by its own workflow (release-linux-full.yml), which adds its files to the release page when they're ready, so it never holds up the other downloads. It also installs everything its engine needs before it's checked, and says exactly what's missing if the engine can't load.

## v1.29.1

- Same as v1.29.0 (below). The v1.29.0 build stopped on Windows because one new check read a file the wrong way there; this version fixes that check, so all the downloads get built.

## v1.29.0

- **Linux: a smarter app window.** On Zorin and Pop!_OS the window could stay gray for 20 seconds, then inPace reopened as an Edge window. The cause: inPace forced the page engine (WebKit) to draw without the graphics card, and newer WebKit versions on Wayland show nothing that way.
  - inPace now tries WebKit's normal drawing first. If the window stays blank for 4 seconds or the engine crashes, it tries the safe way, then a full software way, then the Edge or Chrome app window.
  - The way that works is remembered (`window.json` in the data folder), so the next start goes straight to it, with no waiting.
  - If none of inPace's own windows work, the next starts open the Edge or Chrome app window at once. After each update inPace tries its own window again. To try again yourself: `INPACE_WINDOW=reset inpace`.
  - When a way fails, `window.log` now says why, with the engine's own error message.
- **New Linux download with its own engine:** `inPace-linux-full.deb` and `inPace-linux-full.AppImage`. It's the same app with its own page engine (Chromium, through Qt) inside, so the window looks and works the same on every Linux, whatever WebKit the system has. About 150 MB bigger. It updates itself to the same kind of download.
- **Linux AppImage:** both Linux versions now also come as an AppImage, one file that runs on most Linux systems without installing. It updates itself too.
- The website's download section shows both Linux versions, with the normal one first and what makes the other one different.

## v1.28.20

- **Linux: inPace opens faster and stays in its own window.** Reported on Zorin and Pop!_OS: the inPace window opened, closed after a while, and inPace reopened as an Edge or Chrome window.
  - The window used to get 20 seconds to load *every* picture of the first page, or inPace decided it didn't work there. Now it counts as working as soon as the page starts to show, and waits up to 60 seconds.
  - If the page engine stops before the first page shows, it tries again (up to 3 times in a minute) instead of giving up at once.
  - The window now opens at the same moment as the app, with Tempo and "Opening inPace…" and a moving bar, instead of an empty wait.
  - Anything that goes wrong with the window is written to `window.log` in the inPace data folder, so it can be reported.

## v1.28.19

- **Linux: inPace stays in its own window.** On some systems (reported on Pop!_OS with COSMIC), the page engine inside the window could stop when opening a page like My courses. inPace then closed the window and opened in the browser instead. Now it simply loads the page again in the same window. Only if it keeps failing (3 times in a minute) does it move to another way of showing inPace.

## v1.28.18

- **inPace is on Telegram:** follow [t.me/inPace_app](https://t.me/inPace_app) for new versions, new courses and roadmaps, in English and Arabic. The link is in the side menu (next to Discord), on the Feedback page, on the website and in the library.
- New versions, new and updated courses and roadmaps are now posted to the Telegram channel by themselves, like on Discord, with the course covers.
- Discord posts are now in English and Arabic.

## v1.28.17

- **Roadmaps have pictures now.** Every roadmap, from the library or made by you, gets a bold picture made from the covers of its first three courses, with the path and the number of courses on it. It shows in the library's Roadmaps tab, on your Roadmaps page and at the top of each roadmap. Nobody has to draw one: it updates itself when the courses change, and works offline with your own courses' covers.
- **Tempo the librarian** now welcomes you to the course library, glasses on, reading next to a pile of books.

## v1.28.16

- **The library is in sections:** Linux, Cloud and DevOps; Programming and Web; Data and Databases; AI and Machine Learning; Maths; Careers and Interviews; Business and Accounting; Languages; Build inPace. The buttons above the list jump to a section, and inside each one courses go from beginner to advanced. Works the same on phones (the section buttons scroll sideways).
- **A smarter course search,** in the library and in My courses: it looks inside module and lesson titles too, forgives a small typo ("kubernets"), understands short names (k8s, js, ml, postgres), ignores Arabic spelling variants (أ/ا, ة/ه), and shows the best matches first.
- **Level and language filters** in the library: beginner, intermediate or advanced; English or Arabic.
- Courses with extra files now say "Extra downloads" instead of always "Videos download separately".

## v1.28.15

- **"Play without ads" works for far more videos.** YouTube now gives most videos only as separate picture and sound files, which inPace used to skip. Now it tries one file first, then plays the picture and sound files together (kept in step), then the phone stream where the device plays it, and if YouTube says no, it asks again as other YouTube apps (TV, iPhone and more).
- **Two choices in the video's place:** "Play on YouTube" (faster, more qualities) and "Play without ads" (can take a little longer). The extra row under the video is gone, and a failed try just says "No ad-free copy right now." (the details are in its tooltip).
- **A sharp still picture when you pause a YouTube video:** the 1280×720 one when YouTube has it, instead of the small 480×360 one. Videos played without ads stop on their real last frame.
- **A calmer lesson page around videos:** the part line is one short line ("Part 1 of 33 · 0:30–19:49 · Full video"), and Download is one small button with the size on it.

## v1.28.14

- **No more jumping ahead on phones.** While a video plays, its control bar hides, but it could still be touched: a tap or a scroll low on the video moved it forward. Now the hidden bar can't be touched, and the first tap on a playing video just shows the controls (like phone video apps); the next tap plays or pauses. Same for YouTube lessons and your own video files.
- **"Play without ads" is a button under each YouTube video,** next to "Download this video". Press it and the video plays in inPace's own player through yt-dlp, with no ads. Play still plays it on YouTube. If it can't play without ads, it says why instead of failing quietly.
- **It works more often:** the first time, inPace gets yt-dlp right away and waits for it, and on Android it also accepts YouTube's phone streams.

## v1.28.13

- **The video player fits on phones.** On a narrow screen the control bar no longer spills over: the time stays whole, Quality says "Auto" on one line, and speed and full screen are always there. To make room, volume (your phone has its own buttons) and the 10-second back and forward buttons are hidden on narrow screens, and the big play button no longer covers the progress bar. This is the same for YouTube lessons and your own video files, and for narrow windows on a computer.

## v1.28.12

- **Course outlines show a lesson's videos.** A lesson with YouTube videos in its text now says "video" or "4 videos" next to "slides" in the library, so you can see the videos are there before you add the course.

## v1.28.11

- **Ad blocker for YouTube lessons (on by default, you can turn it off in Settings → YouTube videos).** When you press play, yt-dlp finds the video's plain file and inPace's own player plays it, so YouTube's ads never load. yt-dlp updates itself once a day, and the blocker's settings update from the inPace website, so it keeps working when YouTube changes. The picture can be lower than on YouTube; a link under each video opens YouTube's player for a better picture. If a video can't play this way, YouTube's player opens by itself, with the ad guard.
- **The website shows inPace's GitHub stars**, live, in the top menu and with the other numbers.

## v1.28.10

- **Getting a course's files is three clear steps.** When slides, videos or files aren't on your device yet, the course page says: **1. Download them** (the official links are right there), **2. Find them for me**, **3. Saved them somewhere else?** choose that folder or the .zip.
- **"Find them for me"** looks in Downloads, Documents and Desktop (on a phone, Download), inside folders too, and remembers the folder it found. If the files are in a **.zip**, inPace unzips it into its own folder first (safely: nothing lands outside it, and Mac leftovers are skipped).
- **You can choose a .zip** instead of a folder, and inPace unzips it.

## v1.28.9

- **Calmer on laptop screens.** On screens up to 1600 pixels wide, text and buttons are a little smaller, the side menu and top bar are slimmer, course pages put the picture beside a shorter title, and My courses fits four courses in a row. Nothing looks zoomed in anymore.
- **Course files in subfolders are found.** If you choose a folder that keeps the files one or more folders down (like "DLS Slides/DLS_C1/C1_W1.pdf"), inPace now finds them by name.
- **Download links for official sources.** Courses can list where to get their files; the course page shows them as "Official sources", and as buttons when files are missing. Book courses can link straight to a free PDF (**Download the book (PDF)**).

## v1.28.8

- **Choose the YouTube quality:** a new button in the video bar: **Auto**, 1080p, 720p, 480p or 360p, remembered for next time. (YouTube ignores direct quality requests from apps, but it picks the quality from the size of its player, so inPace sizes it for the quality you chose. On a slow connection YouTube may still go lower.)
- **YouTube ads don't get in the way:** while an ad plays, inPace steps aside so you can see it and press **Skip ad**, shows "Ad: the lesson starts after it", and doesn't save the ad's time as your place in the lesson. Your player comes back when the lesson starts.
- **The ad guard is your choice:** Settings → **YouTube videos** → **Ad guard** (on by default).
- **It keeps working when YouTube changes:** if YouTube doesn't answer inPace's player, the lesson switches to YouTube's own player by itself, from the same second. And the few numbers that guide the player (and the ad guard) come from the inPace website once a day, like yt-dlp's updates, so they can be fixed without a new version. They're numbers and switches only, never code.

## v1.28.7

- **Updates now really show up.** The app window kept its old copy of inPace's script and styles after an update, so new things (like the new YouTube player) didn't appear. Their links now change whenever the files change, so every update loads the new ones.
- **Delete all my data** (Settings, at the bottom): removes your courses, progress, notes, milestones, people, races, reminders and private key, and inPace starts fresh. You type a word to confirm, and you can also delete the videos inPace downloaded.

## v1.28.6

- **A real Windows installer: `inPace-setup.exe`.** Run it and click through: it installs inPace for you (no admin password), adds it to the Start menu (and the desktop if you like), shows up in *Settings → Apps* with an uninstaller, and opens inpace:// links. Your courses and progress stay in `Documents\inPace`, so installing, updating or removing inPace never touches them.
- **Windows trusts it more:** inPace is now a normal program folder instead of one self-unpacking .exe (the thing virus scanners distrust most), and its files say who made them and which version they are.
- **Updates on Windows use the installer too:** when a new version is ready, "Install and restart" runs it quietly, and inPace opens again by itself.
- Copies of inPace you unzipped before still update themselves: first to this version, then to the installed version with the update after.

## v1.28.5

- **YouTube videos use inPace's own player now**, the same one as video files: the big play button, ±10 seconds, volume slider, speed, subtitles (CC), full screen, and the same keyboard keys (K or space, J, L, arrows, F, M, C).
- **No more YouTube clutter:** its title bar, logo, buttons and "More videos" panel are hidden. When a video is paused you see its picture and inPace's play button instead of YouTube's pause screen.
- A lesson that plays one part of a long video counts from 0:00 to the part's length, the same as video files.

## v1.28.4

- **The Android app is back in the release.** The 1.28.3 Android build stopped at its first step, so 1.28.3 shipped for computers only. 1.28.4 has everything from 1.28.3, for phones too.

## v1.28.3

- **"A new version is out" now only shows when there really is one.** Versions 1.28.1 and 1.28.2 were published with the old number (1.28.0) inside, so they kept saying an update was waiting. From now on each release takes its number from its tag, so this can't happen again.
- **New courses in the library:** inPace looks for new library courses twice a day. When there are some, you get one notification, a number on **Course library** in the menu, a note at the top of the library, and a **New** tag on each new course (they're listed first).
- **A real Refresh button** in the library, with when the list was last checked.
- **Tables in lessons look right on phones:** whole words (no more "Featur e"), tighter rows, and you swipe sideways when a table is wide.
- **About inPace** in Settings: your version, the code on GitHub (stars welcome), Discord and the website. The footer has an **About** link too.
- **Website fix on phones:** the top bar no longer squeezes the inPace logo under the Discord button.

## v1.28.0

- **inPace speaks 14 languages.** English, العربية, Español, Français, Deutsch, Português, Bahasa Indonesia, Türkçe, Tiếng Việt, Русский, हिन्दी, ไทย, 日本語 and 简体中文.
  - **It picks yours by itself** the first time you open it, from your phone's or computer's own language. You can also pick from the list on the welcome page, or change it any time in **Settings → Interface language**.
  - Every screen is translated: the menu, your courses, lessons, quizzes, milestones, the library, roadmaps, settings, and Tempo's welcome tour.
  - Letters that inPace's own font doesn't have (Japanese, Chinese, Thai, Hindi, Russian, Vietnamese, Turkish) come from the fonts already on your device. Nothing extra is downloaded, and inPace still works with no internet.
  - Dates are written the way each language writes them.
- **The website speaks them too**, and opens in your language the first time you visit.
- **Anything not yet translated shows in English** instead of breaking, so a language is useful from its first line.
- **Want to fix a word, or add your language?** It's one file per language. See `community/TRANSLATING.md`, or tell us on Discord.

## v1.27.0

- **The inPace Discord.** A place to ask for help, request courses and talk with other learners, in English and Arabic. Open it from **Discord community** in the menu, from the Feedback page, or from the Discord button on both websites.
  - New releases, new library courses, every change we make, and new feedback are posted there by themselves.
  - **Tempo, the inPace bot,** answers common problems in #help and #مساعدة right away, in your language (black videos, MKV files, YouTube errors, subtitles, installing). When the team marks a message with 🐞, it becomes a GitHub issue, and Tempo tells you when it's fixed.
- **New in the library: English irregular verbs**, in English and in Arabic. Over 100 verbs learned in a dozen patterns, with the common mistakes and the full list to review. Asked for on Reddit.
- **Lessons cut from a long video say so.** A line above the video says which part it is ("Part 2 of 3") and which minutes it plays, with a link to the full video. The course outline marks these lessons too ("✂ part 2/3").
- **A bar for just your part.** Under a YouTube video that's cut into lessons, inPace adds its own controls. The bar goes from 0:00 to the end of your part, with play, back and forward 10 seconds, and speed. YouTube's own controls still work too.
- **Your own subtitles.** Put a subtitle file next to a video with the same name ("Lesson 1.srt", or "Lesson 1.ar.srt" for Arabic) and it shows up by itself. Or press **CC** on the player, then **Add a subtitle file**. Both .srt and .vtt work, and so do old Arabic files that aren't UTF-8. inPace remembers the subtitles you picked.
- **When a video can't play, you know why.** Instead of a black box, the player says what's wrong and what to do:
  - A format the app window can't show (MKV, AVI, H.265…): **Open in your video player**, or convert it to MP4.
  - Linux: if your computer is missing video support, it shows the one command to install it. The .deb now installs it by itself.
  - YouTube refusing to play a video inside apps: a button to watch it on YouTube.
- **More video files count as lessons:** AVI, WMV, FLV, MPG and 3GP.
- New Arabic translations for everything above.

## v1.26.0

- **A pop-up when a new version is out.** inPace checks GitHub at most twice a day. When there's a newer version, a window shows what's new and one button to get it:
  - On Windows, Mac and Linux: **Update now**. If you turned on automatic updates, there is no pop-up, it just updates.
  - On Android: **Download the new version**, which gets the new app file.
  - If you run inPace from its source code: the `git pull` command to run.
  - **Later** hides it for 3 days. A newer version shows it again. Offline, nothing happens.
- **Feedback and ideas.** A new page in the menu (and in **More** on a phone) to tell us about a problem, an idea or a question. Fill it in, press **Continue on GitHub**, and GitHub opens with everything filled in, including your inPace version and system if you want.
- **Share this course.** Every course page now has a **Share this course** button under **Continue**. It sends a short link when the course is in the library, or the course file, or helps you publish it.
- **Share a course, from inside the app.** The library page has **Share a course**: it lists your courses, and each one has a **Publish** button. The publish page is now a short form (description, language, tags, license, notes) that fills in the library's GitHub form for you. You only drag the course file in.
- **The websites are easier to find on Google.** Both websites now have a sitemap, real page addresses, link previews with a picture, and the details search engines read (free app, free courses, languages, lesson hours).
- **New pages on the websites:** a **Share your course** form in the library and a **Feedback and ideas** form on the inPace website.
- New Arabic translations for everything above.

## v1.25.2

- **The first open speaks your language.** On a phone or computer set to Arabic, inPace opens in Arabic from the very first screen, and in English otherwise. The welcome page also has **English** and **العربية** buttons at the top, so you can pick before you type your name. The choice is saved, and you can still change it in **Settings**.
- **The welcome tour works on phones.** Before, six of its steps all pointed at the **More** button, and you couldn't see what they talked about. Now the tour opens the **More** sheet and points at each item inside it (People, Races, Open a file, light or dark, Settings, Tempo's island), then closes it again.
  - On a phone the tour's card goes across the screen, above or below the item it talks about, so it never covers it.
- New Arabic translations for the above.

## v1.25.1

- **Roadmaps with courses you can't get.** A roadmap someone sent you as a link or a file can name a course that's only on their computer.
  - Before, the roadmap stopped at that course: no button, and it could never be finished. Now it moves on to the next course you can take.
  - Its page lists those courses and gives three ways out: **Open a course file** (ask the sender for it), **Check the library again**, or **Take them off the roadmap**, which keeps a copy without them as your own version.
  - inPace only takes courses off after checking the library online, so a course never gets taken off because you were offline.
  - Before you follow a shared roadmap, its page already says which courses can't be added.
- **Offline is not "missing".** When inPace has no library list yet (offline, or the library was never opened), courses on a roadmap say **Needs the internet** and **Check again**, instead of **Not in the library**. The share page no longer warns that every course is missing in that case.
- **Add all.** Following a roadmap still downloads nothing, and you add each course when you get to it. Now there's also **Add all**, with the total size, to get every course at once, for example before a trip. Courses you already have stay as they are.
- **Safer adding.** A roadmap's **Add** button only adds courses that are on that roadmap.
- New Arabic translations for everything above.

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
