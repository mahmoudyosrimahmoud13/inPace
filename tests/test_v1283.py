"""v1.28.3: honest update notice, new library courses, Markdown extras, YouTube with inPace's controls."""
import html
import json

from inpace import library, media, updater
from inpace.app import md
from tests.test_app import client


def test_the_running_copy_is_not_called_out_of_date():
    assert not updater.newer(updater.__version__)
    assert updater.newer("99.0.0")


def _index(*ids):
    return {"courses": [{"id": i, "title": f"Course {i}", "hash": "h", "modules": 1, "lessons": 1} for i in ids]}


def test_new_library_courses_get_a_badge_then_a_new_tag(tmp_path, monkeypatch):
    v, c = client(tmp_path, "Omar")
    monkeypatch.setattr(library, "load_index", lambda home, refresh=False: _index("a", "b"))
    c.get("/library")                     # first look: remembers, nothing is "new"
    assert json.loads(v._meta("library_new", "[]")) == []
    monkeypatch.setattr(library, "load_index", lambda home, refresh=False: _index("a", "b", "c"))
    page = html.unescape(c.get("/library").text)
    assert "New</span>" in page and "1 new course(s)" in page
    assert page.index("Course c") < page.index("Course a")   # new ones first
    assert json.loads(v._meta("library_new", "[]")) == []    # seen now: the badge goes away
    assert "Look for new courses" in page                    # the Refresh button


def test_markdown_extras():
    out = md.render("~~old~~ see https://ex.org/x.\n\n- [x] done\n\n> [!TIP]\n> hi\n\nA[^1].\n\n[^1]: note\n")
    assert "<s>old</s>" in out and '<a href="https://ex.org/x">' in out
    assert 'type="checkbox" disabled checked' in out and "callout-tip" in out
    assert 'href="#fn-1"' in out and '<li id="fn-1"' in out and "note" in out


