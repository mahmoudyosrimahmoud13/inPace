"""v1.15.1: moving through a course: next module, Back goes to the course, a tidier My courses, phones."""
import html
import sys

import pytest

from tests.test_app import client


def _tour(tmp_path):
    v, c = client(tmp_path, "Omar")
    c.post("/courses/sample/tour")
    c.post("/courses/tour/start")
    return v, c, v.journey_for_course("tour")


def test_finished_module_offers_the_next_one(tmp_path):
    v, c, jid = _tour(tmp_path)
    m1 = v.get_course("tour").modules[0]
    for les in m1["lessons"]:
        r = c.post(f"/learn/{jid}/lesson/{les['id']}/done", data={}, follow_redirects=False)
    assert r.headers["location"].startswith(f"/learn/{jid}/module/{m1['id']}")
    page = html.unescape(c.get(f"/learn/{jid}/module/{m1['id']}").text)
    m2 = v.get_course("tour").modules[1]
    assert "Start the next module" in page and f"/learn/{jid}/lesson/{m2['lessons'][0]['id']}" in page
    assert "Next: " + m2["title"] in page
    # The course page has a Continue button to the next lesson.
    course = html.unescape(c.get(f"/learn/{jid}").text)
    assert "continue-btn" in course and m2["lessons"][0]["title"] in course


def test_lesson_done_can_answer_for_in_page_navigation(tmp_path):
    v, c, jid = _tour(tmp_path)
    les = v.get_course("tour").modules[0]["lessons"]
    r = c.post(f"/learn/{jid}/lesson/{les[0]['id']}/done", data={"next": les[1]["id"]}, headers={"X-InPace-Nav": "1"})
    assert r.status_code == 200 and r.json()["go"].startswith(f"/learn/{jid}/lesson/{les[1]['id']}")
    page = c.get(f"/learn/{jid}/lesson/{les[1]['id']}").text
    # Links inside a course replace the page, so Back goes to the course and not through every lesson.
    assert "data-replace" in page and "data-nav-form" in page and "data-up" in page


def test_my_courses_is_simple(tmp_path):
    v, c, jid = _tour(tmp_path)
    page = html.unescape(c.get("/courses").text)
    assert 'class="card course-card' in page and f'href="/learn/{jid}"' in page
    assert "% · Next: " in page and "Sample courses (" in page
    assert page.count('class="btn primary"') <= 2  # one Add button, not a row of buttons per course


@pytest.mark.skipif(sys.version_info < (3, 10), reason="the app needs 3.10")
def test_every_file_compiles_on_the_oldest_python():
    """f-strings with a backslash inside { } only work from Python 3.12. CI runs 3.10, so catch it here too."""
    import ast
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    bad = []
    for p in list((root / "inpace").rglob("*.py")) + list((root / "packaging").glob("*.py")):
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FormattedValue):
                seg = ast.get_source_segment(src, node.value) or ""
                if "\\" in seg:
                    bad.append(f"{p.name}:{node.lineno}")
    assert not bad, bad
