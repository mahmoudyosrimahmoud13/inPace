"""After `flutter create`, adjust the generated Android project for inPace.

  - the app name and the inpace:// links
  - permission to talk to the local inPace server (http://127.0.0.1) and to record voice notes
  - a minimum Android version that the Python runtime supports
"""
import re
from pathlib import Path

# The app's one screen, with picture-in-picture added. The page says when floating makes sense ("auto": a video
# plays or a timer runs); Android 12+ then floats by itself when you leave, older ones on onUserLeaveHint.
# While floating, the page is told so it shows only the video and the timer.
PIP_ACTIVITY = r"""package org.inpace.inpace_mobile

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.PictureInPictureParams
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.support.v4.media.MediaMetadataCompat
import android.support.v4.media.session.MediaSessionCompat
import android.support.v4.media.session.PlaybackStateCompat
import android.util.Rational
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.net.URL

// inPace's one screen, plus:
//  - picture-in-picture: leave inPace while a video plays or a timer runs, and it keeps floating over other apps
//  - a media session: the lesson video shows in Android's media controls (notification shade, lock screen), with
//    play/pause, 10 seconds back and forward, and previous/next lesson. Android's floating window uses it too.
// The page drives both through the "inpace/pip" channel (see main.dart and app.js).
class MainActivity : FlutterActivity() {
    private var autoPip = false
    private var channel: MethodChannel? = null
    private var session: MediaSessionCompat? = null
    private var artUrl = ""
    private var art: Bitmap? = null
    private var last: Map<*, *>? = null
    private val main = Handler(Looper.getMainLooper())
    private val mediaAction = "org.inpace.inpace_mobile.MEDIA"
    private val mediaReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val what = intent?.getStringExtra("what") ?: return
            channel?.invokeMethod("media", what)
        }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "inpace/pip")
        channel?.setMethodCallHandler { call, result ->
            when (call.method) {
                "auto" -> {
                    autoPip = call.arguments == true
                    if (Build.VERSION.SDK_INT >= 31) {
                        try { setPictureInPictureParams(params()) } catch (e: Exception) { }
                    }
                    result.success(null)
                }
                "enter" -> result.success(enter())
                "media" -> {
                    try { media(call.arguments as? Map<*, *>) } catch (e: Exception) { }
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
        try {
            ContextCompat.registerReceiver(this, mediaReceiver, IntentFilter(mediaAction), ContextCompat.RECEIVER_NOT_EXPORTED)
        } catch (e: Exception) { }
    }

    override fun onDestroy() {
        try { unregisterReceiver(mediaReceiver) } catch (e: Exception) { }
        try { session?.release() } catch (e: Exception) { }
        session = null
        cancelMedia()
        super.onDestroy()
    }

    // ---- picture-in-picture ----
    private fun params(): PictureInPictureParams {
        val b = PictureInPictureParams.Builder().setAspectRatio(Rational(16, 9))
        if (Build.VERSION.SDK_INT >= 31) b.setAutoEnterEnabled(autoPip)
        return b.build()
    }

    private fun enter(): Boolean {
        if (Build.VERSION.SDK_INT < 26) return false
        return try { enterPictureInPictureMode(params()) } catch (e: Exception) { false }
    }

    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        if (autoPip && Build.VERSION.SDK_INT in 26..30) enter()
    }

    override fun onPictureInPictureModeChanged(isInPictureInPictureMode: Boolean, newConfig: Configuration) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        channel?.invokeMethod("changed", isInPictureInPictureMode)
    }

    // ---- the media session and its notification ----
    private fun tell(what: String) { channel?.invokeMethod("media", what) }

    private fun media(a: Map<*, *>?) {
        if (a == null || a["active"] != true) {
            try { session?.isActive = false } catch (e: Exception) { }
            cancelMedia()
            return
        }
        last = a
        val s = session ?: MediaSessionCompat(this, "inPace").also { ms ->
            ms.setCallback(object : MediaSessionCompat.Callback() {
                override fun onPlay() { tell("play") }
                override fun onPause() { tell("pause") }
                override fun onStop() { tell("pause") }
                override fun onSkipToNext() { tell("next") }
                override fun onSkipToPrevious() { tell("prev") }
                override fun onFastForward() { tell("fwd") }
                override fun onRewind() { tell("back") }
                override fun onSeekTo(pos: Long) { tell("seek:$pos") }
            })
            session = ms
        }
        val title = (a["title"] as? String) ?: "inPace"
        val artist = (a["artist"] as? String) ?: ""
        val playing = a["playing"] == true
        val pos = (((a["position"] as? Number)?.toDouble()) ?: 0.0) * 1000.0
        val dur = (((a["duration"] as? Number)?.toDouble()) ?: 0.0) * 1000.0
        val rate = ((a["rate"] as? Number)?.toFloat()) ?: 1f
        val hasNext = a["next"] == true
        val hasPrev = a["prev"] == true
        val url = (a["art"] as? String) ?: ""
        if (url != artUrl) {
            artUrl = url
            art = null
            if (url.isNotEmpty()) {
                Thread {
                    try {
                        val bmp = URL(url).openStream().use { BitmapFactory.decodeStream(it) }
                        main.post { if (artUrl == url && bmp != null) { art = bmp; last?.let { media(it) } } }
                    } catch (e: Exception) { }
                }.start()
            }
        }
        val meta = MediaMetadataCompat.Builder()
            .putString(MediaMetadataCompat.METADATA_KEY_TITLE, title)
            .putString(MediaMetadataCompat.METADATA_KEY_ARTIST, artist)
            .putString(MediaMetadataCompat.METADATA_KEY_ALBUM, "inPace")
        if (dur > 0) meta.putLong(MediaMetadataCompat.METADATA_KEY_DURATION, dur.toLong())
        art?.let { meta.putBitmap(MediaMetadataCompat.METADATA_KEY_ALBUM_ART, it) }
        s.setMetadata(meta.build())
        var actions = PlaybackStateCompat.ACTION_PLAY or PlaybackStateCompat.ACTION_PAUSE or
            PlaybackStateCompat.ACTION_PLAY_PAUSE or PlaybackStateCompat.ACTION_SEEK_TO or
            PlaybackStateCompat.ACTION_FAST_FORWARD or PlaybackStateCompat.ACTION_REWIND or PlaybackStateCompat.ACTION_STOP
        if (hasNext) actions = actions or PlaybackStateCompat.ACTION_SKIP_TO_NEXT
        if (hasPrev) actions = actions or PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS
        s.setPlaybackState(
            PlaybackStateCompat.Builder()
                .setActions(actions)
                .setState(if (playing) PlaybackStateCompat.STATE_PLAYING else PlaybackStateCompat.STATE_PAUSED,
                    pos.toLong(), if (playing) rate else 0f)
                .build()
        )
        s.isActive = true
        notifyMedia(s, title, artist, playing, hasPrev, hasNext)
    }

    private fun button(what: String, req: Int): PendingIntent {
        val i = Intent(mediaAction).setPackage(packageName).putExtra("what", what)
        return PendingIntent.getBroadcast(this, req, i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    private fun notifyMedia(s: MediaSessionCompat, title: String, artist: String, playing: Boolean, hasPrev: Boolean, hasNext: Boolean) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(MEDIA_CH) == null) {
            nm.createNotificationChannel(NotificationChannel(MEDIA_CH, "Lesson video", NotificationManager.IMPORTANCE_LOW))
        }
        var icon = resources.getIdentifier("ic_stat_inpace", "drawable", packageName)
        if (icon == 0) icon = applicationInfo.icon
        val open = PendingIntent.getActivity(this, 0,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val b = NotificationCompat.Builder(this, MEDIA_CH)
            .setSmallIcon(icon)
            .setContentTitle(title)
            .setContentText(artist)
            .setContentIntent(open)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)
            .setSilent(true)
            .setOngoing(playing)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
        art?.let { b.setLargeIcon(it) }
        var n = 0
        if (hasPrev) { b.addAction(android.R.drawable.ic_media_previous, "Previous", button("prev", 1)); n++ }
        val back = n
        b.addAction(android.R.drawable.ic_media_rew, "-10s", button("back", 2)); n++
        val pp = n
        if (playing) b.addAction(android.R.drawable.ic_media_pause, "Pause", button("pause", 3))
        else b.addAction(android.R.drawable.ic_media_play, "Play", button("play", 3))
        n++
        val fwd = n
        b.addAction(android.R.drawable.ic_media_ff, "+10s", button("fwd", 4)); n++
        if (hasNext) { b.addAction(android.R.drawable.ic_media_next, "Next", button("next", 5)); n++ }
        b.setStyle(androidx.media.app.NotificationCompat.MediaStyle()
            .setMediaSession(s.sessionToken)
            .setShowActionsInCompactView(back, pp, fwd))
        try { nm.notify(MEDIA_ID, b.build()) } catch (e: Exception) { }
    }

    private fun cancelMedia() {
        try { (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(MEDIA_ID) } catch (e: Exception) { }
    }

    companion object {
        const val MEDIA_ID = 7301
        const val MEDIA_CH = "inpace_media"
    }
}
"""

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
        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="codenote"/></intent>
