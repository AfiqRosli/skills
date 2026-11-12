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
     to `alignment/last-run.json`

Idempotent by card key — re-running replaces the draft file and checklist line.

Usage:
  uv run file-cards.py --orchestration-dir /path/docs/orchestration
      --cards cards.json [--backlog-dir /path/docs/orchestration/backlogs]
      [--attention-threshold 80] [--dry-run] [-o result.json]

Cards JSON: [{"key","title","backlog","confidence","flags":[...],
              "asks": 0, "body": "...", "wireframe": "https://wiretext.app/w/…"}]
`asks` is derived from the card's Questions section; a supplied count that
disagrees warns and the derived count wins — a card's asks>0 → Needs Attention.
`wireframe` is optional — when absent, a wiretext URL is recovered from the
card body's Visual Preview section if present. Cards declaring a non-`none`
`## Execution Surface` also route to Needs Attention — a declared risk
surface is an Operator-eyeball item by definition (and ineligible for self-approve).
Contract checks that can't be trusted to the prompt layer are enforced here:
frontmatter `declared_surface` must equal the Execution Surface tokens, and a
missing Execution Surface section warns instead of passing as honest `none`.
When `cdo-product` is installed (`.agents/skills/cdo-product/SKILL.md`), a card
with no `P&D co-sign:` line skipped the second signature — not a refusal: it
gets flagged `unsigned-cosign` and routed to Needs Attention so the bypass
(any path — drain-side drafts, inline drafts, manual filing) is visible. A
`P&D co-sign:` line with a non-`sign` verdict (e.g. `P&D disputed`) counts as
stamped — the co-sign ran, the Operator adjudicates the dispute.
Re-filing a key snapshots the replaced draft to `alignment/superseded/`
before overwrite, so later reads can diff what changed.
Exit codes: 0=ok, 1=validation error, 2=runtime error
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

ENTRY_RE = re.compile(r"^- \[ \] (?P<key>\S+?) — ")
FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
KEY_RE = re.compile(r"^[A-Za-z0-9][\w.-]*$")
WIRETEXT_RE = re.compile(r"https://wiretext\.app/w/[A-Za-z0-9_-]+")
# Gate-bypass tokens (a confirmed card pre-clears those dispatch gates):
#   schema-migration, deps-changed
# Attention-only tokens (route to Needs Attention; gates still apply):
#   env-changed, api-contract, data-backfill
RISK_TOKENS = {"none", "schema-migration", "deps-changed",
               "env-changed", "api-contract", "data-backfill"}
COSIGN_RE = re.compile(r"P&D co-sign:", re.I)


def _find_project_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "_bmad").is_dir():
            return p
    return start


def _section(body: str, name: str) -> str:
    m = re.search(rf"^## {re.escape(name)}\s*$", body or "", flags=re.M)
    if not m:
        return ""
    rest = body[m.end():]
    nxt = re.search(r"^## ", rest, flags=re.M)
    return rest[:nxt.start()] if nxt else rest


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
    the 'None — …' sentinel. The card carries the questions; the count is
    derivable, so it isn't trusted to the prompt layer."""
    n = 0
    for line in _section(body, "Questions for the Operator").splitlines():
        m = re.match(r"^\s*-\s+(.*)$", line)
        if m and not re.match(r"(?i)none\b", m.group(1)):
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
    return errors


def _contract_warnings(card: dict, declared: list) -> tuple:
    """Cross-check the machine-comparable contract: frontmatter
    `declared_surface` must equal the Execution Surface tokens, and a
    missing Execution Surface section is a defect, not an honest `none`.
    Returns (warnings, contract_broken) — contract_broken routes to
    Needs Attention."""
    body = card.get("body") or ""
    warnings, broken = [], False
    if not _section(body, "Execution Surface").strip():
        warnings.append("no `## Execution Surface` section — a skipped step "
                        "can't pass as a declared `none`")
        broken = True
    fm_declared = _frontmatter(body).get("declared_surface")
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


