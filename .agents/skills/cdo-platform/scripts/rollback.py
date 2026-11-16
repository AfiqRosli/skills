#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""rollback.py — abort-safe revert of one shipped story.

Was a prose runbook (identify commits → revert → journal): the first
two steps always have one correct answer, so they're a script now.
Resolve the story's shipped commit (ledger `lane_sha` first, `git log
--grep "^cdo {key}:"` fallback for legacy ships), verify the ledger
reads `shipped` when a story entry exists, `git revert --no-edit`. A
conflicting revert aborts clean and names the paths — the tree is
never left half-reverted.

  rollback.py {key} --orchestration-dir {orch} --project-root {root}
      [--work-tree {dir}] [--reason "..."] [--dry-run]

The revert lands in the caller's checkout — land it with land.py like
a ship commit; publishing stays the Operator's push/sign-off leg.

JSON: {status, key, lane_sha, revert_commit, pushed, conflicts}.
Exit 0 reverted, 1 refused/conflicts, 2 error.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)


def parse_args():
    p = argparse.ArgumentParser(
        description="Abort-safe revert of one shipped story.")
    p.add_argument("key")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--project-root", required=True)
    p.add_argument("--work-tree", default=None,
                   help="checkout to revert in (default: project-root)")
    p.add_argument("--reason", default="")
    p.add_argument("--dry-run", action="store_true",
                   help="resolve + verify only, no revert")
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


def story_entry(orch: Path, key: str):
    led = orch / "flow-ledger.yaml"
    if not led.is_file():
        return None
    led_doc = yaml.safe_load(led.read_text(encoding="utf-8")) or {}
    return (led_doc.get("stories") or {}).get(key)


def resolve_sha(work: Path, key: str, st):
    """lane_sha from the ledger, else log-grep the lane ref."""
    sha = (st or {}).get("lane_sha")
    if sha:
        return sha, "ledger"
    log = git(work, "log", "--format=%H", f"--grep=^cdo {key}:",
              "refs/heads/cdo-lane")
    if log.returncode == 0:
        lines = [l.strip() for l in log.stdout.splitlines() if l.strip()]
        if lines:
            return lines[0], "log-grep"
    return None, None


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    orch = Path(args.orchestration_dir).resolve()
    work = Path(args.work_tree).resolve() if args.work_tree else root

    st = story_entry(orch, args.key)
    status = (st or {}).get("status")
    if st is not None and status != "shipped":
        emit({"status": "refused", "key": args.key,
              "errors": [f"story reads '{status}' — rollback only what "
                         "was shipped (unshipped → kill via "
                         "dispatch.py outcome)"]}, 1, args.output)

    sha, source = resolve_sha(work, args.key, st)
    if not sha:
        emit({"status": "refused", "key": args.key,
              "errors": ["no shipped commit found — no lane_sha in "
                         "ledger, no 'cdo {key}:' commit on "
                         "refs/heads/cdo-lane"]}, 1, args.output)

    cat = git(work, "cat-file", "-e", f"{sha}^{{commit}}")
    if cat.returncode != 0:
        emit({"status": "error", "key": args.key, "lane_sha": sha,
              "errors": [f"resolved sha {sha[:12]} is not a commit here"]},
             2, args.output)

    pushed = bool((st or {}).get("pushed"))
    if args.dry_run:
        emit({"status": "plan", "key": args.key, "lane_sha": sha,
              "source": source, "pushed": pushed,
              "would_run": f"git revert --no-edit {sha}"}, 0, args.output)

    rv = git(work, "revert", "--no-edit", sha)
    if rv.returncode != 0:
        unmerged = git(work, "diff", "--name-only", "--diff-filter=U")
        conflicts = [l for l in unmerged.stdout.splitlines() if l]
        git(work, "revert", "--abort")
        emit({"status": "conflicts", "key": args.key, "lane_sha": sha,
              "source": source, "revert_commit": None, "pushed": pushed,
              "conflicts": conflicts,
              "errors": ["revert conflicted and was aborted — escalate "
                         "to the duty officer"]}, 1, args.output)

    emit({"status": "reverted", "key": args.key, "lane_sha": sha,
          "source": source,
          "revert_commit": git(work, "rev-parse", "HEAD").stdout.strip(),
          "pushed": pushed, "conflicts": []}, 0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"status": "error",
                          "errors": [f"runtime error: {e}"]}))
        sys.exit(2)
