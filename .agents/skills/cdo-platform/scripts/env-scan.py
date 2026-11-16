#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""env-scan — credential logistics for cdo-platform.

Cross-references three sources and reports coverage:

  .env               — which keys are set (never prints values)
  # TEMP-CDO markers — which set keys are placeholders awaiting real values
  archived cards     — which env keys confirmed items declare they need
  checklist Requisitions — what's already asked for

Output: JSON coverage report — {real, temp, missing, requisitioned}.
Exit codes: 0=all covered, 1=gaps exist, 2=runtime error

Usage:
  uv run env-scan.py --orchestration-dir /path/docs/orchestration
      [--env-file /path/.env] [--file-requisitions] [-o report.json]

`--file-requisitions` appends `- [ ] KEY — needed by {cards}` under the
checklist's `## Requisitions` for each missing key — the regex owns the
format, so the scanner owns the filing (deduped vs pending + granted).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ENV_KEY_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]+)\s*=")
ENV_IN_CARD_RE = re.compile(r"^- `?([A-Z][A-Z0-9_]+)`?\b", re.M)
REQ_RE = re.compile(r"^- \[(?P<m>[ x])\] (?P<key>[A-Z][A-Z0-9_]+)")


def parse_args():
    p = argparse.ArgumentParser(description="Env var coverage scan.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--env-file", help="default: {project-root}/.env")
    p.add_argument("--file-requisitions", action="store_true",
                   help="append missing keys under ## Requisitions")
    p.add_argument("-o", "--output")
    return p.parse_args()


def env_state(env_file: Path) -> tuple:
    """Return (set-of-real-keys, set-of-temp-keys)."""
    if not env_file.is_file():
        return set(), set()
    real, temp = set(), set()
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ENV_KEY_RE.match(line)
        if not m:
            continue
        (temp if "# TEMP-CDO" in line else real).add(m.group(1))
    return real, temp


def card_externals(orch: Path) -> dict:
    """ENV key -> card that requires it, across archived cards."""
    need = {}
    align = orch / "alignment"
    if not align.is_dir():
        return need
    for f in align.glob("*/*/*/*.md"):
        section = f.read_text(encoding="utf-8", errors="replace")
        block = section.split("## Externals Needed")[-1].split("## ")[0] \
            if "## Externals Needed" in section else ""
        for k in ENV_IN_CARD_RE.findall(block):
            need.setdefault(k, []).append(f.stem)
    return need


def checklist_requisitions(orch: Path) -> tuple:
    f = orch / "alignment-checklist.md"
    if not f.is_file():
        return [], []
    text = re.sub(r"<!--.*?-->", "", f.read_text(encoding="utf-8"), flags=re.S)
    pending, granted = [], []
    in_req = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_req = line.strip().startswith("## Requisitions")
            continue
        if in_req:
            m = REQ_RE.match(line.strip())
            if m:
                (granted if m.group("m") == "x" else pending).append(m.group("key"))
    return pending, granted


def file_requisitions(orch: Path, missing: list, needed: dict,
                      already: set) -> list:
    """Append `- [ ] KEY — needed by {cards}` under `## Requisitions`.

    The checklist regex owns the line format, so the scanner owns the
    filing — keys already pending or granted aren't re-filed. Returns
    the keys actually appended."""
    to_file = [k for k in missing if k not in already]
    if not to_file:
        return []
    f = orch / "alignment-checklist.md"
    lines = f.read_text(encoding="utf-8").splitlines() if f.is_file() else []
    new = [f"- [ ] {k} — needed by {', '.join(needed[k])}" for k in to_file]
    idx = next((i for i, l in enumerate(lines)
                if l.strip().startswith("## Requisitions")), None)
    if idx is None:
        lines += ["", "## Requisitions", "", *new]
    else:
        end = next((i for i in range(idx + 1, len(lines))
                    if lines[i].startswith("## ")), len(lines))
        while end > idx + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = new
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return to_file


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    env_path = Path(args.env_file) if args.env_file else orch.parent.parent / ".env"

    real, temp = env_state(env_path)
    needed = card_externals(orch)
    req_pending, req_granted = checklist_requisitions(orch)
    have = real | temp

    missing = sorted(k for k in needed if k not in have)
    unresolved_req = sorted(set(req_pending))

    filed = file_requisitions(orch, missing, needed,
                              set(req_pending) | set(req_granted)) \
        if args.file_requisitions else []

    result = {
        "status": "ok" if not missing and not temp else "gaps",
        "coverage": {
            "real": sorted(real),
            "temp_placeholders": sorted(temp),
            "missing": missing,
            "missing_for_cards": {k: needed[k] for k in missing},
        },
        "requisitions": {"pending": unresolved_req, "granted": sorted(req_granted)},
        "filed_requisitions": filed,
        "recommendation": [],
    }
    if missing:
        result["recommendation"].append(
            f"filed requisitions for: {filed} — grant + set values"
            if filed else
            f"file requisitions for: {missing} (or grant + set values)"
        )
    if temp:
        result["recommendation"].append(
            f"replace TEMP-CDO placeholders: {temp} — they unblock dispatch "
            "but aren't real credentials"
        )

    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
