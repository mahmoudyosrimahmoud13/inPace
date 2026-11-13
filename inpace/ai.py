"""Make a course with any AI chat: we build the prompt, the user pastes the answer back."""
from __future__ import annotations

LEVELS = {"beginner": "a complete beginner", "some": "someone with some basics", "advanced": "an advanced learner"}

TEMPLATE = """You are helping me create a self-study course for the inPace app.

{source_block}
Level: {level_text}
Length: about {weeks} weeks, {hours} hours per week
Course language: {language}
{notes_line}
Write the whole course as ONE YAML document inside a single ```yaml code block, and nothing else.
Use exactly this structure:

```yaml
title: "Course title"
description: "One or two sentences about the course"
version: 1
language: {lang_code}
modules:
  - title: "Module title"
    lessons:
      - title: "Lesson title"
        minutes: 20
        content: |
          ## A heading
          The full lesson text in Markdown. Explain clearly, with examples.
    requires:
      - type: practical
        prompt: "Something to make or do, that leaves a file as proof (a notebook, a photo, a document)"
      - type: explain
        prompt: "A question the learner answers in their own words"
      - type: quiz
        questions: [q1, q2, q3]
        pass: 70
questions:
  q1:
    text: "The question"
    right: ["A correct answer", "Another correct answer, worded differently"]
    wrong: ["A believable wrong answer", "Another wrong answer", "Another", "Another"]
    why: "One sentence explaining the right answer"
    show: 4
```

Rules:
- Make {modules} modules. Each module has 2 to 4 lessons with real, complete teaching text (not outlines).
- Every module ends with a practical task, an explain question, and a quiz of 3 to 5 questions.
- Every question has at least 2 right answers and at least 4 wrong answers. Wrong answers must be believable.
  The app shows one right answer mixed with wrong ones, in random order.
- Question ids are unique across the course (q1, q2, q3, ...).
- Use plain, friendly language for {level_text}.
- When a picture of the idea helps (steps, a flow, how parts connect, a timeline), add a diagram as a
  ```mermaid code block inside the lesson text, for example a flowchart. Keep diagrams small and simple.
{source_rules}- Output only the YAML code block.
"""

SOURCES = ("topic", "book", "playlist", "course", "project", "material", "exam")


def _source(kind: str, f: dict) -> tuple[str, str, str]:
    """(what the course is about, extra rules, a short topic name) for each way to start a course."""
    g = lambda k: str(f.get(k) or "").strip()  # noqa: E731
    if kind == "book":
        book = g("book_title") or "the book"
        by = f" by {g('book_author')}" if g("book_author") else ""
        part = f"\nOnly these parts of the book: {g('chapters')}" if g("chapters") else ""
        block = f"Base the course on the book \"{book}\"{by}.{part}"
        rules = (
            "- Follow the book's own order. Each module covers one chapter or a few chapters; say which in the module title,\n"
            "  for example \"Chapters 1-2: Getting started\".\n"
            "- Start every lesson with a line like \"Read: Chapter 3, pages about X\" so the learner reads the book alongside.\n"
            "- Explain the book's ideas in your own words with new examples. Never copy sentences or long passages from the book.\n"
            "- Base quizzes and tasks on the book's key ideas, so someone who read the chapter can answer them.\n"
            "- If you don't know this book well, say so in the description and keep to what is widely known about it.\n")
        return block, rules, f"{book}{by}"
    if kind == "playlist":
        name = g("playlist") or "my playlist"
        videos = g("videos")[:8000]
        listed = (f"\nThe videos, in order (title | link):\n<<<\n{videos}\n>>>" if videos else "")
        block = f"Base the course on the YouTube playlist \"{name}\".{listed}"
        rules = ("- Each video becomes one lesson, in the same order. Put its link in the lesson as `media: <link>` exactly as given,\n"
                 "  and use the video's title as the lesson title.\n"
                 "- In each lesson's content, write what to watch for, the key ideas in your own words, and a short summary.\n"
                 "- Group the videos into modules of 3 to 6 lessons that belong together, with a clear module title.\n"
                 "- NEVER invent video links. If I didn't list the videos, write normal lessons by topic and leave `media` out.\n")
        return block, rules, name
    if kind == "course":
        name = g("course_name") or "the course"
        where = f" on {g('platform')}" if g("platform") else ""
        outline = f"\nIts sections, in order:\n<<<\n{g('course_outline')[:8000]}\n>>>" if g("course_outline") else ""
        block = f"Make a companion course for an online course I'm taking: \"{name}\"{where}.{outline}"
        rules = ("- Follow that course's order: one module per section (or a few small sections), named like the section.\n"
                 "- Start every lesson with a line like \"Watch: Section 2, the videos about X\".\n"
                 "- Lessons are short study notes in your own words: key ideas, common mistakes, and a worked example.\n"
                 "- Tasks are hands-on practice that proves I can do what the section teaches, not just watch it.\n"
                 "- Don't copy text from the course.\n")
        return block, rules, name
    if kind == "project":
        goal = g("project") or "a project"
        block = f"Teach me by building this project, step by step: {goal}"
        rules = ("- Every module adds one working piece to the project, so at the end the whole project works.\n"
                 "- Each module's practical task is that piece, with a clear \"done when\" check, and a file or screenshot as proof.\n"
                 "- Teach only the theory each step needs, right when it's needed.\n")
        return block, rules, goal
    if kind == "material":
        text = g("material")[:12000]
        block = ("Base the course on my own material below (notes, a syllabus, or a table of contents):\n"
                 f"<<<\n{text}\n>>>")
        rules = ("- Keep the order and the topics of my material. Fill in the teaching text where my material is only an outline.\n"
                 "- Don't add topics my material doesn't mention, unless they are needed to understand it.\n")
        return block, rules, g("topic") or "my material"
    if kind == "exam":
        exam = g("exam") or "the exam"
        block = f"Prepare me for this exam or certificate: {exam}"
        rules = ("- Cover the exam's official topics, in a sensible order, and say in the description which topics are covered.\n"
                 "- Write quiz questions in the style of the real exam, with believable wrong answers.\n"
                 "- End the course with a final module of mixed revision and practice questions.\n")
        return block, rules, exam
    topic = g("topic") or "a topic"
    return f"Topic: {topic}", "", topic


