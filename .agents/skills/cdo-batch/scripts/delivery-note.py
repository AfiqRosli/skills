# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""delivery-note.py — the output side of the fresh-eyes contract.

Alignment interrogates the product office's INPUT before dispatch; this
interrogates the work's OUTPUT after it. No story reaches the Operator as the
worker's self-report — a separate session (or Marshal) reads the evidence
(card, intent.md, ledger findings, sessions/{key}.md, the actual diff), writes
a durable assessment doc under alignment/reviews/ — the Operator-pending
staging — THEN files the one-line checklist briefing pointing at it. The
doc STAYS staged: the Operator's verdict on the line is what graduates it
beside the card (apply-decisions owns the move), so reviews/ at a glance
is the shipped-awaiting-review queue.

  pending   → terminal stories needing a review for their CURRENT attempt:
              shipped (success lane) and blocked/killed/deferred (postmortem
              lane). Excludes keys already reviewed at this attempt, on the
              checklist, or covered by a live r-* review session.
  file {key} --verdict V --note "..." --doc {path} [--session s]
            → requires the assessment doc to exist at the canonical staging
              path (alignment/reviews/{key}.review-{attempt}.md) — doc
              before line, always. Shipped stories land under
              `## Delivered`, failures under `## Escalations`. Stamps
              stories.{key}.delivery_review {verdict, attempt, at, by, note,
              doc} pointing at the staged path.
  file-wave --batch {id} --doc {path} --note "..."
            → files the batch-drain holistic read as a Delivered line and
              stamps batch.wave_review — same staging convention; the
              Operator's verdict lands it in the dated archive.
  spawn-review {key} → delegate to spawn-dispatch.py --kind review (dedupes on
              current-attempt state). Honors cdo.dispatch_mode — `manual`
              refuses spawning: Marshal files reviews by hand.
  pending-extract → shipped stories missing academy extraction for their
              CURRENT attempt — no extract stamp and no live a-* session.
              The MANUAL extraction surface: extraction is never
              auto-spawned on ship — the Operator/Marshal decides when it
              runs. Each entry carries `delivered` state (awaiting-review
              | review-filed | confirmed) so approved work and
              still-awaiting-review work are distinguishable at a glance.
  file-extract {key} [--doc {path}] [--session s]
            → stamp stories.{key}.extract {attempt, at, by, doc}. Requires
              learning/knowledge/{key}.yaml to exist — evidence before stamp,
              same contract as file's doc-before-line.

Verdicts (convention, enforced by prompts not code):
  shipped   → sound | flagged:delivery-{x} | flagged:card-{x}
  failed    → postmortem:{clean|hollow}
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cardlayout import confirmed_card, staged_review_doc  # noqa: E402

DELIVERED_SECTION = "## Delivered"
ESCALATIONS_SECTION = "## Escalations"
REVIEWABLE_STATUSES = {"shipped", "blocked", "killed", "deferred"}
LINE_RE = re.compile(r"^- \[(?P<mark>[ xA\-])\] (?P<key>[A-Za-z0-9_-]+)\b")


def parse_args():
    p = argparse.ArgumentParser(description="Delivered-review briefing surface.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--stall-timeout-minutes", type=int, default=45)
    p.add_argument("-o", "--output")
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("pending")
    f = sub.add_parser("file")
    f.add_argument("key")
    f.add_argument("--verdict", required=True,
                   help="sound | flagged:delivery-{x} | flagged:card-{x} | "
                        "postmortem:{clean|hollow}")
    f.add_argument("--note", required=True,
                   help="one line — Marshal's assessed read")
    f.add_argument("--doc", default="",
                   help="assessment doc path (default: canonical staging "
                        "alignment/reviews/{key}.review-{attempt}.md — must "
                        "exist; stays staged until the Operator's verdict "
                        "graduates it beside the card)")
    f.add_argument("--session", default="")
    s = sub.add_parser("spawn-review")
    s.add_argument("key")
    s.add_argument("--project-root", default="",
                   help="default: orchestration dir's grandparent")
    s.add_argument("--permission-mode", default="bypass")
    s.add_argument("--devin-bin", default="devin")
    s.add_argument("--dry-run", action="store_true")
    sub.add_parser("pending-extract")
    fe = sub.add_parser("file-extract")
    fe.add_argument("key")
    fe.add_argument("--doc", default="",
                    help="default: learning/knowledge/{key}.yaml — must exist")
    fe.add_argument("--session", default="")
    w = sub.add_parser("file-wave")
    w.add_argument("--batch", required=True)
    w.add_argument("--doc", default="",
                   help="wave doc — default: staging at "
                        "alignment/reviews/wave-{batch}.md; the Operator's "
                        "verdict lands it in the dated archive")
    w.add_argument("--note", required=True)
    w.add_argument("--session", default="")
    return p.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def load_ledger(orch: Path):
    p = orch / "flow-ledger.yaml"
    if not p.is_file():
        return p, None
    try:
        return p, yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return p, None


