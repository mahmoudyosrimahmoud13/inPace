"""Make the files of the "Tour of inPace" sample course (inpace/sample_courses/tour/files).

Run once when the sample changes; the files are kept in git. Needs (only for making them, not for inPace):
python-docx, python-pptx, openpyxl, Pillow, LibreOffice (for the PDF with bookmarks) and ffmpeg.

    python packaging/make_tour_course.py
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "inpace" / "sample_courses" / "tour" / "files"
SUN, INK, PINK, PAPER, GREEN = "#FFD43B", "#111111", "#E6007E", "#F7F3EA", "#1F9D6A"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(size: int, bold: bool = True):
    return ImageFont.truetype(FONT if bold else FONT_R, size)


def mark(d: ImageDraw.ImageDraw, x: int, y: int, s: float) -> None:
    """The inPace mark: three stones on a path."""
    d.line([(x + 15 * s, y + 42 * s), (x + 42 * s, y + 16 * s)], fill=INK, width=int(4 * s))
    for cx, cy, r, fill in ((15, 42, 6, INK), (29, 29, 6, INK), (42, 16, 7, PINK)):
        d.ellipse([x + (cx - r) * s, y + (cy - r) * s, x + (cx + r) * s, y + (cy + r) * s], fill=fill, outline=INK, width=int(3 * s))


def cover() -> None:
    im = Image.new("RGB", (1200, 675), SUN)
    d = ImageDraw.Draw(im)
    mark(d, 760, 120, 6.5)
    d.text((80, 230), "A tour of", font=font(64), fill=INK)
    d.text((80, 310), "inPace", font=font(150), fill=INK)
    d.text((84, 500), "Every kind of lesson, in one short course", font=font(34, False), fill=INK)
    im.save(OUT / "cover.jpg", quality=85)


def diagram() -> None:
    im = Image.new("RGB", (1400, 420), PAPER)
    d = ImageDraw.Draw(im)
    steps = [("Learn", "lessons, books, videos"), ("Practise", "tasks and quizzes"),
             ("Save a milestone", "a signed snapshot"), ("Get checked", "a friend approves")]
    w = 300
    for i, (title, sub) in enumerate(steps):
        x = 40 + i * (w + 40)
        d.rectangle([x + 8, 108, x + w + 8, 318], fill=INK)
        d.rectangle([x, 100, x + w, 310], fill=SUN if i % 2 == 0 else "#FFFFFF", outline=INK, width=5)
        d.text((x + 24, 140), f"{i + 1}", font=font(54), fill=PINK)
        d.text((x + 24, 210), title, font=font(30), fill=INK)
        d.text((x + 24, 258), sub, font=font(22, False), fill=INK)
        if i < 3:
            d.polygon([(x + w + 12, 195), (x + w + 32, 205), (x + w + 12, 215)], fill=INK)
    d.text((40, 30), "How inPace keeps you going", font=font(40), fill=INK)
    im.save(OUT / "how-it-works.png", optimize=True)


def video() -> None:
    """Eight seconds: the inPace colors with a counting clock, small enough to ship with the app."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "color=c=0xFFD43B:s=640x360:d=8,format=yuv420p", "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
                    "-vf", (f"drawtext=fontfile={FONT}:text='A tour of inPace':fontsize=46:fontcolor=0x111111:x=(w-tw)/2:y=110,"
                            f"drawtext=fontfile={FONT_R}:text='This is a video lesson. inPace remembers where you stop.':"
                            "fontsize=20:fontcolor=0x111111:x=(w-tw)/2:y=185,"
                            f"drawtext=fontfile={FONT}:text='%{{eif\\:t\\:d}} s':fontsize=40:fontcolor=0xE6007E:x=(w-tw)/2:y=250"),
                    "-af", "volume=0.08", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "48k",
                    "-movflags", "+faststart", "-shortest", str(OUT / "welcome-video.mp4")], check=True)


