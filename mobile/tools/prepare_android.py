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

perms = ['android.permission.INTERNET', 'android.permission.RECORD_AUDIO', 'android.permission.MODIFY_AUDIO_SETTINGS',
         # course folders on the phone (videos, PDFs, pages) are read where they are
         'android.permission.MANAGE_EXTERNAL_STORAGE', 'android.permission.READ_MEDIA_VIDEO',
         'android.permission.READ_MEDIA_AUDIO', 'android.permission.READ_MEDIA_IMAGES']
for p in perms:
    if p not in m:
        m = m.replace("<application", f'<uses-permission android:name="{p}"/>\n    <application', 1)
if "READ_EXTERNAL_STORAGE" not in m:
    m = m.replace("<application", '<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32"/>\n    <application', 1)

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
wanted = """        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="https"/></intent>
        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="mailto"/></intent>
        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="tg"/></intent>
"""
if 'android:scheme="mailto"' not in m:
    if "</queries>" in m:
        m = m.replace("</queries>", wanted + "    </queries>", 1)
    else:
        m = m.replace("</manifest>", "    <queries>\n" + wanted + "    </queries>\n</manifest>", 1)
manifest.write_text(m, encoding="utf-8")

for name in ("build.gradle.kts", "build.gradle"):
    g = ROOT / name
    if g.exists():
        t = g.read_text(encoding="utf-8")
        t = re.sub(r"minSdk(?:Version)?\s*=?\s*flutter\.minSdkVersion", "minSdk = 24" if name.endswith("kts") else "minSdkVersion 24", t)
        g.write_text(t, encoding="utf-8")
print("Android project ready:", manifest)

# Some plugins (file_picker…) are compiled against an older Android SDK than the libraries they use need,
# which fails the release check ("checkReleaseAarMetadata"). Compile every plugin against a new SDK.
COMPILE_SDK = 36
root = ROOT.parent
kts = root / "build.gradle.kts"
groovy = root / "build.gradle"
if kts.exists():
    t = kts.read_text(encoding="utf-8")
    if "inPace: compile plugins" not in t:
        block = f"""// inPace: compile plugins against a new Android SDK
subprojects {{
    afterEvaluate {{
        val ext = extensions.findByName("android")
        if (ext != null) {{
            // Called by name, so this file doesn't need the Android Gradle plugin's classes.
            val setter = ext.javaClass.methods.firstOrNull {{ it.name == "setCompileSdk" && it.parameterCount == 1 }}
            if (setter != null) {{
                setter.invoke(ext, {COMPILE_SDK})
            }} else {{
                ext.javaClass.getMethod("compileSdkVersion", Int::class.javaPrimitiveType).invoke(ext, {COMPILE_SDK})
            }}
            println("inPace: ${{project.name}} compiles against Android SDK {COMPILE_SDK}")
        }}
        // Skip the release "lint" check of each plugin: it only looks for code warnings, and newer lint
        // versions can crash on older Java ("List.removeLast()"), which would stop the whole build.
        tasks.matching {{ it.name.startsWith("lintVital") }}.configureEach {{ enabled = false }}
    }}
}}

"""
        # Must come before "evaluationDependsOn", which evaluates the projects early.
        i = t.find("subprojects")
        t = t[:i] + block + t[i:] if i >= 0 else t + "\n" + block
        kts.write_text(t, encoding="utf-8")
elif groovy.exists():
    t = groovy.read_text(encoding="utf-8")
    if "inPace: compile plugins" not in t:
        block = f"""// inPace: compile plugins against a new Android SDK
subprojects {{
    afterEvaluate {{ p ->
        if (p.hasProperty("android")) {{ p.android {{ compileSdkVersion {COMPILE_SDK} }} }}
    }}
}}

"""
        i = t.find("subprojects")
        t = t[:i] + block + t[i:] if i >= 0 else t + "\n" + block
        groovy.write_text(t, encoding="utf-8")

for name in ("build.gradle.kts", "build.gradle"):
    g = ROOT / name
    if g.exists():
        t = g.read_text(encoding="utf-8")
        t = re.sub(r"compileSdk\s*=\s*flutter\.compileSdkVersion", f"compileSdk = {COMPILE_SDK}", t)
        t = re.sub(r"compileSdkVersion\s+flutter\.compileSdkVersion", f"compileSdkVersion {COMPILE_SDK}", t)
        g.write_text(t, encoding="utf-8")
print("Plugins compile against Android SDK", COMPILE_SDK)

# Download one thing at a time: parallel downloads of the Python runtime can corrupt Gradle's download cache
# ("Unable to determine the current character ... int value of 0").
props = ROOT.parent / "gradle.properties"
t = props.read_text(encoding="utf-8") if props.exists() else ""
if "org.gradle.parallel" not in t:
    props.write_text(t.rstrip() + "\norg.gradle.parallel=false\n", encoding="utf-8")

# Release signing: one fixed key, so a new version installs over the old one and keeps people's data.
# GitHub passes the key's path and passwords in INPACE_KEYSTORE / INPACE_KEYSTORE_PASSWORD (from repository secrets).
app_kts = ROOT / "build.gradle.kts"
if app_kts.exists():
    t = app_kts.read_text(encoding="utf-8")
    if "inPace release key" not in t:
        signing = """
    // inPace release key (see .github/workflows/android.yml); without it, builds are signed with a test key
    signingConfigs {
        create("release") {
            val ks = file(System.getenv("INPACE_KEYSTORE") ?: "no-keystore")
            if (ks.exists()) {
                storeFile = ks
                storePassword = System.getenv("INPACE_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("INPACE_KEY_ALIAS") ?: "inpace"
                keyPassword = System.getenv("INPACE_KEY_PASSWORD") ?: System.getenv("INPACE_KEYSTORE_PASSWORD")
            }
        }
    }
"""
        t = t.replace("    buildTypes {", signing + "\n    buildTypes {", 1)
        t = t.replace('signingConfig = signingConfigs.getByName("debug")',
                      'signingConfig = if (file(System.getenv("INPACE_KEYSTORE") ?: "no-keystore").exists()) '
                      'signingConfigs.getByName("release") else signingConfigs.getByName("debug")', 1)
        app_kts.write_text(t, encoding="utf-8")
        print("Release signing ready")
