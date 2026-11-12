#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""sweep-worktrees.py — remove dead .cdo-work dispatch worktrees.

The single shared implementation of "is this worktree dead" — was
reimplemented inline by cdo-review's verdict sweep AND cdo-watch's age
janitor (a third copy lives in operator muscle memory). Both callers now
delegate here; the only difference is their trigger:

  verdict-triggered (apply-decisions): no --older-than — any lockless
      worktree is removable the moment a Delivered item confirms.
  age-triggered (watch janitor): --older-than GROUP_LOCK_TTL_MIN —
      backstop for worktrees nobody reviewed.

Live rule — a lock file still claims it:
  `locks/{stem}.lock` (drain and worker ids both lock under their full
  spawn name) OR `locks/{key}.lock` for w-/r-/a-{key}-{ts} workers whose
  story key holds its own per-story claim — OR the worktree's own gitdir
  shows an in-flight op (index.lock, MERGE_HEAD, REBASE_HEAD...): a
  wrongly-broken lock never sweeps a tree that's mid-operation.

--skip-key keeps worktrees whose story key matches (just-rejected
Delivered items — the rollback/reshape escalation may still need the
tree). g-* worktrees can't be key-matched — the name embeds only the
queue's first key — so any --skip-key keeps ALL g-* trees that pass.

  sweep-worktrees.py --project-root {root} --orchestration-dir {orch}
      [--older-than MIN] [--skip-key KEY]... [--dry-run] [-o out.json]

Output JSON: {removed: [names], kept: [names], errors: [strings]}.
Exit 0 ok (removal failures report inside `errors`), 2 runtime error.
Stdlib only.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORK_ROOT = ".cdo-work"
WORKER_KEY_RE = re.compile(r"^[wra]-(.+)-\d{8,}$")
GROUP_KEY_RE = re.compile(r"^g-(.+)-\d{8,}$")
# a live worker's gitdir markers — locks can be broken mid-work; these
# say the tree is mid-operation right now
LIVE_MARKERS = ("index.lock", "MERGE_HEAD", "REBASE_HEAD",
                "CHERRY_PICK_HEAD", "REVERT_HEAD")


def worktree_gitdir(wt: Path):
    """A linked worktree's `.git` is a file pointing at its gitdir."""
    gitfile = wt / ".git"
    try:
        content = gitfile.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not content.startswith("gitdir:"):
        return None
    return Path(content[7:].strip())


def busy(wt: Path) -> bool:
    gitdir = worktree_gitdir(wt)
    if not gitdir:
        return False
    return any((gitdir / m).exists() for m in LIVE_MARKERS)


def parse_args():
    p = argparse.ArgumentParser(
        description="Sweep dead .cdo-work worktrees.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--older-than", type=float, default=None,
                   help="only remove dead worktrees idle > MIN minutes")
    p.add_argument("--skip-key", action="append", default=[],
                   help="keep worktrees whose story key matches (e.g. "
                        "just-rejected Delivered items)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("-o", "--output")
    return p.parse_args()


def emit(result: dict, code: int, out: str):
    blob = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


def age_minutes(wt: Path) -> float:
    """Idle clock — the worktree dir's own mtime is shallow (activity
    lands in subdirs), so prefer the gitdir's HEAD reflog: every commit/
    checkout rewrites it. Falls back to dir mtime."""
    candidates = []
    gitdir = worktree_gitdir(wt)
    if gitdir:
        candidates.append(gitdir / "logs" / "HEAD")
    candidates.append(wt)
    mtimes = []
    for c in candidates:
        try:
            mtimes.append(c.stat().st_mtime)
        except OSError:
            pass
    if not mtimes:
        return float("inf")
    return (datetime.now(timezone.utc).timestamp() - max(mtimes)) / 60


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    orch = Path(args.orchestration_dir).resolve()
    work_root = root / WORK_ROOT
    locks_dir = orch / "locks"
    skip = set(args.skip_key)
    result = {"removed": [], "kept": [], "errors": []}

    if not work_root.is_dir():
        emit(result, 0, args.output)
    proc = subprocess.run(
        ["git", "-C", str(root), "worktree", "list", "--porcelain"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        emit({**result, "errors": [
            f"worktree list failed: {proc.stderr.strip()[:200]}"]},
            2, args.output)

    prefix = str(work_root.resolve()).replace("\\", "/")
    for line in proc.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        wt = Path(line[9:].strip())
        if not str(wt).replace("\\", "/").startswith(prefix):
            continue
        stem = wt.name
        m = WORKER_KEY_RE.match(stem)
        if m and m.group(1) in skip:
            result["kept"].append(f"{stem} — skipped (key in skip list)")
            continue
        if not m and GROUP_KEY_RE.match(stem) and skip:
            # g-* worktrees hold a whole drain's queue — the name embeds
            # only the first key, so a just-rejected member can't be
            # matched; keep the tree while its escalation is live
            result["kept"].append(f"{stem} — skipped (rejected pass)")
            continue
        live = (locks_dir / f"{stem}.lock").is_file() or \
            (m and (locks_dir / f"{m.group(1)}.lock").is_file())
        if live:
            result["kept"].append(f"{stem} — live lock")
            continue
        if busy(wt):
            # git-level liveness — mid-rebase/merge/commit inside the
            # tree; its lock may have been broken wrongly, never force
            result["kept"].append(f"{stem} — mid-operation")
            continue
        if args.older_than is not None \
                and age_minutes(wt) <= args.older_than:
            result["kept"].append(f"{stem} — dead but young")
            continue
        if args.dry_run:
            result["removed"].append(f"{stem} (dry-run)")
            continue
        rm = subprocess.run(
            ["git", "-C", str(root), "worktree", "remove", "--force",
             str(wt)], capture_output=True, text=True)
        if rm.returncode == 0:
            result["removed"].append(stem)
        else:
            result["errors"].append(
                f"{stem} — remove failed: {rm.stderr.strip()[:120]}")

    emit(result, 0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"removed": [], "kept": [],
                          "errors": [f"runtime error: {e}"]}))
        sys.exit(2)
