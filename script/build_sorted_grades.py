#!/usr/bin/env python3
"""Write a quick-reference grade distribution to a Markdown file.

Usage:
    python3 script/build_sorted_grades.py [--data results/grades.json] [--out results/sorted_grades.md]

Reads the same results/grades.json as build_pdf.py (and reuses its scoring
logic directly, so this always agrees with what's on the strips) and writes
one line per student — score, percentage, and letter grade — sorted highest
to lowest. This is a plain-text companion to the PDF for a quick scan of
where the class landed, not a replacement for it.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_pdf import student_total, letter_grade  # noqa: E402


def build(data):
    rows = []
    for student in data["students"]:
        final_total, total_max = student_total(student)
        pct = (final_total / total_max * 100) if total_max else 0
        rows.append((pct, final_total, total_max, letter_grade(pct), student["name"]))

    rows.sort(key=lambda r: -r[0])

    lines = [f"# {data.get('title', 'Grades')} — Sorted by Grade", ""]
    for pct, final_total, total_max, grade, name in rows:
        lines.append(f"- {final_total}/{total_max} ({pct:.1f}%, {grade}) — {name}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="results/grades.json", help="Input grading JSON (default: results/grades.json)")
    ap.add_argument("--out", default="results/sorted_grades.md", help="Output Markdown path (default: results/sorted_grades.md)")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.is_file():
        sys.exit(f"no such file: {data_path}")
    data = json.loads(data_path.read_text())

    if not data.get("students"):
        sys.exit("grades JSON has no students — nothing to write")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build(data))
    print(f"wrote {out_path} ({len(data['students'])} student(s))")


if __name__ == "__main__":
    main()
