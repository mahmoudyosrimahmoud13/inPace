"""Host mode (v1.34): share inPace with people on your own network.

You turn it on in Settings. inPace then opens a second door on your network (a port, 8780 unless you pick
another) that anyone on the same Wi-Fi can reach in a browser. The door asks for a username and password: you
make an account for each person. After signing in, each person gets their OWN inPace, with its own data folder
(<your data folder>/hosted/homes/<username>/), its own progress and its own keys. Nobody can see or change
anybody else's progress, and the people who sign in never see yours.

How it works, and why it's safe by design:
- The door is the only thing the network can reach. It checks the password, then passes the page on to that
  person's own inPace, which runs as a separate program on this computer and listens only on 127.0.0.1 (this
  computer). Each of those only answers requests that carry a secret only the door knows.
- A separate program per person means nothing is shared by accident: every inPace keeps some settings for the
  whole program (the language, the timer), and two people in one program would mix them up.
- In a shared inPace, everything that would act on THIS computer is turned off for the people who sign in:
  opening files in your apps, "Show in folder", folders on this computer, video downloads, updates, alarms,
  "Quit". See BLOCKED.
- A person's inPace stops by itself after 30 minutes without a page, and starts again when they come back.

Passwords are kept as scrypt hashes (never the password itself). Sign-ins are limited to 10 tries in 10 minutes
from one address.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

DEFAULT_PORT = 8780
USER_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")
MIN_PASSWORD = 8
IDLE_STOP = 30 * 60          # a person's inPace stops after this long without a page
SESSION_IDLE = 12 * 3600     # sign in again after 12 hours without a page
TRIES, TRY_WINDOW = 10, 600  # sign-in tries per address, per 10 minutes
COOKIE = "inpace_host"

# Pages that act on the computer that runs inPace. A person who signed in through the door can't use them.
BLOCKED = (
    re.compile(r"^/add/(folder|organize|copying/|book)"),
    re.compile(r"^/courses/from-folder"),
    re.compile(r"^/courses/[^/]+/(media-folder|find-files|open-media|book|offline/|publish)"),
    re.compile(r"^/pick-folder"),
    re.compile(r"^/downloads/(settings|delete|open|pause|resume|stop|start|cancel|retry|clear)"),
    re.compile(r"^/pdf/open-outside"),
    re.compile(r"^/codenote/open"),
    re.compile(r"^/window/"),
    re.compile(r"^/quit"),
    re.compile(r"^/updates/"),
    re.compile(r"^/settings/(videos|youtube|ai|restore|delete-everything|host)"),
    re.compile(r"^/reminders/test"),
    re.compile(r"^/learn/[^/]+/task/[^/]+/git"),
)


def blocked(path: str) -> bool:
    return any(rx.match(path) for rx in BLOCKED)


def is_hosted() -> bool:
    """True inside a person's own inPace that the door started."""
    return bool(os.environ.get("INPACE_HOSTED"))


# ---- accounts ------------------------------------------------------------------------------------------------

class AccountProblem(Exception):
    pass


def _folder(home: Path) -> Path:
    return Path(home) / "hosted"


def user_home(home: Path, username: str) -> Path:
    if not USER_RE.match(username or ""):
        raise AccountProblem("That isn't a username.")
    return _folder(home) / "homes" / username


