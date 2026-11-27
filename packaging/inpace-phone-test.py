#!/usr/bin/env python3
"""inPace phone speed test: run on a computer with the phone connected by USB.

Needs: adb (sudo apt install adb), USB debugging on the phone, and in inPace on the phone:
Settings -> Testing from a computer -> Allow inspecting over USB. Only Python's standard library is used.

It measures: how long the app takes to open, how long each page takes (Python's answer vs. drawing the page),
how smooth scrolling is, how busy and full the phone is. It writes inpace-speed-report.txt; send that file.
Nothing is changed on the phone except opening pages in inPace (and restarting inPace once, for the start test).
"""
import base64
import json
import os
import socket
import struct
import subprocess
import sys
import time

PKG = "org.inpace.inpace_mobile"
PORT = 9333
OUT = []


def say(line=""):
    print(line, flush=True)
    OUT.append(str(line))


def adb(*args, timeout=30):
    r = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()


# ---- a tiny websocket client (so nothing has to be installed) ---------------------------------------------
class WS:
    def __init__(self, url):
        hostport, path = url[len("ws://"):].split("/", 1)
        host, port = hostport.split(":")
        self.s = socket.create_connection((host, int(port)), timeout=90)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.s.recv(4096)
            if not chunk:
                raise RuntimeError("the phone closed the connection")
            buf += chunk
        head, self.buf = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise RuntimeError(head.decode(errors="replace"))

    def send(self, text, op=0x1):
        data = text.encode() if isinstance(text, str) else text
        hdr = bytearray([0x80 | op])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", n)
        mask = os.urandom(4)
        hdr += mask
        self.s.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(1 << 16)
            if not chunk:
                raise EOFError
            self.buf += chunk
        d, self.buf = self.buf[:n], self.buf[n:]
        return d

    def recv(self):
        msg = b""
        while True:
            b1, b2 = self._read(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            data = self._read(n)
            if b2 & 0x80:
                m = self._read(4)
                data = bytes(x ^ m[i % 4] for i, x in enumerate(data))
            if op == 0x9:  # ping
                self.send(data, op=0xA)
                continue
            if op == 0x8:
                raise EOFError
            msg += data
            if b1 & 0x80:
                return msg.decode("utf-8", "replace")


class Page:
    def __init__(self, ws_url):
        self.ws = WS(ws_url)
        self.i = 0

    def call(self, method, **params):
        self.i += 1
        mid = self.i
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})

    def reconnect(self):
        """The page was replaced (the loading screen became the first page): connect to the new one."""
        try:
            self.ws.s.close()
        except Exception:
            pass
        for _ in range(40):
            try:
                t = page_targets()
                if t:
                    self.ws = WS(t[0]["webSocketDebuggerUrl"])
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def js(self, expr, timeout=60):
        try:
            r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True, timeout=timeout * 1000)
        except RuntimeError:  # the page moved on while we asked: ask again next time
            return None
        except (EOFError, OSError):  # the page was replaced: connect to the new one
            self.reconnect()
            return None
        if r.get("exceptionDetails"):
            return None
        return (r.get("result") or {}).get("value")

    def wait_loaded(self, path_prefix="", timeout=90):
        end = time.time() + timeout
        while time.time() < end:
            v = self.js("document.readyState + '|' + location.href")
            if v and v.startswith("complete|http://127.0.0.1") and (not path_prefix or path_prefix in v):
                return True
            time.sleep(0.15)
        return False


def page_targets():
    import urllib.request
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=10) as r:
        return [t for t in json.load(r) if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]


def connect(timeout=120):
    """Find inPace's web view on the phone and connect to it through adb."""
    end = time.time() + timeout
    while time.time() < end:
        pid = adb("shell", "pidof", PKG)
        socks = adb("shell", "cat", "/proc/net/unix")
        names = sorted({w.lstrip("@") for line in socks.splitlines() for w in line.split()
                        if "webview_devtools_remote" in w})
        name = next((n for n in names if pid and n.endswith("_" + pid.split()[0])), names[0] if names else "")
        if name:
            adb("forward", f"tcp:{PORT}", f"localabstract:{name}")
            try:
                t = page_targets()
                if t:
                    return Page(t[0]["webSocketDebuggerUrl"])
            except Exception:
                pass
        time.sleep(0.4)
    return None


