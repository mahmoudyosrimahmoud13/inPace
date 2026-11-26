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
import android.os.SystemClock
import android.util.Rational
import android.view.View
import android.widget.RemoteViews
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.net.URL
import org.json.JSONArray
import org.json.JSONObject

// inPace's one screen, plus:
//  - picture-in-picture: leave inPace while a video plays or a timer runs, and it keeps floating over other apps
//  - a media session: the lesson video shows in Android's media controls (notification shade, lock screen), with
//    play/pause, 10 seconds back and forward, and previous/next lesson. Android's floating window uses it too.
// The page drives both through the "inpace/pip" channel (see main.dart and app.js).
class MainActivity : FlutterActivity() {
    private var autoPip = false
    private var pendingOpen: String? = null
    private var pendingTimer: String? = null
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
                "install" -> result.success(install(call.arguments as? String ?: ""))
                "live" -> result.success(try { live(call.arguments as? Map<*, *>) } catch (e: Exception) { false })
                "schedule" -> result.success(try { InpaceCards.schedule(this, call.arguments as? Map<*, *>) } catch (e: Exception) { false })
                "unschedule" -> result.success(try { InpaceCards.unschedule(this, call.arguments as? List<*>) } catch (e: Exception) { false })
                "unscheduleBelow" -> result.success(try { InpaceCards.unscheduleBelow(this, (call.arguments as? Number)?.toInt() ?: 0) } catch (e: Exception) { false })
                "takeOpen" -> {
                    result.success(mapOf("url" to pendingOpen, "timer" to pendingTimer))
                    pendingOpen = null
                    pendingTimer = null
                }
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
        handleIntent(intent, false)  // opened from the sprint card: the app asks for it once it's ready (takeOpen)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent, true)
    }

    private fun handleIntent(i: Intent?, now: Boolean) {
        if (i == null) return
        val url = i.getStringExtra("inpace_url")
        val act = i.getStringExtra("inpace_timer")
        i.removeExtra("inpace_url")
        i.removeExtra("inpace_timer")
        if (act != null) {
            if (now && channel != null) channel?.invokeMethod("timer", act) else pendingTimer = act
        } else if (url != null) {
            if (now && channel != null) channel?.invokeMethod("open", url) else pendingOpen = url
        }
    }

    override fun onDestroy() {
        try { unregisterReceiver(mediaReceiver) } catch (e: Exception) { }
        try { session?.release() } catch (e: Exception) { }
        session = null
        cancelMedia()
        super.onDestroy()
    }

    // ---- inPace's own notification cards (v1.37.3): see InpaceCards below ----
    private fun live(a: Map<*, *>?): Boolean = InpaceCards.post(this, a)

    // ---- updates (v1.37): open Android's install dialog for a downloaded APK ----
    // Returns "ask" when Android first wants you to allow inPace to install apps (its setting opens), else "ok".
    private fun install(path: String): String {
        if (Build.VERSION.SDK_INT >= 26 && !packageManager.canRequestPackageInstalls()) {
            val i = Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                           android.net.Uri.parse("package:$packageName"))
            startActivity(i)
            return "ask"
        }
        val uri = androidx.core.content.FileProvider.getUriForFile(this, "$packageName.inpace.files", java.io.File(path))
        val i = Intent(Intent.ACTION_VIEW)
        i.setDataAndType(uri, "application/vnd.android.package-archive")
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(i)
        return "ok"
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
        const val LIVE_CH = "inpace_live"
    }
}