def test_youtube_hides_its_own_controls():
    class T(str):
        pass
    out = media.youtube_player("c1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "", lambda _: False, lambda s: s)
    assert "controls=0" in out and 'data-l-full="Full screen"' in out
    assert 'data-yt-id="dQw4w9WgXcQ"' in out and 'data-l-pip=' in out   # the same player labels as video files


def test_script_and_style_links_change_when_the_files_change(tmp_path):
    from inpace.app import STATIC_V
    v, c = client(tmp_path, "Omar")
    page = c.get("/").text
    assert f"/static/app.js?v={STATIC_V['app.js']}" in page and f"/static/style.css?v={STATIC_V['style.css']}" in page
    assert "?v=30" not in page and "?v=36" not in page


def test_delete_all_my_data(tmp_path):
    v, c = client(tmp_path, "Omar")
    (v.home / "courses" / "mine").mkdir()
    (v.home / "notes.txt").write_text("x")
    r = c.post("/settings/delete-everything", data={"confirm": "nope"})
    assert "Nothing was deleted" in html.unescape(r.text) and (v.home / "notes.txt").exists()
    r = c.post("/settings/delete-everything", data={"confirm": "DELETE"})
    assert not (v.home / "notes.txt").exists() and not (v.home / "courses" / "mine").exists()
    assert not v.is_set_up and "Welcome to inPace" in html.unescape(r.text)


def test_youtube_has_quality_and_ad_labels():
    out = media.youtube_player("c1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "", lambda _: False, lambda s: s)
    assert 'data-l-quality="Quality"' in out and 'data-l-auto="Auto"' in out and "data-l-ad=" in out


def test_youtube_rules_are_data_only_and_checked():
    from inpace import ytrules
    r = ytrules.clean({"own_controls": "yes", "fallback_ms": 10**9, "cover_after_ms": 1000, "evil": "<script>"})
    assert r["own_controls"] is True and r["fallback_ms"] == 9000 and r["cover_after_ms"] == 1000 and "evil" not in r


def test_ad_guard_is_on_by_default_and_can_be_turned_off(tmp_path):
    v, c = client(tmp_path, "Omar")
    assert "Ad guard" in html.unescape(c.get("/settings").text)
    out = media.youtube_player("c1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "", lambda _: False, lambda s: s)
    assert "&quot;ad_guard&quot;: true" in out and "controls=0" in out
    c.post("/settings/youtube", data={})                       # unticked
    out = media.youtube_player("c1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "", lambda _: False, lambda s: s)
    assert "&quot;ad_guard&quot;: false" in out and "controls=0" in out   # still inPace's player


def test_files_one_folder_down_in_the_chosen_folder_are_found(tmp_path):
    """Slides kept as "DLS Slides/DLS_C1/C1_W1.pdf": choosing "DLS Slides" is enough."""
    v, c = client(tmp_path, "Omar")
    nested = tmp_path / "DLS Slides" / "DLS_C1"
    nested.mkdir(parents=True)
    (nested / "C1_W1.pdf").write_bytes(b"%PDF-1.4")
    v.set_media_root("slides", str(tmp_path / "DLS Slides"))
    assert v.find_media("slides", "C1_W1.pdf#pages=2-4") == nested / "C1_W1.pdf"
    assert v.find_media("slides", "C9_W9.pdf") is None


def test_find_course_files_in_a_folder_or_a_zip(tmp_path, monkeypatch):
    import zipfile as zf_mod
    from inpace import coursefiles
    dl = tmp_path / "Downloads"
    (dl / "DLS Slides" / "DLS_C1").mkdir(parents=True)
    (dl / "DLS Slides" / "DLS_C1" / "C1_W1.pdf").write_bytes(b"%PDF")
    assert coursefiles.find_folder({"C1_W1.pdf"}, [dl]) == dl / "DLS Slides"
    with zf_mod.ZipFile(dl / "slides.zip", "w") as z:
        z.writestr("Slides/C2/C2_W1.pdf", b"%PDF")
        z.writestr("__MACOSX/Slides/._C2_W1.pdf", b"x")
        z.writestr("../evil.txt", b"x")
    assert coursefiles.find_zip({"C2_W1.pdf"}, [dl]) == dl / "slides.zip"
    out = coursefiles.unzip(dl / "slides.zip", tmp_path / "inpace" / "course-files" / "c2")
    assert (out / "Slides" / "C2" / "C2_W1.pdf").is_file()
    assert not (tmp_path / "inpace" / "course-files" / "evil.txt").exists() and not (out / "__MACOSX").exists()


# ---- 1.28.11: the ad blocker (yt-dlp finds the plain file; inPace's own player plays it) ----
def test_stream_uses_ytdlp_and_caches(tmp_path):
    from inpace import offline
    calls = []

    class FakeDL:
        def __init__(self, opts): self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=False):
            calls.append((url, download, self.opts["format"]))
            return {"url": "https://rr1.googlevideo.com/videoplayback?x=1", "height": 360}

    fake = type("M", (), {"YoutubeDL": FakeDL})
    offline._STREAMS.clear()
    got = offline.stream(tmp_path, "CS4cs9xVecg", load_fn=lambda h: fake)
    assert got == {"url": "https://rr1.googlevideo.com/videoplayback?x=1", "height": 360}
    assert calls[0][1] is False and "acodec!=none" in calls[0][2]
    offline.stream(tmp_path, "CS4cs9xVecg", load_fn=lambda h: fake)
    assert len(calls) == 1  # kept, not asked again


def test_stream_refuses_bad_ids_and_bad_urls(tmp_path):
    from inpace import offline

    class Bad:
        def __init__(self, o): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, *a, **k): return {"url": "file:///etc/passwd"}

    offline._STREAMS.clear()
    assert "url" not in offline.stream(tmp_path, "../../etc", load_fn=lambda h: None)
    got = offline.stream(tmp_path, "AAAAAAAAAAA", load_fn=lambda h: type("M", (), {"YoutubeDL": Bad}))
    assert "url" not in got and got["why"]


def test_ad_block_rule_and_setting(tmp_path):
    from inpace import ytrules
    assert ytrules.clean({})["ad_block"] is True
    assert ytrules.clean({"ad_block": "yes"})["ad_block"] is True
    assert ytrules.clean({"ad_block_wait_ms": 1})["ad_block_wait_ms"] == 12000
    ytrules.use_home(tmp_path, pref=lambda: True, block_pref=lambda: False)
    try:
        assert ytrules.current()["ad_block"] is False
    finally:
        ytrules.use_home(tmp_path)


def test_player_asks_for_the_ad_free_file(tmp_path):
    from inpace import media, ytrules
    ytrules.use_home(tmp_path)
    out = media.youtube_player("c", "https://www.youtube.com/watch?v=CS4cs9xVecg", "", lambda p: False, lambda s, **k: s)
    assert 'data-yt-noads="/yt-stream/CS4cs9xVecg"' in out and "Play without ads" in out
    ytrules.use_home(tmp_path, block_pref=lambda: False)
    try:
        out = media.youtube_player("c", "https://www.youtube.com/watch?v=CS4cs9xVecg", "", lambda p: False, lambda s, **k: s)
        assert "data-yt-noads" not in out
    finally:
        ytrules.use_home(tmp_path)


def test_stream_says_why_when_ytdlp_fails(tmp_path):
    from inpace import offline

    class Boom:
        def __init__(self, o): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, *a, **k): raise RuntimeError("Sign in to confirm you're not a bot")

    offline._STREAMS.clear()
    got = offline.stream(tmp_path, "BBBBBBBBBBB", load_fn=lambda h: type("M", (), {"YoutubeDL": Boom}))
    assert "url" not in got and "bot" in got["why"]


def test_hidden_player_bar_cannot_be_touched():
    import pathlib
    css = (pathlib.Path(__file__).parent.parent / "inpace" / "static" / "style.css").read_text()
    assert ".player.playing:not(.awake) .pl-bar { opacity: 0; pointer-events: none; }" in css


def test_stream_two_files_and_other_clients(tmp_path):
    from inpace import offline
    seen = []

    class DL:
        def __init__(self, o): self.o = o
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, *a, **k):
            seen.append(self.o.get("extractor_args"))
            if not self.o.get("extractor_args"):
                raise RuntimeError("Requested format is not available")
            return {"requested_formats": [
                {"url": "https://v.googlevideo.com/v", "vcodec": "avc1", "acodec": "none", "height": 720},
                {"url": "https://v.googlevideo.com/a", "vcodec": "none", "acodec": "mp4a"}]}

    offline._STREAMS.clear()
    got = offline.stream(tmp_path, "CCCCCCCCCCC", load_fn=lambda h: type("M", (), {"YoutubeDL": DL}))
    assert got == {"video": "https://v.googlevideo.com/v", "audio": "https://v.googlevideo.com/a", "height": 720}
    assert seen[0] is None and "tv" in seen[1]["youtube"]["player_client"]


