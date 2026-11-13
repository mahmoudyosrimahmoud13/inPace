"""inPace on Android: start the same inPace web app the desktop uses, for the Flutter shell to show.

The Flutter side passes INPACE_HOME (a private folder of the app) and INPACE_PORT, then opens
http://127.0.0.1:<port>/ in a web view once /ping answers. If anything fails while starting, the reason is
written to <INPACE_HOME>/start-error.txt and the app's error screen shows it.
"""
import os
import traceback

os.environ.setdefault("INPACE_MOBILE", "android")  # no desktop window, no desktop updater

home = os.environ.get("INPACE_HOME") or os.path.join(os.getcwd(), "inPace")
port = int(os.environ.get("INPACE_PORT", "8765"))

try:
    import uvicorn

    from inpace.app import create_app
    from inpace.offline import start_auto_updates
    from inpace.vault import Vault

    start_auto_updates(home)  # yt-dlp for offline YouTube lessons: a new copy once a day, if you chose that

    # h11 and asyncio are pure Python, so they work everywhere (uvloop and httptools need compiled parts).
    uvicorn.run(create_app(Vault(home)), host="127.0.0.1", port=port, log_level="warning", loop="asyncio", http="h11")
except BaseException:
    try:
        os.makedirs(home, exist_ok=True)
        with open(os.path.join(home, "start-error.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
    except Exception:
        pass
    raise
