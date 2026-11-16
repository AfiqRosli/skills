#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Org-state digest — the machine-parseable read of the orchestration home.

Reads flow-ledger.yaml, alignment-checklist.md, frago-inbox.md, and handover.md;
emits one compact JSON the four capabilities consume instead of re-parsing
files (and fumbling timestamp math) each time.

Computes, deterministically:
  - pool depth vs buffer minimum
  - in-flight elapsed time vs stall threshold (flags stalls) — a LIST:
    a drain session runs stories serially but aux sessions (r-/a-) overlap
  - dispatch locks presence + staleness — per-story locks under locks/,
    plus the legacy dispatch.lock (double-dispatch guard is per key)
  - autonomy streak counter from checklist/doctrine markers
  - pending Operator item counts by checklist section
  - unconsumed FRAGO count (entries without a consumed marker)
  - spawned worker session records (sessions/*.json)
  - headless status contract fields

Usage:
  uv run state-digest.py --orchestration-dir /path/docs/orchestration
      [--stall-timeout-minutes 45] [--alignment-buffer-min 2] [-o out.json]

Exit codes: 0=ok, 1=state-integrity anomalies found (digest still emitted), 2=error
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

from cardlayout import CONF_RE, confirmed_card  # noqa: E402

TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2})")
UNCONSUMED_RE = re.compile(r"^###\s+\d{4}-\d{2}-\d{2}", re.M)


def parse_args():
    p = argparse.ArgumentParser(description="Emit a JSON digest of the cdo orchestration state.")
    p.add_argument("--orchestration-dir", required=True, help="Resolved orchestration home")
    p.add_argument("--stall-timeout-minutes", type=int, default=45)
    p.add_argument("--alignment-buffer-min", type=int, default=2)
    p.add_argument("-o", "--output", help="Write JSON to file instead of stdout")
    return p.parse_args()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(text: str):
    m = TIMESTAMP_RE.search(text or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def checklist_counts(text: str) -> dict:
    """Count unchecked items per section heading. HTML comments are stripped
    first — format examples inside <!-- --> must not count as pending items."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    counts, current = {}, "_top"
    for line in text.splitlines():
        h = re.match(r"^##\s+(.+)$", line)
        if h:
            current = h.group(1).strip()
            counts.setdefault(current, 0)
        elif line.strip().startswith("- [ ]"):
            counts[current] = counts.get(current, 0) + 1
    return {k: v for k, v in counts.items() if v}


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    anomalies = []

    ledger = {}
    ledger_path = orch / "flow-ledger.yaml"
    if ledger_path.is_file():
        try:
            ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            anomalies.append(f"flow-ledger.yaml unparseable: {e}")
    else:
        anomalies.append("flow-ledger.yaml missing")

    # pool + batch
    pool = ledger.get("pool") or {}
    batch = ledger.get("batch") or {}
    stories = ledger.get("stories") or {}
    confirmed = pool.get("confirmed") or []
    quarantined = pool.get("quarantined") or []
    signals = ledger.get("signals") or []

    # dispatch locks — per-story locks under locks/ plus the legacy file
    locked = {}
    lock_files = []
    locks_dir = orch / "locks"
    if locks_dir.is_dir():
        lock_files += sorted(locks_dir.glob("*.lock"))
    legacy_lock = orch / "dispatch.lock"
    if legacy_lock.is_file():
        lock_files.append(legacy_lock)
    now = now_utc()
    for lf in lock_files:
        text = lf.read_text(encoding="utf-8", errors="replace")
        parts = text.split()
        session = parts[0] if parts else None
        ts = parse_ts(text)
        age = round((now - ts).total_seconds() / 60, 1) if ts else None
        # g-*.lock — a drain's spawn marker holds every queued key and
        # expires on its terminal evidence (sessions/drain.md pushed, or a
        # terminal drain.acp.json) or the 24h TTL — not the stall window
        if lf.parent.name == "locks" and lf.stem.startswith("g-"):
            drain_done = None
            drain_report = orch / "sessions" / "drain.md"
            drain_acp = orch / "sessions" / "drain.acp.json"
            if drain_report.is_file() and ts and \
                    datetime.fromtimestamp(
                        drain_report.stat().st_mtime,
                        tz=timezone.utc) > ts:
                drain_done = "sessions/drain.md landed after the marker"
            if not drain_done and drain_acp.is_file():
                try:
                    acp = json.loads(drain_acp.read_text(
                        encoding="utf-8", errors="replace"))
                    if acp.get("stop_reason"):
                        drain_done = (f"drain.acp.json terminal "
                                      f"({acp['stop_reason']})")
                except (json.JSONDecodeError, OSError):
                    pass
            if drain_done and (age is None or age <= 24 * 60):
                anomalies.append(
                    f"{lf.stem} fresh but the drain is terminal — "
                    f"{drain_done}; janitor should expire the marker")
            for k in (parts[2].split(",") if len(parts) > 2 else []):
                if k:
                    locked[k] = {
                        "session": session, "age_minutes": age,
                        "stale": age is not None and age > 24 * 60,
                        "legacy": False, "group": lf.stem,
                    }
            continue
        key = lf.stem if lf.parent.name == "locks" else \
            (parts[2] if len(parts) > 2 else lf.stem)
        locked[key] = {
            "session": session, "age_minutes": age,
            "stale": age is not None and age > args.stall_timeout_minutes * 2,
            "legacy": lf.parent.name != "locks",
        }

    # in-flight stall check — deterministic time math, not LLM arithmetic.
    # Every in-flight story should hold its own lock, drain or solo.
    in_flight = []
    stalled = []
    for key, st in stories.items():
        if isinstance(st, dict) and st.get("status") == "in-flight":
            step_started = parse_ts(str(st.get("step_started", "")))
            elapsed = round((now - step_started).total_seconds() / 60, 1) if step_started else None
            entry = {"story": key, "step": st.get("step"),
                     "elapsed_minutes": elapsed,
                     "session": st.get("session"),
                     "lock_held": key in locked}
            in_flight.append(entry)
            if not entry["lock_held"]:
                anomalies.append(f"{key} in-flight but holds no lock — unclaimed work?")
            if elapsed is not None and elapsed > args.stall_timeout_minutes:
                stalled.append(key)
            elif elapsed is None:
                anomalies.append(f"{key} in-flight with unparseable step_started")

    # spawned worker session records — sessions/{key}.json from spawn-dispatch
    live_sessions = {}
    sessions_dir = orch / "sessions"
    if sessions_dir.is_dir():
        for sf in sorted(sessions_dir.glob("*.json")):
            try:
                rec = json.loads(sf.read_text(encoding="utf-8"))
                # key by filename stem — a {key}.review.json record must not
                # clobber the dispatch worker's {key}.json entry
                live_sessions[sf.stem] = {
                    "session_name": rec.get("session_name"),
                    "pid": rec.get("pid"),
                    "started": rec.get("started"),
                }
            except json.JSONDecodeError:
                anomalies.append(f"sessions/{sf.name} unparseable")

    # delivered-but-unbriefed — shipped stories with neither a filed review
    # NOR a live r-* review session (fresh {key}.review.json counts as covered)
    reviewing = set()
    if sessions_dir.is_dir():
        for rf in sessions_dir.glob("*.review.json"):
            try:
                rec = json.loads(rf.read_text(encoding="utf-8"))
                started = parse_ts(str(rec.get("started", "")))
                if started and (now - started).total_seconds() / 60 \
                        <= args.stall_timeout_minutes:
                    reviewing.add(rec.get("key") or rf.stem.replace(".review", ""))
            except json.JSONDecodeError:
                pass
    delivered_pending = [
        key for key, st in stories.items()
        if isinstance(st, dict)
        and st.get("status") in ("shipped", "blocked", "killed", "deferred")
        and (st.get("delivery_review") or {}).get("attempt")
            != (st.get("attempts") or 1)
        and key not in reviewing
    ]

    # intent staleness — doctrine's newest entry vs intent.md's refreshed
    # stamp. A stale intent doc means both gates are reasoning off drift.
    intent_stale = None
    intent_f = orch / "intent.md"
    doctrine_f = orch / "doctrine.md"
    if intent_f.is_file() and doctrine_f.is_file():
        m_ref = re.search(r"Refreshed:\*?\*?\s*(\d{4}-\d{2}-\d{2})",
                          intent_f.read_text(encoding="utf-8", errors="replace"))
        doc_dates = re.findall(r"^### (\d{4}-\d{2}-\d{2})",
                               doctrine_f.read_text(encoding="utf-8",
                                                    errors="replace"),
                               re.M)
        if m_ref and doc_dates:
            intent_stale = max(doc_dates) > m_ref.group(1)
    elif not intent_f.is_file():
        intent_stale = True  # missing intent doc = maximally stale

    # flag-rate by confidence band — does conf% mean anything? Reads the
    # archived card's declared confidence vs the delivery verdict.
    conf_band = {}
    for key, st in stories.items():
        dv = (st or {}).get("delivery_review") if isinstance(st, dict) else None
        if not dv:
            continue
        # newest non-reject archive — a re-confirmed key's latest card
        # carries the verdict-relevant confidence (cardlayout semantics)
        card = confirmed_card(orch, key)
        m = CONF_RE.search(
            card.read_text(encoding="utf-8", errors="replace")) \
            if card else None
        band = (">=95" if m and int(m.group(1)) >= 95
                else "80-94" if m and int(m.group(1)) >= 80
                else "<80" if m else "unrated")
        b = conf_band.setdefault(band, {"filed": 0, "flagged": 0})
        b["filed"] += 1
        if dv.get("verdict") != "sound":
            b["flagged"] += 1

    # wave review pending — batch drained (nothing confirmed, nothing
    # in-flight) but no holistic read filed yet
    wave_pending = bool(batch.get("id")) and not in_flight \
        and len(confirmed) == 0 and not (batch.get("wave_review")) \
        and bool(stories)

    # checklist
    checklist_path = orch / "alignment-checklist.md"
    checklist = {}
    if checklist_path.is_file():
        checklist = checklist_counts(checklist_path.read_text(encoding="utf-8", errors="replace"))

    # unconsumed FRAGO entries (### headers lacking a consumed marker)
    frago_pending = 0
    inbox = orch / "frago-inbox.md"
    if inbox.is_file():
        text = inbox.read_text(encoding="utf-8", errors="replace")
        frago_pending = len(
            [b for b in text.split("###")[1:]
             if TIMESTAMP_RE.match(b.strip()) and "→ processed" not in b]
        )

    # earned-autonomy state — the counter lives in the ledger (incremented by
    # cdo-review on each Operator decision); we surface it, never recompute it
    autonomy = ledger.get("autonomy") or {}
    streak = autonomy.get("streak", 0) or 0

    # parked cards — deferred inventory; their checklist lines resolved at
    # defer time so nothing surfaces them but this count
    parked_dir = orch / "alignment" / "parked"
    parked = sorted(f.stem for f in parked_dir.glob("*.md")) \
        if parked_dir.is_dir() else []

    digest = {
        "script": "cdo-state-digest",
        "generated_at": now.strftime("%Y-%m-%dT%H:%MZ"),
        "batch": {
            "id": batch.get("id"),
            "manifest_size": len(batch.get("manifest") or []),
        },
        "pool": {
            "confirmed": len(confirmed),
            "quarantined": len(quarantined),
            "below_buffer": len(confirmed) < args.alignment_buffer_min,
        },
        "in_flight": in_flight,
        "stalled_stories": stalled,
        "dispatch_locks": locked,
        "worker_sessions": live_sessions,
        "delivered_pending": delivered_pending,
        "wave_pending": wave_pending,
        "parked_cards": {"count": len(parked), "keys": parked},
        "intent_stale": intent_stale,
        "review_flag_rate_by_conf": conf_band,
        "signals_open": len(signals),
        "operator_items_pending": checklist,
        "operator_items_total": sum(checklist.values()),
        "frago_pending": frago_pending,
        "autonomy": {
            "enabled": autonomy.get("enabled", False),
            "streak": streak,
            "threshold": autonomy.get("threshold", 10),
            "self_approve_active": bool(
                autonomy.get("enabled") and streak >= autonomy.get("threshold", 10)
            ),
        },
        "integrity_anomalies": anomalies,
        "status": "ok" if not anomalies else "anomalies",
    }

    out = json.dumps(digest, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    sys.exit(0 if not anomalies else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
