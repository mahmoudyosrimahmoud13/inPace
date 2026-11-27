// inPace for Android.
//
// The phone runs the same inPace app as the desktop: Python starts a small web server that only this phone can
// reach (127.0.0.1), and this Flutter shell shows it full screen. Links to other apps (Telegram, WhatsApp,
// email, the browser) open those apps, and inpace:// links open the right screen inside inPace.
// Reminders, alarms and Tempo's nudges are scheduled here as Android notifications, from the plan the page
// sends (see Reminders below and inpace/reminders.py), so they arrive even when inPace is closed.

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:app_links/app_links.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_file_dialog/flutter_file_dialog.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:serious_python/serious_python.dart';
import 'package:share_plus/share_plus.dart';
import 'package:timezone/timezone.dart' as tz;
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import 'package:webview_flutter_platform_interface/webview_flutter_platform_interface.dart'
    show WebViewPermissionResourceType;

// How long inPace takes to start: from here to "Python answers" and to "the first page is drawn" (shown in
// Settings, so it can be checked on a real phone without any tools).
final Stopwatch startClock = Stopwatch();

Future<void> main() async {
  startClock.start();
  WidgetsFlutterBinding.ensureInitialized();
  // Notifications get ready while the splash screen is already showing (the app used to wait for them first).
  // inPace still works without notifications.
  Reminders.ready = Reminders.init().catchError((_) {});
  runApp(const InPaceApp());
}

// ---- Reminders, alarms and Tempo's nudges ------------------------------------------------------------------
// The page sends a plan (inpace/reminders.py: plan()); every reminder time in the next 4 weeks and every
// automatic nudge becomes a scheduled Android notification. The page sends the plan again whenever inPace is
// used, so the schedule always matches your latest progress.
class Reminders {
  static final plugin = FlutterLocalNotificationsPlugin();
  static const snoozeId = 900000; // snoozed alarms: a new plan never removes them
  static const testId = 899999;
  static const tripId = 850001; // the focus trip's countdown, shown while a trip runs
  static const tripDoneId = 850002; // "your plant is ready", at the trip's last second
  static const tripNextId = 850003; // a sprint's next breaks and blocks (850003 to 850006), scheduled ahead
  static const sprintId = 850007; // today's sprint window: a yellow card with the countdown (v1.37)
  static const updateId = 850008; // the update downloading (v1.37)
  static const downloadsId = 850010; // downloads in progress (a foreground service, so Android lets them finish)
  static const downloadsDoneId = 850011; // "Downloads finished"
  static void Function()? onDownloadsStop;
  static String _tripKey = '';
  static String _sprintKey = '';
  static Timer? _sprintTick; // redraws the sprint card's progress bar every minute while the app lives
  // The sprint and timer card (v1.37.3) is drawn by MainActivity with its own layout: Android 12+ ignores an app's
  // colors on ordinary notifications. When the sprint timer runs, it's part of the sprint card (one card, not two).
  static const _native = MethodChannel('inpace/pip');
  static bool _nativeOk = true;
  static Map<String, dynamic>? _liveTrip; // the running or paused timer or focus trip
  static Map<String, dynamic>? _liveSprint; // today's open sprint window
  static Timer? _phaseEnd; // when a block or break ends, ask inPace what runs next
  static Future<void> Function()? onRefresh; // set by the app: fetch the timer and the sprint again
  // inPace's sun yellow: every notification carries it, and the live ones (timer, sprint, downloads) are painted with it.
  static const sun = Color(0xFFFFD43B);
  static Map<String, dynamic> labels = {};
  static String? pendingPage; // a page to open, from a tapped notification
  static Future<void> ready = Future.value(); // done once init() has finished (or failed)
  static void Function(String page)? onOpen;
  static void Function(String text)? onToast;
  static void Function(String action)? onTimerAction; // 'pause', 'resume' or 'stop'

  // The buttons on the focus timer's notification (the words come from the page, in your language).
  static List<AndroidNotificationAction>? _timerActions(Map<String, dynamic> t, bool running) {
    if (t['actions'] != true) return null;
    return <AndroidNotificationAction>[
      running
          ? AndroidNotificationAction('timer_pause', (t['l_pause'] as String?) ?? 'Pause', showsUserInterface: true)
          : AndroidNotificationAction('timer_resume', (t['l_resume'] as String?) ?? 'Go on', showsUserInterface: true),
      AndroidNotificationAction('timer_stop', (t['l_stop'] as String?) ?? 'Stop', showsUserInterface: true, cancelNotification: true),
    ];
  }

  static Future<bool> showCard(Map<String, dynamic> a) => _drawNative(a);

  static Future<bool> _drawNative(Map<String, dynamic> a) async {
    if (!_nativeOk) return false;
    try {
      return (await _native.invokeMethod<bool>('live', a)) == true;
    } on MissingPluginException {
      _nativeOk = false;
      return false;
    } catch (_) {
      return false;
    }
  }

  static String _mmss(Object? seconds) {
    final s = ((seconds as num?) ?? 0).toInt().clamp(0, 359999);
    final h = s ~/ 3600, m = (s % 3600) ~/ 60, r = s % 60;
    String two(int x) => x.toString().padLeft(2, '0');
    return h > 0 ? '$h:${two(m)}:${two(r)}' : '${two(m)}:${two(r)}';
  }

  static List<List<String>> _liveActions(Map<String, dynamic> t, bool running) {
    if (t['actions'] != true) return [];
    return [
      running ? ['pause', (t['l_pause'] as String?) ?? 'Pause'] : ['resume', (t['l_resume'] as String?) ?? 'Go on'],
      ['stop', (t['l_stop'] as String?) ?? 'Stop'],
    ];
  }

  static Map<String, dynamic> _sprintCard(Map<String, dynamic> sp, Map<String, dynamic>? t) {
    final start = ((sp['start_ms'] as num?) ?? 0).toInt();
    final end = ((sp['end_ms'] as num?) ?? 0).toInt();
    final now = DateTime.now().millisecondsSinceEpoch;
    final pct = (((now - start) * 100) ~/ (end - start).clamp(1, 1 << 40)).clamp(0, 100);
    final running = t != null && t['state'] == 'running';
    final stopped = sp['stopped'] == true && t == null;
    return {
      'id': sprintId,
      'channel': (sp['live_channel'] as String?) ?? 'Sprint and timer',
      'kicker': '${sp['l_sprint'] ?? 'Sprint'} · ${sp['head'] ?? ''}',
      'title': (sp['title'] as String?) ?? '',
      'ends_ms': end,
      'clock_label': (sp['l_left'] as String?) ?? '',
      'progress': pct,
      'body': stopped ? ((sp['stopped_body'] as String?) ?? '') : ((sp['body'] as String?) ?? ''),
      'face': (stopped || (t != null && !running)) ? 'tempo_sleepy' : 'tempo_read',
      'url': (sp['url'] as String?) ?? '/',
      'ongoing': true,
      'timeout_ms': end - now,
      if (t != null) 'phase': running ? ((t['short'] as String?) ?? '') : ((t['l_paused'] as String?) ?? 'Paused'),
      if (running) 'phase_ends_ms': t!['ends_ms'],
      if (t != null && !running) 'phase_text': _mmss(t['left_s']),
      'actions': t == null ? <List<String>>[] : _liveActions(t, running),
    };
  }

