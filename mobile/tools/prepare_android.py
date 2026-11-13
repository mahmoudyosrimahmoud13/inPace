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
# Offline YouTube lessons are saved in the phone's Download folder. Android 11+ lets an app save its own files there;
# Android 10 needs the old storage mode, and Android 9 and older the write permission.
if "WRITE_EXTERNAL_STORAGE" not in m:
    m = m.replace("<application", '<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="29"/>\n    <application', 1)
if "requestLegacyExternalStorage" not in m:
    m = m.replace("<application", '<application android:requestLegacyExternalStorage="true"', 1)
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
# Reminders and alarms (flutter_local_notifications): permissions, the plugin's receivers, and an activity that
# can show a ringing alarm over the lock screen.
for p in ("android.permission.POST_NOTIFICATIONS", "android.permission.VIBRATE", "android.permission.RECEIVE_BOOT_COMPLETED",
          "android.permission.USE_EXACT_ALARM", "android.permission.USE_FULL_SCREEN_INTENT", "android.permission.WAKE_LOCK"):
    if p not in m:
        m = m.replace("<application", f'<uses-permission android:name="{p}"/>\n    <application', 1)
if "SCHEDULE_EXACT_ALARM" not in m:  # Android 12 (Android 13+ uses USE_EXACT_ALARM above)
    m = m.replace("<application", '<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" android:maxSdkVersion="32"/>\n    <application', 1)
receivers = """
        <receiver android:exported="false" android:name="com.dexterous.flutterlocalnotifications.ActionBroadcastReceiver"/>
        <receiver android:exported="false" android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationReceiver"/>
        <receiver android:exported="false" android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationBootReceiver">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED"/>
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED"/>
                <action android:name="android.intent.action.QUICKBOOT_POWERON"/>
                <action android:name="com.htc.intent.action.QUICKBOOT_POWERON"/>
            </intent-filter>
        </receiver>
"""
if "ScheduledNotificationReceiver" not in m:
    m = m.replace("</application>", receivers + "    </application>", 1)
if "showWhenLocked" not in m:
    m = re.sub(r'(<activity\b(?=[^>]*MainActivity))', r'\1 android:showWhenLocked="true" android:turnScreenOn="true"', m, count=1)
manifest.write_text(m, encoding="utf-8")

# The small notification icon (white inPace mark), kept even when unused resources are removed from release builds.
# Tempo's faces for notifications (tempo_*.png, villain.png) come from mobile/icon/res and are kept the same way.
res = ROOT / "src" / "main" / "res"
(res / "drawable").mkdir(parents=True, exist_ok=True)
(res / "drawable" / "ic_stat_inpace.xml").write_text("""<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="58" android:viewportHeight="58">
    <group android:translateX="0" android:translateY="1">
        <path android:strokeColor="#FFFFFFFF" android:strokeWidth="5" android:strokeLineCap="round" android:pathData="M15,42L42,16"/>
        <path android:fillColor="#FFFFFFFF" android:pathData="M8,42a7,7 0 1,0 14,0a7,7 0 1,0 -14,0"/>
        <path android:fillColor="#FFFFFFFF" android:pathData="M22,29a7,7 0 1,0 14,0a7,7 0 1,0 -14,0"/>
        <path android:fillColor="#FFFFFFFF" android:pathData="M33,16a9,9 0 1,0 18,0a9,9 0 1,0 -18,0"/>
    </group>
</vector>
""", encoding="utf-8")
(res / "raw").mkdir(parents=True, exist_ok=True)
(res / "raw" / "keep.xml").write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n<resources xmlns:tools="http://schemas.android.com/tools" '
    'tools:keep="@drawable/ic_stat_inpace,@drawable/tempo_*,@drawable/villain" />\n', encoding="utf-8")

for name in ("build.gradle.kts", "build.gradle"):
    g = ROOT / name
    if g.exists():
        t = g.read_text(encoding="utf-8")
        t = re.sub(r"minSdk(?:Version)?\s*=?\s*flutter\.minSdkVersion", "minSdk = 24" if name.endswith("kts") else "minSdkVersion 24", t)
        # The notifications plugin uses newer Java date and time classes; "desugaring" brings them to older Androids.
        if name.endswith("kts") and "isCoreLibraryDesugaringEnabled" not in t:
            t = t.replace("compileOptions {", "compileOptions {\n        isCoreLibraryDesugaringEnabled = true", 1)
            t = t.rstrip() + '\n\ndependencies {\n    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")\n}\n'
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
        // serious_python downloads the Python runtime for each kind of phone at the same time, and every
        // download writes the same notes file (build/.../download-task/etags.json). Two writing at once
        // corrupt it ("Unable to determine the current character ... int value of 0"). One at a time:
        val pyDownloads = tasks.names.filter {{ it.startsWith("downloadDistArchive_") }}.sorted()
        pyDownloads.zipWithNext {{ before, after -> tasks.named(after).configure {{ mustRunAfter(before) }} }}
        if (pyDownloads.size > 1) println("inPace: Python downloads run one at a time: ${{pyDownloads.joinToString()}}")
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
