#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Dispatch state machine for cdo-batch — ledger, locks, and backlog surgery.

Actions:

  check {key}      → readiness verdict: confirmed? in pool? externals present?
                     Emits {ready, reasons[], missing_env[], locks[]}. Confirmed
                     cards live under alignment/YYYY/MM/DD/ — drafts/ is NOT a card.
  claim {key}      → write locks/{key}.lock + mark story in-flight (step_started)
                     + remove from pool.confirmed. Refuses if that key's lock is
                     held & fresh, or if this --session already holds another key.
  heartbeat {key}  → refresh step_started + this story's lock timestamp for a
                     live dispatch; checkpoint mid-pipeline so long steps don't
                     read as stalls. Must come from the lock-holding session.
  outcome {key}    → record status/step/findings; blocked|killed|deferred also
                     quarantines and flips the backlog marker.
                     --burn N adds to cost.burned.
  quarantine {key} → move key to pool.quarantined with reason, backlog → [-].
  reconfirm {key}  → reverse a quarantine: quarantined → confirmed pool,
                     backlog [-] → [x]. For repaired items re-entering dispatch.
  requisition {key}→ append a Requisitions checklist entry for the item.
  release {key}    → delete locks/{key}.lock; requires --session matching the
                     holder (or --force for stale-lock breaks). No key releases
                     the legacy dispatch.lock if one exists.

Locks are PER STORY — `locks/{key}.lock`, one line `{session} {ts} {key}`.
Dispatch is linear: one drain session works the queue key by key; it holds
only the lock of the story it currently runs. One story per session is still
enforced between claim boundaries: a session holding a fresh lock may not
claim a second key. A legacy top-level `dispatch.lock` is honored as the
lock for its embedded key.

Usage:
  uv run dispatch.py --orchestration-dir /path/docs/orchestration
      ACTION [key] [--step dev] [--session s-3] [--reason "..."]
      [--status done|verified|shipped|blocked|killed|deferred]
      [--findings "..."] [--lane-sha SHA] [--burn N]
      [--stall-timeout-minutes 45] [--env-file /path/.env] [-o result.json]

Exit codes: 0=ok, 1=action refused/failed validation, 2=runtime error
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

from cardlayout import confirmed_card as _confirmed_card  # noqa: E402

TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})")
ENV_IN_CARD_RE = re.compile(r"^- `?([A-Z][A-Z0-9_]+)`?\b", re.M)
BACKLOG_MARKER_RE = r"^- \[[xA\- ]\] "
OUTCOME_STATUSES = {"done", "verified", "shipped", "blocked", "killed", "deferred"}
SHIPPED_STATUSES = {"done", "verified", "shipped"}
ESCAPE_STATUSES = {"blocked", "killed", "deferred"}
# 13-26 — machine-gated transitions: the ledger no longer accepts a status
# the legs never produced. done←in-flight, verified←done, shipped←verified;
# escape hatches only from in-flight. --force overrides (journaled).
TRANSITIONS = {"done": "in-flight", "verified": "done", "shipped": "verified"}


def parse_args():
    p = argparse.ArgumentParser(description="cdo dispatch state machine.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("action",
                   choices=["check", "claim", "heartbeat", "outcome",
                            "quarantine", "reconfirm", "requisition", "release"])
    p.add_argument("key", nargs="?", help="story/item key")
    p.add_argument("--step", default="", help="pipeline step name")
    p.add_argument("--session", default="", help="session/agent identifier")
    p.add_argument("--reason", default="")
    p.add_argument("--status", default="", help="outcome status")
    p.add_argument("--findings", default="")
    p.add_argument("--lane-sha", default="",
                   help="the story's landed lane commit (cdo-lane ref tip) — "
                        "the pre-deploy sign-off pushes by this sha")
    p.add_argument("--burn", type=float, default=0,
                   help="cost units consumed by this outcome → cost.burned")
    p.add_argument("--stall-timeout-minutes", type=int, default=45)
    p.add_argument("--env-file", help=".env path for externals check")
    p.add_argument("--project-root", default="",
                   help="project root — default: orchestration-dir's "
                        "grandparent (the standard install layout)")
    p.add_argument("--force", action="store_true", help="break another session's lock")
    p.add_argument("-o", "--output")
    return p.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def load_ledger(orch: Path) -> tuple:
    p = orch / "flow-ledger.yaml"
    if not p.is_file():
        return p, {}
    try:
        return p, yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return p, {}