  static Map<String, dynamic> _timerCard(Map<String, dynamic> t) {
    final running = t['state'] == 'running';
    final now = DateTime.now().millisecondsSinceEpoch;
    final ends = (t['ends_ms'] as num?)?.toInt();
    final goal = ((t['goal'] as num?) ?? 0).toInt() * 60000;
    final pct = (running && ends != null && goal > 0) ? (100 - ((ends - now) * 100 ~/ goal)).clamp(0, 100) : -1;
    return {
      'id': tripId,
      'channel': (t['live_channel'] as String?) ?? 'Sprint and timer',
      'kicker': (t['channel'] as String?) ?? 'inPace',
      'title': running ? ((t['title'] as String?) ?? '') : ((t['paused_title'] as String?) ?? ''),
      'ends_ms': running ? ends : null,
      'clock_text': _mmss(t['left_s']),
      'clock_label': '',
      'progress': pct,
      'body': running ? ((t['body'] as String?) ?? '') : ((t['paused_body'] as String?) ?? ''),
      'face': running ? 'tempo_read' : 'tempo_sleepy',
      'url': (t['url'] as String?) ?? '/island/trip',
      'ongoing': running,
      'timeout_ms': (running && ends != null) ? ends - now : 0,
      'actions': _liveActions(t, running),
    };
  }

  // Draw both cards from what we know now. False when the app's own layout isn't available (then the plain
  // notifications below are used, as before).
  static Future<bool> _renderLive() async {
    final t = _liveTrip;
    final sp = _liveSprint;
    final now = DateTime.now().millisecondsSinceEpoch;
    final spOpen = sp != null && ((sp['end_ms'] as num?) ?? 0) > now;
    final merged = spOpen && t != null && t['sprint'] == true;
    if (spOpen) {
      if (!await _drawNative(_sprintCard(sp!, merged ? t : null))) return false;
    } else if (!await _drawNative({'id': sprintId, 'cancel': true})) {
      return false;
    }
    if (t != null && !merged) return _drawNative(_timerCard(t));
    return _drawNative({'id': tripId, 'cancel': true});
  }

  static AndroidFlutterLocalNotificationsPlugin? get android =>
      plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();

  static Future<void> init() async {
    await plugin.initialize(
      settings: const InitializationSettings(android: AndroidInitializationSettings('ic_stat_inpace')),
      onDidReceiveNotificationResponse: _tapped,
    );
    final launch = await plugin.getNotificationAppLaunchDetails();
    final response = launch?.notificationResponse;
    if (launch != null && launch.didNotificationLaunchApp && response != null) _tapped(response);
  }

  static void _tapped(NotificationResponse r) {
    Map<String, dynamic> data = {};
    try {
      if (r.payload != null) data = jsonDecode(r.payload!) as Map<String, dynamic>;
    } catch (_) {}
    if (r.actionId == 'stop') return;
    // Pause, Go on and Stop on the focus timer's notification: the app tells inPace, then the page updates it.
    if (r.actionId != null && r.actionId!.startsWith('timer_')) {
      onTimerAction?.call(r.actionId!.substring(6));
      return;
    }
    if (r.actionId == 'dl_stop') {
      onDownloadsStop?.call();
      return;
    }
    if (r.actionId == 'snooze') {
      _snooze(data);
      onToast?.call((labels['snoozed'] as String?) ?? 'Snoozed for 10 minutes.');
      return;
    }
    final page = (data['url'] as String?) ?? '/';
    if (onOpen != null) {
      onOpen!(page);
    } else {
      pendingPage = page;
    }
  }

  static String? takePending() {
    final p = pendingPage;
    pendingPage = null;
    return p;
  }

  static NotificationDetails _details(String kind, String body, [String picture = '']) {
    final style = BigTextStyleInformation(body);
    // Tempo's face (or the villain) as the big picture. The PNGs live in mobile/icon/res/drawable-nodpi.
    final face = picture.isEmpty ? null : DrawableResourceAndroidBitmap(picture);
    if (kind == 'alarm') {
      return NotificationDetails(
        android: AndroidNotificationDetails(
          'inpace_alarms', (labels['alarms'] as String?) ?? 'Alarms',
          importance: Importance.max,
          priority: Priority.max,
          category: AndroidNotificationCategory.alarm,
          fullScreenIntent: true,
          audioAttributesUsage: AudioAttributesUsage.alarm,
          sound: const UriAndroidNotificationSound('content://settings/system/alarm_alert'),
          additionalFlags: Int32List.fromList(<int>[4]), // FLAG_INSISTENT: keeps ringing until you act
          timeoutAfter: 10 * 60 * 1000,
          styleInformation: style,
          largeIcon: face,
          color: sun,
          actions: <AndroidNotificationAction>[
            AndroidNotificationAction('snooze', (labels['snooze'] as String?) ?? 'Snooze 10 min',
                showsUserInterface: true, cancelNotification: true),
            AndroidNotificationAction('stop', (labels['stop'] as String?) ?? 'Stop', cancelNotification: true),
          ],
        ),
      );
    }
    final tempo = kind == 'tempo';
    return NotificationDetails(
      android: AndroidNotificationDetails(
        tempo ? 'inpace_tempo' : 'inpace_reminders',
        tempo ? ((labels['tempo'] as String?) ?? 'Tempo') : ((labels['channel'] as String?) ?? 'Reminders'),
        importance: tempo ? Importance.defaultImportance : Importance.high,
        priority: tempo ? Priority.defaultPriority : Priority.high,
        category: AndroidNotificationCategory.reminder,
        styleInformation: style,
        largeIcon: face,
        color: sun,
      ),
    );
  }

  // A reminder, one of Tempo's nudges or an alarm as inPace's own card (v1.37.3): yellow like the app, Tempo's
  // face, and Open (or Snooze and Stop for an alarm). Android 12+ would draw a plain grey card otherwise.
  static Map<String, dynamic> _card(int id, String title, String body, String kind, String url, String picture) {
    final k = kind == 'alarm' ? 'alarm' : (kind == 'tempo' ? 'tempo' : 'reminder');
    return {
      'id': id,
      'kind': k,
      'channel': k == 'alarm'
          ? ((labels['alarms'] as String?) ?? 'Alarms')
          : k == 'tempo' ? ((labels['tempo'] as String?) ?? 'Tempo') : ((labels['channel'] as String?) ?? 'Reminders'),
      'kicker': k == 'alarm'
          ? ((labels['k_alarm'] as String?) ?? 'Alarm')
          : k == 'tempo' ? ((labels['tempo'] as String?) ?? 'Tempo') : ((labels['k_reminder'] as String?) ?? 'Reminder'),
      'title': title,
      'body': body,
      'face': picture.isEmpty ? 'tempo_wave' : picture,
      'url': url,
      'actions': k == 'alarm'
          ? [
              ['snooze', (labels['snooze'] as String?) ?? 'Snooze 10 min'],
              ['dismiss', (labels['stop'] as String?) ?? 'Stop'],
            ]
          : [
              ['open', (labels['open'] as String?) ?? 'Start studying'],
            ],
    };
  }

  static Future<bool> _nativeCall(String method, Object? args) async {
    if (!_nativeOk) return false;
    try {
      return (await _native.invokeMethod<bool>(method, args)) == true;
    } on MissingPluginException {
      _nativeOk = false;
      return false;
    } catch (_) {
      return false;
    }
  }