def load_users(home: Path) -> dict:
    try:
        data = json.loads((_folder(home) / "users.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_users(home: Path, users: dict) -> None:
    f = _folder(home)
    f.mkdir(parents=True, exist_ok=True)
    tmp = f / ".users.json.tmp"
    tmp.write_text(json.dumps(users, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f / "users.json")
    try:
        os.chmod(f / "users.json", 0o600)
    except OSError:
        pass


def _hash(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32).hex()


def password_problem(password: str, username: str = "", others: dict | None = None) -> str:
    """Why a password isn't good enough, in plain words, or "" when it is."""
    if len(password or "") < MIN_PASSWORD:
        return "This password is easy to guess. Use 8 characters or more."
    if username and password.lower() == username.lower():
        return "Don't use the username as the password."
    for u, info in (others or {}).items():
        if u != username and check_password_hash(info, password):
            return "Give each person their own password."
    return ""


def check_password_hash(info: dict, password: str) -> bool:
    try:
        return hmac.compare_digest(_hash(password, bytes.fromhex(info["salt"])), info["hash"])
    except (KeyError, ValueError, TypeError):
        return False


def add_user(home: Path, username: str, name: str, password: str) -> dict:
    """Make an account and its own inPace data folder. Raises AccountProblem with a plain reason."""
    from .vault import Vault
    username = (username or "").strip().lower()
    name = re.sub(r"\s+", " ", name or "").strip()[:60]
    if not USER_RE.match(username):
        raise AccountProblem("A username has 3 to 32 small letters, digits, dots, dashes or underscores.")
    users = load_users(home)
    if username in users:
        raise AccountProblem("There's already an account with that username.")
    if not name:
        raise AccountProblem("Give the person's name.")
    problem = password_problem(password, username, users)
    if problem:
        raise AccountProblem(problem)
    salt = secrets.token_bytes(16)
    users[username] = {"name": name, "salt": salt.hex(), "hash": _hash(password, salt), "made": int(time.time())}
    h = user_home(home, username)
    v = Vault(h)
    v.setup(name, "#1F7A56")
    v._set_meta("tour_done", "1")
    v.db.close()
    _save_users(home, users)
    return users[username]


def set_password(home: Path, username: str, password: str) -> None:
    users = load_users(home)
    if username not in users:
        raise AccountProblem("There's no account with that username.")
    problem = password_problem(password, username, users)
    if problem:
        raise AccountProblem(problem)
    salt = secrets.token_bytes(16)
    users[username].update(salt=salt.hex(), hash=_hash(password, salt))
    _save_users(home, users)


def remove_user(home: Path, username: str) -> None:
    """Delete an account and everything in its inPace (its progress too)."""
    users = load_users(home)
    if username not in users:
        return
    h = user_home(home, username)
    users.pop(username)
    _save_users(home, users)
    if DOOR.running:
        DOOR.stop_worker(username)
        DOOR.end_sessions(username)
    root = (_folder(home) / "homes").resolve()
    if h.exists() and h.resolve().parent == root:
        shutil.rmtree(h, ignore_errors=True)


def check_login(home: Path, username: str, password: str) -> bool:
    info = load_users(home).get((username or "").strip().lower())
    if not info:
        _hash(password or "x", b"0" * 16)  # take as long as a real check, so a wrong name isn't faster
        return False
    return check_password_hash(info, password or "")


def give_course(owner, course_id: str, usernames: list[str]) -> int:
    """Put one of your courses in other people's inPace. Its files are linked, not copied, when the disk allows
    (so a big course takes no extra space), and a course that points to a folder of videos on this computer
    points there for them too (they can watch, not change it). Returns how many accounts got it."""
    from .vault import Vault
    c = owner.get_course(course_id)
    if not c:
        raise AccountProblem("That course isn't on this computer.")
    src = owner.home / "courses" / course_id
    media = owner.media_dir(course_id)
    users = load_users(owner.home)
    done = 0
    for u in usernames:
        if u not in users:
            continue
        h = user_home(owner.home, u)
        dst = h / "courses" / course_id
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        if media.exists():
            _link_tree(media, h / "media" / course_id)
        v = Vault(h)
        root = owner.media_root(course_id)
        if root:
            v.set_media_root(course_id, str(root))
        v._courses.pop(course_id, None)
        v.db.close()
        done += 1
    return done


def _link_tree(src: Path, dst: Path) -> None:
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        target = dst / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        try:
            os.link(p, target)
        except OSError:
            shutil.copy2(p, target)


# ---- the network -------------------------------------------------------------------------------------------

def addresses() -> list[str]:
    """This computer's addresses on its networks (where others reach the door), best first."""
    found: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent: this only asks which address the computer would use
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in found:
                found.append(ip)
    except OSError:
        pass
    return [ip for ip in found if not ip.startswith("127.")]


def network_looks_public(ips: list[str]) -> bool:
    """No home or office address (192.168.x, 10.x, 172.16-31.x): the computer may be on a public or mobile
    network, or straight on the internet."""
    ok = False
    for ip in ips:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if a.is_private and not a.is_loopback and not a.is_link_local:
            ok = True
    return not ok


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


# ---- the door ----------------------------------------------------------------------------------------------

def _command(home: Path, port: int) -> tuple[list[str], dict]:
    """How to start one person's inPace: this same program, with their data folder, only for the door."""
    env = {**os.environ, "INPACE_HOSTED": "1", "INPACE_SCHEDULER": "off", "INPACE_NO_WARMUP": "1",
           "INPACE_HOST_TOKEN": DOOR.token, "INPACE_HOST_NAME": DOOR.owner_name, "INPACE_DOOR_PORT": str(DOOR.port)}
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
    else:
        root = str(Path(__file__).resolve().parent.parent)
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
        cmd = [sys.executable, "-m", "inpace"]
    return cmd + ["--home", str(home), "--port", str(port), "--no-browser", "--hosted"], env


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Door:
    """The door on the network: sign-in, then each person's own inPace behind it."""

    def __init__(self):
        self.server = None
        self.thread = None
        self.home: Path | None = None
        self.port = 0
        self.token = ""
        self.owner_name = ""
        self.sessions: dict[str, dict] = {}      # cookie -> {"user", "seen"}
        self.workers: dict[str, dict] = {}       # username -> {"proc", "port", "seen"}
        self.tries: dict[str, list[float]] = {}  # address -> times of failed sign-ins
        self.lock = threading.Lock()
        self.error = ""

    @property
    def running(self) -> bool:
        return bool(self.server and self.thread and self.thread.is_alive())

    def start(self, home: Path, port: int, owner_name: str = "") -> None:
        import uvicorn
        if self.running:
            return
        self.home, self.port, self.owner_name = Path(home), int(port), owner_name
        self.token = secrets.token_urlsafe(32)
        self.error = ""
        config = uvicorn.Config(door_app(self), host="0.0.0.0", port=self.port, log_level="warning",
                                proxy_headers=False, server_header=False)
        self.server = uvicorn.Server(config)
        self.server.install_signal_handlers = lambda: None  # it runs in a thread, beside inPace's own server

        def run():
            try:
                self.server.run()
            except (OSError, SystemExit) as e:
                self.error = str(e) or "The port is busy."
        self.thread = threading.Thread(target=run, name="inpace-door", daemon=True)
        self.thread.start()
        threading.Thread(target=self._sweep, name="inpace-door-sweep", daemon=True).start()
        for _ in range(50):
            if self.server.started or not self.thread.is_alive():
                break
            time.sleep(0.05)

    def stop(self) -> None:
        if self.server:
            self.server.should_exit = True
        for u in list(self.workers):
            self.stop_worker(u)
        self.sessions.clear()
        if self.thread:
            self.thread.join(timeout=5)
        self.server = self.thread = None

    # sessions
    def new_session(self, user: str) -> str:
        sid = secrets.token_urlsafe(32)
        self.sessions[sid] = {"user": user, "seen": time.time()}
        return sid

    def session_user(self, sid: str | None) -> str | None:
        s = self.sessions.get(sid or "")
        if not s or time.time() - s["seen"] > SESSION_IDLE or s["user"] not in load_users(self.home):
            self.sessions.pop(sid or "", None)
            return None
        s["seen"] = time.time()
        return s["user"]

    def end_sessions(self, user: str) -> None:
        for sid in [k for k, s in self.sessions.items() if s["user"] == user]:
            self.sessions.pop(sid, None)

    def too_many_tries(self, addr: str) -> bool:
        now = time.time()
        recent = [t for t in self.tries.get(addr, []) if now - t < TRY_WINDOW]
        self.tries[addr] = recent
        return len(recent) >= TRIES

    def failed(self, addr: str) -> None:
        self.tries.setdefault(addr, []).append(time.time())

    # each person's own inPace
    def worker_port(self, user: str) -> int:
        with self.lock:
            w = self.workers.get(user)
            if w and w["proc"].poll() is None:
                w["seen"] = time.time()
                return w["port"]
            port = _free_local_port()
            cmd, env = _command(user_home(self.home, user), port)
            flags = 0x08000000 if sys.platform == "win32" else 0  # no console window on Windows
            proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, creationflags=flags)
            self.workers[user] = {"proc": proc, "port": port, "seen": time.time()}
        for _ in range(300):  # up to 30 seconds for it to start
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return port
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        raise RuntimeError("That inPace didn't start.")

    def stop_worker(self, user: str) -> None:
        w = self.workers.pop(user, None)
        if w and w["proc"].poll() is None:
            w["proc"].terminate()
            try:
                w["proc"].wait(timeout=5)
            except subprocess.TimeoutExpired:
                w["proc"].kill()

    def _sweep(self) -> None:
        while self.running or (self.thread and self.thread.is_alive()):
            time.sleep(60)
            for u, w in list(self.workers.items()):
                if time.time() - w["seen"] > IDLE_STOP:
                    self.stop_worker(u)


DOOR = Door()


# ---- the door's pages, and passing pages on ----------------------------------------------------------------

LOGIN_PAGE = """<!doctype html>
<html lang="{lang}" dir="{dir}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><link rel="stylesheet" href="/static/style.css"><link rel="icon" href="/static/icon.svg"></head>
<body class="host-door"><main class="host-login card stack">
<p><img src="/static/icon.svg" width="44" height="44" alt=""></p>
<h1>{title}</h1>
<p class="muted">{lead}</p>
{err}
<form method="post" action="/host-login" class="stack">
<label>{l_user}<input name="username" autocomplete="username" required autocapitalize="none" spellcheck="false" dir="ltr"></label>
<label>{l_pass}<input name="password" type="password" autocomplete="current-password" required dir="ltr"></label>
<button class="btn primary big">{l_go}</button>
</form>
<p class="small muted">{note}</p>
</main></body></html>"""

WORDS = {
    "en": {"title": "Sign in to {owner}inPace", "lead": "inPace on this network. Ask the person who runs it for your username and password.",
           "user": "Username", "pass": "Password", "go": "Sign in",
           "note": "Your progress is kept on that computer, and the person who runs it can see it.",
           "bad": "That username and password don't match.", "slow": "Too many tries. Wait 10 minutes, then try again.",
           "busy": "Your inPace couldn't start on that computer. Try again in a minute."},
    "ar": {"title": "سجّل الدخول إلى inPace{owner}", "lead": "inPace على هذه الشبكة. اطلب اسم المستخدم وكلمة المرور من الشخص الذي يشغّله.",
           "user": "اسم المستخدم", "pass": "كلمة المرور", "go": "دخول",
           "note": "تقدّمك محفوظ على ذلك الجهاز، والشخص الذي يشغّله يقدر يراه.",
           "bad": "اسم المستخدم وكلمة المرور غير متطابقين.", "slow": "محاولات كثيرة. انتظر 10 دقائق ثم حاول مرة أخرى.",
           "busy": "تعذّر تشغيل inPace الخاص بك على ذلك الجهاز. حاول بعد دقيقة."},
}


def _words(accept: str) -> tuple[str, dict]:
    lang = "ar" if (accept or "").lower().startswith("ar") else "en"
    return lang, WORDS[lang]


def login_html(door: Door, accept: str, err: str = "") -> str:
    from html import escape
    lang, w = _words(accept)
    owner = escape(door.owner_name)
    title = w["title"].format(owner=(owner + "'s ") if lang == "en" and owner else (" " + owner if owner else ""))
    return LOGIN_PAGE.format(lang=lang, dir="rtl" if lang == "ar" else "ltr", title=title, lead=w["lead"],
                             err=f'<p class="note bad" role="alert">{escape(w[err])}</p>' if err else "",
                             l_user=w["user"], l_pass=w["pass"], l_go=w["go"], note=w["note"])


def door_app(door: Door):
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, RedirectResponse, Response
    from starlette.routing import Mount, Route
    from starlette.staticfiles import StaticFiles

    here = Path(__file__).resolve().parent

    def _cookie(resp: Response, sid: str, clear: bool = False) -> Response:
        if clear:
            resp.delete_cookie(COOKIE, path="/")
        else:
            resp.set_cookie(COOKIE, sid, httponly=True, samesite="strict", path="/", max_age=SESSION_IDLE)
        return resp

    async def login_page(request: Request):
        if door.session_user(request.cookies.get(COOKIE)):
            return RedirectResponse("/", status_code=303)
        return HTMLResponse(login_html(door, request.headers.get("accept-language", "")),
                            headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"})

    async def login(request: Request):
        addr = request.client.host if request.client else "?"
        accept = request.headers.get("accept-language", "")
        if door.too_many_tries(addr):
            return HTMLResponse(login_html(door, accept, "slow"), status_code=429)
        form = await request.form()
        user = str(form.get("username", "")).strip().lower()
        ok = await asyncio.get_running_loop().run_in_executor(
            None, check_login, door.home, user, str(form.get("password", "")))
        if not ok:
            door.failed(addr)
            return HTMLResponse(login_html(door, accept, "bad"), status_code=401)
        return _cookie(RedirectResponse("/", status_code=303), door.new_session(user))

    async def logout(request: Request):
        door.sessions.pop(request.cookies.get(COOKIE, ""), None)
        return _cookie(RedirectResponse("/host-login", status_code=303), "", clear=True)

    routes = [Route("/host-login", login_page), Route("/host-login", login, methods=["POST"]),
              Route("/host-logout", logout, methods=["POST", "GET"]),
              Mount("/static", StaticFiles(directory=here / "static"), name="static")]
    inner = Starlette(routes=routes)

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            return await inner(scope, receive, send)
        if scope["type"] != "http":
            return
        path = scope.get("path", "")
        if path.startswith(("/host-login", "/host-logout", "/static/")):
            return await inner(scope, receive, send)
        req = Request(scope)
        user = door.session_user(req.cookies.get(COOKIE))
        if not user:
            if scope["method"] == "GET" and "text/html" in req.headers.get("accept", "text/html"):
                return await RedirectResponse("/host-login", status_code=303)(scope, receive, send)
            return await Response("Sign in first.", status_code=401)(scope, receive, send)
        try:
            port = await asyncio.get_running_loop().run_in_executor(None, door.worker_port, user)
        except Exception:
            return await HTMLResponse(login_html(door, req.headers.get("accept-language", ""), "busy"),
                                      status_code=503)(scope, receive, send)
        await proxy(scope, receive, send, port, door.token)

    return app


HOP = {b"connection", b"keep-alive", b"proxy-connection", b"te", b"trailer", b"transfer-encoding", b"upgrade",
       b"host", b"x-inpace-host", b"x-forwarded-for"}


async def proxy(scope, receive, send, port: int, token: str) -> None:
    """Pass one request on to a person's own inPace and stream the answer back (videos too, with seeking).
    HTTP/1.0 to it, so its answer simply ends when the connection closes."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        target = scope.get("raw_path") or scope["path"].encode("utf-8")
        if scope.get("query_string"):
            target += b"?" + scope["query_string"]
        head = [f"{scope['method']} ".encode() + target + b" HTTP/1.0", f"Host: 127.0.0.1:{port}".encode(),
                f"X-Inpace-Host: {token}".encode(), b"Connection: close"]
        length = None
        for k, v in scope.get("headers") or []:
            k = k.lower()
            if k in HOP:
                continue
            if k == b"cookie":  # the door's own cookie stays at the door
                v = b"; ".join(c for c in v.split(b"; ") if not c.strip().startswith(COOKIE.encode() + b"="))
                if not v:
                    continue
            if k == b"content-length":
                length = int(v or 0)
            head.append(k + b": " + v)
        body_parts = []
        more = True
        if length is None:  # no length given (rare from a browser): read the whole body first
            while more:
                msg = await receive()
                body_parts.append(msg.get("body", b""))
                more = msg.get("more_body", False)
            body = b"".join(body_parts)
            if body:
                head.append(f"Content-Length: {len(body)}".encode())
            writer.write(b"\r\n".join(head) + b"\r\n\r\n" + body)
        else:
            writer.write(b"\r\n".join(head) + b"\r\n\r\n")
            while more:
                msg = await receive()
                writer.write(msg.get("body", b""))
                await writer.drain()
                more = msg.get("more_body", False)
        await writer.drain()
        status_line = await reader.readline()
        try:
            status = int(status_line.split(b" ")[1])
        except (IndexError, ValueError):
            status = 502
        headers = []
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            k, _, v = line.decode("latin-1").partition(":")
            k = k.strip().lower().encode("latin-1")
            if k in HOP:
                continue
            headers.append((k, v.strip().encode("latin-1")))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
    finally:
        writer.close()


def watch_the_door() -> None:
    """In a person's own inPace: stop when the door is gone (you quit inPace or turned host mode off), so
    nothing is left running on your computer."""
    port = int(os.environ.get("INPACE_DOOR_PORT") or 0)
    if not port:
        return
    misses, every = 0, float(os.environ.get("INPACE_DOOR_CHECK") or 20)
    while True:
        time.sleep(every)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            misses = 0 if s.connect_ex(("127.0.0.1", port)) == 0 else misses + 1
        if misses >= 3:
            os._exit(0)
