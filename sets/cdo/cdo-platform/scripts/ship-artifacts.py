#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""ship-artifacts.py — sweep a story's orchestration artifacts into the
ship commit's tree.

A worktree drain commits code in `.cdo-work/{drain_id}` — but the story's
artifacts (devlog, archived card, session reports, review docs, knowledge
extract, story doc) are written to the MAIN checkout's {orchestration_dir}
and `_bmad-output/`, so a bare `git add -A` in the worktree silently drops
them. The ship leg runs this BEFORE `git commit` so the lane commit carries
the story's complete record, not just its code.

What counts as a story artifact (per key — explicit allowlist; shared
orchestration state like flow-ledger.yaml, locks/, checklists, backlogs,
wave/drain records is NEVER swept):

  {orch}/devlog/**/{key}/**                    devlog dir (index, journal, retro)
  {orch}/alignment/**/{key}*.md                archived card + review docs
  {orch}/sessions/{key}.*                      session reports + spawn records
  {orch}/learning/knowledge/{key}.yaml         academy extraction
  {root}/_bmad-output/**/{key}*.md             per-story docs (shared sprint
                                               yamls never match — they
                                               aren't keyed by story)

Usage:
  uv run ship-artifacts.py --orchestration-dir {orch} --project-root {root}
      --worktree {dir} --keys S1,S2

--worktree = the tree about to commit; omit it (or pass the project root)
for a shared-checkout ship — artifacts are already in-tree, the report just
names them for staging. Output is JSON: {swept: {key: [relpaths]}, copied:
N}. Exit 0 always — a missing artifact is a report field, not a failure.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from cardlayout import BAYS  # noqa: E402 — vendored bay taxonomy


def parse_args():
    p = argparse.ArgumentParser(
        description="Sweep story artifacts into the ship commit's tree.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--project-root", required=True)
    p.add_argument("--worktree", default="",
                   help="tree about to commit — default: project root "
                        "(shared checkout = nothing to copy, report only)")
    p.add_argument("--keys", required=True, help="comma list of story keys")
    p.add_argument("-o", "--output")
    return p.parse_args()


def is_keyed(name: str, key: str) -> bool:
    """Filename belongs to the key: `{key}`, `{key}.x`, `{key}-x` — a bare
    prefix match would let "S1" sweep "S10-foo.md"."""
    return (name == key or
            (name.startswith(key) and name[len(key)] in ".-_"))


def story_paths(orch: Path, root: Path, key: str) -> list:
    """Every existing artifact path for the key — dirs expanded to files."""
    found = []
    devlog = orch / "devlog"
    if devlog.is_dir():
        for d in devlog.rglob(key):
            if d.is_dir() and d.name == key:
                found.extend(f for f in d.rglob("*") if f.is_file())
    if (orch / "alignment").is_dir():
        # parked/ and reviews/ are holding bays, superseded/ is frozen
        # history — a shipped story's artifacts live in the dated archive
        # (drafts stay in scope: an unreviewed card is still the story's
        # declared intent)
        found.extend(p for p in (orch / "alignment").rglob("*.md")
                     if is_keyed(p.stem, key)
                     and not ((BAYS - {"drafts"}) & set(p.parts)))
    if (orch / "sessions").is_dir():
        found.extend(p for p in (orch / "sessions").iterdir()
                     if p.is_file() and is_keyed(p.name, key))
    kn = orch / "learning" / "knowledge" / f"{key}.yaml"
    if kn.is_file():
        found.append(kn)
    bmad = root / "_bmad-output"
    if bmad.is_dir():
        found.extend(p for p in bmad.rglob("*.md")
                         if is_keyed(p.stem, key))
    # drain records are drain-scoped, not story-scoped — never a {key} match
    return sorted(set(found))


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    root = Path(args.project_root).resolve()
    worktree = Path(args.worktree).resolve() if args.worktree else root
    copy = worktree != root
    keys = [k.strip() for k in args.keys.split(",") if k.strip()]

    swept, copied = {}, 0
    for key in keys:
        paths = story_paths(orch, root, key)
        rels = []
        for src in paths:
            try:
                rel = src.resolve().relative_to(root)
            except ValueError:
                continue  # artifact outside the repo can't ride the commit
            rels.append(str(rel))
            if copy:
                dest = worktree / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                copied += 1
        swept[key] = rels

    out = json.dumps({
        "status": "ok",
        "worktree": str(worktree) if copy else None,
        "swept": swept,
        "copied": copied,
        "note": ("artifact files mirrored into the worktree — commit as usual"
                 if copy else
                 "shared checkout — stage these paths with the story commit"),
    }, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
