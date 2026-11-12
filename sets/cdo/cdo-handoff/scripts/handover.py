#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Shift handover — the continuity file, regenerated deterministically.

Actions:

  write  → rebuild handover.md from live state (ledger + checklist + signals)
           plus --summary / --next-action narrative args
  read   → emit the resume payload as JSON + freshness check vs the ledger
           (a handover that disagrees with the ledger is an integrity anomaly)

The handover is the ONLY thing the next session knows at cold start — write it
at every batch boundary, story end, and session close.

Usage:
  uv run handover.py --orchestration-dir /path/docs/orchestration
      write [--summary "..."] [--next-action "..."]
  uv run handover.py --orchestration-dir /path/docs/orchestration read

Exit codes: 0=ok, 1=integrity anomaly on read, 2=runtime error
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})")


def parse_args():
    p = argparse.ArgumentParser(description="cdo shift handover read/write.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("action", choices=["write", "read"])
    p.add_argument("--summary", default="", help="session summary line")
    p.add_argument("--next-action", default="", help="the next right move")
    p.add_argument("-o", "--output")
    return p.parse_args()


def utcnow():
    return datetime.now(timezone.utc)


def iso_now():
    return utcnow().strftime("%Y-%m-%dT%H:%M")


def parse_ts(text):
    m = TS_RE.search(text or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_state(orch: Path):
    ledger, checklist = {}, ""
    lp = orch / "flow-ledger.yaml"
    if lp.is_file():
        try:
            ledger = yaml.safe_load(lp.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            ledger = {"_unparseable": True}
    cp = orch / "alignment-checklist.md"
    if cp.is_file():
        checklist = cp.read_text(encoding="utf-8", errors="replace")
    return ledger, checklist


def pending_items(checklist: str) -> list:
    # strip HTML comments first — format examples inside <!-- --> must not count
    text = re.sub(r"<!--.*?-->", "", checklist, flags=re.S)
    return [l.strip() for l in text.splitlines() if l.strip().startswith("- [ ]")]


def infer_next(ledger: dict) -> str:
    stories = ledger.get("stories") or {}
    in_flight = [k for k, s in stories.items() if isinstance(s, dict) and s.get("status") == "in-flight"]
    if in_flight:
        return (f"monitor in-flight workers: {', '.join(in_flight)} "
                f"(steps: {', '.join(str(stories[k].get('step')) for k in in_flight)})")
    confirmed = (ledger.get("pool") or {}).get("confirmed") or []
    if confirmed:
        return f"run ready-set + spawn workers for confirmed pool: {', '.join(confirmed)}"
    return "confirmed pool empty — run cdo-align to draft candidates"


def cmd_write(orch, args):
    ledger, checklist = load_state(orch)
    stories = ledger.get("stories") or {}
    pool = ledger.get("pool") or {}
    batch = ledger.get("batch") or {}
    cost = ledger.get("cost") or {}
    autonomy = ledger.get("autonomy") or {}
    signals = ledger.get("signals") or []

    in_flight = [
        (k, s) for k, s in stories.items()
        if isinstance(s, dict) and s.get("status") == "in-flight"
    ]
    quarantined = pool.get("quarantined") or []

    snap_lines = []
    manifest = batch.get("manifest") or []
    for item in manifest:
        st = stories.get(item) or {}
        snap_lines.append(f"- {item}: {st.get('status', 'queued')}"
                          + (f" (step {st['step']})" if st.get("step") else ""))
    if not snap_lines:
        snap_lines.append("- (no active batch manifest)")
    snap_lines.append(f"- pool: {len(pool.get('confirmed') or [])} confirmed, "
                      f"{len(quarantined)} quarantined")
    if cost.get("budget"):
        snap_lines.append(f"- cost: {cost.get('burned', 0)} / {cost['budget']}")
    if autonomy.get("enabled"):
        snap_lines.append(f"- autonomy streak: {autonomy.get('streak', 0)}/"
                          f"{autonomy.get('threshold', 10)}")

    esc_lines = [
        f"- {q['key']}: {q.get('reason', '?')}" for q in quarantined
        if isinstance(q, dict)
    ]
    esc_lines += [f"- [{s.get('type')}] {s.get('detail', '')} ({s.get('at', '')})"
                  for s in signals if isinstance(s, dict)]
    if not esc_lines:
        esc_lines.append("- none")

    pend = pending_items(checklist) or ["- none"]

    next_action = args.next_action or infer_next(ledger)

    doc = f"""# Shift Handover

Session-to-session continuity for the CDO. Written by `cdo-handoff` at every
batch checkpoint; the next CDO instance cold-starts from this file — no devlog
archeology required.

## Last Checkpoint

- batch: {batch.get('id') or 'none'}
- in-flight workers: {(', '.join(k + ' @ ' + str(s.get('step')) + ' (' + str(s.get('session') or 'n/a') + ')' for k, s in in_flight)) if in_flight else 'none'}
- timestamp: {iso_now()}
- summary: {args.summary or '(none provided)'}

## Batch State Snapshot

""" + "\n".join(snap_lines) + f"""

## Open Escalations

""" + "\n".join(esc_lines) + f"""

## Pending Operator Items

""" + "\n".join(pend) + f"""

## Next Action

{next_action}
"""
    (orch / "handover.md").write_text(doc, encoding="utf-8")
    return {"status": "written", "next_action": next_action,
            "in_flight": [k for k, _ in in_flight],
            "pending_count": len(pend) if pend != ["- none"] else 0}


def cmd_read(orch, args):
    hp = orch / "handover.md"
    if not hp.is_file():
        return {"status": "no-handover", "note": "cold start — no handover exists"}
    text = hp.read_text(encoding="utf-8", errors="replace")
    anomalies = []

    # freshness — compare checkpoint timestamp to now
    m = re.search(r"^- timestamp: (\S+)", text, re.M)
    age_minutes = None
    if m:
        t = parse_ts(m.group(1))
        if t:
            age_minutes = round((utcnow() - t).total_seconds() / 60, 1)
    else:
        anomalies.append("handover has no parseable timestamp")

    # integrity — handover's claimed in-flight set must match the ledger.
    # Covers both the per-worker line ("in-flight workers: S1 @ dev (w-S1), …")
    # and the older singular line ("in-flight story: S1").
    ledger, _ = load_state(orch)
    if ledger.get("_unparseable"):
        anomalies.append("flow-ledger.yaml unparseable — cannot verify claimed state")
        ledger = {}
    claimed = re.search(r"^- in-flight (?:workers|story): (.+)$", text, re.M)
    claimed_keys = []
    if claimed and claimed.group(1).strip() != "none":
        claimed_keys = re.findall(r"([A-Za-z0-9_-]+) @", claimed.group(1)) or \
            [claimed.group(1).split()[0].rstrip(",")]
    stories = ledger.get("stories") or {}
    actual = {k for k, s in stories.items()
              if isinstance(s, dict) and s.get("status") == "in-flight"}
    for k in claimed_keys:
        if k not in actual:
            anomalies.append(f"handover claims {k} in-flight; ledger disagrees")
    if not claimed_keys and actual:
        anomalies.append(f"ledger has {sorted(actual)} in-flight but handover says none")
    claimed_key = claimed_keys[0] if claimed_keys else None

    def section(name):
        m = re.search(rf"## {name}\n\n(.*?)(?=\n## |\Z)", text, re.S)
        return m.group(1).strip() if m else ""

    return {
        "status": "ok" if not anomalies else "anomalies",
        "age_minutes": age_minutes,
        "in_flight": claimed_key,
        "escalations": section("Open Escalations"),
        "pending_ceo": section("Pending Operator Items"),
        "next_action": section("Next Action"),
        "integrity_anomalies": anomalies,
    }


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    if not orch.is_dir():
        print(json.dumps({"errors": [f"orchestration dir not found: {orch}"]}))
        sys.exit(2)
    result = cmd_write(orch, args) if args.action == "write" else cmd_read(orch, args)
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    sys.exit(1 if result.get("integrity_anomalies") else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
