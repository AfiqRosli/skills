#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Env-var parity check for cdo-code-e2e — deterministic replacement for the
manual .env/.env.example scans in steps 3, 5, and 8.

Extracts env-var NAMES referenced by the changed files
(process.env.X / import.meta.env.X / process.env["X"] / import.meta.env["X"])
and reports which are missing from .env and .env.example. Key names only —
secret values are never read or emitted.

Usage:
  python env-parity.py [PROJECT_ROOT] [--files f1 f2 ...]
  (files may be plain paths or `git status --porcelain` output;
   default input is porcelain at PROJECT_ROOT)
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitpaths import expand_dirs, normalize_changed_paths  # noqa: E402

ENV_REF_RE = re.compile(
    r"(?:process\.env|import\.meta\.env)\s*(?:\.\s*|\[\s*[\"'])([A-Z_][A-Z0-9_]*)")
SCAN_EXTENSIONS = {
    ".ts", ".tsx", ".vue", ".js", ".jsx", ".mjs", ".cjs", ".py", ".sh",
}
IGNORED_PARTS = {"node_modules", ".git", ".nuxt", ".output", "dist", ".netlify"}


def env_keys(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=", line)
        if m:
            keys.add(m.group(1))
    return keys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project_root", type=Path, nargs="?", default=Path.cwd())
    ap.add_argument("--files", nargs="*", default=None,
                    help="Files to scan (porcelain input normalized; default: git status)")
    args = ap.parse_args()

    root = args.project_root.resolve()
    if args.files is not None:
        changed, unparsed = normalize_changed_paths(args.files)
    else:
        proc = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
        changed, unparsed = normalize_changed_paths(proc.stdout.splitlines())

    scan_files = [
        f for f in expand_dirs(root, changed, IGNORED_PARTS)
        if Path(f).suffix in SCAN_EXTENSIONS and (root / f).is_file()
    ]

    referenced: dict[str, list[str]] = {}
    for f in scan_files:
        for m in ENV_REF_RE.finditer(
                (root / f).read_text(encoding="utf-8", errors="replace")):
            referenced.setdefault(m.group(1), [])
            if f not in referenced[m.group(1)]:
                referenced[m.group(1)].append(f)

    env_defined = env_keys(root / ".env")
    example_defined = env_keys(root / ".env.example")
    missing_env = sorted(k for k in referenced if k not in env_defined)
    missing_example = sorted(k for k in referenced if k not in example_defined)

    result = {
        "script": "env-parity", "version": "1.0.0",
        "status": "pass" if not missing_env and not missing_example else "fail",
        "scanned_files": len(scan_files),
        "referenced": {k: referenced[k] for k in sorted(referenced)},
        "missing_in_env": missing_env,
        "missing_in_env_example": missing_example,
        "unparsed_input": unparsed,
    }
    if unparsed:
        result["status"] = "error"
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
