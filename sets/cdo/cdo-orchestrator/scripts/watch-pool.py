#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""watch-pool — the 15-minute pool-activity watchdog for the CDO.

Detects the failure mode the plain watch can't: a dispatch worker whose
process is dead while confirmed or in-flight work remains. The g-*.lock
still looks fresh (24h TTL) and the per-key lock's heartbeat only goes
stale at 2x stall timeout, so ready-set refuses a respawn and the pool
silently wedges with stories owed.

Recovery mirrors the scripted dead-drain takeover the duty officer runs
by hand: break the dead session's locks, orphan its in-flight keys back
through `outcome blocked` -> `reconfirm` (attempts preserved, findings
journaled, WIP adoptable by the next claim), then respawn ONE drain on
ready-set's topo-ordered dispatch_now.

Cases per pass:
  live drain                        -> healthy, exit 0
  no drain + nothing pending        -> idle, exit 0
  dead drain + work pending         -> sweep, requeue, respawn, exit 1
  pending but undispatchable        -> report ready-set reasons, exit 1

Circuit breaker (sessions/pool-watch-state.json): a respawned drain
found dead at a later pass is a fast death. >=4 consecutive fast deaths,
or >=8 respawns in one UTC day, opens the breaker — the watchdog drops
an escalation signal for the frontline intake and stops spawning. Delete
the state file to reset after triage.

Cronable: locks/pool-watch.lock prevents overlap; every act lands in
logs/pool-watch.log as JSON lines; each pass also runs cdo-watch scan +
intake so stall/integrity signals keep flowing into the ledger.

Usage:
  python watch-pool.py --project-root ROOT --orchestration-dir docs/orchestration
      [--stall-timeout-minutes 45] [--dry-run]
Exit codes: 0=healthy/idle, 1=action taken or attention needed, 2=error
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

GRACE_MINUTES = 10        # unresolvable sessions younger than this are "live"
MAX_FAST_DEATHS = 4       # consecutive respawned drains dying -> breaker opens
MAX_DAY_RESPAWNS = 8      # hard daily respawn cap
LOCK_MAX_AGE_MIN = 30     # pool-watch.lock older than this = crashed pass
WORKER_PREFIX = "w-"      # dispatch workers (drains + lone) — r-/a- are mop-ups


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime | None = None) -> str:
    return (ts or now_utc()).strftime("%Y-%m-%dT%H:%M")


