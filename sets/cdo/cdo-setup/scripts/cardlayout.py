#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Shared alignment-card filesystem layout for cdo scripts — the ONE
definition of where a card is allowed to live and what each bay means:

    alignment/drafts/{key}.md               unreviewed drafts
    alignment/parked/{key}.md               consciously deferred —
                                            "looked at, not now"
    alignment/reviews/{key}.review-{n}.md   Operator-pending delivery
                                            reviews — the verdict on the
                                            filed line graduates the doc
                                            beside the card it judged
    alignment/superseded/                   frozen history — re-filed or
                                            unparked copies
    alignment/YYYY/MM/DD/{key}.md           confirmed/rejected archive —
                                            the contract that authorized
                                            the work

Every script that filters a card glob, derives a staging path, or reads
card metadata must come through here — an inline copy of this taxonomy
drifted once already (dispatch picked arbitrary archives, state-digest
the oldest). Vendored per skill's scripts/ dir like gitpaths.py: when you
change this file, copy it to every scripts/ dir that carries it.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # script still degrades — frontmatter reads return {}
    yaml = None

# The four holding bays — anything under these is NOT an archived card.
BAYS = frozenset({"drafts", "parked", "reviews", "superseded"})

# A rejected card is archived for audit but authorizes nothing — the
# verdict comment rides line 1 (archive stamps prepend; parked/deferred
# stamps insert after frontmatter instead — see apply-decisions).
REJECT_HEAD_RE = re.compile(r"\s*<!--\s*reject")

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
CONF_RE = re.compile(r"- \*\*Confidence:\*\* (\d+)%")
TITLE_RE = re.compile(r"^#\s+Alignment Card\s+—\s+\S+?:\s*(.+)$", re.M)
SOURCE_RE = re.compile(r"- \*\*Source:\*\* `([^`]+)`")

# Checklist checkbox line carrying a card/story key — the format
# file-cards.py writes, apply-decisions.py resolves, delivery-note.py
# dedupes, and watch.py inventories. One regex, one contract.
CHECKBOX_KEY_RE = re.compile(r"^- \[(?P<mark>[ xA\-])] (?P<key>\S+?) — ",
                             re.M)


def is_bay(path: Path) -> bool:
    """Path sits inside a holding bay — never an archived card."""
    return bool(BAYS & set(path.parts))


def confirmed_card(orch: Path, key: str):
    """The card that authorized the work — the NEWEST non-reject archive
    under alignment/YYYY/MM/DD/ (a re-confirmed key benchmarks against
    its later card). Holding bays authorize nothing; rejected archives
    carry `<!-- reject` on line 1; cards with no verdict comment (hand-
    archived, legacy) count as confirmed. Path or None."""
    for f in sorted((orch / "alignment").glob(f"**/{key}.md"),
                    reverse=True):
        if is_bay(f):
            continue
        head = f.read_text(encoding="utf-8", errors="replace")[:200]
        if REJECT_HEAD_RE.match(head):
            continue
        return f
    return None


def staged_review_doc(orch: Path, key: str, attempt: int) -> Path:
    """The Operator-pending staging path — an r-{key} session writes
    here, delivery-note files the line pointing at it, and the verdict
    on that line (apply-decisions) graduates it beside the card."""
    return (orch / "alignment" / "reviews"
            / f"{key}.review-{attempt}.md")


def card_frontmatter(body: str) -> dict:
    """The card's YAML frontmatter — {} when absent/unparseable (a card
    whose stamp landed BEFORE the `---` reads as frontmatterless — the
    deferred-stamp placement bug this module exists to prevent)."""
    if yaml is None:
        return {}
    m = FRONTMATTER_RE.match(body or "")
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def grounded_commit(body: str) -> str:
    """`grounded_against.commit` from card frontmatter — '' when absent."""
    g = card_frontmatter(body).get("grounded_against") or {}
    return str(g.get("commit") or "") if isinstance(g, dict) else ""


def head_sha(root: Path) -> str:
    """`git rev-parse HEAD` at the project root — '' when unreachable."""
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                              capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def grounding_stale(grounded: str, head: str) -> bool:
    """grounded_against diverged from HEAD — prefix-tolerant (short vs
    long sha). False when either side is empty (can't prove staleness)."""
    return bool(grounded and head
                and not head.startswith(grounded)
                and not grounded.startswith(head))


def card_title(body: str) -> str:
    m = TITLE_RE.search(body or "")
    return m.group(1).strip() if m else ""


def card_backlog(body: str) -> str:
    """Backlog file stem from the card's `- **Source:**` line."""
    m = SOURCE_RE.search(body or "")
    return m.group(1).split("/")[-1].replace(".md", "") if m else "code"


def card_confidence(body: str):
    """Declared confidence percent — None when absent."""
    m = CONF_RE.search(body or "")
    return int(m.group(1)) if m else None


# ---- Visual Preview / mock-assets contract -----------------------------
# The ONE definition of the Visual Preview line shapes and the
# assets/{key}/ staging taxonomy — file-cards writes these lines,
# apply-decisions rewrites them on every lifecycle move, resolve-item
# parses them. All three must read the same shapes or the pointer rots.

MOCK_FILENAME = "mock.html"

# Line shapes — column-0 anchored on BOTH sides: a stale indented
# `  - **Mock:**` line must not survive a writer's replace and then win
# a reader's first-match scan.
WIREFRAME_VALUE_RE = re.compile(r"^- \*\*Wireframe:\*\*\s*(.+)$", re.M)
MOCK_LINE_RE = re.compile(r"^- \*\*Mock:\*\*.*$", re.M)
MOCK_VALUE_RE = re.compile(r"^- \*\*Mock:\*\*\s*(.+)$", re.M)

