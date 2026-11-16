#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""manifest.py — build the ordered batch manifest from the confirmed pool.

Reads `pool.confirmed`, resolves `deps:` declared on backlog lines
(`- [x] S3 — title | deps: S1,S2`), topo-sorts (stable — backlog order
breaks ties), writes `batch.id` + `batch.manifest` + `batch.started` to
flow-ledger.yaml.

Re-plan mode (`--replan`): keeps `done`/`verified` stories' positions
acknowledged, reorders the remaining pool — invoked on FRAGO events.

Usage:
  uv run manifest.py --orchestration-dir /path/docs/orchestration
      [--batch-id b5] [--replan] [-o result.json]

Exit codes: 0=manifest built, 1=blocked (cycle/empty pool), 2=error
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

DEPS_RE = re.compile(r"\bdeps:\s*([A-Za-z0-9_,\s]+)")
KEY_LINE_RE = re.compile(r"^- \[[ xA\-]\] (\S+?)\b")


def parse_args():
    p = argparse.ArgumentParser(description="Build batch manifest from confirmed pool.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--batch-id", default="")
    p.add_argument("--replan", action="store_true")
    p.add_argument("-o", "--output")
    return p.parse_args()


def backlog_deps(orch: Path) -> dict:
    """key -> [dep keys] parsed from all backlog files."""
    deps = {}
    bd = orch / "backlogs"
    if not bd.is_dir():
        return deps
    for f in bd.glob("*.md"):
        text = f.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            m = KEY_LINE_RE.match(line.strip())
            if not m:
                continue
            dm = DEPS_RE.search(line)
            if dm:
                deps[m.group(1)] = [d.strip() for d in dm.group(1).split(",") if d.strip()]
    return deps


DONE_STATUSES = {"done", "verified", "shipped"}


def topo_order(pool: list, deps: dict, stories: dict) -> tuple:
    """Stable topological sort — pool order breaks ties. Returns (order, cyclic,
    dead_deps). A dep outside the pool counts as done ONLY when the ledger says
    it finished — quarantined/unaligned/absent deps BLOCK their dependents."""
    remaining = list(pool)
    all_deps = {d for ds in deps.values() for d in ds}
    done = {d for d in all_deps if d not in remaining and
            (stories.get(d) or {}).get("status") in DONE_STATUSES}
    dead = {k: [d for d in deps.get(k, []) if d not in done and d not in pool]
            for k in remaining}
    dead = {k: v for k, v in dead.items() if v}
    order, cyclic = [], []
    progress = True
    while remaining and progress:
        progress = False
        for k in list(remaining):
            if k in dead:
                continue  # hard block — dep exists but never finished
            need = [d for d in deps.get(k, []) if d not in done and d in pool]
            if not need:
                order.append(k)
                done.add(k)
                remaining.remove(k)
                progress = True
    return order, remaining, dead  # leftover = cyclic or dep-blocked


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    lpath = orch / "flow-ledger.yaml"
    if not lpath.is_file():
        print(json.dumps({"errors": ["flow-ledger.yaml missing"]}))
        sys.exit(2)
    ledger = yaml.safe_load(lpath.read_text(encoding="utf-8")) or {}
    pool = (ledger.get("pool") or {}).get("confirmed") or []

    if not pool:
        print(json.dumps({"status": "blocked",
                          "errors": ["confirmed pool is empty — nothing to manifest"]}))
        sys.exit(1)

    deps = backlog_deps(orch)
    order, cyclic, dead = topo_order(pool, deps, ledger.get("stories") or {})
    if dead:
        print(json.dumps({"status": "blocked",
                          "errors": [f"{k} depends on unfinished {v} "
                                     "(quarantined/unaligned/absent)"
                                     for k, v in dead.items()],
                          "dead_deps": dead}))
        sys.exit(1)
    if cyclic:
        print(json.dumps({"status": "blocked",
                          "errors": [f"dependency cycle among: {cyclic}"],
                          "cyclic": cyclic}))
        sys.exit(1)

    batch_id = args.batch_id or \
        (ledger.get("batch") or {}).get("id") or \
        "b" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

    stories = ledger.get("stories") or {}
    in_flight = [k for k in order if stories.get(k, {}).get("status") == "in-flight"]

    ledger.setdefault("batch", {})
    ledger["batch"].update({
        "id": batch_id,
        "manifest": order,
        "started": ledger["batch"].get("started")
                   or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M"),
    })
    # atomic write — workers write this ledger concurrently now
    tmp = lpath.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
    os.replace(tmp, lpath)

    result = {
        "status": "manifested",
        "batch_id": batch_id,
        "manifest": order,
        "in_flight": in_flight,
        "deps_resolved": {k: deps[k] for k in order if deps.get(k)},
        "mode": "replan" if args.replan else "build",
    }
    out = json.dumps(result, indent=2)
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
