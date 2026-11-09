#!/usr/bin/env python3
"""Convert an uploaded assessment (the quiz itself, and/or its answer key)
into one standard, human- and Claude-readable Markdown file per document,
plus a rendered image per page.

This is the *source document* pipeline, not the student-work pipeline:
  script/extract_images.py     -> student photos in images/
  script/extract_assessment.py -> the blank quiz / answer key in assessment/

Usage:
    python3 script/extract_assessment.py [--dir assessment] [--dpi 150]
                                         [--max-edge 1400] [--force]
                                         [--porcelain]

Layout it reads and writes (all under --dir, default `assessment/`):

    assessment/
      source/                      <- put uploads here (pdf, md, txt, image, zip)
      form-202610271.md            <- one Markdown file per converted document
      key-202610271.md
      pages/
        form-202610271/page-1.jpg  <- one render per page

Why Markdown + page images, rather than text alone: a math assessment's
figures are usually vector line art with no text layer at all (observed on
a real upload: `pdfimages -list` reports no rasters, yet Q6 draws four
labeled triangles). Text extraction keeps the side *labels* but loses which
segment connects where, so it cannot be graded from text alone. Each page's
extracted text is therefore written next to a link to that page's render:
the Markdown is faithful and diffable, and the figure is one click away for
a human or one view away for an agent.

Extracted text goes inside a fenced block on purpose. `pdftotext -layout`
encodes the page's visual structure in whitespace (answer blanks, two-column
"(a) ... (b) ..." rows, the triangle labels); rendering it as Markdown prose
would collapse that alignment and lose information.

Conversion tiers, chosen per file automatically:
  *.zip                  unpacked into source/<name>/, then each member is
                         classified below (the .zip itself is left in place)
  *.pdf with text layer  pdftotext -layout, split per page  (fast, lossless)
  *.pdf without one      pages rendered only; marked for transcription
  *.md / *.txt           copied in under a provenance header
  images / *.heic        downscaled into pages/; marked for transcription

PDF handling uses poppler (`pdftotext`, `pdftoppm`, `pdfinfo`) rather than a
Python PDF library: those binaries are already a system dependency on most
machines, which keeps this script free of any new pip requirement. Install
with `brew install poppler` (macOS) or `apt install poppler-utils`.

Known limitation: each image file becomes its own one-page document, so a
multi-page quiz uploaded as N separate photos produces N stubs. Merge them
by hand (or upload a PDF) if that matters.

Refuses to overwrite an existing converted file unless --force is passed, so
re-running after adding one more upload only converts what's new.
"""
import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

PDF_EXTS = {".pdf"}
TEXT_EXTS = {".md", ".txt", ".markdown"}
IMAGE_EXTS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
ZIP_EXTS = {".zip"}

# "FORM\n 202610271" (page corner) and "Form 202610271" (title line) both occur.
FORM_RE = re.compile(r"\bFORMS?\b\s*[:#]?\s*(\d{4,})", re.IGNORECASE)
ANSWER_KEY_NAME_RE = re.compile(r"answer|key", re.IGNORECASE)
ANSWER_KEY_TEXT_RE = re.compile(r"answer\s*key", re.IGNORECASE)

# Below this many characters of extracted text per page, treat the PDF as
# scanned (no usable text layer) and fall back to transcription.
MIN_CHARS_PER_PAGE = 50


def have(binary):
    return shutil.which(binary) is not None


