#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""push-state.py — publish orchestration state to the ship lane before a
cloud dispatch.

A Devin Cloud worker clones the repo fresh — it sees nothing that isn't
pushed. This script commits dirty `docs/orchestration/` state (the confirmed
pool, archived cards, checklist resolutions, session prompts) and pushes the
current HEAD to `origin/{lane}` (the ship lane, `preview` by default), so the
spawned session inherits the dispatch order it was spawned to run.

Only `docs/orchestration/` is staged — code changes in flight elsewhere are
the Operator's business, not a spawn's.

Usage:
  uv run push-state.py --project-root /path/project
      --orchestration-dir /path/docs/orchestration
      [--lane preview] [--message "why"] [--dry-run] [-o result.json]

Emits {status, committed, pushed, lane, head, base_ref}. Exit codes:
0=pushed (or already clean + pushed), 1=push refused (non-FF — reconcile
with origin first), 2=error (not a repo, no remote, git missing).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Commit + push orchestration "
                                           "state to the ship lane.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--lane", default="preview",
                   help="remote branch the pool state publishes to "
                        "(default: preview — the ship_target lane)")
    p.add_argument("--message", default="",
                   help="commit message tail (e.g. 'dispatch pool: S7,S9')")
    p.add_argument("--dry-run", action="store_true",
                   help="report what would happen, touch nothing")
    p.add_argument("-o", "--output")
    return p.parse_args()


def emit(result: dict, code: int, out: str):
    blob = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


def git(root: Path, *args, check=False):
    proc = subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    orch = Path(args.orchestration_dir).resolve()

    probe = git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        emit({"errors": [f"not a git work tree: {root}"]}, 2, args.output)
    remote = git(root, "remote", "get-url", "origin")
    if remote.returncode != 0:
        emit({"errors": ["no `origin` remote — cloud workers have nothing "
                         "to clone from"]}, 2, args.output)

    try:
        orch_rel = orch.relative_to(root).as_posix()
    except ValueError:
        emit({"errors": [f"orchestration dir {orch} is outside {root} — "
                         "the clone wouldn't carry it anyway"]}, 2, args.output)

    head = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    dirty = git(root, "status", "--porcelain", "--", orch_rel)
    dirty_paths = [l[3:] for l in dirty.stdout.splitlines() if l.strip()]

    plan = {"committed": False, "pushed": False, "lane": args.lane,
            "head": head, "branch": branch, "dirty_paths": dirty_paths,
            "base_ref": f"origin/{args.lane}"}

    if args.dry_run:
        plan.update({"status": "dry-run",
                     "would_commit": bool(dirty_paths),
                     "would_push": f"HEAD:{args.lane}"})
        emit(plan, 0, args.output)

    if dirty_paths:
        git(root, "add", "--", orch_rel, check=True)
        msg = "cdo: orchestration state" + (f" — {args.message}"
                                          if args.message else "")
        commit = git(root, "commit", "-m", msg)
        if commit.returncode != 0:
            emit({"errors": [f"commit failed: {commit.stderr.strip()}"]},
                 2, args.output)
        plan["committed"] = True
        head = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
        plan["head"] = head

    # HEAD:lane — explicit refspec so callers on any branch (Marshal on
    # preview, a cloud drain on its lane clone) publish the same way
    push = git(root, "push", "origin", f"HEAD:{args.lane}")
    if push.returncode != 0:
        err = push.stderr.strip()
        non_ff = bool(re.search(r"non-fast-forward|rejected", err))
        emit({"errors": [
            f"push to origin/{args.lane} refused: {err}",
            "local HEAD is behind the lane — fetch + rebase/merge "
            "origin before spawning" if non_ff else
            "push failed — check remote access"], "partial": plan},
            1, args.output)
    plan["pushed"] = True
    plan["status"] = "pushed"
    emit(plan, 0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
