#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""land.py — land the caller's HEAD on the integration lane, FF-only.

The deterministic spine of every ship leg (was prompt-prose; a `land.py`
exists because four copies of this chain drifted into two critical bugs):
capture ship sha → ancestor check → rebase if base went stale → CAS
`update-ref` → rebase+retry once on refusal → advance the local
{ship_target} mirror. Never forces, never pushes — origin publication is
the Operator's pre-deploy sign-off.

Call from the context whose HEAD should land:
  - worktree drain: run inside `.cdo-work/{drain}` (default work-tree = cwd)
  - shared checkout: run anywhere in the main checkout

  land.py --project-root {root} [--work-tree {dir}] [--lane {ship_target}]
          [--to refs/heads/cdo-lane] [--reconcile] [--dry-run]

  --reconcile is forwarded to advance-lane.py — drain-end sweeps pass it
  so org-state churn doesn't leave the mirror stale and ad-hoc Operator
  WIP on the checkout stashes aside + pops back instead of blocking.

Output JSON: status landed | already-abreast | blocked | error —
  blocked means a sibling moved the lane twice (or rebase failed): the
  outcome journal records `blocked`, it is not retried silently.
Exit 0 landed/abreast, 1 blocked, 2 error. Stdlib only.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

LANE_REF = "refs/heads/cdo-lane"


def parse_args():
    p = argparse.ArgumentParser(
        description="Land HEAD on the integration lane, FF-only.")
    p.add_argument("--project-root", required=True,
                   help="main checkout root (owns the shared refs)")
    p.add_argument("--work-tree", default=None,
                   help="checkout whose HEAD lands (default: cwd)")
    p.add_argument("--lane", default="preview")
    p.add_argument("--to", default=LANE_REF)
    p.add_argument("--reconcile", action="store_true",
                   help="forward --reconcile to the advance call")
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


def git(cwd: Path, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True)


def resolve(cwd: Path, ref: str) -> str:
    return git(cwd, "rev-parse", "--verify", f"{ref}^{{commit}}") \
        .stdout.strip()


def is_ancestor(cwd: Path, anc: str, desc: str) -> bool:
    return git(cwd, "merge-base", "--is-ancestor", anc, desc) \
        .returncode == 0


def advance(root: Path, lane: str, target: str, reconcile: bool) -> dict:
    # root-relative, not Path(__file__): worktree spawns snapshot-copy
    # .agents into the worktree — __file__ there points at the stale copy
    script = root / ".agents" / "skills" / "cdo-platform" / "scripts" / \
        "advance-lane.py"
    cmd = [sys.executable, str(script), "--project-root", str(root),
           "run", "--to", target, "--lane", lane]
    if reconcile:
        cmd.append("--reconcile")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"status": "error",
                "raw": (proc.stdout or proc.stderr)[:200]}


def advance_warnings(adv: dict) -> list:
    """Warnings an advance result is carrying: a refused converge, or a
    WIP stash pop that needs the Operator's hands (conflicts kept the
    stash — never silently dropped)."""
    warnings = []
    if adv.get("status") not in \
            ("advanced", "already-abreast", "reconciled"):
        warnings.append(
            "lane advance refused: " + "; ".join(
                adv.get("errors", [adv.get("status", "?")])[:2]))
    pop = adv.get("stash_pop") or {}
    if pop.get("status") == "conflicts":
        warnings.append(
            "ad-hoc WIP stash pop conflicted on "
            + ", ".join(pop.get("files") or ["(see stash)"])
            + f" — WIP kept in {pop.get('ref', 'stash')}, resolve by hand")
    elif pop.get("status") == "deferred":
        warnings.append(
            "ad-hoc WIP stayed stashed (merge unresolved): "
            + pop.get("ref", "stash"))
    return warnings


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    work = Path(args.work_tree).resolve() if args.work_tree \
        else Path(os.getcwd()).resolve()
    probe = git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        emit({"status": "error",
              "errors": [f"not a git work tree: {root}"]}, 2, args.output)
    # identity check — the work-tree must share the project's object
    # store; landing a foreign repo's HEAD silently poisons the lane
    common_w = git(work, "rev-parse", "--git-common-dir").stdout.strip()
    common_r = git(root, "rev-parse", "--git-common-dir").stdout.strip()
    if common_w and common_r:
        cw = Path(common_w)
        cr = Path(common_r)
        cw = cw if cw.is_absolute() else (work / cw).resolve()
        cr = cr if cr.is_absolute() else (root / cr).resolve()
        if cw != cr:
            emit({"status": "error",
                  "errors": [f"{work} is not a worktree of {root} "
                             "(git common dirs differ)"]}, 2, args.output)

    ship = resolve(work, "HEAD")
    if not ship:
        emit({"status": "error",
              "errors": [f"HEAD does not resolve in {work}"]}, 2,
             args.output)
    tip = resolve(root, args.to)
    plan = {"work_tree": str(work), "ship": ship, "lane_tip": tip or None,
            "rebased": False, "retries": 0}

    if tip == ship:
        # already on the lane — still advance: a stale {lane} mirror
        # (missed/failed earlier advance) heals here, not nowhere
        adv = advance(root, args.lane, args.to, args.reconcile)
        emit({**plan, "status": "already-abreast", "advance": adv,
              "warnings": advance_warnings(adv)}, 0, args.output)
    if args.dry_run:
        stale = bool(tip) and not is_ancestor(work, tip, ship)
        emit({**plan, "status": "dry-run",
              "action": ("rebase+update-ref" if stale else "update-ref")
              + "+advance"}, 0, args.output)

    for attempt in range(2):            # CAS + one rebase-and-retry
        if tip and not is_ancestor(work, tip, ship):
            # base went stale — a commit whose tree predates landed
            # sibling work must never become the lane tip (CAS guards
            # the ref move, not the content)
            rb = git(work, "rebase", tip)
            if rb.returncode != 0:
                git(work, "rebase", "--abort")
                emit({**plan, "status": "blocked",
                      "errors": ["rebase onto lane tip failed (aborted): "
                                 + (rb.stderr or rb.stdout).strip()[:300]]},
                     1, args.output)
            ship = resolve(work, "HEAD")
            plan["ship"] = ship
            plan["rebased"] = True
        cas = git(root, "update-ref", args.to, ship,
                  "0000000000000000000000000000000000000000") \
            if not tip else git(root, "update-ref", args.to, ship, tip)
        if cas.returncode == 0:
            adv = advance(root, args.lane, args.to, args.reconcile)
            emit({**plan, "status": "landed", "lane_sha": ship,
                  "advance": adv,
                  "warnings": advance_warnings(adv)}, 0, args.output)
        tip = resolve(root, args.to) or tip
        plan["retries"] = attempt + 1

    emit({**plan, "status": "blocked",
          "errors": [f"CAS refused twice — a sibling moved {args.to} "
                     "concurrently; rebase+retry already spent, never "
                     "forcing"]}, 1, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"status": "error",
                          "errors": [f"runtime error: {e}"]}))
        sys.exit(2)
