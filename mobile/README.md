# inPace for Android (in progress)

The phone runs the same inPace app as the desktop. Python starts inPace's small web server on the phone
(`127.0.0.1`, only the phone can reach it), and this Flutter app shows it full screen.

```text
mobile/
  pubspec.yaml              Flutter packages (serious_python runs Python, webview_flutter shows the app)
  lib/main.dart             start Python, wait until it answers, show it; links, back button, microphone
  app/src/main.py           the Python side: starts inPace on the port Flutter chose
  app/src/requirements.txt  Python libraries (PyNaCl has a ready Android build on pypi.flet.dev)
  tools/prepare_android.py  fixes up the generated Android project: name, permissions, inpace:// links
```

The Android project files (`android/`) aren't kept in git. GitHub makes them fresh with `flutter create` on every
build, and `tools/prepare_android.py` adjusts them.

**Build:** GitHub → **Actions → android → Run workflow**. The APKs appear under the run's **Artifacts**. It also
runs on every version tag.

## The app icon

The Android icon is the one made with IconKitchen, in `mobile/icon/res` (the build copies it into the app).
If that folder is removed, the build makes an icon from `packaging/android-icon/foreground.png` instead.

To use your own icon from [IconKitchen](https://icon.kitchen): upload `packaging/android-icon/inpace-mark.svg`,
pick the background color `#FFD43B`, and download the Android files. Unzip, and put the `res` folder from it at
`mobile/icon/res`. The next build uses it.

## Done

- Starts inPace on the phone and shows it full screen, with a start screen while it loads
- Links to Telegram, WhatsApp, email and websites open those apps
- `inpace://` links open the right screen (friend links, progress, course links)
- The phone's back button goes back inside inPace (and leaves full-screen video)
- Downloads (progress files, course files, backups, contact cards…): **Send it** (share sheet) or **Save it on this phone**
- "Add a file" buttons open Android's file picker
- "Choose folder" opens Android's folder picker, after asking for "All files access" (needed to read course videos where they are)
- Voice notes ask for the microphone
- Videos can go full screen
- "More apps…" opens Android's share sheet
- The inPace app icon
- No desktop update prompts on Android; Settings points to the website for new versions
- The top bar fits phone screens
- A tab bar at the bottom (Home, Courses, Add, Milestones, More), calmer pages and bigger buttons
- Restoring a backup keeps the app open
- On version tags, the APKs are added to the GitHub release, and the website has an Android download button

## Next

- Tell us what's still hard to use on a phone
- Test on real phones and fix what the first builds show