LONGTASKS = ("window.__lt=[];try{new PerformanceObserver(function(l){l.getEntries().forEach(function(e){__lt.push(e.duration)})})"
             ".observe({type:'longtask',buffered:true})}catch(e){}")
TIMINGS = """(function(){var n=performance.getEntriesByType('navigation')[0]||{};var lt=window.__lt||[];
return {python:Math.round(n.responseStart-n.requestStart), html_done:Math.round(n.responseEnd-n.startTime),
ready:Math.round(n.domContentLoadedEventEnd-n.startTime), loaded:Math.round(n.loadEventEnd-n.startTime),
kb:Math.round((n.encodedBodySize||0)/1024), nodes:document.getElementsByTagName('*').length,
images:document.images.length, longtasks:lt.length, longtask_ms:Math.round(lt.reduce(function(a,b){return a+b},0))}})()"""
SCROLL = """new Promise(function(res){var se=document.scrollingElement;var max=se.scrollHeight-innerHeight;
if(max<200){res({fps:null,worst_ms:null,scroll_px:max});return}var f=0,worst=0,t0=performance.now(),last=t0;se.scrollTop=0;
function step(t){f++;worst=Math.max(worst,t-last);last=t;var p=Math.min((t-t0)/2500,1);se.scrollTop=max*p;
if(p<1)requestAnimationFrame(step);else res({fps:Math.round(f/2.5),worst_ms:Math.round(worst),scroll_px:max})}
requestAnimationFrame(step)})"""
FETCH = """(async function(){var r=[];for(var i=0;i<3;i++){var t=performance.now();var x=await fetch(location.pathname,{cache:'no-store'});
await x.text();r.push(Math.round(performance.now()-t))}return r})()"""


def start_test(times=5):
    """Open inPace again and again: fully closed (like swiping it away), and from the background (like pressing
    Home and coming back). The first start after installing an update is slower: Python prepares inPace's code."""
    say(f"== Opening and closing inPace, {times} times each, and opening it from a notification")
    cold, warm = [], []
    for n in range(1, times + 1):
        adb("shell", "am", "force-stop", PKG)
        time.sleep(3)
        t0 = time.time()
        adb("shell", "monkey", "-p", PKG, "-c", "android.intent.category.LAUNCHER", "1")
        page = connect(150)
        if not page:
            say(f"  closed start {n}: couldn't reach inPace's pages")
            continue
        ok = page.wait_loaded("", 150)
        t = time.time() - t0
        cold.append(t)
        inside = page.js("fetch('/debug/startup').then(function(r){return r.ok ? r.text() : ''})") or ""
        say(f"  closed start {n}: first page after {t:.1f} s" + ("" if ok else " (timed out)") + (f"   {inside}" if inside else ""))
        time.sleep(3)
    for n in range(1, times + 1):
        adb("shell", "input", "keyevent", "KEYCODE_HOME")
        time.sleep(4)
        t0 = time.time()
        adb("shell", "monkey", "-p", PKG, "-c", "android.intent.category.LAUNCHER", "1")
        page = connect(60)
        answered = page.js("1") if page else None
        t = time.time() - t0
        warm.append(t)
        say(f"  from background {n}: answering again after {t:.1f} s" + ("" if answered == 1 else " (no answer)"))
        time.sleep(2)
    # Tapping one of inPace's notifications: Android opens the app with the page to show (the same thing a tap does)
    notif = []
    for n in range(1, min(times, 3) * 2 + 1):
        closed = n % 2 == 1
        target = "/sprints" if closed else "/insights"
        if closed:
            adb("shell", "am", "force-stop", PKG)
        else:
            adb("shell", "input", "keyevent", "KEYCODE_HOME")
        time.sleep(3)
        t0 = time.time()
        adb("shell", "am", "start", "-n", PKG + "/.MainActivity", "-f", "0x20000000", "--es", "inpace_url", target)
        page = connect(150)
        shown = False
        end = time.time() + 150
        while page and time.time() < end:
            v = page.js("document.readyState + '|' + location.pathname")
            if v and v == "complete|" + target:
                shown = True
                break
            time.sleep(0.1)
        t = time.time() - t0
        notif.append(t)
        say(f"  notification tap, app {'closed' if closed else 'in background'}: {target} shown after {t:.1f} s"
            + ("" if shown else " (that page never came)"))
        time.sleep(2)
    if cold:
        say(f"  closed starts: fastest {min(cold):.1f} s, slowest {max(cold):.1f} s, middle {sorted(cold)[len(cold) // 2]:.1f} s")
    if warm:
        say(f"  from background: fastest {min(warm):.1f} s, slowest {max(warm):.1f} s")
    say()


