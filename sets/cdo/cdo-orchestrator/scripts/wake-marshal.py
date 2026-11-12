# /// script
# requires-python = ">=3.10"
# ///
"""wake-marshal — spawn an autonomous Marshal wake as a local Devin ACP
session. Designed for Task Scheduler (hourly cadence) but works invoked
by hand; --dry-run composes the prompt + record without spawning.

The wake is an ACP session under tab-id `cdo-marshal` — viewable in the
Devin IDE like drain/review sessions. A `locks/wake.lock` guard prevents
overlap: a fresh lock means the previous wake is still running → skip;
a stale one means it crashed → sweep and go anyway.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OPERATOR = "Operator"


def _operator_name(root: Path) -> str:
    """'Operator Afiq' — _bmad/config.user.yaml `user_name`, then the
    BMAD user block."""
    import re
    for name in ("config.user.yaml", "config.yaml"):
        cfg = root / "_bmad" / name
        if cfg.is_file():
            m = re.search(r"^\s*user_name:\s*['\"]?([^'\"\n]+)",
                          cfg.read_text(encoding="utf-8"), re.M)
            if m and m.group(1).strip():
                return f"{OPERATOR} {m.group(1).strip()}"
    return OPERATOR


def _prompt(orch: Path, root: Path, operator: str) -> str:
    return f"""You are Marshal — the Chief Delivery Officer of this repo's autonomous delivery org — running an autonomous wake. Your human decision-maker is {operator}. No one is watching; act within the authority envelope, write everything down, and exit.

Invoke the `cdo-orchestrator` skill, then run the Default Wake sequence in `.agents/skills/cdo-orchestrator/references/autonomous-wake.md`: resume (handover.md + flow-ledger.yaml + intent.md) → FRAGO inbox → signal/escalation triage → advance the batch (spawn ONE drain if pool.confirmed is non-empty and no fresh g-*.lock marks a live drain) → mop up delivered reviews/extractions → boundaries hold → update handover.md → append your wake entry to logs/autonomous-wake.log → exit.

