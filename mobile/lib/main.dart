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

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    await Reminders.init();
  } catch (_) {} // inPace still works without notifications
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
  static Map<String, dynamic> labels = {};
  static String? pendingPage; // a page to open, from a tapped notification
  static void Function(String page)? onOpen;
  static void Function(String text)? onToast;

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
      ),
    );
  }

  static Future<void> _at(int id, DateTime when, String title, String body, String kind, String url,
      {String picture = '', bool exact = false}) async {
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

  static Future<void> sync(Map<String, dynamic> plan) async {
    labels = Map<String, dynamic>.from((plan['labels'] as Map?) ?? {});
    for (final p in await plugin.pendingNotificationRequests()) {
      if (p.id < testId) await plugin.cancel(id: p.id);
    }
    final now = DateTime.now();
    var id = 1;
    for (final raw in (plan['reminders'] as List? ?? const [])) {
      final r = raw as Map<String, dynamic>;
      final hm = (r['time'] as String).split(':');
      final days = (r['days'] as List).cast<int>(); // 0 = Monday
      for (var i = 0; i < 28 && id < 400; i++) {
        final when = DateTime(now.year, now.month, now.day + i, int.parse(hm[0]), int.parse(hm[1]));
        if (!when.isAfter(now) || !days.contains(when.weekday - 1)) continue;
        await _at(id++, when, r['title'] as String, r['body'] as String, r['kind'] as String, r['url'] as String,
            picture: (r['picture'] as String?) ?? '');
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

class _ShellState extends State<Shell> {
  WebViewController? _web;
  late int _port;
  String? _problem;
  String? _pendingLink;
  StreamSubscription<Uri>? _links;
  Widget? _fullScreen; // a video playing full screen

  String get _base => 'http://127.0.0.1:$_port/';

  @override
  void initState() {
    super.initState();
    _start();
  }

  @override
  void dispose() {
    _links?.cancel();
    super.dispose();
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
      _port = await _freePort();
      // Python runs on its own thread for as long as the app is open.
      SeriousPython.run(
        appFileName: 'main.py',
        environmentVariables: {
          'INPACE_HOME': '${data.path}/inPace',
          'INPACE_PORT': '$_port',
          'INPACE_MOBILE': 'android',
          // Python on a phone often thinks it is in London. Tell it the real clock.
          'INPACE_TZ_MINUTES': '${DateTime.now().timeZoneOffset.inMinutes}',
        },
        sync: false,
      );
      await _waitUntilUp();
      _listenForLinks();
      final fromNotification = Reminders.takePending();
      if (fromNotification != null) _pendingLink = fromNotification.replaceFirst(RegExp(r'^/'), '');
      Reminders.onOpen = (page) => _openPage(page.replaceFirst(RegExp(r'^/'), ''));
      Reminders.onToast = _toast;
      _openWebView();
    } catch (e) {
      setState(() => _problem = '$e');
    }
  }

  Future<void> _waitUntilUp() async {
    final deadline = DateTime.now().add(const Duration(seconds: 60));
    while (DateTime.now().isBefore(deadline)) {
      try {
        final r = await http.get(Uri.parse('${_base}ping')).timeout(const Duration(seconds: 2));
        if (r.statusCode == 200) return;
      } catch (_) {}
      await Future.delayed(const Duration(milliseconds: 300));
    }
    throw Exception('inPace took too long to start.');
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
    if (_web == null) {
      _pendingLink = path;
    } else {
      _web!.loadRequest(Uri.parse(_base + path));
    }
  }

  void _openPage(String path) {
    if (_web == null) {
      _pendingLink = path;
    } else {
      _web!.loadRequest(Uri.parse(_base + path));
    }
  }

  bool _isOurs(String url) => url.startsWith(_base);

  void _openWebView() {
    final params = const PlatformWebViewControllerCreationParams();
    final controller = WebViewController.fromPlatformCreationParams(params)
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFFF7F3EA))
      ..setNavigationDelegate(NavigationDelegate(
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
    controller.loadRequest(Uri.parse(_base + (_pendingLink ?? '')));
    setState(() => _web = controller);
  }

  // ---- Messages from the page (see app.js, "Android app") -------------------------------------------
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
    if (web != null && await web.canGoBack()) {
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
          child: Padding(
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
    final web = _web;
    if (web == null) {
      return const Scaffold(
        backgroundColor: Color(0xFFFFD43B),
        body: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('inPace', style: TextStyle(fontSize: 40, fontWeight: FontWeight.w800, color: Color(0xFF111111))),
            SizedBox(height: 16),
            CircularProgressIndicator(color: Color(0xFF111111)),
          ]),
        ),
      );
    }
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (await _goBack()) SystemNavigator.pop();
      },
      child: Scaffold(
        body: _fullScreen != null
            ? ColoredBox(color: Colors.black, child: _fullScreen!)
            : SafeArea(child: WebViewWidget(controller: web)),
      ),
    );
  }
}