// inPace's notification cards (v1.37.3). Android 12+ ignores an app's colors on ordinary notifications, so every
// inPace notification brings its own layout: a yellow box like the app, Tempo's face, the text, and buttons.
//  - "live": the sprint and timer card, with countdowns Android keeps ticking (Chronometers)
//  - "reminder", "tempo": a reminder or one of Tempo's nudges, with Open
//  - "alarm": rings until you act (alarm sound, full screen on a locked phone), with Snooze and Stop
// Scheduled cards are kept by inPace itself (AlarmManager), saved in a small store so they come back after a
// restart of the phone, and drawn by InpaceCardReceiver when their time comes, even if inPace is closed.
object InpaceCards {
    private const val STORE = "inpace_cards"
    const val FIRE = "org.inpace.inpace_mobile.CARD"
    const val SNOOZE = "org.inpace.inpace_mobile.CARD_SNOOZE"
    const val STOP = "org.inpace.inpace_mobile.CARD_STOP"

    private fun mapOfJson(o: JSONObject): Map<String, Any?> {
        val m = HashMap<String, Any?>()
        for (k in o.keys()) {
            val v = o.opt(k)
            m[k] = when (v) {
                is JSONArray -> (0 until v.length()).map { i ->
                    val x = v.opt(i)
                    if (x is JSONArray) (0 until x.length()).map { j -> x.opt(j) } else x
                }
                JSONObject.NULL -> null
                else -> v
            }
        }
        return m
    }

    private fun jsonOf(a: Map<*, *>): String {
        val o = JSONObject()
        for ((k, v) in a) {
            o.put(k.toString(), when (v) {
                is List<*> -> JSONArray(v.map { x -> if (x is List<*>) JSONArray(x) else x })
                null -> JSONObject.NULL
                else -> v
            })
        }
        return o.toString()
    }

