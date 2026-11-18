#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""cdo-setup ship-lane setup — ensure the configured ship_target branch
exists and, when safe, is the checked-out branch.

The org's ship model: automation commits land on the configured lane
(default `preview`), production refs stay Operator-gated. This script
makes that lane real:

  created_and_switched   : lane did not exist; `git switch -c <lane>`
                           (or `git switch <lane>` tracking an existing
                           remote lane) ran and the checkout now sits
                           on the lane.
  created_not_switched   : lane created via `git branch <lane>` but the
                           user's checkout stays — they're mid-feature
                           on another branch; ship work lands via push,
                           not by sitting on the lane.
  already_on_lane        : lane existed and was already checked out.
  exists_not_checked_out : lane exists; checkout is on another branch.
                           Never yanks the user's working tree.
  deferred               : zero-commit repo — `git branch` cannot name
                           an unborn HEAD's target. Create the lane
                           after the first commit (the greenfield
                           scaffold's wire stage is the usual producer).

Read the JSON result; the only failure mode is a git/command error.
Uncommitted changes are carried by `git switch -c` — safe to run on a
dirty tree.

Usage:
  uv run ensure-lane.py --project-root /path/to/project --lane preview
                        [--no-switch] [--verbose]

Exit codes: 0=ok (any status above), 2=runtime/git error
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_BRANCHES = {"main", "master", "trunk", "develop"}


def parse_args():
    p = argparse.ArgumentParser(
        description="Ensure the configured ship-target branch exists and, when safe, is checked out."
    )
    p.add_argument("--project-root", required=True, help="Absolute path to the project root")
    p.add_argument("--lane", default="",
                   help="Ship-target branch name (default: --answers "
                        "module.ship_target, else 'preview')")
    p.add_argument("--answers", default="",
                   help="propose-config answers.json — supplies ship_target")
    p.add_argument("--no-switch", action="store_true",
                   help="Create the lane if missing but never change the checked-out branch")
    p.add_argument("-o", "--output", help="Write JSON to file instead of stdout")
    p.add_argument("--verbose", action="store_true", help="Diagnostics to stderr")
    return p.parse_args()


def git(root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if check and r.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({r.returncode}): {(r.stderr or r.stdout).strip()}"
        )
    return r


def ref_exists(root: Path, ref: str) -> bool:
    return git(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0


def remote_lane(root: Path, lane: str) -> str:
    """Return 'origin/<lane>' style ref if exactly one remote carries it."""
    hits = []
    for remote in git(root, "remote").stdout.split():
        ref = f"refs/remotes/{remote}/{lane}"
        if ref_exists(root, ref):
            hits.append(remote)
    return hits[0] if len(hits) == 1 else ""


def emit(result: dict, output, code: int) -> None:
    payload = json.dumps(result, indent=2)
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    sys.exit(code)


def main() -> None:
    args = parse_args()
    root = Path(args.project_root).resolve()
    lane = args.lane.strip()
    if not lane and args.answers:
        answers = json.loads(Path(args.answers).read_text(encoding="utf-8"))
        lane = str((answers.get("module") or {}).get("ship_target") or "").strip()
    lane = lane or "preview"

    result = {
        "script": "cdo-ensure-lane",
        "version": "1.0.0",
        "project_root": str(root),
        "lane": lane,
        "status": "error",
        "current_branch": None,
        "remote_lane": None,
    }

    if not lane:
        result["reason"] = "empty lane name"
        emit(result, args.output, 2)

    if not (root / ".git").exists():
        result["reason"] = "not a git repo — cdo requires git (gate should have caught this)"
        emit(result, args.output, 2)
    if not shutil.which("git"):
        result["reason"] = "git not on PATH"
        emit(result, args.output, 2)

    try:
        has_commits = git(root, "rev-parse", "--verify", "HEAD").returncode == 0
        current = git(root, "branch", "--show-current").stdout.strip() or None
        result["current_branch"] = current
        lane_exists = ref_exists(root, f"refs/heads/{lane}")
        remote = remote_lane(root, lane)
        result["remote_lane"] = remote or None

        # Where a new lane should point: a remote lane beats the local
        # default branch, which beats HEAD (mid-feature checkouts must
        # not pin the lane to an unmerged tip).
        default_ref = next(
            (b for b in sorted(DEFAULT_BRANCHES)
             if ref_exists(root, f"refs/heads/{b}")),
            "HEAD",
        )

        if not has_commits:
            result["status"] = "deferred"
            result["reason"] = (
                "zero-commit repo — a branch cannot point at an unborn HEAD. "
                "Create the lane after the first commit."
            )
        elif lane_exists and current == lane:
            result["status"] = "already_on_lane"
        elif lane_exists:
            result["status"] = "exists_not_checked_out"
            result["reason"] = (
                f"lane exists; checkout stays on '{current}' — "
                "ship work lands via push, not by sitting on the lane."
            )
        elif args.no_switch or current not in DEFAULT_BRANCHES | {None}:
            # Create the lane for the org without moving the user's
            # checkout — either --no-switch was passed or they're
            # mid-feature on a non-default branch.
            if remote:
                git(root, "branch", "--track", lane, f"{remote}/{lane}", check=True)
                base = f"{remote}/{lane}"
            else:
                git(root, "branch", lane, default_ref, check=True)
                base = default_ref
            result["status"] = "created_not_switched"
            result["reason"] = (
                f"lane created at {base}; checkout stays on '{current}'"
                + (" (--no-switch)" if args.no_switch else " (mid-feature)")
            )
        else:
            if remote:
                # `git switch <lane>` DWIMs to a local branch tracking
                # the single remote lane.
                git(root, "switch", lane, check=True)
            else:
                git(root, "switch", "-c", lane, check=True)
            result["status"] = "created_and_switched"
            result["current_branch"] = lane
            result["reason"] = (
                f"tracking {remote}/{lane}" if remote else "created at HEAD"
            )
    except (OSError, RuntimeError) as e:
        result["reason"] = str(e)
        emit(result, args.output, 2)

    emit(result, args.output, 0)


if __name__ == "__main__":
    main()
