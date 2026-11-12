#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""resolve-item.py — the shared per-key evidence digest. Every reference that
says "read the card + ledger entry + backlog line + signals" narrates the same
four-file gather — this script is the one deterministic place it happens.

Usage:
  uv run resolve-item.py --orchestration-dir /path/docs/orchestration {key}
      [-o digest.json]

Emits JSON: {key, resolved_key, ledger: {...}, card_path, card_status, card_body,
card: {declared, unknown_tokens, wireframe, wireframe_status},
backlog: {file, line}, signals: [...]} — None for anything absent.
Consumers judge; this script fetches.

`key` may be a sprint story key (02-01-utm-parameter-tracking — the
canonical backlog/ledger key), a dept item key (CT1, P7), or a bare NN-NN
story prefix — the last is mapped to the backlog line whose key carries
that prefix when direct lookup finds nothing.

card_status: draft (under alignment/drafts/) | confirmed (dated archive,
no reject head) | rejected (archive opens <!-- reject) | absent.
Only `confirmed` authorizes card-covered bypasses — everything else is
unsigned. declared[] is parsed only from the `## Execution Surface`
section's `- **Risk surface:**` line; wireframe only from `## Visual
Preview`. Section-scoped: token prose elsewhere in the card never counts.

Exit codes: 0=resolved, 1=key not found anywhere, 2=runtime error
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


# Gate-bypass tokens (only these authorize card-covered bypass):
#   schema-migration, deps-changed
# Attention-only tokens (declared = Needs Attention routing; no bypass):
#   env-changed, api-contract, data-backfill
RISK_TOKENS = {"none", "schema-migration", "deps-changed",
               "env-changed", "api-contract", "data-backfill"}
WIRETEXT_RE = re.compile(r"https://wiretext\.app/w/[A-Za-z0-9_-]+")
REJECT_HEAD_RE = re.compile(r"^\s*<!--\s*reject", re.M)
BACKLOG_ITEM_RE = re.compile(r"^- \[.\] (\S+)")
SECTION_RE = re.compile(r"^## ", re.M)


def _section(body: str, name: str) -> str:
    """Return the body of a '## name' section (up to the next '## ')."""
    m = re.search(rf"^## {re.escape(name)}\s*$", body, flags=re.M)
    if not m:
        return ""
    rest = body[m.end():]
    nxt = SECTION_RE.search(rest)
    return rest[:nxt.start()] if nxt else rest


def _parse_card(body: str) -> dict:
    """Extract the machine-checkable fields from a card body — section-scoped
    so prose mentions elsewhere never read as declarations."""
    surf = _section(body, "Execution Surface")
    tokens, unknown = [], []
    m = re.search(r"- \*\*Risk surface:\*\*\s*(.+)", surf)
    if m:
        for tok in re.split(r"[,\s]+", m.group(1).strip().strip("`")):
            tok = tok.strip().strip("`").lower()
            if not tok:
                continue
            (tokens if tok in RISK_TOKENS else unknown).append(tok)
    if "none" in tokens:
        tokens = [t for t in tokens if t != "none"]

    vp = _section(body, "Visual Preview")
    wm = WIRETEXT_RE.search(vp)
    if wm:
        wstatus, wire = "url", wm.group(0)
    elif re.search(r"no UI surface", vp):
        wstatus, wire = "no-ui-surface", None
    elif re.search(r"unavailable", vp):
        wstatus, wire = "unavailable", None
    else:
        wstatus, wire = "absent", None
    return {"declared": tokens, "unknown_tokens": unknown,
            "wireframe": wire, "wireframe_status": wstatus}


def _card_status(orch: Path, card: Path, body: str) -> str:
    try:
        rel = card.relative_to(orch).as_posix()
    except ValueError:
        rel = str(card)
    if "/drafts/" in rel:
        return "draft"
    if "/parked/" in rel:
        return "parked"
    return "rejected" if REJECT_HEAD_RE.match(body) else "confirmed"


def _find_item_key_by_story(orch: Path, story_prefix: str):
    """Map a bare story prefix (02-01) to the leading key of the backlog line
    that carries it — `- [x] 02-01-utm-… — title` → `02-01-utm-…`."""
    bd = orch / "backlogs"
    if not bd.is_dir():
        return None
    story_re = re.compile(rf"\b{re.escape(story_prefix)}\b")
    for f in sorted(bd.glob("*.md")):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            im = BACKLOG_ITEM_RE.match(line.strip())
            if im and story_re.search(line):
                return im.group(1)
    return None


def _resolve(orch: Path, key: str, digest: dict):
    keyre = re.compile(rf"\b{re.escape(key)}\b")

    # ledger story record
    lpath = orch / "flow-ledger.yaml"
    if lpath.is_file():
        ledger = yaml.safe_load(lpath.read_text(encoding="utf-8")) or {}
        digest["ledger"] = (ledger.get("stories") or {}).get(key)
        digest["signals"] = [s for s in ledger.get("signals") or []
                             if isinstance(s, dict) and s.get("key") == key]
        if digest["ledger"]:
            digest["found"] = True

    # alignment card — drafts first, then parked, then the dated archive
    card = None
    draft = orch / "alignment" / "drafts" / f"{key}.md"
    parked = orch / "alignment" / "parked" / f"{key}.md"
    if draft.is_file():
        card = draft
    elif parked.is_file():
        card = parked
    else:
        archived = sorted((orch / "alignment").glob(f"**/{key}.md")) \
            if (orch / "alignment").is_dir() else []
        card = archived[-1] if archived else None
    if card:
        body = card.read_text(encoding="utf-8")
        digest["card_path"] = str(card.relative_to(orch)).replace("\\", "/")
        digest["card_body"] = body
        digest["card_status"] = _card_status(orch, card, body)
        digest["card"] = _parse_card(body)
        digest["found"] = True

    # backlog line — token-boundary key match across all backlogs
    bd = orch / "backlogs"
    if bd.is_dir():
        for f in sorted(bd.glob("*.md")):
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if keyre.search(line) and line.strip().startswith("- ["):
                    digest["backlog"] = {"file": f.name, "line": line.strip()}
                    digest["found"] = True
                    break
            if "backlog" in digest:
                break


def parse_args():
    p = argparse.ArgumentParser(description="Resolve an item key into its evidence digest.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("key")
    p.add_argument("-o", "--output")
    return p.parse_args()


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    key = args.key
    keyre = re.compile(rf"\b{re.escape(key)}\b")

    digest = {"key": key, "found": False}
    _resolve(orch, key, digest)

    # story-slug fallback — a NN-NN story key (02-01-some-title) maps to the
    # backlog item whose title carries the same NN-NN prefix
    if not digest["found"]:
        m = re.match(r"(\d+-\d+)", key)
        if m:
            item_key = _find_item_key_by_story(orch, m.group(1))
            if item_key:
                digest["resolved_key"] = item_key
                _resolve(orch, item_key, digest)

    out = json.dumps(digest, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    sys.exit(0 if digest["found"] else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