SKIP = ("remove", "delete", "export", "download", "/stop", "quit", "/file", ".json", ".svg", ".zip", ".pdf", "backup",
        "/m/", "sample-file", "reset", "/debug", "logout", "/static/", "share.html", "record", "/files/", "/evidence/",
        "codenote/lesson", "/print", "outbox", "/new", "/ai", "/card", "/report", ".md", ".yaml", ".inpace")


def pattern(path):
    import re
    p = path.split("#")[0]
    p = re.sub(r"/[0-9a-f]{8,}", "/:id", p)
    p = re.sub(r"/lesson/[^/?]+", "/lesson/:l", p)
    p = re.sub(r"/(courses|roadmaps|library|people|review|races|module|modules)/[^/?]+", r"/\1/:x", p)
    return p.split("?")[0]


def tour(page, base, limit=70):
    """Visit every kind of page in the app, the way you would: tap a link on the page you're on and wait until the
    next page is shown. One of each kind (one course, one lesson...)."""
    say(f"== Every page, one after another (tap a link, wait until the page is shown; up to {limit} kinds)")
    LINKS = """[].map.call(document.querySelectorAll('a[href^="/"]'),function(a){return a.getAttribute('href')})"""
    seen, queue, rows = set(), ["/"], []
    page.call("Page.navigate", url=base + "/")
    page.wait_loaded("", 60)
    time.sleep(1)
    while queue and len(rows) < limit:
        path = queue.pop(0)
        pat = pattern(path)
        if pat in seen:
            continue
        seen.add(pat)
        target = path.split("#")[0]
        before = page.js("location.href")
        t0 = time.time()
        clicked = page.js("(function(){var a=[].filter.call(document.querySelectorAll('a[href]'),function(x){return x.getAttribute('href')==%s})[0];"
                          "if(a){a.click();return true}location.href=%s;return false})()" % (json.dumps(path), json.dumps(target)))
        shown = False
        end = time.time() + 60
        while time.time() < end:
            v = page.js("document.readyState + '|' + location.pathname + location.search + '|' + location.href")
            if v and v.startswith("complete|"):
                _, here, href = v.split("|", 2)
                if here == target:
                    shown = True
                    break
                if href != before and time.time() - t0 > 2:  # it went somewhere else (a redirect): that counts
                    shown = True
                    target = here
                    break
                if href == before and time.time() - t0 > 8:  # nothing happened
                    break
            time.sleep(0.05)
        ms = (time.time() - t0) * 1000
        time.sleep(0.6)
        tm = page.js(TIMINGS) or {}
        rows.append((ms, target, tm, clicked, shown))
        say(f"  {ms:6.0f} ms  {target[:60]:<60} python {tm.get('python')}  ready {tm.get('ready')}"
            f"  busy {tm.get('longtask_ms')} ms" + ("" if shown else "  (didn't finish)") + ("" if clicked else "  (typed, no link)"))
        for h in page.js(LINKS) or []:
            if h and not any(k in h for k in SKIP) and pattern(h) not in seen and h not in queue:
                queue.append(h)
    if rows:
        rows.sort(key=lambda r: -r[0])
        say("  slowest 10:")
        for ms, target, tm, _c, _s in rows[:10]:
            say(f"    {ms:6.0f} ms  {target}")
        say(f"  {len(rows)} pages, middle {sorted(r[0] for r in rows)[len(rows) // 2]:.0f} ms, slowest {rows[0][0]:.0f} ms")
    say()


