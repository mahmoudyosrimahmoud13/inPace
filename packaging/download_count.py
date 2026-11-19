"""Keeps the website's download counter from ever going back (site/downloads.json).

GitHub counts each release's downloads, but a deleted release takes its count with it, and GitHub's list only
gives the newest 100 releases at a time. This reads every release (all pages) and saves each one's count, keeping
the bigger number, so the total on the website only goes up.

    python packaging/download_count.py [site/downloads.json]       (GITHUB_TOKEN optional, avoids rate limits)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = "mahmoudyosrimahmoud13/inpace"


def live(fetch=None) -> dict[str, int]:
    """Every release's downloads now: {tag: count}."""
    out: dict[str, int] = {}
    page = 1
    while True:
        url = f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={page}"
        if fetch:
            rels = fetch(url)
        else:
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "inpace-site"})
            if os.environ.get("GITHUB_TOKEN"):
                req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
            with urllib.request.urlopen(req, timeout=30) as r:
                rels = json.load(r)
        if not rels:
            return out
        for r in rels:
            out[r["tag_name"]] = sum(a.get("download_count", 0) or 0 for a in r.get("assets") or [])
        if len(rels) < 100:
            return out
        page += 1


def merge(saved: dict[str, int], now: dict[str, int]) -> dict[str, int]:
    """Each release keeps the bigger number; releases that are gone keep their last count."""
    out = dict(saved)
    for tag, n in now.items():
        out[tag] = max(out.get(tag, 0), n)
    return dict(sorted(out.items()))


def main(argv: list[str], fetch=None) -> dict:
    path = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent / "site" / "downloads.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8")).get("releases", {})
    except (OSError, ValueError):
        saved = {}
    releases = merge(saved, live(fetch))
    data = {"total": sum(releases.values()), "releases": releases}
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print("downloads:", data["total"])
    return data


if __name__ == "__main__":
    main(sys.argv[1:])
