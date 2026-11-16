#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""spawn-plan.py — deterministic multi-group dispatch launcher (13-45).

Runs ready-set.py, then spawns ONE external session per dependency group
from its spawn_plan — no LLM judgment anywhere:

  - a multi-key group (dep-connected) → one linear drain session
    (`spawn-dispatch --keys k1,k2`), topo order preserved
  - a solo key (no dep edges) → its own session (`spawn-dispatch --key k`)

Parallel groups are safe: spawn-dispatch's drain guard is
intersection-based — only overlapping key-sets refuse. Every local
session launches as a VISIBLE external command prompt (the WMI shim),
carrying DEVIN_MODEL from --model / cdo.dispatch_model.

Usage:
  uv run spawn-plan.py --orchestration-dir /path/docs/orchestration
      --project-root /path/project [--model "..."] [--no-push]
      [--dry-run] [-o result.json]

Exit codes: 0=all spawned (or dry-run), 1=any spawn refused, 2=runtime error
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def parse_args():
    p = argparse.ArgumentParser(description="Spawn one session per dependency group.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--project-root", required=True)
    p.add_argument("--model", default="",
                   help="worker model for every session (default: "
                        "cdo.dispatch_model, else GLM-5.3 Flash Low)")
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("-o", "--output")
    return p.parse_args()


def main():
    args = parse_args()
    ready = subprocess.run(
        [sys.executable, str(HERE / "ready-set.py"),
         "--orchestration-dir", args.orchestration_dir,
         "--project-root", args.project_root],
        capture_output=True, text=True)
    try:
        plan = json.loads(ready.stdout)
    except json.JSONDecodeError:
        print(json.dumps({"errors": [
            f"ready-set failed: {ready.stderr.strip() or ready.stdout[:400]}"]}))
        return 2
    if plan.get("errors"):
        print(json.dumps(plan))
        return 2

    groups = plan.get("spawn_plan") or []
    if not groups:
        result = {"status": "nothing-to-spawn",
                  "dispatch_now": plan.get("dispatch_now", []),
                  "waiting": plan.get("waiting", {})}
        blob = json.dumps(result, indent=2)
        (Path(args.output).write_text(blob, encoding="utf-8")
         if args.output else print(blob))
        return 0

    spawned, refused = [], []
    for group in groups:
        keys = group["keys"]
        cmd = [sys.executable, str(HERE / "spawn-dispatch.py"),
               "--orchestration-dir", args.orchestration_dir,
               "--project-root", args.project_root,
               "--local"]
        if args.no_push:
            cmd += ["--no-push"]
        if args.model:
            cmd += ["--model", args.model]
        cmd += (["--keys", ",".join(keys)] if len(keys) > 1
                else ["--key", keys[0]])
        if args.dry_run:
            cmd += ["--dry-run"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        try:
            data = json.loads(proc.stdout) if proc.stdout else {}
        except json.JSONDecodeError:
            data = {"errors": [proc.stdout[:400] or proc.stderr[:400]]}
        entry = {"keys": keys, "mode": group["mode"],
                 "returncode": proc.returncode, "result": data}
        (spawned if proc.returncode == 0 else refused).append(entry)

    result = {"status": "ok" if not refused else "partial",
              "spawned": spawned, "refused": refused,
              "waiting": plan.get("waiting", {})}
    blob = json.dumps(result, indent=2)
    (Path(args.output).write_text(blob, encoding="utf-8")
     if args.output else print(blob))
    return 1 if refused else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
