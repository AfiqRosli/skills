#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Deterministic pre-pass for cdo-align — emits every input the Ground the
Read phase needs as compact JSON, so the prompt layer spends context on
judgment, not on slicing append-only stores by hand.

Emits: scaffold verdicts, the doctrine slice (Standing Policies in full +
newest N decision-log entries) with intent.md staleness, the selected
worklist from backlog markers, a card-corpus index (drafts / archives /
superseded — frontmatter fields only, not bodies), a flow-ledger excerpt,
HEAD commit, and drafts whose grounded_against commit no longer matches
(stale reads waiting to become drift).

Backlog markers: `- [ ]` unaligned, `- [A]` draft filed, `- [?]` undraftable
(disposition recorded; only --story re-selects it).

Usage:
  uv run preflight.py --orchestration-dir /path/docs/orchestration
      [--backlog-dir DIR] [--story KEY | --limit N | --all] [--backlog NAME]
      [--recent N] [-o out.json]

Exit codes: 0=ok, 2=runtime error
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from cardlayout import (  # noqa: E402 — vendored card-layout contract
    card_frontmatter, grounding_stale, head_sha)

ENTRY_RE = re.compile(r"^- \[(?P<mark>[ A?])\] (?P<key>\S+?) — (?P<title>.*)$")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DEFAULT_LIMIT = 10
DECISION_LOG_TAIL = 15


def _section(body: str, name: str) -> str:
    m = re.search(rf"^## {re.escape(name)}\s*$", body or "", flags=re.M)
    if not m:
        return ""
    rest = body[m.end():]
    nxt = re.search(r"^## ", rest, flags=re.M)
    return rest[:nxt.start()] if nxt else rest


def scan_backlogs(backlog_dir: Path, backlog_filter, story_key, limit, warnings):
    """Return (worklist, skipped). `- [ ]` selects; `[A]`/`[?]` skip unless
    --story targets the key (the re-draft / corrected-back path)."""
    worklist, skipped = [], []
    if not backlog_dir.is_dir():
        warnings.append(f"backlog dir missing: {backlog_dir}")
        return worklist, skipped
    for f in sorted(backlog_dir.glob("*.md")):
        if backlog_filter and f.stem != backlog_filter:
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            m = ENTRY_RE.match(line)
            if not m:
                continue
            key, mark = m.group("key"), m.group("mark")
            entry = {"key": key, "title": m.group("title").strip(),
                     "backlog": f.stem, "marker": mark}
            if story_key:
                if key != story_key:
                    continue
            elif mark != " ":
                skipped.append({**entry,
                                "reason": "draft filed" if mark == "A"
                                else "undraftable"})
                continue
            worklist.append(entry)
            if story_key:
                return worklist, skipped
    if story_key and not worklist:
        warnings.append(f"--story {story_key}: no backlog line found")
    return worklist[:limit] if limit else worklist, skipped


def doctrine_slice(orch: Path, warnings) -> dict:
    p = orch / "doctrine.md"
    if not p.is_file():
        warnings.append("doctrine.md missing — proceed and flag: no precedent read")
        return {"path": str(p), "present": False}
    body = p.read_text(encoding="utf-8")
    log = [l for l in _section(body, "Decision Log").splitlines()
           if l.strip().startswith("-")][:DECISION_LOG_TAIL]
    return {
        "path": str(p), "present": True,
        "standing_policies": _section(body, "Standing Policies").strip(),
        "recent_log": log,
        "newest_log_date": (DATE_RE.search(log[0]).group(0)
                            if log and DATE_RE.search(log[0]) else None),
    }


def intent_status(orch: Path, newest_log_date, warnings) -> dict:
    p = orch / "intent.md"
    if not p.is_file():
        warnings.append("intent.md missing — draft one from product docs + "
                        "doctrine before aligning; alignment without a "
                        "baseline is opinion")
        return {"path": str(p), "present": False}
    body = p.read_text(encoding="utf-8")
    m = re.search(r"Refreshed:\s*(\d{4}-\d{2}-\d{2})", body)
    refreshed = m.group(1) if m else None
    return {
        "path": str(p), "present": True, "refreshed": refreshed,
        "stale": bool(refreshed and newest_log_date
                      and newest_log_date > refreshed),
    }


