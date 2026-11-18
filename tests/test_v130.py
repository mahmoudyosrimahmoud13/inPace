"""v1.30: the floating timer (pill, card or ring), the mini player, the pop-out mini window, Settings in groups."""
import html
import json
import time

from inpace import focus, garden
from tests.test_app import client

J = {"x-inpace-fetch": "1", "accept": "application/json"}


def test_timer_start_pause_resume_stop(tmp_path):
    v, c = client(tmp_path, "Omar")
    assert c.get("/timer.json").json() == {"on": False}
    d = c.post("/timer/start", data={"minutes": "25", "label": "SQL"}, headers=J).json()
    assert d["on"] and d["kind"] == "timer" and d["state"] == "running" and d["goal"] == 1500 and d["label"] == "SQL"
    assert c.post("/timer/pause", headers=J).json()["state"] == "paused"
    assert c.post("/timer/resume", headers=J).json()["state"] == "running"
    assert c.post("/timer/stop", headers=J).json() == {"on": False}


def test_the_timer_is_its_own_thing(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/timer/start", data={"minutes": "10"}, headers=J)
    page = c.get("/settings").text + c.get("/").text
    assert 'name="follow"' not in page                      # no "pause with the video" any more
    import pathlib
    js = (pathlib.Path(__file__).resolve().parent.parent / "inpace/static/app.js").read_text(encoding="utf-8")
    assert 'inpaceTimer.pause("video")' not in js and 'inpaceTimer.resume("video")' not in js


def test_timer_ends(tmp_path):
    v, c = client(tmp_path, "Omar")
    focus.start(v, 10)
    d = focus._load(v)
    d["run_from"] -= 601
    focus._save(v, d)
    out = c.get("/timer.json").json()
    assert out["on"] is False and out["done"] is True
    assert c.get("/timer.json").json() == {"on": False}


def test_timer_with_a_plant_is_an_island_trip(tmp_path):
    v, c = client(tmp_path, "Omar")
    garden.set_on(v, True)
    d = c.post("/timer/start", data={"minutes": "25", "plant": "1"}, headers=J).json()
    assert d["kind"] == "trip" and garden.active(v)["state"] == "running"
    assert c.post("/timer/pause", headers=J).json()["state"] == "paused"
    c.post("/timer/stop", headers=J)
    assert garden.active(v)["state"] == "resting"   # the sprout keeps its minutes


def test_plant_ignored_without_the_island(tmp_path):
    v, c = client(tmp_path, "Omar")
    d = c.post("/timer/start", data={"minutes": "25", "plant": "1"}, headers=J).json()
    assert d["kind"] == "timer"


def test_every_page_has_the_timer_and_its_look(tmp_path):
    v, c = client(tmp_path, "Omar")
    page = c.get("/").text
    assert "data-ftimer" in page and 'data-look="pill"' in page and "data-timer-open" in page
    c.post("/settings/timer", data={"look": "ring"})
    assert 'data-look="ring"' in c.get("/courses").text
    c.post("/settings/timer", data={"look": "nonsense"})
    assert focus.look(v) == "pill"


def test_timer_shows_on_the_page_when_running(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/timer/start", data={"minutes": "45"}, headers=J)
    page = c.get("/").text
    data = json.loads(html.unescape(page.split('id="timer-data">', 1)[1].split("</script>", 1)[0]))
    assert data["on"] and data["goal"] == 2700


def test_five_more_minutes(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/timer/start", data={"minutes": "10"}, headers=J)
    assert c.post("/timer/add", headers=J).json()["goal"] == 900


def test_settings_are_in_groups_with_the_timer(tmp_path):
    v, c = client(tmp_path, "Omar")
    page = html.unescape(c.get("/settings").text)
    for g in ("g-you", "g-study", "g-videos", "g-ai", "g-data", "g-app"):
        assert f'id="{g}"' in page
    assert 'id="timer"' in page and 'name="look" value="ring"' in page
    assert page.index('id="g-study"') < page.index('id="timer"') < page.index('id="g-videos"')


def test_pop_out_window_page_and_routes(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/courses/sample/python-basics")
    jid = c.post(f"/courses/python-basics/start", follow_redirects=False).headers["location"].rsplit("/", 1)[1]
    page = c.get(f"/learn/{jid}/lesson/m1-l1?mini=1&key=x").text
    assert "data-mini-window" in page and "data-mw-back" in page and "data-ftimer" in page and "data-mw-start" not in page
    assert c.post("/window/popout", data={"url": "/"}).json() == {"ok": False}   # no app window in the tests
    assert c.post("/window/popout", data={"url": "https://evil.example/"}).json() == {"ok": False}
    assert c.post("/window/popout/close").json() == {"ok": False}


def test_phone_notification_shows_the_plain_timer(tmp_path, monkeypatch):
    monkeypatch.setenv("INPACE_MOBILE", "android")
    v, c = client(tmp_path, "Omar")
    c.post("/timer/start", data={"minutes": "25"}, headers=J)
    t = c.get("/island/live.json").json()["trip"]
    assert t["title"] == "Focus timer" and t["url"] == "/" and t["ends_ms"]
    assert t["actions"] is True and t["l_pause"] == "Pause" and t["l_stop"] == "Stop"   # buttons on the notification


def test_videos_show_in_the_systems_media_controls():
    import pathlib
    js = (pathlib.Path(__file__).resolve().parent.parent / "inpace/static/app.js").read_text(encoding="utf-8")
    assert "window.inpaceMediaSession = " in js and "new MediaMetadata" in js
    for action in ("play", "pause", "seekbackward", "seekforward", "previoustrack", "nexttrack"):
        assert f'set("{action}"' in js


def test_island_trip_has_the_same_buttons_and_they_change_the_trip(tmp_path):
    v, c = client(tmp_path, "Omar")
    garden.set_on(v, True)
    c.post("/timer/start", data={"minutes": "25", "plant": "1"}, headers=J)
    page = c.get("/island/trip").text
    assert 'action="/timer/pause"' in page and 'action="/timer/add"' in page and 'action="/island/rest"' in page
    r = c.post("/timer/pause", headers={"referer": "http://testserver/island/trip"}, follow_redirects=False)
    assert r.headers["location"].startswith("/island/trip")
    assert garden.active(v)["state"] == "paused"
    c.post("/island/resume")                        # coming back to the screen doesn't undo your pause
    assert garden.active(v)["state"] == "paused"
    assert 'action="/timer/resume"' in c.get("/island/trip").text
    c.post("/timer/resume", headers=J)
    assert c.post("/timer/add", headers=J).json()["goal"] == 30 * 60   # +5 min: the plant grows for 30
    assert garden.active(v)["goal"] == 30


def test_tempo_asks_nicely_for_notifications(tmp_path):
    v, c = client(tmp_path, "Omar")
    page = html.unescape(c.get("/courses").text)
    assert "data-notify-sheet" in page and "Can Tempo tap you on the shoulder?" in page
    assert "data-notify-yes" in page and "data-notify-later" in page


def test_android_has_a_media_session_and_fills_its_floating_window():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    prep = (root / "mobile/tools/prepare_android.py").read_text(encoding="utf-8")
    assert "MediaSessionCompat" in prep and "androidx.media:media" in prep and "MediaStyle" in prep
    dart = (root / "mobile/lib/main.dart").read_text(encoding="utf-8")
    assert "case 'media':" in dart and "inpaceMediaControl" in dart
    css = (root / "inpace/static/style.css").read_text(encoding="utf-8")
    assert "html.in-pip .pip-video video { position: absolute !important; inset: 0 !important; width: 100% !important; height: 100% !important;" in css


def test_v1304_fixes(tmp_path):
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    v, c = client(tmp_path, "Omar")
    # the lesson page carries the course picture, for the phone's media controls
    c.post("/courses/sample/python-basics")
    jid = c.post("/courses/python-basics/start", follow_redirects=False).headers["location"].rsplit("/", 1)[1]
    assert 'data-cover="/m/python-basics/' in c.get(f"/learn/{jid}/lesson/m1-l1").text
    js = (root / "inpace/static/app.js").read_text(encoding="utf-8")
    assert "const wantPip = () => { const n = window.inpaceNowPlaying; return !!(n && !n.v.paused && !n.v.ended); };" in js  # only video floats
    assert 'if (k !== "embed") player.dataset[k]' in js                                                          # YouTube keeps its id
    css = (root / "inpace/static/style.css").read_text(encoding="utf-8")
    assert ".look-pick input, .timer-len input { width: 1px !important" in css                                   # Settings no longer slides
    assert "html.in-pip .ftimer, html.in-pip .mini-bar, html.in-pip .notify-sheet { display: none !important; }" in css
    dart = (root / "mobile/lib/main.dart").read_text(encoding="utf-8")
    assert "_inPip = call.arguments == true" in dart and "floating: edge to edge" in dart


def test_youtube_subtitle_languages_are_picked_well():
    from inpace import offline
    info = {"language": "en",
            "subtitles": {"es": [{"ext": "json3", "url": "x"}, {"ext": "vtt", "url": "es.vtt", "name": "Spanish"}],
                          "live_chat": [{"ext": "vtt", "url": "chat"}]},
            "automatic_captions": {"en-orig": [{"ext": "vtt", "url": "en.vtt", "name": "English (Original)"}],
                                   "en": [{"ext": "vtt", "url": "en2.vtt", "name": "English"}],
                                   "ar": [{"ext": "vtt", "url": "ar.vtt", "name": "Arabic"}],
                                   "fr": [{"ext": "vtt", "url": "fr.vtt", "name": "French"}]}}
    got = offline.pick_subtitles(info, "ar")
    assert [(t["lang"], t["auto"]) for t in got] == [("es", False), ("en", True), ("ar", True)]   # no chat, no French
    assert got[1]["name"] == "English" and got[2]["translated"] is True


def test_youtube_subtitles_routes(tmp_path, monkeypatch):
    from inpace import offline
    v, c = client(tmp_path, "Omar")
    monkeypatch.setattr(offline, "subtitles", lambda home, vid, ui="en", load_fn=None: {"tracks": [
        {"lang": "en", "name": "English", "auto": True, "url": "u"}, {"lang": "es", "name": "Spanish", "auto": False, "url": "u2"}]})
    d = c.get("/yt-subs/dQw4w9WgXcQ.json").json()
    assert [t["label"] for t in d["tracks"]] == ["English · made by YouTube", "Spanish"]
    monkeypatch.setattr(offline, "subtitle_text", lambda home, vid, lang, ui="en", fetch=None: "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhi\n")
    r = c.get("/yt-subs/dQw4w9WgXcQ/en.vtt")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/vtt")
    monkeypatch.setattr(offline, "subtitle_text", lambda *a, **k: "")
    assert c.get("/yt-subs/dQw4w9WgXcQ/xx.vtt").status_code == 404


def test_quality_menu_mirrors_youtube_and_youtube_screen_stays_hidden():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    js = (root / "inpace/static/app.js").read_text(encoding="utf-8")
    assert "i.availableQualityLevels" in js and "youtubeQuality(player, frame, v, box)" in js
    css = (root / "inpace/static/style.css").read_text(encoding="utf-8")
    assert "html.in-pip .pip-video .yt-cover { display: block !important;" in css


def test_quality_menu_asks_for_that_size(tmp_path, monkeypatch):
    """Picking 720p in a YouTube lesson's quality menu gets the video at that size, even with the ad blocker off."""
    from inpace import offline, ytrules
    v, c = client(tmp_path, "Omar")
    seen = {}

    def fake_stream(home, vid, load_fn=None, hls=False, quality="720", sized=False):
        seen.update(quality=quality, sized=sized)
        return {"video": "https://x/v.mp4", "audio": "https://x/a.m4a", "height": int(quality)}
    monkeypatch.setattr(offline, "stream", fake_stream)
    monkeypatch.setattr(ytrules, "current", lambda: {"ad_block": False})
    assert c.get("/yt-stream/dQw4w9WgXcQ").json().get("why")              # the plain ad-free choice is off
    d = c.get("/yt-stream/dQw4w9WgXcQ?q=720").json()                      # the quality menu still works
    assert d["height"] == 720 and seen == {"quality": "720", "sized": True}


def test_sized_stream_puts_the_size_first(tmp_path):
    class Fake:
        opts = []

        class YoutubeDL:
            def __init__(self, o): Fake.opts.append(o)
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def extract_info(self, url, download=False):
                return {"requested_formats": [{"vcodec": "avc1", "url": "https://v", "height": 1080},
                                              {"acodec": "mp4a", "vcodec": "none", "url": "https://a"}]}
    from inpace import offline
    out = offline.stream(tmp_path, "dQw4w9WgXcQ", load_fn=lambda h: Fake, quality="1080", sized=True)
    assert out["height"] == 1080 and Fake.opts[-1]["format"].startswith("bv*[ext=mp4][vcodec^=avc1][height<=1080]")
    offline.stream(tmp_path, "dQw4w9WgXcQ", load_fn=lambda h: Fake, quality="1080")
    assert Fake.opts[-1]["format"].startswith("18/")                      # the ad-free choice keeps the quick file first


def test_phone_page_view_is_not_rebuilt_for_the_floating_window():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    dart = (root / "mobile/lib/main.dart").read_text(encoding="utf-8")
    assert "WebViewWidget(key: _webKey" in dart and "top: !_inPip" in dart
    js = (root / "inpace/static/app.js").read_text(encoding="utf-8")
    assert "revive()" in js and '"unloadModule", ["captions"]' in js and "ytOwnPlayer(" in js


def test_amoled_black_and_phone_landscape_layout(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/settings/look", data={"theme": "dark", "dark_style": "black"})
    page = c.get("/courses").text
    assert 'data-theme="dark" data-black' in page
    c.post("/settings/look", data={"theme": "", "dark_style": ""})
    assert "data-black" not in c.get("/courses").text.split(">", 2)[1]
    import pathlib
    css = (pathlib.Path(__file__).resolve().parent.parent / "inpace/static/style.css").read_text(encoding="utf-8")
    assert ":root[data-black][data-theme=dark]" in css
    # 761-860px wide (a phone on its side): the side menu is hidden, so the page must not keep its column
    assert "@media (min-width: 861px) { .shell { grid-template-columns: 228px" in css
