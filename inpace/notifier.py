"""Notifications and alarms on a computer, and the computer's own scheduler.

inPace is closed most of the time, so reminders are handed to the computer's scheduler, which starts a small
part of inPace at the right moment (`inpace --remind <id>`, `inpace --check-reminders`):

  Windows  Task Scheduler (schtasks), tasks in the "inPace" folder; notifications are Windows toasts
  Mac      launchd agents in ~/Library/LaunchAgents (org.inpace.*); notifications through osascript
  Linux    systemd user timers in ~/.config/systemd/user (inpace-*), or cron when systemd isn't there;
           notifications through notify-send, alarms ring with paplay and ask with zenity or kdialog

Set INPACE_SCHEDULER=off to never touch the scheduler (the tests do).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from xml.sax.saxutils import escape

DAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
SYSTEMD_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
AUMID = "inPace.App"
NO_WINDOW = 0x08000000  # Windows: don't flash a console window
SNOOZE_MINUTES = 10


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    if sys.platform == "win32":
        kw.setdefault("creationflags", NO_WINDOW)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=kw.pop("timeout", 30), **kw)


# ---- how to start inPace from the scheduler --------------------------------------------------------------

def command(home: Path | None = None) -> list[str] | None:
    """The command that starts this copy of inPace, or None when the scheduler can't run it."""
    from .vault import default_home
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
    elif sys.platform == "win32":
        return None  # running from source on Windows: reminders work in the installed app
    else:
        env = shutil.which("env") or "/usr/bin/env"
        root = str(Path(__file__).resolve().parent.parent)
        cmd = [env, f"PYTHONPATH={root}", sys.executable, "-m", "inpace"]
    if home and Path(home).resolve() != Path(default_home()).resolve():
        cmd += ["--home", str(home)]
    return cmd


def entries(v) -> list[dict]:
    """What the scheduler should run: one entry per reminder that's on, and an hourly check for Tempo's nudges."""
    from . import reminders
    d = reminders.load(v)
    out = [{"name": f"reminder-{r['id']}", "args": ["--remind", r["id"]], "time": r["time"], "days": r["days"]}
           for r in d["items"] if r["on"]]
    if any(d["auto"].values()):
        out.append({"name": "check", "args": ["--check-reminders"], "hourly": True})
    return out


# ---- Linux: systemd user timers (or cron) ---------------------------------------------------------------

def _systemd_quote(arg: str) -> str:
    arg = arg.replace("%", "%%")
    if not any(c in arg for c in ' "\'\\'):
        return arg
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'


def linux_units(items: list[dict], cmd: list[str]) -> dict[str, str]:
    files = {}
    for e in items:
        unit = f"inpace-{e['name']}"
        exec_line = " ".join(_systemd_quote(a) for a in cmd + e["args"])
        files[unit + ".service"] = (
            "[Unit]\nDescription=inPace reminder\n\n[Service]\nType=oneshot\n"
            "Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=%t/bus\n"
            f"ExecStart={exec_line}\n")
        if e.get("hourly"):
            when = "hourly"
        else:
            days = "" if len(e["days"]) == 7 else ",".join(SYSTEMD_DAYS[d] for d in e["days"]) + " "
            when = f"{days}*-*-* {e['time']}:00"
        files[unit + ".timer"] = (
            f"[Unit]\nDescription=inPace reminder\n\n[Timer]\nOnCalendar={when}\nUnit={unit}.service\n\n"
            "[Install]\nWantedBy=timers.target\n")
    return files


def cron_lines(items: list[dict], cmd: list[str]) -> list[str]:
    import shlex
    env = "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus DISPLAY=${DISPLAY:-:0}"
    lines = []
    for e in items:
        run = " ".join(shlex.quote(a) for a in cmd + e["args"])
        if e.get("hourly"):
            lines.append(f"0 * * * * {env} {run}")
        else:
            h, m = e["time"].split(":")
            dow = "*" if len(e["days"]) == 7 else ",".join(str((d + 1) % 7) for d in e["days"])
            lines.append(f"{int(m)} {int(h)} * * {dow} {env} {run}")
    return lines


