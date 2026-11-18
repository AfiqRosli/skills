#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml>=6.0"]
# ///
"""File drafted alignment cards into the Operator checklist — deterministic surgery.

Takes a cards JSON (array produced by the prompt layer, or an envelope
{"cards": [...], "undraftable": [...], "gaps": [...]}), then:

  1. validates every card up front — named errors, no half-filed runs
  2. writes each card body to `alignment/drafts/{key}.md`
  3. appends a one-line entry to `alignment-checklist.md` under
     "## Needs Attention" (flagged, open asks, declared risk surface, or
     low confidence) or "## Routine Review", sorted ascending by confidence
  4. flips the backlog marker `- [ ]`/`[?]` -> `- [A]` (alignment pending)
     so items aren't redrafted; `undraftable` entries flip `- [ ]` -> `- [?]`
  5. appends `gaps` to `alignment/gap-findings.md` and writes a run receipt
     to `alignment/last-run.json` — when cards filed, the receipt carries
     `suggest: cdo-review`, an advisory next-leg pointer for the pipeline
     driver (skills don't spawn successors)

Idempotent by card key — re-running replaces the draft file and checklist line.

Usage:
  uv run file-cards.py --orchestration-dir /path/docs/orchestration
      --cards cards.json [--backlog-map '{"code": "backlogs/code.md"}']
      [--backlog-dir DIR] [--attention-threshold 80] [--dry-run] [-o out.json]

`--backlog-map` is the cdo:backlog_map config value as JSON — orch-relative
paths; the script resolves where each backlog file lives itself (entries may
sit outside {orch}/backlogs; unmapped stems fall back to --backlog-dir).
`--backlog-dir` remains the manual override when no map is passed.

Cards JSON: a bare array, or an envelope
{"cards": [...], "undraftable": [{key, reason, backlog}], "gaps": [...]} —
undraftable entries flip `- [ ]` -> `- [?]`; gaps append to
alignment/gap-findings.md.
Card objects: {"key","title","backlog","confidence","flags":[...],
               "asks": 0, "body": "...",
               "wireframe": "https://wiretext.app/w/…",
               "mock": "/path/to/mock.html"}
`asks` is derived from the card's Questions section; a supplied count that
disagrees warns and the derived count wins — a card's asks>0 → Needs Attention.
Contract checks enforced at filing (not trusted to the prompt layer):
  - every template-required `##` section must be present and non-empty —
    a section-less card is a named validation error
  - frontmatter `grounded_against.commit` must be non-empty (an empty
    commit goes dark to staleness detection); commit != HEAD warns
  - frontmatter `declared_surface` must equal the Execution Surface tokens
  - the `P&D co-sign:` stamp must be the contracted line
    `- **P&D co-sign:** {verdict}` — a substring mention or the template's
    unsubstituted `{...}` placeholder is not a signature
  - Questions bullets count unless they match the `None —` sentinel shape
    (a real question phrased "None of the …" still counts)
`wireframe` is optional — when absent, a wiretext URL is recovered from the
card body's Visual Preview section if present. `mock` is optional — a path to
a produced HTML mock (file or directory), staged under
`alignment/drafts/assets/{key}/` with the card's `**Mock:**` line set to the
staged path; relative paths anchor to the --cards file's directory; a
missing path degrades to `unavailable` with a warning, never fatal.
Draft-completeness gate: a produced or attempted Wireframe (URL or
`unavailable` — attempting presupposes a surface) beside Mock
`n/a`/absent is a named validation error — the card is not
draft-complete and the batch fails before anything files. The mirror is
advisory: a produced mock beside Wireframe `n/a`/absent flags
`wire-missing` → Needs Attention (the wire's gate is downstream).
`unavailable — {reason}` is an honest claim on either side — never an
error, and never an excuse for the other side's `n/a`.
A file mock's health floor warns on: non-HTML/tiny bodies, external asset
refs, placeholder styling (→ `ungrounded:design-tokens`), and a header
comment declaring no environment frame (`browser:{route}` |
`phone:{host-app|bare}` — the env choice stays prompt-side judgment; the
declaration's presence is the fixed-shape check).
Sizing catch: `**Sizing:** full` with >=3 distinct frontmatter `touches`
entries trips the `oversized` signal deterministically — an unflagged card
gets flagged `oversized` → Needs Attention (signal 2, sequential
sub-features, stays interpretive in the prompt layer). Cards declaring a non-`none`
`## Execution Surface` also route to Needs Attention — a declared risk
surface is an Operator-eyeball item by definition (and ineligible for self-approve).
When `cdo-product` is installed (`.agents/skills/cdo-product/SKILL.md`), a card
with no `P&D co-sign:` line skipped the second signature — not a refusal: it
gets flagged `unsigned-cosign` and routed to Needs Attention so the bypass
(any path — drain-side drafts, inline drafts, manual filing) is visible. A
`P&D co-sign:` line with a non-`sign` verdict (e.g. `P&D disputed`) counts as
stamped — the co-sign ran, the Operator adjudicates the dispute.
Re-filing a key snapshots the replaced draft to `alignment/superseded/`
before overwrite, so later reads can diff what changed.
Receipt: stdout JSON carries status, dry_run, filed[], needs_attention[],
routine[], undraftable[], gaps, warnings, filed_count/attention_count/
routine_count, and `suggest: cdo-review` when anything filed; the same
receipt persists to `alignment/last-run.json` — that pair is the headless
caller contract (blocked stops print `{"status": "blocked", ...}` from the
prompt layer instead).
Exit codes: 0=ok, 1=validation error, 2=runtime error
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

from cardlayout import (  # noqa: E402 — vendored card-layout contract
    MOCK_VALUE_RE, RISK_TOKENS, WIREFRAME_VALUE_RE, grounding_stale,
    head_sha, retarget_mock, superseded_assets)
from cardlayout import section as _section  # noqa: E402
from cardlayout import set_mock_line as _set_mock_line  # noqa: E402

ENTRY_RE = re.compile(r"^- \[ \] (?P<key>\S+?) — ")
FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
KEY_RE = re.compile(r"^[A-Za-z0-9][\w.-]*$")
WIRETEXT_RE = re.compile(r"https://wiretext\.app/w/[A-Za-z0-9_-]+")
# Gate-bypass tokens live in cardlayout.RISK_TOKENS (a confirmed card
# pre-clears schema-migration/deps-changed; the rest only route).
# The co-sign stamp is a contracted line shape, not a substring — column-0
# anchored like MOCK_VALUE_RE/WIREFRAME_VALUE_RE; a `{...}` verdict is the
# template's unsubstituted placeholder, not a signature.
COSIGN_STAMP_RE = re.compile(r"^- \*\*P&D co-sign:\*\*\s*(.+)$", re.M)
EXTERNAL_REF_RE = re.compile(
    r"(?:src|href)\s*=\s*[\"']https?://|@import|url\(\s*[\"']?https?://",
    re.I)
PLACEHOLDER_TOKEN = "placeholder styling"
FRAME_TOKEN_RE = re.compile(r"\b(?:browser|phone)\s*:", re.I)

# The template's `##` sections are the card's completeness contract —
# `Suggested Split` excluded (oversized-only by contract). A card that
# can't produce all of them isn't draftable (SKILL.md), so a missing
# section is a validation error, not a flag.
REQUIRED_SECTIONS = (
    "Marshal's Read", "System Context", "Visual Preview",
    "Questions for the Operator", "Acceptance Criteria", "Scope Boundary",
    "Externals Needed", "Execution Surface", "Flags", "Doctrine Grounding")


def _find_project_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "_bmad").is_dir():
            return p
    return start


def _risk_tokens(body: str):
    """Parse the `## Execution Surface` `**Risk surface:**` line. Returns
    (declared, unknown) — `none` stripped from declared; anything outside
    the enum reported so a typo can't silently fail closed."""
    m = re.search(r"- \*\*Risk surface:\*\*\s*(.+)", _section(body, "Execution Surface"))
    declared, unknown = [], []
    if m:
        for tok in re.split(r"[,\s]+", m.group(1).strip().strip("`")):
            tok = tok.strip().strip("`").lower()
            if not tok:
                continue
            (declared if tok in RISK_TOKENS else unknown).append(tok)
    return [t for t in declared if t != "none"], unknown


