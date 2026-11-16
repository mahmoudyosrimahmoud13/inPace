"""Builds the inPace Discord server in one go.

You do two things by hand (Discord doesn't let a bot make a server):
  1. In Discord, press + and "Create My Own" to make an empty server.
  2. At https://discord.com/developers/applications make an app, open "Bot", press "Reset Token" and copy it.

Then run:  python3 community/discord_setup.py
It asks for the token, gives you a link to add the bot to your server, and builds everything:
channels in English and Arabic, language roles, rules, the welcome message, and the hooks that post
new releases, new courses, feedback and every push by themselves. Running it again is safe:
it only adds what's missing.

Only the Python that comes with your computer is needed. The token is never saved anywhere.
"""
from __future__ import annotations

import base64
import getpass
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

API = "https://discord.com/api/v10"
ROOT = Path(__file__).resolve().parent.parent
APP_REPO = "mahmoudyosrimahmoud13/inPace"
LIB_REPO = "mahmoudyosrimahmoud13/inpace-library"
SITE = "https://mahmoudyosrimahmoud13.github.io/inPace/"
LIBRARY = "https://mahmoudyosrimahmoud13.github.io/inpace-library/"
SECRETS_FILE = Path.home() / "inpace-discord-webhooks.txt"

# Permissions (Discord's numbers)
VIEW, SEND, REACT = 1 << 10, 1 << 11, 1 << 6
THREADS = (1 << 35) | (1 << 36) | (1 << 38)
TEXT, VOICE, CATEGORY, NEWS = 0, 2, 4, 5

ROLES = [  # name, color, shown apart in the member list
    ("Team", 0xFFD43B, True),
    ("Course maker", 0x1F9D6A, True),
    ("English", 0x5DADE2, False),
    ("العربية", 0xE6007E, False),
]

# category, [(channel, kind, topic, who can write)]   kind: text/news/voice   write: all/team/none
LAYOUT = [
    ("📌 Start here", [
        ("welcome", "text", "Welcome to inPace! أهلًا بك في inPace!", "team"),
        ("rules", "text", "Be kind, share what you made, help each other. كن لطيفًا، وشارك، وساعد غيرك.", "team"),
    ]),
    ("📣 News", [
        ("announcements", "news", "News from the inPace team. أخبار فريق inPace.", "team"),
        ("releases", "text", "Every new version of inPace, posted by itself. كل إصدار جديد ينشر هنا تلقائيًا.", "none"),
        ("new-courses", "text", "New courses and roadmaps in the library. الدورات والمسارات الجديدة في المكتبة.", "none"),
        ("dev-log", "text", "What we are building right now: every change, as it happens. ما نعمل عليه الآن.", "none"),
        ("feedback-feed", "text", "New problems, ideas and questions from GitHub. المشاكل والأفكار الجديدة من GitHub.", "none"),
    ]),
    ("💬 Everyone", [
        ("introductions", "text", "Say hi: who you are and what you're learning. عرّف بنفسك وبما تتعلمه.", "all"),
        ("show-your-progress", "text", "Finished a module? A milestone? Show it! أنهيت وحدة؟ شاركنا!", "all"),
        ("course-requests", "text", "Ask for a course you want in the library. اطلب دورة تريدها في المكتبة.", "all"),
        ("ideas", "text", "Ideas to make inPace better. أفكار لتحسين inPace.", "all"),
        ("off-topic", "text", "Anything else. أي شيء آخر.", "all"),
        ("Study together", "voice", "", "all"),
    ]),
    ("🇬🇧 English", [
        ("general", "text", "Chat in English.", "all"),
        ("help", "text", "Something not working? Ask here, with a screenshot if you can.", "all"),
        ("make-courses", "text", "Making a course? Share tips, ask for reviews.", "all"),
    ]),
    ("🇪🇬 العربية", [
        ("عام", "text", "دردشة بالعربية.", "all"),
        ("مساعدة", "text", "شيء لا يعمل؟ اسأل هنا، ومعك لقطة شاشة إن أمكن.", "all"),
        ("صناعة-الدورات", "text", "تصنع دورة؟ شارك النصائح واطلب رأي الآخرين.", "all"),
    ]),
    ("🔒 Team", [
        ("team-chat", "text", "Only the team sees this. Discord also sends its server news here.", "private"),
    ]),
]
DEFAULT_CHANNELS = ["welcome", "rules", "announcements", "releases", "new-courses", "dev-log", "feedback-feed",
                    "introductions", "show-your-progress", "course-requests", "ideas", "off-topic", "Study together"]
