// inPace for Android.
//
// The phone runs the same inPace app as the desktop: Python starts a small web server that only this phone can
// reach (127.0.0.1), and this Flutter shell shows it full screen. Links to other apps (Telegram, WhatsApp,
// email, the browser) open those apps, and inpace:// links open the right screen inside inPace.

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:app_links/app_links.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_file_dialog/flutter_file_dialog.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:serious_python/serious_python.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import 'package:webview_flutter_platform_interface/webview_flutter_platform_interface.dart'
    show WebViewPermissionResourceType;

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const InPaceApp());
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
        },
        sync: false,
      );
      await _waitUntilUp();
      _listenForLinks();
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
    }
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
