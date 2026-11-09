#!/usr/bin/env python3
"""Archive a finished quiz: move images/, results/, assessment/, and both
rubric files into archive_<name>/, then leave fresh empty images/,
results/ and assessment/ directories and an empty rubric.md behind so the
project is ready for the next quiz.

rubric.local.md (the real, answer-bearing rubric, git-ignored) is archived
alongside rubric.md rather than left behind: a stale rubric sitting next to
the next quiz's assessment reads as current, and its answers belong to a
different test.

Usage:
    python3 script/archive_quiz.py <name> [--dry-run]

Example:
    python3 script/archive_quiz.py degrees-radians
    -> archive_degrees-radians/images/...
       archive_degrees-radians/results/...
       archive_degrees-radians/assessment/...
       archive_degrees-radians/rubric.md
       archive_degrees-radians/rubric.local.md

rosters/ is deliberately left alone: rosters track students across quizzes,
not one quiz. assessment/ does move, since the converted quiz and answer
keys belong to the quiz being archived.

Refuses to run if archive_<name>/ already exists, to avoid overwriting or
merging into a previous archive — pass a different name, or move/remove
the existing one first.
"""
import argparse
import shutil
import sys
from pathlib import Path

# Tracked in git so the directory survives a fresh clone; it is repo
# structure rather than quiz data, so it is recreated after archiving
# instead of being carried into the archive.
PLACEHOLDER = ".placeholder"


def is_empty(directory: Path):
    """True when a directory holds nothing but its tracked placeholder."""
    return not any(p.name != PLACEHOLDER for p in directory.iterdir())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="Name for this quiz; archive goes to archive_<name>/")
    ap.add_argument("--dest-root", default=".", help="Where to create archive_<name>/ (default: current directory)")
    ap.add_argument("--images-dir", default="images", help="Source images directory (default: images)")
    ap.add_argument("--results-dir", default="results", help="Source results directory (default: results)")
    ap.add_argument("--assessment-dir", default="assessment", help="Source assessment directory (default: assessment)")
    ap.add_argument("--rubric", default="rubric.md", help="Source rubric template (default: rubric.md)")
    ap.add_argument("--local-rubric", default="rubric.local.md",
                    help="Real, git-ignored rubric, archived too if present (default: rubric.local.md)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would move without moving anything")
    args = ap.parse_args()

    images_dir = Path(args.images_dir)
    results_dir = Path(args.results_dir)
    assessment_dir = Path(args.assessment_dir)
    rubric_path = Path(args.rubric)
    local_rubric_path = Path(args.local_rubric)
    archive_dir = Path(args.dest_root) / f"archive_{args.name}"

    if archive_dir.exists():
        sys.exit(f"refusing to archive: {archive_dir} already exists (pick a different name)")

    sources = []
    for label, src, is_dir in [
        ("images", images_dir, True),
        ("results", results_dir, True),
        ("assessment", assessment_dir, True),
        ("rubric.md", rubric_path, False),
        (local_rubric_path.name, local_rubric_path, False),
    ]:
        if not src.exists():
            print(f"  (skipping {label}: {src} does not exist)")
            continue
        if is_dir and is_empty(src):
            print(f"  (skipping {label}: {src} is empty)")
            continue
        sources.append((label, src, is_dir))

    if not sources:
        sys.exit(
            "nothing to archive — images/, results/, assessment/, and the "
            "rubric files are all missing or empty"
        )

    print(f"{'Would move' if args.dry_run else 'Moving'} into {archive_dir}/:")
    for label, src, _ in sources:
        print(f"  {src} -> {archive_dir / src.name}")

    if args.dry_run:
        return

    archive_dir.mkdir(parents=True)
    for label, src, is_dir in sources:
        shutil.move(str(src), str(archive_dir / src.name))

    # Leave fresh empty directories (and an empty rubric.md) behind so the
    # existing scripts/workflow keep working unchanged for the next quiz.
    # Each directory's .placeholder is tracked in git, so restore it here and
    # drop the copy that rode along into the archive — otherwise archiving
    # would show up as a deletion of three tracked files.
    for directory in (images_dir, results_dir, assessment_dir):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / PLACEHOLDER).touch()
        archived_placeholder = archive_dir / directory.name / PLACEHOLDER
        if archived_placeholder.exists():
            archived_placeholder.unlink()
    if not rubric_path.exists():
        rubric_path.touch()

    print(
        f"Done. Archived to {archive_dir}/; {images_dir}/, {results_dir}/, "
        f"{assessment_dir}/, and an empty {rubric_path} are ready for the next quiz."
    )


if __name__ == "__main__":
    main()