def _frontmatter(body: str) -> dict:
    """Parse the card's YAML frontmatter block; {} when absent/unparseable."""
    m = FM_RE.match(body or "")
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _derived_asks(body: str) -> int:
    """Count question bullets in `## Questions for the Operator`, excluding
    only the contracted `None —` sentinel — a real question that happens to
    start with the word 'None' ("None of the endpoints cover X — …") still
    counts. The card carries the questions; the count is derivable, so it
    isn't trusted to the prompt layer."""
    n = 0
    for line in _section(body, "Questions for the Operator").splitlines():
        m = re.match(r"^\s*-\s+(.*)$", line)
        if m and not re.match(r"(?i)none\b\s*—", m.group(1)):
            n += 1
    return n


def _validate(cards: list) -> list:
    """Up-front validation — every failure names its card. A bad card is a
    validation error (exit 1), never a half-filed run."""
    errors, seen = [], set()
    for i, card in enumerate(cards):
        if not isinstance(card, dict):
            errors.append(f"card #{i}: not an object")
            continue
        label = card.get("key") or f"#{i}"
        key = card.get("key")
        if not key or not isinstance(key, str) or not KEY_RE.match(key):
            errors.append(f"card #{i}: bad or missing 'key' — must match "
                          f"{KEY_RE.pattern} (it becomes a filename)")
        elif key in seen:
            errors.append(f"card {key}: duplicate key — two cards would "
                          f"overwrite the same draft file")
        seen.add(key)
        if not card.get("title"):
            errors.append(f"card {label}: missing 'title'")
        try:
            int(card.get("confidence"))
        except (TypeError, ValueError):
            errors.append(f"card {label}: 'confidence' must be a number "
                          f"(got {card.get('confidence')!r})")
        if not card.get("body"):
            errors.append(f"card {label}: missing 'body'")
        else:
            missing = [s for s in REQUIRED_SECTIONS
                       if not _section(card["body"], s).strip()]
            if missing:
                errors.append(f"card {label}: missing required sections "
                              f"{missing} — the template's section list is "
                              "the completeness contract")
    return errors