METRICS = ("TaskDuration", "ScriptDuration", "LayoutDuration", "RecalcStyleDuration", "LayoutCount", "RecalcStyleCount",
           "JSHeapUsedSize", "Nodes")
RESOURCES = """(function(){return performance.getEntriesByType('resource').map(function(r){return [Math.round(r.duration),
Math.round((r.encodedBodySize||0)/1024), r.name.replace(location.origin,'')]}).sort(function(a,b){return b[0]-a[0]}).slice(0,6)})()"""


def metrics(page):
    try:
        return {m["name"]: m["value"] for m in page.call("Performance.getMetrics").get("metrics", [])}
    except Exception:
        return {}


def js_profile(page, url, path):
    """Record which JavaScript functions the phone spends its time in while the page opens."""
    try:
        page.call("Profiler.enable")
        page.call("Profiler.setSamplingInterval", interval=500)
        page.call("Profiler.start")
        page.call("Page.navigate", url=url)
        time.sleep(0.3)
        page.wait_loaded(path, 60)
        time.sleep(1.5)
        prof = page.call("Profiler.stop")["profile"]
    except Exception as e:
        return [f"(no profile: {e})"]
    nodes = {n["id"]: n for n in prof["nodes"]}
    dt = prof.get("timeDeltas") or []
    own = {}
    for sid, d in zip(prof.get("samples") or [], dt):
        cf = nodes[sid]["callFrame"]
        if cf.get("functionName") == "(idle)":
            continue
        import re
        u = re.sub(r"^https?://[^/]+", "", cf.get("url", "")).split("?")[0]
        key = (cf.get("functionName") or "(anonymous)") + (f"  {u}:{cf.get('lineNumber', 0) + 1}" if u else "")
        own[key] = own.get(key, 0) + d / 1000
    total = sum(own.values()) or 1
    top = sorted(own.items(), key=lambda x: -x[1])[:10]
    return [f"{ms:7.0f} ms {100 * ms / total:5.1f}%  {k}" for k, ms in top]


