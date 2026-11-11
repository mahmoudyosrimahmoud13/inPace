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
    print(f"""## Download inPace {version}

| Your computer | Download | How to open |
|---|---|---|
| **Windows** 10 or 11 | [inPace-windows.zip]({base}/inPace-windows.zip) | Unzip, then double-click **inPace.exe** |
| **Mac** (Apple Silicon: M1 or newer) | [inPace-mac.dmg]({base}/inPace-mac.dmg) | Open it, drag **inPace** into Applications |
| **Ubuntu / Debian** | [inPace-linux.deb]({base}/inPace-linux.deb) | Double-click to install, then find **inPace** in your apps |
| **Other Linux** | [inPace-linux.tar.gz]({base}/inPace-linux.tar.gz) | Unpack, then run **inPace** |

**First time opening it?** The app isn't signed yet, so your computer may warn you once:
- **Windows:** "Windows protected your PC" → click **More info** → **Run anyway**.
- **Mac:** "can't be opened" → right-click inPace → **Open** → **Open**.

Your data stays on your computer. Updating is safe: just download the new version, and your courses and progress are still there.

## What's new

{changes_for(version)}

---
Need help or found a bug? [Open an issue](https://github.com/{repo}/issues/new).
""")


if __name__ == "__main__":
    main()
