"""Builds the inPace Telegram group in one go, with the same topics as the Discord server.

You do three things by hand (a bot can't make a group):
  1. In Telegram: New Group, name it "inPace", add your bot (from @BotFather), create it.
  2. In the group: Edit > Topics: on. Edit > Group type: Public, link t.me/inPace_app (or another name).
  3. Edit > Administrators: make the bot an admin with every right turned on.

Then run:  python3 community/telegram_setup.py
It asks for the bot token and the group, then sets the inPace logo and description, makes the topics
(the bot-only ones are closed, so only admins and the bot post there), and posts and pins the welcome.
Running it again is safe: it remembers the topics it made in ~/inpace-telegram.txt and only adds what's missing.
At the end it prints the two GitHub secrets that make the automatic posts land in the right topics.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAVED = Path.home() / "inpace-telegram.txt"

# key (the same names the Discord hooks use), topic name, icon colour, closed (only admins and the bot write)
TOPICS = [
    ("welcome", "👋 Welcome and rules · أهلًا والقواعد", 0xFFD67E, True),
    ("announcements", "📣 Announcements · الإعلانات", 0xFF93B2, True),
    ("releases", "🚀 New versions · الإصدارات", 0x6FB9F0, True),
    ("courses", "📚 New courses and roadmaps · الدورات والمسارات الجديدة", 0x8EEE98, True),
    ("devlog", "🛠️ Dev log · سجل التطوير", 0xCB86DB, True),
    ("feedback", "🐞 Problems and ideas from GitHub · المشاكل والأفكار", 0xFB6F5F, True),
    ("introductions", "🙋 Introductions · عرّف بنفسك", 0x6FB9F0, False),
    ("progress", "🏆 Show your progress · شارك تقدّمك", 0xFFD67E, False),
    ("requests", "📝 Course requests · اطلب دورة", 0x8EEE98, False),
    ("ideas", "💡 Ideas · أفكار", 0xFFD67E, False),
    ("help", "🆘 Help · مساعدة", 0xFB6F5F, False),
    ("make", "✍️ Making courses · صناعة الدورات", 0xCB86DB, False),
    ("offtopic", "🎲 Anything else · أي شيء آخر", 0xFF93B2, False),
]
GENERAL = "💬 General chat · دردشة عامة"
DESCRIPTION = ("inPace: free, open-source learning app. Courses, roadmaps, news and help, in English and Arabic.\n"
               "inPace: تطبيق تعلّم مجاني ومفتوح المصدر. دورات ومسارات وأخبار ومساعدة، بالعربي والإنجليزي.")
WELCOME = """🐢 <b>Welcome to inPace!</b>
inPace is a free, open-source learning app. Your courses, roadmaps and progress stay on your own device.

<b>Get started</b>
• Download: https://mahmoudyosrimahmoud13.github.io/inPace/
• The course library: https://mahmoudyosrimahmoud13.github.io/inpace-library/
• Say hi in 🙋 Introductions, ask in 🆘 Help, and ask for courses in 📝 Course requests.
• New versions, courses and roadmaps are posted here by themselves.

<b>Rules</b>
1. Be kind. No insults, spam or ads.
2. Help others the way you'd like to be helped.
3. Share what you made and what you finished.
4. Keep each topic on its subject.

━━━━━━━━━━

🐢 <b>أهلًا بك في inPace!</b>
inPace تطبيق تعلّم مجاني ومفتوح المصدر. دوراتك ومساراتك وتقدّمك تبقى على جهازك.

<b>ابدأ من هنا</b>
• التحميل: https://mahmoudyosrimahmoud13.github.io/inPace/
• مكتبة الدورات: https://mahmoudyosrimahmoud13.github.io/inpace-library/
• عرّف بنفسك في 🙋، واسأل في 🆘 مساعدة، واطلب الدورات في 📝.
• الإصدارات والدورات والمسارات الجديدة تُنشر هنا تلقائيًا.

