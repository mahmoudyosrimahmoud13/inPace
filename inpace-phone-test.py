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


def main():
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
    say()
    for _ in range(3):
        try:
            page.call("Page.enable")
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
            time.sleep(0.3)
            page.wait_loaded(path.split("?")[0], 60)
            time.sleep(1.2)
            tm = page.js(TIMINGS) or {}
            sc = page.js(SCROLL, 30) or {}
            say(f"  {path:<28} {visit:<5} python {tm.get('python')}  ready {tm.get('ready')}  loaded {tm.get('loaded')}"
                f"  | {tm.get('kb')} KB, {tm.get('nodes')} elements, {tm.get('images')} images"
                f"  | busy {tm.get('longtask_ms')} ms in {tm.get('longtasks')} long tasks"
                f"  | scroll {sc.get('fps')} fps, worst frame {sc.get('worst_ms')} ms")
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
    for l in mem.splitlines():
        if "TOTAL" in l and ("PSS" in l or l.strip().startswith("TOTAL")):
            say("  inPace memory: " + " ".join(l.split()))
            break
    say()
    say("Done.")
    adb("forward", "--remove", f"tcp:{PORT}")
    with open("inpace-speed-report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(OUT) + "\n")
    print("\nSaved inpace-speed-report.txt here: " + os.path.abspath("inpace-speed-report.txt"))


if __name__ == "__main__":
    main()
