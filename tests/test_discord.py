"""The Discord setup builds the whole server in one run, safely again on a second run, and the GitHub poster
writes the right messages. A fake Discord stands in for the real one."""
import importlib.util
import io
import json
import re
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "community" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeDiscord:
    def __init__(self, community_ok=True):
        self.n = 1000
        self.gid = "1"
        self.guild = {"id": "1", "name": "inPace", "features": [], "icon": None}
        self.roles = [{"id": "1", "name": "@everyone"}]
        self.channels = [{"id": "2", "name": "Text Channels", "type": 4},
                         {"id": "3", "name": "general", "type": 0, "parent_id": "2"},
                         {"id": "4", "name": "Voice Channels", "type": 4},
                         {"id": "5", "name": "General", "type": 2, "parent_id": "4"}]
        self.messages, self.hooks, self.onboarding = {}, {}, None
        self.community_ok = community_ok
        self.calls = []

    def new_id(self):
        self.n += 1
        return str(self.n)

    def __call__(self, req):
        method, path = req.get_method(), req.full_url.split("/api/v10", 1)[1]
        body = json.loads(req.data) if req.data else None
        self.calls.append((method, path, body))
        assert req.headers["Authorization"] == "Bot T0KEN"
        out = self.route(method, path.split("?")[0], body)
        if isinstance(out, int):
            raise urllib.error.HTTPError(req.full_url, out, "no", {}, io.BytesIO(b'{"message":"no"}'))
        resp = io.BytesIO(json.dumps(out).encode() if out is not None else b"")
        resp.__enter__ = lambda *a: resp
        resp.__exit__ = lambda *a: None
        return resp

    def route(self, m, p, b):
        g = "/guilds/1"
        if p == "/oauth2/applications/@me":
            return {"id": "777"}
        if p == "/users/@me":
            return {"id": "777"}
        if p == "/users/@me/guilds":
            return [{"id": "1", "name": "inPace"}]
        if p == g and m == "GET":
            return self.guild
        if p == g and m == "PATCH":
            if "features" in b:
                if not self.community_ok:
                    return 403
                assert b["rules_channel_id"] and b["public_updates_channel_id"]
                self.guild["features"] = b["features"]
            if "icon" in b:
                self.guild["icon"] = "abc"
            return self.guild
        if p == g + "/roles":
            if m == "GET":
                return self.roles
            r = {"id": self.new_id(), **b}
            self.roles.append(r)
            return r
        if p == g + "/channels":
            if m == "GET":
                return self.channels
            c = {"id": self.new_id(), **b}
            self.channels.append(c)
            return c
        if p == g + "/onboarding":
            if m == "GET":
                return self.onboarding or {"prompts": []}
            ids = {c["id"] for c in self.channels}
            assert all(c in ids for c in b["default_channel_ids"]) and len(b["default_channel_ids"]) >= 7
            self.onboarding = b
            return b
        mm = re.match(r"/channels/(\d+)(/.*)?$", p)
        if mm:
            cid, rest = mm.group(1), mm.group(2) or ""
            if rest == "" and m == "DELETE":
                self.channels = [c for c in self.channels if c["id"] != cid]
                return None
            if rest == "" and m == "PATCH":
                c = next(c for c in self.channels if c["id"] == cid)
                c.update(b)
                return c
            if rest == "/messages":
                if m == "GET":
                    return self.messages.get(cid, [])
                assert len(b["content"]) <= 2000
                msg = {"id": self.new_id(), "author": {"id": "777"}, **b}
                self.messages.setdefault(cid, []).append(msg)
                return msg
            if rest == "/webhooks":
                if m == "GET":
                    return self.hooks.get(cid, [])
                w = {"id": self.new_id(), "token": "tok" + cid}
                self.hooks.setdefault(cid, []).append(w)
                return w
            if rest == "/invites":
                return {"code": "inpace"}
        raise AssertionError(f"unexpected {m} {p}")


