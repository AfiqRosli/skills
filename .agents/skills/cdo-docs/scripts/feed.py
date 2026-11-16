#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""feed.py — inbound docs intake from shipped work.

Scans flow-ledger.yaml for stories with status done/verified/shipped whose
key doesn't yet appear in backlogs/docs.md, and appends unaligned docs
candidates: `- [ ] DOC{n} — {title} | source: {key} | type: guide | attempt: N`.

Attempt-aware: when a story's `attempts` exceeds the `attempt:` recorded on
its DOC line, the doc is stale. An open `- [ ]`/`[A]` item gets its attempt
bumped + `| re-attempted: N` flag; a consumed `[x]`/`[-]` item gets a fresh
refresh item so the rewrite goes through alignment like everything else.

Shipped work is docs debt until documented — this script makes sure it's
*considered*. Alignment decides doc-worthiness; feed only enqueues.

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


def parse_args():
    p = argparse.ArgumentParser(description="Feed docs backlog from shipped work.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("-o", "--output")
    return p.parse_args()


def next_doc_key(existing: str) -> str:
    nums = [int(m.group(1)) for m in re.finditer(r"\bDOC(\d+)\b", existing)]
    return f"DOC{max(nums, default=0) + 1}"


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


ATTEMPT_RE = re.compile(r"\| attempt: (\d+)")


def doc_attempt_for(existing: str, key: str):
    """Highest attempt number on any DOC line citing this key; None when the
    key has no DOC line. `source: K` matched on token boundary — a line for
    S12 must not swallow S1."""
    best = None
    for line in existing.splitlines():
        if not re.search(rf"source: {re.escape(key)}\b", line):
            continue
        m = ATTEMPT_RE.search(line)
        a = int(m.group(1)) if m else 1  # legacy line, pre-attempt tracking
        best = a if best is None else max(best, a)
    return best


def refresh_open_item(existing: str, key: str, cur: int):
    """Bump an open `- [ ]`/`[A]` DOC line for `key` to attempt `cur` and flag
    it re-attempted — one item, marked for refresh. Returns updated text."""
    lines = existing.splitlines()
    for i, l in enumerate(lines):
        if not re.search(rf"source: {re.escape(key)}\b", l):
            continue
        if not re.match(r"^- \[[ A]\]", l):
            continue
        if ATTEMPT_RE.search(l):
            l = ATTEMPT_RE.sub(f"| attempt: {cur}", l)
        else:
            l += f" | attempt: {cur}"
        l = re.sub(r"\| re-attempted: \d+", "", l).rstrip()
        l += f" | re-attempted: {cur}"
        lines[i] = l
        break
    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    lpath = orch / "flow-ledger.yaml"
    if not lpath.is_file():
        print(json.dumps({"errors": ["flow-ledger.yaml missing"]}))
        sys.exit(2)
    ledger = yaml.safe_load(lpath.read_text(encoding="utf-8")) or {}
    stories = ledger.get("stories") or {}

    bfile = orch / "backlogs" / "docs.md"
    bfile.parent.mkdir(parents=True, exist_ok=True)
    existing = bfile.read_text(encoding="utf-8") if bfile.is_file() else \
        "# Docs Backlog\n\n## Items\n\n"

    fed, refreshed = [], []
    for key, st in sorted(stories.items()):
        if not isinstance(st, dict) or st.get("status") not in DONE_STATUSES:
            continue
        cur = int(st.get("attempts") or 1)
        seen_at = doc_attempt_for(existing, key)
        title = story_title(orch, key)
        if seen_at is None:
            doc = next_doc_key(existing)
            line = (f"- [ ] {doc} — {title} | source: {key} | type: guide"
                    f" | attempt: {cur}\n")
            existing = existing.rstrip("\n") + "\n" + line
            fed.append({"key": doc, "source": key, "title": title})
        elif cur > seen_at:
            if re.search(rf"^- \[[ A]\] DOC\d+ — .*source: {re.escape(key)}\b",
                         existing, flags=re.M):
                existing = refresh_open_item(existing, key, cur)
                refreshed.append({"source": key, "attempt": cur,
                                  "action": "flagged-open-item"})
            else:
                doc = next_doc_key(existing)
                t = f"{title} (refresh — attempt {cur})"
                line = (f"- [ ] {doc} — {t} | source: {key} | type: guide"
                        f" | attempt: {cur}\n")
                existing = existing.rstrip("\n") + "\n" + line
                fed.append({"key": doc, "source": key, "title": t})
                refreshed.append({"source": key, "attempt": cur,
                                  "action": "new-refresh-item"})

    if fed or refreshed:
        bfile.write_text(existing, encoding="utf-8")

    result = {"status": "fed" if (fed or refreshed) else "no_new",
              "items_added": fed,
              "refreshed": refreshed,
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