"""
if 'android:scheme="codenote"' not in m and "</queries>" in m and 'android:scheme="mailto"' in m:
    # Works with CodeNote (inPace 1.31): see whether CodeNote is installed (Android 11+ needs this to look).
    m = m.replace("</queries>", '        <intent><action android:name="android.intent.action.VIEW"/><data android:scheme="codenote"/></intent>\n    </queries>', 1)
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
# Downloads keep going when you leave the app: while videos or courses download, the progress notification
# belongs to a foreground service (flutter_local_notifications' own), of the "data sync" kind.
for p in ("android.permission.FOREGROUND_SERVICE", "android.permission.FOREGROUND_SERVICE_DATA_SYNC"):
    if p not in m:
        m = m.replace("<application", f'<uses-permission android:name="{p}"/>\n    <application', 1)
if "flutterlocalnotifications.ForegroundService" not in m:
    m = m.replace("</application>", """        <service android:name="com.dexterous.flutterlocalnotifications.ForegroundService"
            android:exported="false" android:stopWithTask="false" android:foregroundServiceType="dataSync"/>
    </application>""", 1)
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

# Picture-in-picture: leave inPace while a video plays or a timer runs, and it keeps floating over other apps.
m = manifest.read_text(encoding="utf-8")
if "supportsPictureInPicture" not in m:
    m = re.sub(r'(<activity\b(?=[^>]*MainActivity))', r'\1 android:supportsPictureInPicture="true" android:resizeableActivity="true"', m, count=1)
    manifest.write_text(m, encoding="utf-8")
kotlin = ROOT / "src" / "main" / "kotlin" / "org" / "inpace" / "inpace_mobile" / "MainActivity.kt"
kotlin.parent.mkdir(parents=True, exist_ok=True)
kotlin.write_text(PIP_ACTIVITY, encoding="utf-8")

# The media session (MediaSessionCompat, MediaStyle) comes from androidx.media.
for gradle in (ROOT / "build.gradle.kts", ROOT / "build.gradle"):
    if gradle.exists():
        g = gradle.read_text(encoding="utf-8")
        if "androidx.media:media" not in g:
            line = 'implementation("androidx.media:media:1.7.0")' if gradle.suffix == ".kts" else "implementation 'androidx.media:media:1.7.0'"
            gradle.write_text(g.rstrip() + "\n\ndependencies {\n    " + line + "\n}\n", encoding="utf-8")
        break
