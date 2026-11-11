"""Make a course with any AI chat: we build the prompt, the user pastes the answer back."""
from __future__ import annotations

LEVELS = {"beginner": "a complete beginner", "some": "someone with some basics", "advanced": "an advanced learner"}

TEMPLATE = """You are helping me create a self-study course for the inPace app.

Topic: {topic}
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
- Output only the YAML code block.
"""


def build_prompt(topic: str, level: str, weeks: int, hours: int, language: str, notes: str = "") -> str:
    weeks = max(1, min(int(weeks or 4), 52))
    modules = max(2, min(weeks, 12))
    lang_code = "ar" if language.lower().startswith(("ar", "عرب")) else "en"
    return TEMPLATE.format(
        topic=topic.strip() or "a topic",
        level_text=LEVELS.get(level, LEVELS["beginner"]),
        weeks=weeks,
        hours=max(1, min(int(hours or 3), 40)),
        language=language or "English",
        lang_code=lang_code,
        modules=modules,
        notes_line=f"Extra wishes: {notes.strip()}\n" if notes.strip() else "",
    )
