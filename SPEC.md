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

**Media in lessons.** A lesson can have one main `media:` item shown at the top (`video:`, `audio:` and
`url:` mean the same), and its text can embed more, written like a Markdown picture:

```yaml
lessons:
  - {title: Welcome, media: "01 Intro/01 - Welcome.mp4"}        # a file next to the course
  - {title: Talk, media: "https://www.youtube.com/watch?v=..."} # YouTube or Vimeo: loads only on play
  - {title: Lab, media: "/home/sara/Videos/lab.mp4"}            # a full path also works
```

```markdown
![Pendulum](sims/pendulum.html)   <- a web page, run in a sealed box (no internet, no access to inPace)
![](<media/my clip.mp4>)          <- use <...> when the path has spaces
https://youtu.be/...              <- a YouTube or Vimeo link alone on a line becomes a player
```

Kinds: video (`.mp4 .webm .m4v .mov .ogv .mkv`), audio (`.mp3 .m4a .aac .ogg .oga .opus .wav .flac .weba`),
web page (`.html .htm`), picture, PDF, office (`.docx .pptx .xlsx .xlsm`: a read-only preview plus a download
button), code (`.py .js .ts .java .go .sql .yaml .json .ipynb Dockerfile` and more, shown with colours), a project
folder (a path ending in `/`: all its code files), YouTube, Vimeo, and any other link.

**Part of a PDF.** A PDF path may end in `#pages=A-B` (or `#pages=A` for one page), both 1-based and inclusive:
`media: "book.pdf#pages=12-19"`. The reader shows only those pages and keeps a separate reading position for each
range. The range is not part of the file's path: lookups, `media_index`, copying and packs use the plain file.

```yaml
book: small-steps.pdf          # optional: the course was made from this book
modules:
  - id: m1
    title: "Chapter 1: Learning a little every day"
    lessons:
      - {title: Introduction, media: "small-steps.pdf#pages=2-2"}
      - {title: 1.1 Why small steps work, media: "small-steps.pdf#pages=3-3"}
```

`book: <path>` (optional) names the PDF a course was made from. It is not part of the fingerprint, and a shared
pack leaves the book's file out (books are often large and not yours to share): the learner points inPace to
their own copy.

**Files stay where they are.** inPace never copies a course's files unless asked. Paths are looked up, in order:
the file itself (full paths), the course's own small files (`<home>/media/<course>/`, added in the editor or
carried inside a pack), then the folder this computer was pointed to for that course. Each folder is searched
for the whole path and then for shorter and shorter endings of it, so a moved or renamed folder still works.
When files are missing, inPace asks for the folder where they are now. `media_index: {path: size}` in
`course.yaml` lists the course's files (made automatically when a folder becomes a course).

**Lesson text** is CommonMark Markdown with tables. Raw HTML is not allowed. Code blocks are coloured on the
device. Two additions:
- **Diagrams:** a code block marked `mermaid` is drawn as a diagram (flowcharts, sequence diagrams, timelines,
  mind maps and the rest of Mermaid 10). The drawing code is bundled, so it works offline. A diagram with a
  mistake shows its text and a short note instead.

  ````markdown
  ```mermaid
  flowchart LR
      A[Lessons] --> B[Module done] --> C[Save a milestone]
  ```
  ````
- **Right to left:** each paragraph, heading, list item, quote and table cell gets its own direction from the
  words it mostly uses (code and links don't count), so Arabic and English can be mixed freely in one lesson.
  Code is always left to right.

**Course picture.** `image: <path>` in `course.yaml` (optional) is a picture file next to the course (jpg, png, webp, gif), found like any other course file. It is not part of the fingerprint. A shared pack includes it under `files/`.

**Pack with files:** an optional `files/` folder inside the `.lpack` carries the course's files
(`files/<path inside the course>`), extracted to `<home>/media/<course>/` on install.

**Course fingerprint** = fingerprint of `{id, title, version, description, language, modules, questions}`
with lesson text inlined. Answers are not included, so a copy with or without answers has the same fingerprint.

**Course updates.** A course is matched by its `id`. When a course arrives whose `id` is already installed but
whose content fingerprint differs, the app keeps it in `<home>/pending/<id>/` (`course/` plus any `files/`) and lets
the learner choose: *update* (replace the course; the version before goes to `<home>/course_history/<id>/` for Undo;
progress is kept because events refer to lesson and task ids), *separate* (install under a new id `<id>-2`, `-3`, …)
or *keep* (throw the pending copy away). A course made from a folder can be refreshed: lessons whose `media` is not
yet in the course are added, and existing modules, lessons, tasks and ids are never changed.

**Deleting a course.** The course folder and `<home>/media/<id>/` are removed. Journeys of that course are marked
archived rather than erased, because milestones are append-only and a checker may already hold them. The linked
folder on the computer is never touched.

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

## 11. Links

Any inPace file small enough can travel as a link instead: `https://mahmoudyosrimahmoud13.github.io/inPace/open#BODY`
or `inpace://open/BODY`, where `BODY` is the file's JSON (compact, UTF-8), compressed with zlib and written in
URL-safe base64 without padding. The older `inpace:BODY` code form is still read. Apps read the first such
link or code found anywhere in a pasted message. Links are offered up to 3,500 characters; bigger files are sent
as files.

**Progress updates.** A progress file may carry `since: N` and only the milestones after N (and no `outline`).
The learner picks N as the highest milestone every one of their checkers has replied about. The checker's app
puts its stored milestones 1..N in front, keeps its stored `outline`, and then checks the whole chain as in §4.
If it has fewer than N stored milestones it refuses and asks for the full file.

## 12. Course library

**Download links.** `downloads: [{title, url, size}]` in `course.yaml` (optional, up to 10, http/https only) says
where to download course files that aren't inside the course file.

**Signed submissions.** A library submission is a course `.zip` with answers, small files under `files/`, and
`inpace-author.json`: `{kind: "library-course", course, version, hash, author, name, at, sig}`, where `hash` is the
course fingerprint (§1) of the course as read back from the zip, `author` is the author's public key and `sig` signs
everything else. The library accepts a course id only from the key that first published it.

**library.json.** `{inpace: "library", v: 1, updated, courses: [{id, title, description, language, version, hash,
modules, lessons, minutes, tags, license, author: {name, id, verified}, downloads, cover, pack, sha256, size,
updated, link}]}`. Apps download `pack` only from the library's own site and install it only if its SHA-256 matches.

**Course links.** `{inpace: "library-course", id, title, author}` sent as a link (§11) opens that course in the
Course library.