  // Cancel a scheduled or shown notification, wherever it was made.
  static Future<void> _cancel(int id) async {
    try { await plugin.cancel(id: id); } catch (_) {}
    await _nativeCall('unschedule', [id]);
  }

  static Future<void> _at(int id, DateTime when, String title, String body, String kind, String url,
      {String picture = '', bool exact = false}) async {
    if (await _nativeCall('schedule', {..._card(id, title, body, kind, url, picture), 'at_ms': when.millisecondsSinceEpoch})) {
      return;
    }
    final at = tz.TZDateTime.from(when, tz.UTC);
    final payload = jsonEncode({'url': url, 'title': title, 'body': body, 'kind': kind, 'picture': picture});
    final mode = kind == 'alarm'
        ? AndroidScheduleMode.alarmClock
        : kind == 'tempo' && !exact
            ? AndroidScheduleMode.inexactAllowWhileIdle
            : AndroidScheduleMode.exactAllowWhileIdle;
    try {
      await plugin.zonedSchedule(id: id, scheduledDate: at, notificationDetails: _details(kind, body, picture),
          androidScheduleMode: mode, title: title, body: body, payload: payload);
    } catch (_) {
      // Not allowed to use exact times on this phone: a few minutes late is better than nothing.
      await plugin.zonedSchedule(id: id, scheduledDate: at, notificationDetails: _details(kind, body, picture),
          androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle, title: title, body: body, payload: payload);
    }
  }

  static DateTime _onOrAfter(DateTime after, int hour, int minute, DateTime now) {
    final from = after.isAfter(now) ? after : now;
    var when = DateTime(from.year, from.month, from.day, hour, minute);
    if (!when.isAfter(from)) when = DateTime(from.year, from.month, from.day + 1, hour, minute);
    return when;
  }

  static String _planKey = '';
  static DateTime _planAt = DateTime.fromMillisecondsSinceEpoch(0);

  static Future<void> sync(Map<String, dynamic> plan) async {
    labels = Map<String, dynamic>.from((plan['labels'] as Map?) ?? {});
    // The same plan as last time, scheduled less than a day ago: nothing to do (v1.37.1). Scheduling runs on the
    // phone's screen thread, so doing it only when something changed keeps the app smooth.
    final key = jsonEncode(plan);
    if (key == _planKey && DateTime.now().difference(_planAt).inHours < 24) return;
    _planKey = key;
    _planAt = DateTime.now();
    for (final p in await plugin.pendingNotificationRequests()) {
      if (p.id < tripId) await plugin.cancel(id: p.id); // the trip and the test have their own, kept
    }
    await _nativeCall('unscheduleBelow', tripId);
    final now = DateTime.now();
    var id = 1;
    for (final raw in (plan['reminders'] as List? ?? const [])) {
      final r = raw as Map<String, dynamic>;
      final hm = (r['time'] as String).split(':');
      final days = (r['days'] as List).cast<int>(); // 0 = Monday
      final every = (r['every'] as num?)?.toInt() ?? 1; // "Other": every few days from its first day
      final start = DateTime.tryParse((r['start'] as String?) ?? '');
      // Two weeks ahead is plenty: the plan is sent again every half hour of use (v1.37.1: was four weeks and up
      // to 400 alarms, which took a slow phone a long time at every start).
      for (var i = 0; i < (every > 1 ? 31 : 14) && id < 150; i++) {
        final when = DateTime(now.year, now.month, now.day + i, int.parse(hm[0]), int.parse(hm[1]));
        if (!when.isAfter(now)) continue;
        if (every > 1) {
          if (start == null) continue;
          final gap = DateTime.utc(when.year, when.month, when.day).difference(DateTime.utc(start.year, start.month, start.day)).inDays;
          if (gap < 0 || gap % every != 0) continue;
        } else if (!days.contains(when.weekday - 1)) {
          continue;
        }
        await _at(id++, when, r['title'] as String, r['body'] as String, r['kind'] as String, r['url'] as String,
            picture: (r['picture'] as String?) ?? '');
        await Future<void>.delayed(const Duration(milliseconds: 15)); // let the screen breathe between alarms
      }
    }
    final evening = ((plan['evening'] as String?) ?? '18:30').split(':');
    for (final raw in (plan['auto'] as List? ?? const [])) {
      final a = raw as Map<String, dynamic>;
      final after = DateTime.parse(a['after'] as String).toLocal();
      final exact = a['exact'] == true; // a focus trip ends at its own minute, not in the evening
      if (exact && !after.isAfter(now)) continue;
      final when = exact ? after : _onOrAfter(after, int.parse(evening[0]), int.parse(evening[1]), now);
      await _at(id++, when, a['title'] as String, a['body'] as String, 'tempo', a['url'] as String,
          picture: (a['picture'] as String?) ?? '', exact: exact);
    }
  }

  // The focus trip in a notification: Tempo and a countdown that Android keeps running by itself, so it
  // works while inPace is in the background or even closed. It disappears when the time is up, and
  // "your plant is ready" rings at that moment. In "Phone down" mode, leaving the trip pauses it instead.
  static Future<void> trip(Map<String, dynamic>? t) async {
    final state = t?['state'] as String?;
    final key = t == null ? '' : '${t['id']}|$state|${t['ends_ms']}';
    if (key == _tripKey) return;
    _tripKey = key;
    try {
      for (var i = 0; i < 4; i++) {
        await _cancel(tripNextId + i); // a sprint's alerts are scheduled again below, if it still runs
      }
      _phaseEnd?.cancel();
      if (t == null || (state != 'running' && state != 'paused')) {
        _liveTrip = null;
        await plugin.cancel(id: tripId);
        await _cancel(tripDoneId);
        await _renderLive();
        return;
      }
      _liveTrip = t;
      final channel = (t['channel'] as String?) ?? 'Focus trip';
      final payload = jsonEncode({'url': (t['url'] as String?) ?? '/island/trip'});
      if (state == 'paused') {
        await _cancel(tripDoneId);
        if (await _renderLive()) return;
        final body = (t['paused_body'] as String?) ?? '';
        await plugin.show(id: tripId, title: t['paused_title'] as String?, body: body, payload: payload,
            notificationDetails: NotificationDetails(android: AndroidNotificationDetails('inpace_live', (t['live_channel'] as String?) ?? channel,
                importance: Importance.defaultImportance, priority: Priority.defaultPriority, onlyAlertOnce: true,
                playSound: false, enableVibration: false,
                category: AndroidNotificationCategory.progress, styleInformation: BigTextStyleInformation(body),
                color: sun, colorized: true,
                actions: _timerActions(t, false),
                largeIcon: const DrawableResourceAndroidBitmap('tempo_sleepy'))));
        return;
      }
      final ends = DateTime.fromMillisecondsSinceEpoch((t['ends_ms'] as num).toInt());
      final left = ends.difference(DateTime.now());
      if (left.inSeconds <= 0) {
        _liveTrip = null;
        await plugin.cancel(id: tripId);
        await _renderLive();
        return;
      }
      // When this block or break ends, ask inPace what runs next, so the card moves on by itself.
      _phaseEnd = Timer(left + const Duration(seconds: 3), () => onRefresh?.call());
      final body = (t['body'] as String?) ?? '';
      if (!await _renderLive()) await plugin.show(id: tripId, title: t['title'] as String?, body: body, payload: payload,
          notificationDetails: NotificationDetails(android: AndroidNotificationDetails('inpace_live', (t['live_channel'] as String?) ?? channel,
              importance: Importance.defaultImportance, priority: Priority.defaultPriority, onlyAlertOnce: true,
              playSound: false, enableVibration: false,
              ongoing: true, autoCancel: false,
              showWhen: true, when: ends.millisecondsSinceEpoch, usesChronometer: true, chronometerCountDown: true,
              timeoutAfter: left.inMilliseconds, // gone when the time is up
              category: AndroidNotificationCategory.progress, styleInformation: BigTextStyleInformation(body),
              color: sun, colorized: true,
              actions: _timerActions(t, true),
              largeIcon: const DrawableResourceAndroidBitmap('tempo_read'))));
      await _at(tripDoneId, ends, (t['done_title'] as String?) ?? '', (t['done_body'] as String?) ?? '', 'tempo',
          (t['url'] as String?) ?? '/island/trip', picture: 'tempo_cheer', exact: true);
      // A sprint day: "back to focus" and "break time" for the next blocks, even if inPace stays closed.
      final next = t['next'];
      if (next is List) {
        var i = 0;
        for (final n in next.take(4)) {
          if (n is! Map) continue;
          final at = DateTime.fromMillisecondsSinceEpoch(((n['at_ms'] as num?) ?? 0).toInt());
          if (at.isAfter(DateTime.now())) {
            await _at(tripNextId + i, at, (n['title'] as String?) ?? '', (n['body'] as String?) ?? '', 'tempo',
                (t['url'] as String?) ?? '/', picture: (n['picture'] as String?) ?? 'tempo_wave', exact: true);
          }
          i++;
        }
      }
    } catch (_) {
      _tripKey = ''; // notifications not allowed (yet): try again on the next page
    }
  }

