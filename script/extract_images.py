#!/usr/bin/env python3
"""Convert raw quiz photos into small, token-efficient JPEGs and delete the
raw originals.

Handles HEIC/HEIF (iPhone photos) and any oversized PNG/JPEG already in the
directory. Runs in parallel across files.

Usage:
    python3 script/extract_images.py [--dir images] [--max-edge 1400]
                                      [--quality 88] [--parallize 8]
                                      [--force]

IMPORTANT — orientation is NOT auto-corrected here:
    EXIF orientation tags on these scans have been observed to be simply
    wrong (tag says "normal" while the decoded pixels are sideways), and
    OCR-based auto-rotation (tested with `tesseract --psm 0`) was also
    unreliable on this sparse handwritten content — under 50% confidence,
    and it gave a wrong answer on two images whose correct orientation was
    already known. Rather than silently mis-rotate a scan, this script
    leaves that to a human/agent with vision: after running it, look at
    each new file in --dir and fix any that are sideways/upside-down with
    rotate_image.py (see that script's docstring).
"""
import argparse
import multiprocessing as mp
import sys
from pathlib import Path

from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()

RAW_EXTS = {".heic", ".heif", ".png", ".tif", ".tiff", ".bmp", ".webp"}
JPEG_EXTS = {".jpg", ".jpeg"}


def process_one(job):
    path_str, max_edge, quality = job
    path = Path(path_str)
    out_path = path.with_suffix(".jpg")
    try:
        im = Image.open(path)
        im = ImageOps.exif_transpose(im)  # best-effort; a no-op when the
        im = im.convert("RGB")            # tag is missing or wrong

        w, h = im.size
        scale = max_edge / max(w, h)
        if scale < 1:
            im = im.resize(
                (max(1, round(w * scale)), max(1, round(h * scale))),
                Image.LANCZOS,
            )
        im.save(out_path, "JPEG", quality=quality)

        if out_path != path:
            path.unlink()

        w2, h2 = im.size
        flag = "  ⚠ landscape aspect — verify orientation" if w2 > h2 else ""
        return (path.name, f"-> {out_path.name} ({w2}x{h2}){flag}", None)
    except Exception as e:  # noqa: BLE001 - report and keep going
        return (path.name, None, str(e))


def find_targets(root: Path, max_edge: int, force: bool):
    targets = []
    for p in sorted(root.iterdir()):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in RAW_EXTS:
            targets.append(p)
        elif ext in JPEG_EXTS:
            if force:
                targets.append(p)
                continue
            try:
                with Image.open(p) as im:
                    if max(im.size) > max_edge:
                        targets.append(p)
            except Exception:
                pass
    return targets


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dir", default="images", help="Directory of quiz images (default: images)")
    ap.add_argument("--max-edge", type=int, default=1400, help="Longest edge in pixels (default: 1400)")
    ap.add_argument("--quality", type=int, default=88, help="JPEG quality (default: 88)")
    ap.add_argument("--parallize", type=int, default=8, help="Worker processes (default: 8)")
    ap.add_argument("--force", action="store_true", help="Reprocess existing .jpg files even if already small enough")
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.is_dir():
        sys.exit(f"no such directory: {root}")

    targets = find_targets(root, args.max_edge, args.force)
    if not targets:
        print(f"Nothing to do — no raw or oversized images found in {root}")
        return

    print(f"Processing {len(targets)} image(s) with {args.parallize} worker(s)...")
    jobs = [(str(p), args.max_edge, args.quality) for p in targets]

    errors = []
    with mp.Pool(processes=max(1, args.parallize)) as pool:
        for name, status, err in pool.imap_unordered(process_one, jobs):
            if err:
                print(f"  {name}: ERROR: {err}")
                errors.append(name)
            else:
                print(f"  {name}: {status}")

    print("Done." if not errors else f"Done, with {len(errors)} error(s): {', '.join(errors)}")
    print(
        "\nNext: view each new/changed file in", root,
        "and fix orientation with rotate_image.py before grading — see that script's docstring."
    )


if __name__ == "__main__":
    main()