def _contract_warnings(card: dict, declared: list, head: str = "") -> tuple:
    """Cross-check the machine-comparable contract: frontmatter
    `declared_surface` must equal the Execution Surface tokens, and
    `grounded_against.commit` must be non-empty — an empty commit leaves
    the staleness tripwire dark (the template default `""` is exactly the
    case this catches). A commit behind HEAD warns: the read may predate
    the filing, not the card's fault. Returns (warnings, contract_broken)
    — contract_broken routes to Needs Attention."""
    body = card.get("body") or ""
    warnings, broken = [], False
    fm = _frontmatter(body)
    ga = fm.get("grounded_against")
    commit = (ga or {}).get("commit") if isinstance(ga, dict) else None
    if not commit:
        warnings.append("grounded_against.commit empty — staleness "
                        "detection can't benchmark this card")
        broken = True
    elif head and grounding_stale(commit, head):
        warnings.append(f"grounded_against.commit {commit} is behind HEAD "
                        f"{head} — card filed against a stale read")
    if not (isinstance(ga, dict) and ga.get("drafted")):
        warnings.append("grounded_against.drafted missing — the stamp "
                        "carries commit + date")
    fm_declared = fm.get("declared_surface")
    if fm_declared is not None:
        fm_set = {t for t in fm_declared if t != "none"}
        if fm_set != set(declared):
            warnings.append(f"frontmatter declared_surface "
                            f"{sorted(fm_set)} != Execution Surface "
                            f"{sorted(declared)} — contract drift")
            broken = True
    return warnings, broken


def _wireframe_url(card: dict):
    """Explicit `wireframe` field wins if it's actually a wiretext URL; else
    recover one — but only from the `## Visual Preview` section, never from
    prose elsewhere in the card."""
    w = card.get("wireframe")
    if w and WIRETEXT_RE.fullmatch(str(w).strip()):
        return str(w).strip(), None
    warn = (f"wireframe field '{w}' isn't a wiretext.app URL — ignored"
            ) if w else None
    m = WIRETEXT_RE.search(_section(card.get("body"), "Visual Preview"))
    return (m.group(0) if m else None), warn


def _artifact_gate(card: dict, wire, mock_rel):
    """Draft-completeness gate — the filer-side half of 'not
    draft-complete until both resolve'. A produced or attempted
    Wireframe (URL or `unavailable` — attempting presupposes a surface)
    beside a Mock that is `n/a` or absent is a named validation error:
    the batch fails before anything files. Honest exits stay open —
    `n/a` beside no wire claim, `unavailable — {reason}` on the mock.
    Reads the body after `_mock_plan` stamped the Mock line, so both
    sides are truthful. The mirror (mock produced, wire denied) is
    advisory — `_mock_wire_consistency` flags it; the wire's gate is
    downstream."""
    sec = _section(card.get("body"), "Visual Preview")
    m = WIREFRAME_VALUE_RE.search(sec)
    wval = m.group(1).strip().strip("`") if m else ""
    m = MOCK_VALUE_RE.search(sec)
    mval = m.group(1).strip().strip("`") if m else ""
    wire_claimed = bool(wire) or wval.startswith("unavailable")
    mock_denied = not mval or mval.startswith("n/a")
    if wire_claimed and mock_denied:
        return (f"{card['key']}: wireframe "
                f"{'produced' if wire else 'attempted'} but Mock is "
                f"`{'n/a' if mval else 'absent'}` — a wire presupposes "
                "a UI surface; produce the mock or the n/a is wrong")
    return None


