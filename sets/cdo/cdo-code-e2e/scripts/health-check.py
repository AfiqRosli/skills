#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Run the cdo-code-e2e health check and emit a compact JSON report.

Runs type-check, lint, and build via bun in the project root, returning
pass/fail per check with only the tail of failures — instead of dumping
raw logs into context. Scripts absent from package.json report
"skipped", not "fail". Dev-server/browser smoke is out of scope: the
user runs their own dev server outside this pipeline.

`--changed-files` may include directories (e.g. from `git status
--porcelain` untracked output) — they are expanded to the files they
contain before linting, and lint-ignored paths are dropped.

The build check is delta-aware: when --changed-files is given and no
file is build-critical (mirrors scripts/pre-push-build-validation.sh's
trigger list), build reports "skipped" — the pre-push hook re-validates
build-critical changes at push time anyway. --force-build overrides.

Usage: python health-check.py [PROJECT_ROOT] [--changed-files f1 f2 ...] [--force-build]
"""
import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

TAIL_LINES = 15
TIMEOUT_S = 600

# Mirrors scripts/pre-push-build-validation.sh TRIGGER_PATTERNS/TRIGGER_DIRS —
# keep in sync if that list changes.
BUILD_CRITICAL_FILES = {
    "netlify.toml", "package.json", "bun.lockb", "bun.lock",
    "nuxt.config.ts", "scripts/migrate.ts",
}
BUILD_CRITICAL_DIRS = ("server/",)

# Paths eslint ignores (or that never should be linted) — passing them
# explicitly produces spurious "all files ignored" failures.
IGNORED_PATH_PARTS = {
    "node_modules", ".git", ".nuxt", ".output", "dist", ".netlify",
}

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitpaths import expand_dirs, normalize_changed_paths  # noqa: E402


def is_build_critical(path: str) -> bool:
    norm = path.replace("\\", "/")
    return norm in BUILD_CRITICAL_FILES or norm.startswith(BUILD_CRITICAL_DIRS)


def run(cmd: list[str], cwd: Path) -> dict:
    if shutil.which(cmd[0]) is None:
        return {"cmd": " ".join(cmd), "status": "error", "exit": None,
                "tail": f"{cmd[0]} not found on PATH"}
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=TIMEOUT_S)
        ok = proc.returncode == 0
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-TAIL_LINES:])
        return {"cmd": " ".join(cmd), "status": "pass" if ok else "fail",
                "exit": proc.returncode, "tail": None if ok else tail}
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "status": "error", "exit": None,
                "tail": f"timed out after {TIMEOUT_S}s"}


def skipped(check: str, reason: str) -> dict:
    return {"cmd": check, "status": "skipped", "exit": None, "tail": reason}


def package_scripts(root: Path) -> dict:
    try:
        return json.loads(
            (root / "package.json").read_text(encoding="utf-8")
        ).get("scripts", {})
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project_root", type=Path, nargs="?", default=Path.cwd())
    ap.add_argument("--changed-files", nargs="*", default=None,
                    help="Lint only these files via bunx eslint (default: whole project lint script). Directories are expanded to files.")
    ap.add_argument("--only", default=None,
                    help="Comma-separated subset of checks: type-check,lint,build")
    ap.add_argument("--force-build", action="store_true",
                    help="Run the build check even when the delta has no build-critical files")
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    root = args.project_root.resolve()
    scripts = package_scripts(root)
    lint_files = None
    unparsed_files: list[str] = []
    if args.changed_files:
        paths, unparsed_files = normalize_changed_paths(args.changed_files)
        lint_files = expand_dirs(root, paths, IGNORED_PATH_PARTS)

    def type_check() -> dict:
        name = next((s for s in ("type-check", "typecheck", "tsc") if s in scripts), None)
        if name is None:
            return skipped("type-check", "no type-check script in package.json")
        return run(["bun", "run", name], root)

    def lint() -> dict:
        if lint_files is not None:
            # bun run lint forwards args after the "." baked into lint:js —
            # call eslint directly so scoping actually scopes.
            if unparsed_files:
                return {"cmd": "lint", "status": "error", "exit": None,
                        "tail": "un-parsable --changed-files lines (porcelain "
                                "status codes not normalized): "
                                + "; ".join(unparsed_files)}
            if shutil.which("bunx") is None:
                return skipped("lint", "bunx not found on PATH")
            if not lint_files:
                return skipped("lint", "no lintable files after expanding directories")
            return run(["bunx", "eslint", *lint_files], root)
        if "lint" not in scripts:
            return skipped("lint", "no lint script in package.json")
        return run(["bun", "run", "lint"], root)

    def build() -> dict:
        if "build" not in scripts:
            return skipped("build", "no build script in package.json")
        if not args.force_build and lint_files is not None \
                and not any(is_build_critical(f) for f in lint_files):
            hook_note = (" — pre-push hook re-validates build-critical changes at push"
                         if (root / "scripts" / "pre-push-build-validation.sh").exists()
                         else "")
            return skipped("build", f"no build-critical files in delta{hook_note}")
        return run(["bun", "run", "build"], root)

    available = {"type-check": type_check, "lint": lint, "build": build}
    if args.only:
        wanted = [s.strip() for s in args.only.split(",")]
        unknown = [s for s in wanted if s not in available]
        if unknown:
            print(f"error: unknown check(s): {', '.join(unknown)} "
                  f"(valid: {', '.join(available)})", file=sys.stderr)
            return 2
        selected = [available[s] for s in wanted]
    else:
        selected = list(available.values())

    with ThreadPoolExecutor(max_workers=len(selected)) as pool:
        checks = list(pool.map(lambda fn: fn(), selected))

    failed = [c for c in checks if c["status"] in ("fail", "error")]
    result = {
        "script": "health-check", "version": "1.2.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "summary": {"total": len(checks), "failed": len(failed),
                    "skipped": sum(c["status"] == "skipped" for c in checks)},
        "note": "dev-server/browser smoke not covered — user runs their own dev server; verify touched routes manually",
    }
    out = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