def _sync_linux(items: list[dict], cmd: list[str]) -> str:
    systemctl = shutil.which("systemctl")
    folder = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user"
    if systemctl and _run([systemctl, "--user", "is-system-running"], timeout=10).stdout.strip() not in ("", "offline"):
        want = linux_units(items, cmd)
        folder.mkdir(parents=True, exist_ok=True)
        old = {p.name for p in folder.glob("inpace-*") if p.suffix in (".timer", ".service")}
        for name in old - set(want):
            if name.endswith(".timer"):
                _run([systemctl, "--user", "disable", "--now", name], timeout=15)
            (folder / name).unlink(missing_ok=True)
        for name, text in want.items():
            (folder / name).write_text(text, encoding="utf-8")
        _run([systemctl, "--user", "daemon-reload"], timeout=15)
        for name in want:
            if name.endswith(".timer"):
                r = _run([systemctl, "--user", "enable", "--now", name], timeout=15)
                if r.returncode != 0:
                    return "error: " + (r.stderr or r.stdout).strip()[:200]
        _sync_cron([], cmd, quiet=True)  # tidy up an older cron setup
        return "ok: systemd"
    return _sync_cron(items, cmd)


def _sync_cron(items: list[dict], cmd: list[str], quiet: bool = False) -> str:
    crontab = shutil.which("crontab")
    if not crontab:
        return "ok: none" if quiet else "unsupported: no systemd or cron on this computer"
    cur = _run([crontab, "-l"], timeout=10)
    lines = cur.stdout.splitlines() if cur.returncode == 0 else []
    start, end = "# inPace reminders (start)", "# inPace reminders (end)"
    keep, inside = [], False
    for line in lines:
        if line == start:
            inside = True
        elif line == end:
            inside = False
        elif not inside:
            keep.append(line)
    new = keep + ([start] + cron_lines(items, cmd) + [end] if items else [])
    if new == lines:
        return "ok: cron"
    r = subprocess.run([crontab, "-"], input="\n".join(new) + "\n", capture_output=True, text=True, timeout=10)
    return "ok: cron" if r.returncode == 0 else "error: " + r.stderr.strip()[:200]


# ---- Mac: launchd agents ---------------------------------------------------------------------------------

def mac_plists(items: list[dict], cmd: list[str]) -> dict[str, bytes]:
    import plistlib  # only on a Mac (it needs Python's XML parser, which phones may not have)
    out = {}
    for e in items:
        label = f"org.inpace.{e['name']}"
        p = {"Label": label, "ProgramArguments": cmd + e["args"], "RunAtLoad": False, "ProcessType": "Interactive"}
        if e.get("hourly"):
            p["StartInterval"] = 3600
        else:
            h, m = (int(x) for x in e["time"].split(":"))
            if len(e["days"]) == 7:
                p["StartCalendarInterval"] = {"Hour": h, "Minute": m}
            else:  # launchd counts Sunday as 0
                p["StartCalendarInterval"] = [{"Weekday": (d + 1) % 7, "Hour": h, "Minute": m} for d in e["days"]]
        out[label + ".plist"] = plistlib.dumps(p)
    return out


def _sync_mac(items: list[dict], cmd: list[str]) -> str:
    folder = Path.home() / "Library" / "LaunchAgents"
    folder.mkdir(parents=True, exist_ok=True)
    want = mac_plists(items, cmd)
    domain = f"gui/{os.getuid()}"
    for p in folder.glob("org.inpace.*.plist"):
        if p.name not in want:
            _run(["launchctl", "bootout", f"{domain}/{p.stem}"], timeout=15)
            p.unlink(missing_ok=True)
    for name, data in want.items():
        path = folder / name
        if path.exists() and path.read_bytes() == data:
            continue
        _run(["launchctl", "bootout", f"{domain}/{path.stem}"], timeout=15)
        path.write_bytes(data)
        r = _run(["launchctl", "bootstrap", domain, str(path)], timeout=15)
        if r.returncode != 0:
            r = _run(["launchctl", "load", "-w", str(path)], timeout=15)  # older macOS
            if r.returncode != 0:
                return "error: " + (r.stderr or r.stdout).strip()[:200]
    return "ok: launchd"


# ---- Windows: Task Scheduler ------------------------------------------------------------------------------

def windows_tasks(items: list[dict], cmd: list[str]) -> list[list[str]]:
    out = []
    for e in items:
        task = ["schtasks", "/Create", "/F", "/TN", f"inPace\\{e['name']}", "/TR", subprocess.list2cmdline(cmd + e["args"])]
        if e.get("hourly"):
            task += ["/SC", "HOURLY", "/ST", "00:00"]
        elif len(e["days"]) == 7:
            task += ["/SC", "DAILY", "/ST", e["time"]]
        else:
            task += ["/SC", "WEEKLY", "/D", ",".join(DAY_CODES[d] for d in e["days"]), "/ST", e["time"]]
        out.append(task)
    return out


