#!/usr/bin/env python3
"""Render a problem-by-problem class breakdown from results/grades.json:
for each graded section (Problem 1, 2, 3, 4, 5a, 5b, 5c, 6a, 6b, 7 for the
current rubric — whatever section labels actually appear, in first-seen
order), what percentage of the class landed in each of five buckets:

  blank      — nothing written for this problem at all
  off-topic  — wrote something there, but it doesn't address the problem
  wrong      — a genuine, on-topic attempt that earned no credit
  partial    — earned some but not all of the section's points
  correct    — earned full credit

Usage:
    python3 script/build_problem_report.py [--data results/grades.json] [--out results/problem_breakdown.pdf]

This is a separate, optional report from script/build_pdf.py's per-student
strips — see CLAUDE.md's "Problem-by-problem breakdown" section for when to
run it. It reads the whole grades.json fresh every time (not incremental).

How a section's bucket is decided, from what's already in grades.json:
  - earned == total points            -> correct
  - 0 < earned < total points         -> partial
  - earned == 0, section has "response": "blank"     -> blank
  - earned == 0, section has "response": "off_topic" -> off-topic
  - earned == 0, no "response" set                   -> wrong (the default)
The "Name" section is always excluded (it isn't a graded problem).
"""
import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

from weasyprint import HTML

sys.path.insert(0, str(Path(__file__).parent))
from build_pdf import clean_points  # noqa: E402

BUCKETS = ["correct", "partial", "wrong", "off_topic", "blank"]
BUCKET_LABEL = {
    "correct": "Correct", "partial": "Partial", "wrong": "Wrong",
    "off_topic": "Off-topic", "blank": "Blank",
}
BUCKET_COLOR = {
    "correct": "#0a7a27", "partial": "#c9961a", "wrong": "#b30000",
    "off_topic": "#6a6a9a", "blank": "#999999",
}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def section_bucket(section):
    criteria = section.get("criteria", [])
    # Round before comparing: with fractional criteria, binary float
    # summation makes `earned == total` false for a full-credit section
    # (0.1 + 0.2 != 0.3), which would misreport it as partial.
    total = clean_points(sum(c["points"] for c in criteria))
    earned = clean_points(sum(c["points"] for c in criteria if c.get("earned")))
    if total == 0:
        return None
    if earned == total:
        return "correct"
    if earned > 0:
        return "partial"
    resp = section.get("response")
    if resp == "blank":
        return "blank"
    if resp == "off_topic":
        return "off_topic"
    return "wrong"


def collect(students):
    """Returns (section_labels_in_order, {label: {bucket: count}}, untagged_zero_count).

    untagged_zero_count is how many zero-credit sections carried no
    "response" tag and so fell into the "wrong" bucket by default. It
    drives the caveat on the report: if grading predated that tag (or
    applied it inconsistently), those sections may really be blank or
    off-topic, and the blank/off-topic split is understated by that much.
    """
    order = []
    counts = OrderedDict()
    untagged_zero = 0
    for s in students:
        for sec in s.get("sections", []):
            label = sec["label"]
            if label == "Name":
                continue
            bucket = section_bucket(sec)
            if bucket is None:
                continue
            if label not in counts:
                counts[label] = {b: 0 for b in BUCKETS}
                order.append(label)
            counts[label][bucket] += 1
            if bucket == "wrong":
                untagged_zero += 1
    return order, counts, untagged_zero


def render_bar(label, counts, n_students):
    total = sum(counts.values())
    segments = ""
    for b in BUCKETS:
        n = counts[b]
        if n == 0:
            continue
        pct = n / total * 100
        segments += (
            f'<div class="seg" style="width:{pct:.3f}%; background:{BUCKET_COLOR[b]};" '
            f'title="{BUCKET_LABEL[b]}: {n}"></div>'
        )
    legend = "".join(
        f'<span class="legenditem"><span class="swatch" style="background:{BUCKET_COLOR[b]}"></span>'
        f'{BUCKET_LABEL[b]} {counts[b]} ({counts[b]/total*100:.0f}%)</span>'
        for b in BUCKETS if counts[b] > 0
    )
    missing = n_students - total
    missing_note = (
        f'<span class="missingnote">({missing} student(s) have no entry for this section)</span>'
        if missing else ""
    )
    return f"""
    <div class="row">
      <div class="rowlabel">{esc(label)}</div>
      <div class="bar">{segments}</div>
      <div class="legend">{legend}{missing_note}</div>
    </div>
    """


