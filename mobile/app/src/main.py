"""inPace on Android: start the same inPace web app the desktop uses, for the Flutter shell to show.

The Flutter side passes INPACE_HOME (a private folder of the app) and INPACE_PORT, then opens
http://127.0.0.1:<port>/ in a web view once /ping answers.
"""
import os

os.environ.setdefault("INPACE_MOBILE", "android")  # no desktop window, no desktop updater

import uvicorn  # noqa: E402

from inpace.app import create_app  # noqa: E402
from inpace.vault import Vault  # noqa: E402

home = os.environ.get("INPACE_HOME") or os.path.join(os.getcwd(), "inPace")
port = int(os.environ.get("INPACE_PORT", "8765"))

from inpace.offline import start_auto_updates  # noqa: E402

start_auto_updates(home)  # yt-dlp for offline YouTube lessons: a new copy once a day, if you chose that

# h11 and asyncio are pure Python, so they work everywhere (uvloop and httptools need compiled parts).
uvicorn.run(create_app(Vault(home)), host="127.0.0.1", port=port, log_level="warning", loop="asyncio", http="h11")