def parse_args():
    p = argparse.ArgumentParser(description="File alignment cards into the Operator checklist.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--cards", required=True, help="JSON file with drafted cards")
    p.add_argument("--backlog-dir",
                   help="Backlog dir for marker flips (default: {orch}/backlogs)")
    p.add_argument("--attention-threshold", type=int, default=80,
                   help="Confidence below this (or any flags) → Needs Attention")
    p.add_argument("--dry-run", action="store_true",
                   help="compute routing + markers, write nothing")
    p.add_argument("-o", "--output")
    return p.parse_args()


def checklist_line(card: dict, wire) -> str:
    flags = f" | flags: {', '.join(card['flags'])}" if card.get("flags") else ""
    asks = int(card.get("asks") or 0)
    asks_txt = f" | asks: {asks}" if asks else ""
    wire_txt = f" | wire: {wire}" if wire else ""
    return (
        f"- [ ] {card['key']} — {card['title']} | conf {card['confidence']}%{flags}{asks_txt}"
        f"{wire_txt} | draft: alignment/drafts/{card['key']}.md"
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


def flip_backlog_marker(backlog_dir: Path, backlog_name: str, key: str,
                        dry: bool = False) -> bool:
    """Flip `- [ ]` or `- [?]` key → `- [A] key` (`[?]` = previously marked
    undraftable, now drafted). True also when the line is already [A]
    (idempotent re-file) — False only when the key has no backlog line."""
    f = backlog_dir / f"{backlog_name}.md"
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
                     dry: bool = False) -> bool:
    """Flip `- [ ] key` → `- [?] key` — a recorded disposition, so the item
    stops re-scanning as if merely unaligned. `--story` re-selects it."""
    f = backlog_dir / f"{backlog_name}.md"
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

    drafts_dir = orch / "alignment" / "drafts"
    if not args.dry_run:
        drafts_dir.mkdir(parents=True, exist_ok=True)
    lines = checklist_path.read_text(encoding="utf-8").splitlines()

    filed = []
    unflipped = []
    warnings = []
    superseded_dir = orch / "alignment" / "superseded"
    for card in sorted(cards, key=lambda c: int(c.get("confidence", 0))):
        key = card["key"]
        draft_path = drafts_dir / f"{key}.md"
        if draft_path.is_file() and \
                draft_path.read_text(encoding="utf-8") != card["body"]:
            if not args.dry_run:
                superseded_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y-%m-%dT%H%M")
                draft_path.replace(superseded_dir / f"{key}.{stamp}.md")
        # a fresh draft supersedes a parked card for the same key — the
        # rethink path (unpark) already moves parked→superseded; cover the
        # manual-marker-flip route too so parked/ can't double-file
        parked_path = orch / "alignment" / "parked" / f"{key}.md"
        if parked_path.is_file() and not args.dry_run:
            superseded_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%dT%H%M")
            parked_path.replace(
                superseded_dir / f"{key}.{stamp}.parked.md")
            warnings.append(f"{key}: parked card moved to superseded/ — "
                            "fresh draft takes precedence")
        if not args.dry_run:
            draft_path.write_text(card["body"], encoding="utf-8")

        wire, warn = _wireframe_url(card)
        if warn:
            warnings.append(f"{key}: {warn}")
        declared, unknown = _risk_tokens(card.get("body"))
        if unknown:
            warnings.append(
                f"{key}: unrecognized Execution Surface tokens {unknown} — "
                f"valid: {sorted(RISK_TOKENS)}. A typo fails closed at the gate.")
        cwarns, contract_broken = _contract_warnings(card, declared)
        warnings += [f"{key}: {w}" for w in cwarns]
        if cosign_required and not COSIGN_RE.search(card.get("body") or ""):
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
        lines = insert_sorted(lines, checklist_line(card, wire), conf, *bounds)

        marked = flip_backlog_marker(
            backlog_dir, normalize_backlog(card.get("backlog", "code"), orch),
            key, dry=args.dry_run,
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
            key, dry=args.dry_run)
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
        "undraftable": undrafted,
        "gaps": gaps,
    }
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
            "undraftable": undrafted,
            "gaps": gaps,
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