LANG_CHANNELS = {"English": ["general", "help", "make-courses"], "العربية": ["عام", "مساعدة", "صناعة-الدورات"]}
HOOKS = {"releases": "releases", "courses": "new-courses", "devlog": "dev-log", "feedback": "feedback-feed",
         "announcements": "announcements"}

WELCOME = f"""# Welcome to inPace 🐢
inPace is a free, open-source learning app. Courses, roadmaps and your progress live on your own device.

**Get started**
• Download the app: {SITE}#download
• Free courses and roadmaps: {LIBRARY}
• The guide: {SITE}guide.html

**Where to go**
• Say hi in <#introductions> and show what you finished in <#show-your-progress>
• Something not working? <#help> (English) or <#مساعدة> (العربية)
• Want a course? <#course-requests>. Made one? Share it: {LIBRARY}share.html
• <#releases>, <#new-courses> and <#dev-log> post by themselves, so you never miss a thing.

━━━━━━━━━━━━━━━━━━━━
# أهلًا بك في inPace 🐢
inPace تطبيق تعلّم مجاني ومفتوح المصدر. الدورات والمسارات وتقدّمك كلها على جهازك أنت.

**ابدأ من هنا**
• حمّل التطبيق: {SITE}#download
• دورات ومسارات مجانية: {LIBRARY}
• الدليل: {SITE}guide.html

**أين تذهب**
• عرّف بنفسك في <#introductions> وشاركنا تقدمك في <#show-your-progress>
• شيء لا يعمل؟ <#مساعدة> بالعربية أو <#help> بالإنجليزية
• تريد دورة؟ <#course-requests>. صنعت دورة؟ شاركها: {LIBRARY}share.html
"""

RULES = """# Rules · القواعد
1. **Be kind.** Everyone here is learning. No insults, no hate, no spam.
2. **Help with patience.** There are no stupid questions.
3. **Share only what you made**, or what you're allowed to share. No pirated courses or books.
4. **Problems:** say your system (Windows, Mac, Linux, Android), your inPace version, and add a screenshot.
5. **Stay on topic** in each channel. Anything else goes to <#off-topic>.

━━━━━━━━━━━━━━━━━━━━
1. **كن لطيفًا.** كلنا نتعلم. لا إهانات ولا كراهية ولا رسائل مزعجة.
2. **ساعد بصبر.** لا يوجد سؤال غبي.
3. **شارك فقط ما صنعته** أو ما يحق لك مشاركته. لا دورات ولا كتب مقرصنة.
4. **عند المشاكل:** اذكر نظامك (ويندوز، ماك، لينكس، أندرويد) ونسخة inPace، وأضف لقطة شاشة.
5. **التزم بموضوع كل قناة.** وأي شيء آخر في <#off-topic>.
"""


class Discord:
    """A tiny Discord API client: just what this script needs, with waiting when Discord says 'slow down'."""

    def __init__(self, token: str, opener=None):
        self.token = token
        self.open = opener or urllib.request.urlopen

    def __call__(self, method: str, path: str, body=None, quiet: bool = False):
        data = json.dumps(body).encode() if body is not None else None
        for _ in range(6):
            req = urllib.request.Request(API + path, data=data, method=method, headers={
                "Authorization": f"Bot {self.token}", "Content-Type": "application/json",
                "User-Agent": "DiscordBot (https://github.com/mahmoudyosrimahmoud13/inPace, 1.0)"})
            try:
                with self.open(req) as r:
                    raw = r.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", "replace")
                if e.code == 429:
                    try:
                        wait = float(json.loads(text).get("retry_after", 1))
                    except ValueError:
                        wait = 2
                    time.sleep(min(wait, 30) + 0.2)
                    continue
                if quiet:
                    return None
                raise SystemExit(f"\nDiscord said no ({e.code}) to {method} {path}:\n{text[:600]}") from None
        raise SystemExit("Discord kept asking us to slow down. Wait a minute and run this again.")


def snowflake() -> str:
    return str(((int(time.time() * 1000) - 1420070400000) << 22) | random.getrandbits(22))


def icon_data() -> str | None:
    p = ROOT / "community" / "server-icon.png"  # made for Discord's round pictures
    if not p.is_file():
        p = ROOT / "inpace" / "static" / "icon-256.png"
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode() if p.is_file() else None


def ask(question: str, default: bool = True) -> bool:
    if not sys.stdin.isatty():
        return default
    a = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not a else a.startswith("y")


