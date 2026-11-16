#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Surgically mark a story done in both tracking surfaces.

- Story doc: `Status: <x>` -> `Status: done`, plus a Change Log entry.
- Sprint yaml: `development_status[<key>]` -> `done`, appending
  `DONE <date>` to the story's trailing comment without touching anything else.

Prints a unified-diff-style summary so the caller can verify only the
intended lines changed.

Usage:
  python mark-done.py --story-file F --sprint-status Y --story-key K \
      --summary "what shipped"
"""
import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def edit_story(path: Path, date: str, summary: str) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    new = lines[:]
    for i, line in enumerate(new):
        if re.match(r"^Status:\s*", line):
            new[i] = "Status: done"
            break
    else:
        raise SystemExit("no Status: line in story file")

    entry = f"- {date}: Pipeline complete (cdo-code-e2e) — {summary}"
    # Append under "## Change Log" if present, else at end of file
    for i, line in enumerate(new):
        if re.match(r"^##\s+Change Log", line, re.I):
            j = len(new) - 1
            while j > i and not new[j].strip():
                j -= 1
            new.insert(j + 1, entry)
            break
    else:
        new += ["", "## Change Log", "", entry]
    return list(difflib.unified_diff(lines, new, lineterm="")), new


def edit_sprint(path: Path, key: str, date: str, summary: str) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    new = lines[:]
    pat = re.compile(rf"^(\s*){re.escape(key)}:\s*([a-z-]+)(\s*(#.*)?)$")
    for i, line in enumerate(new):
        m = pat.match(line)
        if not m:
            continue
        indent, _status, _tail, comment = m.groups()
        new[i] = f"{indent}{key}: done"
        if comment:
            new[i] += " " + comment.rstrip() + f", DONE {date} — {summary}"
        else:
            new[i] += f"  # DONE {date} — {summary}"
        # last_updated bump
        for j, l2 in enumerate(new):
            if re.match(r"^last_updated:", l2):
                new[j] = f"last_updated: {date}"
                break
        return list(difflib.unified_diff(lines, new, lineterm="")), new
    raise SystemExit(f"story key '{key}' not found in {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--story-file", type=Path, required=True)
    ap.add_argument("--sprint-status", type=Path, required=True)
    ap.add_argument("--story-key", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--dry-run", action="store_true", help="Print diffs without writing")
    args = ap.parse_args()

    story_diff, story_new = edit_story(args.story_file, args.date, args.summary)
    sprint_diff, sprint_new = edit_sprint(args.sprint_status, args.story_key, args.date, args.summary)

    if not args.dry_run:
        args.story_file.write_text("\n".join(story_new) + "\n", encoding="utf-8")
        args.sprint_status.write_text("\n".join(sprint_new) + "\n", encoding="utf-8")

    print(json.dumps({
        "script": "mark-done", "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "dry_run": args.dry_run,
        "story_diff": story_diff,
        "sprint_diff": sprint_diff,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