CSS = """
@page { size: Letter; margin: 0.5in 0.55in; }
* { box-sizing: border-box; }
body { font-family: Helvetica, Arial, sans-serif; color: #111; font-size: 9pt; }
h1 { font-size: 15pt; margin: 0 0 2px 0; }
.sub { font-size: 8.5pt; color: #666; margin-bottom: 4px; }
.caveat { font-size: 8pt; color: #a15c00; font-style: italic; margin-bottom: 14px; }
.row { margin-bottom: 16px; page-break-inside: avoid; }
.rowlabel { font-weight: bold; font-size: 10pt; margin-bottom: 3px; }
.bar { display: flex; width: 100%; height: 16px; border: 0.75px solid #888; border-radius: 2px; overflow: hidden; margin-bottom: 4px; }
.seg { height: 100%; }
.legend { font-size: 7.8pt; color: #333; }
.legenditem { margin-right: 12px; white-space: nowrap; }
.swatch { display: inline-block; width: 8px; height: 8px; margin-right: 3px; border-radius: 1px; vertical-align: middle; }
.missingnote { color: #999; font-style: italic; }
.summary { margin-top: 4px; font-size: 7.6pt; color: #555; }
"""


def build(data, n_students):
    students = data["students"]
    order, counts, untagged_zero = collect(students)
    base_title = data.get("title", "Grading Results")
    base_title = base_title.rsplit(" — Grading Results", 1)[0]
    title = base_title + " — Problem Breakdown"
    rows = "".join(render_bar(label, counts[label], n_students) for label in order)
    if untagged_zero:
        caveat = (
            f"Blank vs. off-topic vs. wrong is read from each section's optional "
            f'"response" tag in grades.json. {untagged_zero} zero-credit section(s) here '
            f'carry no tag and are counted as "wrong" by default — if that tag was not set '
            f"consistently while grading, some of those are really blank or off-topic, and "
            f'those two buckets are understated by up to that much. See CLAUDE.md\'s '
            f'"Problem-by-problem breakdown" note.'
        )
    else:
        caveat = (
            'Every zero-credit section carries an explicit "response" tag, so the '
            "blank / off-topic / wrong split below is exact."
        )
    return f"""
    <html><head><meta charset="utf-8"><style>{CSS}</style></head>
    <body>
    <h1>{esc(title)}</h1>
    <div class="sub">What percentage of the class left each problem blank, wrote something
    off-topic, got it wrong, got it partially correct, or got it fully correct
    ({n_students} student(s)).</div>
    <div class="caveat">{caveat}</div>
    {rows}
    </body></html>
    """, untagged_zero


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="results/grades.json", help="Input grading JSON (default: results/grades.json)")
    ap.add_argument("--out", default="results/problem_breakdown.pdf", help="Output PDF path (default: results/problem_breakdown.pdf)")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.is_file():
        sys.exit(f"no such file: {data_path}")
    data = json.loads(data_path.read_text())

    if not data.get("students"):
        sys.exit("grades JSON has no students — nothing to report on")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html_str, untagged_zero = build(data, len(data["students"]))
    HTML(string=html_str).write_pdf(out_path)
    print(f"wrote {out_path} ({len(data['students'])} student(s))")
    if untagged_zero:
        print(
            f'note: {untagged_zero} zero-credit section(s) have no "response" tag and were '
            'counted as "wrong" — blank/off-topic may be undercounted (see CLAUDE.md).'
        )
    else:
        print('all zero-credit sections are "response"-tagged — the blank/off-topic split is exact.')


if __name__ == "__main__":
    main()
