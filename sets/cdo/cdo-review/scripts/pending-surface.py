#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""pending-surface.py — the Operator review agenda as deterministic JSON.

Replaces hand-assembly of the pending surface: parses
alignment-checklist.md into per-section item lists (key, mark, trailing
metadata fields), surfaces the parked inventory, flags an interrupted
staged-verdicts file, and counts staged review docs — everything the
Present pass renders, none of it derived by the LLM.

Usage:
  uv run pending-surface.py --orchestration-dir {orch} [-o out.json]
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from cardlayout import CHECKBOX_KEY_RE, BAYS  # noqa: E402

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
META_RE = re.compile(r"\|\s*([a-zA-Z_-]+):\s*([^|]+)")


def parse_checklist(text: str) -> dict:
    """Sections -> pending items. Each item: key, section, the free text
    between `key — ` and the first `|` (title/note), plus `| k: v` meta
    fields flattened (draft, review, verdict, conf, wire, lane, filed)."""
    sections = {}
    current = None
    for line in text.splitlines():
        h = SECTION_RE.match(line.strip())
        if h:
            current = h.group(1)
            sections.setdefault(current, [])
            continue
        m = CHECKBOX_KEY_RE.match(line)
        if not m:
            continue
        rest = line[m.end():]
        head, _, tail = rest.partition("|")
        meta = {k.strip(): v.strip() for k, v in META_RE.findall(tail)}
        item = {"key": m.group("key"), "mark": m.group("mark"),
                "section": current, "text": head.strip(" —"),
                "meta": meta, "line": line.strip()}
        if m.group("mark") == " ":
            sections[current].append(item)
    return sections


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("-o", "--output")
    args = p.parse_args()
    orch = Path(args.orchestration_dir).resolve()

    out = {"status": "ok", "generated_at":
           datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")}

    cl = orch / "alignment-checklist.md"
    sections = parse_checklist(
        cl.read_text(encoding="utf-8", errors="replace")) \
        if cl.is_file() else {}
    out["checklist_present"] = cl.is_file()
    out["sections"] = sections
    out["pending_count"] = sum(len(v) for v in sections.values())

    staged = orch / "pending-decisions.jsonl"
    if staged.is_file():
        out["staged_decisions"] = {
            "path": "pending-decisions.jsonl",
            "lines": sum(1 for l in
                         staged.read_text(encoding="utf-8").splitlines()
                         if l.strip()),
            "warning": "verdicts staged but never applied — apply or "
                       "discard before collecting new decisions"}

    parked = orch / "alignment" / "parked"
    if parked.is_dir():
        inv = []
        for f in sorted(parked.glob("*.md")):
            m = re.search(r"<!-- deferred (\d{4}-\d{2}-\d{2})",
                          f.read_text(encoding="utf-8", errors="replace"))
            inv.append({"key": f.stem,
                        "deferred": m.group(1) if m else None})
        if inv:
            out["parked"] = inv

    reviews = orch / "alignment" / "reviews"
    if reviews.is_dir():
        docs = [f.name for f in reviews.glob("*.md")]
        out["staged_reviews"] = docs
        out["staged_review_count"] = len(docs)

    blob = json.dumps(out, indent=2)
    if args.output:
        Path(args.output).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(0)


if __name__ == "__main__":
    main()