  // Today's sprint window (v1.37): one yellow card that stays while the window is open, with a countdown to
  // its end that Android keeps running by itself and a bar showing how far through the day you are. The
  // bar is redrawn every minute while inPace lives; when the window closes, the card goes by itself.
  static Future<void> sprint(Map<String, dynamic>? sp) async {
    final key = sp == null ? '' : '${sp['rid']}|${sp['end_ms']}|${sp['stopped']}|${sp['head']}';
    if (key == _sprintKey) return;
    _sprintKey = key;
    _sprintTick?.cancel();
    _sprintTick = null;
    try {
      if (sp == null) {
        _liveSprint = null;
        await plugin.cancel(id: sprintId);
        await _renderLive();
        return;
      }
      await _drawSprint(sp);
      _sprintTick = Timer.periodic(const Duration(minutes: 1), (_) => _drawSprint(sp));
    } catch (_) {
      _sprintKey = '';
    }
  }

  static Future<void> _drawSprint(Map<String, dynamic> sp) async {
    final start = ((sp['start_ms'] as num?) ?? 0).toInt();
    final end = ((sp['end_ms'] as num?) ?? 0).toInt();
    final now = DateTime.now().millisecondsSinceEpoch;
    if (end <= now) {
      _sprintTick?.cancel();
      _sprintTick = null;
      _liveSprint = null;
      await plugin.cancel(id: sprintId);
      await _renderLive();
      return;
    }
    _liveSprint = sp;
    if (await _renderLive()) return;
    final total = (end - start).clamp(1, 1 << 40);
    final pct = (((now - start) * 100) ~/ total).clamp(0, 100);
    final stopped = sp['stopped'] == true;
    final body = stopped ? ((sp['stopped_body'] as String?) ?? '') : ((sp['body'] as String?) ?? '');
    final title = '${sp['title'] ?? ''}${sp['head'] != null ? ' · ${sp['head']}' : ''}';
    try {
      await plugin.show(id: sprintId, title: title, body: body,
          payload: jsonEncode({'url': (sp['url'] as String?) ?? '/'}),
          notificationDetails: NotificationDetails(android: AndroidNotificationDetails(
              'inpace_live', (sp['live_channel'] as String?) ?? 'Sprint and timer',
              importance: Importance.defaultImportance, priority: Priority.defaultPriority, onlyAlertOnce: true,
              playSound: false, enableVibration: false,
              ongoing: true, autoCancel: false,
              showWhen: true, when: end, usesChronometer: true, chronometerCountDown: true,
              timeoutAfter: end - now,
              showProgress: true, maxProgress: 100, progress: pct,
              category: AndroidNotificationCategory.progress,
              styleInformation: BigTextStyleInformation(body, summaryText: sp['l_left'] as String?),
              color: sun, colorized: true,
              largeIcon: DrawableResourceAndroidBitmap(stopped ? 'tempo_sleepy' : 'tempo_read'))));
    } catch (_) {}
  }

  static Future<void> _snooze(Map<String, dynamic> data) async {
    await _at(snoozeId + DateTime.now().second, DateTime.now().add(const Duration(minutes: 10)),
        (data['title'] as String?) ?? 'inPace', (data['body'] as String?) ?? '', 'alarm', (data['url'] as String?) ?? '/',
        picture: (data['picture'] as String?) ?? '');
  }

  static Future<bool> enabled() async => (await android?.areNotificationsEnabled()) ?? false;

  static Future<bool> allow() async {
    await android?.requestNotificationsPermission();
    if ((await android?.canScheduleExactNotifications()) == false) await android?.requestExactAlarmsPermission();
    return enabled();
  }

  static Future<void> test(String kind, Map<String, dynamic> message, Map<String, dynamic> newLabels) async {
    labels = {...labels, ...newLabels};
    if (!await enabled() && !await allow()) return;
    final body = (message['body'] as String?) ?? '';
    if (await _drawNative(_card(testId, (message['title'] as String?) ?? '', body, kind == 'alarm' ? 'alarm' : 'notify',
        (message['url'] as String?) ?? '/', (message['picture'] as String?) ?? 'tempo_wave'))) {
      return;
    }
    await plugin.show(id: testId, title: message['title'] as String?, body: body,
        notificationDetails: _details(kind == 'alarm' ? 'alarm' : 'notify', body, (message['picture'] as String?) ?? 'tempo_wave'),
        payload: jsonEncode({...message, 'kind': kind}));
  }
}

class InPaceApp extends StatelessWidget {
  const InPaceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'inPace',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: const Color(0xFFFFD43B), useMaterial3: true),
      home: const Shell(),
    );
  }
}

