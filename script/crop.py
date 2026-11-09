#!/usr/bin/env python3
"""Crop and upscale a region of an image so cramped handwriting is easier
to read while grading.

Usage:
    python3 script/crop.py images/IMG_1234.jpg 0.0 0.1 0.6 0.4 out.jpg [--scale 2.5]

x0 y0 x1 y1 are fractions (0-1) of the image width/height, top-left origin.
"""
import argparse
from pathlib import Path

from PIL import Image


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="Source image")
    ap.add_argument("x0", type=float)
    ap.add_argument("y0", type=float)
    ap.add_argument("x1", type=float)
    ap.add_argument("y1", type=float)
    ap.add_argument("out", help="Output path for the cropped/upscaled image")
    ap.add_argument("--scale", type=float, default=2.5, help="Upscale factor (default: 2.5)")
    args = ap.parse_args()

    im = Image.open(args.path).convert("RGB")
    w, h = im.size
    box = (
        int(w * args.x0), int(h * args.y0),
        int(w * args.x1), int(h * args.y1),
    )
    crop = im.crop(box)
    crop = crop.resize((max(1, int(crop.width * args.scale)), max(1, int(crop.height * args.scale))), Image.LANCZOS)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out, quality=95)
    print(f"{out} ({crop.width}x{crop.height})")


if __name__ == "__main__":
    main()
