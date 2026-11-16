#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Fork-drift check — vendored `.agents/skills/cdo-*` vs `.devin/skills/code-*`.

The cdo-* owner skills are verbatim forks of the .devin originals, retargeted
onto the cdo-* chain ("upstream changes do not propagate; port fixes
deliberately"). Nothing enforces the port — this script measures it: each
pair is diffed after name normalization, so remaining differences are real
content drift (fixes that landed in one tree only, contract edits, deletions).

Status per pair:
  in-sync           normalized files identical
  drifted           content differs — inspect diff_lines samples
  missing-copy      original exists, no vendored copy (a silent fallback risk)
  missing-original  vendored copy exists, original gone (orphaned fork)

Usage:
  uv run fork-drift.py [--project-root PATH] [-o report.json]

Exit codes: 0=all pairs in-sync, 1=drift detected, 2=runtime error
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

# original (.devin/skills/) → vendored (.agents/skills/)
PAIRS = {
    "code-e2e": "cdo-code-e2e",
    "code-alignment-uncommitted-changes": "cdo-alignment-uncommitted-changes",
    "code-security-audit-uncommitted-changes":
        "cdo-security-audit-uncommitted-changes",
    "code-review-implement-refinement": "cdo-review-implement-refinement",
    "documentation": "cdo-documentation",
    "code-git-push": "cdo-git-push",
    "code-git-quick-push": "cdo-git-quick-push",
    "code-git-pr-message": "cdo-git-pr-message",
    "code-version-change-for-production": "cdo-version-change-for-production",
    "project-version-upgrade": "cdo-version-upgrade",
}

# vendored → original, longest-first so cdo-git-quick-push normalizes
# before cdo-git-push
_V2O = dict((v, k) for k, v in PAIRS.items())
_VENDORED_NAMES = sorted(PAIRS.values(), key=len, reverse=True)

# secondary files diffed per pair: (original rel-path, vendored rel-path).
# Pairs whose workflow content lives outside SKILL.md would otherwise be
# invisible to the drift check (the bulk of a carved skill's content).
SECONDARY = {
    "project-version-upgrade": [
        ("workflow.md", "references/workflow.md"),
    ],
}


def _normalize(text: str) -> str:
    """Map vendored `cdo-*` names back to their `.devin` originals so a pure
    retarget diffs clean — remaining differences are real content drift."""
    for v in _VENDORED_NAMES:
        text = text.replace(v, _V2O[v])
    return text


def _pair_status(original: Path, vendored: Path) -> dict:
    label = vendored.parent.name
    if not vendored.is_file():
        return {"vendored": label, "original": original.parent.name,
                "status": "missing-copy", "diff_lines": 0, "sample": []}
    if not original.is_file():
        return {"vendored": label, "original": original.parent.name,
                "status": "missing-original", "diff_lines": 0, "sample": []}
    a = original.read_text(encoding="utf-8", errors="replace").splitlines()
    b = _normalize(
        vendored.read_text(encoding="utf-8", errors="replace")).splitlines()
    diff = [l for l in difflib.unified_diff(a, b, lineterm="")
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    status = "in-sync" if not diff else "drifted"
    return {"vendored": label, "original": original.parent.name,
            "status": status, "diff_lines": len(diff),
            "sample": diff[:10]}


def check_forks(root: Path) -> list:
    out = []
    for original, vendored in PAIRS.items():
        entry = _pair_status(
            root / ".devin" / "skills" / original / "SKILL.md",
            root / ".agents" / "skills" / vendored / "SKILL.md")
        entry["file"] = "SKILL.md"
        out.append(entry)
        for o_rel, v_rel in SECONDARY.get(original, []):
            sub = _pair_status(
                root / ".devin" / "skills" / original / o_rel,
                root / ".agents" / "skills" / vendored / v_rel)
            sub["file"] = o_rel
            out.append(sub)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--project-root", default=".")
    p.add_argument("-o", "--output")
    args = p.parse_args()
    root = Path(args.project_root).resolve()
    for q in [root, *root.parents]:
        if (q / "_bmad").is_dir():
            root = q
            break

    pairs = check_forks(root)
    drifted = [d for d in pairs if d["status"] != "in-sync"]
    result = {"script": "fork-drift", "status": "drift" if drifted else "in-sync",
              "pairs": pairs, "drifted": len(drifted)}
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    sys.exit(1 if drifted else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