def parse_ts(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M").replace(
            tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def age_minutes(ts: str) -> float | None:
    t = parse_ts(ts)
    return ((now_utc() - t).total_seconds() / 60) if t else None


def log_line(orch: Path, record: dict) -> None:
    try:
        lf = orch / "logs" / "pool-watch.log"
        lf.parent.mkdir(exist_ok=True)
        with lf.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


def run(argv: list, cwd: Path, timeout: int = 120) -> tuple[int, dict | str]:
    """Run a sibling script; parse its stdout as JSON when possible."""
    try:
        r = subprocess.run(argv, cwd=str(cwd), capture_output=True,
                           text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 2, f"{argv[1] if len(argv) > 1 else argv[0]} failed: {e}"
    try:
        return r.returncode, json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        return r.returncode, (r.stdout or r.stderr or "").strip()


def pid_alive(pid: int) -> bool:
    """Liveness probe. tasklist on Windows (PID-reuse-tolerant via image
    name), os.kill(pid, 0) elsewhere."""
    if os.name == "nt":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=30)
            return f'"{pid}"' in r.stdout
        except (OSError, subprocess.TimeoutExpired):
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def session_records(orch: Path) -> dict:
    """session_name -> {pid, record_path} from sessions/*.json spawn
    records (skipping *.acp.json terminal records)."""
    out = {}
    sd = orch / "sessions"
    if not sd.is_dir():
        return out
    for f in sd.glob("*.json"):
        if f.name.endswith(".acp.json"):
            continue
        try:
            rec = json.loads(f.read_text(encoding="utf-8",
                                         errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue
        name = rec.get("session_name")
        if name and rec.get("pid"):
            out[name] = {"pid": rec["pid"], "record": f.name,
                         "started": rec.get("started", "")}
    return out


def drain_locks(orch: Path) -> list:
    """g-*.lock files -> [{path, session, ts, keys, age}]."""
    out = []
    ld = orch / "locks"
    if not ld.is_dir():
        return out
    for f in sorted(ld.glob("g-*.lock")):
        parts = f.read_text(encoding="utf-8", errors="replace").split()
        ts = parts[1] if len(parts) > 1 else ""
        out.append({
            "path": f, "session": parts[0] if parts else "",
            "ts": ts, "age": age_minutes(ts),
            "keys": parts[2].split(",") if len(parts) > 2 else []})
    return out


def in_flight(orch: Path) -> list:
    """[(key, session, step, step_started)] for ledger stories in-flight."""
    lpath = orch / "flow-ledger.yaml"
    try:
        import yaml
        ledger = yaml.safe_load(lpath.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    out = []
    for key, st in (ledger.get("stories") or {}).items():
        if isinstance(st, dict) and st.get("status") == "in-flight":
            out.append({"key": key, "session": st.get("session") or "",
                        "step": st.get("step"),
                        "step_started": st.get("step_started") or "",
                        "age": age_minutes(st.get("step_started") or "")})
    return out


def confirmed_pool(orch: Path) -> list:
    try:
        import yaml
        ledger = yaml.safe_load(
            (orch / "flow-ledger.yaml").read_text(encoding="utf-8")) or {}
        return (ledger.get("pool") or {}).get("confirmed") or []
    except Exception:
        return []


def load_state(orch: Path) -> dict:
    sf = orch / "sessions" / "pool-watch-state.json"
    try:
        st = json.loads(sf.read_text(encoding="utf-8"))
        if st.get("day") != now_utc().strftime("%Y-%m-%d"):
            st["day"], st["day_respawns"] = \
                now_utc().strftime("%Y-%m-%d"), 0
        return st
    except (json.JSONDecodeError, OSError):
        return {"fast_deaths": 0, "day": now_utc().strftime("%Y-%m-%d"),
                "day_respawns": 0, "respawns": []}


def save_state(orch: Path, st: dict) -> None:
    try:
        (orch / "sessions" / "pool-watch-state.json").write_text(
            json.dumps(st, indent=2), encoding="utf-8")
    except OSError:
        pass


def scripts(root: Path) -> dict:
    return {
        "dispatch": root / ".agents/skills/cdo-batch/scripts/dispatch.py",
        "ready": root / ".agents/skills/cdo-batch/scripts/ready-set.py",
        "spawn": root / ".agents/skills/cdo-batch/scripts/spawn-dispatch.py",
        "watch": root / ".agents/skills/cdo-watch/scripts/watch.py",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir", default="docs/orchestration")
    p.add_argument("--stall-timeout-minutes", type=int, default=45)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    root = Path(args.project_root).resolve()
    orch = Path(args.orchestration_dir)
    if not orch.is_absolute():
        orch = (root / orch).resolve()
    s = scripts(root)
    missing = [k for k, f in s.items() if not f.is_file()]
    if missing:
        rec = {"status": "error", "missing_scripts": missing}
        print(json.dumps(rec))
        return 2

    # overlap guard — a crashed pass leaves a stale lock to sweep
    locks_dir = orch / "locks"
    locks_dir.mkdir(exist_ok=True)
    lock = locks_dir / "pool-watch.lock"
    if lock.exists():
        age = (datetime.now().timestamp() - lock.stat().st_mtime) / 60
        if age < LOCK_MAX_AGE_MIN:
            rec = {"status": "skipped",
                   "reason": f"pool-watch.lock live ({age:.0f}m)"}
            print(json.dumps(rec))
            return 0
        lock.unlink()
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as fh:
            fh.write(f"pool-watch {iso()}")
    except FileExistsError:
        print(json.dumps({"status": "skipped",
                          "reason": "pool-watch.lock lost the race"}))
        return 0

    report = {"at": iso(), "live": [], "dead": [], "unresolvable": [],
              "recovered": [], "swept_locks": [], "actions": []}
    try:
        # cdo-watch legs — signals + intake first so the ledger is current
        if not args.dry_run:
            run([sys.executable, str(s["watch"]), "--orchestration-dir",
                 str(orch), "--mode", "intake"], root)
            rc, scan = run([sys.executable, str(s["watch"]),
                            "--orchestration-dir", str(orch), "--mode",
                            "scan", "--stall-timeout-minutes",
                            str(args.stall_timeout_minutes)], root)
            if isinstance(scan, dict):
                report["watch_signals"] = scan.get("signals", [])
                report["watch_anomalies"] = scan.get("anomalies", [])

        records = session_records(orch)
        inflight = in_flight(orch)
        pool = confirmed_pool(orch)
        dlocks = drain_locks(orch)
        grace = args.stall_timeout_minutes  # unresolvable-session horizon

        # liveness map for every session that holds pool work
        sessions = {d["session"] for d in dlocks}
        sessions.update(f["session"] for f in inflight
                        if f["session"].startswith(WORKER_PREFIX))
        status = {}  # session -> "live" | "dead" | "unresolvable"
        for sess in sessions:
            rec = records.get(sess)
            if rec and rec.get("pid"):
                status[sess] = "live" if pid_alive(rec["pid"]) else "dead"
                (report["live"] if status[sess] == "live"
                 else report["dead"]).append(
                    {"session": sess, "pid": rec["pid"]})
            else:
                # no pid to probe — grace for a spawn still writing its record
                ages = [d["age"] for d in dlocks if d["session"] == sess]
                ages += [f["age"] for f in inflight
                         if f["session"] == sess]
                age = min((a for a in ages if a is not None), default=None)
                status[sess] = ("unresolvable-young"
                                if age is not None and age < GRACE_MINUTES
                                else "dead")
                report["unresolvable" if status[sess] != "dead"
                       else "dead"].append(
                    {"session": sess, "reason": "no session record/pid",
                     "age_minutes": age})

        live_drains = [x for x in sessions
                       if status[x] in ("live", "unresolvable-young")
                       and x.startswith("w-")]
        dead_sessions = {x for x in sessions if status[x] == "dead"}

        pending = bool(pool) or bool(inflight)
        state = load_state(orch)
        # a drain this watchdog spawned is now dead — a fast death; the
        # streak resets only when a pass observes a live drain
        prior = {r.get("session") for r in state.get("respawns", [])}
        if dead_sessions & prior:
            state["fast_deaths"] = state.get("fast_deaths", 0) + 1
            report["fast_deaths"] = state["fast_deaths"]
            if not args.dry_run:
                save_state(orch, state)
        breaker_open = (state["fast_deaths"] >= MAX_FAST_DEATHS
                        or state["day_respawns"] >= MAX_DAY_RESPAWNS)

        if live_drains:
            # a drain survived a full pass — reset the death streak
            state["fast_deaths"] = 0
            if not args.dry_run:
                save_state(orch, state)
            report.update(status="healthy", drains=live_drains,
                          pool_confirmed=len(pool), in_flight=len(inflight))
        elif not pending and not dead_sessions:
            report.update(status="idle", pool_confirmed=0, in_flight=0)
        else:
            # dead or absent workers + work owed. Recover orphans.
            for f in inflight:
                if f["session"] not in dead_sessions:
                    continue
                key = f["key"]
                if not args.dry_run:
                    run([sys.executable, str(s["dispatch"]),
                         "--orchestration-dir", str(orch), "release", key,
                         "--force"], root)
                    run([sys.executable, str(s["dispatch"]),
                         "--orchestration-dir", str(orch), "outcome", key,
                         "--status", "blocked", "--reason",
                         f"worker {f['session']} died mid-run "
                         f"(pool-watch takeover)"], root)
                    run([sys.executable, str(s["dispatch"]),
                         "--orchestration-dir", str(orch), "reconfirm", key,
                         "--reason", "requeued after worker death — "
                         "attempts preserved, WIP adoptable"], root)
                report["recovered"].append(key)

            # sweep dead sessions' g-locks (+ orphans when nothing lives)
            for d in dlocks:
                if d["session"] in dead_sessions or (
                        not live_drains and
                        d["session"] not in [r["session"]
                                             for r in report["live"]]):
                    report["swept_locks"].append(d["path"].name)
                    if not args.dry_run:
                        d["path"].unlink(missing_ok=True)

            if not pending:
                report.update(status="idle-swept",
                              note="dead markers cleared, pool empty")
            else:
                rc, ready = run([sys.executable, str(s["ready"]),
                                 "--orchestration-dir", str(orch),
                                 "--stall-timeout-minutes",
                                 str(args.stall_timeout_minutes)], root)
                now_keys = ready.get("dispatch_now", []) \
                    if isinstance(ready, dict) else []
                report["waiting"] = ready.get("waiting", {}) \
                    if isinstance(ready, dict) else ready

                if not now_keys:
                    report.update(status="blocked",
                                  note="work pending, none dispatchable")
                elif breaker_open:
                    report.update(status="circuit-open",
                                  note="respawn breaker tripped — "
                                  "escalation filed, not spawning",
                                  dispatch_now=now_keys)
                    sig = (orch / "signals"
                           / f"escalation-pool-watch-{now_utc():%Y%m%d%H%M}.md")
                    if not args.dry_run:
                        sig.write_text(
                            "pool-watch breaker open: respawned drains "
                            f"keep dying ({state['fast_deaths']} fast "
                            f"deaths, {state['day_respawns']} respawns "
                            "today). exec-boundary failure is systemic — "
                            "triage before re-arming (delete "
                            "sessions/pool-watch-state.json).\n",
                            encoding="utf-8")
                        run([sys.executable, str(s["watch"]),
                             "--orchestration-dir", str(orch),
                             "--mode", "intake"], root)
                else:
                    # one key per spawn — each dispatch is its own session
                    # (its own console/session record); the finished
                    # session's exit triggers the next key's spawn on a
                    # later pass
                    keys_csv = now_keys[0]
                    if args.dry_run:
                        report["actions"].append(
                            f"would spawn drain --keys {keys_csv}")
                    else:
                        rc, spawn = run(
                            [sys.executable, str(s["spawn"]),
                             "--orchestration-dir", str(orch),
                             "--project-root", str(root),
                             "--keys", keys_csv], root, timeout=300)
                        report["spawn"] = spawn \
                            if isinstance(spawn, dict) \
                            else {"raw": spawn, "rc": rc}
                        if rc == 0:
                            state["day_respawns"] += 1
                            state["respawns"].append(
                                {"session": spawn.get("session_name"),
                                 "at": iso(), "keys": now_keys})
                            save_state(orch, state)
                            report.update(status="respawned",
                                          dispatch_now=now_keys)
                        else:
                            report.update(status="spawn-refused",
                                          dispatch_now=now_keys)

        report["status"] = report.get("status", "idle")
        log_line(orch, report)
        print(json.dumps(report, default=str))
        return 0 if report["status"] in ("healthy", "idle", "skipped") else 1
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
