#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""case-file.py — assemble a forensic case file for a story/incident key.

Gathers, deterministically:
  - the ledger's story record (status, step, attempts, findings)
  - signals mentioning the key
  - doctrine entries mentioning the key
  - the backlog line + card paths (draft or archived)
  - checklist mentions

Writes `learning/cases/{key}-{date}.md` (a skeleton the LLM fills with
analysis) and emits the assembled timeline as JSON.

Usage:
  uv run case-file.py --orchestration-dir /path/docs/orchestration {key}
      [-o timeline.json]

Exit codes: 0=assembled, 1=key not found anywhere, 2=error
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


def parse_args():
    p = argparse.ArgumentParser(description="Assemble forensic case file.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("key")
    p.add_argument("-o", "--output")
    return p.parse_args()


def grep_file(path: Path, needle: str) -> list:
    """Token-boundary match — 'S1' must not hit lines carrying 'S12'."""
    if not path.is_file():
        return []
    pat = re.compile(rf"\b{re.escape(needle)}\b")
    return [l.strip() for l in
            path.read_text(encoding="utf-8", errors="replace").splitlines()
            if pat.search(l)]


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    key = args.key

    # ledger record
    ledger = {}
    lpath = orch / "flow-ledger.yaml"
    if lpath.is_file():
        try:
            ledger = yaml.safe_load(lpath.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            ledger = {"_unparseable": True}
    story = (ledger.get("stories") or {}).get(key)
    signals = [s for s in (ledger.get("signals") or [])
               if isinstance(s, dict) and key in str(s.get("key", ""))]
    quarantine = [q for q in (ledger.get("pool") or {}).get("quarantined") or []
                  if isinstance(q, dict) and q.get("key") == key]

    # file mentions
    doctrine_hits = grep_file(orch / "doctrine.md", key)
    checklist_hits = grep_file(orch / "alignment-checklist.md", key)
    backlog_hits = []
    bd = orch / "backlogs"
    if bd.is_dir():
        for f in sorted(bd.glob("*.md")):
            backlog_hits += [(f.name, l) for l in grep_file(f, key)]

    cards = [str(c.relative_to(orch)) for c in orch.glob(
        f"alignment/**/{key}.md")] if (orch / "alignment").is_dir() else []
    signal_files = [f.name for f in (orch / "signals").glob(f"*{key}*.md")] \
        if (orch / "signals").is_dir() else []

    found = bool(story or signals or quarantine or backlog_hits or
                 cards or signal_files or doctrine_hits or checklist_hits)
    if not found:
        print(json.dumps({"status": "not_found",
                          "key": key,
                          "errors": [f"no trace of {key} in operational state"]}))
        sys.exit(1)

    timeline = {
        "key": key,
        "ledger_story": story,
        "quarantine": quarantine,
        "signals": signals,
        "signal_files": signal_files,
        "cards": cards,
        "backlog_lines": backlog_hits,
        "doctrine_mentions": doctrine_hits,
        "checklist_mentions": checklist_hits,
    }

    # case file skeleton — the LLM writes the analysis into this
    cases = orch / "learning" / "cases"
    cases.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    case_path = cases / f"{key}-{today}.md"
    if not case_path.is_file():
        case_path.write_text(
            f"# Case File: {key}\n\n"
            f"_assembled {today} by cdo-continuity — analysis to follow_\n\n"
            "## Timeline evidence\n\n"
            f"- ledger status: {(story or {}).get('status', 'none')}\n"
            f"- attempts: {(story or {}).get('attempts', 0)}\n"
            f"- signals: {len(signals)}\n"
            f"- quarantine entries: {len(quarantine)}\n\n"
            "## Analysis\n\n{to fill: what happened, root cause, what doctrine changes}\n",
            encoding="utf-8")

    result = {
        "status": "assembled",
        "case_file": str(case_path.relative_to(orch)),
        "timeline": timeline,
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
