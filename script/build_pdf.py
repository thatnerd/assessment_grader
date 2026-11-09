#!/usr/bin/env python3
"""Render a grades JSON file into a cut-and-staple grading PDF: one compact
strip per student, dashed separators, sized to waste little paper when
printed and cut apart.

Usage:
    python3 script/build_pdf.py [--data results/grades.json] [--out results/grades.pdf]

--------------------------------------------------------------------------
JSON schema (see script/grades.example.json for a filled-in example):

{
  "title": "<quiz name> — Grading Results",
  "cut_note": "Cut along dashed lines and staple each strip to the matching student's quiz.",
  "students": [
    {
      "file": "IMG_1234.jpg",          // source image, for traceability
      // (a multi-page test uses "files": ["IMG_1.jpg", "IMG_2.jpg"] instead —
      // see script/pending_images.py --pages)
      "name": "Student Name",
      "name_uncertain": false,          // true if handwriting was hard to read
      "form": "202610271",              // optional; which printed form/version
                                        // this student took, when a quiz has
                                        // several whose answers differ. Read it
                                        // off the student's own page — see
                                        // CLAUDE.md step 5.
      "sections": [
        {
          "label": "Header",
          "style": "inline",            // one compact line of chips + a detail string
          "detail": "Period 6 · 9/21/26 · AP Precalculus",
          "criteria": [
            {"label": "Date",   "points": 1,  "earned": true},
            {"label": "Period", "points": 1,  "earned": true},
            {"label": "Class",  "points": 1,  "earned": false}
          ]
          // "Name" is NOT a header chip: it's its own checklist section
          // (a single criterion labeled "Name") carrying the grade-floor
          // points. See CLAUDE.md's grade-floor policy for why, and note
          // that build_problem_report.py excludes the section labeled
          // exactly "Name" from its per-problem breakdown.
        },
        {
          "label": "Prob 7 (bonus)",
          "style": "checklist",
          "extra_credit": true,          // optional; see note below
          "criteria": [
            {"label": "...", "points": 1, "earned": true}
          ]
        },
        {
          "label": "Prob 1: convert π/2 rad → degrees",
          "style": "checklist",          // a bulleted pass/fail list
          "criteria": [
            {"label": "Starting point written", "points": 1, "earned": true},
            {
              "label": "Correct answer: 90",
              "points": 1,
              "earned": false,
              "correct_answer": "90°",      // optional; shown only when earned=false
              "their_answer": "60°"         // optional; shown alongside correct_answer
            }
          ],
          "why": "Dropped a factor of 2 while simplifying 360/(2π)."
          // optional per-section one-liner — the *reason* behind the lost
          // points, shown next to the auto-computed "Lost N/M pts: ..."
          // summary line (that line itself is generated automatically from
          // whichever criteria have earned=false — don't write it by hand).
        }
        // ...as many checklist sections as the rubric has (arranged side
        // by side, wrapping automatically). There should be at most one
        // "inline" section, normally first (the header).
      ],
      "adjustments": [                  // optional; e.g. a handwritten late penalty
        {"label": "late", "points": -3}
      ],
      "notes": "Free-text notes about the student as a whole (security flags, name-legibility caveats, cross-problem observations) — not where per-problem point-loss reasons go; use each section's \"why\" for that instead."
    }
  ]
}

Points — on a criterion or an adjustment — may be fractional (0.5, 2.25).
Values are rounded to the cent for display and summation, and a whole
number is collapsed, so 2.0 renders as "2". Note that a criterion's
"earned" is strictly boolean: to express partial credit *within* one
criterion, split it into several cumulative criteria rather than inventing
a fractional value.

A section's max points = sum of its criteria's points. A student's total
= sum of all section points earned (required *and* extra-credit sections
both count toward this) + sum of adjustment points (adjustments are
typically negative). When adjustments is non-empty, the strip shows both
the pre-adjustment and final score.

A section with `"extra_credit": true` contributes its earned points to a
student's total the same as any other section, but its max points are
excluded from the denominator used for every percentage/letter-grade
calculation (per-student and class statistics both). This is how bonus
problems work: earning them only helps, never required to reach 100%.
The strip labels an extra-credit section's title with "(extra credit)".

For a checklist section with earned < max, the strip automatically prints
"Lost N/M pt(s): <missed criteria labels>" — computed from whichever
criteria have earned=false, not something to write by hand. Add a per-
criterion "correct_answer" (and optionally "their_answer") wherever a
wrong sub-part has one specific right value, and a per-section "why" when
there's a one-line reason worth stating beyond the missed labels (e.g. an
arithmetic slip) — both optional, both skip cleanly when omitted.

Do not hardcode this quiz's specific rubric (π/2 rad, 120°, ...) anywhere
else — the rubric changes between runs. Grade fresh against the current
rubric.md and produce grades.json accordingly; this script only renders it.

A "Class statistics" box is rendered automatically at the top of the PDF —
maximum points, mean, median, mode, and population standard deviation of
final scores (mean/median also shown as a letter grade) — computed fresh
from grades.json on every render, nothing to pass in or keep in sync by
hand. Each student's strip likewise shows their percentage and letter
grade under the raw score, using the same fixed GRADE_SCALE constant
(A+ ≥96, A 93-95, A- 90-92, B+ 87-89, B 83-86, B- 80-82, C+ 77-79, C 73-76,
C- 70-72, D+ 67-69, D 63-66, D- 60-62, F <60) — see that constant's comment
for the confirm-before-changing policy.
--------------------------------------------------------------------------
"""
import argparse
import html
import json
import statistics
import sys
from pathlib import Path