def _mock_wire_consistency(card: dict, wire, mock_rel, warnings: list):
    """Mirror-direction consistency: a produced mock beside Wireframe
    `n/a`/absent flags `wire-missing` → Needs Attention — advisory, the
    wire's gate is downstream. The opposite direction is the
    `_artifact_gate` contract break and never reaches here. Reads the
    card body after `_mock_plan` stamped the Mock line plus the actual
    staging result, so both sides are truthful."""
    key = card["key"]
    sec = _section(card.get("body"), "Visual Preview")
    m = WIREFRAME_VALUE_RE.search(sec)
    wval = m.group(1).strip().strip("`") if m else ""
    m = MOCK_VALUE_RE.search(sec)
    mval = m.group(1).strip().strip("`") if m else ""
    wire_denied = not wval or wval.startswith("n/a")
    mock_present = bool(mock_rel) or (
        mval and not mval.startswith(("n/a", "unavailable")))
    if mock_present and wire_denied:
        warnings.append(
            f"{key}: mock produced but Wireframe is "
            f"`{'n/a' if wval else 'absent'}` — a mock proves a UI "
            "surface; produce the wire or the claim is wrong")
        flags = card.setdefault("flags", [])
        if isinstance(flags, list) and "wire-missing" not in flags:
            flags.append("wire-missing")


def _sizing_contract(card: dict, warnings: list):
    """The `oversized` flag's countable half: `**Sizing:** full` plus >=3
    distinct frontmatter `touches` entries trips the signal — an unflagged
    card gets `oversized` appended (advisory; it still files, flagged →
    Needs Attention). Signal 2 (sequential sub-features) stays in the
    prompt layer — it's interpretive, not countable."""
    fm = _frontmatter(card.get("body"))
    touches = fm.get("touches")
    m = re.search(r"- \*\*Sizing:\*\*\s*`?(\w+)`?", card.get("body") or "")
    flags = card.setdefault("flags", [])
    if (m and m.group(1).lower() == "full"
            and isinstance(touches, list)
            and len({str(t) for t in touches}) >= 3
            and isinstance(flags, list) and "oversized" not in flags):
        warnings.append(
            f"{card['key']}: size `full` spanning "
            f"{len({str(t) for t in touches})} touches entries trips the "
            "`oversized` signal but the card didn't declare it — flagged")
        flags.append("oversized")


def _mock_health(src_path: Path, warnings: list, key: str):
    """Mechanical floor for the renderable artifact — existence is already
    proven; here we warn on files that don't look like a self-contained
    HTML mock (empty/tiny, no HTML structure, external asset refs).
    Warn-only, never blocks — same posture as every optional artifact."""
    try:
        head = src_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        warnings.append(f"{key}: mock staged but unreadable — "
                        "couldn't verify it opens")
        return ""
    if len(head.strip()) < 200 or "<html" not in head.lower() \
            and "<!doctype" not in head.lower():
        warnings.append(f"{key}: mock doesn't look like an HTML file — "
                        "verify it opens from file:// before review")
    elif EXTERNAL_REF_RE.search(head):
        warnings.append(f"{key}: mock references external assets "
                        "(http/CDN) — the file contract is self-contained")
    if not FRAME_TOKEN_RE.search(head[:600]):
        warnings.append(f"{key}: mock header declares no environment frame "
                        "(`browser:{{route}}` | `phone:{{host-app|bare}}`) — "
                        "the file contract names the frame it renders in")
    return head


