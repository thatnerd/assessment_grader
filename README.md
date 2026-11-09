# Quiz grading setup

Grade a stack of photographed quiz pages against `rubric.md` and get back a
printable PDF: one compact, cut-and-staple strip per student showing what
they got right and wrong, ready to cut apart and staple to each quiz.

## Directory layout

- `rubric.md` — the grading rubric. Edit this for each new quiz/assignment.
- `assessment/` — the quiz itself (not student work). Drop the quiz and/or
  its answer key into `assessment/source/` in whatever form you have — PDF,
  Markdown, a text file, a photo, or a zip of several — and one command
  converts it into readable Markdown plus a picture of every page. See
  "Uploading the quiz itself" below.
- `images/` — put one photo per student here (any filename). `.HEIC` photos
  straight off an iPhone are fine.
- `results/grades.json` — the structured grading data (one entry per
  student). This is the source of truth; the PDF is generated from it.
- `results/grades.pdf` — the printable output. Starts with a class
  statistics box (mean, median, mode, standard deviation), computed fresh
  from `grades.json` every time it's rendered.
- `rosters/` — one `.json` file per class, listing that class's student
  names. Optional, but once it exists for a class, Claude uses it to keep
  a student's name spelled the same way every quiz, even when the
  handwriting varies — see "Class rosters" below. Not touched by
  archiving, since rosters track students across quizzes, not one quiz.
- `script/` — the automation described below.

## Typical workflow

1. **Upload the quiz itself (optional, once per quiz).** Put the quiz —
   and its answer key, if you have one — into `assessment/source/`, then
   run `python3 script/extract_assessment.py`. Claude then grades against
   what the quiz actually says rather than reconstructing it from
   students' handwriting. Worth doing if your quiz has several forms; see
   "Uploading the quiz itself" below.

2. **Take a photo of each student's quiz** and drop it in `images/`.
   Any orientation is fine at this point — that gets sorted out below.

3. **Ask Claude Code to grade the batch.** In this project directory, run:
   ```
   claude
   ```
   and say something like *"grade the new quizzes in images/ against
   rubric.md."* Claude will convert the photos, check orientation, grade
   each one against the rubric, and produce `results/grades.pdf`.

   You generally don't need to run the scripts yourself — Claude runs them
   as part of grading. The rest of this section is for when you want to
   run a step by hand (e.g. to sanity-check images before asking Claude to
   grade, or to fix one image's rotation yourself).

4. **Open `results/grades.pdf`, print it, cut along the dashed lines, and
   staple each strip to the matching student's quiz.**

5. **Missed a few, or a late student turns theirs in?** Just drop the extra
   photo(s) into `images/` — one or a dozen, doesn't matter — and ask
   Claude again. It only grades what's new and adds it to the same
   `results/grades.pdf`; it won't re-grade or duplicate anyone already in
   there.

6. **Multi-page test?** If each student's test is several photos (e.g. a
   3-page packet) instead of one, just say so — *"grade this, it's a
   3-page test"* — and Claude will group the photos N at a time instead of
   treating every photo as a different student.

## Uploading the quiz itself

Put the quiz in `assessment/source/` — a PDF, a Markdown or text file, a
photo, or a `.zip` containing any of those — and run:
```
python3 script/extract_assessment.py
```
You get one Markdown file per document in `assessment/`, plus a picture of
every page under `assessment/pages/`. Both you and Claude can read the
result; nothing in there is committed to git.

A few things worth knowing:

- **Several versions of the same test are handled.** If your forms are
  labelled (e.g. `FORM 202610271` in the corner), each is converted
  separately and paired with its answer key, and Claude grades each
  student against the form they actually sat. This matters: different
  forms usually have different numbers, so grading everyone against one
  answer key marks correct papers wrong.
- **Figures are preserved as page images, not text.** Triangles and graphs
  are line drawings with no text behind them, so the extracted text keeps
  the labels but loses the shapes. That's why every page is also saved as
  a picture — Claude reads those for any diagram question.
- **A scanned (photographed) PDF has no text to extract.** The converter
  says so plainly and falls back to the page images, which Claude reads
  directly. A PDF exported from Word, Google Docs or similar converts
  perfectly.
- Re-running only converts what's new; add `--force` to redo everything.

## Class rosters

