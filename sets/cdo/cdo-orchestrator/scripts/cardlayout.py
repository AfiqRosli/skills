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

import re
import subprocess
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