def test_setup_builds_everything_and_twice_is_safe(tmp_path, monkeypatch):
    ds = _load("discord_setup")
    fake = FakeDiscord()
    api = ds.Discord("T0KEN", opener=fake)
    monkeypatch.setattr(ds, "ask", lambda *a, **k: True)
    out = ds.build(api, "1", log=lambda *a: None)
    names = [c["name"] for c in fake.channels]
    for want in ("welcome", "rules", "announcements", "releases", "new-courses", "dev-log", "feedback-feed",
                 "general", "help", "عام", "مساعدة", "team-chat", "Study together"):
        assert names.count(want) == 1, want
    assert "Text Channels" not in names and "General" not in names  # empty starters removed
    assert {"Team", "English", "العربية", "Course maker"} <= {r["name"] for r in fake.roles}
    assert "COMMUNITY" in fake.guild["features"] and fake.guild["icon"]
    ann = next(c for c in fake.channels if c["name"] == "announcements")
    assert ann["type"] == ds.NEWS
    # read-only news channels: everyone reads, only the team writes
    rel = next(c for c in fake.channels if c["name"] == "releases")
    everyone = next(o for o in rel["permission_overwrites"] if o["id"] == "1")
    assert int(everyone["deny"]) & ds.SEND
    # the welcome message points at real channels, not names
    welcome = next(c for c in fake.channels if c["name"] == "welcome")
    text = " ".join(m["content"] for m in fake.messages[welcome["id"]])
    assert "<#introductions>" not in text and re.search(r"<#\d+>", text)
    # language question: each option gives a role and its channels
    opts = fake.onboarding["prompts"][0]["options"]
    assert [o["title"] for o in opts] == ["English", "العربية"] and all(o["role_ids"] and o["channel_ids"] for o in opts)
    assert set(out["hooks"]) == {"releases", "courses", "devlog", "feedback", "announcements"}
    assert out["invite"] == "https://discord.gg/inpace" and out["community"]

    # Second run: nothing new is made, no second welcome message, same webhooks.
    before = (len(fake.channels), len(fake.roles), sum(len(v) for v in fake.messages.values()))
    out2 = ds.build(api, "1", log=lambda *a: None)
    assert (len(fake.channels), len(fake.roles), sum(len(v) for v in fake.messages.values())) == before
    assert out2["hooks"] == out["hooks"]


def test_setup_still_works_without_community(monkeypatch):
    ds = _load("discord_setup")
    fake = FakeDiscord(community_ok=False)
    monkeypatch.setattr(ds, "ask", lambda *a, **k: False)
    out = ds.build(ds.Discord("T0KEN", opener=fake), "1", log=lambda *a: None)
    assert not out["community"] and out["hooks"]["releases"].startswith("https://discord.com/api/webhooks/")
    assert "general" in [c["name"] for c in fake.channels]  # starter kept when you say no


def test_site_page_and_secret_file(tmp_path, monkeypatch):
    ds = _load("discord_setup")
    monkeypatch.setattr(ds, "ROOT", tmp_path)
    (tmp_path / "site").mkdir()
    page = ds.write_site_page("https://discord.gg/abc")
    assert 'url=https://discord.gg/abc' in page.read_text(encoding="utf-8")
    monkeypatch.setattr(ds.shutil, "which", lambda *_: None)
    monkeypatch.setattr(ds, "SECRETS_FILE", tmp_path / "hooks.txt")
    assert ds.save_secrets({"releases": "u"}) == "file"
    assert json.loads((tmp_path / "hooks.txt").read_text(encoding="utf-8")) == {"releases": "u"}


def test_poster_messages(monkeypatch, tmp_path):
    dp = _load("discord_post")
    rel = dp.release_message({"tag_name": "v1.27.0", "name": "inPace v1.27.0", "html_url": "https://x", "body": "- New"})
    assert "v1.27.0" in rel["content"] and "#download" in rel["embeds"][0]["description"]
    push = dp.push_message({"commits": [{"message": "v1.27.0: things\n\nmore", "url": "https://c"}],
                            "repository": {"name": "inPace"}, "compare": "https://cmp"})
    assert "v1.27.0: things" in push["embeds"][0]["description"] and "more" not in push["embeds"][0]["description"]
    assert dp.push_message({"commits": []}) is None
    iss = dp.issue_message({"issue": {"title": "Idea or suggestion: Dark PDF", "html_url": "https://i", "body": "pls",
                                      "labels": [], "user": {"login": "x"}}})
    assert iss["embeds"][0]["title"] == "💡 Idea: Dark PDF"
    assert dp.issue_message({"issue": {"pull_request": {}}}) is None
    # no secret: never posts
    monkeypatch.delenv("DISCORD_WEBHOOKS", raising=False)
    sent = []
    monkeypatch.setattr(dp, "send", lambda *a: sent.append(a))
    dp.main()
    assert not sent
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"commits": [{"message": "x", "url": "u"}], "repository": {"name": "inPace"}}))
    monkeypatch.setenv("DISCORD_WEBHOOKS", json.dumps({"devlog": "https://hook"}))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(ev))
    dp.main()
    assert sent and sent[0][0] == "https://hook"


def test_release_goes_to_telegram_too(monkeypatch):
    dp = _load("discord_post")
    msg = dp.release_message({"tag_name": "v9.9.9", "name": "inPace v9.9.9", "html_url": "https://r", "body": "- New <b>"})
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert dp.telegram(msg) is False
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT", "@inpace")
    sent = []

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b"{}"
    assert dp.telegram(msg, opener=lambda req: sent.append(req) or R())
    body = json.loads(sent[0].data)
    assert body["chat_id"] == "@inpace" and "v9.9.9" in body["text"] and "&lt;b&gt;" in body["text"]