    private fun channel(ctx: Context, kind: String, name: String): String {
        val id = when (kind) {
            "alarm" -> "inpace_alarms"
            "reminder" -> "inpace_reminders"
            "tempo" -> "inpace_tempo"
            else -> MainActivity.LIVE_CH
        }
        if (Build.VERSION.SDK_INT < 26) return id
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(id) != null) return id
        val imp = when (kind) {
            "alarm" -> NotificationManager.IMPORTANCE_HIGH
            "reminder" -> NotificationManager.IMPORTANCE_HIGH
            else -> NotificationManager.IMPORTANCE_DEFAULT
        }
        val ch = NotificationChannel(id, name, imp)
        when (kind) {
            "alarm" -> ch.setSound(android.provider.Settings.System.DEFAULT_ALARM_ALERT_URI,
                android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_ALARM)
                    .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
            "live" -> { ch.setSound(null, null); ch.enableVibration(false); ch.setShowBadge(false) }
            else -> { }
        }
        nm.createNotificationChannel(ch)
        return id
    }

    fun openIntent(ctx: Context, req: Int, url: String, timer: String?): PendingIntent {
        val i = Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_NEW_TASK).putExtra("inpace_url", url)
        if (timer != null) i.putExtra("inpace_timer", timer)
        return PendingIntent.getActivity(ctx, req, i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    private fun broadcast(ctx: Context, action: String, req: Int, id: Int, json: String): PendingIntent {
        val i = Intent(ctx, InpaceCardReceiver::class.java).setAction(action).putExtra("id", id).putExtra("card", json)
        return PendingIntent.getBroadcast(ctx, req, i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    private fun clock(v: RemoteViews, clockId: Int, textId: Int, ends: Long?, text: String?) {
        val left = (ends ?: 0L) - System.currentTimeMillis()
        if (ends != null && left > 0) {
            v.setViewVisibility(clockId, View.VISIBLE)
            v.setViewVisibility(textId, View.GONE)
            v.setChronometer(clockId, SystemClock.elapsedRealtime() + left, null, true)
            v.setChronometerCountDown(clockId, true)
        } else if (!text.isNullOrEmpty()) {
            v.setViewVisibility(clockId, View.GONE)
            v.setViewVisibility(textId, View.VISIBLE)
            v.setTextViewText(textId, text)
        } else {  // a reminder: no clock at all
            v.setViewVisibility(clockId, View.GONE)
            v.setViewVisibility(textId, View.GONE)
        }
    }

    private fun fill(ctx: Context, v: RemoteViews, a: Map<*, *>, id: Int, big: Boolean, json: String) {
        v.setTextViewText(R.id.live_kicker, (a["kicker"] as? String) ?: "")
        v.setTextViewText(R.id.live_title, (a["title"] as? String) ?: "")
        clock(v, R.id.live_clock, R.id.live_clock_text, (a["ends_ms"] as? Number)?.toLong(), a["clock_text"] as? String)
        val face = ctx.resources.getIdentifier((a["face"] as? String) ?: "tempo_read", "drawable", ctx.packageName)
        if (face != 0) v.setImageViewResource(R.id.live_face, face)
        if (!big) return
        val label = (a["clock_label"] as? String) ?: ""
        v.setViewVisibility(R.id.live_left, if (label.isEmpty()) View.GONE else View.VISIBLE)
        v.setTextViewText(R.id.live_left, label)
        val body = (a["body"] as? String) ?: ""
        v.setViewVisibility(R.id.live_body, if (body.isEmpty()) View.GONE else View.VISIBLE)
        v.setTextViewText(R.id.live_body, body)
        val phase = (a["phase"] as? String) ?: ""
        if (phase.isEmpty()) {
            v.setViewVisibility(R.id.live_phase_row, View.GONE)
        } else {
            v.setViewVisibility(R.id.live_phase_row, View.VISIBLE)
            v.setTextViewText(R.id.live_phase, phase)
            clock(v, R.id.live_phase_clock, R.id.live_phase_text, (a["phase_ends_ms"] as? Number)?.toLong(),
                (a["phase_text"] as? String) ?: "")
        }
        val pct = (a["progress"] as? Number)?.toInt() ?: -1
        if (pct < 0) {
            v.setViewVisibility(R.id.live_bar, View.GONE)
        } else {
            v.setViewVisibility(R.id.live_bar, View.VISIBLE)
            v.setProgressBar(R.id.live_bar, 100, pct.coerceIn(0, 100), false)
        }
        val acts = (a["actions"] as? List<*>) ?: emptyList<Any>()
        val ids = intArrayOf(R.id.live_btn1, R.id.live_btn2)
        v.setViewVisibility(R.id.live_btns, if (acts.isEmpty()) View.GONE else View.VISIBLE)
        val url = (a["url"] as? String) ?: "/"
        for (k in ids.indices) {
            val pair = acts.getOrNull(k) as? List<*>
            if (pair == null || pair.size < 2) {
                v.setViewVisibility(ids[k], View.GONE)
                continue
            }
            v.setViewVisibility(ids[k], View.VISIBLE)
            v.setTextViewText(ids[k], pair[1].toString())
            val key = pair[0].toString()
            val req = id * 4 + 1 + k
            v.setOnClickPendingIntent(ids[k], when (key) {
                "snooze" -> broadcast(ctx, SNOOZE, req, id, json)
                "dismiss" -> broadcast(ctx, STOP, req, id, json)
                "open" -> openIntent(ctx, req, url, null)
                else -> openIntent(ctx, req, url, key)  // pause, resume, stop: the timer's buttons
            })
        }
    }

    // Show a card now. a: id, kind, title, body, kicker, face, url, and for the live card its clocks.
    fun post(ctx: Context, a: Map<*, *>?): Boolean {
        if (a == null) return false
        val id = (a["id"] as? Number)?.toInt() ?: return false
        val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (a["cancel"] == true) {
            nm.cancel(id)
            return true
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            ctx.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return true
        val kind = (a["kind"] as? String) ?: "live"
        val ch = channel(ctx, kind, (a["channel"] as? String) ?: "inPace")
        if (kind == "live" && Build.VERSION.SDK_INT >= 26) {
            for (old in arrayOf("inpace_sprint", "inpace_trip")) {  // the old silent channels
                try { nm.deleteNotificationChannel(old) } catch (e: Exception) { }
            }
        }
        val json = jsonOf(a)
        val small = RemoteViews(ctx.packageName, R.layout.inpace_live)
        val big = RemoteViews(ctx.packageName, R.layout.inpace_live_big)
        fill(ctx, small, a, id, false, json)
        fill(ctx, big, a, id, true, json)
        var icon = ctx.resources.getIdentifier("ic_stat_inpace", "drawable", ctx.packageName)
        if (icon == 0) icon = ctx.applicationInfo.icon
        val open = openIntent(ctx, id * 4, (a["url"] as? String) ?: "/", null)
        val b = NotificationCompat.Builder(ctx, ch)
            .setSmallIcon(icon)
            .setColor(0xFFFFD43B.toInt())
            .setContentTitle((a["title"] as? String) ?: "inPace")
            .setContentText((a["body"] as? String) ?: "")
            .setStyle(NotificationCompat.DecoratedCustomViewStyle())
            .setCustomContentView(small)
            .setCustomBigContentView(big)
            .setContentIntent(open)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
        when (kind) {
            "live" -> b.setOnlyAlertOnce(true).setShowWhen(false).setOngoing(a["ongoing"] == true).setAutoCancel(false)
                .setCategory(NotificationCompat.CATEGORY_PROGRESS).setPriority(NotificationCompat.PRIORITY_DEFAULT)
            "alarm" -> b.setCategory(NotificationCompat.CATEGORY_ALARM).setPriority(NotificationCompat.PRIORITY_MAX)
                .setFullScreenIntent(open, true).setAutoCancel(true).setTimeoutAfter(10 * 60 * 1000L)
                .setSound(android.provider.Settings.System.DEFAULT_ALARM_ALERT_URI, android.media.AudioManager.STREAM_ALARM)
            "reminder" -> b.setCategory(NotificationCompat.CATEGORY_REMINDER).setPriority(NotificationCompat.PRIORITY_HIGH).setAutoCancel(true)
            else -> b.setCategory(NotificationCompat.CATEGORY_REMINDER).setPriority(NotificationCompat.PRIORITY_DEFAULT).setAutoCancel(true)
        }
        val timeout = (a["timeout_ms"] as? Number)?.toLong() ?: 0L
        if (timeout > 0) b.setTimeoutAfter(timeout)
        val n = b.build()
        if (kind == "alarm") n.flags = n.flags or android.app.Notification.FLAG_INSISTENT  // keeps ringing until you act
        nm.notify(id, n)
        return true
    }

    private fun prefs(ctx: Context) = ctx.getSharedPreferences(STORE, Context.MODE_PRIVATE)

    private fun arm(ctx: Context, id: Int, at: Long, kind: String, json: String) {
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as android.app.AlarmManager
        val pi = broadcast(ctx, FIRE, id, id, json)
        val exact = Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms()
        try {
            when {
                kind == "alarm" && exact -> am.setAlarmClock(android.app.AlarmManager.AlarmClockInfo(at, openIntent(ctx, id * 4, "/", null)), pi)
                exact -> am.setExactAndAllowWhileIdle(android.app.AlarmManager.RTC_WAKEUP, at, pi)
                else -> am.setAndAllowWhileIdle(android.app.AlarmManager.RTC_WAKEUP, at, pi)  // a few minutes late at most
            }
        } catch (e: SecurityException) {
            am.setAndAllowWhileIdle(android.app.AlarmManager.RTC_WAKEUP, at, pi)
        }
    }

    // Schedule a card for later: a has at_ms plus everything post() takes.
    fun schedule(ctx: Context, a: Map<*, *>?): Boolean {
        if (a == null) return false
        val id = (a["id"] as? Number)?.toInt() ?: return false
        val at = (a["at_ms"] as? Number)?.toLong() ?: return false
        val json = jsonOf(a)
        arm(ctx, id, at, (a["kind"] as? String) ?: "reminder", json)
        prefs(ctx).edit().putString("c$id", json).apply()
        return true
    }

    fun unschedule(ctx: Context, ids: List<*>?): Boolean {
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as android.app.AlarmManager
        val ed = prefs(ctx).edit()
        for (x in ids ?: emptyList<Any>()) {
            val id = (x as? Number)?.toInt() ?: continue
            val i = Intent(ctx, InpaceCardReceiver::class.java).setAction(FIRE)
            val pi = PendingIntent.getBroadcast(ctx, id, i, PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE)
            if (pi != null) { am.cancel(pi); pi.cancel() }
            ed.remove("c$id")
        }
        ed.apply()
        return true
    }

    fun unscheduleBelow(ctx: Context, limit: Int): Boolean {
        val ids = prefs(ctx).all.keys.mapNotNull { it.removePrefix("c").toIntOrNull() }.filter { it < limit }
        return unschedule(ctx, ids)
    }

    // The time came (or the phone restarted): draw due cards, arm the rest again.
    fun fire(ctx: Context, id: Int, json: String?) {
        prefs(ctx).edit().remove("c$id").apply()
        if (json == null) return
        try { post(ctx, mapOfJson(JSONObject(json))) } catch (e: Exception) { }
    }

    fun rearm(ctx: Context) {
        val now = System.currentTimeMillis()
        for ((k, v) in prefs(ctx).all) {
            val id = k.removePrefix("c").toIntOrNull() ?: continue
            val json = v as? String ?: continue
            try {
                val o = JSONObject(json)
                val at = o.optLong("at_ms", 0L)
                if (at > now) arm(ctx, id, at, o.optString("kind", "reminder"), json)
                else if (now - at < 6 * 3600 * 1000L) fire(ctx, id, json)  // missed while the phone was off
                else prefs(ctx).edit().remove(k).apply()
            } catch (e: Exception) { }
        }
    }

    fun snooze(ctx: Context, id: Int, json: String?) {
        (ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(id)
        if (json == null) return
        try {
            val o = JSONObject(json)
            o.put("at_ms", System.currentTimeMillis() + 10 * 60 * 1000L)
            val nid = 900000 + (System.currentTimeMillis() / 1000 % 60).toInt()  // the snoozed range: a new plan never removes it
            o.put("id", nid)
            schedule(ctx, mapOfJson(o))
        } catch (e: Exception) { }
    }
}

class InpaceCardReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getIntExtra("id", 0)
        val json = intent.getStringExtra("card")
        when (intent.action) {
            InpaceCards.FIRE -> InpaceCards.fire(context, id, json)
            InpaceCards.SNOOZE -> InpaceCards.snooze(context, id, json)
            InpaceCards.STOP -> (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(id)
            Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED, "android.intent.action.QUICKBOOT_POWERON" ->
                InpaceCards.rearm(context)
        }
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
# inPace's own notification cards (v1.37.3): drawn when their time comes, and armed again after a phone restart.
if "InpaceCardReceiver" not in m:
    m = m.replace("</application>", """        <receiver android:name=".InpaceCardReceiver" android:exported="false">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED"/>
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED"/>
                <action android:name="android.intent.action.QUICKBOOT_POWERON"/>
            </intent-filter>
        </receiver>
    </application>""", 1)
# Updates (v1.37): the app downloads the new APK itself and opens Android's install dialog.
if "REQUEST_INSTALL_PACKAGES" not in m:
    m = m.replace("<application", '<uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES"/>\n    <application', 1)
if "inpace.files" not in m:
    m = m.replace("</application>", """        <provider android:name="androidx.core.content.FileProvider" android:authorities="${applicationId}.inpace.files"
            android:exported="false" android:grantUriPermissions="true">
            <meta-data android:name="android.support.FILE_PROVIDER_PATHS" android:resource="@xml/inpace_paths"/>
        </provider>
    </application>""", 1)
paths_xml = ROOT / "src" / "main" / "res" / "xml" / "inpace_paths.xml"
paths_xml.parent.mkdir(parents=True, exist_ok=True)
paths_xml.write_text('<?xml version="1.0" encoding="utf-8"?>\n<paths>\n    <cache-path name="updates" path="updates/"/>\n</paths>\n', encoding="utf-8")
if "showWhenLocked" not in m:
    m = re.sub(r'(<activity\b(?=[^>]*MainActivity))', r'\1 android:showWhenLocked="true" android:turnScreenOn="true"', m, count=1)
manifest.write_text(m, encoding="utf-8")

# The sprint and timer card (v1.37.3): its own layout, so it looks like inPace on Android 12+ too (Android ignores an
# app's colors on ordinary notifications there). Collapsed: one row, 48dp tall at most. Expanded: the full card.
_lay = ROOT / "src" / "main" / "res" / "layout"
_lay.mkdir(parents=True, exist_ok=True)
_drw = ROOT / "src" / "main" / "res" / "drawable"
_drw.mkdir(parents=True, exist_ok=True)
(_drw / "inpace_live_box.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#FFD43B"/><corners android:radius="14dp"/><stroke android:width="2dp" android:color="#111111"/>
</shape>
""", encoding="utf-8")
(_drw / "inpace_live_pill.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#111111"/><corners android:radius="999dp"/>
</shape>
""", encoding="utf-8")
(_drw / "inpace_live_face.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="oval">
    <solid android:color="#FFFFFF"/><stroke android:width="2dp" android:color="#111111"/>
</shape>
""", encoding="utf-8")
(_drw / "inpace_live_btn_dark.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#111111"/><corners android:radius="8dp"/>
</shape>
""", encoding="utf-8")
(_drw / "inpace_live_btn_light.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#FFFFFF"/><corners android:radius="8dp"/><stroke android:width="2dp" android:color="#111111"/>
</shape>
""", encoding="utf-8")
(_lay / "inpace_live.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="wrap_content"
    android:orientation="horizontal" android:gravity="center_vertical"
    android:background="@drawable/inpace_live_box" android:paddingStart="12dp" android:paddingEnd="6dp"
    android:paddingTop="3dp" android:paddingBottom="3dp">
    <Chronometer android:id="@+id/live_clock" android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:textColor="#111111" android:textSize="20sp" android:textStyle="bold" android:fontFamily="monospace"/>
    <TextView android:id="@+id/live_clock_text" android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:textColor="#111111" android:textSize="15sp" android:textStyle="bold" android:visibility="gone"/>
    <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1"
        android:orientation="vertical" android:layout_marginStart="10dp">
        <TextView android:id="@+id/live_kicker" android:layout_width="match_parent" android:layout_height="wrap_content"
            android:textColor="#5A4A00" android:textSize="11sp" android:textStyle="bold" android:maxLines="1" android:ellipsize="end"/>
        <TextView android:id="@+id/live_title" android:layout_width="match_parent" android:layout_height="wrap_content"
            android:textColor="#111111" android:textSize="13sp" android:textStyle="bold" android:maxLines="1" android:ellipsize="end"/>
    </LinearLayout>
    <ImageView android:id="@+id/live_face" android:layout_width="34dp" android:layout_height="34dp"
        android:background="@drawable/inpace_live_face" android:padding="3dp" android:scaleType="fitCenter"
        android:contentDescription="Tempo"/>
</LinearLayout>
""", encoding="utf-8")
(_lay / "inpace_live_big.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical"
    android:background="@drawable/inpace_live_box" android:padding="12dp">
    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
        android:orientation="horizontal" android:gravity="center_vertical">
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1"
            android:orientation="vertical">
            <TextView android:id="@+id/live_kicker" android:layout_width="match_parent" android:layout_height="wrap_content"
                android:textColor="#5A4A00" android:textSize="12sp" android:textStyle="bold" android:maxLines="1" android:ellipsize="end"/>
            <TextView android:id="@+id/live_title" android:layout_width="match_parent" android:layout_height="wrap_content"
                android:textColor="#111111" android:textSize="16sp" android:textStyle="bold" android:maxLines="2" android:ellipsize="end"/>
            <LinearLayout android:layout_width="wrap_content" android:layout_height="wrap_content"
                android:orientation="horizontal" android:gravity="bottom" android:layout_marginTop="2dp">
                <Chronometer android:id="@+id/live_clock" android:layout_width="wrap_content" android:layout_height="wrap_content"
                    android:textColor="#111111" android:textSize="32sp" android:textStyle="bold" android:fontFamily="monospace"/>
                <TextView android:id="@+id/live_clock_text" android:layout_width="wrap_content" android:layout_height="wrap_content"
                    android:textColor="#111111" android:textSize="22sp" android:textStyle="bold" android:visibility="gone"/>
                <TextView android:id="@+id/live_left" android:layout_width="wrap_content" android:layout_height="wrap_content"
                    android:textColor="#5A4A00" android:textSize="12sp" android:textStyle="bold"
                    android:layout_marginStart="6dp" android:layout_marginBottom="6dp"/>
            </LinearLayout>
        </LinearLayout>
        <ImageView android:id="@+id/live_face" android:layout_width="56dp" android:layout_height="56dp"
            android:background="@drawable/inpace_live_face" android:padding="5dp" android:scaleType="fitCenter"
            android:contentDescription="Tempo"/>
    </LinearLayout>
    <LinearLayout android:id="@+id/live_phase_row" android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:orientation="horizontal" android:gravity="center_vertical" android:background="@drawable/inpace_live_pill"
        android:paddingStart="12dp" android:paddingEnd="12dp" android:paddingTop="4dp" android:paddingBottom="4dp"
        android:layout_marginTop="6dp">
        <TextView android:id="@+id/live_phase" android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:textColor="#FFFFFF" android:textSize="13sp" android:textStyle="bold" android:maxLines="1"/>
        <Chronometer android:id="@+id/live_phase_clock" android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:textColor="#FFD43B" android:textSize="14sp" android:textStyle="bold" android:fontFamily="monospace"
            android:layout_marginStart="8dp"/>
        <TextView android:id="@+id/live_phase_text" android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:textColor="#FFD43B" android:textSize="13sp" android:textStyle="bold" android:layout_marginStart="8dp"
            android:visibility="gone"/>
    </LinearLayout>
    <ProgressBar android:id="@+id/live_bar" style="?android:attr/progressBarStyleHorizontal"
        android:layout_width="match_parent" android:layout_height="8dp" android:layout_marginTop="10dp"
        android:max="100" android:progressTint="#111111" android:progressBackgroundTint="#8A7300"/>
    <TextView android:id="@+id/live_body" android:layout_width="match_parent" android:layout_height="wrap_content"
        android:textColor="#2B2400" android:textSize="13sp" android:textStyle="bold" android:layout_marginTop="8dp"
        android:maxLines="2" android:ellipsize="end"/>
    <LinearLayout android:id="@+id/live_btns" android:layout_width="match_parent" android:layout_height="wrap_content"
        android:orientation="horizontal" android:layout_marginTop="10dp">
        <TextView android:id="@+id/live_btn1" android:layout_width="0dp" android:layout_height="38dp" android:layout_weight="1"
            android:gravity="center" android:background="@drawable/inpace_live_btn_dark" android:textColor="#FFFFFF"
            android:textSize="14sp" android:textStyle="bold"/>
        <TextView android:id="@+id/live_btn2" android:layout_width="0dp" android:layout_height="38dp" android:layout_weight="1"
            android:gravity="center" android:background="@drawable/inpace_live_btn_light" android:textColor="#111111"
            android:textSize="14sp" android:textStyle="bold" android:layout_marginStart="8dp"/>
    </LinearLayout>
</LinearLayout>
""", encoding="utf-8")

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
