// inPace for Android.
//
// The phone runs the same inPace app as the desktop: Python starts a small web server that only this phone can
// reach (127.0.0.1), and this Flutter shell shows it full screen. Links to other apps (Telegram, WhatsApp,
// email, the browser) open those apps, and inpace:// links open the right screen inside inPace.

import 'dart:async';
import 'dart:io';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:serious_python/serious_python.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';

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
      ));
    final android = controller.platform;
    if (android is AndroidWebViewController) {
      android.setMediaPlaybackRequiresUserGesture(false);
      // Voice notes: let the page use the microphone (Android still asks the person first).
      android.setOnPlatformPermissionRequest((request) => request.grant());
    }
    controller.loadRequest(Uri.parse(_base + (_pendingLink ?? '')));
    setState(() => _web = controller);
  }

  Future<bool> _goBack() async {
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
      child: Scaffold(body: SafeArea(child: WebViewWidget(controller: web))),
    );
  }
}
