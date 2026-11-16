#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""feed.py — inbound-only content intake from shipped work.

Scans flow-ledger.yaml for stories with status done/verified/shipped whose
key doesn't yet appear in backlogs/content.md, and appends unaligned
content candidates: `- [ ] CT{n} — {title} | source: {key} | kind: post|guide`.

The growth office writes inbound content only — this script is what makes
the source material arrive on its own.

Usage:
  uv run feed.py --orchestration-dir /path/docs/orchestration [-o result.json]

Exit codes: 0=fed (or nothing new), 2=error
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

DONE_STATUSES = {"done", "verified", "shipped"}
KEY_LINE_RE = re.compile(r"^- \[[ xA\-]\] (\S+?)\b")


def parse_args():
    p = argparse.ArgumentParser(description="Feed content backlog from shipped work.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("-o", "--output")
    return p.parse_args()


def next_ct_key(existing: str) -> str:
    nums = [int(m.group(1)) for m in re.finditer(r"\bCT(\d+)\b", existing)]
    return f"CT{max(nums, default=0) + 1}"


def story_title(orch: Path, key: str) -> str:
    """Best-effort title: archived card's first heading, else the key."""
    for c in orch.glob(f"alignment/*/*/*/{key}.md"):
        for line in c.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    for c in orch.glob(f"alignment/drafts/{key}.md"):
        for line in c.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return key


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    lpath = orch / "flow-ledger.yaml"
    if not lpath.is_file():
        print(json.dumps({"errors": ["flow-ledger.yaml missing"]}))
        sys.exit(2)
    ledger = yaml.safe_load(lpath.read_text(encoding="utf-8")) or {}
    stories = ledger.get("stories") or {}

    bfile = orch / "backlogs" / "content.md"
    bfile.parent.mkdir(parents=True, exist_ok=True)
    existing = bfile.read_text(encoding="utf-8") if bfile.is_file() else \
        "# Content Backlog\n\n## Items\n\n"

    fed = []
    for key, st in sorted(stories.items()):
        if not isinstance(st, dict) or st.get("status") not in DONE_STATUSES:
            continue
        # token-boundary — backlog holding `source: S12` must not swallow S1
        if re.search(rf"\b{re.escape(key)}\b", existing):
            continue  # already represented in the backlog
        ct = next_ct_key(existing)
        title = story_title(orch, key)
        line = f"- [ ] {ct} — {title} | source: {key} | kind: post\n"
        existing = existing.rstrip("\n") + "\n" + line
        fed.append({"key": ct, "source": key, "title": title})

    if fed:
        bfile.write_text(existing, encoding="utf-8")

    result = {"status": "fed" if fed else "no_new",
              "items_added": fed,
              "done_stories_seen": sum(1 for s in stories.values()
                                     if isinstance(s, dict)
                                     and s.get("status") in DONE_STATUSES)}
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