from weasyprint import HTML

CHECK = "&#10003;"
CROSS = "&#10007;"

# Letter-grade cutoffs (percent, inclusive lower bound), highest first.
# This is a fixed policy applied to every quiz — confirmed with the user
# on 2026-10-18. If the user ever asks to change these cutoffs, present
# the full reconstructed table back to them and get explicit confirmation
# before editing this constant — don't silently adjust it.
GRADE_SCALE = [
    (96, "A+"), (93, "A"), (90, "A-"),
    (87, "B+"), (83, "B"), (80, "B-"),
    (77, "C+"), (73, "C"), (70, "C-"),
    (67, "D+"), (63, "D"), (60, "D-"),
    (0, "F"),
]


def letter_grade(pct):
    for threshold, letter in GRADE_SCALE:
        if pct >= threshold:
            return letter
    return "F"


def esc(s):
    return html.escape(str(s))


def clean_points(x):
    """Round a points value to the cent to absorb binary float summation
    noise (e.g. ten 0.1s summing to 0.9999999999999999), and collapse a
    whole number to int so it renders as "1" rather than "1.0"."""
    x = round(x, 2)
    return int(x) if x == int(x) else x


def signed_points(x):
    """Render a points value with an explicit sign, for adjustments.

    Fractional adjustments are legal (e.g. a -0.5 deduction), so this must
    not use ":+d", which raises ValueError on a float. A bare ":+" formats
    ints and floats alike, and clean_points first strips float noise and
    collapses a whole number so -2.0 renders as "-2" rather than "-2.0"."""
    return f"{clean_points(x):+}"


def section_totals(section):
    earned = sum(c["points"] for c in section["criteria"] if c.get("earned"))
    maximum = sum(c["points"] for c in section["criteria"])
    return clean_points(earned), clean_points(maximum)


def render_inline_section(section):
    earned, maximum = section_totals(section)
    chips = []
    for c in section["criteria"]:
        ok = bool(c.get("earned"))
        cls = "ok" if ok else "no"
        pts = clean_points(c["points"]) if ok else 0
        mark = CHECK if ok else CROSS
        chips.append(
            f'<span class="{cls}">{esc(c["label"])} {pts}/{clean_points(c["points"])} {mark}</span>'
        )
    detail = section.get("detail", "")
    detail_html = f'<span class="detail">&mdash; {esc(detail)}</span>' if detail else ""
    return (
        f'<div class="headerline"><strong>{esc(section["label"])} {earned}/{maximum}:</strong> '
        f'{" ".join(chips)} {detail_html}</div>'
    ), earned, maximum


def render_checklist_section(section):
    earned, maximum = section_totals(section)
    rows = []
    missed_labels = []
    for c in section["criteria"]:
        ok = bool(c.get("earned"))
        cls = "ok" if ok else "no"
        mark = CHECK if ok else CROSS
        extra = ""
        if not ok:
            missed_labels.append(c["label"])
            correct = c.get("correct_answer")
            if correct:
                theirs = c.get("their_answer")
                wrote = f" (wrote: {esc(theirs)})" if theirs else ""
                extra = f' <span class="correct">&mdash; correct: {esc(correct)}{wrote}</span>'
        rows.append(f'<li class="{cls}"><span class="mark">{mark}</span>{esc(c["label"])}{extra}</li>')

    lost_html = ""
    if earned < maximum:
        why = section.get("why", "")
        why_html = f' &mdash; {esc(why)}' if why else ""
        lost_html = (
            f'<div class="lost">Lost {clean_points(maximum - earned)}/{maximum} pt(s): '
            f'{esc(", ".join(missed_labels))}{why_html}</div>'
        )

    ec_badge = ' <span class="ecbadge">extra credit</span>' if section.get("extra_credit") else ""
    return (
        f'<div class="prob"><div class="probtitle">{esc(section["label"])} '
        f'({earned}/{maximum}){ec_badge}</div><ul>{"".join(rows)}</ul>{lost_html}</div>'
    ), earned, maximum