<b>القواعد</b>
1. كن لطيفًا. لا شتائم ولا إعلانات ولا رسائل مزعجة.
2. ساعد غيرك كما تحب أن يساعدك.
3. شارك ما صنعته وما أنهيته.
4. التزم بموضوع كل قسم."""


def call(token: str, method: str, fields: dict, photo: Path | None = None) -> dict:
    url = f"{os.environ.get('TELEGRAM_API', 'https://api.telegram.org')}/bot{token}/{method}"
    if photo:
        b = uuid.uuid4().hex
        body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items())
        body += (f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="{photo.name}"\r\n'
                 f'Content-Type: image/png\r\n\r\n').encode() + photo.read_bytes() + f"\r\n--{b}--\r\n".encode()
        ctype = f"multipart/form-data; boundary={b}"
    else:
        body, ctype = json.dumps(fields).encode(), "application/json"
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}")
        except ValueError:
            return {"ok": False, "description": str(e)}


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or getpass.getpass("Bot token (from @BotFather, hidden as you paste): ").strip()
    saved = json.loads(SAVED.read_text(encoding="utf-8")) if SAVED.is_file() else {}
    chat = os.environ.get("TELEGRAM_CHAT") or input(f"The group's link name [{saved.get('chat') or '@inPace_app'}]: ").strip() \
        or saved.get("chat") or "@inPace_app"
    if chat.startswith("https://t.me/") or chat.startswith("t.me/"):
        chat = "@" + chat.rsplit("/", 1)[1]
    me = call(token, "getMe", {})
    if not me.get("ok"):
        print("The token didn't work:", me.get("description")); return 1
    info = call(token, "getChat", {"chat_id": chat})
    if not info.get("ok"):
        print(f"Couldn't open {chat}: {info.get('description')}. Add @{me['result']['username']} to the group as an admin.")
        return 1
    g = info["result"]
    if g.get("type") == "channel":
        print(f"{chat} is a channel. Topics only exist in groups: make a group (step 1 at the top of this file).")
        return 1
    if not g.get("is_forum"):
        print("Topics are off. In the group: Edit > Topics: on. Then run this again.")
        return 1
    print(f"Group: {g.get('title')} ({chat}), bot @{me['result']['username']}")
    icon = ROOT / "community" / "server-icon.png"
    if icon.is_file():
        r = call(token, "setChatPhoto", {"chat_id": chat}, icon)
        print("  + logo" if r.get("ok") else f"  ! logo: {r.get('description')} (give the bot 'Change group info')")
    r = call(token, "setChatDescription", {"chat_id": chat, "description": DESCRIPTION})
    print("  + description" if r.get("ok") or "not modified" in str(r.get("description")) else f"  ! description: {r.get('description')}")
    call(token, "editGeneralForumTopic", {"chat_id": chat, "name": GENERAL})
    topics = dict(saved.get("topics") or {}) if saved.get("chat") == chat else {}
    for key, name, color, closed in TOPICS:
        if key in topics:
            r = call(token, "editForumTopic", {"chat_id": chat, "message_thread_id": topics[key], "name": name})
            if r.get("ok") or "not modified" in str(r.get("description")):
                continue
            topics.pop(key)  # deleted in Telegram: make it again
        r = call(token, "createForumTopic", {"chat_id": chat, "name": name, "icon_color": color})
        if not r.get("ok"):
            print(f"  ! {name}: {r.get('description')} (give the bot 'Manage topics')"); return 1
        topics[key] = r["result"]["message_thread_id"]
        if closed:
            call(token, "closeForumTopic", {"chat_id": chat, "message_thread_id": topics[key]})
        print("  +", name)
        if key == "welcome":
            m = call(token, "sendMessage", {"chat_id": chat, "message_thread_id": topics[key], "text": WELCOME,
                                            "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}})
            if m.get("ok"):
                call(token, "pinChatMessage", {"chat_id": chat, "message_id": m["result"]["message_id"],
                                               "disable_notification": True})
    SAVED.write_text(json.dumps({"chat": chat, "topics": topics}), encoding="utf-8")
    print(f"\nDone. Saved in {SAVED}.")
    print("\nAdd these as GitHub secrets, in BOTH repos (Settings > Secrets and variables > Actions):")
    print("  TELEGRAM_BOT_TOKEN   the bot token")
    print(f"  TELEGRAM_CHAT        {chat}")
    print(f"  TELEGRAM_TOPICS      {json.dumps(topics)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
