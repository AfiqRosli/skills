#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Surgical sprint-status.yaml read/write for cdo-code-e2e intermediate transitions.

mark-done.py owns the final `done` transition (it also edits the story doc).
This script covers everything before that: backlog -> ready-for-dev ->
in-progress -> review, plus 1-line status reads. Same discipline: only the
story's own line changes, comments preserved byte-for-byte, unified diff
printed for verification.

Usage:
  python sprint-status.py get  --sprint-status Y --story-key K
  python sprint-status.py set  --sprint-status Y --story-key K --status review \
      [--note "what changed"] [--dry-run]
  python sprint-status.py add  --sprint-status Y --story-key K [--status proposed] \
      [--note "origin note"] [--dry-run]

`add` inserts a new `NN-MM-slug: {status}` line inside the epic-NN block —
after the last NN-* story line (before epic-NN-retrospective), or directly
under `epic-NN:` when the epic has no stories yet. Refuses on key collision.
`proposed` = CDO-shaped but unaligned; the alignment gate flips it to
`backlog` on Operator confirm.
"""
import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

STATUSES = ("proposed", "backlog", "ready-for-dev", "in-progress", "review",
            "done", "obsolete")


def find_entry(lines: list[str], key: str) -> re.Match | None:
    pat = re.compile(rf"^(\s*){re.escape(key)}:\s*([a-z-]+)(\s*(#.*)?)$")
    for line in lines:
        m = pat.match(line)
        if m:
            return m
    return None


def cmd_get(args) -> dict:
    lines = Path(args.sprint_status).read_text(
        encoding="utf-8", errors="replace").splitlines()
    m = find_entry(lines, args.story_key)
    if not m:
        return {"status": "fail", "error": f"story key '{args.story_key}' not found"}
    return {"status": "pass", "story_key": args.story_key,
            "value": m.group(2), "comment": m.group(4)}


def cmd_set(args) -> dict:
    path = Path(args.sprint_status)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    new = lines[:]
    pat = re.compile(rf"^(\s*){re.escape(args.story_key)}:\s*([a-z-]+)(\s*(#.*)?)$")
    for i, line in enumerate(new):
        m = pat.match(line)
        if not m:
            continue
        indent, _status, _tail, comment = m.groups()
        new[i] = f"{indent}{args.story_key}: {args.status}"
        if comment:
            new[i] += " " + comment.rstrip()
        if args.note:
            stamp = f"{args.status.upper()} {args.date} — {args.note}"
            new[i] += (f", {stamp}" if comment else f"  # {stamp}")
        for j, l2 in enumerate(new):
            if re.match(r"^last_updated:", l2):
                new[j] = f"last_updated: {args.date}"
                break
        diff = list(difflib.unified_diff(lines, new, lineterm=""))
        if not args.dry_run:
            path.write_text("\n".join(new) + "\n", encoding="utf-8")
        return {"status": "pass", "script": "sprint-status",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "story_key": args.story_key, "value": args.status,
                "dry_run": args.dry_run, "diff": diff}
    return {"status": "fail", "error": f"story key '{args.story_key}' not found in {path}"}


def cmd_add(args) -> dict:
    """Insert `{key}: {status}` inside the key's epic-NN block. Position:
    after the last `NN-*` story line in the block (so epic-NN-retrospective
    and section comments stay last); directly under `epic-NN:` when the
    epic has no story lines yet. Refuses when the key already exists."""
    m = re.match(r"^(\d+)-(\d+)-", args.story_key)
    if not m:
        return {"status": "fail",
                "error": f"story key '{args.story_key}' is not NN-MM-slug "
                         "— can't locate its epic block"}
    epic_num = int(m.group(1))
    path = Path(args.sprint_status)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if find_entry(lines, args.story_key):
        return {"status": "fail",
                "error": f"story key '{args.story_key}' already present"}
    epic_re = re.compile(rf"^(\s*)epic-{epic_num}:\s*[a-z-]+")
    story_re = re.compile(rf"^(\s*){epic_num}-\d+-")
    epic_idx = last_story_idx = None
    for i, line in enumerate(lines):
        if epic_re.match(line):
            epic_idx = i
        elif story_re.match(line):
            last_story_idx = i
        elif epic_idx is not None and re.match(r"^\s*epic-\d+:", line):
            break  # reached the next epic block — stop scanning
    if epic_idx is None:
        return {"status": "fail",
                "error": f"no `epic-{epic_num}:` block found in {path.name} "
                         "— create the epic section first"}
    anchor = last_story_idx if last_story_idx is not None else epic_idx
    indent = "  "
    for j in range(anchor, epic_idx, -1):
        im = re.match(r"^(\s*)\S", lines[j])
        if im and lines[j].strip() and not lines[j].lstrip().startswith("#"):
            indent = im.group(1)
            break
    entry = f"{indent}{args.story_key}: {args.status}"
    if args.note:
        entry += f"  # {args.status.upper()} {args.date} — {args.note}"
    new = lines[:anchor + 1] + [entry] + lines[anchor + 1:]
    for j, l2 in enumerate(new):
        if re.match(r"^last_updated:", l2):
            new[j] = f"last_updated: {args.date}"
            break
    diff = list(difflib.unified_diff(lines, new, lineterm=""))
    if not args.dry_run:
        path.write_text("\n".join(new) + "\n", encoding="utf-8")
    return {"status": "pass", "script": "sprint-status",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "story_key": args.story_key, "value": args.status,
            "inserted_after": lines[anchor].strip()[:80],
            "dry_run": args.dry_run, "diff": diff}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("get", cmd_get), ("set", cmd_set), ("add", cmd_add)):
        p = sub.add_parser(name, help=f"{name} a story's sprint status")
        p.add_argument("--sprint-status", type=Path, required=True)
        p.add_argument("--story-key", required=True)
        if name in ("set", "add"):
            p.add_argument("--status",
                           required=name == "set", default="proposed",
                           choices=STATUSES)
            p.add_argument("--note", help="Appended to the traceability comment as `STATUS <date> — <note>`")
            p.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            p.add_argument("--dry-run", action="store_true")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    result = args.fn(args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
