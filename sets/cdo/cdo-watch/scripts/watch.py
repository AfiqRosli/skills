#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""cdo-watch — the night-shift watchdog and janitor, in one passable script.

Modes:

  scan     → stall detection (elapsed vs threshold), state-integrity checks,
             cost-ceiling check; appends open signals to the ledger, emits JSON
  intake   → consume {orch}/signals/*.md files dropped by frontline agents
             (LINE_STOP etc.) into ledger signals; bodies archive to
             signals/archive/ — nothing is destroyed
  resolve  → mark open signals for --key resolved (triaged by the duty officer)
  janitor  → between-batch hygiene: prune resolved checklist lines, break stale
             dispatch locks, drop resolved signals older than --janitor-days

Read-mostly: scan/intake mutate only the `signals` list; janitor performs the
cleanup writes and reports each action.

Usage:
  uv run watch.py --orchestration-dir /path/docs/orchestration
      [--mode scan|intake|janitor] [--stall-timeout-minutes 45]
      [--batch-budget N] [-o report.json]

Exit codes: 0=clean/actions taken, 1=signals or anomalies found, 2=error
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

from cardlayout import CHECKBOX_KEY_RE  # noqa: E402 — vendored line format

TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})")
REQUIRED_LEDGER_KEYS = ("pool", "stories")
REQUIRED_CHECKLIST_SECTIONS = ("## Needs Attention", "## Routine Review")
# a park this old is a "not now" quietly becoming "never"
PARKED_AGE_WARN_DAYS = 14
# staging is for in-flight writes — a doc this old never filed
STAGED_REVIEW_WARN_DAYS = 2


def parse_args():
    p = argparse.ArgumentParser(description="cdo watchdog/janitor pass.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--mode", default="scan", choices=["scan", "intake", "resolve", "janitor"])
    p.add_argument("--key", help="item key — required by resolve mode")
    p.add_argument("--stall-timeout-minutes", type=int, default=45)
    p.add_argument("--batch-budget", type=float, default=None)
    p.add_argument("--env-file", help=".env path — scan for leftover TEMP-CDO placeholders")
    p.add_argument("--janitor-days", type=int, default=3,
                   help="resolved checklist lines older than this many days get pruned")
    p.add_argument("-H", "--headless", action="store_true",
                   help="accepted for caller parity — output is machine JSON either way")
    p.add_argument("-o", "--output")
    return p.parse_args()


def utcnow():
    return datetime.now(timezone.utc)


def iso_now():
    return utcnow().strftime("%Y-%m-%dT%H:%M")


def parse_ts(text):
    m = TS_RE.search(text or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# drain/group lock (g-*.lock) expiry horizon — a cloud session can't
# heartbeat or clean its local-only marker, so it ages out on the clock
GROUP_LOCK_TTL_MIN = 24 * 60


def load_ledger(orch):
    p = orch / "flow-ledger.yaml"
    if not p.is_file():
        return p, None
    try:
        return p, yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return p, None


def save_ledger(lpath, ledger):
    """Atomic write (tmp + os.replace) — workers write this ledger
    concurrently now; a crash mid-write must not leave a torn file."""
    tmp = lpath.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
    os.replace(tmp, lpath)


def add_signal(ledger, sig_type, detail, key=None):
    """Dedupe on (type, key) among OPEN signals only — a resolved signal must
    never suppress a fresh occurrence."""
    sig = {"type": sig_type, "detail": detail, "at": iso_now(), "status": "open"}
    if key:
        sig["key"] = key
    existing = ledger.setdefault("signals", [])
    for s in existing:
        if s.get("type") == sig_type and s.get("key") == key \
                and s.get("status", "open") == "open":
            return False
    existing.append(sig)
    return True


def scan(orch, args):
    signals, anomalies = [], []
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        return {"mode": "scan", "signals": [], "anomalies": ["flow-ledger.yaml missing/unparseable"],
                "status": "degraded"}
    changed = False

    # integrity — the org checks its own records
    for k in REQUIRED_LEDGER_KEYS:
        if k not in ledger:
            anomalies.append(f"flow-ledger missing '{k}'")
    checklist = orch / "alignment-checklist.md"
    if checklist.is_file():
        text = checklist.read_text(encoding="utf-8", errors="replace")
        for sec in REQUIRED_CHECKLIST_SECTIONS:
            if sec not in text:
                anomalies.append(f"checklist missing section '{sec}'")
    else:
        anomalies.append("alignment-checklist.md missing")

    stories = ledger.get("stories") or {}
    now = utcnow()

    # stall detection — pure time math. Locks are per story (locks/{key}.lock)
    # plus the legacy dispatch.lock; each in-flight story holds its own.
    # Group locks (g-*.lock, cloud spawns) hold every comma-listed key and age
    # against a 24h horizon — a cloud session can't heartbeat the marker.

    def held_locks():
        out = {}
        ld = orch / "locks"
        files = list(ld.glob("*.lock")) if ld.is_dir() else []
        legacy = orch / "dispatch.lock"
        if legacy.is_file():
            files.append(legacy)
        for f in files:
            content = f.read_text(encoding="utf-8", errors="replace")
            parts = content.split()
            ts = parse_ts(content)
            if f.parent.name == "locks" and f.stem.startswith("g-"):
                for k in (parts[2].split(",") if len(parts) > 2 else []):
                    if k:
                        out[k] = {"path": f, "ts": ts, "group": True}
                continue
            key = f.stem if f.parent.name == "locks" else \
                (parts[2] if len(parts) > 2 else None)
            if key:
                out[key] = {"path": f, "ts": ts, "group": False}
        return out

    locks = held_locks()
    for key, st in stories.items():
        if isinstance(st, dict) and st.get("status") == "in-flight":
            started = parse_ts(str(st.get("step_started", "")))
            if not started:
                anomalies.append(f"{key} in-flight without parseable step_started")
                continue
            elapsed = (now - started).total_seconds() / 60
            if elapsed > args.stall_timeout_minutes:
                if add_signal(ledger, "stall", f"{elapsed:.0f}m elapsed at step '{st.get('step')}'", key):
                    changed = True
                signals.append({"type": "stall", "key": key, "elapsed_minutes": round(elapsed, 1)})
            if key not in locks:
                anomalies.append(f"{key} in-flight but no locks/{key}.lock — unclaimed work?")

    # stale locks — one signal per wedged story, not one global verdict
    for key, lk in locks.items():
        lt = lk["ts"]
        ttl = GROUP_LOCK_TTL_MIN if lk.get("group") \
            else args.stall_timeout_minutes * 2
        if lt and (now - lt).total_seconds() / 60 > ttl:
            detail = f"lock for {key} held past its ttl"
            signals.append({"type": "stale-lock", "key": key, "detail": detail})
            if add_signal(ledger, "stale-lock", detail, key=key):
                changed = True

    # delivered-but-unbriefed catch-net — the worker normally spawns a
    # fresh-eyes review session on ship (delivery-note spawn-review); a
    # shipped story with no review stamp AND no fresh review record means
    # that spawn died — flag for respawn, don't flag while one is in-flight
    reviewing = set()
    sdir = orch / "sessions"
    if sdir.is_dir():
        for f in sdir.glob("*.review.json"):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                rt = parse_ts(str(rec.get("started", "")))
                if rt and (now - rt).total_seconds() / 60 <= args.stall_timeout_minutes:
                    reviewing.add(rec.get("key") or "")
            except json.JSONDecodeError:
                pass
    for key, st in stories.items():
        if not isinstance(st, dict):
            continue
        if st.get("status") not in ("shipped", "blocked", "killed", "deferred"):
            continue
        if (st.get("delivery_review") or {}).get("attempt") \
                == (st.get("attempts") or 1):
            continue
        if key in reviewing:
            continue
        anomalies.append(
            f"{key} at '{st['status']}' (attempt {st.get('attempts', 1)}) "
            f"unbriefed and no live review session — "
            f"respawn: delivery-note.py spawn-review {key}")

    # 13-28 — usage accounting: roll terminal .acp.json usage into
    # batch.burn so the ledger measures burn, then flag a live drain
    # approaching the budget (report-only — watch signals, never kills).
    batch_burn = {"sessions": {}, "tokens_in": 0, "tokens_out": 0}
    for f in sdir.glob("*.acp.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
            u = rec.get("usage") or {}
            ti, to = int(u.get("inputTokens") or u.get("input_tokens") or 0),                 int(u.get("outputTokens") or u.get("output_tokens") or 0)
            if ti or to:
                batch_burn["sessions"][f.stem] = {
                    "tokens_in": ti, "tokens_out": to,
                    "stop": rec.get("stop_reason")}
                batch_burn["tokens_in"] += ti
                batch_burn["tokens_out"] += to
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    if batch_burn["sessions"]:
        ledger.setdefault("batch", {})["burn"] = batch_burn
        changed = True

    # cost ceiling
    cost = ledger.get("cost") or {}
    budget = args.batch_budget if args.batch_budget is not None else cost.get("budget")
    cfg_frac = 0.8
    try:
        _cfg = yaml.safe_load(
            (orch.parent.parent / "_bmad" / "config.yaml").read_text(
                encoding="utf-8")) or {}
        _cdo = _cfg.get("cdo") or {}
        cfg_frac = float(_cdo.get("burn_warn_fraction") or 0.8)
        if not budget:
            budget = float(_cdo.get("batch_budget") or 0)
    except (OSError, ValueError):
        pass
    locks_dir = orch / "locks"
    live_drain = any(l.stem.startswith("g-") for l in locks_dir.glob("*.lock")) \
        if locks_dir.is_dir() else False
    total_tokens = batch_burn["tokens_in"] + batch_burn["tokens_out"]
    if live_drain and budget and total_tokens >= budget * cfg_frac:
        signals.append({"type": "burn-approaching",
                        "detail": f"drain burn {total_tokens} tokens >= "
                                  f"{cfg_frac:.0%} of budget {budget}"})
        add_signal(ledger, "burn-approaching",
                   f"drain burn {total_tokens} tokens >= {cfg_frac:.0%} "
                   f"of budget {budget}", key="burn")
        changed = True

    if budget and (cost.get("burned") or 0) >= budget:
        signals.append({"type": "cost-ceiling", "detail": f"burned {cost['burned']} >= budget {budget}"})
        # keyed so `resolve --key cost` can close it — a keyless signal can
        # never resolve and would suppress every future budget breach forever
        add_signal(ledger, "cost-ceiling",
                   f"burned {cost['burned']} >= budget {budget}", key="cost")
        changed = True

    # draft/checklist desync — a draft file without a checklist line is invisible work
    drafts = orch / "alignment" / "drafts"
    if drafts.is_dir() and checklist.is_file():
        text_nc = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        keys_on_checklist = set(
            m.group("key") for m in CHECKBOX_KEY_RE.finditer(text_nc))
        for f in drafts.glob("*.md"):
            if f.stem not in keys_on_checklist:
                anomalies.append(f"draft {f.stem} not on checklist")

    # parked desync + aging — a parked card's line resolved at defer, so a
    # live pending line for it is contradictory; and an aging park is a
    # "not now" quietly becoming "never" (resurface or unpark it)
    parked = orch / "alignment" / "parked"
    if parked.is_dir() and checklist.is_file():
        text_nc = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        pending_keys = set(m.group("key")
                           for m in CHECKBOX_KEY_RE.finditer(text_nc)
                           if m.group("mark") == " ")
        for f in parked.glob("*.md"):
            if f.stem in pending_keys:
                anomalies.append(
                    f"parked {f.stem} still has a pending checklist line")
            m = re.search(r"<!-- deferred (\d{4}-\d{2}-\d{2})",
                          f.read_text(encoding="utf-8", errors="replace"))
            if m:
                age = (utcnow().date()
                       - datetime.strptime(m.group(1),
                                           "%Y-%m-%d").date()).days
                if age >= PARKED_AGE_WARN_DAYS:
                    anomalies.append(f"parked {f.stem} aging {age}d — "
                                     "resurface or unpark")

    # staged reviews — reviews/ holds ONLY Operator-pending audit docs: the
    # r-* session files the line, the Operator's verdict graduates the doc
    # beside the card (apply-decisions owns the move). Three states:
    #   pending `| review:` line  → awaiting Operator verdict — quiet, but
    #                               ages like a park when ignored
    #   resolved `| review:` line → apply-decisions missed the move (anomaly)
    #   no line at all + aging    → reviewer died mid-write — file or reap
    reviews_dir = orch / "alignment" / "reviews"
    if reviews_dir.is_dir() and checklist.is_file():
        text_nc = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        for f in reviews_dir.glob("*.md"):
            rel = f.relative_to(orch).as_posix()
            if re.search(rf"^- \[[xA\-]] .*review: {re.escape(rel)}\b",
                         text_nc, re.M):
                anomalies.append(
                    f"review {f.name} resolved but still staged — "
                    "verdict applied, graduation missed")
                continue
            age = (utcnow() - datetime.fromtimestamp(
                f.stat().st_mtime, tz=timezone.utc)).days
            if re.search(rf"^- \[ ] .*review: {re.escape(rel)}\b",
                         text_nc, re.M):
                if age >= PARKED_AGE_WARN_DAYS:
                    anomalies.append(
                        f"review {f.name} awaiting Operator verdict {age}d")
                continue
            if age >= STAGED_REVIEW_WARN_DAYS:
                anomalies.append(
                    f"staged review {f.name} aging {age}d with no checklist "
                    "line — file or reap")

    # alignment/ root strays — a review doc dropped outside every bay and
    # dated dir matches nothing (not a bay, not a card) and never graduates:
    # stranded. Glob covers the root level only, never bay/dated contents.
    align_root = orch / "alignment"
    if align_root.is_dir():
        for f in align_root.glob("*.md"):
            if re.search(r"\.review-\d+\.md$|^wave-", f.name):
                anomalies.append(
                    f"stranded review doc at alignment/{f.name} — belongs "
                    "in reviews/ (pending) or beside the card (verdicted)")

    # TEMP env placeholders — injected to unblock dispatch; if still present they
    # mean a requisition is outstanding (a story will hit a fake credential)
    env_file = Path(args.env_file) if getattr(args, "env_file", None) else None
    if env_file and env_file.is_file():
        temp_keys = [l.split("=", 1)[0].strip() for l in
                     env_file.read_text(encoding="utf-8", errors="replace").splitlines()
                     if "# TEMP-CDO" in l]
        if temp_keys:
            anomalies.append(f"TEMP-CDO placeholders still in .env: {temp_keys}")

    if changed:
        save_ledger(lpath, ledger)

    return {"mode": "scan", "signals": signals, "anomalies": anomalies,
            "status": "clean" if not signals and not anomalies else "attention"}


def intake(orch, args):
    """Consume frontline-dropped signal files into the ledger.

    Filename convention: `{kind}-{key}.md` (e.g. line-stop-13-08-x.md, drift-P2.md).
    The key is parsed from the stem — dedupe is per-key, so the second LINE_STOP
    in the project's life is not eaten by the first one's shadow. Bodies archive
    to signals/archive/ before the inbox copy is removed — evidence survives."""
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        return {"mode": "intake", "status": "error",
                "errors": ["flow-ledger.yaml missing/unparseable"]}
    inbox = orch / "signals"
    archive = inbox / "archive"
    consumed, dropped = [], []
    if inbox.is_dir():
        # the inbox's own docs are not signals — README/INBOX files document
        # the drop convention; consuming them deletes the docs
        for f in sorted(inbox.glob("*.md")):
            if f.stem.upper() in ("README", "INBOX"):
                continue
            body = f.read_text(encoding="utf-8", errors="replace")
            first = next((l.strip() for l in body.splitlines() if l.strip()), f.stem)
            sig_type = "line-stop" if "LINE_STOP" in body.upper() else "frontline"
            # {kind}-{key}.md → key for per-item dedupe. Strip the kind
            # PREFIX — keys are hyphenated (NN-MM-slug), so splitting from
            # the back would take the slug tail, collide dedupe, and make
            # `resolve --key` unclosable. Unknown format → no key rather
            # than a wrong one.
            km = re.match(
                r"^(line-stop|stall|drift|frontline|escalation|stale-lock|"
                r"signal)-(.+)$", f.stem)
            key = km.group(2).strip() if km else None
            if add_signal(ledger, sig_type, f"{f.stem}: {first[:160]}", key=key):
                archive.mkdir(exist_ok=True)
                (archive / f.name).write_text(body, encoding="utf-8")
                consumed.append(f.name)
                f.unlink()
            else:
                # dedupe-dropped — archive it too (a `.dup` suffix so it
                # reads as swallowed-by-dedupe, not processed) or the file
                # wedges in the inbox re-deduped forever
                archive.mkdir(exist_ok=True)
                (archive / f"{f.stem}.dup{f.suffix}").write_text(
                    body, encoding="utf-8")
                f.unlink()
                dropped.append(f.name)
    if consumed:
        save_ledger(lpath, ledger)
    return {"mode": "intake", "consumed": consumed, "skipped_dupes": dropped}


def resolve(orch, args):
    """Mark open signals for --key resolved — the triage side of the lifecycle."""
    if not args.key:
        return {"mode": "resolve", "status": "error", "errors": ["--key required"]}
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        return {"mode": "resolve", "status": "error",
                "errors": ["flow-ledger.yaml missing/unparseable"]}
    resolved = []
    for s in ledger.get("signals") or []:
        if isinstance(s, dict) and s.get("key") == args.key \
                and s.get("status", "open") == "open":
            s["status"] = "resolved"
            s["resolved_at"] = iso_now()
            resolved.append(s.get("type"))
    if resolved:
        save_ledger(lpath, ledger)
    return {"mode": "resolve", "key": args.key, "resolved": resolved}


def janitor(orch, args):
    actions = []
    # prune resolved checklist lines older than --janitor-days
    # (resolved lines carry "→ verdict YYYY-MM-DD"; undated ones are kept)
    checklist = orch / "alignment-checklist.md"
    if checklist.is_file():
        cutoff = utcnow() - timedelta(days=args.janitor_days)
        verdict_date = re.compile(r"→ \S+ (\d{4}-\d{2}-\d{2})")
        kept, pruned = [], 0
        for l in checklist.read_text(encoding="utf-8").splitlines():
            if l.lstrip().startswith("- [x]"):
                m = verdict_date.search(l)
                try:
                    old = m and datetime.strptime(m.group(1), "%Y-%m-%d").replace(
                        tzinfo=timezone.utc) < cutoff
                except ValueError:
                    old = False
                if old:
                    pruned += 1
                    continue
            kept.append(l)
        if pruned:
            checklist.write_text("\n".join(kept) + "\n", encoding="utf-8")
            actions.append(f"pruned {pruned} resolved checklist line(s)")

    # break stale locks — per-story files plus the legacy dispatch.lock;
    # drain locks (g-*.lock, spawn markers) get a 24h horizon OR terminal
    # evidence: a drain's last act pushes/writes sessions/drain.md, and a
    # cloud drain physically cannot remove its local-only marker — expire
    # on the report, not the clock, or every cloud exit zombies a day
    drain_report = orch / "sessions" / "drain.md"
    drain_done_ts = None
    if drain_report.is_file():
        drain_done_ts = datetime.fromtimestamp(
            drain_report.stat().st_mtime, tz=timezone.utc)
    lock_files = []
    locks_dir = orch / "locks"
    if locks_dir.is_dir():
        lock_files += sorted(locks_dir.glob("*.lock"))
    legacy = orch / "dispatch.lock"
    if legacy.is_file():
        lock_files.append(legacy)
    if not lock_files:
        actions.append("no dispatch locks — nothing to break")
    ledger_stories = None  # lazily loaded once — not per lock file
    for lock in lock_files:
        content = lock.read_text(encoding="utf-8", errors="replace")
        lt = parse_ts(content)
        age = (utcnow() - lt).total_seconds() / 60 if lt else float("inf")
        name = lock.name if lock.parent.name == "locks" else "dispatch.lock (legacy)"
        is_drain = lock.stem.startswith("g-")
        ttl = GROUP_LOCK_TTL_MIN if is_drain \
            else args.stall_timeout_minutes * 2
        # a drain whose queued keys are ALL terminal finished its work —
        # whatever killed it before the report doesn't keep the guard
        all_terminal = False
        if is_drain and lt:
            try:
                members = content.split()[2].split(",")
                if ledger_stories is None:
                    _, lgr = load_ledger(orch)
                    ledger_stories = (lgr or {}).get("stories") or {}
                stories = ledger_stories
                TERMINAL = {"done", "verified", "shipped",
                            "blocked", "killed", "deferred", "quarantined"}
                all_terminal = bool(members) and all(
                    (stories.get(m) or {}).get("status") in TERMINAL
                    for m in members)
            except (IndexError, OSError):
                pass
        if (is_drain and drain_done_ts and lt and lt < drain_done_ts) \
                or all_terminal or age > ttl:
            why = ("drain terminal report landed" if is_drain and lt
                   and drain_done_ts and lt < drain_done_ts
                   else "all member keys terminal" if all_terminal
                   else "stale")
            lock.unlink()
            actions.append(f"broke {name} ({why}, {age:.0f}m old)")
        else:
            actions.append(f"{name} fresh — left alone")

    # 13-29 — orphan worktrees: dead (lockless) .cdo-work worktrees older
    # than the TTL get removed so .git/worktrees stays clean. Delegated
    # to cdo-platform's sweep-worktrees.py — the shared implementation
    # (cdo-review's verdict sweep uses it without the TTL).
    sweep = orch.parent.parent / ".agents" / "skills" / "cdo-platform" / \
        "scripts" / "sweep-worktrees.py"
    if sweep.is_file():
        r = subprocess.run(
            [sys.executable, str(sweep), "--project-root",
             str(orch.parent.parent), "--orchestration-dir", str(orch),
             "--older-than", str(GROUP_LOCK_TTL_MIN)],
            capture_output=True, text=True)
        try:
            res = json.loads(r.stdout or "{}")
            actions += [f"removed orphan worktree {n}"
                        for n in res.get("removed", [])]
            actions += [f"orphan worktree {e}" for e in res.get("errors", [])]
        except json.JSONDecodeError:
            actions.append(f"worktree sweep failed: "
                           f"{(r.stderr or r.stdout)[:120]}")

    # docs visibility sweep — cdo-docs audit.py reports pages the site can't
    # reach and nav entries pointing at nothing. Watch notices, doesn't fix:
    # non-empty findings land as an action + one signal for triage (deduped
    # on key while open — a recurring orphan doesn't re-fire until resolved).
    audit = orch.parent.parent / ".agents" / "skills" / "cdo-docs" / \
        "scripts" / "audit.py"
    if audit.is_file():
        r = subprocess.run(
            [sys.executable, str(audit), "--orchestration-dir", str(orch),
             "--project-root", str(orch.parent.parent)],
            capture_output=True, text=True)
        try:
            res = json.loads(r.stdout or "{}")
            orphans = res.get("orphans") or []
            broken = res.get("broken_nav") or []
            if orphans or broken:
                detail = (f"docs visibility: {len(orphans)} orphan page(s), "
                          f"{len(broken)} broken nav entrie(s) — run "
                          f"cdo-docs audit to register/fix")
                actions.append(detail)
                lp, led = load_ledger(orch)
                if led is not None and \
                        add_signal(led, "docs-orphans", detail,
                                   key="docs-visibility"):
                    save_ledger(lp, led)
        except json.JSONDecodeError:
            actions.append(f"docs audit unreadable: "
                           f"{(r.stderr or r.stdout)[:120]}")

    # drop resolved signals older than --janitor-days
    lpath, ledger = load_ledger(orch)
    if ledger is not None:
        cutoff = utcnow() - timedelta(days=args.janitor_days)
        kept, pruned_sigs = [], []
        for s in ledger.get("signals") or []:
            if isinstance(s, dict) and s.get("status") == "resolved":
                ts = parse_ts(str(s.get("resolved_at") or s.get("at") or ""))
                if ts is None or ts < cutoff:
                    pruned_sigs.append(s)
                    continue
            kept.append(s)
        if pruned_sigs:
            ledger["signals"] = kept
            save_ledger(lpath, ledger)
            actions.append(f"pruned {len(pruned_sigs)} resolved signal(s)")

    return {"mode": "janitor", "actions": actions}


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    if not orch.is_dir():
        print(json.dumps({"errors": [f"orchestration dir not found: {orch}"]}))
        sys.exit(2)

    fn = {"scan": scan, "intake": intake, "resolve": resolve, "janitor": janitor}[args.mode]
    result = fn(orch, args)
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    dirty = bool(result.get("signals") or result.get("anomalies") or result.get("errors"))
    sys.exit(1 if dirty else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
