"""Check that every course in community-courses/ loads. Used by GitHub on pull requests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from inpace.course import CourseError, files_from_folder, load_course  # noqa: E402

root = Path(__file__).resolve().parent.parent / "community-courses"
bad = 0
for folder in sorted(p for p in root.iterdir() if p.is_dir()):
    try:
        c = load_course(files_from_folder(folder))
        print(f"OK   {folder.name}: {c.title} ({len(c.modules)} modules, {c.lesson_count} lessons)")
    except CourseError as e:
        bad += 1
        print(f"FAIL {folder.name}:")
        for p in e.problems:
            print(f"     - {p}")
sys.exit(1 if bad else 0)