def student_files(student):
    """Return a student's source image filename(s) as a list, regardless of
    whether the entry uses the single-page "file" key or the multi-page
    "files" key."""
    if "files" in student:
        return list(student["files"])
    if student.get("file"):
        return [student["file"]]
    return []


def student_total(student):
    """Return (final_total, total_max) for a student: section points earned
    (required and extra-credit sections both count) plus adjustment points,
    versus the sum of max points of required (non-extra-credit) sections
    only — extra credit never inflates the denominator."""
    total_earned = sum(
        c["points"]
        for section in student["sections"]
        for c in section["criteria"]
        if c.get("earned")
    )
    total_max = sum(
        c["points"]
        for section in student["sections"]
        if not section.get("extra_credit")
        for c in section["criteria"]
    )
    adj_points = sum(a["points"] for a in student.get("adjustments", []))
    return clean_points(total_earned + adj_points), clean_points(total_max)


def render_student(student):
    inline_html = ""
    checklist_htmls = []
    total_earned = 0
    total_max = 0

    for section in student["sections"]:
        style = section.get("style", "checklist")
        if style == "inline":
            frag, earned, maximum = render_inline_section(section)
            inline_html += frag
        else:
            frag, earned, maximum = render_checklist_section(section)
            checklist_htmls.append(frag)
        total_earned += earned
        if not section.get("extra_credit"):
            total_max += maximum

    adjustments = student.get("adjustments", [])
    adj_points = sum(a["points"] for a in adjustments)
    total_earned = clean_points(total_earned)
    total_max = clean_points(total_max)
    final_total = clean_points(total_earned + adj_points)

    pct = (final_total / total_max * 100) if total_max else 0
    grade = letter_grade(pct)
    grade_html = f'<span class="scoregrade">{pct:.0f}% &middot; {grade}</span>'

    if adjustments:
        adj_desc = ", ".join(f'{a["label"]} {signed_points(a["points"])}' for a in adjustments)
        score_html = (
            f'<div class="score"><span class="scoremain">{final_total} / {total_max}</span>'
            f'{grade_html}'
            f'<span class="scoresub">{total_earned}/{total_max} &middot; {esc(adj_desc)}</span></div>'
        )
    else:
        score_html = f'<div class="score"><span class="scoremain">{final_total} / {total_max}</span>{grade_html}</div>'

    name_flag = ' <span class="flag">(name spelling uncertain)</span>' if student.get("name_uncertain") else ""
    form = student.get("form")
    form_html = f'<span class="form">Form {esc(form)}</span>' if form else ""
    files = student_files(student)
    src = f'<span class="src">{esc(", ".join(files))}</span>' if files else ""
    notes = student.get("notes", "")
    notes_html = f'<div class="notes"><strong>Notes:</strong> {esc(notes)}</div>' if notes else ""

    return f"""
    <section class="strip">
      <div class="toprow">
        <div class="who">
          <span class="name">{esc(student["name"])}</span>{name_flag}
          {form_html}
          {src}
        </div>
        {score_html}
      </div>
      {inline_html}
      <div class="probs">{''.join(checklist_htmls)}</div>
      {notes_html}
    </section>
    """


def render_stats(students):
    totals = [student_total(s)[0] for s in students]
    max_points = student_total(students[0])[1]
    n = len(totals)

    mean = statistics.mean(totals)
    median = statistics.median(totals)
    stdev = statistics.pstdev(totals) if n > 1 else 0.0

    modes = statistics.multimode(totals)
    if n > 1 and len(modes) == n:
        mode_str = "none (all scores unique)"
    else:
        mode_str = ", ".join(str(m) for m in sorted(modes))

    def pct(x):
        return (x / max_points * 100) if max_points else 0

    return f"""
    <div class="stats">
      <strong>Class statistics ({n} student{'s' if n != 1 else ''}):</strong>
      <span>Maximum points: {max_points}</span>
      <span>Mean {mean:.1f} ({pct(mean):.1f}%, {letter_grade(pct(mean))})</span>
      <span>Median {median:.1f} ({pct(median):.1f}%, {letter_grade(pct(median))})</span>
      <span>Mode {mode_str}</span>
      <span>Std Dev {stdev:.1f}</span>
    </div>
    """