def _sync_windows(items: list[dict], cmd: list[str]) -> str:
    q = _run(["schtasks", "/Query", "/FO", "CSV", "/NH"], timeout=30)
    have = set()
    for line in q.stdout.splitlines():
        name = line.split(",")[0].strip('"')
        if name.lower().startswith("\\inpace\\"):
            have.add(name.split("\\")[-1])
    want = {e["name"] for e in items}
    for name in have - want:
        _run(["schtasks", "/Delete", "/F", "/TN", f"inPace\\{name}"], timeout=30)
    for task in windows_tasks(items, cmd):
        r = _run(task, timeout=30)
        if r.returncode != 0:
            return "error: " + (r.stderr or r.stdout).strip()[:200]
    return "ok: task scheduler"


# ---- keeping the scheduler in step ------------------------------------------------------------------------

def sync(v, force: bool = False) -> str:
    """Make the computer's scheduler match your reminders. Returns "ok: ...", "off", "unsupported: ..." or "error: ..."."""
    if os.environ.get("INPACE_SCHEDULER") == "off" or os.environ.get("INPACE_MOBILE"):
        return "off"
    cmd = command(v.home)
    if not cmd:
        return "unsupported: reminders that work while inPace is closed need the installed app"
    items = entries(v)
    sig = hashlib.sha256(json.dumps([sys.platform, cmd, items]).encode()).hexdigest()
    if not force and v._meta("scheduler_sig", "") == sig:
        return v._meta("scheduler_status", "ok") or "ok"
    try:
        if sys.platform == "win32":
            status = _sync_windows(items, cmd)
        elif sys.platform == "darwin":
            status = _sync_mac(items, cmd)
        else:
            status = _sync_linux(items, cmd)
    except Exception as e:  # a missing tool shouldn't stop inPace
        status = f"error: {e}"
    v._set_meta("scheduler_status", status)
    v._set_meta("scheduler_sig", sig if status.startswith("ok") else "")
    return status


# ---- showing a notification -------------------------------------------------------------------------------

def _icon_png() -> str:
    for p in (Path("/usr/share/icons/hicolor/256x256/apps/inpace.png"), Path(__file__).parent / "static" / "icon-256.png"):
        if p.exists():
            return str(p)
    return ""


def _windows_register_aumid() -> None:
    """Windows shows a toast under the name of a registered app id; register "inPace" for this user."""
    try:
        import winreg  # type: ignore
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}") as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "inPace")
            icon = _icon_png()
            if icon:
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, icon)
    except Exception:
        pass


def windows_toast_xml(title: str, body: str, link: str, alarm: bool = False) -> str:
    attrs = ' scenario="alarm"' if alarm else ""
    if link:
        attrs += ' activationType="protocol" launch="' + escape(link, {'"': "&quot;"}) + '"'
    parts = [f"<toast{attrs}>", '<visual><binding template="ToastGeneric">',
             f"<text>{escape(title)}</text><text>{escape(body)}</text>", "</binding></visual>"]
    if alarm:
        parts.append('<audio src="ms-winsoundevent:Notification.Looping.Alarm" loop="true"/>')
        parts.append('<actions><action activationType="system" arguments="snooze" content=""/>'
                     '<action activationType="system" arguments="dismiss" content=""/></actions>')
    parts.append("</toast>")
    return "".join(parts)


def _windows_toast(title: str, body: str, link: str, alarm: bool) -> bool:
    _windows_register_aumid()
    xml = windows_toast_xml(title, body, link, alarm).replace("'", "''")
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null\n"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null\n"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        f"$x.LoadXml('{xml}')\n"
        "$t = New-Object Windows.UI.Notifications.ToastNotification $x\n"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{AUMID}').Show($t)\n")
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    r = _run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
             timeout=60)
    return r.returncode == 0


def _osascript(lines: list[str], args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    cmd = ["osascript"]
    for line in ["on run argv"] + lines + ["end run"]:
        cmd += ["-e", line]
    return _run(cmd + args, timeout=timeout)


def go_link(path: str) -> str:
    return "inpace://go" + (path if path.startswith("/") else "/" + path)


def open_inpace(path: str = "/", home: Path | None = None) -> None:
    """Start inPace (or bring it to that page) on a page."""
    cmd = command(home) if getattr(sys, "frozen", False) or sys.platform != "win32" else [sys.executable, "-m", "inpace"]
    if not cmd:
        return
    kw: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "start_new_session": True}
    if sys.platform == "win32":
        kw = {"creationflags": NO_WINDOW | 0x00000008}  # DETACHED_PROCESS
    subprocess.Popen(cmd + [go_link(path)], **kw)


