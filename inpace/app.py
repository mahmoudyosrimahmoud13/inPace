"""The local web app. Runs only on this computer (127.0.0.1)."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from markdown_it import MarkdownIt
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import ai, exchange
from .canon import now_utc, short
from .course import (Course, CourseError, course_to_pack, files_from_folder, files_from_zip, load_course,
                     strip_fences)
from .exam import NoAnswers, build_exam, grade, new_seed
from .vault import COLORS, Vault, display_name

HERE = Path(__file__).parent
SAMPLES = HERE / "sample_courses"
MEANINGFUL = {"lesson_done", "evidence_added", "writeup_saved", "quiz_taken"}

md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
env.filters["short"] = short
env.filters["date"] = lambda s: (s or "")[:10]
env.globals["display_name"] = display_name


def avatar(p: dict, size: int = 36) -> Markup:
    color = p.get("color") or "#3A506B"
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        color = "#3A506B"
    letter = (display_name(p) or "?")[:1].upper()
    return Markup('<span class="avatar" style="--c: {}; --s: {}px" aria-hidden="true">{}</span>').format(
        color, int(size), letter)


env.globals["avatar"] = avatar


def create_app(vault: Vault) -> Starlette:
    V = vault

    # ---- helpers -------------------------------------------------------------
    def page(name: str, request: Request, **ctx) -> HTMLResponse:
        base = {"request": request, "msg": request.query_params.get("ok"), "err": request.query_params.get("err")}
        if V.is_set_up:
            base["me"] = V.me
            base["checking"] = [
                {**p, "waiting": V.waiting_count(p["id"])} for p in V.people() if p["i_check"]
            ]
            base["active_path"] = request.url.path
        return HTMLResponse(env.get_template(name).render(**base, **ctx))

    def go(url: str, ok: str | None = None, err: str | None = None) -> RedirectResponse:
        if ok:
            url += ("&" if "?" in url else "?") + "ok=" + quote(ok)
        if err:
            url += ("&" if "?" in url else "?") + "err=" + quote(err)
        return RedirectResponse(url, status_code=303)

    def download(data: bytes, filename: str, mime: str = "application/octet-stream") -> Response:
        safe = re.sub(r"[^\w .,()-]+", "", filename, flags=re.UNICODE).strip() or "file"
        return Response(data, media_type=mime, headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(safe)}"})

    def journey_or_404(jid: str):
        j = V.journey(jid)
        if not j or not V.get_course(j["course_id"]):
            return None
        return j

    def has_new(jid: str) -> bool:
        return any(e["type"] in MEANINGFUL for e in V.events(jid, V.last_event_in_milestones(jid)))

    def journey_card(j: dict) -> dict:
        prog = V.progress(j["id"])
        ms = V.milestones(j["id"])
        last_ok = next((a for m in reversed(ms) for a in m["approvals"] if a["decision"] == "approved"), None)
        waiting = [m for m in ms if not any(a["decision"] == "approved" for a in m["approvals"])]
        return {"journey": j, "progress": prog, "milestones": ms, "last_ok": last_ok, "waiting": waiting,
                "has_new": has_new(j["id"]), "chain_problems": V.check_my_chain(j["id"])}

    # ---- setup ---------------------------------------------------------------
    async def setup(request: Request):
        if request.method == "POST":
            form = await request.form()
            name = str(form.get("name", "")).strip()
            if not name:
                return page("setup.html", request, colors=COLORS, error="Please type your name.")
            V.setup(name, str(form.get("color", COLORS[0])))
            return go("/", ok=f"Welcome, {name}! Pick a course to start.")
        return page("setup.html", request, colors=COLORS)

    async def home(request: Request):
        if not V.is_set_up:
            return go("/setup")
        cards = [journey_card(j) for j in V.journeys()]
        return page("home.html", request, cards=cards, checkers=V.my_checkers(), courses=V.courses())

    # ---- courses ---------------------------------------------------------------
    async def courses(request: Request):
        installed = V.courses()
        have = {c.id for c in installed}
        samples = []
        for p in sorted(SAMPLES.iterdir()):
            if p.is_dir() and p.name not in have:
                try:
                    samples.append(load_course(files_from_folder(p)))
                except CourseError:
                    pass
        rows = [{"course": c, "journey": V.journey_for_course(c.id)} for c in installed]
        return page("courses.html", request, rows=rows, samples=samples)

    async def add_sample(request: Request):
        cid = request.path_params["cid"]
        folder = SAMPLES / cid
        if not folder.is_dir():
            return go("/courses", err="That sample course wasn't found.")
        c = V.install_course(load_course(files_from_folder(folder)))
        return go("/courses", ok=f"Added “{c.title}”. Press Start when you're ready.")

    async def start_course(request: Request):
        cid = request.path_params["cid"]
        if not V.get_course(cid):
            return go("/courses", err="That course isn't installed.")
        jid = V.start_journey(cid)
        return go(f"/learn/{jid}")

    async def export_course(request: Request):
        c = V.get_course(request.path_params["cid"])
        if not c:
            return go("/courses", err="That course isn't installed.")
        with_answers = request.query_params.get("answers") == "1"
        suffix = " (with answers)" if with_answers else ""
        return download(course_to_pack(c, with_answers), f"{c.title}{suffix}.lpack")

    async def remove_course(request: Request):
        cid = request.path_params["cid"]
        if V.journey_for_course(cid):
            return go("/courses", err="You've started this course, so it can't be removed. Your progress depends on it.")
        V.delete_course(cid)
        return go("/courses", ok="Course removed.")

    # ---- AI course maker -----------------------------------------------------
    async def ai_page(request: Request):
        ctx: dict = {"step": 1, "form": {}}
        if request.method == "POST":
            form = await request.form()
            action = form.get("action")
            ctx["form"] = dict(form)
            if action == "prompt":
                ctx["prompt"] = ai.build_prompt(str(form.get("topic", "")), str(form.get("level", "beginner")),
                                                int(form.get("weeks") or 4), int(form.get("hours") or 3),
                                                str(form.get("language", "English")), str(form.get("notes", "")))
                ctx["step"] = 2
            elif action in ("check", "save"):
                text = strip_fences(str(form.get("reply", "")))
                ctx["step"] = 3
                ctx["reply"] = form.get("reply", "")
                try:
                    course = load_course({"course.yaml": text})
                except CourseError as e:
                    ctx["problems"] = e.problems
                else:
                    if action == "save":
                        if V.get_course(course.id):
                            course.id = f"{course.id}-{now_utc()[:10]}"
                        V.install_course(course)
                        return go("/courses", ok=f"Saved “{course.title}”. It's ready to start.")
                    ctx["preview"] = course
        return page("ai.html", request, **ctx)

    # ---- learning ----------------------------------------------------------------
    async def course_overview(request: Request):
        j = journey_or_404(request.path_params["jid"])
        if not j:
            return go("/", err="That course wasn't found.")
        return page("course.html", request, j=j, prog=V.progress(j["id"]))

    def _module_state(prog: dict, module_id: str) -> dict | None:
        return next((m for m in prog["modules"] if m["id"] == module_id), None)

    async def lesson(request: Request):
        j = journey_or_404(request.path_params["jid"])
        if not j:
            return go("/", err="That course wasn't found.")
        course = V.get_course(j["course_id"])
        found = course.find_lesson(request.path_params["lid"])
        if not found:
            return go(f"/learn/{j['id']}", err="That lesson wasn't found.")
        module, les = found
        prog = V.progress(j["id"])
        mstate = _module_state(prog, module["id"])
        if mstate["status"] == "locked":
            return go(f"/learn/{j['id']}", err="Finish the module before this one first.")
        V.add_event(j["id"], "lesson_opened", {"lesson": les["id"]})
        idx = [x["id"] for x in module["lessons"]].index(les["id"])
        lstate = mstate["lessons"][idx]
        nxt = module["lessons"][idx + 1]["id"] if idx + 1 < len(module["lessons"]) else None
        prv = module["lessons"][idx - 1]["id"] if idx > 0 else None
        return page("lesson.html", request, j=j, course=course, module=module, mstate=mstate, lesson=les,
                    lstate=lstate, html=md.render(les["content"]), next_id=nxt, prev_id=prv,
                    has_answers=course.has_answers, prog=prog)

    async def lesson_done(request: Request):
        jid, lid = request.path_params["jid"], request.path_params["lid"]
        j = journey_or_404(jid)
        course = V.get_course(j["course_id"]) if j else None
        found = course.find_lesson(lid) if course else None
        if not found:
            return go("/", err="That lesson wasn't found.")
        if not any(e["type"] == "lesson_done" and e["data"]["lesson"] == lid for e in V.events(jid)):
            V.add_event(jid, "lesson_done", {"lesson": lid, "title": found[1]["title"]})
        form = await request.form()
        target = form.get("next")
        return go(f"/learn/{jid}/lesson/{target}" if target else f"/learn/{jid}/lesson/{lid}", ok="Lesson marked as done.")

    async def _req_ctx(request: Request):
        j = journey_or_404(request.path_params["jid"])
        if not j:
            return None, None, None, None
        course = V.get_course(j["course_id"])
        found = course.find_requirement(request.path_params["rid"])
        if not found:
            return j, course, None, None
        return j, course, found[0], found[1]

    async def add_evidence(request: Request):
        j, course, module, req = await _req_ctx(request)
        if not req:
            return go("/", err="That task wasn't found.")
        form = await request.form()
        up = form.get("file")
        back = f"/learn/{j['id']}/lesson/{module['lessons'][-1]['id']}#tasks"
        if not up or not getattr(up, "filename", ""):
            return go(back, err="Choose a file first.")
        data = await up.read()
        if not data:
            return go(back, err="That file is empty.")
        if len(data) > 100 * 1024 * 1024:
            return go(back, err="That file is over 100 MB. Try a smaller file or a screenshot.")
        V.save_evidence(j["id"], req["id"], up.filename, data, task=req["prompt"])
        return go(back, ok=f"Saved “{up.filename}” as your work.")

    async def save_writeup(request: Request):
        j, course, module, req = await _req_ctx(request)
        if not req:
            return go("/", err="That task wasn't found.")
        form = await request.form()
        text = str(form.get("text", "")).strip()
        words = len(text.split())
        back = f"/learn/{j['id']}/lesson/{module['lessons'][-1]['id']}#tasks"
        if not text:
            return go(back, err="Write something first.")
        V.add_event(j["id"], "writeup_saved", {"req": req["id"], "task": req["prompt"], "text": text, "words": words})
        need = req.get("min_words", 40)
        if words < need:
            return go(back, ok=f"Saved. You have {words} words; this needs at least {need} to count.")
        return go(back, ok="Saved your explanation.")

    async def quiz(request: Request):
        j, course, module, req = await _req_ctx(request)
        if not req or req["type"] != "quiz":
            return go("/", err="That quiz wasn't found.")
        if request.method == "GET":
            seed = new_seed()
            try:
                exam = build_exam(course, req["questions"], seed)
            except NoAnswers:
                return go(f"/learn/{j['id']}/lesson/{module['lessons'][-1]['id']}",
                          err="This course came without answers, so practice quizzes aren't available. "
                              "Ask whoever shared it for the version with answers.")
            return page("quiz.html", request, j=j, course=course, module=module, req=req, exam=exam, seed=seed)
        form = await request.form()
        seed = str(form.get("seed", ""))
        exam = build_exam(course, req["questions"], seed)
        picked = {item["id"]: str(form.get(item["id"], "")) for item in exam}
        result = grade(course, exam, picked)
        passed = result["percent"] >= req.get("pass", 70)
        V.add_event(j["id"], "quiz_taken", {"req": req["id"], "task": module["title"], "mode": "practice",
                                            "seed": seed, "answers": picked,
                                            "score": result["score"], "total": result["total"],
                                            "percent": result["percent"], "passed": passed})
        return page("quiz_result.html", request, j=j, module=module, req=req, result=result, passed=passed)

    # ---- milestones -----------------------------------------------------------
    async def milestones(request: Request):
        cards = [journey_card(j) for j in V.journeys()]
        return page("milestones.html", request, cards=cards, checkers=V.my_checkers())

    async def save_milestone(request: Request):
        jid = request.path_params["jid"]
        if not journey_or_404(jid):
            return go("/milestones", err="That course wasn't found.")
        if not has_new(jid):
            return go("/milestones", err="Nothing new to save yet. Finish a lesson or task first.")
        m = V.create_milestone(jid)
        return go("/milestones", ok=f"Milestone {m['seq']} saved. Now send your progress file to your checker.")

    async def export_progress(request: Request):
        jid = request.path_params["jid"]
        j = journey_or_404(jid)
        if not j:
            return go("/milestones", err="That course wasn't found.")
        if not V.milestones(jid):
            return go("/milestones", err="Save a milestone first.")
        data = exchange.make_progress_file(V, jid)
        title = data["journey"]["course"]["title"]
        return download(exchange.dump(data), f"{V.me['name']} - {title} - {now_utc()[:10]}.inpace", "application/json")

    # ---- people ---------------------------------------------------------------
    async def people(request: Request):
        rows = []
        for p in V.people():
            rows.append({**p, "waiting": V.waiting_count(p["id"]) if p["i_check"] else 0,
                         "journeys": V.received(p["id"]) if p["i_check"] else []})
        return page("people.html", request, people=rows)

    async def my_card(request: Request):
        return download(exchange.dump(exchange.make_contact_card(V)), f"{V.me['name']} - contact card.inpace",
                        "application/json")

    async def add_person(request: Request):
        form = await request.form()
        import json as _json
        try:
            card = _json.loads(str(form.get("card", "")))
            exchange.check_contact_card(card)
        except (ValueError, exchange.FileProblem):
            return go("/people", err="That contact card couldn't be read. Ask for a new one.")
        if card["id"] == V.identity.id:
            return go("/people", err="That's your own contact card.")
        rel = form.get("relationship")
        checks_me = rel in ("checks_me", "buddies")
        i_check = rel in ("i_check", "buddies")
        if not (checks_me or i_check):
            return go("/people", err="Choose how you're connected.")
        V.add_person(card["id"], card["name"], card["color"], checks_me, i_check)
        nick = str(form.get("nickname", "")).strip()
        if nick:
            p = V.person(card["id"])
            V.set_roles(card["id"], bool(p["checks_me"]), bool(p["i_check"]), nick)
        nxt = str(form.get("then", ""))
        if nxt.startswith("/review/") or nxt == "/open":
            return go(nxt, ok=f"Added {card['name']}.")
        return go("/people", ok=f"Added {card['name']}.")

    async def edit_person(request: Request):
        pid = request.path_params["pid"]
        form = await request.form()
        if form.get("remove"):
            V.remove_person(pid)
            return go("/people", ok="Removed.")
        V.set_roles(pid, bool(form.get("checks_me")), bool(form.get("i_check")), str(form.get("nickname", "")))
        return go("/people", ok="Saved.")

    # ---- one place to open any file ------------------------------------------
    async def open_file(request: Request):
        if request.method == "GET":
            return page("open.html", request)
        form = await request.form()
        up = form.get("file")
        if not up or not getattr(up, "filename", ""):
            return go("/open", err="Choose a file first.")
        raw = await up.read()
        if raw[:2] == b"PK":  # a course pack (zip)
            try:
                c = V.install_course(load_course(files_from_zip(raw)))
            except CourseError as e:
                return page("open.html", request, problems=e.problems, filename=up.filename)
            extra = "" if c.has_answers else " It came without answers, so practice quizzes are off."
            return go("/courses", ok=f"Added the course “{c.title}”.{extra}")
        if up.filename.lower().endswith((".yaml", ".yml")) or not raw.lstrip()[:1] == b"{":
            # A single-file course (the all-in-one format, e.g. saved from an AI chat).
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                return go("/open", err="This file isn't text inPace can read.")
            try:
                course = load_course({"course.yaml": strip_fences(text)})
            except CourseError as e:
                hint = []
                if any("is missing" in p and "lessons/" in p for p in e.problems):
                    hint = ["This course keeps its lessons in separate files. Put course.yaml and the lessons "
                            "folder together in a zip file, then open the zip."]
                return page("open.html", request, problems=hint + e.problems, filename=up.filename)
            if V.get_course(course.id) and V.journey_for_course(course.id):
                course.id = f"{course.id}-{now_utc()[:10]}"
            c = V.install_course(course)
            extra = "" if c.has_answers else " It has no answers, so practice quizzes are off."
            return go("/courses", ok=f"Added the course “{c.title}”.{extra}")
        try:
            data = exchange.read_inpace_file(raw)
        except exchange.FileProblem as e:
            return go("/open", err=str(e))
        kind = data["inpace"]
        try:
            if kind == "contact":
                exchange.check_contact_card(data)
                if data["id"] == V.identity.id:
                    return go("/open", err="That's your own contact card. Send it to the other person instead.")
                import json as _json
                return page("add_person.html", request, card=data, card_json=_json.dumps(data),
                            existing=V.person(data["id"]), then="/people")
            if kind == "progress":
                learner = data["learner"]["id"]
                if learner == V.identity.id:
                    return go("/open", err="That's your own progress file. Send it to your checker.")
                p = V.person(learner)
                if not p or not p["i_check"]:
                    import json as _json
                    card = {"id": learner, "name": data["learner"]["name"], "color": data["learner"]["color"]}
                    V.store_received(data)
                    return page("add_person.html", request, card=card, card_json=None, from_progress=True,
                                progress_json=_json.dumps(data), existing=p,
                                then=f"/review/{learner}/{data['journey']['id']}")
                V.store_received(data)
                return go(f"/review/{learner}/{data['journey']['id']}")
            if kind == "approval":
                res = exchange.import_approval_file(V, data)
                word = {"approved": "approved", "question": "has a question about", "flag": "flagged"}[res["decision"]]
                note = f" Note: “{res['note']}”" if res["note"] else ""
                return go("/milestones", ok=f"{res['name']} {word} {res['count']} milestone(s).{note}")
        except exchange.FileProblem as e:
            return go("/open", err=str(e))
        except (KeyError, TypeError, ValueError):
            return go("/open", err="This file is damaged or from a newer version of inPace.")
        return go("/open", err="inPace doesn't know this kind of file yet.")

    async def add_person_from_progress(request: Request):
        """Checker adds an unknown learner straight from their progress file."""
        form = await request.form()
        import json as _json
        try:
            data = _json.loads(str(form.get("progress", "")))
            learner = data["learner"]
        except (ValueError, KeyError):
            return go("/open", err="Something went wrong. Open the file again.")
        V.add_person(learner["id"], learner["name"], learner["color"], False, True)
        nick = str(form.get("nickname", "")).strip()
        if nick:
            V.set_roles(learner["id"], False, True, nick)
        return go(f"/review/{learner['id']}/{data['journey']['id']}", ok=f"Added {learner['name']}.")

    # ---- reviewing someone ------------------------------------------------------
    async def review(request: Request):
        lid, jid = request.path_params["learner"], request.path_params["journey"]
        rec = V.received_one(lid, jid)
        person = V.person(lid)
        if not rec or not person:
            return go("/people", err="Open their progress file first.")
        if request.method == "POST":
            form = await request.form()
            decision = str(form.get("decision"))
            if decision not in ("approved", "question", "flag"):
                return go(f"/review/{lid}/{jid}", err="Choose approve, question or flag.")
            report = exchange.review_progress(V, rec["data"])
            if decision == "approved" and not report["history_ok"]:
                return go(f"/review/{lid}/{jid}", err="You can't approve while there's a problem with the history.")
            seqs = [m["body"]["seq"] for m in report["new"]] or [m["body"]["seq"] for m in report["milestones"][-1:]]
            note = str(form.get("note", ""))
            approval = exchange.make_approval_file(V, rec["data"], decision, note, seqs)
            out = V.home / "outbox"
            out.mkdir(exist_ok=True)
            fname = f"For {display_name(person)} - {decision} - {now_utc()[:10]}.inpace"
            fname = re.sub(r"[^\w .,()-]+", "", fname)
            (out / fname).write_bytes(exchange.dump(approval))
            return go(f"/review/{lid}/{jid}?file={quote(fname)}", ok="Done! Now send the reply file back.")
        report = exchange.review_progress(V, rec["data"])
        course = V.get_course(rec["data"]["journey"]["course"]["id"])
        # Resolve lesson and task names from our own copy of the course, if we have it.
        names = {}
        if course:
            for m in course.modules:
                for les in m["lessons"]:
                    names[les["id"]] = les["title"]
                for r in m["requires"]:
                    names[r["id"]] = r["prompt"]
        return page("review.html", request, person=person, rec=rec, report=report, names=names,
                    reply_file=request.query_params.get("file"), receipts=V.receipts(lid, jid))

    async def outbox(request: Request):
        name = Path(request.path_params["name"]).name
        p = V.home / "outbox" / name
        if not p.exists():
            return go("/people", err="That file is gone. Review again to make a new one.")
        return download(p.read_bytes(), name, "application/json")

    async def settings(request: Request):
        if request.method == "POST":
            form = await request.form()
            V.rename(str(form.get("name", "")).strip() or V.me["name"], str(form.get("color", COLORS[0])))
            return go("/settings", ok="Saved.")
        return page("settings.html", request, colors=COLORS, home=str(V.home))

    def needs_setup(handler):
        async def wrapped(request: Request):
            if not V.is_set_up:
                return go("/setup")
            return await handler(request)
        return wrapped

    routes = [
        Route("/setup", setup, methods=["GET", "POST"]),
        Route("/", needs_setup(home)),
        Route("/courses", needs_setup(courses)),
        Route("/courses/sample/{cid}", needs_setup(add_sample), methods=["POST"]),
        Route("/courses/{cid}/start", needs_setup(start_course), methods=["POST"]),
        Route("/courses/{cid}/export", needs_setup(export_course)),
        Route("/courses/{cid}/remove", needs_setup(remove_course), methods=["POST"]),
        Route("/ai", needs_setup(ai_page), methods=["GET", "POST"]),
        Route("/learn/{jid}", needs_setup(course_overview)),
        Route("/learn/{jid}/lesson/{lid}", needs_setup(lesson)),
        Route("/learn/{jid}/lesson/{lid}/done", needs_setup(lesson_done), methods=["POST"]),
        Route("/learn/{jid}/task/{rid}/evidence", needs_setup(add_evidence), methods=["POST"]),
        Route("/learn/{jid}/task/{rid}/writeup", needs_setup(save_writeup), methods=["POST"]),
        Route("/learn/{jid}/task/{rid}/quiz", needs_setup(quiz), methods=["GET", "POST"]),
        Route("/milestones", needs_setup(milestones)),
        Route("/milestones/{jid}/save", needs_setup(save_milestone), methods=["POST"]),
        Route("/milestones/{jid}/export", needs_setup(export_progress)),
        Route("/people", needs_setup(people)),
        Route("/people/card", needs_setup(my_card)),
        Route("/people/add", needs_setup(add_person), methods=["POST"]),
        Route("/people/add-learner", needs_setup(add_person_from_progress), methods=["POST"]),
        Route("/people/{pid}", needs_setup(edit_person), methods=["POST"]),
        Route("/open", needs_setup(open_file), methods=["GET", "POST"]),
        Route("/review/{learner}/{journey}", needs_setup(review), methods=["GET", "POST"]),
        Route("/outbox/{name}", needs_setup(outbox)),
        Route("/settings", needs_setup(settings), methods=["GET", "POST"]),
        Mount("/static", StaticFiles(directory=HERE / "static"), name="static"),
    ]
    return Starlette(routes=routes)