class Shell extends StatefulWidget {
  const Shell({super.key});

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> with WidgetsBindingObserver {
  WebViewController? _web;
  // Picture-in-picture (floating over other apps): MainActivity.kt answers on this channel.
  static const _pip = MethodChannel('inpace/pip');
  late int _port;
  bool _ready = false; // Python answers
  bool _shown = false; // the first page is drawn: the splash fades out
  bool _splashGone = false;
  int? _pythonMs;
  String? _problem;
  String? _pendingLink;
  StreamSubscription<Uri>? _links;
  Widget? _fullScreen; // a video playing full screen
  bool _inPip = false; // floating over other apps (picture-in-picture)
  // The color under the page (and behind the status bar): the page's own color, so dark mode never flashes cream
  // between pages or while a long page scrolls. The page sends it (app.js); the last one is kept for next time.
  Color _bg = const Color(0xFFF7F3EA);
  File? _bgFile;
  final GlobalKey _webKey = GlobalKey(); // the page's view is never rebuilt from scratch

  String get _base => 'http://127.0.0.1:$_port/';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // The web view starts up (it loads the browser engine, which takes a moment) while Python starts.
    _web = _makeWebView();
    _pip.setMethodCallHandler((call) async {
      if (call.method == 'media') {
        // A button in the media controls: play, pause, back, fwd, prev, next or seek:<ms>.
        await _web?.runJavaScript('window.inpaceMediaControl && window.inpaceMediaControl(${jsonEncode(call.arguments)})');
      }
      if (call.method == 'open') {
        // the sprint or timer card was tapped while inPace was open
        final page = (call.arguments as String? ?? '/').replaceFirst(RegExp(r'^/'), '');
        if (_ready) {
          _openPage(page);
        } else {
          _pendingLink = page;
        }
      }
      if (call.method == 'timer') {
        Reminders.onTimerAction?.call(call.arguments as String? ?? '');
      }
      if (call.method == 'changed') {
        if (mounted) setState(() => _inPip = call.arguments == true);
        // The page shows only the video and the timer while it floats.
        await _web?.runJavaScript('window.inpacePip && window.inpacePip(${call.arguments == true})');
      }
      return null;
    });
    _start();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _links?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Back from Android's "allow installing apps" setting: open the install dialog for the waiting update.
    if (state == AppLifecycleState.resumed && _apkWaiting != null && !_updating) _install();
  }

  Future<int> _freePort() async {
    final socket = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
    final port = socket.port;
    await socket.close();
    return port;
  }

  Future<void> _start() async {
    try {
      final data = await getApplicationDocumentsDirectory();
      // The phone's shared storage (/storage/emulated/0), where Download and Movies are: offline YouTube lessons
      // are saved in Download/inPace/<course> so people can find and play them in other apps too.
      String storage = '/storage/emulated/0';
      try {
        final ext = await getExternalStorageDirectory();
        final i = ext?.path.indexOf('/Android/') ?? -1;
        if (ext != null && i > 0) storage = ext.path.substring(0, i);
      } catch (_) {}
      _port = await _freePort();
      // If Python fails while starting, main.py writes why to this file, and the error screen shows it.
      _errorFile = File('${data.path}/inPace/start-error.txt');
      _bgFile = File('${data.path}/inPace/window-bg.txt');
      _inspectFile = File('${data.path}/inPace/inspect-on.txt');
      try {  // "Allow inspecting over USB" from Settings, kept across starts
        if (await _inspectFile!.exists()) await AndroidWebViewController.enableDebugging(true);
      } catch (_) {}
      try {
        if (await _bgFile!.exists()) _setBg((await _bgFile!.readAsString()).trim(), save: false);
      } catch (_) {}
      try {
        if (await _errorFile!.exists()) await _errorFile!.delete();
      } catch (_) {}
      // Python runs on its own thread for as long as the app is open.
      // The build ships the plain main.py, exactly like 1.20 (1.21 and 1.22 shipped compiled-only code without it,
      // and Python couldn't start).
      SeriousPython.run(
        appFileName: 'main.py',
        environmentVariables: {
          'INPACE_HOME': '${data.path}/inPace',
          'INPACE_PORT': '$_port',
          'INPACE_MOBILE': 'android',
          'INPACE_STORAGE': storage,
          // Python on a phone often thinks it is in London. Tell it the real clock.
          'INPACE_TZ_MINUTES': '${DateTime.now().timeZoneOffset.inMinutes}',
        },
        sync: false,
      );
      await _waitUntilUp();
      _pythonMs = startClock.elapsedMilliseconds;
      _ready = true;
      _listenForLinks();
      await Reminders.ready;
      String? cardTimer;
      try {  // opened from the sprint or timer card (or one of its buttons) while inPace was closed
        final o = await _pip.invokeMethod<Map>('takeOpen');
        final url = o?['url'] as String?;
        if (url != null) _pendingLink = url.replaceFirst(RegExp(r'^/'), '');
        cardTimer = o?['timer'] as String?;
      } catch (_) {}
      Reminders.onRefresh = () async {
        try {
          final r = await http.get(Uri.parse('${_base}island/live.json')).timeout(const Duration(seconds: 6));
          final d = jsonDecode(r.body) as Map<String, dynamic>;
          await Reminders.trip(d['trip'] == null ? null : Map<String, dynamic>.from(d['trip'] as Map));
          await Reminders.sprint(d['sprint'] == null ? null : Map<String, dynamic>.from(d['sprint'] as Map));
        } catch (_) {}
      };
      final fromNotification = Reminders.takePending();
      if (fromNotification != null) _pendingLink = fromNotification.replaceFirst(RegExp(r'^/'), '');
      Reminders.onOpen = (page) => _openPage(page.replaceFirst(RegExp(r'^/'), ''));
      Reminders.onToast = _toast;
      Reminders.onTimerAction = (action) async {
        try {
          await http.post(Uri.parse('${_base}timer/$action'), headers: {'x-inpace-fetch': '1', 'accept': 'application/json'});
        } catch (_) {}
        // The page fetches the timer again and sends the notification its new state.
        await _web?.runJavaScript('window.inpaceTimer && window.inpaceTimer.refresh()');
        await Reminders.onRefresh?.call(); // and the card updates even if no page is open
      };
      if (cardTimer != null && cardTimer.isNotEmpty) Reminders.onTimerAction?.call(cardTimer);
      Reminders.onDownloadsStop = () async {
        try {
          await http.post(Uri.parse('${_base}downloads/stop'), headers: {'x-inpace-soft': '1'});
        } catch (_) {}
        _dlTick();
      };
      _web!.loadRequest(Uri.parse(_base + (_pendingLink ?? '')));
      _pendingLink = null;
      // If the first page never says it's finished (a very slow phone, an error), don't keep the splash forever.
      Future.delayed(const Duration(seconds: 8), () {
        if (mounted && !_shown) setState(() => _shown = true);
      });
    } catch (e) {
      setState(() => _problem = '$e');
    }
  }

  File? _errorFile;

  Future<String> _pythonError() async {
    try {
      final f = _errorFile;
      if (f != null && await f.exists()) {
        final text = (await f.readAsString()).trim();
        final lines = text.split('\n');
        return lines.length > 25 ? lines.sublist(lines.length - 25).join('\n') : text;
      }
    } catch (_) {}
    return '';
  }

  Future<void> _waitUntilUp() async {
    // A phone can be slow right after an update (the app unpacks itself first), so wait up to two minutes.
    final deadline = DateTime.now().add(const Duration(seconds: 120));
    while (DateTime.now().isBefore(deadline)) {
      try {
        final r = await http.get(Uri.parse('${_base}ping')).timeout(const Duration(seconds: 3));
        if (r.statusCode == 200) return;
      } catch (_) {}
      final why = await _pythonError();
      if (why.isNotEmpty) throw Exception('Python stopped while starting:\n$why');
      await Future.delayed(const Duration(milliseconds: 100));
    }
    final why = await _pythonError();
    throw Exception('inPace took too long to start.${why.isEmpty ? '' : '\n$why'}');
  }