def audio() -> None:
    """A gentle three-note chime, as an audio lesson."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=f=523:d=1.2[a];sine=f=659:d=1.2[b];sine=f=784:d=2.4[c];[a][b][c]concat=n=3:v=0:a=1,"
                    "afade=t=out:st=3.6:d=1.2,volume=0.35", "-c:a", "libmp3lame", "-b:a", "64k", str(OUT / "chime.mp3")],
                   check=True)


def code() -> None:
    (OUT / "study_timer.py").write_text('''"""A tiny study timer: work for a while, then take a short break."""
import time

WORK_MINUTES = 25
BREAK_MINUTES = 5


def countdown(minutes: int, label: str) -> None:
    print(f"{label}: {minutes} minutes")
    for left in range(minutes, 0, -1):
        print(f"  {left} min left")
        time.sleep(60)


if __name__ == "__main__":
    countdown(WORK_MINUTES, "Study")
    countdown(BREAK_MINUTES, "Break")
    print("Done. Mark the lesson as done in inPace!")
''', encoding="utf-8")


def page() -> None:
    (OUT / "flashcards.html").write_text('''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flashcards</title>
<style>
  body { font: 18px/1.5 system-ui, sans-serif; background: #F7F3EA; color: #111; margin: 0; padding: 24px; }
  .card { max-width: 520px; margin: 0 auto; background: #fff; border: 3px solid #111; box-shadow: 6px 6px 0 #111; padding: 28px;
          min-height: 160px; cursor: pointer; display: grid; place-items: center; text-align: center; }
  .card.back { background: #FFD43B; }
  .row { display: flex; gap: 12px; justify-content: center; margin-top: 22px; }
  button { font: inherit; font-weight: 700; padding: 8px 18px; border: 3px solid #111; background: #fff; cursor: pointer; }
  p { text-align: center; color: #555; }
</style></head>
<body>
<p>A web page can be a lesson too. This one is a set of flashcards: tap the card to turn it over.</p>
<div class="card" id="card" role="button" tabindex="0"></div>
<div class="row"><button id="prev">Back</button><button id="next">Next</button></div>
<p id="count"></p>
<script>
  const cards = [
    ["What is a milestone?", "A signed snapshot of your progress that nobody can quietly change."],
    ["Who approves a milestone?", "Your checker: a friend, parent or mentor you choose."],
    ["Where is your data kept?", "On your own device, in one folder. No account, no cloud."],
    ["What does a lesson with #pages=10-14 show?", "Only those pages of the book."],
  ];
  let i = 0, back = false;
  const card = document.getElementById("card"), count = document.getElementById("count");
  const show = () => { card.textContent = cards[i][back ? 1 : 0]; card.classList.toggle("back", back); count.textContent = `${i + 1} / ${cards.length}`; };
  card.onclick = () => { back = !back; show(); };
  card.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); card.onclick(); } };
  document.getElementById("next").onclick = () => { i = (i + 1) % cards.length; back = false; show(); };
  document.getElementById("prev").onclick = () => { i = (i + cards.length - 1) % cards.length; back = false; show(); };
  show();
</script>
</body></html>
''', encoding="utf-8")


BOOK = [
    ("Chapter 1: Learning a little every day", [
        ("1.1 Why small steps work", [
            "Big goals are easy to start and hard to keep. A small step you can take every day is the opposite: it is "
            "easy to keep, and it adds up. Ten minutes a day is more than an hour a week, and it never feels heavy.",
            "When a step is small, missing a day doesn't break you. You just take the next step tomorrow.",
            "Try it: pick one lesson for today, set a timer for ten minutes, and stop when it rings. Tomorrow, do it again.",
        ]),
        ("1.2 Pick a time, not a mood", [
            "Waiting until you feel like studying means waiting a long time. Instead, pick a time, like after dinner, "
            "and let a reminder do the remembering for you.",
            "In inPace, open Reminders and choose the time and the days. An alarm keeps ringing until you stop it.",
            "Good times are the ones that already exist in your day: right after dinner, on the bus, or before you open your phone in the morning.",
        ]),
    ]),
    ("Chapter 2: Practice that sticks", [
        ("2.1 Explain it in your own words", [
            "If you can explain an idea simply, you understand it. If you can't, you have found exactly what to review.",
            "That's why many inPace modules ask you to write a short explanation before you move on.",
            "Write as if you were telling a friend. Short sentences, one idea at a time, and an example from your own life.",
        ]),
        ("2.2 Come back to old questions", [
            "Memory fades fast at first and slower later. Seeing a question again after one day, then three days, then a "
            "week, keeps it for good. inPace's daily review does this for you.",
            "A review takes a few minutes. Answer what you can, and the questions you miss come back sooner.",
        ]),
    ]),
    ("Chapter 3: Someone in your corner", [
        ("3.1 Why a checker helps", [
            "We keep promises to other people better than promises to ourselves. A checker is someone you trust who "
            "looks at your milestones and says: well done.",
            "Your checker doesn't need to know the subject. They see what you did, when you did it, and your own words about it.",
        ]),
        ("3.2 Proof you can trust", [
            "Each milestone is signed and linked to the one before it, so your history can't be quietly changed. Your "
            "checker's inPace checks every signature before they approve.",
            "So when your checker approves a milestone, you both know it's real. That's a record you can be proud of.",
        ]),
    ]),
]


def book() -> None:
    """A small book with chapter and section bookmarks, made with LibreOffice so the PDF has a real outline."""
    from docx import Document
    from docx.enum.text import WD_BREAK
    from docx.shared import Pt
    doc = Document()
    doc.styles["Normal"].font.size = Pt(19)
    for name, size in (("Title", 40), ("Heading 1", 30), ("Heading 2", 25)):
        doc.styles[name].font.size = Pt(size)
    doc.add_heading("Small Steps", 0)
    doc.add_paragraph("A short sample book for the inPace tour. Each chapter is a part of the course, and each "
                      "section is a lesson that shows only its own pages.")
    doc.add_paragraph("Written for inPace. Free to use and share.")
    for ch_title, sections in BOOK:
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        doc.add_heading(ch_title, 1)
        doc.add_paragraph("This chapter has two short sections.")
        for s_title, paras in sections:
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            doc.add_heading(s_title, 2)
            for p in paras:
                doc.add_paragraph(p)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "small-steps.docx"
        doc.save(src)
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf:writer_pdf_Export:{\"ExportBookmarks\":{\"type\":\"boolean\",\"value\":\"true\"}}",
                        "--outdir", tmp, str(src)], check=True, capture_output=True)
        shutil.copy2(Path(tmp) / "small-steps.pdf", OUT / "small-steps.pdf")


def word() -> None:
    from docx import Document
    from docx.shared import Inches
    doc = Document()
    doc.add_heading("My study notes", 0)
    doc.add_paragraph("This is a Word document shown inside a lesson. inPace shows the headings, lists, tables and "
                      "pictures. To edit it, download it and open it in Word, LibreOffice or Google Docs.")
    doc.add_heading("What I want to learn this month", 1)
    for item in ("Finish the Python Basics course", "Read one chapter of a book every week", "Save a milestone every Friday"):
        doc.add_paragraph(item, style="List Bullet")
    doc.add_heading("My week", 1)
    t = doc.add_table(rows=1, cols=3)
    t.style = "Table Grid"
    for c, text in zip(t.rows[0].cells, ("Day", "What", "Minutes")):
        c.text = text
    for row in (("Monday", "Lesson 1", "20"), ("Wednesday", "Lesson 2", "25"), ("Friday", "Review and milestone", "15")):
        cells = t.add_row().cells
        for c, text in zip(cells, row):
            c.text = text
    doc.add_heading("How it fits together", 1)
    doc.add_picture(str(OUT / "how-it-works.png"), width=Inches(6))
    p = doc.add_paragraph()
    p.add_run("Tip: ").bold = True
    p.add_run("keep notes short. One idea per line is easier to review later.").italic = True
    doc.save(OUT / "study-notes.docx")


def slides() -> None:
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text = "Meet inPace"
    s.placeholders[1].text = "Slides open right inside a lesson"
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "What you can add to a course"
    tf = s.placeholders[1].text_frame
    tf.text = "Videos, audio and YouTube links"
    for text, lvl in (("PDFs, and parts of a book", 0), ("Word, PowerPoint and Excel files", 0), ("Only to view: edit them in Office", 1),
                      ("Web pages, pictures and code", 0)):
        p = tf.add_paragraph()
        p.text, p.level = text, lvl
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "The inPace loop"
    s.shapes.add_picture(str(OUT / "how-it-works.png"), Inches(0.5), Inches(2.2), width=Inches(9))
    prs.save(OUT / "meet-inpace.pptx")


def sheet() -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Study plan"
    rows = [("Week", "Topic", "Lessons", "Minutes", "Done"),
            (1, "Start here", 2, 30, "Yes"), (2, "Watch and listen", 3, 25, "Yes"), (3, "Read a book", 3, 40, "No"),
            (4, "Office files", 3, 30, "No"), (5, "Try it yourself", 2, 35, "No"), ("", "Total", 13, 160, "")]
    for r in rows:
        ws.append(r)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="FFD43B")
    ws2 = wb.create_sheet("Reading log")
    for r in (("Date", "Book", "Pages"), ("Monday", "Small Steps", "1-4"), ("Thursday", "Small Steps", "5-8")):
        ws2.append(r)
    wb.save(OUT / "study-plan.xlsx")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cover()
    diagram()
    video()
    audio()
    code()
    page()
    book()
    word()
    slides()
    sheet()
    total = sum(p.stat().st_size for p in OUT.iterdir())
    for p in sorted(OUT.iterdir()):
        print(f"{p.stat().st_size // 1024:6d} KB  {p.name}")
    print(f"{total // 1024:6d} KB  in all")


if __name__ == "__main__":
    main()