def _mock_plan(card: dict, warnings: list, cards_dir: Path, orch: Path):
    """Resolve the card's `mock` payload into (src_path, staged_rel).
    Sets the body's `**Mock:**` line to the deterministic staged path —
    `alignment/drafts/assets/{key}/mock.html` for a file, or
    `alignment/drafts/assets/{key}/mock/` for a directory — or
    `unavailable — {reason}` when the supplied path doesn't exist
    (warned, never fatal; same posture as the wireframe).
    A body that claims a mock path while the payload carries none is
    existence-checked and degraded, never trusted. Relative `mock` paths
    anchor to the --cards file's directory, not the process CWD.
    Returns (None, None) when nothing stages. The copy happens later,
    after any supersede snapshot has moved the old assets away."""
    key = card["key"]
    body = card.get("body") or ""
    src = card.get("mock")
    if not src:
        # declared-but-not-staged: the card's Mock line claims a path the
        # payload didn't supply — existence-check the claim or degrade it
        mm = MOCK_VALUE_RE.search(_section(body, "Visual Preview"))
        if mm:
            mval = mm.group(1).strip().strip("`")
            if not mval.startswith(("n/a", "unavailable")):
                if (orch / mval).exists():
                    return None, mval  # already staged — line is truthful
                warnings.append(
                    f"{key}: card declares mock '{mval}' but no mock was "
                    "staged — card marked unavailable")
                card["body"] = _set_mock_line(
                    body, "unavailable — mock declared but not staged")
        return None, None
    src_path = Path(str(src)).expanduser()
    if not src_path.is_absolute():
        src_path = cards_dir / src_path
    if not src_path.exists():
        warnings.append(f"{key}: mock path '{src}' doesn't exist — "
                        "card marked unavailable")
        card["body"] = _set_mock_line(
            body, f"unavailable — mock file missing: {src}")
        return None, None
    if not _section(body, "Visual Preview").strip():
        warnings.append(f"{key}: mock staged but card has no "
                        "## Visual Preview section — Mock line not writable")
    if src_path.is_dir():
        rel = f"alignment/drafts/assets/{key}/mock/"
    else:
        head = _mock_health(src_path, warnings, key)
        if PLACEHOLDER_TOKEN in head:
            flags = card.setdefault("flags", [])
            if isinstance(flags, list) \
                    and "ungrounded:design-tokens" not in flags:
                flags.append("ungrounded:design-tokens")
                warnings.append(
                    f"{key}: mock uses placeholder styling — flagged "
                    "ungrounded:design-tokens")
        rel = f"alignment/drafts/assets/{key}/mock.html"
    card["body"] = _set_mock_line(body, rel)
    return src_path, rel


def _copy_mock(src_path: Path, key: str, drafts_dir: Path):
    dest_root = drafts_dir / "assets" / key
    dest_root.mkdir(parents=True, exist_ok=True)
    if src_path.is_dir():
        dest = dest_root / "mock"
        if src_path.resolve() == dest.resolve():
            return  # already staged in place
        shutil.copytree(src_path, dest, dirs_exist_ok=True)
        return
    dest = dest_root / "mock.html"
    if src_path.resolve() == dest.resolve():
        return  # already staged in place — self-copy would raise
    shutil.copy2(src_path, dest)


def parse_args():
    p = argparse.ArgumentParser(description="File alignment cards into the Operator checklist.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--cards", required=True, help="JSON file with drafted cards")
    p.add_argument("--backlog-map",
                   help="JSON of the cdo:backlog_map config ({stem: orch-relative"
                   " path}) — the script resolves backlog file locations;"
                   " supersedes --backlog-dir for mapped stems")
    p.add_argument("--backlog-dir",
                   help="Backlog dir for marker flips (default: {orch}/backlogs)")
    p.add_argument("--attention-threshold", type=int, default=80,
                   help="Confidence below this (or any flags) → Needs Attention")
    p.add_argument("--dry-run", action="store_true",
                   help="compute routing + markers, write nothing")
    p.add_argument("-o", "--output")
    return p.parse_args()


def checklist_line(card: dict, wire, mock=None) -> str:
    flags = f" | flags: {', '.join(card['flags'])}" if card.get("flags") else ""
    asks = int(card.get("asks") or 0)
    asks_txt = f" | asks: {asks}" if asks else ""
    wire_txt = f" | wire: {wire}" if wire else ""
    mock_txt = f" | mock: {mock}" if mock else ""
    return (
        f"- [ ] {card['key']} — {card['title']} | conf {card['confidence']}%{flags}{asks_txt}"
        f"{wire_txt}{mock_txt} | draft: alignment/drafts/{card['key']}.md"
    )


def insert_sorted(lines: list, new_line: str, conf: int, start: int, end: int) -> list:
    """Insert new_line into checklist lines[start:end] sorted ascending by conf%."""
    key = ENTRY_RE.match(new_line)
    key = key.group("key") if key else None
    kept = []
    for i in range(start, end):
        line = lines[i]
        m = ENTRY_RE.match(line)
        if m and m.group("key") == key:
            continue  # replace existing entry for this key
        kept.append(line)
    conf_re = re.compile(r"\| conf (\d+)%")
    pos = len(kept)
    for i, line in enumerate(kept):
        m = conf_re.search(line)
        if m and int(m.group(1)) > conf:
            pos = i
            break
    kept.insert(pos, new_line)
    return lines[:start] + kept + lines[end:]