# Visual Preview status vocabulary — sentinels match by PREFIX; the
# reason trails the em-dash (`unavailable — mock file missing: …`).
VP_NO_UI = "n/a — no UI surface"
VP_UNAVAILABLE = "unavailable — "

# Execution Surface token enum — filing (file-cards) and resolution
# (resolve-item) share it; a token set that drifts between producer and
# consumer silently mis-routes.
RISK_TOKENS = {"none", "schema-migration", "deps-changed",
               "env-changed", "api-contract", "data-backfill"}


def section(body: str, name: str) -> str:
    """Body of a `## name` section up to the next `## ` — section-scoped
    card parsing so prose elsewhere never reads as a declaration."""
    m = re.search(rf"^## {re.escape(name)}\s*$", body or "", flags=re.M)
    if not m:
        return ""
    rest = body[m.end():]
    nxt = re.search(r"^## ", rest, flags=re.M)
    return rest[:nxt.start()] if nxt else rest


def assets_dir(bay_root: Path, key: str) -> Path:
    """`{bay}/assets/{key}` — the card's visual-design asset bay, wherever
    the card sits (drafts/parked/dated-archive/superseded stamp)."""
    return bay_root / "assets" / key


def draft_mock_rel(key: str) -> str:
    """The orch-relative Mock pointer a freshly filed card carries —
    file-cards writes it; every move retargets it via retarget_mock."""
    return f"alignment/drafts/assets/{key}/{MOCK_FILENAME}"


def superseded_assets(superseded: Path, key: str, stamp: str,
                      suffix: str = "") -> Path:
    """`superseded/{key}.{stamp}[.suffix].assets` — the mock archive that
    rides beside the frozen card copy."""
    return superseded / f"{key}.{stamp}{suffix}.assets"


def set_mock_line(body: str, text: str) -> str:
    """Set/replace the `- **Mock:**` line inside `## Visual Preview` —
    after the Wireframe line when present, else appended to the section.
    Writers own this line so the cited path stays truthful; a missing
    section returns the body unchanged (the caller decides the warn).
    The insert index is guarded — a terminal Wireframe line with no
    trailing newline can't crash mid-drain."""
    sec = section(body, "Visual Preview")
    if not sec:
        return body
    line = f"- **Mock:** {text}"
    new_sec, n = MOCK_LINE_RE.subn(lambda _: line, sec, count=1)
    if not n:
        m = WIREFRAME_VALUE_RE.search(new_sec)
        if m:
            nl = new_sec.find("\n", m.end())
            at = (nl + 1) if nl != -1 else len(new_sec)
            new_sec = new_sec[:at] + line + "\n" + new_sec[at:]
        else:
            new_sec = new_sec.rstrip("\n") + "\n" + line + "\n"
    return body.replace(sec, new_sec, 1)


def retarget_mock(body: str, key: str, new_assets_rel: str) -> str:
    """Re-point the card's Mock line after its assets moved to
    `{new_assets_rel}` (orch-relative) — preserves the pointer tail
    (`mock.html`, `mock/` dir, or a named file) across hops. Sentinel
    values (n/a, unavailable — reason, anything not under assets/{key}/)
    pass through untouched."""
    m = MOCK_VALUE_RE.search(body or "")
    if not m:
        return body
    old = m.group(1).strip().strip("`")
    marker = f"assets/{key}/"
    if marker not in old:
        return body
    tail = old.split(marker, 1)[1]
    new_val = f"{new_assets_rel}/{tail}" if tail else new_assets_rel
    return set_mock_line(body, new_val)


def main() -> None:
    """Self-describing CLI: dump the layout contract, or resolve one key.

      uv run cardlayout.py                     # the contract as JSON
      uv run cardlayout.py --orchestration-dir <orch> <key>
    """
    p = argparse.ArgumentParser(
        description="The cdo alignment-card layout contract — bays, archive "
                    "shape, and per-key path resolution.")
    p.add_argument("key", nargs="?", help="card/story key to resolve")
    p.add_argument("--orchestration-dir", "-d",
                   help="orchestration root (required with a key)")
    p.add_argument("-o", "--output", help="write JSON to file instead of stdout")
    args = p.parse_args()

    if not args.key:
        out = {
            "contract": {
                "bays": sorted(BAYS),
                "archive": "alignment/YYYY/MM/DD/{key}.md",
                "review_staging": "alignment/reviews/{key}.review-{n}.md",
                "assets": "{bay}/assets/{key}/",
                "mock_file": MOCK_FILENAME,
                "risk_tokens": sorted(RISK_TOKENS),
                "visual_preview_sentinels": [VP_NO_UI, VP_UNAVAILABLE + "<reason>"],
            }
        }
        code = 0
    else:
        if not args.orchestration_dir:
            print(json.dumps({"errors": [
                "--orchestration-dir is required when resolving a key"]}))
            sys.exit(2)
        orch = Path(args.orchestration_dir).resolve()
        card = confirmed_card(orch, args.key)
        out = {
            "key": args.key,
            "confirmed_card": (
                str(card.relative_to(orch)).replace("\\", "/")
                if card else None),
            "review_staging": str(
                staged_review_doc(orch, args.key, 1)
                .relative_to(orch)).replace("\\", "/"),
            "status": "confirmed" if card else "absent",
        }
        code = 0 if card else 1

    blob = json.dumps(out, indent=2)
    if args.output:
        Path(args.output).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
