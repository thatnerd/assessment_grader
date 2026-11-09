#!/usr/bin/env python3
"""Safely merge one or more newly-graded students into results/grades.json,
without hand-editing the (potentially large) existing file.

This is the "append to a complete batch" step: grade each new image (a
vision/agent task — this script doesn't do that part), write the result as
a small JSON fragment (a single student object, or a JSON array/`{"students":
[...]}` of several), then merge it in:

    python3 script/append_grades.py new_student.json
    python3 script/append_grades.py new_student_1.json new_student_2.json
    python3 script/append_grades.py --data results/grades.json batch.json

Refuses to add a student whose source file (or, for a multi-page test, any
one of its "files") already has an entry in the target JSON, so re-running
against the same fragment (or accidentally grading the same image twice)
never silently duplicates or overwrites a result — pass --replace to
intentionally overwrite an existing entry (e.g. a regrade).

If --data doesn't exist yet, it's created fresh — pass --title in that case
(see script/build_pdf.py's docstring for the full schema, including the
multi-page "files": [...] form — see also script/pending_images.py --pages,
which groups sequential images for a multi-page test).
"""
import argparse
import json
import sys
from pathlib import Path

REQUIRED_STUDENT_KEYS = {"name", "sections"}


def load_fragment(path: Path):
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "students" in data:
        return data["students"]
    if isinstance(data, dict):
        return [data]
    sys.exit(f"{path}: expected a student object, a list of students, or {{\"students\": [...]}}")


def student_files(student):
    """A student's source filename(s) as a list, whether given as "file"
    (single page) or "files" (multi-page test)."""
    if "files" in student:
        return list(student["files"])
    if student.get("file"):
        return [student["file"]]
    return []


def validate_student(student, source):
    missing = REQUIRED_STUDENT_KEYS - student.keys()
    if missing:
        sys.exit(f"{source}: student {student.get('name', '?')!r} is missing required field(s): {sorted(missing)}")
    if not student_files(student):
        sys.exit(f"{source}: student {student.get('name', '?')!r} has no \"file\" or \"files\" entry")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fragments", nargs="+", help="One or more JSON files with new student(s) to append")
    ap.add_argument("--data", default="results/grades.json", help="Target grading JSON (default: results/grades.json)")
    ap.add_argument("--title", default="Grading Results", help="Title to use if --data doesn't exist yet")
    ap.add_argument(
        "--cut-note",
        default="Cut along dashed lines and staple each strip to the matching student's quiz.",
        help="Cut note to use if --data doesn't exist yet",
    )
    ap.add_argument("--replace", action="store_true", help="Overwrite an existing entry for the same file instead of refusing")
    args = ap.parse_args()

    data_path = Path(args.data)
    if data_path.is_file():
        data = json.loads(data_path.read_text())
    else:
        data = {"title": args.title, "cut_note": args.cut_note, "students": []}

    existing_by_file = {}
    for i, s in enumerate(data["students"]):
        for f in student_files(s):
            existing_by_file[f] = i

    added, replaced = [], []
    for frag_path_str in args.fragments:
        frag_path = Path(frag_path_str)
        if not frag_path.is_file():
            sys.exit(f"no such file: {frag_path}")
        for student in load_fragment(frag_path):
            validate_student(student, frag_path)
            files = student_files(student)
            label = ", ".join(files)
            matched_indices = {existing_by_file[f] for f in files if f in existing_by_file}
            if matched_indices:
                if not args.replace:
                    sys.exit(
                        f"refusing to append: {label!r} overlaps an existing entry in {data_path} "
                        "(pass --replace to overwrite it intentionally)"
                    )
                if len(matched_indices) > 1:
                    sys.exit(
                        f"refusing to append: {label!r} overlaps *multiple* existing entries in "
                        f"{data_path} — resolve this by hand, it's not a simple replace"
                    )
                idx = matched_indices.pop()
                data["students"][idx] = student
                replaced.append(label)
            else:
                data["students"].append(student)
                idx = len(data["students"]) - 1
                added.append(label)
            for f in files:
                existing_by_file[f] = idx

    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    if added:
        print(f"Added {len(added)}: {', '.join(added)}")
    if replaced:
        print(f"Replaced {len(replaced)}: {', '.join(replaced)}")
    print(f"{data_path} now has {len(data['students'])} student(s). Run script/build_pdf.py to re-render.")


if __name__ == "__main__":
    main()