def atomic_write(path: Path, text: str):
    """Temp-file + os.replace — a crash mid-write never leaves a torn ledger.
    Does not make read-modify-write transactional; concurrent writers still
    race (last-writer-wins) — a ledger mutex is the follow-up if needed."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def save_ledger(path: Path, ledger: dict):
    atomic_write(path, yaml.safe_dump(ledger, sort_keys=False))


# A drain lock (`locks/g-{...}.lock`, written by spawn-dispatch) holds every
# key in its comma-list for the drain session until it exits. It's a spawn
# marker, not a worker claim — a cloud session can't heartbeat, so it ages
# against a 24h horizon, not the story stall window.
GROUP_LOCK_TTL_MINUTES = 24 * 60


def iter_locks(orch: Path):
    """Yield {path, key, session, ts} for every held dispatch lock.

    Locks live at `locks/{key}.lock` (content `{session} {ts} {key}`). A legacy
    top-level `dispatch.lock` counts as the lock for its embedded key. Drain
    locks (`g-{...}.lock`) yield one entry per comma-listed key, flagged
    `group`."""
    ld = orch / "locks"
    if ld.is_dir():
        for f in sorted(ld.glob("*.lock")):
            parts = f.read_text(encoding="utf-8", errors="replace").split()
            if f.stem.startswith("g-"):
                group_keys = parts[2].split(",") if len(parts) > 2 else []
                for k in group_keys:
                    yield {
                        "path": f, "key": k,
                        "session": parts[0] if parts else None,
                        "ts": parts[1] if len(parts) > 1 else None,
                        "legacy": False, "group": True,
                    }
                continue
            yield {
                "path": f, "key": f.stem,
                "session": parts[0] if parts else None,
                "ts": parts[1] if len(parts) > 1 else None,
                "legacy": False, "group": False,
            }
    legacy = orch / "dispatch.lock"
    if legacy.is_file():
        parts = legacy.read_text(encoding="utf-8", errors="replace").split()
        yield {
            "path": legacy,
            "key": parts[2] if len(parts) > 2 else None,
            "session": parts[0] if parts else None,
            "ts": parts[1] if len(parts) > 1 else None,
            "legacy": True,
        }


def lock_age_minutes(ts: str):
    if not ts:
        return None
    try:
        t = datetime.strptime(ts, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 60
    except ValueError:
        return None


def all_locks(orch: Path, stall_minutes: int) -> list:
    """Every held lock with staleness — the full dispatch picture."""
    out = []
    for lk in iter_locks(orch):
        age = lock_age_minutes(lk["ts"])
        ttl = GROUP_LOCK_TTL_MINUTES if lk.get("group") else stall_minutes * 2
        out.append({
            "key": lk["key"], "session": lk["session"],
            "age_minutes": age,
            "stale": age is not None and age > ttl,
            "legacy": lk["legacy"], "group": lk.get("group", False),
        })
    return out


def lock_info(orch: Path, key: str, stall_minutes: int) -> dict:
    """Lock state for ONE key — only same-key fresh locks block a claim."""
    for lk in all_locks(orch, stall_minutes):
        if lk["key"] == key:
            return {"held": True, **lk}
    return {"held": False}


def write_lock(orch: Path, key: str, session: str) -> bool:
    """Atomic claim — O_CREAT|O_EXCL so a lost race REFUSES instead of
    silently overwriting a competitor's lock. Returns False when the file
    already exists."""
    ld = orch / "locks"
    ld.mkdir(exist_ok=True)
    body = f"{session or 'unknown-session'} {now_iso()} {key}"
    try:
        fd = os.open(str(ld / f"{key}.lock"),
                     os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    return True


def lock_path_for(orch: Path, key: str):
    """The file to refresh on heartbeat — the per-key lock wins; a drain
    (g-*) lock is only a fallback so a heartbeat never rewrites the
    drain's comma-list down to one key."""
    group_path = None
    for lk in iter_locks(orch):
        if lk["key"] == key:
            if lk.get("group"):
                group_path = group_path or lk["path"]
                continue
            return lk["path"]
    return group_path


def confirmed_card(orch: Path, key: str):
    """A confirmed card lives under alignment/YYYY/MM/DD/ — never drafts/
    or parked/ (unconfirmed cards authorize nothing). Rejected cards are
    archived too (audit trail) but carry `<!-- reject` on line 1 and do
    NOT authorize dispatch; cards without a verdict comment (hand-archived,
    or legacy archives) count as confirmed. Newest archive wins.
    Implementation: cardlayout.confirmed_card (vendored single source)."""
    return _confirmed_card(orch, key)


