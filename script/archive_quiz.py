#!/usr/bin/env python3
"""Archive a finished quiz: move images/, results/, and rubric.md into
archive_<name>/, then leave fresh empty images/ and results/ directories
and an empty rubric.md behind so the project is ready for the next quiz.

Usage:
    python3 script/archive_quiz.py <name> [--dry-run]

Example:
    python3 script/archive_quiz.py degrees-radians
    -> archive_degrees-radians/images/...
       archive_degrees-radians/results/...
       archive_degrees-radians/rubric.md

Refuses to run if archive_<name>/ already exists, to avoid overwriting or
merging into a previous archive — pass a different name, or move/remove
the existing one first.
"""
import argparse
import shutil
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="Name for this quiz; archive goes to archive_<name>/")
    ap.add_argument("--dest-root", default=".", help="Where to create archive_<name>/ (default: current directory)")
    ap.add_argument("--images-dir", default="images", help="Source images directory (default: images)")
    ap.add_argument("--results-dir", default="results", help="Source results directory (default: results)")
    ap.add_argument("--rubric", default="rubric.md", help="Source rubric file (default: rubric.md)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would move without moving anything")
    args = ap.parse_args()

    images_dir = Path(args.images_dir)
    results_dir = Path(args.results_dir)
    rubric_path = Path(args.rubric)
    archive_dir = Path(args.dest_root) / f"archive_{args.name}"

    if archive_dir.exists():
        sys.exit(f"refusing to archive: {archive_dir} already exists (pick a different name)")

    sources = []
    for label, src, is_dir in [
        ("images", images_dir, True),
        ("results", results_dir, True),
        ("rubric.md", rubric_path, False),
    ]:
        if not src.exists():
            print(f"  (skipping {label}: {src} does not exist)")
            continue
        if is_dir and not any(src.iterdir()):
            print(f"  (skipping {label}: {src} is empty)")
            continue
        sources.append((label, src, is_dir))

    if not sources:
        sys.exit("nothing to archive — images/, results/, and rubric.md are all missing or empty")

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
    images_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    if not rubric_path.exists():
        rubric_path.touch()

    print(
        f"Done. Archived to {archive_dir}/; {images_dir}/, {results_dir}/, and "
        f"an empty {rubric_path} are ready for the next quiz."
    )


if __name__ == "__main__":
    main()
