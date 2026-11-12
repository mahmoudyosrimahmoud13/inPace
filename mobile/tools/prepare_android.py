"""After `flutter create`, adjust the generated Android project for inPace.

  - the app name and the inpace:// links
  - permission to talk to the local inPace server (http://127.0.0.1) and to record voice notes
  - a minimum Android version that the Python runtime supports
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "android" / "app"
manifest = ROOT / "src" / "main" / "AndroidManifest.xml"
m = manifest.read_text(encoding="utf-8")

perms = ['android.permission.INTERNET', 'android.permission.RECORD_AUDIO', 'android.permission.MODIFY_AUDIO_SETTINGS']
for p in perms:
    if p not in m:
        m = m.replace("<application", f'<uses-permission android:name="{p}"/>\n    <application', 1)

m = re.sub(r'android:label="[^"]*"', 'android:label="inPace"', m, count=1)
if "usesCleartextTraffic" not in m:
    m = m.replace("<application", '<application android:usesCleartextTraffic="true"', 1)

link_filter = """
            <intent-filter android:autoVerify="false">
                <action android:name="android.intent.action.VIEW"/>
                <category android:name="android.intent.category.DEFAULT"/>
                <category android:name="android.intent.category.BROWSABLE"/>
                <data android:scheme="inpace"/>
            </intent-filter>"""
if 'android:scheme="inpace"' not in m:
    # Put it inside MainActivity, after its launcher filter.
    m = re.sub(r"(<activity[^>]*MainActivity[\s\S]*?</intent-filter>)", lambda x: x.group(1) + link_filter, m, count=1)

# Let url_launcher see which apps can open links (Android 11+ package visibility).
if "<queries>" not in m:
    m = m.replace("</manifest>", """    <queries>
        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="https"/></intent>
        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="mailto"/></intent>
        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="tg"/></intent>
    </queries>
</manifest>""", 1)
manifest.write_text(m, encoding="utf-8")

for name in ("build.gradle.kts", "build.gradle"):
    g = ROOT / name
    if g.exists():
        t = g.read_text(encoding="utf-8")
        t = re.sub(r"minSdk(?:Version)?\s*=?\s*flutter\.minSdkVersion", "minSdk = 24" if name.endswith("kts") else "minSdkVersion 24", t)
        g.write_text(t, encoding="utf-8")
print("Android project ready:", manifest)
