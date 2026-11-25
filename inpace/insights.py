"""Insights (v1.37): how your studying goes, in a few charts. Focus time per day, lessons finished, the hours
you work best, each course's progress, and for every running sprint, the plan against what you ticked.

Everything comes from what inPace already keeps: the focus timer's totals per hour, the events of each course
(a finished lesson, a quiz, a task), and the sprint's log of ticks. The charts are small inline SVGs drawn here,
so the page is just HTML: nothing to download, and they follow the theme's colours."""
from __future__ import annotations

import datetime as _dt
import html
from collections import Counter

from . import focus, roadmaps

DAYS = 28  # the daily charts look back four weeks


# ---- the numbers -------------------------------------------------------------------------------------------

def _local_date(at: str) -> _dt.date | None:
    """The local day of an event stamp like 2026-11-24T20:10:00Z."""
    try:
        when = _dt.datetime.strptime(at[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_dt.timezone.utc)
        return when.astimezone().date()
    except ValueError:
        return None


def study(v, today: _dt.date | None = None, days: int = DAYS) -> dict:
    """Your last `days` days: focus minutes and finished lessons per day, quizzes, the best hours, the streak,
    this week against last week, and each course's progress."""
    today = today or _dt.date.today()
    first = today - _dt.timedelta(days=days - 1)
    dates = [first + _dt.timedelta(days=i) for i in range(days)]
    keys = [d.isoformat() for d in dates]

    hours = focus.hour_totals(v)
    by_day: Counter = Counter()
    by_hour: Counter = Counter()  # hour of the day (0-23) -> seconds, over the whole history kept
    for k, secs in hours.items():
        by_day[k[:10]] += int(secs)
        if "T" in k:
            try:
                by_hour[int(k[11:13])] += int(secs)
            except ValueError:
                pass
    focus_min = [by_day.get(k, 0) // 60 for k in keys]

    lessons: Counter = Counter()
    quizzes: Counter = Counter()
    courses = []
    for j in v.journeys():
        for e in v.events(j["id"]):
            d = _local_date(e["at"])
            if not d or d < first:
                continue
            if e["type"] == "lesson_done":
                lessons[d.isoformat()] += 1
            elif e["type"] in ("quiz_taken", "exam_taken"):
                quizzes[d.isoformat()] += 1
        try:
            p = v.progress(j["id"])
        except Exception:
            continue
        if p.get("course"):
            courses.append({"id": j["id"], "course": j["course_id"], "title": p["course"].title,
                            "percent": p["percent"], "done": p["lessons_done"], "total": p["lessons_total"],
                            "finished": p["finished"]})
    lessons_n = [lessons.get(k, 0) for k in keys]
    quizzes_n = [quizzes.get(k, 0) for k in keys]
    courses.sort(key=lambda c: (c["finished"], -c["percent"]))

    active = [bool(focus_min[i] or lessons_n[i] or quizzes_n[i]) for i in range(days)]
    streak = 0
    for i in range(days - 1, -1, -1):
        if active[i]:
            streak += 1
        elif i < days - 1:  # today may still be empty; yesterday ends the streak
            break
    week = lambda a, b: {"focus": sum(focus_min[a:b]), "lessons": sum(lessons_n[a:b]), "quizzes": sum(quizzes_n[a:b])}
    this_week, last_week = week(days - 7, days), week(days - 14, days - 7)
    top_hour = max(by_hour, key=by_hour.get) if by_hour else None
    return {"dates": dates, "focus": focus_min, "lessons": lessons_n, "quizzes": quizzes_n, "active": active,
            "streak": streak, "this_week": this_week, "last_week": last_week,
            "hours": [by_hour.get(h, 0) // 60 for h in range(24)], "top_hour": top_hour,
            "courses": courses, "total_focus": sum(focus_min), "total_lessons": sum(lessons_n),
            "active_days": sum(active)}


def sprint(rm: dict, sp: dict) -> dict | None:
    """One running sprint: per day, what the plan expected to be ticked by then, what was ticked, the focus
    minutes against the daily goal, and the days worked."""
    if not sp.get("running"):
        return None
    run = rm["sprint_run"]
    units = sum(r["units"] for r in sp["steps"] if not r["optional"]) or 1
    expected = []
    for d in range(1, run["days"] + 1):
        expected.append(sum(r["units"] for r in sp["steps"] if r["range"] and r["range"][1] <= d and not r["optional"]))
    ticked = [0] * run["days"]
    for at, _c, _i, on in run.get("log") or []:
        try:
            d = roadmaps.sprint_day(run, _dt.datetime.fromisoformat(at))
        except ValueError:
            continue
        if 1 <= d <= run["days"]:
            ticked[d - 1] += 1 if on else -1
    done = []
    total = 0
    for n in ticked:
        total = max(0, total + n)
        done.append(min(total, units))
    today = max(1, min(sp["day"], run["days"]))
    strip = sp["strip"]
    return {"days": run["days"], "day": sp["day"], "today": today, "units": units,
            "expected": expected, "done": done[:today] if sp["day"] >= 1 else [],
            "focus": [x["focus"] for x in strip], "goal": sp["focus_goal"],
            "ticks": [x["ticks"] for x in strip], "percent": sp["percent"],
            "on_track": (done[today - 1] if sp["day"] >= 1 else 0) >= expected[today - 1],
            "worked": sum(1 for x in strip[:today] if x["ticks"] or x["focus"]) if sp["day"] >= 1 else 0}


# ---- the charts (inline SVG) ---------------------------------------------------------------------------------

def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def bars(values: list[int], labels: list[str], title: str, unit: str = "", goal: int | None = None,
         mark: int | None = None, tone: str = "sun") -> str:
    """A bar for each value, the labels under some of them, an optional dotted goal line, and the bar `mark`
    highlighted (today)."""
    n = max(1, len(values))
    top = max(max(values or [0]), goal or 0, 1)
    W, H, pad_l, pad_b, pad_t = 600, 180, 34, 24, 10
    gap = 3
    bw = (W - pad_l) / n - gap
    ih = H - pad_b - pad_t
    y = lambda val: pad_t + ih - ih * val / top
    out = [f'<svg class="chart tone-{tone}" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(title)}">']
    for frac in ((0.5, 1.0) if top >= 2 else (1.0,)):
        out.append(f'<line class="ch-grid" x1="{pad_l}" x2="{W}" y1="{y(top * frac):.1f}" y2="{y(top * frac):.1f}"/>')
        out.append(f'<text class="ch-axis" x="{pad_l - 6}" y="{y(top * frac) + 4:.1f}" text-anchor="end">{int(top * frac)}{_esc(unit)}</text>')
    if goal:
        out.append(f'<line class="ch-goal" x1="{pad_l}" x2="{W}" y1="{y(goal):.1f}" y2="{y(goal):.1f}"/>')
    step = max(1, n // 7)
    for i, val in enumerate(values):
        x = pad_l + i * (bw + gap)
        cls = "ch-bar on" if i == mark else "ch-bar"
        if val:
            out.append(f'<rect class="{cls}" x="{x:.1f}" y="{y(val):.1f}" width="{bw:.1f}" height="{ih * val / top:.1f}" rx="2"><title>{_esc(labels[i])}: {val}{_esc(unit)}</title></rect>')
        else:
            out.append(f'<rect class="{cls} empty" x="{x:.1f}" y="{H - pad_b - 2}" width="{bw:.1f}" height="2" rx="1"/>')
        if i % step == 0 or i == n - 1:
            out.append(f'<text class="ch-axis" x="{x + bw / 2:.1f}" y="{H - 6}" text-anchor="middle">{_esc(labels[i])}</text>')
    out.append("</svg>")
    return "".join(out)


def lines(expected: list[int], done: list[int], title: str, labels: list[str]) -> str:
    """The plan (a thin line) against what was ticked (a thick one), by sprint day."""
    n = max(2, len(expected))
    top = max(max(expected or [0]), max(done or [0]), 1)
    W, H, pad_l, pad_b, pad_t, pad_r = 600, 180, 34, 24, 10, 10
    ih = H - pad_b - pad_t
    x = lambda i: pad_l + (W - pad_l - pad_r) * i / (n - 1)
    y = lambda val: pad_t + ih - ih * val / top
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(title)}">']
    for frac in ((0.5, 1.0) if top >= 2 else (1.0,)):
        out.append(f'<line class="ch-grid" x1="{pad_l}" x2="{W - pad_r}" y1="{y(top * frac):.1f}" y2="{y(top * frac):.1f}"/>')
        out.append(f'<text class="ch-axis" x="{pad_l - 6}" y="{y(top * frac) + 4:.1f}" text-anchor="end">{int(top * frac)}</text>')
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(expected))
    out.append(f'<polyline class="ch-plan" points="{pts}"/>')
    if done:
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(done))
        out.append(f'<polyline class="ch-done" points="{pts}"/>')
        i, v = len(done) - 1, done[-1]
        out.append(f'<circle class="ch-dot" cx="{x(i):.1f}" cy="{y(v):.1f}" r="5"><title>{_esc(labels[i])}: {v}</title></circle>')
    for i, lab in enumerate(labels):
        if i % max(1, n // 7) == 0 or i == n - 1:
            out.append(f'<text class="ch-axis" x="{x(i):.1f}" y="{H - 6}" text-anchor="middle">{_esc(lab)}</text>')
    out.append("</svg>")
    return "".join(out)


def clock(hours: list[int], title: str) -> str:
    """Twenty-four cells, one per hour of the day, darker the more you focused then."""
    top = max(max(hours or [0]), 1)
    W, H = 600, 54
    cw = W / 24
    out = [f'<svg class="chart clock tone-sun" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(title)}">']
    for h, m in enumerate(hours):
        a = 0.08 + 0.92 * m / top if m else 0.06
        out.append(f'<rect class="ch-cell" x="{h * cw + 1:.1f}" y="4" width="{cw - 2:.1f}" height="30" rx="3" style="opacity:{a:.2f}"><title>{h:02d}:00 · {m} min</title></rect>')
        if h % 6 == 0:
            out.append(f'<text class="ch-axis" x="{h * cw + 1:.1f}" y="{H - 4}">{h:02d}</text>')
    out.append("</svg>")
    return "".join(out)