If you want names spelled consistently across quizzes even when the
handwriting is hard to read, add a roster for the class:
```json
{
  "class": "AP Precalculus",
  "period": "6-7",
  "students": ["Full Name", "Full Name", ...]
}
```
Save it as any filename under `rosters/`, e.g. `rosters/ap-precalc.json`.
Claude checks new batches against it automatically: names that closely
match a roster entry get that entry's spelling, and names that don't
closely match anything get flagged in the summary so you can confirm
whether to add them (a new student, or just a name Claude should learn).
You don't have to create a roster up front — Claude will offer to start
one from a batch's names if a class doesn't have one yet.

## Making sure images are oriented correctly

This is the one step worth understanding, because it can't be fully
automated: **photo orientation metadata on these scans can't be trusted**,
and neither can automatic OCR-based rotation detection — both were tested
and found unreliable on handwritten quiz pages (confirmed wrong, confident,
on images whose correct orientation was already known). So every image
gets a quick human/Claude visual check before grading.

If you want to check this yourself before handing off to Claude:

- Open each file in `images/` (Preview, Finder's quick look, etc.).
- If a page is sideways or upside down, fix it in place:
  ```
  python3 script/rotate_image.py images/IMG_1234.jpg 90
  ```
  The number is how many degrees to rotate **clockwise** to make it
  right-side up — try 90, 180, or 270 and re-open the file to check.

Claude does this same check as part of grading, so you don't have to do it
yourself — but if you notice a sideways page in the final PDF, this is the
command to fix it before re-running the grading step for that student.

## Running the scripts by hand

Everything here also happens automatically when Claude grades a batch;
these are for manual use if you want it.

**Convert new photos to small, upright-orientation-checked JPEGs and
delete the raw originals:**
```
python3 script/extract_images.py
```
Converts any `.HEIC`/`.HEIF` file (and any oversized `.png`/`.jpg`) in
`images/` to a compact `.jpg`, then deletes the original. Runs in
parallel; add `--parallize 4` to use fewer workers on a slower machine, or
`--parallize 16` on a faster one (default: 8). Safe to re-run.

**Rotate one image:**
```
python3 script/rotate_image.py images/IMG_1234.jpg <90|180|270>
```

**Zoom into part of an image** (useful if you're eyeballing a student's
work yourself and the handwriting is small):
```
python3 script/crop.py images/IMG_1234.jpg 0 0.1 0.6 0.4 /tmp/zoom.jpg
```
The four numbers are the crop box as fractions of the image (left, top,
right, bottom), so `0 0.1 0.6 0.4` means "the left 60% of the width,
between 10% and 40% down the page."

**Convert an uploaded quiz/answer key** into Markdown + page images:
```
python3 script/extract_assessment.py
```

**Check what's still ungraded** (e.g. after adding more photos):
```
python3 script/pending_images.py
```
Lists images in `images/` that don't have an entry in `results/grades.json`
yet. For a multi-page test, add `--pages N` so it groups photos N at a time
(in filename order) instead of treating each one as a separate student —
it warns (without hiding) if a group looks incomplete or the filenames
aren't actually consecutive, in case photos got mixed up between students.

**Re-render the PDF** after `results/grades.json` changes:
```
python3 script/build_pdf.py
```

**Merge new grading results into `results/grades.json`** (this is what
Claude uses internally to add newly-graded students without touching
existing ones — not something you'd normally run by hand, but here for
reference):
```
python3 script/append_grades.py new_students.json
```

**Archive a finished quiz** (once you're done with it, to make room for the
next one):
```
python3 script/archive_quiz.py <name>
```
Moves `images/`, `results/`, `assessment/`, and `rubric.md` into
`archive_<name>/`, and leaves empty `images/`/`results/`/`assessment/`
directories and an empty `rubric.md` behind so you can start the next quiz
right away. Refuses to run if
`archive_<name>/` already exists (pick a different name rather than risk
overwriting an old archive). Add
`--dry-run` to preview what would move without moving anything.

## First-time setup

The scripts need a few Python packages:
```
pip install -r script/requirements.txt
```
(`Pillow`, `pillow-heif` for reading iPhone photos, and `weasyprint` for
producing the PDF.)

Converting an uploaded **PDF** quiz also needs poppler, which pip can't
install:
```
brew install poppler          # macOS
sudo apt install poppler-utils  # Debian/Ubuntu
```
Everything else works without it.