def pick_guild(api: Discord, app_id: str, wanted: str | None) -> dict:
    guilds = api("GET", "/users/@me/guilds") or []
    if not guilds:
        link = f"https://discord.com/oauth2/authorize?client_id={app_id}&scope=bot&permissions=8"
        print("\nStep 2 of 3: add the bot to your new server.")
        print("  Open this link, choose your server, press Continue, then Authorize:\n")
        print("  " + link + "\n")
        try:
            webbrowser.open(link)
        except Exception:
            pass
        print("Waiting for the bot to join", end="", flush=True)
        for _ in range(300):
            time.sleep(3)
            print(".", end="", flush=True)
            guilds = api("GET", "/users/@me/guilds") or []
            if guilds:
                print(" joined!")
                break
        else:
            raise SystemExit("\nThe bot didn't join in 15 minutes. Open the link above, then run this again.")
    if wanted:
        for g in guilds:
            if g["id"] == wanted or g["name"] == wanted:
                return g
        raise SystemExit(f"The bot isn't in a server called {wanted}.")
    if len(guilds) == 1:
        return guilds[0]
    print("\nThe bot is in more than one server:")
    for i, g in enumerate(guilds, 1):
        print(f"  {i}. {g['name']}")
    n = input("Which one is the inPace server? Type its number: ").strip()
    return guilds[int(n) - 1]