def notify(title: str, body: str, path: str = "/", home: Path | None = None) -> bool:
    """Show a notification. Clicking it opens inPace on that page, where the computer allows it."""
    try:
        if sys.platform == "win32":
            return _windows_toast(title, body, go_link(path), alarm=False)
        if sys.platform == "darwin":
            return _osascript(['display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"'],
                              [title, body]).returncode == 0
        ns = shutil.which("notify-send")
        if ns:
            icon = _icon_png()
            r = _run([ns, "-a", "inPace", *(["-i", icon] if icon else []), title, body], timeout=15)
            return r.returncode == 0
        gdbus = shutil.which("gdbus")
        if gdbus:
            r = _run([gdbus, "call", "--session", "--dest", "org.freedesktop.Notifications", "--object-path",
                      "/org/freedesktop/Notifications", "--method", "org.freedesktop.Notifications.Notify",
                      "inPace", "0", _icon_png(), title, body, "[]", "{}", "10000"], timeout=15)
            return r.returncode == 0
    except Exception:
        return False
    return False


class _Ringer:
    """Plays an alarm sound again and again until stopped (Mac and Linux; Windows toasts ring by themselves)."""

    def __init__(self) -> None:
        self.stop = threading.Event()
        self.cmd = self._sound()

    @staticmethod
    def _sound() -> list[str] | None:
        if sys.platform == "darwin":
            return ["afplay", "/System/Library/Sounds/Glass.aiff"]
        for tool, files in (("paplay", ["/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
                                        "/usr/share/sounds/freedesktop/stereo/complete.oga"]),
                            ("canberra-gtk-play", None)):
            exe = shutil.which(tool)
            if not exe:
                continue
            if files is None:
                return [exe, "-i", "alarm-clock-elapsed"]
            for f in files:
                if Path(f).exists():
                    return [exe, f]
        return None

    def start(self) -> None:
        if not self.cmd:
            return

        def loop() -> None:
            end = time.time() + 600  # never ring for more than 10 minutes
            while not self.stop.is_set() and time.time() < end:
                try:
                    subprocess.run(self.cmd, capture_output=True, timeout=30)
                except Exception:
                    return
                self.stop.wait(0.6)
        threading.Thread(target=loop, daemon=True).start()


def _ask_alarm(title: str, body: str, labels: dict) -> str:
    """Show the alarm and wait: returns "stop", "snooze" or "open"."""
    stop, snooze, start = labels["stop"], labels["snooze"], labels["open"]
    if sys.platform == "darwin":
        r = _osascript(["set b to button returned of (display dialog (item 2 of argv) with title (item 1 of argv) "
                        "buttons {item 3 of argv, item 4 of argv, item 5 of argv} default button (item 5 of argv) "
                        "giving up after 600)", "return b"], [title, body, snooze, start, stop], timeout=620)
        out = r.stdout.strip()
        return "snooze" if out == snooze else "open" if out == start else "stop"
    zenity = shutil.which("zenity")
    if zenity:
        r = _run([zenity, "--question", "--title", f"inPace: {title}", "--text", body, "--ok-label", stop,
                  "--cancel-label", snooze, "--extra-button", start, "--timeout", "600", "--icon-name", "alarm-symbolic"],
                 timeout=620)
        if r.returncode == 0 or r.returncode == 5:
            return "stop"
        return "open" if r.stdout.strip() == start else "snooze"
    kdialog = shutil.which("kdialog")
    if kdialog:
        r = _run([kdialog, "--title", f"inPace: {title}", "--yesnocancel", body, "--yes-label", stop,
                  "--no-label", snooze, "--cancel-label", start], timeout=620)
        return {0: "stop", 1: "snooze"}.get(r.returncode, "open")
    notify(title, body)
    time.sleep(60)  # no dialog tool: ring for a minute
    return "stop"


def alarm(title: str, body: str, path: str, labels: dict, home: Path | None = None) -> str:
    """Ring until you stop it. Snooze rings again after 10 minutes (up to three times)."""
    if sys.platform == "win32":
        _windows_toast(title, body, go_link(path), alarm=True)  # Windows rings, snoozes and stops it by itself
        return "shown"
    for _ in range(4):
        ringer = _Ringer()
        ringer.start()
        try:
            choice = _ask_alarm(title, body, labels)
        finally:
            ringer.stop.set()
        if choice == "open":
            open_inpace(path, home)
            return "open"
        if choice != "snooze":
            return "stop"
        time.sleep(SNOOZE_MINUTES * 60)
    return "stop"
