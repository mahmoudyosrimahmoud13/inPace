"""Exams: one right answer mixed with wrong ones, in a random but repeatable order.

The order comes only from the exam's seed, using SHA-256, so any app that
follows SPEC.md rebuilds the exact same exam from the same seed.
"""
from __future__ import annotations

import secrets

from .canon import sha256_hex
from .course import Course


class NoAnswers(Exception):
    pass


def _rank(*parts: str) -> str:
    return sha256_hex("\x1f".join(parts).encode("utf-8"))


def new_seed() -> str:
    return secrets.token_hex(8)


def build_exam(course: Course, question_ids: list[str], seed: str) -> list[dict]:
    if not course.answers:
        raise NoAnswers()
    exam = []
    for qid in sorted(question_ids, key=lambda q: _rank(seed, "order", q)):
        q = course.questions[qid]
        right = course.answers[qid]["right"]
        wrong = [o for o in q["options"] if o not in right]
        pick_right = sorted(right, key=lambda o: _rank(seed, qid, "right", o))[0]
        pick_wrong = sorted(wrong, key=lambda o: _rank(seed, qid, "wrong", o))[: q["show"] - 1]
        shown = sorted([pick_right, *pick_wrong], key=lambda o: _rank(seed, qid, "show", o))
        exam.append({"id": qid, "text": q["text"], "choices": [{"id": o, "text": q["options"][o]} for o in shown]})
    return exam


def grade(course: Course, exam: list[dict], picked: dict[str, str]) -> dict:
    if not course.answers:
        raise NoAnswers()
    details, score = [], 0
    for item in exam:
        qid = item["id"]
        right = set(course.answers[qid]["right"])
        shown_right = next(c for c in item["choices"] if c["id"] in right)
        chosen = picked.get(qid)
        ok = chosen in right
        score += ok
        details.append({
            "text": item["text"],
            "chosen": next((c["text"] for c in item["choices"] if c["id"] == chosen), "No answer"),
            "right": shown_right["text"],
            "ok": ok,
            "why": course.answers[qid].get("why", ""),
        })
    total = len(exam)
    return {"score": score, "total": total, "percent": round(100 * score / total) if total else 0, "details": details}