def test_youtube_box_offers_two_choices(tmp_path):
    from inpace import media, ytrules
    ytrules.use_home(tmp_path)
    out = media.youtube_player("c", "https://www.youtube.com/watch?v=CS4cs9xVecg", "", lambda p: False, lambda s, **k: s)
    assert 'class="yt-choice play"' in out and 'class="yt-choice" data-yt-noads' in out and "Play on YouTube" in out and "yt-noads-row" not in out


# ---- 1.28.16: library sections and a smarter search ----
def test_library_groups_by_section_and_level():
    from inpace.app import _library_groups
    index = {"sections": [{"id": "linux-cloud-devops", "en": "Linux, Cloud and DevOps", "ar": "لينكس"},
                          {"id": "languages", "en": "Languages", "ar": "اللغات"}]}
    entries = [
        {"id": "adv", "title": "Advanced Linux", "section": "linux-cloud-devops", "tags": ["linux", "advanced"], "language": "en"},
        {"id": "fund", "title": "Linux Fundamentals", "section": "linux-cloud-devops", "tags": ["linux", "beginner"], "language": "en"},
        {"id": "eng", "title": "English A1", "section": "languages", "tags": ["english", "beginner"], "language": "ar"},
        {"id": "odd", "title": "Something else", "section": "unknown", "tags": [], "language": "en"},
    ]
    groups, topics = _library_groups(index, entries, "ar")
    assert [g["id"] for g in groups] == ["linux-cloud-devops", "languages", "other"]
    assert [e["id"] for e in groups[0]["entries"]] == ["fund", "adv"]          # beginner before advanced
    assert groups[0]["label"] == "لينكس" and topics[0] == {"id": "linux-cloud-devops", "label": "لينكس"}


