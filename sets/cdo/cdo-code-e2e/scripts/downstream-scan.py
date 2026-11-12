#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Downstream-impact pre-pass for cdo-code-e2e step 11 (story-sync).

Instead of the orchestrator reading every subsequent story section to hunt
for integration points, this scans the planning epic doc for mentions of
the change set's file stems and reports which story sections they hit —
the LLM then reads only the flagged sections.

Matching is stem-based, not basename: `stores/ThingStore.ts` also matches
prose mentioning `ThingStore` (the store name is how stories reference it).

Usage:
  python downstream-scan.py --epic <epic_doc> --files f1 f2 ...
  [--sprint-status <yaml> --story-key <key>]  (restrict to stories after key)
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitpaths import normalize_changed_paths  # noqa: E402

STORY_HEADING_RE = re.compile(r"^#{2,4}\s+Story\s+([\d.]+)[:\s]", re.M)
DOC_EXTENSIONS = {".md", ".yaml", ".yml", ".txt"}


def story_order(sprint_status: Path) -> list[str]:
    """development_status key order from the sprint yaml."""
    keys: list[str] = []
    for line in sprint_status.read_text(
            encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s{2}([\w-]+):\s*\S+", line)
        if m:
            keys.append(m.group(1))
    return keys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--epic", type=Path, required=True,
                    help="Planning epic doc holding subsequent-story sections")
    ap.add_argument("--files", nargs="*", required=True,
                    help="Changed files (porcelain input normalized; dirs ignored)")
    ap.add_argument("--sprint-status", type=Path, default=None,
                    help="Sprint yaml — with --story-key, restrict scan to stories after it")
    ap.add_argument("--story-key", default=None)
    args = ap.parse_args()

    changed, unparsed = normalize_changed_paths(args.files)
    stems = sorted({
        Path(f).stem for f in changed
        if Path(f).suffix and Path(f).suffix not in DOC_EXTENSIONS
        and len(Path(f).stem) >= 4  # short stems false-positive on prose
    })

    text = args.epic.read_text(encoding="utf-8", errors="replace")
    headings = [(m.group(1), m.start()) for m in STORY_HEADING_RE.finditer(text)]
    sections = []
    for i, (num, start) in enumerate(headings):
        end = headings[i + 1][1] if i + 1 < len(headings) else len(text)
        sections.append({"story": num, "body": text[start:end]})

    restrict: list[str] | None = None
    if args.sprint_status and args.story_key:
        order = story_order(args.sprint_status)
        try:
            idx = order.index(args.story_key)
            restrict = order[idx + 1:]
        except ValueError:
            restrict = []

    flagged = []
    for sec in sections:
        hits = sorted({s for s in stems
                       if re.search(rf"\b{re.escape(s)}\b", sec["body"])})
        entry = {"story": sec["story"], "matched_stems": hits}
        if restrict is not None:
            entry["after_current"] = any(
                k.startswith(sec["story"].replace(".", "-")) for k in restrict)
        if hits:
            flagged.append(entry)

    result = {
        "script": "downstream-scan", "version": "1.0.0",
        "status": "pass",
        "epic": str(args.epic),
        "sections_scanned": len(sections),
        "stems": stems,
        "flagged_sections": flagged,
        "unparsed_input": unparsed,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