def server_profile(page, path):
    v = page.js("fetch('/debug/profile?runs=3&path=' + encodeURIComponent(%s)).then(function(r){return r.ok ? r.text() : "
                "'(not in this version)'})" % json.dumps(path), 300)
    return (v or "(no answer)").rstrip().splitlines()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("start", "tour"):
        mode = sys.argv[1]
        if not adb("version"):
            sys.exit("adb isn't installed. Run: sudo apt install adb")
        say(f"inPace {mode} test  " + time.strftime("%Y-%m-%d %H:%M"))
        if mode == "start":
            start_test(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
        else:
            page = connect(60)
            if not page:
                sys.exit("Open inPace on the phone first.")
            page.call("Page.enable")
            page.call("Page.addScriptToEvaluateOnNewDocument", source=LONGTASKS)
            tour(page, page.js("location.origin"))
        name = f"inpace-{mode}-report.txt"
        with open(name, "w", encoding="utf-8") as f:
            f.write("\n".join(OUT) + "\n")
        print("\nSaved " + name)
        return
    if not adb("version"):
        sys.exit("adb isn't installed. Run: sudo apt install adb")
    devs = [l for l in adb("devices").splitlines()[1:] if l.strip()]
    if not devs or "unauthorized" in devs[0]:
        sys.exit("No phone found (or it asks 'Allow USB debugging?': tap Allow on the phone), then run this again.")
    say("inPace phone speed test  " + time.strftime("%Y-%m-%d %H:%M"))
    say("Phone: %s %s, Android %s, %s CPU cores" % (adb("shell", "getprop", "ro.product.manufacturer"),
        adb("shell", "getprop", "ro.product.model"), adb("shell", "getprop", "ro.build.version.release"),
        adb("shell", "nproc") or "?"))
    say("Memory: " + " ".join(adb("shell", "cat", "/proc/meminfo").splitlines()[:3]))
    say("Battery saver: " + (adb("shell", "settings", "get", "global", "low_power") or "?"))
    ver = adb("shell", "dumpsys", "package", PKG)
    say("inPace: " + next((l.strip() for l in ver.splitlines() if "versionName" in l), "not installed?"))
    say()

    # 1. Opening the app from closed
    say("== 1. Opening inPace from closed")
    adb("shell", "am", "force-stop", PKG)
    time.sleep(1.5)
    t0 = time.time()
    adb("shell", "monkey", "-p", PKG, "-c", "android.intent.category.LAUNCHER", "1")
    page = connect(150)
    if not page:
        sys.exit("Couldn't reach inPace's pages. In inPace: Settings -> Testing from a computer -> "
                 "Allow inspecting over USB, then run this again.")
    t_view = time.time() - t0
    ok = page.wait_loaded("", 150)
    t_first = time.time() - t0
    say(f"  web view ready after {t_view:.1f} s; first page shown after {t_first:.1f} s" + ("" if ok else " (timed out)"))
    time.sleep(2)
    say("  inside inPace: " + str(page.js("fetch('/debug/startup').then(function(r){return r.ok ? r.text() : '(not in this version)'})")))
    say()
    for _ in range(3):
        try:
            page.call("Page.enable")
            page.call("Performance.enable")
            page.call("Page.addScriptToEvaluateOnNewDocument", source=LONGTASKS)
            break
        except (RuntimeError, EOFError, OSError):
            page.reconnect()
            time.sleep(1)
    base = None
    for _ in range(60):
        base = page.js("location.origin")
        if base and base.startswith("http://127.0.0.1"):
            break
        time.sleep(0.5)
    if not base or not base.startswith("http://127.0.0.1"):
        sys.exit("inPace's first page didn't come up. Open inPace on the phone, wait for Home, then run this again.")
    time.sleep(3)

    # 2. Each page, twice (first visit, then again)
    say("== 2. Pages (times in ms; python = waiting for inPace's answer, ready = page usable, loaded = all done)")
    adb("shell", "dumpsys", "gfxinfo", PKG, "reset")
    paths = ["/", "/courses", "@course", "@lesson", "/roadmaps", "/sprints", "/insights", "/library", "/island",
             "/downloads", "/settings"]
    found = {}
    for raw in paths:
        path = raw
        if raw == "@course":
            path = found.get("course")
        elif raw == "@lesson":
            path = found.get("lesson")
        if not path:
            continue
        for visit in ("first", "again"):
            try:
                page.call("Page.navigate", url=base + path)
            except (RuntimeError, EOFError, OSError):
                page.reconnect()
                page.call("Page.navigate", url=base + path)
            m0 = metrics(page)
            time.sleep(0.3)
            page.wait_loaded(path.split("?")[0], 60)
            time.sleep(1.2)
            tm = page.js(TIMINGS) or {}
            m1 = metrics(page)
            sc = page.js(SCROLL, 30) or {}
            say(f"  {path:<28} {visit:<5} python {tm.get('python')}  ready {tm.get('ready')}  loaded {tm.get('loaded')}"
                f"  | {tm.get('kb')} KB, {tm.get('nodes')} elements, {tm.get('images')} images"
                f"  | busy {tm.get('longtask_ms')} ms in {tm.get('longtasks')} long tasks"
                f"  | scroll {sc.get('fps')} fps, worst frame {sc.get('worst_ms')} ms")
            if visit == "first" and m1:
                d = {k: m1.get(k, 0) - m0.get(k, 0) for k in METRICS}
                say(f"      phone time: script {d['ScriptDuration'] * 1000:.0f} ms, layout {d['LayoutDuration'] * 1000:.0f} ms"
                    f" ({d['LayoutCount']:.0f}x), styles {d['RecalcStyleDuration'] * 1000:.0f} ms ({d['RecalcStyleCount']:.0f}x),"
                    f" all tasks {d['TaskDuration'] * 1000:.0f} ms; JS memory {m1.get('JSHeapUsedSize', 0) / 1048576:.0f} MB")
                res = page.js(RESOURCES) or []
                say("      slowest files: " + ";  ".join(f"{r[2][-38:]} {r[0]} ms {r[1]} KB" for r in res[:4]))
        if path == "/courses":
            found["course"] = page.js("([].map.call(document.querySelectorAll('a[href]'),function(a){return a.getAttribute('href')})"
                                      ".filter(function(h){return /^\\/learn\\/[^\\/?#]+$/.test(h)})[0])||null")
        if raw == "@course":
            found["lesson"] = page.js("([].map.call(document.querySelectorAll('a[href]'),function(a){return a.getAttribute('href')})"
                                      ".filter(function(h){return /^\\/learn\\/[^\\/]+\\/lesson\\//.test(h)})[0])||null")
    say()

    # 3. Python alone (the same page asked 3 times, without drawing it)
    say("== 3. inPace's answer alone, 3 times each (ms)")
    for path in ["/", "/courses", "/roadmaps", "/settings"]:
        try:
            page.call("Page.navigate", url=base + path)
        except (RuntimeError, EOFError, OSError):
            page.reconnect()
            continue
        page.wait_loaded(path, 60)
        say(f"  {path:<12} {page.js(FETCH, 60)}")
    say()

    # 3a. Every page, one after another
    tour(page, base)

    # 3b. Where Python's time goes on each page (inPace's own profiler, 1.37.8 and newer)
    say("== 3b. Inside inPace: which code the time goes to (3 renders each)")
    for path in ["/", "/courses", found.get("course"), found.get("lesson"), "/roadmaps", "/library", "/settings"]:
        if path:
            for line in server_profile(page, path)[:22]:
                say("  " + line)
    say()

    # 3c. Which JavaScript the phone runs while a page opens
    say("== 3c. JavaScript time while the page opens (top functions)")
    for path in ["/", "/courses", "/library", found.get("lesson")]:
        if path:
            say("  " + path)
            for line in js_profile(page, base + path, path.split("?")[0]):
                say("    " + line)
    say()

    # 4. Frames drawn by the app while we scrolled
    say("== 4. Frames the phone drew (Android's own count)")
    g = adb("shell", "dumpsys", "gfxinfo", PKG)
    for l in g.splitlines():
        if any(k in l for k in ("Total frames rendered", "Janky frames", "50th percentile", "90th percentile",
                                "99th percentile", "Number Missed Vsync", "Number Slow UI thread")):
            say("  " + l.strip())
    say()

    # 5. How busy and full the phone is
    say("== 5. The phone right now")
    top = adb("shell", "top", "-b", "-n", "1")
    for l in top.splitlines()[:16]:
        say("  " + l.rstrip())
    mem = adb("shell", "dumpsys", "meminfo", PKG)
    inside = False
    for l in mem.splitlines():
        if "App Summary" in l:
            inside = True
        if inside:
            say("  " + l.rstrip())
            if l.strip().startswith("TOTAL SWAP") or l.strip().startswith("TOTAL PSS"):
                break
    wv = adb("shell", "dumpsys", "meminfo", "com.google.android.webview:sandboxed_process0")
    for l in wv.splitlines():
        if l.strip().startswith("TOTAL PSS") or l.strip().startswith("TOTAL:"):
            say("  web view's own process: " + " ".join(l.split()))
            break
    say("  busiest apps (CPU %, last minutes):")
    for l in adb("shell", "dumpsys", "cpuinfo").splitlines()[1:12]:
        say("    " + l.strip())
    say()
    # 6. Opening and closing, several times (last: it restarts inPace)
    start_test(5)
    say("Done.")
    adb("forward", "--remove", f"tcp:{PORT}")
    with open("inpace-speed-report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(OUT) + "\n")
    print("\nSaved inpace-speed-report.txt here: " + os.path.abspath("inpace-speed-report.txt"))


if __name__ == "__main__":
    main()
