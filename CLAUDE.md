# Quiz grading — agent instructions

This project grades photographed quiz pages against a rubric and produces a
printable, cut-and-staple PDF of per-student results.

Directory layout:
- `rubric.md` — the current rubric. **Read it fresh every time**, and
  **cross-check it against the actual assessment images, not just for
  internal self-consistency** — see Workflow step 2. It changes between
  runs (different problems, different point values, different header
  requirements) — never assume a previous session's specific rubric (e.g.
  "convert π/2 rad to degrees") still applies. If it's inconsistent —
  either internally, or against what the images actually show — stop and
  propose a specific corrected rubric for the user to confirm, rather than
  grading against something you know is wrong.
- `images/` — one photo per student, named freely (e.g. `IMG_1234.jpg`).
  New batches typically arrive as `.HEIC`/`.HEIF` (iPhone) files here.
- `rosters/*.json` — one file per class, holding canonical student name
  spellings. Durable across quizzes (not archived with the rest — see
  "Class rosters" below). Check it as part of grading, not just when asked.
- `results/grades.json` — structured grading data (see schema below).
- `results/grades.pdf` — the rendered output, built from `grades.json`.
- `results/sorted_grades.md` — all students sorted by grade, highest to
  lowest, built from `grades.json` alongside `grades.pdf` every render
  (see workflow step 7).
- `script/` — automation (see below). Read each script's own docstring/
  `--help` before using it; this file gives the workflow, not the details.

This project is graded incrementally — the user may add 1, a handful, or a
full class's worth of images at any point, including after a batch has
already been graded once (they forgot a few, a late student turns theirs
in, etc.). Every step below is designed to be safe to re-run and to only
touch what's new; never assume you're starting from zero, and never regrade
or re-render more than what's actually pending unless asked.

## Workflow

