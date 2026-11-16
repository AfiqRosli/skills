#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""ship-commit.py — the deterministic ship-commit trio in one call.

What was four prose copies (sweep artifacts → stage → commit):
  1. ship-artifacts.py — mirror/name every story-scoped artifact
     (devlog, archived card, sessions, review docs, knowledge files)
  2. stage — `--add-all` (worktree/drain sweeps) or explicit `--paths`
     plus the swept artifact paths (shared checkout: never `add -A`,
     the main tree carries unrelated dirty state)
  3. `git commit -m {msg}` in the work-tree, reporting the sha

  ship-commit.py --project-root {root} --orchestration-dir {orch}
      --keys {k[,k2]} --message "cdo {key}: shipped"
      [--work-tree {dir}] [--add-all | --paths p...] [--no-verify]
      [--require-status verified]

`--require-status {status}` gates the commit on the ledger: every key
must read that status in flow-ledger.yaml (the per-story ship steps
pass `verified` — the cardinal-sin gate becomes structural). Leave it
off for post-ship artifact sweeps (their keys already read `shipped`).

Exit 0 committed/nothing-to-commit, 1 refused/failed, 2 error.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

RESERVED = [f":!**/{n}" for n in
            ["nul", "con", "prn", "aux"]
            + [f"com{i}" for i in range(1, 10)]
            + [f"lpt{i}" for i in range(1, 10)]]


def parse_args():
    p = argparse.ArgumentParser(
        description="Sweep artifacts, stage, commit — the ship trio.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--keys", required=True)
    p.add_argument("--work-tree", default=None,
                   help="checkout to commit in (default: project-root)")
    p.add_argument("--message", required=True)
    p.add_argument("--add-all", action="store_true",
                   help="git add -A — worktree/drain sweeps only")
    p.add_argument("--paths", nargs="*", default=[],
                   help="extra paths to stage (story code files)")
    p.add_argument("--no-verify", action="store_true")
    p.add_argument("--require-status", default=None, metavar="STATUS",
                   help="refuse unless every key reads this status in "
                        "flow-ledger.yaml (per-story ships pass 'verified')")
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


def check_status(orch: Path, keys: list, required: str):
    """Every key must read `required` in the ledger — the ship gate."""
    led = orch / "flow-ledger.yaml"
    stories = {}
    if led.is_file():
        doc = yaml.safe_load(led.read_text(encoding="utf-8")) or {}
        stories = doc.get("stories") or {}
    return [f"{k} reads '{(stories.get(k) or {}).get('status')}', "
            f"requires '{required}'"
            for k in keys if (stories.get(k) or {}).get("status") != required]


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    orch = Path(args.orchestration_dir).resolve()
    work = Path(args.work_tree).resolve() if args.work_tree else root

    if args.require_status:
        keys = [k.strip() for k in args.keys.split(",") if k.strip()]
        bad = check_status(orch, keys, args.require_status)
        if bad:
            emit({"status": "refused", "errors": bad}, 1, args.output)

    # root-relative, not Path(__file__): worktree spawns snapshot-copy
    # .agents into the worktree — __file__ there points at the stale copy
    script = root / ".agents" / "skills" / "cdo-platform" / "scripts" / \
        "ship-artifacts.py"
    cmd = [sys.executable, str(script), "--orchestration-dir", str(orch),
           "--project-root", str(root), "--keys", args.keys]
    if work != root:
        cmd += ["--worktree", str(work)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        art = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        emit({"status": "error",
              "errors": ["ship-artifacts output unparseable: "
                         f"{(proc.stderr or proc.stdout)[:200]}"]},
             2, args.output)
    if art.get("status") != "ok":
        emit({"status": "error", "artifacts": art,
              "errors": ["ship-artifacts failed"]}, 1, args.output)
    swept = sorted({p for rels in (art.get("swept") or {}).values()
                    for p in rels})

    if args.add_all:
        add = git(work, "add", "-A", "--", ".", *RESERVED)
        staged = "all"
    else:
        to_add = swept + list(args.paths)
        if not to_add:
            emit({"status": "nothing-to-commit", "sha": None,
                  "artifacts": art, "staged": []}, 0, args.output)
        add = git(work, "add", "--", *to_add, *RESERVED)
        staged = to_add
    if add.returncode != 0:
        emit({"status": "error", "artifacts": art,
              "errors": [f"git add failed: {add.stderr.strip()[:200]}"]},
             2, args.output)

    ck = git(work, "commit",
             *(["--no-verify"] if args.no_verify else []),
             "-qm", args.message)
    if ck.returncode != 0:
        if "nothing to commit" in (ck.stdout + ck.stderr):
            emit({"status": "nothing-to-commit", "sha": None,
                  "artifacts": art, "staged": staged}, 0, args.output)
        emit({"status": "error", "artifacts": art,
              "errors": [f"commit failed: "
                         f"{(ck.stderr or ck.stdout).strip()[:300]}"]},
             2, args.output)

    emit({"status": "committed", "artifacts": art, "staged": staged,
          "sha": git(work, "rev-parse", "HEAD").stdout.strip()},
         0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"status": "error",
                          "errors": [f"runtime error: {e}"]}))
        sys.exit(2)