def save_ledger(lpath: Path, ledger: dict):
    tmp = lpath.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
    os.replace(tmp, lpath)


# card lookup + staging path live in cardlayout.py — one definition of the
# bays/archive contract, shared with ready-set/dispatch/state-digest.
card_path = confirmed_card
review_doc_path = staged_review_doc


def checklist_item_keys(text: str) -> set:
    """Keys holding a line under Delivered OR Escalations — a review briefing
    may land in either; both count as 'already briefed'."""
    keys, in_section = set(), False
    for line in text.splitlines():
        if line.strip().startswith("## "):
            in_section = line.strip() in (DELIVERED_SECTION, ESCALATIONS_SECTION)
            continue
        if in_section:
            m = LINE_RE.match(line)
            if m:
                keys.add(m.group("key"))
    return keys


def parse_record_ts(ts: str):
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})", ts or "")
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}",
                                 "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fresh_review_keys(orch: Path, stall_minutes: int) -> set:
    """Keys whose review session is (probably) still running — a fresh
    sessions/{key}.review.json record. Stale/unparseable records don't
    suppress — a dead reviewer must not permanently shield a story."""
    keys = set()
    sessions_dir = orch / "sessions"
    if not sessions_dir.is_dir():
        return keys
    now = datetime.now(timezone.utc)
    for f in sessions_dir.glob("*.review.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        started = parse_record_ts(str(rec.get("started", "")))
        if started and (now - started).total_seconds() / 60 <= stall_minutes:
            keys.add(rec.get("key") or f.stem.replace(".review", ""))
    return keys


def fresh_academy_keys(orch: Path, stall_minutes: int) -> set:
    """Keys whose academy extraction session is (probably) still running —
    a fresh sessions/{key}.academy.json record. Same stale-tolerance rule
    as reviews: a dead extractor must not permanently shield the story."""
    keys = set()
    sessions_dir = orch / "sessions"
    if not sessions_dir.is_dir():
        return keys
    now = datetime.now(timezone.utc)
    for f in sessions_dir.glob("*.academy.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        started = parse_record_ts(str(rec.get("started", "")))
        if started and (now - started).total_seconds() / 60 <= stall_minutes:
            keys.add(rec.get("key") or f.stem.replace(".academy", ""))
    return keys


def extract_doc_path(orch: Path, key: str):
    """The knowledge graph the a-{key} session should have produced."""
    return orch / "learning" / "knowledge" / f"{key}.yaml"


def needs_extract(st: dict) -> bool:
    """True when a story shipped and its extract stamp doesn't cover the
    CURRENT attempt — mirrors needs_review's attempt-awareness."""
    if st.get("status") != "shipped":
        return False
    attempt = st.get("attempts") or 1
    extracted = st.get("extract") or {}
    return extracted.get("attempt") != attempt


def needs_review(st: dict) -> bool:
    """True when a story sits at a reviewable terminal status and its
    delivery_review stamp doesn't cover the CURRENT attempt."""
    if st.get("status") not in REVIEWABLE_STATUSES:
        return False
    attempt = st.get("attempts") or 1
    reviewed = st.get("delivery_review") or {}
    return reviewed.get("attempt") != attempt


def cmd_pending(orch: Path, stall_minutes: int) -> dict:
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        return {"status": "error",
                "errors": ["flow-ledger.yaml missing/unparseable"]}
    checklist = orch / "alignment-checklist.md"
    on_checklist = checklist_item_keys(
        checklist.read_text(encoding="utf-8", errors="replace")
    ) if checklist.is_file() else set()
    reviewing = fresh_review_keys(orch, stall_minutes)

    pending = []
    for key, st in (ledger.get("stories") or {}).items():
        if not isinstance(st, dict) or not needs_review(st):
            continue
        if key in on_checklist or key in reviewing:
            continue
        findings = st.get("findings") or []
        attempt = st.get("attempts") or 1
        doc = review_doc_path(orch, key, attempt)
        card = card_path(orch, key)
        pending.append({
            "key": key,
            "status": st["status"],
            "attempt": attempt,
            "session": st.get("session"),
            "findings_tail": findings[-1] if findings else None,
            "card": card.relative_to(orch).as_posix() if card else None,
            "review_doc": doc.relative_to(orch).as_posix() if doc else None,
            "session_report": f"sessions/{key}.md",
            "acp_record": "sessions/{key}.acp.json (lone dispatch) or sessions/drain.acp.json (drain)",
        })
    return {"status": "ok", "pending": pending, "count": len(pending)}


def delivered_state(st: dict) -> str:
    """Where a shipped story sits in the Delivered-review arc — the
    Operator's accept decision is what makes a delivered story 'approved'.
    pre_deploy.marked_at is stamped when a Delivered confirm files the
    sign-off item; delivery_review.attempt covering the current attempt
    means an auditor filed and the verdict awaits the Operator."""
    pd = st.get("pre_deploy") or {}
    if pd.get("marked_at") or pd.get("signed_at"):
        return "confirmed"
    dr = st.get("delivery_review") or {}
    if dr.get("attempt") == (st.get("attempts") or 1):
        return "review-filed"
    return "awaiting-review"


def cmd_pending_extract(orch: Path, stall_minutes: int) -> dict:
    """Shipped stories whose extraction never landed — the manual
    extraction surface. Extraction is Operator/Marshal-invoked only
    (never auto-spawned on ship): extract inline via `cdo-academy
    extract {key}` or deliberate-spawn
    `spawn-dispatch.py --kind academy --key {key}`."""
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        return {"status": "error",
                "errors": ["flow-ledger.yaml missing/unparseable"]}
    extracting = fresh_academy_keys(orch, stall_minutes)

    pending = []
    for key, st in (ledger.get("stories") or {}).items():
        if not isinstance(st, dict) or not needs_extract(st):
            continue
        if key in extracting:
            continue
        doc = extract_doc_path(orch, key)
        pending.append({
            "key": key,
            "attempt": st.get("attempts") or 1,
            "delivered": delivered_state(st),
            "review_verdict":
                (st.get("delivery_review") or {}).get("verdict"),
            "knowledge_file": doc.relative_to(orch).as_posix(),
            "knowledge_exists": doc.is_file(),
        })
    return {"status": "ok", "pending_extract": pending,
            "count": len(pending)}


def cmd_file_extract(orch: Path, args) -> dict:
    """Stamp stories.{key}.extract — the extraction session's filing act.
    Evidence-first like `file`: the knowledge yaml must exist before the
    stamp lands, so a stamp can't certify an extraction that didn't happen."""
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        return {"status": "error",
                "errors": ["flow-ledger.yaml missing/unparseable"]}
    st = (ledger.get("stories") or {}).get(args.key)
    if not isinstance(st, dict) or st.get("status") != "shipped":
        return {"status": "refused",
                "reason": f"{args.key} is not shipped "
                          f"({(st or {}).get('status', 'absent')})"}
    attempt = st.get("attempts") or 1
    doc = Path(args.doc) if args.doc else extract_doc_path(orch, args.key)
    if not doc.is_absolute():
        doc = (orch / doc).resolve()
    if not doc.is_file():
        return {"status": "refused",
                "reason": f"knowledge file missing: {doc} — extract before "
                          "stamping"}
    try:
        doc_rel = doc.relative_to(orch).as_posix()
    except ValueError:
        return {"status": "refused",
                "reason": f"doc must live under the orchestration dir: {doc}"}

    st["extract"] = {"attempt": attempt, "at": now_iso(),
                     "by": args.session or "marshal", "doc": doc_rel}
    save_ledger(lpath, ledger)
    return {"status": "filed", "key": args.key, "attempt": attempt,
            "doc": doc_rel}


def cmd_file(orch: Path, args) -> dict:
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        return {"status": "error",
                "errors": ["flow-ledger.yaml missing/unparseable"]}
    st = (ledger.get("stories") or {}).get(args.key)
    if not isinstance(st, dict) or st.get("status") not in REVIEWABLE_STATUSES:
        return {"status": "refused",
                "reason": f"{args.key} is not at a reviewable terminal status "
                          f"({(st or {}).get('status', 'absent')})"}
    attempt = st.get("attempts") or 1
    existing = st.get("delivery_review") or {}
    if existing.get("attempt") == attempt:
        return {"status": "refused",
                "reason": f"{args.key} already reviewed at attempt {attempt} "
                          f"({existing.get('at')}) — a re-ship bumps attempts"}

    # the assessment doc is a precondition — the line must point at reasoning,
    # never stand alone. Default resolution: staging path first, then beside
    # the card (a doc already beside the card counts — a Marshal hand-file
    # or a re-run must not be refused for skipping staging).
    card = card_path(orch, args.key)
    doc = Path(args.doc) if args.doc else None
    if doc is None:
        staged = review_doc_path(orch, args.key, attempt)
        final = card.parent / f"{args.key}.review-{attempt}.md" \
            if card is not None else None
        doc = staged if staged.is_file() \
            else final if final is not None and final.is_file() \
            else staged
    if not doc.is_absolute():
        doc = (orch / doc).resolve()
    if not doc.is_file():
        return {"status": "refused",
                "reason": f"assessment doc missing: {doc} — write the review "
                          "before filing the line"}
    # containment BEFORE any move — a refused filing must not mutate the FS;
    # an external --doc must never be silently relocated into the archive
    try:
        doc.relative_to(orch)
    except ValueError:
        return {"status": "refused",
                "reason": f"doc must live under the orchestration dir: {doc}"}

    checklist_path = orch / "alignment-checklist.md"
    if not checklist_path.is_file():
        return {"status": "error",
                "errors": ["alignment-checklist.md missing"]}
    text = checklist_path.read_text(encoding="utf-8")
    if args.key in checklist_item_keys(text):
        return {"status": "refused",
                "reason": f"{args.key} already holds a briefing line"}

    # the doc STAYS staged — reviews/ is the Operator-pending queue: the
    # verdict on this line is what graduates the doc beside the card
    # (apply-decisions owns the move). A doc already beside the card
    # (legacy/hand-filed) stays put.
    doc_rel = doc.relative_to(orch).as_posix()

    section = DELIVERED_SECTION if st["status"] == "shipped" \
        else ESCALATIONS_SECTION
    line = (f"- [ ] {args.key} — {args.note} | verdict: {args.verdict} "
            f"| review: {doc_rel} | filed {now_iso()}"
            + (f" by {args.session}" if args.session else ""))
    lines, placed = text.splitlines(), False
    out = []
    for l in lines:
        out.append(l)
        if not placed and l.strip() == section:
            out.extend(["", line])
            placed = True
    if not placed:
        out.extend(["", section, "", line])
    checklist_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    st["delivery_review"] = {
        "verdict": args.verdict,
        "attempt": attempt,
        "at": now_iso(),
        "by": args.session or "marshal",
        "note": args.note,
        "doc": doc_rel,
    }
    save_ledger(lpath, ledger)
    result = {"status": "filed", "key": args.key, "verdict": args.verdict,
              "attempt": attempt, "section": section, "doc": doc_rel}
    if card is None:
        result["warning"] = ("no confirmed card found — the doc stays in "
                             "alignment/reviews/; it graduates when the "
                             "Operator's verdict lands and a card exists")
    return result


def cmd_file_wave(orch: Path, args) -> dict:
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        return {"status": "error",
                "errors": ["flow-ledger.yaml missing/unparseable"]}
    batch = ledger.setdefault("batch", {})
    if batch.get("wave_review"):
        return {"status": "refused",
                "reason": f"wave review for {batch.get('id')} already filed"}
    # same staging convention as per-story reviews: the wave doc lives at
    # alignment/reviews/wave-{batch}.md while Operator-pending — the
    # verdict on its line lands it in the dated archive (apply-decisions
    # owns the move; a doc already placed elsewhere stays put —
    # containment still enforced)
    doc = Path(args.doc) if args.doc \
        else orch / "alignment" / "reviews" / f"wave-{args.batch}.md"
    if not doc.is_absolute():
        doc = (orch / doc).resolve()
    if not doc.is_file():
        return {"status": "refused",
                "reason": f"wave doc missing: {doc}"}
    try:
        doc_rel = doc.relative_to(orch).as_posix()
    except ValueError:
        return {"status": "refused",
                "reason": f"doc must live under the orchestration dir: {doc}"}

    checklist_path = orch / "alignment-checklist.md"
    line = (f"- [ ] wave-{args.batch} — {args.note} "
            f"| review: {doc_rel} | filed {now_iso()}"
            + (f" by {args.session}" if args.session else ""))
    text = checklist_path.read_text(encoding="utf-8", errors="replace") \
        if checklist_path.is_file() else "# Alignment Checklist\n"
    out, placed = [], False
    for l in text.splitlines():
        out.append(l)
        if not placed and l.strip() == DELIVERED_SECTION:
            out.extend(["", line])
            placed = True
    if not placed:
        out.extend(["", DELIVERED_SECTION, "", line])
    checklist_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    batch["wave_review"] = {"at": now_iso(), "doc": doc_rel,
                            "by": args.session or "marshal"}
    save_ledger(lpath, ledger)
    return {"status": "filed", "batch": args.batch, "doc": doc_rel}


def dispatch_mode(root: Path) -> str:
    cfg = root / "_bmad" / "config.yaml"
    if cfg.is_file():
        try:
            return str((yaml.safe_load(
                cfg.read_text(encoding="utf-8")) or {}).get("cdo", {})
                .get("dispatch_mode", "auto"))
        except yaml.YAMLError:
            pass
    return "auto"


def cmd_spawn_review(orch: Path, args) -> dict:
    """Trigger the story's review session — the worker's last act at any
    terminal state, or Marshal/janitor's mop-up when a review never fired."""
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        return {"status": "error",
                "errors": ["flow-ledger.yaml missing/unparseable"]}
    st = (ledger.get("stories") or {}).get(args.key)
    if not isinstance(st, dict) or not needs_review(st):
        status = (st or {}).get("status", "absent")
        return {"status": "refused",
                "reason": f"{args.key} needs no review (status: {status}, "
                          "or current attempt already reviewed)"}
    checklist = orch / "alignment-checklist.md"
    if checklist.is_file() and args.key in checklist_item_keys(
            checklist.read_text(encoding="utf-8", errors="replace")):
        return {"status": "refused",
                "reason": f"{args.key} already holds a briefing line"}
    if args.key in fresh_review_keys(orch, args.stall_timeout_minutes):
        return {"status": "refused",
                "reason": f"a review session for {args.key} is already "
                          "in-flight (fresh record)"}

    root = Path(args.project_root).resolve() if args.project_root \
        else orch.parent.parent
    if dispatch_mode(root) == "manual":
        return {"status": "refused",
                "reason": "dispatch_mode: manual — file the review yourself "
                          "(delivery-note.py file {key} ...)"}

    spawn = Path(__file__).parent / "spawn-dispatch.py"
    cmd = [sys.executable, str(spawn), "--orchestration-dir", str(orch),
           "--project-root", str(root), "--key", args.key,
           "--kind", "review", "--permission-mode", args.permission_mode,
           "--devin-bin", args.devin_bin]
    if args.dry_run:
        cmd.append("--dry-run")
    run_kw = {}
    if os.name == "nt":
        # workers run consoleless — hide the child's console or Windows
        # allocates a visible one that flashes a command prompt per spawn
        run_kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.run(cmd, capture_output=True, text=True, **run_kw)
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else \
            {"errors": [proc.stderr.strip() or "spawn produced no output"]}
    except json.JSONDecodeError:
        payload = {"errors": [f"spawn output unparseable: {proc.stdout[:200]}"]}
    payload["kind"] = "review"
    return payload


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    if not orch.is_dir():
        print(json.dumps({"errors": [f"orchestration dir not found: {orch}"]}))
        sys.exit(2)
    if args.action == "pending":
        result = cmd_pending(orch, args.stall_timeout_minutes)
    elif args.action == "pending-extract":
        result = cmd_pending_extract(orch, args.stall_timeout_minutes)
    elif args.action == "file-extract":
        result = cmd_file_extract(orch, args)
    elif args.action == "file":
        result = cmd_file(orch, args)
    elif args.action == "file-wave":
        result = cmd_file_wave(orch, args)
    else:
        result = cmd_spawn_review(orch, args)
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    sys.exit(0 if result.get("status") in ("ok", "filed", "spawned", "dry-run") else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