def corpus_index(orch: Path, head: str | None):
    al = orch / "alignment"
    drafts, stale = [], []
    ddir = al / "drafts"
    if ddir.is_dir():
        for f in sorted(ddir.glob("*.md")):
            fm = card_frontmatter(f.read_text(encoding="utf-8"))
            grounded = (fm.get("grounded_against") or {}).get("commit")
            drafts.append({
                "key": fm.get("key") or f.stem, "path": str(f),
                "declared_surface": fm.get("declared_surface") or [],
                "grounded_commit": grounded,
                "no_frontmatter": not fm,
            })
            if grounding_stale(grounded, head or ""):
                stale.append({"key": f.stem, "grounded": grounded,
                              "head": head})
    archived = sorted(
        (f.stem for f in al.glob("[0-9]" * 4 + "/**/*.md")),
    ) if al.is_dir() else []
    parked = sorted(f.stem for f in (al / "parked").glob("*.md")) \
        if (al / "parked").is_dir() else []
    superseded = sorted(f.name for f in (al / "superseded").glob("*.md")) \
        if (al / "superseded").is_dir() else []
    return {"drafts": drafts, "archived": archived, "parked": parked,
            "superseded": superseded}, stale


def ledger_excerpt(orch: Path, recent: int, warnings) -> dict:
    p = orch / "flow-ledger.yaml"
    if not p.is_file():
        warnings.append("flow-ledger.yaml missing — proceed and flag: "
                        "no outcome calibration available")
        return {"path": str(p), "present": False}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        warnings.append(f"flow-ledger.yaml unparseable: {e}")
        return {"path": str(p), "present": False}
    stories = data.get("stories") or {}
    keys = list(stories)[-recent:]
    excerpt = {}
    for k in keys:
        s = stories[k] or {}
        excerpt[k] = {
            "status": s.get("status"), "attempts": s.get("attempts"),
            "verdict": (s.get("delivery_review") or {}).get("verdict"),
            "last_finding": (s.get("findings") or [None])[-1],
        }
    quarantined = [
        {"key": q.get("key"), "reason": q.get("reason")}
        for q in ((data.get("pool") or {}).get("quarantined") or [])
    ]
    return {"path": str(p), "present": True, "stories": excerpt,
            "quarantined": quarantined}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--backlog-dir",
                   help="default: {orchestration-dir}/backlogs")
    p.add_argument("--story", help="re-draft one key regardless of marker")
    p.add_argument("--backlog", help="one backlog file stem only")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--all", action="store_true",
                   help="no limit (headless drain)")
    p.add_argument("--recent", type=int, default=10,
                   help="ledger stories to excerpt (newest N)")
    p.add_argument("-o", "--output")
    args = p.parse_args()

    orch = Path(args.orchestration_dir).resolve()
    warnings: list[str] = []
    checklist = orch / "alignment-checklist.md"
    scaffold = {"checklist": checklist.is_file(),
                "needs_attention": False, "routine_review": False}
    if checklist.is_file():
        text = checklist.read_text(encoding="utf-8")
        scaffold["needs_attention"] = "## Needs Attention" in text
        scaffold["routine_review"] = "## Routine Review" in text
    else:
        warnings.append("checklist missing — run cdo-setup scaffold")

    doctrine = doctrine_slice(orch, warnings)
    intent = intent_status(orch, doctrine.get("newest_log_date"), warnings)
    head = head_sha(Path.cwd()) or None
    if not head:
        warnings.append("git rev-parse HEAD failed — grounded_against.commit "
                        "will be empty; non-git environment")
    corpus, stale = corpus_index(orch, head)
    worklist, skipped = scan_backlogs(
        Path(args.backlog_dir).resolve() if args.backlog_dir
        else orch / "backlogs",
        args.backlog, args.story, None if args.all else args.limit, warnings)

    result = {
        "orchestration_dir": str(orch),
        "scaffold": scaffold,
        "doctrine": doctrine,
        "intent": intent,
        "head_commit": head,
        "worklist": worklist,
        "skipped": skipped,
        "corpus": corpus,
        "stale_drafts": stale,
        "ledger": ledger_excerpt(orch, args.recent, warnings),
        "warnings": warnings,
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
