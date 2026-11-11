# Changelog

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