def test_library_without_sections_still_works():
    from inpace.app import _library_groups
    entries = [{"id": "a", "title": "A", "tags": ["python", "web"]}, {"id": "b", "title": "B", "tags": ["python"]}]
    groups, topics = _library_groups({}, entries, "en")
    assert len(groups) == 1 and len(groups[0]["entries"]) == 2
    assert topics == [{"id": "python", "label": "python"}]


def test_library_page_has_sections_and_filters(tmp_path):
    import json
    from tests.test_app import client
    v, c = client(tmp_path, "Sara")
    (v.home / "library.json").write_text(json.dumps({"inpace": "library", "v": 1, "sections": [
        {"id": "data-databases", "en": "Data and Databases", "ar": "البيانات"}], "courses": [
        {"id": "pg", "title": "PostgreSQL for Beginners", "description": "SQL", "section": "data-databases", "language": "en",
         "tags": ["postgresql", "beginner"], "hash": "x", "modules": 1, "lessons": 1, "minutes": 30,
         "outline": [{"title": "Day 1", "lessons": [{"title": "Install and meet psql"}]}]}], "roadmaps": []}))
    page = c.get("/library").text
    assert "Data and Databases" in page and 'data-section="data-databases"' in page
    assert 'data-level="beginner"' in page and "data-lib-level" in page and "install and meet psql" in page


def test_roadmap_thumbnail_uses_covers_and_path():
    from inpace.app import roadmap_thumb
    rm = {"id": "x", "steps": [{"course": f"c{i}"} for i in range(6)]}
    pics = {"c0": ("img", "https://ex.com/a.jpg"), "c1": ("blank", "P", 120)}
    html = str(roadmap_thumb(rm, pics))
    assert 'src="https://ex.com/a.jpg"' in html and "rt-blank" in html and ">P<" in html
    assert html.count('class="rt-c ') == 3 and "+3" in html and "⚓" in html and "6 courses" in html


def test_roadmap_pages_show_thumbnails(tmp_path):
    import json
    from tests.test_app import client
    v, c = client(tmp_path, "Sara")
    (v.home / "library.json").write_text(json.dumps({"inpace": "library", "v": 1, "courses": [
        {"id": "pg", "title": "PostgreSQL", "description": "SQL", "language": "en", "hash": "x", "modules": 1, "lessons": 1,
         "minutes": 30, "cover": "https://ex.com/pg.jpg"}],
        "roadmaps": [{"id": "sql", "title": "SQL path", "description": "", "language": "en", "tags": [], "hash": "h",
                      "author": {"name": "inPace", "verified": True}, "steps": [{"course": "pg"}], "needs": 1}]}))
    lib = c.get("/library?tab=roadmaps").text
    assert 'class="rt"' in lib and "https://ex.com/pg.jpg" in lib
    c.post("/roadmaps/sql/follow")
    assert 'class="rt"' in c.get("/roadmaps").text
    assert 'class="rt big"' in c.get("/roadmaps/sql").text
