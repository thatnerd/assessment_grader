#!/usr/bin/env python3
"""List images (or, with --pages, groups of images) that don't have a
graded entry in results/grades.json yet — i.e. what still needs grading.
Useful after dropping in one or more new photos (or if a few got missed in
an earlier pass).

Usage:
    python3 script/pending_images.py [--images-dir images] [--data results/grades.json] [--porcelain]
    python3 script/pending_images.py --pages 3 [--images-dir images] [--data results/grades.json] [--porcelain]

By default (--pages 1, single-page tests) each image is its own unit, and
a student's grades.json entry has a "file" key, matched 1:1.

With --pages N > 1 (multi-page tests — one student's test spans N
consecutive photos), images are grouped N at a time in sorted-filename
order; a group counts as pending unless EVERY file in it already appears
in some student's "files" list in grades.json. A group whose filenames
aren't actually numerically consecutive (e.g. a page got skipped, or two
students' photos got interleaved) is flagged with a warning rather than
silently grouped — check those by hand. A leftover partial group at the
end (image count not a multiple of N) is also flagged, not silently
dropped or silently padded.

Exit status: 0 always (this is an informational tool, not a check/gate);
use --porcelain for a script-friendly list: one pending unit per line,
filenames comma-separated for a multi-page group (empty output means
nothing is pending).
"""
import argparse
import json
import re
import sys
from pathlib import Path

RAW_EXTS = {".heic", ".heif"}
TRAILING_NUM = re.compile(r"(\d+)(?=\D*$)")


def trailing_number(name: str):
    """The last run of digits in a filename stem, e.g. "IMG_3901.jpg" -> 3901.
    None if the name has no digits to anchor a sequence check on."""
    m = TRAILING_NUM.search(Path(name).stem)
    return int(m.group(1)) if m else None


def graded_files(data_path: Path):
    if not data_path.is_file():
        return set()
    data = json.loads(data_path.read_text())
    out = set()
    for s in data.get("students", []):
        if "files" in s:
            out.update(s["files"])
        elif s.get("file"):
            out.add(s["file"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images-dir", default="images", help="Directory of quiz images (default: images)")
    ap.add_argument("--data", default="results/grades.json", help="Grading JSON to check against (default: results/grades.json)")
    ap.add_argument("--pages", type=int, default=1, help="Pages per student/test; group N sequential images together (default: 1)")
    ap.add_argument("--porcelain", action="store_true", help="Print only pending units, one per line (comma-separated filenames for a group)")
    args = ap.parse_args()

    if args.pages < 1:
        sys.exit("--pages must be at least 1")

    images_dir = Path(args.images_dir)
    if not images_dir.is_dir():
        sys.exit(f"no such directory: {images_dir}")

    done = graded_files(Path(args.data))

    all_files = sorted(p for p in images_dir.iterdir() if p.is_file())
    raw_pending = [p.name for p in all_files if p.suffix.lower() in RAW_EXTS]
    image_names = [p.name for p in all_files if p.suffix.lower() not in RAW_EXTS]

    if args.pages == 1:
        groups = [[name] for name in image_names]
    else:
        groups = [image_names[i:i + args.pages] for i in range(0, len(image_names), args.pages)]

    pending, partial_mismatch, bad_sequence, incomplete = [], [], [], []
    for group in groups:
        graded_count = sum(1 for name in group if name in done)
        if graded_count == len(group):
            continue  # fully graded already
        if graded_count > 0:
            partial_mismatch.append(group)
            continue
        if args.pages > 1 and len(group) != args.pages:
            incomplete.append(group)
            # still reported as pending below — just also flagged
        if args.pages > 1:
            nums = [trailing_number(n) for n in group]
            if all(n is not None for n in nums) and nums != list(range(nums[0], nums[0] + len(nums))):
                bad_sequence.append(group)
        pending.append(group)

    if args.porcelain:
        for group in pending:
            print(", ".join(group))
        return

    if raw_pending:
        print(f"{len(raw_pending)} raw file(s) not yet extracted (run extract_images.py first):")
        for name in raw_pending:
            print(f"  {name}")
        print()

    if partial_mismatch:
        print(f"⚠ {len(partial_mismatch)} group(s) are PARTIALLY graded (some but not all pages found in {args.data}) — check by hand:")
        for group in partial_mismatch:
            graded = [n for n in group if n in done]
            print(f"  {', '.join(group)}  (already graded: {', '.join(graded)})")
        print()

    if not pending:
        unit = "image" if args.pages == 1 else f"group of {args.pages}"
        print(f"Nothing pending — every {unit} in {images_dir} has a graded entry in {args.data}.")
        return

    unit = "image(s)" if args.pages == 1 else "group(s)"
    print(f"{len(pending)} {unit} in {images_dir} not yet graded in {args.data}:")
    for group in pending:
        flags = []
        if group in incomplete:
            flags.append(f"⚠ incomplete — expected {args.pages} pages, got {len(group)}")
        if group in bad_sequence:
            flags.append("⚠ filenames aren't numerically consecutive — check these aren't mixed up")
        flag_str = f"  {' | '.join(flags)}" if flags else ""
        print(f"  {', '.join(group)}{flag_str}")


if __name__ == "__main__":
    main()