def section_bounds(lines: list, heading: str):
    """Return (start, end) line range of a '## heading' section's items."""
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == f"## {heading}")
    except StopIteration:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return start + 1, end


def normalize_backlog(value: str, orch: Path) -> str:
    """Cards may carry 'code', 'backlogs/code.md', or a dept name ('cdo-growth') —
    normalize to the backlog file stem. Dept names resolve via capabilities.yaml
    `departments.{dept}.backlog` (cdo-growth → content), not string surgery."""
    v = Path(str(value)).stem
    if not v.startswith("cdo-"):
        return v
    caps = orch / "capabilities.yaml"
    if caps.is_file():
        try:
            import yaml
            depts = (yaml.safe_load(caps.read_text(encoding="utf-8")) or {}) \
                .get("departments") or {}
            back = (depts.get(v) or {}).get("backlog")
            if back:
                return Path(str(back)).stem
        except (yaml.YAMLError, ImportError):
            pass
    # fallback: strip cdo- (covers cdo-{x}→backlogs/{x}.md convention)
    return v[4:]


def _backlog_files(raw: str, orch: Path):
    """{stem: Path} from the --backlog-map JSON ({stem: orch-relative
    path}) — the cdo: config value is the org's source of truth for where
    backlog files live. Returns (files, error) — a malformed value is a
    named input error, not a silent fallback."""
    if not raw:
        return {}, None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {}, f"--backlog-map isn't valid JSON: {e}"
    if not isinstance(data, dict):
        return {}, "--backlog-map must be a JSON object {stem: path}"
    files = {}
    for stem, rel in data.items():
        p = Path(str(rel))
        files[Path(str(stem)).stem] = p if p.is_absolute() else orch / p
    return files, None


def _backlog_file(backlog_dir: Path, files: dict, backlog_name: str) -> Path:
    """Mapped file for the stem wins; unmapped stems fall back to the dir."""
    return (files or {}).get(backlog_name) \
        or backlog_dir / f"{backlog_name}.md"


def flip_backlog_marker(backlog_dir: Path, backlog_name: str, key: str,
                        dry: bool = False, files: dict = None) -> bool:
    """Flip `- [ ]` or `- [?]` key → `- [A] key` (`[?]` = previously marked
    undraftable, now drafted). True also when the line is already [A]
    (idempotent re-file) — False only when the key has no backlog line."""
    f = _backlog_file(backlog_dir, files, backlog_name)
    if not f.is_file():
        return False
    text = f.read_text(encoding="utf-8")
    if re.search(rf"^- \[A\] {re.escape(key)}\b", text, flags=re.M):
        return True
    new = re.sub(
        rf"^- \[[ ?]\] {re.escape(key)}\b", f"- [A] {key}", text, count=1,
        flags=re.M
    )
    if new != text:
        if not dry:
            f.write_text(new, encoding="utf-8")
        return True
    return False