1. **Extract new images, if any raw photos were added:**
   ```
   python3 script/extract_images.py
   ```
   This converts any `.HEIC`/`.HEIF`/oversized `.png`/`.jpg` in `images/`
   into small JPEGs (~1400px long edge by default — sized so ~80 quizzes
   fit a session's image-token budget), and **deletes the raw originals**.
   Parallelized across files; pass `--parallize N` to change worker count
   (default 8). Safe to re-run — it skips files that are already small
   enough, and cleans up any stale raw file left next to an already-
   extracted `.jpg`. Naturally handles 1 new image or many in the same run.

2. **Read `rubric.md` and cross-check it against the actual assessment —
   do this after step 1, with real images in hand, not in isolation.**
   Work out the header requirements and each problem's point breakdown
   fresh from this file every time; never assume a previous session's
   specific rubric still applies. Two separate checks, both required:
   - **Self-consistency**: does the rubric's own problem statement match
     its point-breakdown text — same numbers, same expected answers? This
     alone has been wrong before (a rubric whose problem statement and
     point breakdown described different numbers).
   - **Cross-check against the assessment**: before settling on your
     understanding, view at least a handful of the newly extracted images
     (all of them, if the batch is small) and confirm the rubric's stated
     problem(s)/numbers genuinely match what's printed on the actual quiz
     pages — this naturally feeds into grading, it isn't a wasted extra
     pass. This has caught a real mismatch before: a rubric that said
     "210 degrees" when the printed quiz actually said "270 degrees",
     only discovered once multiple students' answers all converged on 270.

   If you find **any** inconsistency this way — internal, or between the
   rubric and the actual assessment — don't just raise it as an open
   question: **propose a specific suggested corrected rubric** (the exact
   replacement text, derived from the evidence) and get the user to
   confirm before editing `rubric.md` or grading anything against it. This
   check only needs doing once per rubric version — not on every
   incremental append within the same quiz, only when `rubric.md` is new
   or has changed since you last checked it.

3. **Find out what actually needs grading:**
   ```
   python3 script/pending_images.py
   ```
   Compares `images/` against `results/grades.json` and lists images with
   no graded entry yet — this is how you pick up newly-added photos (or
   ones missed in an earlier pass) without re-grading everyone. Always run
   this rather than assuming "new images" means "everything in `images/`."
   **If this is a multi-page test** (see below), pass `--pages N` so it
   groups images N at a time instead of treating each as its own student.
   **If it warns about gaps or non-consecutive filenames, see "Multi-page
   tests" below before trusting the grouping** — don't assume the warning
   is cosmetic.

4. **Fix orientation — this step is manual, not automatic.** Tested and
   confirmed unreliable for this: (a) the images' own EXIF orientation
   tags (observed flatly wrong — tagged "normal" while the pixels were
   sideways), and (b) OCR-based auto-rotation via `tesseract --psm 0`
   (under 50% confidence, and it proposed the wrong rotation on two images
   whose correct orientation was already known). `extract_images.py` prints
   a `⚠ landscape aspect` hint for files that come out wider than tall —
   worth checking first, since these quiz pages are always portrait — but
   that's a hint, not a verdict: **view every newly extracted image**
   yourself. If one is sideways or upside down:
   ```
   python3 script/rotate_image.py images/IMG_1234.jpg 90
   ```
   The number is the clockwise rotation needed to make it right-side up
   (try 90, 180, or 270). Re-view the file after rotating to confirm.
   Do not proceed to grading an image until it displays upright.

5. **Grade each pending student image against the rubric** (the list from
   step 3 — not the whole directory, unless that list is everything).
   View each file in `images/`; use `script/crop.py` to zoom into a region
   if handwriting is too cramped to read at normal size:
   ```
   python3 script/crop.py images/IMG_1234.jpg 0.0 0.1 0.6 0.4 /tmp/zoom.jpg --scale 2.5
   ```
   (`x0 y0 x1 y1` are fractions of the image, top-left origin.)

   Grading fidelity rules:
   - Grade exactly what's on the page against exactly what the rubric
     says. A correct final answer doesn't retroactively earn credit for a
     missing required step, and a shown step doesn't earn credit if the
     rubric's specific target (e.g. a specific expression) isn't what's
     written.
   - Watch for a handwritten grading annotation such as `(-3, late)` or
     `(-6, late)` (often in red/different-colored ink) — this is a point
     deduction to apply, not part of the student's own work. Capture it as
     an `adjustments` entry (see schema below) rather than baking it into
     a criterion or silently dropping it.
   - Cursive names are often genuinely ambiguous. Give your best-guess
     transcription and set `"name_uncertain": true` rather than silently
     guessing or blocking on it. Before finalizing names, reconcile the
     batch against `rosters/` — see "Class rosters" below; this often
     resolves an ambiguous cursive guess into a confident one.
   - **Per-problem breakdown: for every wrong criterion that has one
     specific right value** (a final answer, a specific expression —
     not a mechanical step like "answer boxed" or a presence check like
     "Date"), **set `"correct_answer"` to that value, and `"their_answer"`
     to what the student actually wrote** (or a short description if it
     wasn't a clean single value, e.g. "blank"). The strip shows both
     automatically next to the ✗. **For every checklist section where
     points were lost, add a one-line `"why"`** stating the underlying
     reason (e.g. "dropped a factor of 2 while simplifying") when there's
     something more specific to say than the missed criteria labels alone
     — the strip auto-computes "Lost N/M pts: <missed labels>" from the
     criteria themselves, so don't restate that part by hand, just add the
     *reason* on top of it. Skip `"why"` when the missed-labels line
     already says everything there is to say (e.g. a blank problem).
   - **Whenever a section earns zero points, tag *how* it was zero** by
     setting `"response"` on that section to `"blank"` (nothing written
     for this problem at all) or `"off_topic"` (the student wrote
     something there, but it doesn't engage with the actual problem —
     unrelated scratch work, a flat non-answer like "nope.", copying a
     different problem's content, doodles). Leave `"response"` unset for
     a zero-point section where the student made a genuine, on-topic
     attempt that was simply incorrect — that's the default ("wrong") and
     needs no tag. A section with partial or full credit never needs this
     tag either, since earning any points already proves it was
     attempted. This powers `script/build_problem_report.py`'s
     blank/off-topic/wrong/partial/correct breakdown — see that script's
     docstring and "Problem-by-problem breakdown" below.
   - **Grade floor: baked into the rubric's `Name` criterion, not a
     post-hoc adjustment.** District policy requires no student's score
     drop below 53% of the quiz's total possible points — the minimum
     exists to keep a single F from being weighted too heavily against a
     student's overall grade. Rather than computing a score and then
     raising it after the fact, the rubric assigns `Name` a fixed point
     value chosen so that a legible name *by itself* already clears 53% of
     the quiz's total (name points + every other problem's points
     combined) — any additional correct work on top of that only raises
     the score further, never needs correcting down. **Grade `Name` as an
     ordinary checklist section**, same as any other problem, with a
     single criterion labeled just `"Name"` (not a longer description):
     full points if the student made any legible attempt at a name
     (first/last, nickname, initials — doesn't need to be fully
     readable), zero only if there's no name at all anywhere on the
     packet. Do **not** add a
     separate `adjustments` floor-raise entry anymore — that mechanism is
     obsolete now that `Name` itself supplies the floor. (A packet with
     *no name at all*, not even an illegible attempt, won't reach the
     floor this way — flag that to the user rather than inventing a
     workaround.)
   - **Extra credit: a section can be marked `"extra_credit": true`** (see
     `script/build_pdf.py`'s docstring for the exact schema). Its earned
     points still add to a student's total, but its max points are
     **excluded from the percentage denominator** everywhere (per-student
     and class statistics both) — so it only ever helps, never required to
     reach 100%. When computing `Name`'s floor value (below), "every other
     problem's points" means only the **required** (non-extra-credit)
     problems — extra credit doesn't count toward the total that `Name`
     needs to clear 53% of, since a student who skips all of it entirely
     must still be able to reach the floor from required work alone.
   - **This point value is a fixed, confirmed policy for the current
     rubric** (currently, for "Unit Test: Lines, Radians, and
     Right-Triangle Trig": Name = 113 points, required total = 213
     points [Name + the test's own 100 points: Part A 15 + Part B 24 +
     Part C 34 + Part D 27], up to 10 more available as extra credit
     [one problem, unchanged] — this test prints no dedicated Name line
     item of its own, so Name was added after grading, per the user's
     explicit request on 2026-10-19, specifically so that signing the
     test alone is worth exactly the 53% floor and every point of actual
     work adds on top rather than being capped there once the floor is
     cleared. Confirmed with the user that this mathematically raises
     *every* student's percentage, not just previously-floored ones
     (e.g. an unfloored 88% became 94.4%) — an intended consequence of
     this design, not a bug; see `rubric.md`'s header note for the full
     derivation. This is this quiz's own number, not a carryover from a
     previous quiz — recompute fresh for every new
     rubric, the same way, rather than reusing a prior quiz's Name value).
     **If the user
     ever asks to change the point totals (a new quiz, more/fewer
     problems, reweighting which problems are required vs. extra credit,
     etc.), recompute `Name` the same way — smallest integer N solving
     N/(N + sum of every *required* problem's points) ≥ 0.53 — and show
     the user the arithmetic for explicit confirmation before editing
     `rubric.md`,** the same standing rule used for the `GRADE_SCALE`
     letter cutoffs below. This also means every other required problem's
     percentage share of the quiz shrinks whenever `Name` is a large
     fraction of the required total — that's an expected consequence of
     this policy, not a bug, but worth flagging to the user if it produces
     a big swing (e.g. it visibly compresses high scores upward too, not
     just low ones) — and remember that a student who aces required work
     *and* extra credit can end up well over 100%; that's intentional here
     (capped only informally, by keeping extra-credit point values small
     relative to the required total — see `rubric.md`), not a bug either.
   - **Penalties are still floor-protected (confirmed with the user on
     2026-10-19).** The `Name` points guarantee the floor for the
     *unpenalized, required-only* score, but a late penalty or other
     deduction applied as an `adjustments` entry can still pull the net
     score below 53% on its own (e.g. 74 Name points minus a 6-point late
     penalty, with little else earned on required problems). After
     computing the student's full score — `Name` + every required problem
     section + every adjustment, including penalties (extra credit can
     help here too, but don't rely on it) — check it against the same
     floor used to derive `Name` in the first place (for the current
     trigonometry rubric: `ceil(139 × 0.53)` = 74; this will always equal
     `Name`'s own point value for whichever rubric is active, since `Name`
     was chosen to be the smallest integer clearing that exact threshold —
     recompute this per-rubric, don't reuse 74 for a future quiz). If the
     penalized net total is still below that floor, add one more
     `adjustments` entry that brings it back up to exactly the floor,
     labeled plainly (e.g. `"Grade floor: raised from 43/92 to 49/92
     (minimum 53%, district policy)"`), the same way the old mechanism
     used to for the whole score. In other words: `Name`
     handles the floor for a normal (non-penalized) submission by itself,
     with no adjustment needed; a floor-topup `adjustments` entry is only
     ever needed in the less-common case where a penalty pushes the
     penalized score below what `Name` alone guarantees.

6. **Append the newly-graded student(s) to `results/grades.json`.** Don't
   hand-edit that file directly — write the new student(s) (one object, or
   a JSON array of several) to a scratch file and merge it in:
   ```
   python3 script/append_grades.py /tmp/new_students.json
   ```
   This works the same whether it's the very first batch (creates
   `results/grades.json` fresh — pass `--title "<quiz name>"` in that case)
   or an append to an already-graded batch, and it refuses to silently
   duplicate or clobber an existing student — pass `--replace` only when
   you specifically intend to overwrite a prior entry (e.g. a regrade the
   user asked for). Schema is documented in the docstring at the top of
   `script/build_pdf.py`, and `results/grades.json` (if present) is a
   complete worked example — read it before writing a new fragment.
   Briefly: each student has `sections` (an inline "Header" section plus
   one "checklist" section per rubric problem, each with `criteria` of
   `{label, points, earned, correct_answer?, their_answer?}`, an optional
   per-section `why`, an optional per-section `response` for a zero-point
   section — see the grading-fidelity bullet above — and an optional
   per-section `extra_credit: true` for a bonus problem per the current
   rubric's required/extra-credit split), an optional `adjustments` list
   (e.g. the late penalty), and free-text `notes` for *whole-student* context
   (security flags, name-legibility caveats, cross-problem observations)
   — per-problem point-loss reasons go in that section's `why`, not here.

7. **Render the PDF:**
   ```
   python3 script/build_pdf.py
   ```
   Reads `results/grades.json`, writes `results/grades.pdf` — a class
   statistics box (maximum points, mean, median, mode, standard deviation
   — mean/median also shown as a letter grade — computed fresh every
   render, nothing to pass in) followed by one strip per student, each
   showing its own percentage and letter grade under the raw score, dashed
   cut lines, sized so several fit per page and a teacher can cut-and-
   staple each strip to the matching quiz without wasting paper. It always
   renders the *whole* file, so previously-graded students reappear in the
   output too — that's expected, not a sign something needs to be redone.

   The letter-grade cutoffs are a **fixed policy** (`GRADE_SCALE` in
   `script/build_pdf.py`: A+ ≥96, A 93-95, A- 90-92, B+ 87-89, B 83-86,
   B- 80-82, C+ 77-79, C 73-76, C- 70-72, D+ 67-69, D 63-66, D- 60-62,
   F <60 — confirmed with the user on 2026-10-18), applied the same way to
   every quiz regardless of its point total, since it's percentage-based.
   **If the user ever asks to change these cutoffs, reconstruct the full
   table and show it back to them for explicit confirmation before editing
   the constant** — don't silently adjust it, and don't assume a typo'd or
   out-of-order cutoff is what they meant without checking (this exact
   scale was set after catching a cutoff that was internally
   inconsistent — e.g. a "B+" range higher than "A+").

   **Also regenerate the sorted grade list, every time, right after the
   PDF:**
   ```
   python3 script/build_sorted_grades.py
   ```
   Writes `results/sorted_grades.md` — one line per student (score,
   percentage, letter grade), sorted highest to lowest, reusing
   `build_pdf.py`'s own scoring/letter-grade functions directly so it
   can never drift out of sync with the PDF. This is a quick-scan
   companion to the PDF (confirmed with the user on 2026-10-19 to be a
   standing part of every render, not an on-request extra) — like
   `build_pdf.py`, it always rewrites the *whole* file from
   `results/grades.json`, so don't skip it on an incremental append.

8. **Report a summary table to the user** (name, score, notable issues) —
   for an incremental append, lead with what's new, but feel free to
   mention how it fits into the running batch. Don't just say "done."

## Multi-page tests

Some tests span several photos per student (e.g. a 3-page packet
photographed one page at a time) instead of the usual one-photo-per-student
quiz. Tell `pending_images.py` how many pages each test has:
```
python3 script/pending_images.py --pages 3
```
It groups images N at a time in sorted-filename order and reports each
group as one pending unit, e.g. `IMG_4001.jpg, IMG_4002.jpg, IMG_4003.jpg`.
It flags (but still reports, doesn't silently drop) two problem cases —
read these before grading the group they apply to:
- **A leftover partial group** (image count isn't a multiple of N) — a
  page is probably missing or misfiled.
- **Non-consecutive filenames within a group** (e.g. a skipped/retaken
  photo shifted the grouping) — these pages may not actually belong to
  the same student; check manually before trusting the grouping.

**When `pending_images.py` raises any warning on a multi-page batch** (a
gap, a non-consecutive run, an incomplete group), don't trust the naive
"N consecutive files = one student" chunking — a single missing or
reordered photo shifts every group after it, and this can run for dozens
of files before it's obvious something's wrong (confirmed the hard way:
an entire batch's grouping silently drifted for ~15 students before the
mismatch was caught by content, not by any automated check). Instead,
reconstruct groupings by content: find each student's actual page-1 (the
name/header page) as the anchor, and follow that student's pages forward
by matching page numbers and content continuity (problem-set version,
handwriting, ink color) rather than assuming raw filename adjacency.
Expect this to turn up genuinely unresolvable cases — a page that's
missing outright, two candidate pages for the same slot with different
content, a student whose name page never got photographed at all. Don't
silently guess; record what you found (including the ambiguity) in the
manifest below and flag it to the user.

**Before grading an irregular batch, write your reconstructed grouping to
`results/student_files.json` and let the user review it** — this is a
cheap checkpoint that catches a bad grouping before you sink effort into
grading it wrong. For a clean batch (every group exactly N consecutive
files, zero warnings), this is optional; use your judgment, but err
toward writing it when you're not fully confident in a grouping.
```json
{
  "students": [
    {"name": "Full Name", "name_uncertain": false, "files": ["IMG_1001.jpg", "IMG_1002.jpg"]},
    {"name": "Name unknown", "name_uncertain": true, "files": ["IMG_1010.jpg", "IMG_1011.jpg"],
     "notes": "Page 1 never photographed; distinguishing feature: answered entirely in red ink."}
  ]
}
```
- Use the literal name `"Name unknown"` for a student whose name page is
  genuinely missing (not just hard to read — that's `name_uncertain`
  with a best-guess name instead). If more than one student in the same
  batch has no name, give each a `"notes"` describing something
  identifiable about the physical paper (ink color, distinctive content,
  which pages are present) so the user can match it by hand later —
  don't just number them, since that implies an ordering that isn't real.
- This file is a review checkpoint, not a grading record — once the user
  confirms it (or corrects it), proceed to grade normally and write the
  real result to `results/grades.json` as usual. Don't treat
  `student_files.json` as a substitute for that; it's upstream of it,
  and the two files can keep diverging as grading reveals more (e.g. a
  name page found out of order) if you remember to update both.

When grading a multi-page group, view all N images (they're pages of one
submission — read them in order) and write **one** student entry covering
the whole group, using `"files": [...]` (a list) instead of the single-page
`"file"` key:
```json
{
  "files": ["IMG_4001.jpg", "IMG_4002.jpg", "IMG_4003.jpg"],
  "name": "Student Name",
  "sections": [ ... combined across all pages ... ],
  "notes": "..."
}
```
`append_grades.py` and `build_pdf.py` both understand `"files"` —
duplicate detection checks every file in the list (not just the first),
and the strip shows all source filenames. Don't split one multi-page
submission into several student entries, and don't mix `--pages N`
grouping with single-page `"file"` entries in the same batch unless the
test genuinely has a mix of lengths (rare — ask the user if you suspect
this).

## Class rosters

`rosters/*.json` hold canonical student name spellings per class — a
durable, cross-quiz resource (unlike `images/`, `results/`, and
`rubric.md`, it is **not** touched by `archive_quiz.py`) that exists
because the same student's name often gets transcribed differently quiz to
quiz from messy handwriting. Mechanical fuzzy-matching lives in
`script/roster.py` (read its docstring for subcommand details); the
judgment calls below are this workflow.

Each roster file is one class:
```json
{
  "class": "AP Precalculus",
  "period": "6-7",
  "students": ["Full Name", "Full Name", ...]
}
```

**Before finalizing names in a batch** (this slots into step 5, after
you've transcribed your best guess for each student but before writing the
graded entries), find the matching roster and reconcile against it:
```
python3 script/roster.py match "Transcribed Name 1" "Transcribed Name 2" ...
```
Pass your best-guess transcription for every student in the batch in one
call — the roster with the highest match count is the batch's class. If
every roster scores 0 (including when `rosters/` has nothing for this
class yet), proceed with your best-guess transcriptions as usual; don't
block grading on a roster that doesn't exist.

With the right roster identified, handle each name by its own match:
- **Close match** → use the roster's canonical spelling on the graded
  entry, not your raw transcription — this is what keeps a student's name
  spelled the same way quiz to quiz. This doesn't need flagging to the
  user; it's exactly what the roster is for.
- **No close match** → either a genuinely new/unlisted student or a
  transcription too far off to resolve. Use your best-guess transcription
  (with `"name_uncertain": true` if the handwriting itself was ambiguous),
  and **propose adding the name to the roster in your step-8 summary**
  rather than adding it unprompted. Add it only after the user confirms
  it's correct and genuinely new/unlisted:
  ```
  python3 script/roster.py add "New Student" --roster rosters/<file>.json
  ```

**Propose growing or creating a roster proactively, not just reactively**
— e.g. if a batch's class has no roster file at all (`match` scored every
roster 0), suggest creating one from the batch's now-confirmed names once
grading is done, rather than waiting to be asked. Same rule either way:
propose, get confirmation, then add — never add silently.

## Problem-by-problem breakdown

A separate, optional report — `results/problem_breakdown.pdf` — shows,
for each graded section (Problem 1, 2, 3, 4, 5a, 5b, 5c, 6a, 6b, 7), what
percentage of the class landed in each of five buckets: blank, off-topic,
wrong, partial, correct. This is **not part of the normal per-batch
workflow** (don't generate it automatically after every grading run) —
only build or rebuild it when the user specifically asks for this
breakdown, since it reads the *whole* `results/grades.json` fresh each
time (not incremental).

```
python3 script/build_problem_report.py
```

It relies entirely on data already in `results/grades.json` — each
section's `criteria` (for the correct/partial/wrong split, via points
earned vs. possible) plus the optional `"response"` tag described above
(for the blank/off-topic split on a zero-point section). If you haven't
been tagging `"response"` consistently (e.g. grading done before this
feature existed), the script will undercount blank/off-topic and lump
them into "wrong" — tell the user this before presenting the numbers as
authoritative, and offer to go back through ungraded-for-this-field
students if they want it precise.

## Archiving a finished quiz

Once a quiz is fully graded and the user is done with it, `images/`,
`results/`, and `rubric.md` can be moved out of the way to make room for
the next one:
```
python3 script/archive_quiz.py <name>
```
Moves everything into `archive_<name>/` (as `archive_<name>/images/`,
`archive_<name>/results/`, `archive_<name>/rubric.md`) and leaves fresh
empty `images/`/`results/` directories and an empty `rubric.md` behind,
ready for the next quiz's rubric to be written into. Refuses to run if
`archive_<name>/` already exists, so it never silently overwrites a
previous archive. Only do this when the user asks to archive/finish up a
quiz, not as part of routine grading — it's a project-reorganizing step,
not a grading step. `rosters/` is deliberately left out of this move —
rosters track students, not individual quizzes, so they stay in place
across every archive.

## Scaling to a full class (many students, one session)

The image sizing in `extract_images.py` is deliberately tuned (~1400px
long edge ≈ 2000 image tokens each) so grading ~80 quizzes fits comfortably
in one session's token budget. If you're about to grade a large batch,
extract all images first (one parallelized pass), fix orientation for all
of them, *then* grade — don't interleave extraction and grading one file
at a time.
