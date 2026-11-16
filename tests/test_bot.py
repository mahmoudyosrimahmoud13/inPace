"""Tempo, the Discord bot: it answers known problems in the right language, turns 🐞 into GitHub issues,
tells people when they're fixed, ranks what to fix first, and does nothing twice. Fake Discord and GitHub."""
import importlib.util
import io
import json
import re
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)


def _bot():
    spec = importlib.util.spec_from_file_location("inpace_bot", ROOT / "community" / "bot.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inpace_bot"] = mod
    spec.loader.exec_module(mod)
    return mod


def ts(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")


class World:
    """A tiny Discord server and GitHub, enough for the bot."""

    def __init__(self):
        self.n = 500
        self.channels = {"help": "11", "مساعدة": "12", "ideas": "13", "course-requests": "14", "team-chat": "15",
                         "general": "16", "عام": "17"}
        self.msgs = {cid: [] for cid in self.channels.values()}
        self.posted, self.issues, self.labels = [], [], []
        self.reactors = {}  # (channel, msg) -> [user ids]

    def add(self, channel, text, user="u1", hours=1, reactions=None, ref=None):
        self.n += 1
        m = {"id": str(self.n), "type": 0, "content": text, "timestamp": ts(hours), "attachments": [],
             "author": {"id": user, "username": user, "global_name": user.title()}, "reactions": reactions or []}
        if ref:
            m["message_reference"] = {"message_id": ref}
        self.msgs[self.channels[channel]].insert(0, m)
        return m

    def __call__(self, req):
        url, method = req.full_url, req.get_method()
        body = json.loads(req.data) if req.data else None
        out = self.route(method, url, body)
        if isinstance(out, int):
            raise urllib.error.HTTPError(url, out, "x", {}, io.BytesIO(b"{}"))
        r = io.BytesIO(json.dumps(out).encode() if out is not None else b"")
        r.__enter__ = lambda *a: r
        r.__exit__ = lambda *a: None
        return r

    def route(self, m, url, b):
        if url.startswith("https://api.github.com"):
            p = url[len("https://api.github.com"):]
            if p.endswith("/labels") and m == "POST":
                self.labels.append(b["name"])
                return b
            if re.match(r"/repos/[^/]+/inPace/issues$", p) and m == "POST":
                it = {"number": len(self.issues) + 1, "html_url": f"https://github.com/x/inPace/issues/{len(self.issues) + 1}", **b}
                self.issues.append(it)
                return it
            if "/issues?state=closed" in p:
                return [{"html_url": "https://github.com/x/inPace/issues/9", "state_reason": "completed",
                         "body": "x\n<!-- discord:11/999 -->"}]
            if "inPace/issues?state=open" in p:
                return [{"title": "Problem: Videos are black on Ubuntu", "body": "the video doesn't play", "labels": [],
                         "html_url": "https://github.com/x/inPace/issues/3", "user": {"login": "sam"},
                         "created_at": ts(5), "comments": 0, "reactions": {"+1": 2}},
                        {"title": "PR", "pull_request": {}, "labels": [], "html_url": "", "user": {"login": "a"}, "created_at": ts(1)}]
            if "inpace-library/issues?state=open" in p:
                return [{"title": "Course: Spanish B2", "body": "", "labels": [{"name": "course-submission"}],
                         "html_url": "https://github.com/x/lib/issues/4", "user": {"login": "ana"}, "created_at": ts(30), "comments": 1}]
            if p.endswith("/repos/mahmoudyosrimahmoud13/inPace"):
                return {"stargazers_count": 12, "forks_count": 2, "open_issues_count": 3}
            if "/releases" in p:
                return [{"tag_name": "v1.27.0", "assets": [{"name": "inPace-windows.zip", "download_count": 40},
                                                           {"name": "inPace-android-arm64-v8a.apk", "download_count": 25},
                                                           {"name": "SHA256SUMS", "download_count": 3}]}]
            return []
        p = url.split("/api/v10", 1)[1]
        if p == "/users/@me":
            return {"id": "bot"}
        if p == "/users/@me/guilds":
            return [{"id": "1"}]
        if p.startswith("/guilds/1?"):
            return {"id": "1", "owner_id": "owner", "approximate_member_count": 57, "approximate_presence_count": 9}
        if p == "/guilds/1/channels":
            return [{"id": cid, "name": n, "type": 0} for n, cid in self.channels.items()]
        if p == "/guilds/1/roles":
            return [{"id": "r-team", "name": "Team"}]
        mm = re.match(r"/guilds/1/members/(\w+)", p)
        if mm:
            return {"roles": ["r-team"] if mm.group(1) == "yosri" else []}
        mm = re.match(r"/channels/(\d+)/messages\?limit", p)
        if mm:
            return json.loads(json.dumps(self.msgs[mm.group(1)]))
        mm = re.match(r"/channels/(\d+)/messages/(\d+)/reactions/([^/]+)/@me", p)
        if mm:
            cid, mid, emo = mm.groups()
            import urllib.parse
            emo = urllib.parse.unquote(emo)
            for msg in self.msgs.get(cid, []):
                if msg["id"] == mid:
                    r = next((r for r in msg["reactions"] if r["emoji"]["name"] == emo), None)
                    if r:
                        r["me"], r["count"] = True, r["count"] + 1
                    else:
                        msg["reactions"].append({"emoji": {"name": emo}, "count": 1, "me": True})
            return None
        mm = re.match(r"/channels/(\d+)/messages/(\d+)/reactions/([^/?]+)$", p)
        if mm:
            return [{"id": u} for u in self.reactors.get((mm.group(1), mm.group(2)), [])]
        mm = re.match(r"/channels/(\d+)/messages/(\d+)$", p)
        if mm:
            if mm.group(2) == "999":
                return {"id": "999", "content": "the timer is broken", "reactions": []}
            return 404
        mm = re.match(r"/channels/(\d+)/messages$", p)
        if mm and m == "POST":
            self.posted.append((mm.group(1), b))
            return {"id": "p" + str(len(self.posted))}
        raise AssertionError(f"unexpected {m} {p}")


def make(world, ai_key=""):
    mod = _bot()
    return mod, mod.Bot("T", "gh", http=mod.Http(opener=world), now=NOW, ai_key=ai_key)


def test_kinds_topics_and_answers():
    mod = _bot()
    assert mod.kind_of("video player not working :(") == "problem"
    assert mod.kind_of("would be cool if you could let us use our own subtitle files") == "idea"
    assert mod.kind_of("الفيديو مش شغال عندي") == "problem"
    assert mod.kind_of("how do I add a course?") == "question"
    assert mod.topic_of("larger or longer video files dont seem to open") == "video"
    assert mod.topic_of("the apk won't install on my phone") == "android"
    assert "gstreamer1.0-libav" in mod.faq_answer("video player not working, black screen")["en"]
    assert "HandBrake" in mod.faq_answer("my mkv lecture won't open")["ar"]
    assert mod.faq_answer("hi everyone!") is None


def test_watch_helps_in_their_language_once():
    w = World()
    w.add("help", "video player not working, just a black screen", hours=1)
    w.add("مساعدة", "الفيديو مش شغال والشاشة سوداء", hours=2)
    w.add("help", "hello! love the app", hours=1)
    w.add("help", "my video is black", user="yosri", hours=1)  # the team doesn't get auto answers
    mod, bot = make(w)
    got = bot.watch()
    assert got["helped"] == 2
    replies = [b for cid, b in w.posted]
    en = next(b for b in replies if "gstreamer" in b["content"] and "If this doesn't fix it" in b["content"])
    ar = next(b for b in replies if "سيرد عليك الفريق" in b["content"])
    assert en["message_reference"] and ar["message_reference"] and en["allowed_mentions"]["parse"] == []
    # every message is marked as seen, so the next run says nothing again
    assert all(any(r.get("me") and r["emoji"]["name"] == "👀" for r in m["reactions"]) for m in w.msgs["11"])
    assert make(w)[1].watch()["helped"] == 0


def test_bug_reaction_from_the_team_opens_an_issue():
    w = World()
    m = w.add("help", "The timer stops when I lock my phone", hours=3,
              reactions=[{"emoji": {"name": "🐞"}, "count": 1, "me": False}])
    w.reactors[("11", m["id"])] = ["yosri"]
    stranger = w.add("ideas", "make it purple", hours=3, reactions=[{"emoji": {"name": "🐞"}, "count": 1, "me": False}])
    w.reactors[("13", stranger["id"])] = ["random"]  # not on the team: ignored
    mod, bot = make(w)
    assert bot.bugs_to_issues() == 1
    issue = w.issues[0]
    assert issue["labels"] == ["from-discord"] and "The timer stops" in issue["title"]
    assert f"<!-- discord:11/{m['id']} -->" in issue["body"] and "from-discord" in w.labels
    assert any("on our fix list" in b["content"] for _, b in w.posted)
    assert make(w)[1].bugs_to_issues() == 0  # ✅ marks it done


def test_closed_issue_tells_the_reporter():
    w = World()
    mod, bot = make(w)
    assert bot.tell_fixed() == 1
    assert any("Fixed!" in b["content"] and b["message_reference"]["message_id"] == "999" for _, b in w.posted)


def test_report_ranks_what_to_fix_first():
    w = World()
    w.add("help", "video player not working", hours=3)
    w.add("help", "longer video files don't open within the course", hours=30, reactions=[{"emoji": {"name": "👍"}, "count": 3}])
    w.add("مساعدة", "التطبيق مش بيفتح بعد التحديث", hours=20)
    w.add("ideas", "would be cool to have a dark PDF reader", hours=40, reactions=[{"emoji": {"name": "👍"}, "count": 5}])
    w.add("course-requests", "irregular verbs in english please", hours=10)
    w.add("help", "how do I share my course?", hours=50)
    mod, bot = make(w)
    got = bot.report()
    assert got["groups"][0] == "video"  # most reports, most votes
    cid, post = w.posted[-1]
    assert cid == "15" and "Tempo's report" in post["content"]
    titles = [e["title"] for e in post["embeds"]]
    assert titles[0] == "🔥 What to fix first"
    fix = post["embeds"][0]["description"]
    assert fix.startswith("**1. Videos and YouTube") and "3 reports" in fix
    assert any(t.startswith("⏳ Waiting for an answer") for t in titles)
    assert any(t == "💡 Most wanted ideas" for t in titles) and any("Course requests" in t for t in titles)
    nums = next(e for e in post["embeds"] if e["title"] == "📈 Numbers")["description"]
    assert "12 stars" in nums and "65 downloads" in nums and "57 people" in nums
    # !fix posts only the short list
    w.add("team-chat", "!fix", user="owner", hours=0.1)
    assert bot.commands() == 1 and len(w.posted[-1][1]["embeds"]) == 1
    assert bot.commands() == 0


def test_no_token_means_off(monkeypatch, capsys):
    mod = _bot()
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    mod.main([])
    assert "the bot is off" in capsys.readouterr().out
