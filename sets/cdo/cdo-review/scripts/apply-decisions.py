#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Apply Operator decisions to the cdo orchestration state — deterministic
half of cdo-review.

For each decision {key, verdict, note}:

  confirm        → archive card to alignment/YYYY/MM/DD/, backlog [A]→[x],
                   ledger pool.confirmed += key, story queued, sprint yaml
                   `proposed` → `backlog` when the key carries an entry,
                   streak +1 if card conf ≥95%
  confirm-edited → same, but streak resets to 0 and the edit is journaled
                   (the Operator had to change something — that's a correction)
  reject         → archive card with verdict, backlog [A]→[-], quarantine,
                   streak resets
  defer          → card moves drafts/ → alignment/parked/ and the checklist
                   line resolves `→ deferred` — parked means "looked at,
                   consciously not now", so drafts/ holds only unexamined
                   work. Non-card items stay pending (no parked concept).
  resurface      → the rethink-NOT-needed path: parked card returns to
                   drafts/ verbatim and the checklist re-pends a line in the
                   section the deferred line sits in. Warns when the card's
                   grounded_against.commit is stale vs HEAD — the rethink
                   path is `unpark`.
  unpark         → the rethink path: parked card moves to superseded/ and
                   the backlog marker flips [A]→[ ] so the next align run
                   redrafts it against current code.
  granted        → non-card verdict (requisitions/sign-offs): [x] applied
  blocked        → non-card verdict: [-] applied + journaled as a correction
  (non-card key) → checklist box checked with verdict + note, no archive

Pre-deploy gating (## Pre-deploy Sign-offs — the preview-lane push gate):
  confirm on a ## Delivered item for a shipped story marks it for
  pre-deploy — inserts `- [ ] {key} — push to origin/{lane}` under
  ## Pre-deploy Sign-offs and stamps stories.{key}.pre_deploy.marked_at.
  A later confirm/granted on that item stamps pre_deploy.signed_at and
  lands the key in `push_approved` — cdo-review then runs cdo-platform's
  push leg (push-lane.py), the ONLY origin publisher. reject/blocked on a
  pre-deploy item stamps pre_deploy.rejected — the work stays local.

Review-doc graduation (alignment/reviews/ staging): a checklist line resolved
while carrying `| review: alignment/reviews/...` moves the staged doc beside
its confirmed card — the verdict IS the graduation, so reviews/ reads as
"shipped, awaiting Operator" only while the line pends. Wave docs and
no-card edges land in today's dated dir (warned); a defer never resolves a
Delivered/Escalations line (defer is scoped to card sections — reviews are
accept/reject or stay pending, there is no "review later" verdict).

Invalid verdicts are collected into `invalid` — the rest still apply (one bad
item never aborts the Operator's whole pass). Confirm on a checklist line with
no draft card warns rather than silently pooling nothing.

Usage:
  uv run apply-decisions.py --orchestration-dir /path/docs/orchestration
      --decisions decisions.json [--config /path/_bmad/config.yaml]
      [-o result.json]

Decisions JSON: [{"key","verdict","note"}]
Exit codes: 0=ok, 1=some items invalid, 2=runtime error
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

from cardlayout import (  # noqa: E402 — vendored card-layout contract
    CHECKBOX_KEY_RE, CONF_RE, card_backlog, card_title, confirmed_card,
    grounded_commit, grounding_stale, head_sha)

VERDICTS = {"confirm", "confirm-edited", "reject", "defer", "granted",
            "blocked", "resurface", "unpark"}
CARD_VERDICTS = {"confirm", "confirm-edited", "reject", "defer"}
CARD_LINE_RE = CHECKBOX_KEY_RE
STREAK_CONF_MIN = 95
# checklist lines filed by delivery-note carry `| review: {orch-rel path}` —
# the audit doc stays in alignment/reviews/ staging until a verdict lands
REVIEW_PTR_RE = re.compile(r"\|\s*review:\s*(\S+)")


def parse_args():
    p = argparse.ArgumentParser(description="Apply Operator decisions to cdo orchestration state.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--decisions", required=True,
                   help="JSON array or JSONL file of decisions")
    p.add_argument("--consume", action="store_true",
                   help="delete the decisions file after a successful apply — "
                        "used with staged pending-decisions.jsonl")
    p.add_argument("--config", help="_bmad/config.yaml path — syncs cdo.earned_autonomy "
                                  "into the ledger's autonomy.enabled")
    p.add_argument("--project-root", default="",
                   help="project root for the sprint-yaml flips — default: "
                        "orchestration-dir's grandparent (standard install)")
    p.add_argument("-o", "--output")
    return p.parse_args()


def stamp() -> tuple:
    n = datetime.now(timezone.utc)
    return n.strftime("%Y-%m-%d"), n.strftime("%H:%M")


def checklist_apply(lines: list, key: str, verdict: str, date: str,
                    note: str, sections: Optional[set] = None) -> list:
    """Mark the key's pending checkbox resolved with the verdict. `sections`
    scopes resolution to those `## ` headings — card-parking verdicts must
    never sweep a same-key Delivered or Pre-deploy line to `→ deferred`."""
    out = []
    current = ""
    for line in lines:
        h = re.match(r"^##\s+(.+)$", line)
        if h:
            current = h.group(1).strip()
        m = CARD_LINE_RE.match(line)
        if m and m.group("key") == key and m.group("mark") == " " \
                and (sections is None or current in sections):
            suffix = f" → {verdict} {date}" + (f" — {note}" if note else "")
            line = line.replace("- [ ]", "- [x]", 1) + suffix
        out.append(line)
    return out


def item_sections(lines: list, key: str) -> set:
    """Which `## ` sections hold pending `- [ ] {key}` lines. One verdict
    resolves every pending line for the key — semantics apply per resolved
    section (a Delivered confirm is delivery acceptance; the same confirm
    resolving a Pre-deploy line is push authorization)."""
    found, current = set(), ""
    for line in lines:
        h = re.match(r"^##\s+(.+)$", line)
        if h:
            current = h.group(1).strip()
        m = CARD_LINE_RE.match(line)
        if m and m.group("key") == key and m.group("mark") == " ":
            found.add(current)
    return found


def stamp_card(body: str, comment: str) -> str:
    """Stamp a verdict comment INSIDE the card — after the frontmatter
    block when present so start-of-file `---` parsers (grounded_against,
    preflight's no_frontmatter) still see the YAML on line 1, else at the
    top. The
    dated-archive convention prepends the stamp instead: `<!-- reject` on
    line 1 is the machine signal card readers check first — a parked card
    has no such reader, frontmatter integrity wins."""
    m = re.match(r"\A---\n.*?\n---\n", body or "", re.S)
    if m:
        return body[:m.end()] + f"\n<!-- {comment} -->\n\n" + body[m.end():]
    return f"<!-- {comment} -->\n\n" + body


def insert_checklist_item(lines: list, section: str, item_line: str,
                          create_before: str) -> list:
    """Insert `item_line` at the top of `## {section}`'s item list (after
    the section's leading comment/blank block — items never sort above
    the section blurb); create the section before the `create_before`
    heading when absent."""
    for i, line in enumerate(lines):
        if line.strip() == f"## {section}":
            j = i + 1
            while j < len(lines) and (lines[j].lstrip().startswith("<!--")
                                      or not lines[j].strip()):
                j += 1
            lines.insert(j, item_line)
            return lines
    idx = next((i for i, l in enumerate(lines)
                if l.strip() == create_before), len(lines))
    lines[idx:idx] = [f"## {section}", "", item_line, ""]
    return lines


def supersede_checklist_item(lines: list, section: str, key: str,
                             date: str) -> list:
    """Resolve a still-pending `- [ ] {key}` under `## {section}` as
    superseded — a re-mark for a newer lane sha retires the stale ask."""
    out, in_section = [], False
    for line in lines:
        h = re.match(r"^##\s+(.+)$", line)
        if h:
            in_section = h.group(1).strip() == section
        m = CARD_LINE_RE.match(line)
        if in_section and m and m.group("key") == key \
                and m.group("mark") == " ":
            line = line.replace("- [ ]", "- [x]", 1) + \
                f" → superseded {date}"
        out.append(line)
    return out


def flip_sprint_proposed(root: Path, key: str,
                         new_status: str = "backlog") -> str:
    """Sprint-status verdict surgery: the key's `proposed` line becomes
    `backlog` on confirm (Operator confirmation makes shaped work real) or
    `obsolete` on reject — the same three-write lifecycle, closed both ways.
    Scans sprint yamls newest-first and flips the one holding the key —
    a rollover can't strand the entry. Surgical: only the status token
    changes, comments and ordering stay byte-for-byte (same discipline as
    cdo-code-e2e's sprint-status.py)."""
    impl = root / "_bmad-output" / "implementation-artifacts"
    if not impl.is_dir():
        return ""
    def vkey(p: Path):
        m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})(?:\.(\d+))?", p.stem)
        return tuple(int(g or 0) for g in m.groups()) if m else (0,) * 4
    for yml in sorted(impl.glob("sprint-status-*.yaml"), key=vkey,
                      reverse=True):
        name = flip_status_in_yaml(yml, yml.read_text(encoding="utf-8"),
                                 key, new_status)
        if name:
            return name
    return ""


def flip_status_in_yaml(yml: Path, text: str, key: str,
                        new_status: str = "backlog") -> str:
    """One-line status surgery on a `proposed` entry — confirm flips to
    `backlog`, reject flips to `obsolete`. Returns the yaml filename."""
    pat = re.compile(rf"^(\s*{re.escape(key)}:\s*)proposed(\s*(#.*)?)$", re.M)
    new, n = pat.subn(rf"\g<1>{new_status}\g<2>", text, count=1)
    if n == 0:
        return ""
    if re.search(r"^last_updated:", new, re.M):
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new = re.sub(r"^last_updated:.*$", f"last_updated: {stamp}",
                     new, count=1, flags=re.M)
    yml.write_text(new, encoding="utf-8")
    return yml.name


def flip_backlog(backlog_dir: Path, backlog: str, key: str, new_mark: str, note: str) -> bool:
    """Flip the marker only — the rest of the line carries title/size/deps."""
    f = backlog_dir / f"{backlog}.md"
    if not f.is_file():
        return False
    text = f.read_text(encoding="utf-8")
    pat = re.compile(rf"^(- )\[A\]( {re.escape(key)}\b)(.*)$", re.M)
    m = pat.search(text)
    if not m:
        return False
    suffix = m.group(3)
    if note and new_mark == "-":
        suffix = (suffix + f" — {note}") if suffix else f" — {note}"
    text = text[: m.start()] + f"{m.group(1)}[{new_mark}]{m.group(2)}{suffix}" + text[m.end():]
    f.write_text(text, encoding="utf-8")
    return True


def graduate_review_docs(orch: Path, key: str, checklist: list,
                         ledger: dict, date: str) -> dict:
    """A resolved line carrying `| review: alignment/reviews/...` means the
    audit doc sat Operator-pending — the verdict IS the graduation: move it
    beside the confirmed card (today's dated dir for wave docs / missing
    cards), rewrite the pointer in the line, and refresh the ledger stamp
    (stories.{key}.delivery_review.doc / batch.wave_review.doc). Only fires
    on resolved lines — a still-pending `| review:` pointer means the doc
    is still awaiting verdict."""
    moved, warns = [], []
    reviews_dir = (orch / "alignment" / "reviews").resolve()
    for i, line in enumerate(checklist):
        m = CARD_LINE_RE.match(line)
        if not m or m.group("key") != key or m.group("mark") == " ":
            continue
        pm = REVIEW_PTR_RE.search(line)
        if not pm:
            continue
        rel = pm.group(1)
        src = (orch / rel).resolve()
        if src.parent != reviews_dir or not src.is_file():
            continue  # already final, external, or gone — nothing to graduate
        card = confirmed_card(orch, key)
        y2, m2, d2 = date.split("-")
        dest_dir = card.parent if card is not None \
            else orch / "alignment" / y2 / m2 / d2
        if card is None and not key.startswith("wave-"):
            warns.append(f"{src.name}: no confirmed card — landed in "
                         f"alignment/{y2}/{m2}/{d2}/ unpaired")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        src.replace(dest)
        new_rel = dest.relative_to(orch).as_posix()
        checklist[i] = line[:pm.start(1)] + new_rel + line[pm.end(1):]
        st = (ledger.get("stories") or {}).get(key) or {}
        dv = st.get("delivery_review") or {}
        if dv.get("doc") == rel:
            dv["doc"] = new_rel
        wr = (ledger.get("batch") or {}).get("wave_review") or {}
        if wr.get("doc") == rel:
            wr["doc"] = new_rel
        moved.append(f"{rel} → {new_rel}")
    return {"moved": moved, "warnings": warns}


def deferred_line(lines: list, key: str):
    """The section + base text of the key's resolved `- [x] … → deferred`
    line — the checklist's own record is the metadata source for a
    re-pended line (conf/flags/asks/wire/draft ref carry over verbatim)."""
    current = ""
    for line in lines:
        h = re.match(r"^##\s+(.+)$", line)
        if h:
            current = h.group(1).strip()
            continue
        m = CARD_LINE_RE.match(line)
        if m and m.group("key") == key and m.group("mark") == "x" \
                and re.search(r"→ deferred\b", line):
            base = re.sub(r"\s*→ deferred.*$", "", line)\
                .replace("- [x]", "- [ ]", 1)
            return current, base
    return None, None


def handle_resurface(orch: Path, proj_root: Path, checklist: list,
                     key: str, parked: Path, draft: Path, date: str,
                     note: str) -> tuple:
    """Revive the parked card verbatim: parked/ → drafts/ + a re-pended
    checklist line where the deferred one sits. A live draft always
    outranks the parked copy — park then redraft means the parked card
    is the stale one, so it goes to superseded/, never overwrites, and
    never earns a second pending line."""
    result = {"key": key, "verdict": "resurface"}
    body = parked.read_text(encoding="utf-8")

    # the grounding check reads frontmatter and must run BEFORE the move —
    # once the card leaves parked/ an `unpark` verdict refuses ("no parked
    # card"), so the advisory names the reachable rethink path instead:
    # the backlog-marker flip.
    grounded = grounded_commit(body)
    head = head_sha(proj_root)
    stale = grounding_stale(grounded, head)

    if draft.is_file():
        superseded = orch / "alignment" / "superseded"
        superseded.mkdir(parents=True, exist_ok=True)
        stamp_s = datetime.now().strftime("%Y-%m-%dT%H%M")
        parked.replace(superseded / f"{key}.{stamp_s}.md")
        result["superseded"] = f"alignment/superseded/{key}.{stamp_s}.md"
        result["warning"] = ("a live draft already exists — the parked "
                             "card moved to superseded/ instead")
    else:
        draft.parent.mkdir(parents=True, exist_ok=True)
        parked.replace(draft)
        result["resurfaced"] = f"alignment/drafts/{key}.md"
        section, base = deferred_line(checklist, key)
        if base:
            checklist = insert_checklist_item(
                checklist, section or "Needs Attention",
                base + f" | resurfaced {date}", "## Routine Review")
        else:
            conf_m = CONF_RE.search(body)
            conf = f" | conf {conf_m.group(1)}%" if conf_m else ""
            title = card_title(body) or key
            checklist = insert_checklist_item(
                checklist, "Needs Attention",
                f"- [ ] {key} — {title}{conf} | draft: "
                f"alignment/drafts/{key}.md | resurfaced {date}",
                "## Routine Review")
            result["warning"] = (result.get("warning", "") +
                                 " no deferred checklist line found — "
                                 "inserted a bare re-pend").strip()
        result["repended"] = section or "Needs Attention"

    if stale:
        result["warning"] = (result.get("warning", "") +
                             f" card grounded at {grounded[:8]}, HEAD is "
                             f"{head[:8]} — stale; a fresh draft is the "
                             "safer call (flip the backlog marker [A]→[ ] "
                             "so the next align run redrafts it)").strip()
    return result, checklist


def handle_unpark(orch: Path, checklist: list, backlog_dir: Path,
                  key: str, parked: Path, date: str, note: str) -> tuple:
    """The rethink path: parked card → superseded/ and backlog [A]→[ ] so
    the next align run redrafts it fresh."""
    result = {"key": key, "verdict": "unpark"}
    body = parked.read_text(encoding="utf-8")
    superseded = orch / "alignment" / "superseded"
    superseded.mkdir(parents=True, exist_ok=True)
    stamp_s = datetime.now().strftime("%Y-%m-%dT%H%M")
    parked.replace(superseded / f"{key}.{stamp_s}.md")
    result["superseded"] = f"alignment/superseded/{key}.{stamp_s}.md"
    if flip_backlog(backlog_dir, card_backlog(body), key, " ", note):
        result["backlog"] = "[A]→[ ] — item redrafts on the next align scan"
    else:
        result["warning"] = ("backlog marker [A] not found for "
                             f"{card_backlog(body)}:{key} — flip it manually "
                             "or the item never redrafts")
    return result, checklist_apply(
        checklist, key, "unparked", date, note,
        sections={"Needs Attention", "Routine Review"})


def ensure_doctrine(doctrine_path: Path) -> bool:
    """Scaffold doctrine.md when absent — corrections must never silently drop."""
    if doctrine_path.is_file():
        return False
    doctrine_path.write_text(
        "# Doctrine\n\n## Decision Log\n\n", encoding="utf-8")
    return True


def doctrine_entry(doctrine_path: Path, date: str, hm: str, key: str,
                   decision: str, reason: str, lesson: str):
    """Insert a Decision Log entry newest-first, after the section heading."""
    text = doctrine_path.read_text(encoding="utf-8")
    entry = (
        f"### {date} {hm} — {key}\n"
        f"- decision: {decision}\n"
        f"- reason: {reason or '(not given)'}\n"
        f"- lesson: {lesson or '(not given)'}\n\n"
    )
    marker = "## Decision Log"
    idx = text.find(marker)
    if idx == -1:
        text = text.rstrip() + f"\n\n{marker}\n\n"
        idx = text.find(marker)
    insert_at = text.find("\n", idx) + 1
    # skip the HTML comment block under the heading if present
    rest = text[insert_at:]
    m = re.match(r"\n*<!--.*?-->\n*", rest, re.S)
    if m:
        insert_at += m.end()
    text = text[:insert_at] + "\n" + entry + text[insert_at:]
    doctrine_path.write_text(text, encoding="utf-8")


def cleanup_dead_worktrees(proj_root: Path, orch: Path,
                           skip: Optional[set] = None) -> list:
    """Verdict-triggered worktree cleanup — "kept until deliverables are
    reviewed and approved, then cleaned up". Delegates the dead-worktree
    rules to cdo-platform's sweep-worktrees.py (the shared
    implementation — watch.py's janitor uses it too); just-rejected
    keys are passed through as --skip-key so their trees survive the
    rollback/reshape escalation."""
    script = proj_root / ".agents" / "skills" / "cdo-platform" / \
        "scripts" / "sweep-worktrees.py"
    cmd = [sys.executable, str(script), "--project-root", str(proj_root),
           "--orchestration-dir", str(orch)]
    for k in sorted(skip or ()):
        cmd += ["--skip-key", k]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        res = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return [f"worktree sweep failed: "
                f"{(proc.stderr or proc.stdout)[:120]}"]
    return [f"removed {n}" for n in res.get("removed", [])] + \
        res.get("kept", []) + res.get("errors", [])


def advance_lane_to_tip(proj_root: Path, lane: str) -> dict:
    """Converge the local ship-target branch to cdo-lane at the review
    boundary — the same "preview = shipped, pending deploy" mirror the
    ship legs maintain. --reconcile checkpoints org-state churn and
    merges when FF is blocked; a refusal (code-path conflict, staged
    index) reports only — the verdicts already applied."""
    script = proj_root / ".agents" / "skills" / "cdo-platform" / \
        "scripts" / "advance-lane.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--project-root", str(proj_root),
         "run", "--to", "refs/heads/cdo-lane", "--lane", lane,
         "--reconcile"],
        capture_output=True, text=True)
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"status": "error",
                "raw": (proc.stdout or proc.stderr)[:200]}


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    proj_root = Path(args.project_root).resolve() if args.project_root \
        else orch.parent.parent
    backlog_dir = orch / "backlogs"

    decisions_path = Path(args.decisions)
    try:
        raw = decisions_path.read_text(encoding="utf-8")
        try:
            decisions = json.loads(raw)
        except json.JSONDecodeError:
            # staged verdicts land as JSONL — one decision per line
            decisions = [json.loads(l) for l in raw.splitlines() if l.strip()]
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    # a one-line staging file parses as a bare dict, not a list — normalize
    # to the list contract (a scalar/null isolates as one bad item below)
    if not isinstance(decisions, list):
        decisions = [decisions]
    # per-item validation — bad verdicts isolate; the rest still apply
    invalid = [d for d in decisions
               if not isinstance(d, dict)
               or not isinstance(d.get("verdict"), str)
               or d.get("verdict") not in VERDICTS
               or not isinstance(d.get("key"), str) or not d.get("key")]
    decisions = [d for d in decisions if d not in invalid]

    date, hm = stamp()
    touched_delivered = False
    confirmed_delivered = False
    rejected_keys = set()
    y, mth, d = date.split("-")
    archive_dir = orch / "alignment" / y / mth / d
    ledger_path = orch / "flow-ledger.yaml"
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {}
    ledger = ledger or {}
    ledger.setdefault("pool", {}).setdefault("confirmed", [])
    ledger["pool"].setdefault("quarantined", [])
    ledger.setdefault("autonomy", {"enabled": False, "streak": 0, "threshold": 10})
    # sync autonomy.enabled from config when the caller passes it
    lane = "preview"
    if args.config:
        try:
            cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
            enabled = str(((cfg.get("cdo") or {}).get("earned_autonomy") or "")
                          ).lower() in ("on", "true", "enabled", "yes")
            ledger["autonomy"]["enabled"] = enabled
            lane = str((cfg.get("cdo") or {}).get("ship_target") or "preview")
        except (OSError, yaml.YAMLError):
            pass
    # warn on unsigned cards when the P&D office exists
    pd_installed = False
    caps_path = orch / "capabilities.yaml"
    if caps_path.is_file():
        try:
            pd_installed = "cdo-product" in (
                (yaml.safe_load(caps_path.read_text(encoding="utf-8")) or {})
                .get("departments") or {})
        except yaml.YAMLError:
            pass
    doctrine_path = orch / "doctrine.md"
    checklist_path = orch / "alignment-checklist.md"
    checklist = checklist_path.read_text(encoding="utf-8").splitlines() if checklist_path.is_file() else []

    applied = []
    newly_confirmed = []
    push_approved = []
    for dec in decisions:
        key, verdict, note = dec["key"], dec["verdict"], dec.get("note", "")

        draft = orch / "alignment" / "drafts" / f"{key}.md"
        parked = orch / "alignment" / "parked" / f"{key}.md"

        if verdict in ("resurface", "unpark"):
            if not parked.is_file():
                applied.append({
                    "key": key, "verdict": verdict,
                    "warning": f"no parked card at "
                               f"alignment/parked/{key}.md — nothing to do"})
                continue
            if verdict == "resurface":
                result, checklist = handle_resurface(
                    orch, proj_root, checklist, key, parked, draft, date, note)
            else:
                result, checklist = handle_unpark(
                    orch, checklist, backlog_dir, key, parked, date, note)
            applied.append(result)
            continue

        if verdict == "defer":
            result = {"key": key, "verdict": "deferred"}
            if draft.is_file():
                # park the card — "looked at, consciously not now" doesn't
                # belong in drafts/ (that says unexamined). Backlog marker
                # stays [A]: the item is still alignment-pending, dormant.
                parked.parent.mkdir(parents=True, exist_ok=True)
                parked.write_text(
                    stamp_card(
                        draft.read_text(encoding="utf-8"),
                        f"deferred {date} {hm} UTC"
                        + (f" — {note}" if note else "")),
                    encoding="utf-8")
                draft.unlink()
                checklist = checklist_apply(
                    checklist, key, "deferred", date, note,
                    sections={"Needs Attention", "Routine Review"})
                result["parked"] = f"alignment/parked/{key}.md"
            elif parked.is_file():
                result["note"] = "already parked"
            applied.append(result)
            continue

        # card verdicts can't land on a parked card — confirm would skip
        # every card branch (archive, pool, sprint flip) while leaving the
        # parked file and [A] marker as zombies; route it through resurface
        # or unpark first so the Operator's intent is explicit.
        if verdict in CARD_VERDICTS and parked.is_file() \
                and not draft.is_file():
            applied.append({
                "key": key, "verdict": verdict,
                "warning": f"{verdict} can't land — {key}'s card is "
                           "parked; resurface it first (or unpark for a "
                           "fresh draft)"})
            continue

        is_card = draft.is_file()
        result = {"key": key, "verdict": verdict, "card": is_card}

        # requisition-style verdicts only apply to non-card items
        if verdict in ("granted", "blocked") and is_card:
            result["warning"] = f"'{verdict}' on a card item — use confirm/reject"
        if verdict in CARD_VERDICTS and not is_card and \
                verdict in ("confirm", "confirm-edited"):
            result["warning"] = ("no draft card found — applied to checklist "
                                 "line only; if this was a story, its card is missing")

        if is_card and verdict in CARD_VERDICTS:
            body = draft.read_text(encoding="utf-8")
            conf_m = CONF_RE.search(body)
            conf = int(conf_m.group(1)) if conf_m else 0
            backlog_m = re.search(r"- \*\*Source:\*\* `([^`]+)`", body)
            backlog = backlog_m.group(1).split("/")[-1].replace(".md", "") if backlog_m else "code"

            archive_dir.mkdir(parents=True, exist_ok=True)
            verdict_head = f"<!-- {verdict} {date} {hm} UTC" + (f" — {note}" if note else "") + " -->\n\n"
            (archive_dir / f"{key}.md").write_text(verdict_head + body, encoding="utf-8")
            draft.unlink()
            result["archived"] = f"alignment/{y}/{mth}/{d}/{key}.md"

            if pd_installed and "P&D co-sign" not in body:
                result["warning"] = (result.get("warning", "") +
                                     " card lacks a P&D co-sign stamp — the "
                                     "co-sign gate was skipped").strip()

            if verdict in ("confirm", "confirm-edited"):
                flip_backlog(backlog_dir, backlog, key, "x", note)
                flipped = flip_sprint_proposed(proj_root, key)
                if flipped:
                    result["sprint_status"] = f"{flipped}: proposed→backlog"
                if key not in ledger["pool"]["confirmed"]:
                    ledger["pool"]["confirmed"].append(key)
                # a re-confirm of a quarantined key lifts the quarantine —
                # confirmed+quarantined is contradictory pool state
                before_q = len(ledger["pool"]["quarantined"])
                ledger["pool"]["quarantined"] = [
                    q for q in ledger["pool"]["quarantined"]
                    if (q.get("key") if isinstance(q, dict) else q) != key]
                if len(ledger["pool"]["quarantined"]) < before_q:
                    result["unquarantined"] = True
                st = ledger.setdefault("stories", {}).setdefault(key, {})
                if not st.get("status") or st["status"] in (
                        "done", "verified", "shipped",
                        "blocked", "killed", "deferred"):
                    # re-confirming a terminal key is a deliberate redo —
                    # reset so dashboards and the drain see pending work
                    st["status"] = "queued"
                newly_confirmed.append(key)
            else:
                flip_backlog(backlog_dir, backlog, key, "-", note or "rejected")
                obsoleted = flip_sprint_proposed(proj_root, key,
                                               "obsolete")
                if obsoleted:
                    result["sprint_status"] = f"{obsoleted}: proposed→obsolete"
                if key not in [q.get("key") for q in
                               ledger["pool"]["quarantined"]
                               if isinstance(q, dict)]:
                    ledger["pool"]["quarantined"].append(
                        {"key": key, "reason": note or "rejected by the Operator"})
                # a reject must un-confirm — an earlier confirm may have
                # pooled this key already, and pool.confirmed drives dispatch
                ledger["pool"]["confirmed"] = [
                    k for k in ledger["pool"]["confirmed"] if k != key]

            # streak bookkeeping — correction resets; high-conf confirm increments
            if verdict == "confirm" and conf >= STREAK_CONF_MIN:
                ledger["autonomy"]["streak"] = ledger["autonomy"].get("streak", 0) + 1
                result["streak"] = ledger["autonomy"]["streak"]
            elif verdict in ("confirm-edited", "reject"):
                ledger["autonomy"]["streak"] = 0
                result["streak_reset"] = True

            # corrections and rejections become doctrine
            if verdict in ("confirm-edited", "reject"):
                if ensure_doctrine(doctrine_path):
                    result["warning"] = (result.get("warning", "") +
                                         " doctrine.md was missing — "
                                         "scaffolded so corrections still "
                                         "journal").strip()
                doctrine_entry(
                    doctrine_path, date, hm, key,
                    "approved-with-edits" if verdict == "confirm-edited" else "rejected",
                    note, dec.get("lesson", ""),
                )
                result["journaled"] = True
        else:
            # non-card checklist item (escalation, sign-off, requisition)
            if verdict in ("reject", "confirm-edited"):
                if ensure_doctrine(doctrine_path):
                    result["warning"] = (result.get("warning", "") +
                                         " doctrine.md was missing — "
                                         "scaffolded so corrections still "
                                         "journal").strip()
                doctrine_entry(doctrine_path, date, hm, key,
                               "rejected" if verdict == "reject" else "approved-with-edits",
                               note, dec.get("lesson", ""))
            # a Delivered item the Operator rejects needs a follow-up escalation —
            # the work already shipped, so the verdict can't just mark the
            # line. The Marshal's verdict steers what kind: flagged:card-* on
            # the delivery review means the ALIGNMENT was wrong (reshape),
            # anything else means the DELIVERY was wrong (rollback). Deferred
            # below — inserting now would let checklist_apply instantly
            # resolve the fresh `- [ ] {key}` escalation line.
            st = (ledger.get("stories") or {}).get(key) or {}
            dv = (st.get("delivery_review") or {}).get("verdict", "")
            sections = item_sections(checklist, key)
            if "Delivered" in sections:
                touched_delivered = True
                if verdict == "reject":
                    rejected_keys.add(key)
                elif verdict == "confirm":
                    confirmed_delivered = True
            if "Delivered" in sections and verdict == "reject" \
                    and st.get("delivery_review"):
                result["escalated"] = "reshape" if str(dv).startswith(
                    "flagged:card") else "rollback"
            elif "Delivered" in sections and verdict == "reject" \
                    and st.get("status") in (
                        "shipped", "blocked", "killed", "deferred"):
                # delivered work rejected but the review stamp is missing —
                # no verdict to steer by, so don't steer to nothing
                result["escalated"] = "triage"
                result["warning"] = (result.get("warning", "") +
                                     " review record missing — filed generic "
                                     "escalation, triage manually").strip()

            # pre-deploy gating — signing runs BEFORE re-marking: a confirm
            # resolving a pending sign-off line signs the sha it asked about
            # (a re-ship then clears signed_at when it re-queues the ask).
            # Signing is the ONLY authorization cdo-platform's push leg reads.
            if "Pre-deploy Sign-offs" in sections:
                has_story = key in (ledger.get("stories") or {})
                pd = st.setdefault("pre_deploy", {}) if has_story else None
                if verdict in ("confirm", "confirm-edited", "granted"):
                    if pd is not None:
                        pd["signed_at"] = f"{date} {hm}"
                    push_approved.append(key)
                    result["pre_deploy_signed"] = True
                    if not has_story:
                        result["warning"] = (result.get("warning", "") +
                                             " signed pre-deploy item has no "
                                             "story record — push-lane will "
                                             "not see it").strip()
                elif verdict in ("reject", "blocked"):
                    if pd is not None:
                        pd["rejected"] = {"at": f"{date} {hm}", "note": note}
                    result["pre_deploy_rejected"] = True
                    if verdict == "blocked":
                        ensure_doctrine(doctrine_path)
                        doctrine_entry(doctrine_path, date, hm, key,
                                       "blocked", note, dec.get("lesson", ""))
                        result["journaled"] = True
            # the Delivered accept marks for pre-deploy — the sign-off item
            # then carries the push itself (filed after checklist_apply so
            # this same verdict can't instantly resolve it)
            if "Delivered" in sections and verdict in (
                    "confirm", "confirm-edited", "granted"):
                sha = st.get("lane_sha") or ""
                pushed_sha = (st.get("pushed") or {}).get("sha") or ""
                if st.get("status") == "shipped" \
                        and not (sha and pushed_sha == sha):
                    pd = st.setdefault("pre_deploy", {})
                    # re-mark when the lane sha moved past the last mark —
                    # a re-ship retires the stale ask and re-queues the push
                    if not pd.get("marked_at") or pd.get("sha") != sha:
                        if pd.get("sha") and pd.get("sha") != sha:
                            # supersede NOW — checklist_apply would otherwise
                            # resolve the stale pending line as this verdict
                            checklist = supersede_checklist_item(
                                checklist, "Pre-deploy Sign-offs", key, date)
                        pd["marked_at"] = f"{date} {hm}"
                        pd["sha"] = sha
                        pd.pop("signed_at", None)
                        pd.pop("rejected", None)
                        # deferred insert — checklist_apply below must not
                        # instantly resolve the fresh `- [ ] {key}` line
                        result["pre_deploy_marked"] = True
                elif st.get("status") == "shipped":
                    result["pre_deploy_skipped"] = "already on origin"

        checklist = checklist_apply(checklist, key, verdict, date, note)
        # a verdict that resolved a `| review:` line graduates the staged
        # audit doc out of reviews/ — that's what makes reviews/ read as
        # "shipped, awaiting Operator" at a glance
        grad = graduate_review_docs(orch, key, checklist, ledger, date)
        if grad["moved"]:
            result["review_graduated"] = "; ".join(grad["moved"])
        if grad["warnings"]:
            result["warning"] = (result.get("warning", "") +
                                 " " + "; ".join(grad["warnings"])).strip()
        if result.get("escalated"):
            if result["escalated"] == "reshape":
                esc = (f"- [ ] {key} — card judged wrong at delivery review "
                       f"({note or 'see review doc'}) — reshape/re-align?")
            elif result["escalated"] == "triage":
                esc = (f"- [ ] {key} — delivered work rejected "
                       f"({note or 'no note'}) — review record missing, "
                       "triage manually")
            else:
                esc = (f"- [ ] {key} — delivered work rejected "
                       f"({note or 'see review doc'}) — rollback via "
                       "cdo-platform?")
            insert_at = next(
                (i + 1 for i, l in enumerate(checklist)
                 if l.strip().startswith("## Escalations")),
                len(checklist))
            checklist.insert(insert_at, esc)
        if result.get("pre_deploy_marked"):
            sha = st.get("lane_sha") or ""
            checklist = insert_checklist_item(
                checklist, "Pre-deploy Sign-offs",
                f"- [ ] {key} — push to origin/{lane}"
                + (f" | lane {sha[:8]}" if sha else "")
                + f" | marked {date}",
                "## Deploy Sign-offs")
        applied.append(result)

    if checklist_path.is_file():
        checklist_path.write_text("\n".join(checklist) + "\n", encoding="utf-8")
    if args.consume:
        try:
            # partial apply keeps just the invalid lines — a re-run must not
            # double-apply the ones that already landed
            if invalid:
                decisions_path.write_text(
                    "".join(json.dumps(d) + "\n" for d in invalid),
                    encoding="utf-8")
            else:
                decisions_path.unlink()
        except OSError:
            pass
    if ledger_path.is_file():
        # atomic — workers write this ledger concurrently now
        tmp = ledger_path.with_suffix(".yaml.tmp")
        tmp.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
        os.replace(tmp, ledger_path)

    wt_report = lane_adv = None
    notices = []
    if confirmed_delivered:
        wt_report = cleanup_dead_worktrees(proj_root, orch,
                                           skip=rejected_keys)
        notices += [w for w in wt_report if "remove failed" in w]
    if touched_delivered:
        lane_adv = advance_lane_to_tip(proj_root, lane)
        if lane_adv.get("status") not in \
                ("advanced", "already-abreast", "reconciled"):
            notices.append(
                "lane advance refused: " + "; ".join(
                    lane_adv.get("errors",
                                 [lane_adv.get("status", "?")])[:2]))

    out = json.dumps({
        "status": "partial" if invalid else "success",
        "applied": applied,
        "invalid": invalid,
        # surface refusal signals top-level — nested-JSON refusals buried
        # inside a success verdict are how the lane silently goes stale
        "warnings": [a.get("warning") for a in applied if a.get("warning")]
                    + notices,
        "confirmed_pool": ledger["pool"]["confirmed"],
        # keys this pass just confirmed — the auto-dispatch pass in cdo-review
        # runs ready-set.py over these (plus anything already pooled)
        "newly_confirmed": newly_confirmed,
        # keys whose ## Pre-deploy Sign-offs items were just signed — the
        # caller runs cdo-platform's push leg (push-lane.py) over these;
        # one push publishes the newest signed lane commit to origin.
        # Net state — a same-pass re-mark can retire a just-signed ask
        "push_approved": [
            k for k in push_approved
            if (((ledger.get("stories") or {}).get(k) or {})
                .get("pre_deploy") or {}).get("signed_at")],
        # Delivered CONFIRMS trigger the worktree cleanup — "kept until
        # reviewed and approved, then cleaned up" (watch janitor
        # backstops); just-rejected keys keep their trees while the
        # rollback/reshape escalation is live
        "worktrees": wt_report,
        # and converge the ship-target branch to the lane tip so the
        # checkout being reviewed against actually shows the shipped work
        "lane_advance": lane_adv,
        "autonomy": ledger["autonomy"],
    }, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    if invalid:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
