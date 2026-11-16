"""Tempo, the inPace Discord bot. GitHub runs it every 20 minutes and every morning (.github/workflows/bot.yml).

What it does:
  * Morning report in #team-chat: what to fix first (problems from Discord and GitHub, grouped and ranked),
    questions nobody answered, the most liked ideas, course requests, and the numbers (stars, downloads, members).
  * Helps people in #help and #مساعدة right away when it knows the answer (black video on Linux, MKV files,
    YouTube refusing to play, subtitles, installing on Windows, Mac and Android…), in their language.
  * React 🐞 to any message (if you're on the Team) and it opens a GitHub issue with it, then tells the person.
    When that issue is closed, it tells them it's fixed.
  * Type !report, !fix or !help in #team-chat for a report now.
  * With the secret ANTHROPIC_API_KEY, Claude also writes a short "fix this first, and why" at the top of the report.

It needs the secret DISCORD_BOT_TOKEN, and "Message Content Intent" turned on for the bot
(discord.com/developers > your app > Bot). Without the token it does nothing.
It keeps no files: what it has handled is marked with its own reactions on the messages (👀, ✅, 🎉).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://discord.com/api/v10"
GH = "https://api.github.com"
APP_REPO = os.environ.get("APP_REPO", "mahmoudyosrimahmoud13/inPace")
LIB_REPO = os.environ.get("LIB_REPO", "mahmoudyosrimahmoud13/inpace-library")
SITE = "https://mahmoudyosrimahmoud13.github.io/inPace/"
LIBRARY = "https://mahmoudyosrimahmoud13.github.io/inpace-library/"
HELP_CHANNELS = ("help", "مساعدة")
LISTEN = ("help", "مساعدة", "ideas", "course-requests", "general", "عام", "make-courses", "صناعة-الدورات", "show-your-progress")
SEEN, DONE, FIXED, BUG = "👀", "✅", "🎉", "🐞"
YELLOW, PINK, GREEN, BLUE = 0xFFD43B, 0xE6007E, 0x1F9D6A, 0x5DADE2
AR = re.compile(r"[؀-ۿ]")

# ---------------------------------------------------------------- what people talk about

TOPICS = [  # (key, English name, Arabic name, words that point to it)
    ("video", "Videos and YouTube", "الفيديو ويوتيوب",
     r"video|youtube|play(er|ing)?\b|black screen|mkv|avi|mp4|subtitle|srt|فيديو|يوتيوب|مشغل|ترجمة|الشاشة سوداء"),
    ("install", "Installing and updating", "التثبيت والتحديث",
     r"install|update|upgrade|download(ed|ing)? the app|setup|\.deb|\.exe|dmg|smartscreen|unidentified|won.?t open|تثبيت|تحديث|تنزيل التطبيق|مش بيفتح|لا يفتح"),
    ("android", "Android and phones", "أندرويد والهاتف",
     r"android|phone|mobile|apk|tablet|اندرويد|أندرويد|موبايل|الهاتف|التليفون"),
    ("library", "Courses and the library", "الدورات والمكتبة",
     r"course|library|roadmap|lesson|quiz|module|دورة|كورس|المكتبة|مسار|درس|اختبار"),
    ("people", "Checking, people and races", "المتابعة والأشخاص والسباقات",
     r"checker|milestone|race|friend|sign(ed)?|verify|متابع|محطة|سباق|صديق"),
    ("ai", "AI course maker", "صانع الدورات بالذكاء الاصطناعي",
     r"\bai\b|claude|chatgpt|gemini|prompt|ذكاء|الذكاء الاصطناعي"),
    ("language", "Arabic and languages", "العربية واللغات",
     r"arabic|rtl|translation|language|عربي|العربية|اللغة|الترجمة العربية"),
    ("data", "Data, backups and files", "البيانات والنسخ الاحتياطي",
     r"backup|data|lost|delete|file|folder|progress gone|نسخة احتياطية|بيانات|اتمسح|ضاع|مجلد|ملف"),
]
PROBLEM = re.compile(r"not work|doesn.?t|didn.?t|can.?t|cannot|won.?t|isn.?t (work|load|open|play)|"
                     r"don.?t (seem to )?(work|open|play|load|show|start|save)|no sound|error|crash|bug|broken|stuck|freez|black|fail|"
                     r"problem|issue|wrong|missing|مش شغال|مش بيشتغل|لا يعمل|مشكلة|خطأ|عطل|بايظ|معلق|مش راضي|لا يفتح|مش بيفتح",
                     re.I)
IDEA = re.compile(r"would be (cool|nice|great)|feature|idea|suggest|please add|could you add|wish|it would|"
                  r"اقتراح|فكرة|ياريت|يا ريت|أتمنى|اتمنى|ممكن تضيف|لو تضيف", re.I)


def topic_of(text: str) -> str:
    low = text.lower()
    best, hits = "other", 0
    for key, _, _, words in TOPICS:
        n = len(re.findall(words, low))
        if n > hits:
            best, hits = key, n
    return best


def topic_name(key: str) -> str:
    for k, en, ar, _ in TOPICS:
        if k == key:
            return f"{en} · {ar}"
    return "Other · أخرى"


def kind_of(text: str, channel: str = "", labels=()) -> str:
    labels = [x.lower() for x in labels]
    if channel == "course-requests" or "course-request" in labels:
        return "course"
    if "bug" in labels or "problem" in labels or text.lower().startswith("problem:"):
        return "problem"
    if channel == "ideas" or "enhancement" in labels or "idea" in labels or text.lower().startswith("idea"):
        return "idea"
    if PROBLEM.search(text):
        return "problem"
    if IDEA.search(text):
        return "idea"
    return "question" if "?" in text or "؟" in text else "chat"


# ---------------------------------------------------------------- answers it knows

FAQ = [
    {"when": r"(video|فيديو).{0,60}(black|blank|not (play|work|show)|doesn.?t (play|work)|مش شغال|لا يعمل|سود)|black screen|الشاشة سوداء",
     "en": "If videos stay black or don't play, update inPace first: version 1.27 explains exactly what's wrong on the video itself.\n"
           "• **Linux:** the app window needs video support. Run this once, then restart inPace:\n"
           "`sudo apt install gstreamer1.0-libav gstreamer1.0-plugins-bad`\n"
           "• **MKV, AVI or H.265 files:** press **Open in your video player**, or convert them to MP4 with HandBrake (free).",
     "ar": "إن بقي الفيديو أسود أو لم يعمل، حدّث inPace أولًا: نسخة 1.27 تشرح على الفيديو نفسه ما المشكلة بالضبط.\n"
           "• **لينكس:** نافذة التطبيق تحتاج دعم الفيديو. نفّذ هذا الأمر مرة واحدة ثم أعد تشغيل inPace:\n"
           "`sudo apt install gstreamer1.0-libav gstreamer1.0-plugins-bad`\n"
           "• **ملفات MKV أو AVI أو H.265:** اضغط **افتحه في مشغّل الفيديو عندك**، أو حوّلها إلى MP4 ببرنامج HandBrake المجاني."},
    {"when": r"\b(mkv|avi|wmv|flv|hevc|h\.?265)\b|(long|large|big|bigger|longer).{0,30}video",
     "en": "Some video formats (MKV, AVI, H.265) don't play inside the app window. In inPace 1.27 the player says so and gives you "
           "**Open in your video player**. To make them play inside inPace, convert them to MP4 (H.264) with HandBrake, it's free.",
     "ar": "بعض صيغ الفيديو (MKV و AVI و H.265) لا تعمل داخل نافذة التطبيق. في inPace 1.27 يخبرك المشغّل بذلك ويعطيك زر "
           "**افتحه في مشغّل الفيديو عندك**. ولتعمل داخل inPace حوّلها إلى MP4 (H.264) ببرنامج HandBrake المجاني."},
    {"when": r"youtube.{0,60}(error|unavailable|won.?t|not (play|work)|configuration|15[0-3])|يوتيوب.{0,40}(خطأ|مش شغال|لا يعمل)",
     "en": "Some YouTube videos block playing inside other apps. Press **Watch it on YouTube** under the video, or **Download this video** "
           "to keep a copy that plays inside inPace without internet.",
     "ar": "بعض فيديوهات يوتيوب لا تسمح بالتشغيل داخل تطبيقات أخرى. اضغط **شاهده على يوتيوب** تحت الفيديو، أو **حمّل هذا الفيديو** "
           "لتحتفظ بنسخة تعمل داخل inPace بدون إنترنت."},
    {"when": r"subtitle|\bsrt\b|\bvtt\b|caption|ترجمة الفيديو|ملف ترجمة|الترجمة",
     "en": "Since inPace 1.27: put the subtitle file next to the video with the same name (`Lesson 1.srt`, or `Lesson 1.ar.srt` for Arabic) "
           "and it shows up by itself. Or press **CC** on the player, then **Add a subtitle file**.",
     "ar": "من نسخة inPace 1.27: ضع ملف الترجمة بجانب الفيديو بالاسم نفسه (`Lesson 1.srt`، أو `Lesson 1.ar.srt` للعربية) "
           "فيظهر تلقائيًا. أو اضغط **CC** في المشغّل ثم **أضف ملف ترجمة**."},
    {"when": r"playlist|(add|import).{0,30}youtube|بلاي ?ليست|قائمة تشغيل",
     "en": "To learn from YouTube: **Add a course → Links**, paste the links (one per line). A long video can be cut at its chapters: "
           "paste the chapter times under its link. For a whole playlist with notes and quizzes, use **Make a course with AI → A YouTube playlist**.",
     "ar": "للتعلّم من يوتيوب: **أضف دورة ← روابط**، والصق الروابط (رابط في كل سطر). ويمكن تقسيم الفيديو الطويل حسب فصوله: "
           "الصق أوقات الفصول تحت رابطه. ولقائمة تشغيل كاملة مع ملاحظات واختبارات استخدم **اصنع دورة بالذكاء الاصطناعي ← قائمة تشغيل يوتيوب**."},
    {"when": r"smartscreen|windows protected|windows.{0,30}(block|virus|defender)|ويندوز.{0,30}(حماية|منع|فيروس)",
     "en": "Windows shows that for new apps that aren't signed yet. Press **More info**, then **Run anyway**. inPace is open source: "
           "anyone can read its code on GitHub.",
     "ar": "يظهر هذا في ويندوز مع التطبيقات الجديدة غير الموقّعة بعد. اضغط **More info** ثم **Run anyway**. inPace مفتوح المصدر: "
           "أي شخص يستطيع قراءة كوده على GitHub."},
    {"when": r"(mac|macos).{0,40}(can.?t be opened|unidentified|damaged|won.?t open)|ماك.{0,30}(لا يفتح|مش بيفتح)",
     "en": "On a Mac, the first time: right-click inPace in Applications, choose **Open**, then **Open** again. "
           "If it still says it's damaged, open **System Settings → Privacy & Security** and press **Open Anyway**.",
     "ar": "على الماك أول مرة: اضغط بالزر الأيمن على inPace في Applications واختر **Open** ثم **Open** مرة أخرى. "
           "وإن ظهر أنه تالف، افتح **System Settings ← Privacy & Security** واضغط **Open Anyway**."},
    {"when": r"(apk|android|اندرويد|أندرويد).{0,50}(not installed|can.?t install|blocked|install|تثبيت|مش بيتثبت)",
     "en": f"For Android: download **inPace-android-arm64-v8a.apk** from {SITE}#download, open it, and allow installing from your browser "
           "when your phone asks. Older phone? The other files are on the release page.",
     "ar": f"لأندرويد: حمّل **inPace-android-arm64-v8a.apk** من {SITE}#download وافتحه، واسمح بالتثبيت من المتصفح عندما يسألك الهاتف. "
           "هاتف قديم؟ الملفات الأخرى في صفحة الإصدار."},
    {"when": r"how.{0,20}update|new version|latest version|إزاي احدث|كيف احدث|نسخة جديدة|آخر نسخة|اخر نسخة",
     "en": f"inPace tells you when a new version is out, and on Windows, Mac and Linux it can update itself: **Settings → Updates**. "
           f"Or download it again from {SITE}#download, your courses and progress stay.",
     "ar": f"يخبرك inPace عند صدور نسخة جديدة، وعلى ويندوز وماك ولينكس يمكنه تحديث نفسه: **الإعدادات ← التحديثات**. "
           f"أو حمّله من جديد من {SITE}#download، وتبقى دوراتك وتقدّمك كما هي."},
    {"when": r"backup|move.{0,30}(computer|laptop|pc)|new (computer|laptop)|lost my progress|نسخة احتياطية|جهاز جديد|انقل",
     "en": "**Settings → Backups** saves everything (courses, progress, milestones) in one file locked with a password. "
           "Open that file in inPace on the other device to bring it all back.",
     "ar": "**الإعدادات ← النسخ الاحتياطية** تحفظ كل شيء (الدورات والتقدّم والمحطات) في ملف واحد مقفول بكلمة سر. "
           "افتح هذا الملف في inPace على الجهاز الآخر ليرجع كل شيء."},
    {"when": r"(share|publish|upload).{0,30}(course|my course)|(انشر|ارفع|شارك).{0,20}(دورة|كورس)",
     "en": f"To share your course with everyone: in **My courses**, open **More** on the course, choose **Publish to the library**, "
           f"then follow the form: {LIBRARY}share.html",
     "ar": f"لمشاركة دورتك مع الجميع: في **دوراتي** افتح **المزيد** على الدورة واختر **انشر في المكتبة**، ثم أكمل النموذج: {LIBRARY}share.html"},
]


def faq_answer(text: str) -> dict | None:
    low = text.lower()
    for f in FAQ:
        if re.search(f["when"], low, re.I):
            return f
    return None


# ---------------------------------------------------------------- talking to Discord and GitHub

class Http:
    def __init__(self, opener=None):
        self.open = opener or urllib.request.urlopen

    def call(self, method, url, headers, body=None, quiet=False):
        data = json.dumps(body).encode() if body is not None else None
        for _ in range(5):
            req = urllib.request.Request(url, data=data, method=method, headers={**headers, "Content-Type": "application/json"})
            try:
                with self.open(req) as r:
                    raw = r.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", "replace")
                if e.code == 429:
                    try:
                        time.sleep(min(float(json.loads(text).get("retry_after", 1)), 20) + 0.2)
                    except ValueError:
                        time.sleep(2)
                    continue
                if quiet:
                    return None
                raise RuntimeError(f"{method} {url} -> {e.code}: {text[:300]}") from None
        return None


class Bot:
    def __init__(self, token: str, gh_token: str = "", http: Http | None = None, now: datetime | None = None, ai_key: str = ""):
        self.http = http or Http()
        self.token, self.gh_token, self.ai_key = token, gh_token, ai_key
        self.now = now or datetime.now(timezone.utc)
        self.me = self.d("GET", "/users/@me")
        guilds = self.d("GET", "/users/@me/guilds") or []
        if not guilds:
            raise SystemExit("The bot isn't in a server.")
        self.guild = self.d("GET", f"/guilds/{guilds[0]['id']}?with_counts=true")
        self.gid = self.guild["id"]
        self.channels = {c["name"]: c for c in self.d("GET", f"/guilds/{self.gid}/channels") if c.get("type") in (0, 5)}
        roles = self.d("GET", f"/guilds/{self.gid}/roles") or []
        self.team_role = next((r["id"] for r in roles if r["name"] == "Team"), None)
        self._team_cache: dict[str, bool] = {}

    # Discord
    def d(self, method, path, body=None, quiet=False):
        return self.http.call(method, API + path, {"Authorization": f"Bot {self.token}",
                                                   "User-Agent": "DiscordBot (https://github.com/mahmoudyosrimahmoud13/inPace, 1.0)"},
                              body, quiet)

    def say(self, channel: str, content: str = "", embeds=None, reply_to: str | None = None):
        ch = self.channels.get(channel)
        if not ch:
            return None
        body = {"content": content[:2000], "allowed_mentions": {"parse": [], "replied_user": True}}
        if embeds:
            body["embeds"] = embeds[:10]
        if reply_to:
            body["message_reference"] = {"message_id": reply_to, "fail_if_not_exists": False}
        return self.d("POST", f"/channels/{ch['id']}/messages", body)

    def react(self, channel_id: str, msg_id: str, emoji: str):
        self.d("PUT", f"/channels/{channel_id}/messages/{msg_id}/reactions/{urllib.parse.quote(emoji)}/@me", quiet=True)

    def mine(self, msg: dict, emoji: str) -> bool:
        return any(r.get("me") and r["emoji"].get("name") == emoji for r in msg.get("reactions", []))

    def count(self, msg: dict, emoji: str) -> int:
        return sum(r.get("count", 0) for r in msg.get("reactions", []) if r["emoji"].get("name") == emoji)

    def messages(self, channel: str, days: float = 7, limit: int = 100) -> list[dict]:
        ch = self.channels.get(channel)
        if not ch:
            return []
        got = self.d("GET", f"/channels/{ch['id']}/messages?limit={limit}", quiet=True) or []
        since = self.now - timedelta(days=days)
        out = []
        for m in got:
            m["_channel"], m["_channel_id"] = channel, ch["id"]
            if parse_time(m["timestamp"]) >= since:
                out.append(m)
        return out

    def is_team(self, user_id: str) -> bool:
        if user_id in self._team_cache:
            return self._team_cache[user_id]
        ok = user_id == self.guild.get("owner_id")
        if not ok and self.team_role:
            member = self.d("GET", f"/guilds/{self.gid}/members/{user_id}", quiet=True) or {}
            ok = self.team_role in member.get("roles", [])
        self._team_cache[user_id] = ok
        return ok

    def link(self, m: dict) -> str:
        return f"https://discord.com/channels/{self.gid}/{m['_channel_id']}/{m['id']}"

    # GitHub
    def g(self, method, path, body=None, quiet=True):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "inPace-bot"}
        if self.gh_token:
            headers["Authorization"] = f"Bearer {self.gh_token}"
        return self.http.call(method, GH + path, headers, body, quiet)

    # ------------------------------------------------------------ every 20 minutes

    def watch(self) -> dict:
        done = {"helped": 0, "issues": 0, "fixed": 0, "commands": 0}
        for name in HELP_CHANNELS:
            for m in reversed(self.messages(name, days=2, limit=50)):
                if m["author"].get("bot") or self.mine(m, SEEN) or m.get("type") not in (0, 19, None):
                    continue
                text = m.get("content") or ""
                ans = faq_answer(text)
                if ans and not self.is_team(m["author"]["id"]):
                    ar = bool(AR.search(text)) or name == "مساعدة"
                    tail = ("\n\n_إن لم يحل هذا المشكلة، سيرد عليك الفريق هنا قريبًا. ولو أمكن أرسل لقطة شاشة ونظامك ونسخة inPace._" if ar else
                            "\n\n_If this doesn't fix it, the team will reply here soon. A screenshot, your system and your inPace version help a lot._")
                    self.say(name, "🐢 " + (ans["ar"] if ar else ans["en"]) + tail, reply_to=m["id"])
                    done["helped"] += 1
                self.react(m["_channel_id"], m["id"], SEEN)
        done["issues"] = self.bugs_to_issues()
        done["fixed"] = self.tell_fixed()
        done["commands"] = self.commands()
        return done

    def bugs_to_issues(self) -> int:
        """🐞 from someone on the Team -> a GitHub issue, and a reply with its link."""
        made = 0
        for name in LISTEN:
            for m in self.messages(name, days=14, limit=100):
                if not self.count(m, BUG) or self.mine(m, DONE):
                    continue
                who = self.d("GET", f"/channels/{m['_channel_id']}/messages/{m['id']}/reactions/{urllib.parse.quote(BUG)}", quiet=True) or []
                if not any(self.is_team(u["id"]) for u in who):
                    continue
                text = (m.get("content") or "").strip()
                pics = [a["url"] for a in m.get("attachments", []) if str(a.get("content_type", "")).startswith("image/")]
                title = re.sub(r"\s+", " ", text)[:80] or "Problem reported on Discord"
                body = (f"Reported on Discord by **{m['author'].get('global_name') or m['author']['username']}** in #{name}:\n\n"
                        + "\n".join("> " + line for line in (text or "(no text)").splitlines())
                        + "".join(f"\n\n![screenshot]({p})" for p in pics[:4])
                        + f"\n\n[Open the message]({self.link(m)})\n<!-- discord:{m['_channel_id']}/{m['id']} -->")
                if not made:  # once: make sure the label exists (it's how closed issues are found again)
                    self.g("POST", f"/repos/{APP_REPO}/labels", {"name": "from-discord", "color": "5865F2",
                                                                 "description": "Reported on the inPace Discord"})
                issue = self.g("POST", f"/repos/{APP_REPO}/issues", {"title": title, "body": body, "labels": ["from-discord"]})
                if not issue:
                    continue
                ar = bool(AR.search(text))
                self.say(name, (f"🐞 شكرًا! أضفنا هذه المشكلة لقائمة الإصلاح: <{issue['html_url']}>. سنخبرك هنا عندما تُحل." if ar else
                                f"🐞 Thanks! This is now on our fix list: <{issue['html_url']}>. We'll tell you here when it's fixed."),
                         reply_to=m["id"])
                self.react(m["_channel_id"], m["id"], DONE)
                made += 1
        return made

    def tell_fixed(self) -> int:
        """Issues that came from Discord and were closed since yesterday: tell the person who reported it."""
        since = (self.now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        items = self.g("GET", f"/repos/{APP_REPO}/issues?state=closed&labels=from-discord&since={since}&per_page=50") or []
        told = 0
        for it in items:
            mm = re.search(r"<!-- discord:(\d+)/(\d+) -->", it.get("body") or "")
            if not mm or it.get("state_reason") == "not_planned":
                continue
            cid, mid = mm.groups()
            msg = self.d("GET", f"/channels/{cid}/messages/{mid}", quiet=True)
            if not msg or self.mine(msg, FIXED):
                continue
            ar = bool(AR.search(msg.get("content") or ""))
            ch = next((n for n, c in self.channels.items() if c["id"] == cid), None)
            if ch:
                self.say(ch, (f"🎉 تم إصلاح هذه المشكلة! سيصل الإصلاح في النسخة القادمة. <{it['html_url']}>" if ar else
                              f"🎉 Fixed! It comes in the next version. <{it['html_url']}>"), reply_to=mid)
            self.react(cid, mid, FIXED)
            told += 1
        return told

    def commands(self) -> int:
        n = 0
        for m in reversed(self.messages("team-chat", days=1, limit=30)):
            cmd = (m.get("content") or "").strip().lower()
            if not cmd.startswith("!") or self.mine(m, DONE) or m["author"].get("bot"):
                continue
            if cmd.startswith(("!report", "!تقرير")):
                self.report(full=True)
            elif cmd.startswith(("!fix", "!اصلاح", "!إصلاح")):
                self.report(full=False)
            elif cmd.startswith(("!help", "!مساعدة")):
                self.say("team-chat", "**Tempo's commands** (I check every 20 minutes):\n"
                                      "`!report` everything: what to fix, unanswered questions, ideas, requests, numbers\n"
                                      "`!fix` only what to fix first\n"
                                      "React 🐞 to any message to turn it into a GitHub issue.")
            else:
                continue
            self.react(m["_channel_id"], m["id"], DONE)
            n += 1
        return n

    # ------------------------------------------------------------ the morning report

    def gather(self) -> list[dict]:
        """Everything people said this week, from Discord and GitHub, as one list."""
        items = []
        for name in LISTEN:
            msgs = self.messages(name, days=7)
            replied = {(m.get("message_reference") or {}).get("message_id") for m in msgs}
            for m in msgs:
                if m["author"].get("bot") or self.is_team(m["author"]["id"]):
                    continue
                text = (m.get("content") or "").strip()
                if len(text) < 8:
                    continue
                k = kind_of(text, name)
                if k == "chat":
                    continue
                items.append({"source": "discord", "where": f"#{name}", "kind": k, "topic": topic_of(text),
                              "text": text, "url": self.link(m), "votes": self.count(m, "👍") + self.count(m, "➕"),
                              "time": parse_time(m["timestamp"]), "who": m["author"].get("global_name") or m["author"]["username"],
                              "answered": m["id"] in replied or self.mine(m, DONE)})
        for repo in (APP_REPO, LIB_REPO):
            for it in self.g("GET", f"/repos/{repo}/issues?state=open&per_page=100") or []:
                if "pull_request" in it:
                    continue
                labels = [lb["name"] for lb in it.get("labels", [])]
                text = f"{it['title']}\n{it.get('body') or ''}"
                k = kind_of(text, "", labels)
                if "course-submission" in labels or "roadmap-submission" in labels:
                    k = "submission"
                items.append({"source": "github", "where": repo.split("/")[1], "kind": k if k != "chat" else "question",
                              "topic": topic_of(text), "text": it["title"], "url": it["html_url"],
                              "votes": (it.get("reactions") or {}).get("+1", 0) + it.get("comments", 0),
                              "time": parse_time(it["created_at"]), "who": it["user"]["login"],
                              "answered": it.get("comments", 0) > 0})
        return items

    def numbers(self) -> list[str]:
        out = []
        repo = self.g("GET", f"/repos/{APP_REPO}") or {}
        if repo:
            out.append(f"⭐ {repo.get('stargazers_count', 0)} stars · 🍴 {repo.get('forks_count', 0)} forks · "
                       f"🐞 {repo.get('open_issues_count', 0)} open issues")
        rel = self.g("GET", f"/repos/{APP_REPO}/releases?per_page=1") or []
        if rel:
            r = rel[0]
            by = {}
            for a in r.get("assets", []):
                n = a["name"].lower()
                kind = ("Windows" if "windows" in n else "Mac" if "mac" in n else "Android" if "android" in n or n.endswith(".apk")
                        else "Linux" if "linux" in n else None)
                if kind:
                    by[kind] = by.get(kind, 0) + a.get("download_count", 0)
            total = sum(by.values())
            out.append(f"⬇️ {r['tag_name']}: {total} downloads (" + ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda x: -x[1])) + ")")
        if self.guild.get("approximate_member_count"):
            out.append(f"👥 {self.guild['approximate_member_count']} people on Discord, {self.guild.get('approximate_presence_count', 0)} online now")
        try:
            with urllib.request.urlopen(LIBRARY + "stats.json", timeout=20) as r:
                st = json.load(r)
            out.append(f"📚 Library: {st['courses']} courses, {st['roadmaps']} roadmaps, {st['lessons']} lessons")
        except Exception:
            pass
        return out

    def report(self, full: bool = True) -> dict:
        items = self.gather()
        fresh = self.now - timedelta(days=1)
        problems = [i for i in items if i["kind"] == "problem"]
        groups: dict[str, list] = {}
        for p in problems:
            groups.setdefault(p["topic"], []).append(p)
        # Rank: how many people hit it, how many agree, how new it is, and whether nobody answered yet.
        def score(g):
            return sum(2 + i["votes"] + (2 if i["time"] >= fresh else 0) + (1 if not i["answered"] else 0) for i in g)
        ranked = sorted(groups.items(), key=lambda kv: -score(kv[1]))
        lines = []
        for n, (topic, g) in enumerate(ranked[:6], 1):
            g = sorted(g, key=lambda i: (-i["votes"], -i["time"].timestamp()))
            new = sum(1 for i in g if i["time"] >= fresh)
            head = f"**{n}. {topic_name(topic)}**: {len(g)} report{'s' if len(g) != 1 else ''}" + (f" (🆕 {new} today)" if new else "")
            ex = "\n".join(f"   • [{short(i['text'], 90)}]({i['url']}) · {i['where']}" for i in g[:3])
            lines.append(head + "\n" + ex)
        embeds = []
        if self.ai_key and items:
            advice = self.ai_advice(items)
            if advice:
                embeds.append({"title": "🧠 Claude's take: fix this first", "description": advice[:4000], "color": BLUE})
        embeds.append({"title": "🔥 What to fix first", "color": PINK,
                       "description": "\n".join(lines)[:4000] or "No problems reported this week. 🎉"})
        if full:
            waiting = sorted([i for i in items if i["source"] == "discord" and not i["answered"] and i["kind"] in ("problem", "question")
                              and i["time"] <= self.now - timedelta(hours=12)], key=lambda i: i["time"])
            if waiting:
                embeds.append({"title": f"⏳ Waiting for an answer ({len(waiting)})", "color": YELLOW,
                               "description": "\n".join(f"• [{short(i['text'], 80)}]({i['url']}) · {i['who']} · {ago(i['time'], self.now)}"
                                                        for i in waiting[:10])[:4000]})
            ideas = sorted([i for i in items if i["kind"] == "idea"], key=lambda i: -i["votes"])
            if ideas:
                embeds.append({"title": "💡 Most wanted ideas", "color": GREEN,
                               "description": "\n".join(f"• [{short(i['text'], 80)}]({i['url']})" + (f" · 👍 {i['votes']}" if i["votes"] else "")
                                                        for i in ideas[:8])[:4000]})
            asks = [i for i in items if i["kind"] in ("course", "submission")]
            if asks:
                embeds.append({"title": "📚 Course requests and submissions", "color": BLUE,
                               "description": "\n".join(f"• [{short(i['text'], 80)}]({i['url']}) · {i['where']}" for i in asks[:10])[:4000]})
            nums = self.numbers()
            if nums:
                embeds.append({"title": "📈 Numbers", "color": YELLOW, "description": "\n".join(nums)})
        day = self.now.strftime("%A %d %B")
        self.say("team-chat", f"🐢 **Tempo's report for {day}**", embeds=embeds)
        return {"problems": len(problems), "groups": [t for t, _ in ranked], "items": len(items)}

    def ai_advice(self, items: list[dict]) -> str:
        """Optional: Claude reads this week's reports and says what to fix first, and why."""
        lines = [f"- [{i['kind']}, {i['topic']}, {i['where']}, votes {i['votes']}, {'answered' if i['answered'] else 'unanswered'}] "
                 f"{short(i['text'], 300)}" for i in items[:80]]
        prompt = ("You help the two-person team behind inPace, a free open-source learning app (desktop and Android, "
                  "English and Arabic). Here is what users reported this week on Discord and GitHub. In at most 6 short bullets, "
                  "in plain English, say what to fix or answer first and why (how many people it hurts, how bad it is). "
                  "Mention a quick win if there is one. No preamble.\n\n" + "\n".join(lines))
        model = os.environ.get("AI_MODEL", "claude-sonnet-5-5")
        try:
            r = self.http.call("POST", "https://api.anthropic.com/v1/messages",
                               {"x-api-key": self.ai_key, "anthropic-version": "2023-06-01"},
                               {"model": model, "max_tokens": 700, "messages": [{"role": "user", "content": prompt}]}, quiet=True)
            return "".join(b.get("text", "") for b in (r or {}).get("content", []) if b.get("type") == "text").strip()
        except Exception:
            return ""


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def short(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip().replace("[", "(").replace("]", ")")
    return text if len(text) <= n else text[: n - 1] + "…"


def ago(t: datetime, now: datetime) -> str:
    h = int((now - t).total_seconds() // 3600)
    return f"{h} h ago" if h < 48 else f"{h // 24} days ago"


def main(argv=None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        print("No DISCORD_BOT_TOKEN secret: the bot is off.")
        return
    mode = (argv[0] if argv else "") or os.environ.get("BOT_MODE", "")
    if not mode:  # GitHub's schedule decides: the morning run is the report
        mode = "report" if os.environ.get("BOT_SCHEDULE", "").startswith("17 6") else "watch"
    bot = Bot(token, os.environ.get("GITHUB_TOKEN", ""), ai_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    print(mode, bot.report() if mode == "report" else bot.watch())


if __name__ == "__main__":
    main()
