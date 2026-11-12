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

## Done

- Starts inPace on the phone and shows it full screen, with a start screen while it loads
- Links to Telegram, WhatsApp, email and websites open those apps
- `inpace://` links open the right screen (friend links, progress, course links)
- The phone's back button goes back inside inPace
- Voice notes can use the microphone
- No desktop update prompts on Android; Settings points to the website for new versions

## Next

- Downloads (progress files, backups, course files): save them and open Android's share sheet
- Opening files: Android's file picker for "Open a file" and uploads
- Course folders on the phone: Android's folder picker for video courses
- Phone-size layout fixes, page by page
- Attach the APKs to the release and add an Android button on the website