  // inpace://open/<data> links from chats, email or the website.
  void _listenForLinks() {
    final appLinks = AppLinks();
    appLinks.getInitialLink().then((uri) {
      if (uri != null) _openLink(uri);
    });
    _links = appLinks.uriLinkStream.listen(_openLink);
  }

  void _openLink(Uri uri) {
    final text = uri.toString();
    final m = RegExp(r'(?:inpace://open/?|/open(?:\.html)?#)([A-Za-z0-9_-]{16,})').firstMatch(text);
    if (m == null) return;
    final path = 'link?d=${m.group(1)}';
    if (!_ready) {
      _pendingLink = path;
    } else {
      _web!.loadRequest(Uri.parse(_base + path));
    }
  }

  void _openPage(String path) {
    if (!_ready) {
      _pendingLink = path;
    } else {
      _web!.loadRequest(Uri.parse(_base + path));
    }
  }

  bool _isOurs(String url) => url.startsWith(_base);

  // Made once, at start; it loads the first page as soon as Python answers.
  WebViewController _makeWebView() {
    final params = const PlatformWebViewControllerCreationParams();
    final controller = WebViewController.fromPlatformCreationParams(params)
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(_bg)
      ..setNavigationDelegate(NavigationDelegate(
        onPageFinished: (_) {
          if (_shown || !_ready || !mounted) return;
          setState(() => _shown = true);
          _reportStartTime();
        },
        onNavigationRequest: (request) {
          if (_isOurs(request.url)) return NavigationDecision.navigate;
          // Telegram, WhatsApp, email, GitHub and every other link open in their own app.
          launchUrl(Uri.parse(request.url), mode: LaunchMode.externalApplication);
          return NavigationDecision.prevent;
        },
      ))
      ..addJavaScriptChannel('InPaceAndroid', onMessageReceived: (m) => _fromPage(m.message));
    final android = controller.platform;
    if (android is AndroidWebViewController) {
      android.setMediaPlaybackRequiresUserGesture(false);
      // Voice notes: ask Android for the microphone, then let the page use it.
      android.setOnPlatformPermissionRequest((request) async {
        final wantsMic = request.types.contains(WebViewPermissionResourceType.microphone);
        if (wantsMic && !(await Permission.microphone.request()).isGranted) {
          request.deny();
        } else {
          request.grant();
        }
      });
      // "Add a file" buttons: Android's file picker.
      android.setOnShowFileSelector(_pickFiles);
      // Videos can go full screen.
      android.setCustomWidgetCallbacks(
        onShowCustomWidget: (widget, onHidden) => setState(() => _fullScreen = widget),
        onHideCustomWidget: () => setState(() => _fullScreen = null),
      );
    }
    return controller;
  }

  Future<void> _reportStartTime() async {
    final page = startClock.elapsedMilliseconds;
    try {
      await http.post(Uri.parse('${_base}startup-time'), body: {'python': '${_pythonMs ?? page}', 'page': '$page'});
    } catch (_) {}
  }

  // ---- Messages from the page (see app.js, "Android app") -------------------------------------------
  // "#12110E" from the page: the web view, the screen behind it and the status bar take that color.
  void _setBg(String hex, {bool save = true}) {
    if (!RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(hex)) return;
    final color = Color(int.parse('FF${hex.substring(1)}', radix: 16));
    if (color == _bg) return;
    if (mounted) {
      setState(() => _bg = color);
    } else {
      _bg = color;
    }
    _web?.setBackgroundColor(color);
    if (save) {
      _bgFile?.writeAsString(hex).catchError((_) => _bgFile!);
    }
  }

  Future<void> _fromPage(String raw) async {
    final Map<String, dynamic> msg = jsonDecode(raw);
    switch (msg['type']) {
      case 'download':
        await _download(msg['url'] as String);
      case 'file':
        await _offerFile(msg['name'] as String, base64Decode(msg['data'] as String));
      case 'pickFolder':
        await _pickFolder(msg['target'] as String);
      case 'share':
        await Share.share(msg['text'] as String);
      case 'notifySync':
        await Reminders.sync(Map<String, dynamic>.from(msg['plan'] as Map));
      case 'trip':
        await Reminders.trip(msg['trip'] == null ? null : Map<String, dynamic>.from(msg['trip'] as Map));
      case 'sprint':
        await Reminders.sprint(msg['sprint'] == null ? null : Map<String, dynamic>.from(msg['sprint'] as Map));
      case 'update':
        await _update(msg['url'] as String, (msg['version'] as String?) ?? '');
      case 'media':
        // The lesson video in Android's media controls (MainActivity.kt makes the media session and notification).
        try { await _pip.invokeMethod('media', msg['state']); } catch (_) {}
      case 'pip':
        // Float over other apps when you leave inPace while a video plays or a timer runs (MainActivity.kt).
        try { await _pip.invokeMethod('auto', msg['auto'] == true); } catch (_) {}
      case 'downloads':
        _watchDownloads();
      case 'inspect':
        await _setInspect(msg['on'] == true);
      case 'bg':
        _setBg(msg['color'] as String? ?? '');
      case 'codenoteCheck':
        // Works with CodeNote: is an app there for codenote:// links? (Needs the <queries> entry in the manifest.)
        {
          bool has = false;
          try { has = await canLaunchUrl(Uri.parse('codenote://open/x')); } catch (_) {}
          await _web?.runJavaScript('window.inpaceCodeNote && window.inpaceCodeNote(${has ? 'true' : 'false'})');
        }
      case 'codenote':
        // Open the lesson in CodeNote (an ACTION_VIEW intent). No app for it after all: the web page instead.
        {
          bool opened = false;
          try { opened = await launchUrl(Uri.parse(msg['link'] as String), mode: LaunchMode.externalNonBrowserApplication); } catch (_) {}
          if (!opened) {
            try { await launchUrl(Uri.parse(msg['web'] as String), mode: LaunchMode.externalApplication); } catch (_) {}
          }
        }
      case 'notifyState':
        await _sendNotifyState();
      case 'notifyAllow':
        await Reminders.allow();
        await _sendNotifyState();
      case 'notifyTest':
        await Reminders.test(msg['kind'] as String, Map<String, dynamic>.from(msg['message'] as Map),
            Map<String, dynamic>.from((msg['labels'] as Map?) ?? {}));
    }
  }

  // ---- Downloads (v1.30.14): a notification with a progress bar while videos or courses download -------------
  // The page says when something starts downloading; from then the app asks inPace how it's going every second
  // and a half, also while you're in another app. While anything downloads, the notification belongs to a
  // foreground service, so Android doesn't close inPace in the middle. When everything is done, it says so.
  Timer? _dlTimer;
  bool _dlForeground = false;
  bool _dlBusy = false;

  void _watchDownloads() {
    if (_dlTimer != null) return;
    _dlTimer = Timer.periodic(const Duration(milliseconds: 1500), (_) => _dlTick());
    _dlTick();
  }