def build(api: Discord, gid: str, log=print) -> dict:
    """Make every role, channel and message that's missing. Returns what other steps need."""
    guild = api("GET", f"/guilds/{gid}")
    roles = {r["name"]: r for r in api("GET", f"/guilds/{gid}/roles")}
    for name, color, hoist in ROLES:
        if name not in roles:
            roles[name] = api("POST", f"/guilds/{gid}/roles", {"name": name, "color": color, "hoist": hoist,
                                                             "mentionable": True, "permissions": "0"})
            log(f"  + role {name}")
    team = roles["Team"]["id"]

    channels = api("GET", f"/guilds/{gid}/channels")
    # Discord's empty starter channels: only removed when nothing has been said in them yet and you agree.
    starters = [c for c in channels if c["name"] in ("Text Channels", "Voice Channels", "general", "General")
                and (c["type"] == CATEGORY or not c.get("last_message_id"))
                and not any(p["name"] in ("🇬🇧 English",) and c.get("parent_id") == p["id"] for p in channels)]
    if starters and len(channels) <= 6 and ask("Remove Discord's empty starter channels (#general and the General voice room)?"):
        for c in starters:
            api("DELETE", f"/channels/{c['id']}", quiet=True)
        channels = api("GET", f"/guilds/{gid}/channels")
        log("  - starter channels removed")

    def find(name, kind=None, parent=None):
        for c in channels:
            if c["name"] == name and (kind is None or c["type"] == kind) and (parent is None or c.get("parent_id") == parent):
                return c
        return None

    ids = {}
    for pos, (cat_name, items) in enumerate(LAYOUT):
        cat = find(cat_name, CATEGORY)
        if not cat:
            over = []
            if cat_name == "🔒 Team":
                over = [{"id": gid, "type": 0, "allow": "0", "deny": str(VIEW)},
                        {"id": team, "type": 0, "allow": str(VIEW | SEND), "deny": "0"}]
            cat = api("POST", f"/guilds/{gid}/channels", {"name": cat_name, "type": CATEGORY, "position": pos,
                                                          "permission_overwrites": over})
            channels.append(cat)
            log(f"  + {cat_name}")
        for name, kind, topic, write in items:
            ch = find(name, None, cat["id"])
            if not ch:
                over = []
                if write in ("team", "none"):
                    over = [{"id": gid, "type": 0, "allow": str(VIEW | REACT), "deny": str(SEND | THREADS)},
                            {"id": team, "type": 0, "allow": str(SEND), "deny": "0"}]
                elif write == "private":
                    over = [{"id": gid, "type": 0, "allow": "0", "deny": str(VIEW)},
                            {"id": team, "type": 0, "allow": str(VIEW | SEND), "deny": "0"}]
                body = {"name": name, "type": VOICE if kind == "voice" else TEXT, "parent_id": cat["id"],
                        "permission_overwrites": over}
                if topic and kind != "voice":
                    body["topic"] = topic
                ch = api("POST", f"/guilds/{gid}/channels", body)
                channels.append(ch)
                log(f"    + #{name}")
            ids[name] = ch["id"]

    def mention(text):
        for name, cid in ids.items():
            text = text.replace(f"<#{name}>", f"<#{cid}>")
        return text

    # The first messages, posted once.
    me = api("GET", "/users/@me")["id"]
    for name, text in (("welcome", WELCOME), ("rules", RULES)):
        old = api("GET", f"/channels/{ids[name]}/messages?limit=20") or []
        if not any(m["author"]["id"] == me for m in old):
            parts = [mention(p) for p in text.split("━━━━━━━━━━━━━━━━━━━━")]
            for part in parts:
                m = api("POST", f"/channels/{ids[name]}/messages", {"content": part.strip()[:2000],
                                                                    "allowed_mentions": {"parse": []}})
            log(f"  + message in #{name}")

    # A Community server: language picking when people join (Onboarding), and #announcements others can follow.
    if "COMMUNITY" not in guild.get("features", []):
        feats = [f for f in guild.get("features", []) if f in ("COMMUNITY", "DISCOVERABLE", "INVITE_SPLASH", "NEWS")]
        ok = api("PATCH", f"/guilds/{gid}", {"features": feats + ["COMMUNITY"], "verification_level": 1,
                                              "explicit_content_filter": 2, "rules_channel_id": ids["rules"],
                                              "public_updates_channel_id": ids["team-chat"],
                                              "preferred_locale": "en-US"}, quiet=True)
        log("  + Community server turned on" if ok else "  ! Couldn't turn on Community (see the note at the end)")
        guild = api("GET", f"/guilds/{gid}")
    community = "COMMUNITY" in guild.get("features", [])
    if not guild.get("icon") and icon_data():
        api("PATCH", f"/guilds/{gid}", {"icon": icon_data()}, quiet=True)
        log("  + server picture")
    if community:
        ch = next((c for c in channels if c["id"] == ids["announcements"]), {})
        if ch.get("type") != NEWS and api("PATCH", f"/channels/{ids['announcements']}", {"type": NEWS}, quiet=True):
            log("  + #announcements can be followed from other servers")
        onboarding = {
            "prompts": [{
                "id": snowflake(), "type": 0, "title": "Which language do you speak? أي لغة تتحدث؟",
                "single_select": False, "required": True, "in_onboarding": True,
                "options": [
                    {"id": snowflake(), "title": "English", "description": "English channels",
                     "emoji_name": "🇬🇧", "role_ids": [roles["English"]["id"]], "channel_ids": [ids[c] for c in LANG_CHANNELS["English"]]},
                    {"id": snowflake(), "title": "العربية", "description": "القنوات العربية",
                     "emoji_name": "🇪🇬", "role_ids": [roles["العربية"]["id"]], "channel_ids": [ids[c] for c in LANG_CHANNELS["العربية"]]},
                ]}, {
                "id": snowflake(), "type": 0, "title": "Do you make courses too? هل تصنع دورات؟",
                "single_select": True, "required": False, "in_onboarding": True,
                "options": [
                    {"id": snowflake(), "title": "Yes, I make courses · نعم", "emoji_name": "🛠️",
                     "role_ids": [roles["Course maker"]["id"]], "channel_ids": [ids["make-courses"], ids["صناعة-الدورات"]]},
                    {"id": snowflake(), "title": "Not yet, I'm here to learn · ليس بعد", "emoji_name": "📚",
                     "role_ids": [], "channel_ids": []},
                ]}],
            "default_channel_ids": [ids[c] for c in DEFAULT_CHANNELS],
            "enabled": True, "mode": 0,
        }
        current = api("GET", f"/guilds/{gid}/onboarding", quiet=True) or {}
        if not current.get("prompts"):
            log("  + language question when people join" if api("PUT", f"/guilds/{gid}/onboarding", onboarding, quiet=True)
                else "  ! Couldn't set the join questions (you can do it in Server Settings > Onboarding)")

    # Webhooks: GitHub posts through these.
    hooks = {}
    pic = icon_data()
    for key, name in HOOKS.items():
        have = [w for w in (api("GET", f"/channels/{ids[name]}/webhooks") or []) if w.get("token")]
        w = have[0] if have else api("POST", f"/channels/{ids[name]}/webhooks",
                                     {"name": "inPace", **({"avatar": pic} if pic else {})})
        hooks[key] = f"https://discord.com/api/webhooks/{w['id']}/{w['token']}"
    log("  + automatic posts are ready")

    invite = api("POST", f"/channels/{ids['welcome']}/invites", {"max_age": 0, "max_uses": 0, "unique": False})
    return {"invite": f"https://discord.gg/{invite['code']}", "hooks": hooks, "community": community}


