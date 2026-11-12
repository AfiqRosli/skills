#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
project-greenfield-scaffold — verify orchestrator.

Runs the scaffolded project's checks and emits a compact JSON report
instead of raw multi-thousand-line build logs. Discovers which checks
exist by reading TARGET/package.json scripts — modules that were
skipped at render time are skipped here automatically.

Check order: type-check → lint → test:run → build → dev-boot. Each runs
`bun run <script>` (falls back to `npm run` when bun isn't on PATH).

dev-boot is the runtime probe the static checks cannot cover: it spawns
`bun run dev` on a scratch port and GETs / and /api/hello until 200 or
timeout, then kills the process tree. An import-time crash (a module
constructing a client without env, e.g. `new Resend()` with no key)
passes type-check/lint/tests/build yet 500s every route — this check
exists to catch exactly that.

Outputs JSON to stdout (or -o FILE): per-check status, exit code,
duration, and a short output tail on failure (default 40 lines —
enough for the LLM to diagnose without ingesting the full log).

Exit 0 when all checks pass, 1 when any fails, 2 on error.
"""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Ordered check candidates — first match wins per slot is not needed:
# all present scripts run in this order.
CHECKS = ["type-check", "lint", "test:run", "build"]

# Runtime probes for the dev-boot check. These routes exercise the page
# pipeline and the Elysia server module — import-time crashes in server
# code surface here while DB-dependent routes are deliberately avoided
# (they legitimately 500 on the shipped placeholder DATABASE_URL).
DEV_PROBES = ["/", "/api/hello"]


def run_check(target: Path, script: str, runner: str, tail_lines: int, verbose: bool) -> dict:
    cmd = [runner, "run", script]
    started = time.monotonic()
    if verbose:
        print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.run(
        cmd,
        cwd=target,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    duration = round(time.monotonic() - started, 1)
    combined = (proc.stdout or "") + (proc.stderr or "")
    tail = combined.strip().splitlines()[-tail_lines:] if proc.returncode != 0 else []
    return {
        "check": script,
        "command": " ".join(cmd),
        "status": "pass" if proc.returncode == 0 else "fail",
        "exit_code": proc.returncode,
        "duration_s": duration,
        "output_tail": tail,
    }


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, deadline: float) -> int | None:
    """Poll URL until deadline; return last seen status code (None = unreachable)."""
    code = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                code = resp.status
        except urllib.error.HTTPError as e:
            code = e.code
        except (urllib.error.URLError, ConnectionError, OSError):
            code = None
        if code == 200:
            return code
        time.sleep(2)
    return code


def kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
        )
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_dev_boot(target: Path, runner: str, timeout_s: int, tail_lines: int, verbose: bool) -> dict:
    port = free_port()
    cmd = [runner, "run", "dev"]
    if runner == "npm":
        cmd.append("--")  # npm needs the separator to forward args to the script
    cmd += ["--port", str(port), "--host", "127.0.0.1"]
    env = {**os.environ, "NUXT_IGNORE_LOCK": "1"}
    started = time.monotonic()
    if verbose:
        print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    log = tempfile.NamedTemporaryFile(
        mode="w+b", delete=False, suffix=".log", prefix="verify-dev-"
    )
    probes: dict[str, int | None] = {}
    status = "fail"
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=target,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )
        deadline = time.monotonic() + timeout_s
        for path in DEV_PROBES:
            code = wait_http(f"http://127.0.0.1:{port}{path}", deadline)
            probes[path] = code
            if code != 200:
                break
        if len(probes) == len(DEV_PROBES) and all(c == 200 for c in probes.values()):
            status = "pass"
    finally:
        try:
            kill_tree(proc)  # type: ignore[possibly-undefined]
        except NameError:
            pass
        log.close()
    duration = round(time.monotonic() - started, 1)
    tail = []
    try:
        lines = Path(log.name).read_text(encoding="utf-8", errors="replace").strip().splitlines()
        tail = lines[-tail_lines:] if status == "fail" else []
    finally:
        try:
            os.unlink(log.name)
        except OSError:
            pass
    return {
        "check": "dev-boot",
        "command": " ".join(cmd),
        "status": status,
        "exit_code": 0 if status == "pass" else 1,
        "duration_s": duration,
        "probes": probes,
        "output_tail": tail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the scaffolded project's verify gate (type-check/lint/test:run/build) and emit compact JSON.",
    )
    parser.add_argument("target", nargs="?", default=".", help="Scaffolded project directory")
    parser.add_argument("--checks", help="Comma-separated package.json scripts to run (default: auto-discover)")
    parser.add_argument("--tail", type=int, default=40, help="Output lines kept per failing check (default 40)")
    parser.add_argument("--runner", choices=["bun", "npm"], help="Package runner (default: bun if on PATH, else npm)")
    parser.add_argument("--stop-on-fail", action="store_true", help="Halt at first failed check")
    parser.add_argument("--no-dev", action="store_true", help="Skip the dev-boot runtime probe")
    parser.add_argument("--dev-timeout", type=int, default=240, help="Seconds to wait for the dev server per probe (default 240)")
    parser.add_argument("-o", "--output", help="Write JSON report to file instead of stdout")
    parser.add_argument("--verbose", action="store_true", help="Progress to stderr")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    pkg_path = target / "package.json"
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {pkg_path}: {e}", file=sys.stderr)
        return 2

    scripts = set(pkg.get("scripts", {}).keys())
    if args.checks:
        checks = [c.strip() for c in args.checks.split(",") if c.strip()]
    else:
        checks = [c for c in CHECKS if c in scripts]
    if not checks:
        print("error: no known check scripts found in package.json", file=sys.stderr)
        return 2

    runner = args.runner or ("bun" if shutil.which("bun") else "npm")

    results = []
    status = "pass"
    for check in checks:
        if check not in scripts:
            results.append({"check": check, "status": "skipped", "reason": "not in package.json scripts"})
            continue
        r = run_check(target, check, runner, args.tail, args.verbose)
        results.append(r)
        if r["status"] == "fail":
            status = "fail"
            if args.stop_on_fail:
                break

    if "dev" in scripts and not args.no_dev and not (args.stop_on_fail and status == "fail"):
        r = run_dev_boot(target, runner, args.dev_timeout, args.tail, args.verbose)
        results.append(r)
        if r["status"] == "fail":
            status = "fail"

    report = {
        "script": "verify",
        "version": "1.0.0",
        "skill_path": str(SCRIPT_DIR.parent),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "target": str(target),
        "runner": runner,
        "checks": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("status") == "pass"),
            "failed": sum(1 for r in results if r.get("status") == "fail"),
            "skipped": sum(1 for r in results if r.get("status") == "skipped"),
        },
    }

    # Persist into the scaffold state artifact so --status (and a resumed
    # session) can see the verify leg already ran.
    state_file = target / ".scaffold-report.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["verify"] = report
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError) as e:
            print(f"warning: could not update {state_file}: {e}", file=sys.stderr)

    payload = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)

    return 0 if status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