def mark_undraftable(backlog_dir: Path, backlog_name: str, key: str,
                     dry: bool = False, files: dict = None) -> bool:
    """Flip `- [ ] key` → `- [?] key` — a recorded disposition, so the item
    stops re-scanning as if merely unaligned. `--story` re-selects it."""
    f = _backlog_file(backlog_dir, files, backlog_name)
    if not f.is_file():
        return False
    text = f.read_text(encoding="utf-8")
    new = re.sub(
        rf"^- \[ \] {re.escape(key)}\b", f"- [?] {key}", text, count=1,
        flags=re.M
    )
    if new != text:
        if not dry:
            f.write_text(new, encoding="utf-8")
        return True
    return False


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    backlog_dir = Path(args.backlog_dir) if args.backlog_dir else orch / "backlogs"
    backlog_files, bmap_err = _backlog_files(args.backlog_map, orch)
    if bmap_err:
        print(json.dumps({"errors": [bmap_err]}))
        sys.exit(1)

    try:
        payload = json.loads(Path(args.cards).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    if isinstance(payload, list):
        payload = {"cards": payload}
    if not isinstance(payload, dict) or not isinstance(
            payload.get("cards"), list):
        print("error: --cards must be a JSON array or an envelope "
              '{"cards": [...], "undraftable": [...], "gaps": [...]}',
              file=sys.stderr)
        sys.exit(1)
    cards = payload["cards"]
    undraftable = payload.get("undraftable") or []
    gaps = payload.get("gaps") or []

    errors = _validate(cards)
    if errors:
        print(json.dumps({"errors": errors}, indent=2))
        sys.exit(1)

    checklist_path = orch / "alignment-checklist.md"
    if not checklist_path.is_file():
        print(json.dumps({"errors": [f"checklist missing: {checklist_path}"]}))
        sys.exit(1)

    # co-sign enforcement: when the dept is installed, a card with no
    # `P&D co-sign:` line bypassed the mandatory second signature
    project_root = _find_project_root(orch)
    cosign_required = (project_root / ".agents" / "skills" / "cdo-product"
                       / "SKILL.md").is_file()
    head = head_sha(project_root)  # "" outside a git repo — compare skips

    warnings = []
    # draft-completeness gate: resolve every card's wire + mock first —
    # a claimed wire beside a denied mock fails the batch before any
    # write, so a wire-only card never half-files a drain
    cards_dir = Path(args.cards).resolve().parent
    plans = {}
    gate_errors = []
    for card in sorted(cards, key=lambda c: int(c.get("confidence", 0))):
        mock_src, mock_rel = _mock_plan(card, warnings, cards_dir, orch)
        wire, warn = _wireframe_url(card)
        if warn:
            warnings.append(f"{card['key']}: {warn}")
        err = _artifact_gate(card, wire, mock_rel)
        if err:
            gate_errors.append(err)
        plans[card["key"]] = (mock_src, mock_rel, wire)
    if gate_errors:
        print(json.dumps({"errors": gate_errors}, indent=2))
        sys.exit(1)

    drafts_dir = orch / "alignment" / "drafts"
    if not args.dry_run:
        drafts_dir.mkdir(parents=True, exist_ok=True)
    lines = checklist_path.read_text(encoding="utf-8").splitlines()

    filed = []
    unflipped = []
    superseded_dir = orch / "alignment" / "superseded"
    for card in sorted(cards, key=lambda c: int(c.get("confidence", 0))):
        key = card["key"]
        # the staged path must be truthful in the filed draft; the file
        # copy waits until after any supersede snapshot moves old assets
        mock_src, mock_rel, wire = plans[key]
        draft_path = drafts_dir / f"{key}.md"
        if draft_path.is_file() and \
                draft_path.read_text(encoding="utf-8") != card["body"]:
            if not args.dry_run:
                superseded_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y-%m-%dT%H%M")
                draft_path.replace(superseded_dir / f"{key}.{stamp}.md")
                # keep the mock with the draft it belonged to
                old_assets = drafts_dir / "assets" / key
                if old_assets.is_dir():
                    shutil.move(str(old_assets),
                                str(superseded_dir / f"{key}.{stamp}.assets"))
        # a fresh draft supersedes a parked card for the same key — the
        # rethink path (unpark) already moves parked→superseded; cover the
        # manual-marker-flip route too so parked/ can't double-file
        parked_path = orch / "alignment" / "parked" / f"{key}.md"
        if parked_path.is_file() and not args.dry_run:
            superseded_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%dT%H%M")
            # parked mock assets ride along — and the parked card's Mock
            # line is retargeted so it never cites a dead path
            parked_assets = orch / "alignment" / "parked" / "assets" / key
            parked_dest = superseded_assets(
                superseded_dir, key, stamp, ".parked")
            body = parked_path.read_text(encoding="utf-8")
            if parked_assets.is_dir():
                shutil.move(str(parked_assets), str(parked_dest))
                body = retarget_mock(
                    body, key,
                    parked_dest.relative_to(orch).as_posix())
            (superseded_dir / f"{key}.{stamp}.parked.md").write_text(
                body, encoding="utf-8")
            parked_path.unlink()
            warnings.append(f"{key}: parked card moved to superseded/ — "
                            "fresh draft takes precedence")
        if not args.dry_run:
            draft_path.write_text(card["body"], encoding="utf-8")
            if mock_src is not None:
                _copy_mock(mock_src, key, drafts_dir)

        _mock_wire_consistency(card, wire, mock_rel, warnings)
        _sizing_contract(card, warnings)
        declared, unknown = _risk_tokens(card.get("body"))
        if unknown:
            warnings.append(
                f"{key}: unrecognized Execution Surface tokens {unknown} — "
                f"valid: {sorted(RISK_TOKENS)}. A typo fails closed at the gate.")
        cwarns, contract_broken = _contract_warnings(
            card, declared, head or "")
        warnings += [f"{key}: {w}" for w in cwarns]
        stamp = COSIGN_STAMP_RE.search(card.get("body") or "")
        if cosign_required and not (stamp and "{" not in stamp.group(1)):
            warnings.append(
                f"{key}: no `P&D co-sign:` stamp — cdo-product is installed, "
                "so this card bypassed the second signature (drain-side and "
                "inline drafts must still co-sign)")
            flags = card.setdefault("flags", [])
            if isinstance(flags, list) and "unsigned-cosign" not in flags:
                flags.append("unsigned-cosign")

        # remove any existing entry for this key across ALL sections —
        # a re-filed card may move between Needs Attention and Routine Review
        lines = [l for l in lines
                 if not (ENTRY_RE.match(l) and ENTRY_RE.match(l).group("key") == key)]

        conf = int(card["confidence"])
        asks = _derived_asks(card.get("body"))
        supplied = int(card.get("asks") or 0)
        if supplied != asks:
            warnings.append(f"{key}: asks field says {supplied}, Questions "
                            f"section holds {asks} — using the derived count")
            card["asks"] = asks
        # open Operator questions always route to Needs Attention — a card that
        # asks something is definitionally not routine; a declared risk
        # surface is an Operator-eyeball item (and ineligible for self-approve)
        needs_attention = card.get("flags") or asks > 0 or declared \
            or contract_broken or conf < args.attention_threshold
        section = "Needs Attention" if needs_attention else "Routine Review"
        bounds = section_bounds(lines, section)
        if not bounds:
            print(json.dumps({"errors": [f"checklist lacks '## {section}' section"]}))
            sys.exit(1)
        lines = insert_sorted(lines, checklist_line(card, wire, mock_rel),
                              conf, *bounds)

        marked = flip_backlog_marker(
            backlog_dir, normalize_backlog(card.get("backlog", "code"), orch),
            key, dry=args.dry_run, files=backlog_files,
        )
        entry = {
            "key": key, "section": section, "confidence": conf,
            "backlog_marked": marked,
        }
        if not marked:
            entry["warning"] = "backlog marker not flipped — item will redraft on next scan"
            unflipped.append(key)
        filed.append(entry)

    undrafted = []
    for item in undraftable:
        key = item.get("key")
        if not key:
            warnings.append("undraftable entry missing 'key' — skipped")
            continue
        ok = mark_undraftable(
            backlog_dir,
            normalize_backlog(item.get("backlog", "code"), orch),
            key, dry=args.dry_run, files=backlog_files)
        undrafted.append({"key": key, "reason": item.get("reason"),
                          "marker_flipped": ok})
        if not ok:
            warnings.append(f"undraftable {key}: no `- [ ]` backlog line found")

    if gaps and not args.dry_run:
        gp = orch / "alignment" / "gap-findings.md"
        block = "\n".join(f"- {g}" for g in gaps)
        with gp.open("a", encoding="utf-8") as f:
            f.write(f"\n## {datetime.now():%Y-%m-%d}\n\n{block}\n")

    if not args.dry_run:
        checklist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = {
        "status": "success",
        "dry_run": bool(args.dry_run),
        "filed": filed,
        "needs_attention": [f["key"] for f in filed if f["section"] == "Needs Attention"],
        "routine": [f["key"] for f in filed if f["section"] == "Routine Review"],
        "filed_count": len(filed),
        "attention_count": sum(1 for f in filed if f["section"] == "Needs Attention"),
        "routine_count": sum(1 for f in filed if f["section"] == "Routine Review"),
        "undraftable": undrafted,
        "gaps": gaps,
    }
    if filed:
        result["suggest"] = "cdo-review"
    if warnings:
        result["warnings"] = warnings
    if unflipped:
        result["status"] = "partial"
        result["errors"] = [
            f"backlog marker not flipped for {unflipped} — check the card's "
            "`backlog` field resolves to a real backlog file (dept name? "
            "stem?). A silent miss here means the item re-drafts forever."
        ]
    if not args.dry_run:
        (orch / "alignment").mkdir(parents=True, exist_ok=True)
        (orch / "alignment" / "last-run.json").write_text(json.dumps({
            "at": datetime.now().isoformat(timespec="seconds"),
            "filed": [f["key"] for f in filed],
            "needs_attention": result["needs_attention"],
            "routine": result["routine"],
            "filed_count": result["filed_count"],
            "attention_count": result["attention_count"],
            "routine_count": result["routine_count"],
            "undraftable": undrafted,
            "gaps": gaps,
            **({"suggest": "cdo-review"} if filed else {}),
        }, indent=2), encoding="utf-8")
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    if unflipped:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