def sources_text(sources: list[dict]) -> tuple[str, str]:
    """The learner's own files attached to the course: what the AI is told about them, and how to use them."""
    if not sources:
        return "", ""
    lines = ["\nMy own files are attached to this course. Lessons can show them right inside inPace:"]
    for s in sources:
        if s.get("toc") is not None:
            lines.append(f'- "{s["file"]}": a PDF book of {s["pages"]} pages.' +
                         (" Its chapters and sections, with their pages:" if s["toc"] else " It has no chapter list."))
            for level, title, a, b in s["toc"]:
                lines.append(f'{"  " * (level + 1)}- {title} (pages {a}-{b})')
        else:
            kinds = {"video": "a video", "audio": "audio", "pdf": "a PDF", "office": "a Word, PowerPoint or Excel file",
                     "html": "a web page", "image": "a picture", "code": "code", "folder": "a folder of code", "note": "notes"}
            lines.append(f'- "{s["file"]}" ({kinds.get(s["kind"], "a file")})')
    rules = (
        "- Use my attached files. Each lesson that teaches part of a PDF book gets a line `media: \"<file>#pages=A-B\"`\n"
        "  (for example `media: \"book.pdf#pages=19-35\"`), with the pages that lesson covers, taken from the page numbers\n"
        "  above. inPace then shows only those pages above the lesson text, and remembers where the learner stopped.\n"
        "  Never use pages beyond the book's last page. If a book has no chapter list, split its pages in order.\n"
        "- A lesson about one of my other files gets `media: \"<file name>\"`, written exactly as listed above.\n"
        "- Put `media:` right under the lesson's title. The lesson text then explains, summarises and adds examples:\n"
        "  don't tell the learner to go and open the file, it's already on screen.\n"
        "- Explain in your own words. Never copy sentences or long passages from my files.\n")
    return "\n".join(lines) + "\n", rules


def build_prompt(topic: str, level: str, weeks: int, hours: int, language: str, notes: str = "",
                 source: str = "topic", sources: list[dict] | None = None, **fields) -> str:
    """The prompt to paste into an AI chat. source: topic, book, material (my notes) or exam.
    sources: the learner's own files attached to the course (see sources_text)."""
    weeks = max(1, min(int(weeks or 4), 52))
    modules = max(2, min(weeks, 12))
    lang_code = "ar" if language.lower().startswith(("ar", "عرب")) else "en"
    block, rules, _ = _source(source if source in SOURCES else "topic", {"topic": topic, **fields})
    files_block, files_rules = sources_text(sources or [])
    if files_block and source == "book":
        # The book itself is attached: its pages are shown, so no "Read: Chapter 3" lines are needed.
        rules = "\n".join(r for r in rules.split("\n") if "Start every lesson with a line like" not in r)
    block += files_block
    rules += files_rules
    return TEMPLATE.format(
        source_block=block,
        source_rules=rules,
        level_text=LEVELS.get(level, LEVELS["beginner"]),
        weeks=weeks,
        hours=max(1, min(int(hours or 3), 40)),
        language=language or "English",
        lang_code=lang_code,
        modules=modules,
        notes_line=f"Extra wishes: {notes.strip()}\n" if notes.strip() else "",
    )
