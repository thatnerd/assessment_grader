#!/usr/bin/env python3
"""Fuzzy-match and maintain class rosters in rosters/*.json.

Rosters are a durable, cross-quiz resource (not touched by archive_quiz.py)
used to canonicalize student name spellings, since the same student's name
is often transcribed differently quiz to quiz from messy handwriting. This
script does the mechanical fuzzy-matching; the judgment calls (is this
really the same student? should we add a new name?) stay with whoever's
grading — see CLAUDE.md's "Class rosters" section for that workflow.

Roster file schema (one file per class):
{
  "class": "AP Precalculus",
  "period": "6-7",
  "students": ["Full Name", "Full Name", ...]
}

Subcommands:

  list
      Show every roster file with its class, period, and student count.
      python3 script/roster.py list

  match <name> [<name> ...]
      Compare a list of (best-effort transcribed) names against every
      roster and report, per roster, how many of those names have a
      close fuzzy match in it — this is how you find which class a new
      batch of images belongs to (the roster with the highest match
      count). For the single best-matching roster, also prints each
      input name's best match in that roster (or "no match") so you can
      decide name-by-name whether to accept the roster spelling.
      python3 script/roster.py match "Thariem Coston" "Fuheem Austin"

  add <name> --roster <path> [--class "..."] [--period "..."]
      Append a name to a roster, creating the file (with --class
      required, --period optional) if it doesn't exist yet. Skips
      silently if the exact name is already present; does NOT fuzzy-check
      for near-duplicates — that judgment call happens before you call
      this, during `match`.
      python3 script/roster.py add "New Student" --roster rosters/ap-precalc-period-6-7.json
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

CLOSE_CUTOFF = 0.6  # difflib similarity ratio; see CLAUDE.md for how to use this


def load_rosters(rosters_dir: Path):
    rosters = []
    if not rosters_dir.is_dir():
        return rosters
    for p in sorted(rosters_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"  (skipping {p}: {e})", file=sys.stderr)
            continue
        data["_path"] = p
        rosters.append(data)
    return rosters


def cmd_list(args):
    rosters = load_rosters(Path(args.rosters_dir))
    if not rosters:
        print(f"No roster files found in {args.rosters_dir}/")
        return
    for r in rosters:
        cls = r.get("class", "?")
        period = r.get("period", "")
        n = len(r.get("students", []))
        period_str = f" (period {period})" if period else ""
        print(f"{r['_path']}: {cls}{period_str} — {n} student(s)")


def cmd_match(args):
    rosters = load_rosters(Path(args.rosters_dir))
    if not rosters:
        print(f"No roster files found in {args.rosters_dir}/ — nothing to match against.")
        return

    names = args.names
    scored = []
    for r in rosters:
        students = r.get("students", [])
        match_count = 0
        for name in names:
            if difflib.get_close_matches(name, students, n=1, cutoff=CLOSE_CUTOFF):
                match_count += 1
        scored.append((match_count, r))

    scored.sort(key=lambda t: t[0], reverse=True)

    print(f"Roster match scores for {len(names)} name(s):")
    for count, r in scored:
        cls = r.get("class", "?")
        period = r.get("period", "")
        period_str = f" (period {period})" if period else ""
        print(f"  {count}/{len(names)}  {r['_path']}  —  {cls}{period_str}")

    best_count, best = scored[0]
    if best_count == 0:
        print("\nNo roster matched any name — likely a new class, or no roster exists for it yet.")
        return

    print(f"\nBest match: {best['_path']} — per-name detail:")
    students = best.get("students", [])
    for name in names:
        matches = difflib.get_close_matches(name, students, n=1, cutoff=CLOSE_CUTOFF)
        if matches:
            ratio = difflib.SequenceMatcher(None, name, matches[0]).ratio()
            print(f'  "{name}" -> "{matches[0]}" (similarity {ratio:.2f})')
        else:
            print(f'  "{name}" -> no match (possibly a new/unlisted student)')


def cmd_add(args):
    roster_path = Path(args.roster)
    if roster_path.is_file():
        data = json.loads(roster_path.read_text())
    else:
        if not args.cls:
            sys.exit(f"{roster_path} doesn't exist yet — pass --class to create it")
        data = {"class": args.cls, "period": args.period or "", "students": []}

    if args.name in data.get("students", []):
        print(f"{args.name!r} is already in {roster_path}")
        return

    data.setdefault("students", []).append(args.name)
    roster_path.parent.mkdir(parents=True, exist_ok=True)
    roster_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Added {args.name!r} to {roster_path} ({len(data['students'])} student(s) total)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rosters-dir", default="rosters", help="Directory of roster JSON files (default: rosters)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all rosters")

    p_match = sub.add_parser("match", help="Fuzzy-match names against all rosters")
    p_match.add_argument("names", nargs="+", help="Names to match (quote each one)")

    p_add = sub.add_parser("add", help="Add a name to a roster, creating it if needed")
    p_add.add_argument("name", help="Full student name to add")
    p_add.add_argument("--roster", required=True, help="Path to the roster JSON file")
    p_add.add_argument("--class", dest="cls", help="Class name (required if creating a new roster)")
    p_add.add_argument("--period", default="", help="Period (optional)")

    args = ap.parse_args()
    {"list": cmd_list, "match": cmd_match, "add": cmd_add}[args.cmd](args)


if __name__ == "__main__":
    main()
