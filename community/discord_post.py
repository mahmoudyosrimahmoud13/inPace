"""Posts to the inPace Discord from GitHub Actions: new releases, every push (dev log), and new feedback.

GitHub runs this (see .github/workflows/discord.yml). It needs the secret DISCORD_WEBHOOKS, which
community/discord_setup.py makes. Without it, it does nothing, so forks and tests never post anywhere.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

YELLOW, GREEN, PINK, BLUE = 0xFFD43B, 0x1F9D6A, 0xE6007E, 0x5DADE2
SITE = "https://mahmoudyosrimahmoud13.github.io/inPace/"


def hooks() -> dict:
    try:
        return json.loads(os.environ.get("DISCORD_WEBHOOKS") or "{}")
    except ValueError:
        return {}


def send(url: str, payload: dict, opener=urllib.request.urlopen) -> None:
    req = urllib.request.Request(url + "?wait=true", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "inPace-GitHub"})
    with opener(req) as r:
        r.read()


def cut(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def github(path: str) -> dict:
    req = urllib.request.Request("https://api.github.com" + path, headers={
        "Authorization": "Bearer " + os.environ.get("GITHUB_TOKEN", ""), "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def release_message(rel: dict) -> dict:
    tag = rel.get("tag_name", "")
    notes = cut(rel.get("body") or "", 3500)
    return {"username": "inPace", "content": f"🐢 **inPace {tag} is out!**", "embeds": [{
        "title": rel.get("name") or f"inPace {tag}", "url": rel.get("html_url"), "color": YELLOW,
        "description": notes + f"\n\n**Download:** {SITE}#download\nThe app also tells you about it and updates itself."}],
        "allowed_mentions": {"parse": []}}


def push_message(event: dict) -> dict | None:
    commits = [c for c in event.get("commits", []) if c.get("distinct", True)]
    if not commits:
        return None
    repo = event.get("repository", {}).get("name", "inPace")
    lines = []
    for c in commits[-10:]:
        first = cut(c.get("message", "").splitlines()[0] if c.get("message") else "", 180)
        lines.append(f"• [{first}]({c.get('url')})")
    more = f"\n…and {len(commits) - 10} more" if len(commits) > 10 else ""
    who = (event.get("head_commit") or {}).get("author", {}).get("name") or event.get("pusher", {}).get("name", "")
    return {"username": "inPace dev log", "embeds": [{
        "title": f"{len(commits)} new change{'s' if len(commits) != 1 else ''} in {repo}", "url": event.get("compare"),
        "description": "\n".join(lines) + more, "color": GREEN, "footer": {"text": who}}],
        "allowed_mentions": {"parse": []}}


def issue_message(event: dict) -> dict | None:
    issue = event.get("issue") or {}
    if not issue or "pull_request" in issue:
        return None
    labels = [lb["name"] for lb in issue.get("labels", [])]
    kind = "💡 Idea" if any("idea" in x.lower() or "enhancement" in x for x in labels) else \
        "🐞 Problem" if any(x in ("bug", "problem") for x in labels) else "💬 Feedback"
    title = issue.get("title", "")
    for prefix in ("Problem:", "Idea or suggestion:", "Question:", "Something else:"):
        if title.startswith(prefix):
            kind = {"Problem:": "🐞 Problem", "Idea or suggestion:": "💡 Idea", "Question:": "❓ Question"}.get(prefix, kind)
            title = title[len(prefix):].strip()
    return {"username": "inPace feedback", "embeds": [{
        "title": cut(f"{kind}: {title}", 250), "url": issue.get("html_url"), "color": PINK,
        "description": cut(issue.get("body") or "", 600) + "\n\nReply on GitHub, or talk about it in #ideas.",
        "footer": {"text": issue.get("user", {}).get("login", "")}}], "allowed_mentions": {"parse": []}}


def main() -> None:
    h = hooks()
    if not h:
        print("No DISCORD_WEBHOOKS secret: nothing to post.")
        return
    name = os.environ.get("GITHUB_EVENT_NAME", "")
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8")) if os.environ.get("GITHUB_EVENT_PATH") else {}
    msg, where = None, None
    if name == "workflow_run":  # the release build finished: post its release page
        run = event.get("workflow_run", {})
        if run.get("conclusion") == "success" and run.get("event") == "push" and str(run.get("head_branch", "")).startswith("v"):
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            msg, where = release_message(github(f"/repos/{repo}/releases/tags/{run['head_branch']}")), "releases"
    elif name == "release":
        msg, where = release_message(event.get("release", {})), "releases"
    elif name == "push":
        msg, where = push_message(event), "devlog"
    elif name == "issues":
        msg, where = issue_message(event), "feedback"
    if msg and h.get(where):
        send(h[where], msg)
        print(f"Posted to #{where}.")
    else:
        print("Nothing to post.")


if __name__ == "__main__":
    sys.exit(main())