def read_card_externals(orch: Path, key: str) -> list:
    f = confirmed_card(orch, key)
    if not f:
        return []
    section = f.read_text(encoding="utf-8", errors="replace")
    env_block = section.split("## Externals Needed")[-1].split("## ")[0] \
        if "## Externals Needed" in section else ""
    return ENV_IN_CARD_RE.findall(env_block)


def env_keys_present(env_file: Path) -> set:
    if not env_file or not env_file.is_file():
        return set()
    keys = set()
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^\s*([A-Z][A-Z0-9_]+)\s*=", line)
        if m:
            keys.add(m.group(1))
    return keys


def dept_produce_entry(orch: Path, key: str):
    """Resolve which dept owns the key's backlog and whether it declares
    a `produce` capability. Returns (dept, entry) or (None, None)."""
    caps_path = orch / "capabilities.yaml"
    if not caps_path.is_file():
        return None, None
    try:
        caps = yaml.safe_load(caps_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None, None
    # which backlog file holds this key?
    owner_file = None
    bd = orch / "backlogs"
    if bd.is_dir():
        pat = re.compile(rf"^- \[[xA\- ]\] {re.escape(key)}\b", re.M)
        for bf in bd.glob("*.md"):
            if pat.search(bf.read_text(encoding="utf-8", errors="replace")):
                owner_file = f"backlogs/{bf.name}"
                break
    if not owner_file:
        return None, None
    for dept, info in (caps.get("departments") or {}).items():
        if not isinstance(info, dict):
            continue
        if f"backlogs/{info.get('backlog')}.md" != owner_file:
            continue
        produce = (info.get("capabilities") or {}).get("produce")
        if produce and produce.get("entry"):
            return dept, produce["entry"]
        return dept, None  # dept owns the backlog but has no produce
    return None, None


def flip_backlog(orch: Path, key: str, new_mark: str, note: str = "") -> bool:
    """Flip the marker on key's backlog line, preserving the rest of the line
    (title/size/deps metadata lives after the key — don't destroy it)."""
    for bf in (orch / "backlogs").glob("*.md"):
        text = bf.read_text(encoding="utf-8")
        pat = re.compile(rf"^(- )\[([xA\- ])\]( {re.escape(key)}\b)(.*)$", re.M)
        m = pat.search(text)
        if not m:
            continue
        suffix = m.group(4)
        if note:
            suffix = (suffix + f" — {note}") if suffix else f" — {note}"
        text = text[:m.start()] + f"{m.group(1)}[{new_mark}]{m.group(3)}{suffix}" + text[m.end():]
        bf.write_text(text, encoding="utf-8")
        return True
    return False


def emit(result: dict, code: int, out: str):
    blob = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    if not orch.is_dir():
        emit({"errors": [f"orchestration dir not found: {orch}"]}, 2, args.output)
    if args.action not in ("release",) and not args.key:
        emit({"errors": ["key required for this action"]}, 1, args.output)
    if args.action == "outcome" and args.status and args.status not in OUTCOME_STATUSES:
        emit({"errors": [f"invalid --status {args.status!r}; want one of {sorted(OUTCOME_STATUSES)}"]},
             1, args.output)

    lpath, ledger = load_ledger(orch)
    ledger.setdefault("pool", {}).setdefault("confirmed", [])
    ledger["pool"].setdefault("quarantined", [])
    ledger.setdefault("stories", {})
    key = args.key

    if args.action == "check":
        reasons = []
        if key not in ledger["pool"]["confirmed"]:
            reasons.append("not in pool.confirmed (unconfirmed or already dispatched)")
        if not confirmed_card(orch, key):
            reasons.append("no confirmed alignment card under alignment/YYYY/MM/DD/")
        if ledger["stories"].get(key, {}).get("status") == "in-flight":
            reasons.append("already in-flight")
        lock = lock_info(orch, key, args.stall_timeout_minutes)
        if (lock["held"] and not lock["stale"]
                and not (lock.get("group")
                         and lock.get("session") == args.session)):
            # a drain lock held by the CALLER's own session is its queue
            # marker, not a competing claim — a drain runs `check` over its
            # own queued keys and must not refuse them (mirrors `claim`)
            age = f"{lock['age_minutes']:.0f}m old" \
                if lock.get("age_minutes") is not None else "unparseable ts"
            reasons.append(f"lock for {key} held by {lock.get('session')} "
                           f"({age})")
        externals = read_card_externals(orch, key)
        env_path = Path(args.env_file) if args.env_file else \
            (Path(args.project_root).resolve()
             if args.project_root else orch.parent.parent) / ".env"
        have = env_keys_present(env_path)
        missing = [e for e in externals if e not in have]
        dept, produce_entry = dept_produce_entry(orch, key)
        if dept and not produce_entry:
            reasons.append(f"dept {dept} owns this backlog but declares no "
                           "`produce` capability — dispatch would dead-end")
        manifest = (ledger.get("batch") or {}).get("manifest") or []
        emit({
            "key": key, "ready": not reasons and not missing, "reasons": reasons,
            "externals_required": externals, "missing_env": missing,
            "lock": lock, "locks": all_locks(orch, args.stall_timeout_minutes),
            "dept": dept, "produce_entry": produce_entry,
            "manifest_position": manifest.index(key) if key in manifest else None,
        }, 0 if not reasons and not missing else 1, args.output)

    if args.action == "claim":
        lock = lock_info(orch, key, args.stall_timeout_minutes)
        if lock["held"] and not lock["stale"] and not (
                lock.get("group") and lock.get("session") == args.session):
            emit({"errors": [f"lock for {key} held by {lock.get('session')} — "
                             "another session may be running it"]}, 1, args.output)
        # one story at a time per session — a session holding any fresh
        # story lock may not claim a second key (drain spawn-locks are
        # markers, not claims — the drain session claims members serially)
        if args.session:
            for lk in all_locks(orch, args.stall_timeout_minutes):
                if lk.get("group"):
                    continue
                if lk["session"] == args.session and lk["key"] != key \
                        and not lk["stale"]:
                    emit({"errors": [f"session {args.session} already holds "
                                     f"{lk['key']} — one story per session"]},
                         1, args.output)
        if key not in ledger["pool"]["confirmed"]:
            emit({"errors": [f"{key} not in pool.confirmed — Dispatch Pool Boundary"]},
                 1, args.output)
        if not write_lock(orch, key, args.session):
            # the file exists despite the earlier check — either a lost race
            # or a stale lock the janitor hasn't swept; stale → break + retry
            stale = (orch / "locks" / f"{key}.lock").exists() and not any(
                lk["key"] == key and not lk["stale"] and not lk.get("group")
                for lk in all_locks(orch, args.stall_timeout_minutes))
            retried = False
            if stale:
                (orch / "locks" / f"{key}.lock").unlink()
                retried = write_lock(orch, key, args.session)
            if not retried:
                emit({"errors": [f"locks/{key}.lock appeared between check "
                                 "and write — a competing claim won the "
                                 "race; do NOT record an outcome for work "
                                 "you didn't run"]}, 1, args.output)
        ledger["pool"]["confirmed"] = [k for k in ledger["pool"]["confirmed"] if k != key]
        st = ledger["stories"].setdefault(key, {})
        st.update({
            "status": "in-flight", "step": args.step or "dispatch",
            "step_started": now_iso(), "session": args.session,
            "attempts": st.get("attempts", 0) + 1,
        })
        save_ledger(lpath, ledger)
        emit({"status": "claimed", "key": key, "attempts": st["attempts"]}, 0, args.output)

    if args.action == "heartbeat":
        st = ledger["stories"].get(key)
        if not st or st.get("status") != "in-flight":
            emit({"errors": [f"{key} is not in-flight — nothing to heartbeat"]},
                 1, args.output)
        # ownership: a heartbeat must come from the lock-holding session
        lock = lock_info(orch, key, args.stall_timeout_minutes)
        holder = lock.get("session")
        if args.session and holder and args.session != holder:
            emit({"errors": [f"lock for {key} held by {holder} — heartbeat refused"]},
                 1, args.output)
        st["step_started"] = now_iso()
        if args.step:
            st["step"] = args.step
        # a heartbeat also proves the holding session is alive — refresh
        # whichever file actually holds the key (legacy dispatch.lock stays
        # legacy rather than silently minting a second per-key lock)
        if holder:
            lp = lock_path_for(orch, key)
            if lp is None:
                lp = orch / "locks" / f"{key}.lock"
            lp.write_text(f"{holder} {now_iso()} {key}\n", encoding="utf-8")
        save_ledger(lpath, ledger)
        emit({"status": "heartbeat", "key": key, "step_started": st["step_started"]},
             0, args.output)

    if args.action == "outcome":
        st = ledger["stories"].setdefault(key, {})
        target = args.status or "done"
        current = st.get("status")
        if target in TRANSITIONS and current != TRANSITIONS[target] and not args.force:
            emit({"errors": [
                f"illegal outcome transition {current or 'none'} → {target} on {key} "
                f"(requires {TRANSITIONS[target]!r}; use --force to override, journaled)"],
            }, 1, args.output)
        if target in ESCAPE_STATUSES and current != "in-flight" and not args.force:
            emit({"errors": [
                f"illegal outcome transition {current or 'none'} → {target} on {key} "
                "(escape hatches require 'in-flight'; use --force to override, journaled)"],
            }, 1, args.output)
        st["status"] = target
        if args.force:
            st.setdefault("findings", []).append(
                f"{now_iso()} FORCE-OVERRIDE: {current or 'none'} → {target} — {args.reason or 'no reason given'}")
        st["step"] = args.step or st.get("step")
        if args.lane_sha:
            st["lane_sha"] = args.lane_sha
        if args.findings:
            st.setdefault("findings", []).append(f"{now_iso()} {args.findings}")
        if args.burn:
            cost = ledger.setdefault("cost", {})
            cost["burned"] = round(cost.get("burned", 0) + args.burn, 2)
        if args.status in ("blocked", "killed", "deferred"):
            if not any(q.get("key") == key for q in ledger["pool"]["quarantined"]
                       if isinstance(q, dict)):
                ledger["pool"]["quarantined"].append(
                    {"key": key, "reason": args.reason or args.status}
                )
            flip_backlog(orch, key, "-", args.reason or args.status)
        elif args.status in SHIPPED_STATUSES:
            flip_backlog(orch, key, "x")
        save_ledger(lpath, ledger)
        emit({"status": "recorded", "key": key, "outcome": st["status"]}, 0, args.output)

    if args.action == "quarantine":
        ledger["pool"]["confirmed"] = [k for k in ledger["pool"]["confirmed"] if k != key]
        if not any(q.get("key") == key for q in ledger["pool"]["quarantined"]
                   if isinstance(q, dict)):
            ledger["pool"]["quarantined"].append(
                {"key": key, "reason": args.reason or "quarantined"}
            )
        st = ledger["stories"].setdefault(key, {})
        st["status"] = "quarantined"
        save_ledger(lpath, ledger)
        flip_backlog(orch, key, "-", args.reason or "quarantined")
        emit({"status": "quarantined", "key": key}, 0, args.output)

    if args.action == "reconfirm":
        qlist = ledger["pool"]["quarantined"]
        if not any(q.get("key") == key for q in qlist if isinstance(q, dict)):
            emit({"errors": [f"{key} is not quarantined — nothing to reconfirm"]},
                 1, args.output)
        ledger["pool"]["quarantined"] = [
            q for q in qlist if not (isinstance(q, dict) and q.get("key") == key)
        ]
        if key not in ledger["pool"]["confirmed"]:
            ledger["pool"]["confirmed"].append(key)
        st = ledger["stories"].setdefault(key, {})
        st["status"] = "queued"
        st.setdefault("findings", []).append(
            f"{now_iso()} reconfirmed — {args.reason or 'repaired'}"
        )
        save_ledger(lpath, ledger)
        flip_backlog(orch, key, "x")
        emit({"status": "reconfirmed", "key": key}, 0, args.output)

    if args.action == "requisition":
        checklist = orch / "alignment-checklist.md"
        if not checklist.is_file():
            emit({"errors": ["alignment-checklist.md missing"]}, 2, args.output)
        lines = checklist.read_text(encoding="utf-8").splitlines()
        line = f"- [ ] {args.reason or 'requisition'} — needed by {key}"
        out_lines, placed = [], False
        for l in lines:
            out_lines.append(l)
            if l.strip().startswith("## Requisitions") and not placed:
                out_lines.append("")
                out_lines.append(line)
                placed = True
        if not placed:
            out_lines += ["", "## Requisitions", "", line]
        checklist.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        emit({"status": "requisition-filed", "key": key}, 0, args.output)

    if args.action == "release":
        # release {key} → that story's per-key lock only. g-* drain markers are
        # spawn-side state the drain removes at its end — a story release must
        # never unlink one, or the double-dispatch guard dies mid-drain.
        targets = []
        if args.key:
            targets = [l["path"] for l in iter_locks(orch)
                       if l["key"] == args.key and not l.get("group")]
        else:
            legacy = orch / "dispatch.lock"
            if legacy.is_file():
                targets.append(legacy)
        for lock in targets:
            lk = next((l for l in iter_locks(orch) if l["path"] == lock), None)
            session = lk["session"] if lk else None
            if session and not args.force:
                if not args.session:
                    emit({"errors": [f"lock for {lk['key']} held — release "
                                     "requires --session naming the holder "
                                     "(or --force to break)"]}, 1, args.output)
                if args.session != session:
                    emit({"errors": [f"lock for {lk['key']} held by {session} — "
                                     "use --force to break another session's "
                                     "lock"]}, 1, args.output)
            lock.unlink()
        emit({"status": "released", "key": args.key or None}, 0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
