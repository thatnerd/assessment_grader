Rubric: <Quiz Title>
====================

<!--
  GENERIC TEMPLATE — replace everything below with your real rubric before
  grading. The grader reads this file fresh every run and cross-checks it
  against the photographed quiz pages, so it must match what is actually
  printed on the quiz (same numbers, same expected answers).

  This file is committed to git as a template. Put your real, quiz-specific
  rubric (it contains answers) in `rubric.md` while grading, but do not commit
  it — keep a private copy as `rubric.local.md` (git-ignored) if you want one.
-->

Source: `<name of the printed quiz / answer key, if any>`

**Versions:** <Is there more than one version (A/B)? Where is the version
printed on the page? If there is only one version, say so and delete the
Version A / Version B splits below.>

**Pages per student:** <1 for a single-photo quiz, or N for a multi-page
packet. This is the number passed to `pending_images.py --pages N`.>

## Point totals

- **Name:** <N> points
- **Required problems:** <sum> points (Part A <x> + Part B <y> + ...)
- **Extra credit:** <z> points (excluded from the percentage denominator)
- **Required total (Name + required problems):** <N + sum> points

**Name / grade-floor arithmetic.** District policy: no student's score drops
below 53% of the required total. `Name` is graded as an ordinary criterion
(full points for any legible attempt at a name, zero only if there is no name
at all) and is sized so that a name by itself clears the floor:

    N = smallest integer with N / (N + required problem points) >= 0.53

Worked example (made-up numbers): required problems total 100 points.
N = 113 gives 113/213 = 53.05% (passes); N = 112 gives 112/212 = 52.83%
(fails). So Name = 113 and the required total is 213.

Show this arithmetic to the user and get confirmation before grading.

## Part A — <Topic> (<x> points)

**Problem 1 (<n> points)** <Problem statement, exactly as printed.>
Expected answer: **<answer>**
<Point breakdown: which steps/criteria earn which points, and what partial
credit looks like.>

**Version A** / **Version B** (only if the versions differ):
- Problem 2(a) (<n> pts): <expected answer for version A> / <for version B>
- Problem 2(b) (<n> pts): ...

## Part B — <Topic> (<y> points)

**Problem 3 (<n> points, <k> each)**
- (a) <expected answer>
- (b) <expected answer>

**Free-response problem (<n> points)** — describe what a full-credit answer
must contain, what earns partial credit, and what earns zero (blank or
off-topic).

## Extra credit (<z> points)

<Problem and expected answer. Extra credit adds to a student's total but is
never part of the percentage denominator or of the Name calculation.>

## Grading notes

- <Accepted equivalent forms (e.g. unsimplified fractions, decimals).>
- <Consistent-with-error rules: does a wrong earlier answer still earn later
  method credit?>
- <Anything else the grader should treat as policy for this quiz.>