CSS = """
@page { size: Letter; margin: 0.35in 0.4in; }
* { box-sizing: border-box; }
body { font-family: Helvetica, Arial, sans-serif; color: #111; font-size: 8.3pt; }
.strip { border-bottom: 1.5px dashed #888; padding: 8px 4px 10px 4px; break-inside: avoid-page; }
.strip:first-child { padding-top: 2px; }
.toprow { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 3px; break-after: avoid-page; break-inside: avoid-page; }
.name { font-size: 13pt; font-weight: bold; }
.src { font-size: 7pt; color: #888; margin-left: 8px; }
.form { font-size: 7.5pt; color: #1a5aa8; font-weight: bold; margin-left: 8px; }
.flag { font-size: 7.5pt; color: #a15c00; font-style: italic; }
.score { text-align: right; border: 1.5px solid #111; padding: 1px 10px; border-radius: 4px; line-height: 1.15; }
.scoremain { font-size: 15pt; font-weight: bold; display: block; }
.scoregrade { font-size: 8pt; font-weight: bold; color: #333; display: block; white-space: nowrap; }
.scoresub { font-size: 6.6pt; color: #555; display: block; white-space: nowrap; }
.headerline { margin-bottom: 5px; }
.headerline .ok { color: #0a7a27; margin-right: 8px; }
.headerline .no { color: #b30000; margin-right: 8px; font-weight: bold; }
.headerline .detail { color: #555; font-style: italic; }
.probs { column-count: 2; column-gap: 14px; }
.prob { break-inside: avoid; margin-bottom: 8px; }
.probtitle { font-weight: bold; margin-bottom: 2px; border-bottom: 0.75px solid #ccc; }
.ecbadge { font-weight: normal; font-size: 6.6pt; color: #7a4e00; background: #fdf0d5; border-radius: 3px; padding: 1px 4px; vertical-align: middle; }
ul { list-style: none; margin: 0; padding: 0; }
li { padding: 0.5px 0; }
li .mark { display: inline-block; width: 13px; font-weight: bold; }
li.ok .mark { color: #0a7a27; }
li.no .mark { color: #b30000; }
li.no { color: #7a0000; }
.correct { color: #1a5aa8; font-style: italic; font-weight: normal; }
.lost { margin-top: 3px; font-size: 7.2pt; color: #7a0000; font-style: italic; }
.notes { margin-top: 5px; font-size: 7.6pt; color: #333; background: #f6f6f6; padding: 4px 6px; border-left: 2px solid #999; }
h1 { font-size: 12pt; margin: 0 0 2px 0; }
.pagehead { margin-bottom: 6px; }
.pagehead .sub { font-size: 7.5pt; color: #666; }
.stats {
  margin-bottom: 10px; padding: 5px 8px; background: #eef2f6; border: 0.75px solid #c4d0dc;
  border-radius: 4px; font-size: 7.6pt; display: flex; gap: 14px; flex-wrap: wrap; align-items: baseline;
}
.stats strong { margin-right: 2px; }
"""


def build(data):
    strips = "".join(render_student(s) for s in data["students"])
    stats_html = render_stats(data["students"])
    title = data.get("title", "Grading Results")
    cut_note = data.get("cut_note", "Cut along dashed lines and staple each strip to the matching student's quiz.")
    return f"""
    <html><head><meta charset="utf-8"><style>{CSS}</style></head>
    <body>
    <div class="pagehead">
      <h1>{esc(title)}</h1>
      <div class="sub">{esc(cut_note)}</div>
    </div>
    {stats_html}
    {strips}
    </body></html>
    """


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="results/grades.json", help="Input grading JSON (default: results/grades.json)")
    ap.add_argument("--out", default="results/grades.pdf", help="Output PDF path (default: results/grades.pdf)")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.is_file():
        sys.exit(f"no such file: {data_path}")
    data = json.loads(data_path.read_text())

    if not data.get("students"):
        sys.exit("grades JSON has no students — nothing to render")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=build(data)).write_pdf(out_path)
    print(f"wrote {out_path} ({len(data['students'])} student(s))")


if __name__ == "__main__":
    main()
