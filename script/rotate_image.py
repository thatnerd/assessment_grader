#!/usr/bin/env python3
"""Rotate a single image file in place (used to fix orientation after
extract_images.py — see that script's docstring for why this is a manual,
vision-driven step rather than an automatic one).

Usage:
    python3 script/rotate_image.py images/IMG_1234.jpg 90

The degree argument is the CLOCKWISE rotation needed to make the image
right-side up (i.e. "this image needs to turn 90 degrees clockwise" ->
pass 90). Any integer is accepted but 90/180/270 are the practical cases.
Overwrites the file in place and strips any EXIF (there shouldn't be any
left after extract_images.py, but this keeps the file clean regardless).
"""
import argparse
import sys
from pathlib import Path

from PIL import Image


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="Image file to rotate in place")
    ap.add_argument("degrees", type=int, help="Clockwise rotation in degrees (e.g. 90, 180, 270)")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.is_file():
        sys.exit(f"no such file: {path}")

    im = Image.open(path).convert("RGB")
    im = im.rotate(-args.degrees, expand=True)  # PIL rotate() is counter-clockwise
    im.save(path, quality=90)
    print(f"{path}: rotated {args.degrees}° clockwise -> {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