def write_site_page(invite: str) -> Path:
    page = ROOT / "site" / "discord.html"
    page.write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>inPace on Discord</title>
<meta name="description" content="Join the inPace community on Discord: help, course requests, new releases and new courses.">
<link rel="canonical" href="{SITE}discord.html">
<meta http-equiv="refresh" content="0; url={invite}">
<link rel="icon" href="assets/icon.svg" type="image/svg+xml">
<style>body{{font:18px/1.6 system-ui,sans-serif;background:#F7F3EA;color:#111;display:grid;place-items:center;min-height:90vh;margin:0;text-align:center}}a{{color:#111;font-weight:700}}</style>
</head><body><p>Opening the inPace Discord…<br><a href="{invite}">Press here if nothing happens</a><br>
<span dir="rtl">جارٍ فتح Discord… <a href="{invite}">اضغط هنا إن لم يحدث شيء</a></span></p></body></html>
""", encoding="utf-8")
    return page


def save_secrets(hooks: dict, token: str = "") -> str:
    """Give GitHub the webhooks (one secret in each repo) and the bot's token (app repo, for Tempo the bot).
    Uses the GitHub app 'gh' if you have it. Otherwise the webhooks go in a file, and the token is never written down."""
    value = json.dumps(hooks)
    if shutil.which("gh") and subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0:
        done = all(subprocess.run(["gh", "secret", "set", "DISCORD_WEBHOOKS", "-R", repo, "--body", value],
                                  capture_output=True).returncode == 0 for repo in (APP_REPO, LIB_REPO))
        if token:
            done = done and subprocess.run(["gh", "secret", "set", "DISCORD_BOT_TOKEN", "-R", APP_REPO, "--body", token],
                                           capture_output=True).returncode == 0
        if done:
            return "gh"
    SECRETS_FILE.write_text(value + "\n", encoding="utf-8")
    try:
        os.chmod(SECRETS_FILE, 0o600)
    except OSError:
        pass
    return "file"


def main(argv=None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    wanted = argv[argv.index("--server") + 1] if "--server" in argv else None
    print(__doc__.split("Then run:")[0].strip() + "\n")
    print("Step 1 of 3: paste the bot token (it won't show while you paste, that's normal).")
    token = os.environ.get("DISCORD_BOT_TOKEN") or getpass.getpass("Bot token: ").strip()
    if not token:
        raise SystemExit("No token, nothing to do.")
    api = Discord(token)
    app = api("GET", "/oauth2/applications/@me")
    guild = pick_guild(api, app["id"], wanted)
    print(f"\nStep 3 of 3: building “{guild['name']}”…")
    out = build(api, guild["id"])
    page = write_site_page(out["invite"])
    how = save_secrets(out["hooks"], token)
    reads = int(app.get("flags") or 0) & ((1 << 18) | (1 << 19))  # "Message Content Intent" is on

    print("\nDone! 🐢\n")
    print(f"  Invite link:  {out['invite']}")
    print(f"  Saved it in:  {page.relative_to(ROOT)}  (the website's Discord button opens it)")
    if how == "gh":
        print("  GitHub:       secrets set (DISCORD_WEBHOOKS in both repos, DISCORD_BOT_TOKEN for Tempo). All on.")
    else:
        print("\n  Last step, so GitHub can post and Tempo the bot can work. Add these secrets on GitHub:")
        print("    Settings > Secrets and variables > Actions > New repository secret")
        print(f"  In github.com/{APP_REPO}:")
        print(f"    Name: DISCORD_WEBHOOKS    Secret: everything inside {SECRETS_FILE}")
        print("    Name: DISCORD_BOT_TOKEN   Secret: the bot token you pasted above")
        print(f"  In github.com/{LIB_REPO}:")
        print("    Name: DISCORD_WEBHOOKS    Secret: the same as above")
        print("  Then delete that file. Anyone with it could post in your channels.")
    if not reads:
        print("\n  Tempo needs to read messages to help people and find problems. Turn it on once:")
        print(f"    https://discord.com/developers/applications/{app['id']}/bot  >  Message Content Intent  >  Save")
    if not out["community"]:
        print("\n  Note: Discord didn't let the bot turn on Community. In Discord: Server Settings > Enable Community,")
        print("  then run this command again to add the language question for new members.")
    print("\n  Keep the bot in the server: it's Tempo, who answers people and writes your morning report.")
    print("  Optional: add the secret ANTHROPIC_API_KEY in the app repo, and Claude adds 'fix this first, and why' to it.")


if __name__ == "__main__":
    main()
