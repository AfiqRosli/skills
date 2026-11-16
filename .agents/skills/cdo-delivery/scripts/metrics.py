#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""metrics.py — takt metrics from flow-ledger.yaml.

The Agile Delivery office's scoreboard: throughput, cycle time, attempt
burn, quarantine rate — all derived, none hand-tallied.

Emits JSON: {stories_by_status, completed, cycle_minutes {avg,max},
attempts {total,avg}, quarantine_rate, throughput_24h}.

Usage:
  uv run metrics.py --orchestration-dir /path/docs/orchestration [-o out.json]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})")
FINDING_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})")


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main():
    p = argparse.ArgumentParser(description="Takt metrics from the flow ledger.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("-o", "--output")
    args = p.parse_args()

    orch = Path(args.orchestration_dir).resolve()
    lpath = orch / "flow-ledger.yaml"
    if not lpath.is_file():
        print(json.dumps({"errors": ["flow-ledger.yaml missing"]}))
        sys.exit(2)
    ledger = yaml.safe_load(lpath.read_text(encoding="utf-8")) or {}
    stories = ledger.get("stories") or {}
    pool = ledger.get("pool") or {}

    by_status, completed, cycles = {}, [], []
    attempts_total, done_24h = 0, 0
    now = datetime.now(timezone.utc)

    for key, st in stories.items():
        if not isinstance(st, dict):
            continue
        status = st.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        attempts_total += st.get("attempts", 0)

        if status in ("done", "verified", "shipped"):
            started = parse_ts(st.get("step_started"))
            # latest finding timestamp approximates completion
            end = None
            for f in (st.get("findings") or [])[::-1]:
                m = FINDING_TS_RE.match(str(f))
                if m:
                    end = parse_ts(m.group(1))
                    break
            completed.append(key)
            if started and end and end >= started:
                cycles.append((end - started).total_seconds() / 60)
                if now - end <= timedelta(hours=24):
                    done_24h += 1

    quarantined = len(pool.get("quarantined") or [])
    confirmed = len(pool.get("confirmed") or [])
    total_seen = len(stories) + quarantined
    result = {
        "stories_by_status": by_status,
        "completed": len(completed),
        "cycle_minutes": {
            "avg": round(sum(cycles) / len(cycles), 1) if cycles else None,
            "max": round(max(cycles), 1) if cycles else None,
        },
        "attempts": {
            "total": attempts_total,
            "avg": round(attempts_total / len(stories), 2) if stories else None,
        },
        "quarantined": quarantined,
        "confirmed_pool": confirmed,
        "quarantine_rate": round(quarantined / total_seen, 3) if total_seen else 0,
        "throughput_24h": done_24h,
        "cost": ledger.get("cost") or {},
        "autonomy": ledger.get("autonomy") or {},
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
