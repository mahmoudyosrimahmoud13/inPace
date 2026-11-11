# inPace format spec (v1)

This document describes the files inPace reads and writes, so other apps can be compatible.

## 1. Canonical form and fingerprints

Before anything is fingerprinted or signed, it is turned into bytes like this:

- JSON, keys sorted, no spaces (`separators=(",", ":")`), UTF-8, non-ASCII kept as is.
- Text: line endings changed to `\n`, then Unicode NFC normalization.
- No floating point numbers. Use integers.

A **fingerprint** is the lowercase hex SHA-256 of those bytes.

Test vector:

```text
data:        {"hello": "world", "n": 1, "text": "سلام\r\nline"}
canonical:   {"hello":"world","n":1,"text":"سلام\nline"}
fingerprint: 264cd6a7c837006cdde548835d210b64cd64d1837e2400a46a3d6ba01cb95a47
```

## 2. People and signatures

Each person has an Ed25519 key pair. Their **id** is the hex public key (64 characters).
A signature is Ed25519 over the canonical bytes of the signed object, written as hex.

**Contact card** (`"inpace": "contact"`): `id`, `name`, `color`, `created_at`, and `sig`, which signs
`{inpace, id, name, color, created_at}` with the card owner's own key.

## 3. Milestones

```json
{
  "kind": "milestone", "v": 1,
  "learner": "<id>", "journey": "<journey id>", "journey_started": "<UTC time>",
  "seq": 1, "prev": "<fingerprint of milestone seq-1, or empty string>",
  "course": {"id": "...", "title": "...", "version": "...", "hash": "<course fingerprint>"},
  "events": [{"seq": 4, "type": "lesson_done", "data": {...}, "at": "2026-11-11T14:00:00Z"}],
  "last_event": 9,
  "summary": {"percent": 50, "lessons_done": 2, "lessons_total": 4, "modules_done": 1, "modules_total": 2, "minutes": 35},
  "created_at": "2026-11-11T14:05:00Z"
}
```

- `hash` = fingerprint of the body above.
- `sig` = learner's signature over `{"kind": "milestone", "hash": hash}`.
- A chain is valid when `seq` counts 1, 2, 3..., every `hash` matches, every `prev` equals the previous `hash`,
  and every `sig` verifies with the learner's id.

Event types: `journey_started`, `lesson_opened`, `lesson_done`, `evidence_added` (file name + SHA-256 only),
`writeup_saved` (full text), `quiz_taken` (seed, chosen option ids, score).

## 4. Progress file (learner to checker)

`"inpace": "progress"`, with `learner` `{id, name, color}`, `journey` `{id, started_at, course}`, and the
full list of `milestones` `[{body, hash, sig}]`.

**Receipts.** A checker stores `(learner, journey, seq, hash)` for every milestone they reviewed.
On every new file, each receipt must still match. This catches a learner who rewrites history and
re-signs it with their own key, which a chain check alone cannot detect.

## 5. Approval file (checker to learner)

`"inpace": "approval"`, with `checker` `{id, name, color}`, `learner`, `journey`, and `decisions`.
Each decision has `kind: "decision"`, `milestone` (hash), `journey`, `learner`, `checker`,
`decision` (`approved` | `question` | `flag`), `note`, `at`, and `sig` over those fields.
The learner only accepts decisions from people they marked as "checks my progress".

## 6. Course packs

A `.lpack` is a zip with `course.yaml`, `lessons/*.md`, `questions.yaml` and (optionally) `answers.yaml`.

```yaml
# course.yaml
id: python-basics
title: Python Basics
version: 1
language: en
modules:
  - id: m1
    title: Your first Python
    lessons:
      - {id: m1-l1, title: What is Python?, file: lessons/m1-l1.md, minutes: 10}
    requires:
      - {id: m1-practical, type: practical, prompt: "Make ..."}
      - {id: m1-explain, type: explain, prompt: "Explain ...", min_words: 30}
      - {id: m1-quiz, type: quiz, questions: [q1, q2], pass: 70}
```

```yaml
# questions.yaml: no hint about which options are right
q1:
  text: What does print("Hi") do?
  show: 4
  options: {a: Shows Hi on the screen, b: Displays the text Hi, c: Sends Hi to a printer, d: Saves Hi in a file, e: ...}
```

```yaml
# answers.yaml
q1: {right: [a, b], why: print() displays text on the screen.}
```

**All-in-one format** (what AI chats produce): one `course.yaml` with `content:` instead of `file:` for each
lesson, and questions written as `right: [...]` and `wrong: [...]` lists. inPace converts it to the split
format, giving options neutral ids from `"o" + sha256(qid + "\x1f" + text)[:6]`.

**Course fingerprint** = fingerprint of `{id, title, version, description, language, modules, questions}`
with lesson text inlined. Answers are not included, so a copy with or without answers has the same fingerprint.

## 7. Building an exam from a seed

`rank(parts...) = sha256(join(parts, "\x1f"))` as hex. For a seed `s`:

1. Question order: sort question ids by `rank(s, "order", qid)`.
2. Right answer shown: the right option with the smallest `rank(s, qid, "right", option_id)`.
3. Wrong answers shown: the `show - 1` wrong options with the smallest `rank(s, qid, "wrong", option_id)`.
4. Display order: sort the chosen options by `rank(s, qid, "show", option_id)`.

The same seed always gives the same exam, so anyone with the course can rebuild what the learner saw.

## 8. Verified exams (`"inpace": "exam"`)

Made by the checker: `id`, `checker` `{id, name, color}`, `learner`, `journey`, `course` `{id, title, hash}`,
`req`, `task`, `pass`, `questions` `[{id, text, choices: [{id, text}], note?}]`, `created_at`, and `sig`
(checker's signature over everything except `sig`). It never contains answers; the checker's app keeps the key.

The learner answers once. That records an `exam_taken` event `{exam, req, task, checker, answers}`, which travels
inside the next milestone. The checker's app grades it with the stored key.

## 9. Extras in an approval file

An approval file may carry `extras`: `{kind: "extras", learner, journey, checker, exam_results: [{exam, score,
total, percent, passed}], requests: [{sha256, name}], at, sig}`, signed by the checker.

## 10. File packs

A zip with `inpace-files.json` (`"inpace": "files"`, `learner`, `journey`, `files: [{sha256, name}]`, `sig` by
the learner) and each file at `files/<sha256>`. The checker accepts a file only if its SHA-256 matches and the
same fingerprint appears in an `evidence_added` event of that learner's milestones.
