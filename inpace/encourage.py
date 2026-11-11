"""What Tempo says. Short, warm, specific to where the learner is.

Every line is plain English with %s slots, so it can be translated (see locales/ar.json).
"""
from __future__ import annotations

from datetime import datetime, timezone


def _hour() -> int:
    return datetime.now().hour


def greeting(card: dict) -> tuple[str, str, list]:
    """(mood, message, values) for one course on the Home page."""
    p = card["progress"]
    pace = card.get("pace") or {}
    module = p.get("current_module")
    if card.get("chain_problems"):
        return "oops", "Something looks off with your record. Check your Milestones page.", []
    if card.get("paused"):
        return "sleepy", "Enjoy your break. I'll keep your place warm. Come back when you're ready.", []
    if p.get("finished"):
        return "proud", "You finished the whole course. That's a real achievement. I'm proud of you!", []
    if card.get("last_ok") and not card.get("has_new") and card["last_ok"]["at"][:10] == datetime.now(timezone.utc).date().isoformat():
        return "cheer", "%s approved your milestone today. Nice work!", [card["last_ok"]["checker_name"]]
    if pace.get("streak", 0) >= 2:
        return "cheer", "%s weeks on pace in a row. Keep the streak going!", [pace["streak"]]
    if p["percent"] == 0:
        return "wave", "Hi! I'm Tempo. Slow and steady wins the race. Let's start with your first lesson.", []
    if module:
        left = sum(1 for les in module["lessons"] if not les["done"])
        tasks = sum(1 for r in module["requires"] if not r["done"])
        if left == 1:
            return "cheer", "Just one lesson left in this module. You're so close!", []
        if left == 0 and tasks:
            return "happy", "All lessons read! %s tasks left to finish this module.", [tasks]
    if card.get("due"):
        return "think", "%s questions are ready for a quick review. It only takes a few minutes.", [card["due"]]
    if p["percent"] >= 75:
        return "cheer", "%s%% done. The finish line is in sight!", [p["percent"]]
    if p["percent"] >= 50:
        return "happy", "Halfway there and still going. That's how it's done.", []
    h = _hour()
    if h < 12:
        return "happy", "Good morning! A little learning now makes the whole day better.", []
    if h >= 21:
        return "sleepy", "Studying late? One short lesson, then rest. Steady beats fast.", []
    return "happy", "Welcome back! Every lesson moves you forward.", []


def empty(kind: str) -> tuple[str, str]:
    return {
        "home": ("wave", "Hi! I'm Tempo. Pick a course and we'll go one step at a time."),
        "races": ("think", "No races yet. Learning is more fun with friends!"),
        "people": ("think", "Learning is easier when someone has your back. Add a checker."),
        "milestones": ("think", "Start a course, then your milestones show up here."),
    }[kind]


CELEBRATE = {
    "lesson": ("happy", "Lesson done! One more step forward."),
    "module": ("cheer", "Module complete! Save a milestone so your checker can see it."),
    "milestone": ("proud", "Milestone saved! Now send your progress file to your checker."),
    "approved": ("cheer", "Your checker approved your work. Well done!"),
    "quiz": ("cheer", "You passed the quiz!"),
    "exam": ("proud", "Exam done! Your answers go with your next milestone."),
    "goal": ("happy", "Goal set. I'll help you keep it."),
    "back": ("wave", "Welcome back! Let's keep going."),
}