  Future<void> _dlTick() async {
    if (_dlBusy) return;
    _dlBusy = true;
    try {
      final r = await http.get(Uri.parse('${_base}downloads.json')).timeout(const Duration(seconds: 6));
      final o = jsonDecode(r.body) as Map<String, dynamic>;
      final n = Map<String, dynamic>.from((o['notice'] as Map?) ?? {});
      final channel = (n['channel'] as String?) ?? 'Downloads';
      final payload = jsonEncode({'url': '/downloads'});
      if (n['running'] == true) {
        final pct = ((n['percent'] as num?) ?? 0).toInt().clamp(0, 100);
        final stop = (n['stop'] as String?) ?? '';
        final details = AndroidNotificationDetails('inpace_downloads', channel,
            importance: Importance.low, priority: Priority.low, onlyAlertOnce: true, ongoing: true, autoCancel: false,
            showProgress: true, maxProgress: 100, progress: pct, indeterminate: pct == 0,
            category: AndroidNotificationCategory.progress, color: Reminders.sun, colorized: true,
            actions: stop.isEmpty ? null : <AndroidNotificationAction>[
              AndroidNotificationAction('dl_stop', stop, showsUserInterface: true, cancelNotification: false),
            ]);
        if (!_dlForeground) {
          _dlForeground = true;
          try {
            await Reminders.android?.startForegroundService(id: Reminders.downloadsId, title: n['title'] as String?,
                body: n['body'] as String?, notificationDetails: details, payload: payload,
                foregroundServiceTypes: {AndroidServiceForegroundType.foregroundServiceTypeDataSync});
          } catch (_) {}  // no foreground service on this phone: a plain notification still shows the progress
        }
        await Reminders.plugin.show(id: Reminders.downloadsId, title: n['title'] as String?, body: n['body'] as String?,
            notificationDetails: NotificationDetails(android: details), payload: payload);
      } else {
        _dlTimer?.cancel();
        _dlTimer = null;
        if (_dlForeground) {
          try { await Reminders.android?.stopForegroundService(); } catch (_) {}
          _dlForeground = false;
        }
        await Reminders.plugin.cancel(id: Reminders.downloadsId);
        if (((n['saved'] as num?) ?? 0) > 0 &&
            !await Reminders.showCard({'id': Reminders.downloadsDoneId, 'kind': 'tempo', 'channel': channel,
              'kicker': channel, 'title': (n['title'] as String?) ?? '', 'body': (n['body'] as String?) ?? '',
              'face': 'tempo_cheer', 'url': '/downloads', 'actions': []})) {
          await Reminders.plugin.show(id: Reminders.downloadsDoneId, title: n['title'] as String?, body: n['body'] as String?,
              payload: payload,
              notificationDetails: NotificationDetails(android: AndroidNotificationDetails('inpace_downloads', channel,
                  importance: Importance.defaultImportance, priority: Priority.defaultPriority,
                  styleInformation: BigTextStyleInformation((n['body'] as String?) ?? ''),
                  color: Reminders.sun,
                  largeIcon: const DrawableResourceAndroidBitmap('tempo_cheer'))));
        }
      }
    } catch (_) {
      // inPace is busy or restarting: the next tick tries again
    } finally {
      _dlBusy = false;
    }
  }

  Future<void> _sendNotifyState() async {
    final on = await Reminders.enabled();
    await _web?.runJavaScript('window.inpaceNotifyState && window.inpaceNotifyState(${jsonEncode({'enabled': on})})');
  }

  String _fileName(http.BaseResponse r, String url) {
    final cd = r.headers['content-disposition'] ?? '';
    final star = RegExp(r"filename\*=UTF-8''([^;]+)").firstMatch(cd);
    if (star != null) return Uri.decodeComponent(star.group(1)!);
    final plain = RegExp(r'filename="?([^";]+)"?').firstMatch(cd);
    if (plain != null) return plain.group(1)!;
    return Uri.parse(url).pathSegments.isNotEmpty ? Uri.decodeComponent(Uri.parse(url).pathSegments.last) : 'inPace file';
  }

  Future<File> _tempFile(String name) async {
    final dir = Directory('${(await getTemporaryDirectory()).path}/shared');
    await dir.create(recursive: true);
    final safe = name.replaceAll(RegExp(r'[\\/:*?"<>|]'), '_');
    return File('${dir.path}/$safe');
  }

  // Updates (v1.37): the new APK is downloaded to the app's own storage, with a yellow progress notification,
  // then Android's install dialog opens (MainActivity hands the file over). If Android doesn't allow inPace to
  // install apps yet, its setting opens first, and the dialog follows once you're back.
  bool _updating = false;
  String? _apkWaiting;

  Future<void> _update(String url, String version) async {
    if (_updating) return;
    _updating = true;
    _toast('Downloading inPace $version…');
    try {
      final dir = Directory('${(await getTemporaryDirectory()).path}/updates');
      await dir.create(recursive: true);
      for (final f in dir.listSync()) {
        try { await f.delete(); } catch (_) {}  // older downloads
      }
      final file = File('${dir.path}/inPace-${version.replaceAll(RegExp(r'[^0-9A-Za-z.]'), '_')}.apk');
      final client = http.Client();
      final resp = await client.send(http.Request('GET', Uri.parse(url)));
      if (resp.statusCode != 200) throw Exception('status ${resp.statusCode}');
      final total = resp.contentLength ?? 0;
      var got = 0;
      var lastPct = -1;
      final sink = file.openWrite();
      await for (final chunk in resp.stream) {
        sink.add(chunk);
        got += chunk.length;
        final pct = total > 0 ? (got * 100 ~/ total) : 0;
        if (pct != lastPct) {
          lastPct = pct;
          await _updateNotice(version, pct, total);
        }
      }
      await sink.close();
      client.close();
      await Reminders.plugin.cancel(id: Reminders.updateId);
      _apkWaiting = file.path;
      await _install();
    } catch (e) {
      await Reminders.plugin.cancel(id: Reminders.updateId);
      _toast("Couldn't download the update: $e");
    } finally {
      _updating = false;
    }
  }

  Future<void> _updateNotice(String version, int pct, int total) async {
    final mb = total > 0 ? ' · ${(total / 1048576).toStringAsFixed(0)} MB' : '';
    if (await Reminders.showCard({'id': Reminders.updateId, 'kind': 'live', 'kicker': 'inPace $version',
        'title': 'Downloading the update$mb', 'body': '', 'face': 'tempo_read', 'url': '/settings#updates',
        'progress': total > 0 ? pct : 0, 'ongoing': true, 'actions': []})) {
      return;
    }
    try {
      await Reminders.plugin.show(id: Reminders.updateId, title: 'inPace $version', body: 'Downloading the update$mb',
          notificationDetails: NotificationDetails(android: AndroidNotificationDetails('inpace_downloads', 'Downloads',
              importance: Importance.low, priority: Priority.low, onlyAlertOnce: true, ongoing: true, autoCancel: false,
              showProgress: true, maxProgress: 100, progress: pct, indeterminate: total == 0,
              category: AndroidNotificationCategory.progress, color: Reminders.sun, colorized: true,
              largeIcon: const DrawableResourceAndroidBitmap('tempo_read'))));
    } catch (_) {}
  }

  Future<void> _install() async {
    final path = _apkWaiting;
    if (path == null) return;
    try {
      final r = await _pip.invokeMethod<String>('install', path);
      if (r == 'ask') {
        _toast('Allow inPace to install updates, then come back.');
      } else {
        _apkWaiting = null;  // Android's install dialog is open
      }
    } catch (e) {
      _apkWaiting = null;
      _toast("Couldn't open the installer: $e");
    }
  }