def run(cmd):
    """Run a command, returning stdout. Exits with a clear message if the
    binary is missing or the call fails."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit(
            f"missing required tool: {cmd[0]!r}. Install poppler "
            "(`brew install poppler`, or `apt install poppler-utils`)."
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"{' '.join(cmd[:2])} failed: {e.stderr.strip() or e}")
    return proc.stdout


def slug(text):
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return out or "document"


def pdf_page_count(path: Path):
    for line in run(["pdfinfo", str(path)]).splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return 0


def pdf_pages_text(path: Path):
    """Extracted text, one entry per page. `pdftotext` separates pages with a
    form feed."""
    raw = run(["pdftotext", "-layout", str(path), "-"])
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return [p.rstrip() for p in pages]


def render_pdf_pages(path: Path, out_dir: Path, dpi: int):
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("page*.jpg"):
        stale.unlink()
    run(["pdftoppm", "-jpeg", "-r", str(dpi), str(path), str(out_dir / "page")])
    return sorted(out_dir.glob("page*.jpg"))


def render_image_page(path: Path, out_dir: Path, max_edge: int):
    """Downscale a photographed/scanned page into out_dir as page-1.jpg."""
    try:
        from PIL import Image, ImageOps
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
    except ImportError:
        sys.exit(
            "converting an image upload needs Pillow: "
            "pip install -r script/requirements.txt"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    im = im.convert("RGB")
    w, h = im.size
    scale = max_edge / max(w, h)
    if scale < 1:
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    out = out_dir / "page-1.jpg"
    im.save(out, "JPEG", quality=88)
    return [out]


def classify(path: Path, text: str):
    """Return (doc_kind, form_id or None) for a source document."""
    head = text[:400]
    is_key = bool(ANSWER_KEY_NAME_RE.search(path.name)) or bool(ANSWER_KEY_TEXT_RE.search(head))
    m = FORM_RE.search(text)
    return ("key" if is_key else "form"), (m.group(1) if m else None)


def printed_title(pages_text):
    """The first substantial line of extracted text, reported as-is. Used for
    orientation only — never as a substitute for reading the document."""
    for page in pages_text:
        for line in page.splitlines():
            line = line.strip()
            if len(line) >= 20 and re.search(r"[A-Za-z]", line) and not line.startswith("Name:"):
                return line
    return None


def build_markdown(*, out_stem, doc_kind, form_id, source_rel, pages_text,
                   page_images, page_count, text_layer, title):
    kind_label = "Answer key" if doc_kind == "key" else "Quiz form"
    heading = f"{kind_label}" + (f" — Form {form_id}" if form_id else f" — {out_stem}")

    lines = [
        f"<!-- Converted by script/extract_assessment.py on {date.today().isoformat()}",
        f"     from {source_rel}",
        "     Regenerate with: python3 script/extract_assessment.py --force",
        "     Do not hand-edit; edits are lost on the next conversion. -->",
        "",
        f"# {heading}",
        "",
        f"- **Document type:** {kind_label.lower()}",
        f"- **Form:** {form_id or 'not detected — check the printed page'}",
        f"- **Pages:** {page_count}",
        f"- **Source:** `{source_rel}`",
    ]
    if title:
        lines.append(f"- **Printed title:** {title}")
    lines.append(
        "- **Text layer:** "
        + ("yes (`pdftotext -layout`)" if text_layer else "**none — needs transcription**")
    )
    lines += ["", "> Figures (triangles, graphs, number lines) are usually vector line art",
              "> with no text layer, so they do **not** survive text extraction — the",
              "> side labels come through but the geometry does not. Read the page image",
              "> under each heading for anything figure-shaped, and use",
              "> `script/crop.py` to zoom in.", ""]

    if not text_layer:
        lines += [
            "**No text could be extracted from this document.** The page images below",
            "are the only usable content: transcribe them before grading against this",
            "assessment, or replace the upload with a text-based PDF.",
            "",
        ]

    for i in range(page_count):
        lines.append(f"## Page {i + 1}")
        lines.append("")
        if i < len(page_images):
            rel = page_images[i]
            lines += [f"![{heading}, page {i + 1}]({rel})", ""]
        page_text = pages_text[i] if i < len(pages_text) else ""
        if page_text.strip():
            lines += ["```text", page_text, "```", ""]
        elif text_layer:
            lines += ["_(no text on this page — see the image above)_", ""]

    return "\n".join(lines).rstrip() + "\n"


def unpack_zips(source_dir: Path, porcelain: bool):
    """Unpack any .zip in source/ into source/<stem>/, leaving the zip itself
    in place as the record of what was uploaded."""
    for zip_path in sorted(source_dir.glob("*.zip")):
        dest = source_dir / zip_path.stem
        if dest.exists():
            if not porcelain:
                print(f"  {zip_path.name}: already unpacked -> source/{dest.name}/")
            continue
        try:
            with zipfile.ZipFile(zip_path) as zf:
                safe = [
                    m for m in zf.namelist()
                    if not m.endswith("/") and not m.startswith("/")
                    and ".." not in Path(m).parts
                ]
                # Most uploads wrap everything in one top-level folder; keeping
                # it would give source/<stem>/<stem>/..., so strip it.
                roots = {Path(m).parts[0] for m in safe}
                strip_root = len(roots) == 1 and all(len(Path(m).parts) > 1 for m in safe)
                for member in safe:
                    rel = Path(*Path(member).parts[1:]) if strip_root else Path(member)
                    target = dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as fh, open(target, "wb") as out:
                        shutil.copyfileobj(fh, out)
        except zipfile.BadZipFile as e:
            print(f"  {zip_path.name}: ERROR: not a readable zip ({e})")
            continue
        if not porcelain:
            print(f"  {zip_path.name}: unpacked -> source/{dest.name}/")


def find_documents(source_dir: Path):
    """Every convertible file under source/, recursively, in sorted order."""
    docs = []
    for p in sorted(source_dir.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        ext = p.suffix.lower()
        if ext in PDF_EXTS | TEXT_EXTS | IMAGE_EXTS:
            docs.append(p)
        elif ext not in ZIP_EXTS:
            continue
    return docs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="assessment", help="Assessment directory (default: assessment)")
    ap.add_argument("--dpi", type=int, default=150, help="Page render resolution for PDFs (default: 150)")
    ap.add_argument("--max-edge", type=int, default=1400, help="Longest edge for image uploads (default: 1400)")
    ap.add_argument("--force", action="store_true", help="Reconvert documents whose .md already exists")
    ap.add_argument("--porcelain", action="store_true", help="Print one converted path per line, nothing else")
    args = ap.parse_args()

    root = Path(args.dir)
    source_dir = root / "source"
    if not source_dir.is_dir():
        sys.exit(
            f"no such directory: {source_dir}\n"
            f"Create it and put the uploaded quiz/answer key there:\n"
            f"  mkdir -p {source_dir} && mv <upload> {source_dir}/"
        )

    if not args.porcelain:
        print(f"Reading uploads from {source_dir}/")
    unpack_zips(source_dir, args.porcelain)

    docs = find_documents(source_dir)
    if not docs:
        sys.exit(f"nothing convertible found in {source_dir} (looked for pdf, md, txt, images, zip)")

    pages_root = root / "pages"
    written, skipped, needs_transcription, forms = [], [], [], {}
    form_page_counts = set()

    for src in docs:
        ext = src.suffix.lower()
        source_rel = src.relative_to(root).as_posix()

        if ext in PDF_EXTS:
            page_count = pdf_page_count(src)
            pages_text = pdf_pages_text(src)
            chars = sum(len(p.strip()) for p in pages_text)
            text_layer = page_count > 0 and chars >= MIN_CHARS_PER_PAGE * page_count
            if not text_layer:
                pages_text = []
        elif ext in TEXT_EXTS:
            page_count, pages_text, text_layer = 1, [src.read_text(errors="replace").rstrip()], True
        elif ext in IMAGE_EXTS:
            page_count, pages_text, text_layer = 1, [], False
        else:
            continue

        doc_kind, form_id = classify(src, "\n".join(pages_text))
        out_stem = f"{doc_kind}-{form_id}" if form_id else slug(src.stem)
        out_path = root / f"{out_stem}.md"

        if out_path.exists() and not args.force:
            skipped.append(out_path)
            continue

        page_dir = pages_root / out_stem
        if ext in PDF_EXTS:
            imgs = render_pdf_pages(src, page_dir, args.dpi)
        elif ext in IMAGE_EXTS:
            imgs = render_image_page(src, page_dir, args.max_edge)
        else:
            imgs = []
        page_count = max(page_count, len(imgs))
        rel_imgs = [p.relative_to(root).as_posix() for p in imgs]

        out_path.write_text(build_markdown(
            out_stem=out_stem, doc_kind=doc_kind, form_id=form_id,
            source_rel=source_rel, pages_text=pages_text, page_images=rel_imgs,
            page_count=page_count, text_layer=text_layer,
            title=printed_title(pages_text),
        ))
        written.append(out_path)
        if doc_kind == "form":
            form_page_counts.add(page_count)
        if not text_layer:
            needs_transcription.append(out_path)
        if form_id:
            forms.setdefault(form_id, {})[doc_kind] = out_path
        if not args.porcelain:
            flag = "" if text_layer else "  ⚠ no text layer — needs transcription"
            print(f"  {source_rel} -> {out_path.name} ({page_count} page(s)){flag}")

    if args.porcelain:
        for p in written:
            print(p)
        return

    if skipped:
        print(f"\nSkipped {len(skipped)} already-converted document(s) (pass --force to redo): "
              f"{', '.join(p.name for p in skipped)}")

    print(f"\nConverted {len(written)} document(s) into {root}/")
    if forms:
        print(f"\nForms detected: {len(forms)}")
        for form_id in sorted(forms):
            parts = forms[form_id]
            have_both = "form" in parts and "key" in parts
            missing = "" if have_both else "  ⚠ missing " + ("answer key" if "key" not in parts else "quiz form")
            print(f"  Form {form_id}: {', '.join(sorted(p.name for p in parts.values()))}{missing}")
        if len(forms) > 1:
            print(
                "\n⚠ Multiple forms: their answers differ, so each student must be graded\n"
                "  against the form printed on their own pages. See CLAUDE.md step 5."
            )
    if needs_transcription:
        print("\n⚠ No text layer (transcribe from the page images before grading): "
              f"{', '.join(p.name for p in needs_transcription)}")

    if len(form_page_counts) == 1:
        pages = form_page_counts.pop()
        if pages > 1:
            print(f"\nEach quiz form is {pages} pages — if students turn in every page, "
                  f"find pending work with:\n  python3 script/pending_images.py --pages {pages}")
    elif len(form_page_counts) > 1:
        print(f"\n⚠ Quiz forms have differing page counts ({sorted(form_page_counts)}) — "
              "pending_images.py --pages assumes one fixed length; check the grouping by hand.")
    print("\nNext: read the converted Markdown, then draft/verify the active rubric "
          "against it — write a real rubric to rubric.local.md (git-ignored), not to "
          "the tracked rubric.md template (CLAUDE.md steps 1-2).")


if __name__ == "__main__":
    main()