Orchestration home: {orch}
Project root: {root}
Rules of engagement: read `.agents/skills/cdo-orchestrator/references/access-boundaries.md` before touching state — deny zones are load-bearing. Never execute unaligned work; production ship stays {operator}-gated. Everything happens on the `preview` lane — local work lands on the `cdo-lane` ref, and the ONLY origin push is a signed `## Pre-deploy Sign-offs` item run through cdo-platform's push leg. Never create or push other branches.
"""


def _log(orch: Path, record: dict) -> None:
    """windowless-safe trace — pythonw has no console to print to"""
    try:
        lf = orch / "logs" / "wake-spawn.log"
        lf.parent.mkdir(exist_ok=True)
        with lf.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", default="",
                   help="repo root (default: orchestration-dir's grandparent)")
    p.add_argument("--orchestration-dir", default="docs/orchestration")
    p.add_argument("--devin-bin", default="devin")
    p.add_argument("--env-file", default=".env")
    p.add_argument("--mode", default="bypass")
    p.add_argument("--lock-max-age-min", type=int, default=60,
                   help="wake.lock older than this counts as a crash")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    # resolve relative paths against the project root — Task Scheduler's
    # cwd is System32, not the repo
    root = Path(args.project_root).resolve() if args.project_root else None
    orch = Path(args.orchestration_dir)
    if not orch.is_absolute():
        orch = ((root or Path.cwd()) / orch).resolve()
    if root is None:
        root = orch.parent.parent
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    sess = orch / "sessions"
    sess.mkdir(exist_ok=True)
    prompt_file = sess / f"wake-{ts}.prompt.md"
    session_json = sess / f"wake-{ts}.acp.json"
    log_file = sess / f"wake-{ts}.log"
    locks = orch / "locks"
    locks.mkdir(exist_ok=True)
    lock = locks / "wake.lock"

    if lock.exists():
        age_min = (datetime.now().timestamp() - lock.stat().st_mtime) / 60
        if age_min < args.lock_max_age_min:
            rec = {"status": "skipped",
                   "reason": f"wake.lock live ({age_min:.0f}m)"}
            _log(orch, rec)
            print(json.dumps(rec))
            return 0
        lock.unlink()  # stale — the previous wake crashed holding it

    if args.dry_run:
        print(json.dumps({"status": "dry-run",
                          "prompt_file": str(prompt_file),
                          "operator": _operator_name(root)}))
        return 0

    # exclusive create — two scheduler fires can't both run a wake
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as fh:
            fh.write(f"w-marshal-{ts} {datetime.now(timezone.utc):%Y-%m-%dT%H:%M}")
    except FileExistsError:
        print(json.dumps({"status": "skipped",
                          "reason": "wake.lock lost the race"}))
        return 0

    prompt_file.write_text(_prompt(orch, root, _operator_name(root)),
                           encoding="utf-8")
    worker = (root / ".agents" / "skills" / "cdo-batch" / "scripts"
              / "acp-worker.py")
    argv = [sys.executable, str(worker),
            "--project-root", str(root),
            "--orchestration-dir", str(orch),
            "--prompt-file", str(prompt_file),
            "--devin-bin", args.devin_bin,
            "--env-file", str(root / args.env_file),
            "--mode", args.mode,
            "--tab-id", "cdo-marshal",
            "--session-json", str(session_json),
            "--log", str(log_file),
            "--echo"]
    def pid_alive(pid: int) -> bool:
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=30)
            return f'"{pid}"' in r.stdout
        except (OSError, subprocess.TimeoutExpired):
            return False

    code = 2
    leave_lock = False
    try:
        if os.name == "nt":
            # WMI spawn, same as spawn-dispatch — the worker is parented
            # to the WMI service host, so a Task Scheduler stop (battery
            # switch, job close, runtime limit) reaps only this waiter,
            # never the wake. Visible console; --echo progress tees to a
            # side log (NOT the session log — the worker opens it itself).
            shim = sess / f"wake-{ts}.cmd"
            shim.write_text(
                "@echo off\r\nset PYTHONIOENCODING=utf-8\r\n"
                "set PYTHONUTF8=1\r\n"
                + subprocess.list2cmdline(argv) +
                " 2>&1 | powershell -NoProfile -Command \"$input | "
                f"Tee-Object -FilePath '{sess / f'wake-{ts}.out.log'}'\""
                "\r\n", encoding="utf-8")
            sp = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "$r = Invoke-CimMethod -ClassName Win32_Process "
                 "-MethodName Create -Arguments @{ CommandLine = "
                 f"'cmd.exe /c \"{shim}\"'; CurrentDirectory = "
                 f"'{root}' }}; if ($r.ReturnValue -eq 0) "
                 "{ Write-Output $r.ProcessId } else { exit 1 }"],
                capture_output=True, text=True, timeout=30)
            if sp.returncode != 0 or not sp.stdout.strip():
                raise OSError(f"WMI spawn failed: {sp.stderr.strip()}")
            pid = int(sp.stdout.strip().splitlines()[-1])
            deadline = time.time() + args.lock_max_age_min * 60
            while pid_alive(pid) and time.time() < deadline:
                time.sleep(15)
            if pid_alive(pid):
                leave_lock = True
                code = 0
            elif session_json.is_file():
                try:
                    code = 2 if json.loads(session_json.read_text(
                        encoding="utf-8")).get("errors") else 0
                except (json.JSONDecodeError, OSError):
                    code = 2
            else:
                code = 2  # died hard — no terminal record
        else:
            r = subprocess.run(argv, cwd=str(root))
            code = r.returncode
    finally:
        if leave_lock:
            # wake outlived the wait window — refresh the lock so the
            # next fire reads it live, not crash-swept
            lock.write_text(
                f"w-marshal-{ts} "
                f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M}")
        else:
            lock.unlink(missing_ok=True)
    result = {"status": ("still-running" if leave_lock
                         else "done" if code == 0 else "failed"),
              "wake_session": f"w-marshal-{ts}",
              "session_json": str(session_json),
              "rc": code}
    _log(orch, result)
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    sys.exit(main())