  // Testing (v1.37.7): a computer on a USB cable (with USB debugging on) can inspect the pages in chrome://inspect.
  File? _inspectFile;
  Future<void> _setInspect(bool on) async {
    try {
      await AndroidWebViewController.enableDebugging(on);
      final f = _inspectFile;
      if (f != null) {
        if (on) {
          await f.create(recursive: true);
        } else if (await f.exists()) {
          await f.delete();
        }
      }
      _toast(on ? 'A computer on USB can inspect inPace now.' : 'Inspecting is off.');
    } catch (e) {
      _toast("Couldn't change it: $e");
    }
  }

  Future<void> _download(String url) async {
    _toast('Getting the file…');
    try {
      final client = http.Client();
      final resp = await client.send(http.Request('GET', Uri.parse(url)));
      if (resp.statusCode != 200) throw Exception('status ${resp.statusCode}');
      final file = await _tempFile(_fileName(resp, url));
      final sink = file.openWrite();
      await resp.stream.pipe(sink); // streamed, so big course files don't fill the memory
      client.close();
      await _offerSaved(file);
    } catch (e) {
      _toast("Couldn't get the file: $e");
    }
  }

  Future<void> _offerFile(String name, List<int> bytes) async {
    final file = await _tempFile(name);
    await file.writeAsBytes(bytes);
    await _offerSaved(file);
  }

  // Ask what to do with a file: send it (WhatsApp, Telegram, email, Drive…) or save it on the phone.
  Future<void> _offerSaved(File file) async {
    if (!mounted) return;
    final name = file.uri.pathSegments.last;
    final choice = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 6),
            child: Text(name, style: const TextStyle(fontWeight: FontWeight.bold), textAlign: TextAlign.center),
          ),
          ListTile(leading: const Icon(Icons.send), title: const Text('Send it (WhatsApp, Telegram, email…)'),
              onTap: () => Navigator.pop(ctx, 'share')),
          ListTile(leading: const Icon(Icons.save_alt), title: const Text('Save it on this phone'),
              onTap: () => Navigator.pop(ctx, 'save')),
        ]),
      ),
    );
    if (choice == 'share') {
      await Share.shareXFiles([XFile(file.path)], text: name);
    } else if (choice == 'save') {
      final saved = await FlutterFileDialog.saveFile(params: SaveFileDialogParams(sourceFilePath: file.path, fileName: name));
      if (saved != null) _toast('Saved.');
    }
  }

  Future<List<String>> _pickFiles(FileSelectorParams params) async {
    final result = await FilePicker.platform.pickFiles(allowMultiple: params.mode == FileSelectorMode.openMultiple);
    if (result == null) return [];
    return result.files.where((f) => f.path != null).map((f) => Uri.file(f.path!).toString()).toList();
  }

  // Course folders (for example a folder of videos) are read straight from the phone's storage,
  // which needs "All files access".
  Future<void> _pickFolder(String target) async {
    if (!(await Permission.manageExternalStorage.isGranted)) {
      final ok = await _ask(
          'Allow inPace to read your course folders?',
          'inPace reads course videos where they are, without copying them. Android calls this "All files access". '
              'inPace only reads the folders you choose.');
      if (!ok || !(await Permission.manageExternalStorage.request()).isGranted) {
        _toast('Without that permission, inPace can only use courses added from files.');
        return;
      }
    }
    final path = await FilePicker.platform.getDirectoryPath();
    if (path == null) return;
    await _web?.runJavaScript('window.inpaceFolderPicked(${jsonEncode(target)}, ${jsonEncode(path)})');
  }

  Future<bool> _ask(String title, String text) async {
    if (!mounted) return false;
    final r = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(text),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Not now')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Continue')),
        ],
      ),
    );
    return r ?? false;
  }

  void _toast(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<bool> _goBack() async {
    if (_fullScreen != null) {
      setState(() => _fullScreen = null);
      return false;
    }
    final web = _web;
    if (web == null) return true;
    // The page decides, like an app would (inpaceBack in app.js): close what's open, go one page back, leave a
    // main page for Home, and say "exit" only on Home. If the page can't answer, fall back to plain history.
    if (_ready) {
      try {
        const js = 'window.inpaceBack ? window.inpaceBack() : "none"';
        final Object result = await web.runJavaScriptReturningResult(js);
        final answer = result.toString().replaceAll('"', '');
        if (answer == 'handled') return false;
        if (answer == 'exit') return true;
      } catch (_) {}
    }
    if (await web.canGoBack()) {
      await web.goBack();
      return false;
    }
    return true;
  }

  @override
  Widget build(BuildContext context) {
    if (_problem != null) {
      return Scaffold(
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              const Text('inPace could not start', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              SelectableText(_problem!),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: () {
                  setState(() => _problem = null);
                  _start();
                },
                child: const Text('Try again'),
              ),
            ]),
          ),
        ),
      );
    }
    final web = _web!;
    // Light status bar icons on a dark page, dark ones on a light page, so the clock and battery stay readable.
    final dark = _bg.computeLuminance() < 0.4;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: (dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark).copyWith(
        statusBarColor: Colors.transparent,
        systemNavigationBarColor: _bg,
        systemNavigationBarIconBrightness: dark ? Brightness.light : Brightness.dark,
      ),
      child: PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (await _goBack()) SystemNavigator.pop();
      },
      child: Scaffold(
        backgroundColor: _bg,
        body: Stack(fit: StackFit.expand, children: [
          // The page's view keeps the same place in the layout when the floating window opens and closes (only
          // the edges change). Swapping its parent made Android take the page off the screen and put it back,
          // which stopped YouTube and left the page laid out at the floating window's small size.
          _fullScreen != null
              ? ColoredBox(color: Colors.black, child: _fullScreen!)
              : ColoredBox(
                  color: _inPip ? Colors.black : _bg,
                  child: SafeArea(
                    top: !_inPip, bottom: !_inPip, left: !_inPip, right: !_inPip, // floating: edge to edge
                    child: WebViewWidget(key: _webKey, controller: web),
                  ),
                ),
          // The splash stays on top until the first page is drawn, then fades away (no white flash).
          if (!_splashGone)
            IgnorePointer(
              ignoring: _shown,
              child: AnimatedOpacity(
                opacity: _shown ? 0 : 1,
                duration: const Duration(milliseconds: 260),
                curve: Curves.easeOut,
                onEnd: () {
                  if (_shown && mounted) setState(() => _splashGone = true);
                },
                child: const Splash(),
              ),
            ),
        ]),
      ),
      ),
    );
  }
}

// Tempo and the inPace logo on yellow, the same picture Android shows before Flutter starts, so the two
// screens join without a jump. A spinner under them shows that inPace is getting ready.
class Splash extends StatelessWidget {
  const Splash({super.key});

  @override
  Widget build(BuildContext context) {
    return const ColoredBox(
      color: Color(0xFFFFD43B),
      child: Stack(alignment: Alignment.center, children: [
        Image(image: AssetImage('assets/splash/splash.png'), width: 240, height: 240),
        Positioned.fill(
          child: Align(
            alignment: Alignment.center,
            child: Padding(
              padding: EdgeInsets.only(top: 330),
              child: SizedBox(
                width: 34,
                height: 34,
                child: CircularProgressIndicator(
                  strokeWidth: 3.5,
                  strokeCap: StrokeCap.round,
                  color: Color(0xFF111111),
                  backgroundColor: Color(0x22111111),
                ),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}
