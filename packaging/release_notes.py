"""Write the release page text: downloads first, then what's new (from CHANGELOG.md).

    python packaging/release_notes.py v1.0.0 owner/repo
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def changes_for(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    v = version.lstrip("v")
    m = re.search(rf"^## \[?v?{re.escape(v)}\]?.*?$\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else "See the commit history for this version."


def main() -> None:
    version, repo = sys.argv[1], sys.argv[2]
    base = f"https://github.com/{repo}/releases/download/{version}"
    site = "https://mahmoudyosrimahmoud13.github.io/inPace"
    docs = f"https://github.com/{repo}/blob/main/docs/HOW-IT-WORKS.md"
    print(f"""## Download inPace {version}

| Your device | Download | How to open |
|---|---|---|
| **Windows** 10 or 11 | [inPace-windows.zip]({base}/inPace-windows.zip) | Unzip, then double-click **inPace.exe** |
| **Mac** (Apple Silicon: M1 or newer) | [inPace-mac.dmg]({base}/inPace-mac.dmg) | Open it, drag **inPace** into Applications |
| **Ubuntu / Debian** | [inPace-linux.deb]({base}/inPace-linux.deb) | Double-click to install, then find **inPace** in your apps |
| **Other Linux** | [inPace-linux.tar.gz]({base}/inPace-linux.tar.gz) | Unpack, then run **inPace** |
| **Android** 7 or newer | [inPace-android-arm64-v8a.apk]({base}/inPace-android-arm64-v8a.apk) | Open it on your phone and tap **Install** |

The Android file may appear a few minutes after the others, because it's built separately.

**First time opening it?** The apps aren't signed by Apple or Microsoft yet, so your device may warn you once:
- **Windows:** "Windows protected your PC" → click **More info** → **Run anyway**.
- **Mac:** "can't be opened" → right-click inPace → **Open** → **Open**.
- **Android:** if your phone asks, allow installing apps from your browser or Files app.

**Reminders:** the first time, allow notifications. On Android, open **More → Reminders** and tap **Allow notifications**. On a Mac, the first reminder may ask to allow notifications from "Script Editor", which is what shows them.

**Updating is safe.** Your courses and progress stay.
- **Computer:** inPace updates itself if you said yes, or download the new version above.
- **Android:** download the new APK and tap **Update**. Every version is signed with the same key, so it installs over the old one.

Your data stays on your device. Nothing goes online unless you press something that needs it.

## What's new

{changes_for(version)}

---
[Website]({site}/) · [Guide]({site}/guide.html) · [How inPace works]({docs}) · [Course library](https://mahmoudyosrimahmoud13.github.io/inpace-library/) · [Open an issue](https://github.com/{repo}/issues/new)

Checking a download? Its SHA-256 fingerprint is in `SHA256SUMS` below (the Android file isn't listed there yet).
""")



if __name__ == "__main__":
    main()
