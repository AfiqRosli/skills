#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Resolve cdo module config — one JSON blob for the orchestrator's activation.

Reads _bmad/config.yaml (cdo: section + shared root keys) and
_bmad/config.user.yaml (user prefs), applies defaults for anything unset,
and emits the resolved map Marshal works from. Replaces ~half a dozen
manual reads on every activation.

Usage:
  uv run resolve-config.py --project-root /path [-o out.json]

Output JSON keys: user_name, communication_language, document_output_language,
orchestration_dir, sprint_status_path, story_location, devlog_dir,
product_docs, package_manager, health_commands, backlog_map, earned_autonomy,
alignment_buffer_min, stall_timeout_minutes, batch_budget, ship_target,
dispatch_target, dispatch_mode, dispatch_permission_mode,
installed (bool — cdo section present).

{project-root} tokens in stored values are resolved against --project-root;
`resolved` fields carry absolute paths, raw values keep the token.

Exit codes: 0=ok, 2=runtime error
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

DEFAULTS = {
    "orchestration_dir": "{project-root}/docs/orchestration",
    "sprint_status_path": "{project-root}/_bmad-output/implementation-artifacts/sprint-status.yaml",
    "story_location": "{project-root}/_bmad-output/implementation-artifacts/stories",
    "devlog_dir": "{project-root}/docs/orchestration/devlog",
    "product_docs": "{project-root}/docs/product",
    "package_manager": None,
    "health_commands": "",
    "backlog_map": {},
    "earned_autonomy": "off",
    "alignment_buffer_min": 2,
    "stall_timeout_minutes": 45,
    "batch_budget": None,
    "ship_target": "preview",
    "dispatch_target": "local",
    "dispatch_mode": "auto",
    "dispatch_permission_mode": "bypass",
}

CORE_DEFAULTS = {
    "user_name": None,
    "communication_language": "English",
    "document_output_language": "English",
}


def parse_args():
    p = argparse.ArgumentParser(description="Resolve cdo module config to a single JSON blob.")
    p.add_argument("--project-root", required=True, help="Absolute project root")
    p.add_argument("-o", "--output", help="Write JSON to file instead of stdout")
    return p.parse_args()


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}


PATH_KEYS = {"orchestration_dir", "sprint_status_path", "story_location",
             "devlog_dir", "product_docs"}

# Core keys are canonical in the TOML layers on BMAD v6.12+ (config.toml /
# custom/config.toml / config.user.toml / custom/config.user.toml), resolved
# by the installer's own _bmad/scripts/resolve_config.py. YAML config.yaml /
# config.user.yaml remain the module-section contract (cdo: etc.) and the
# fallback when the resolver is absent. TOML wins for the keys it carries.
_CENTRAL_KEYS = [
    "core.user_name",
    "core.communication_language",
    "core.document_output_language",
]


def load_central(root: Path) -> dict:
    """Core config via the installer's TOML resolver. Returns {flat_key: value};
    empty dict when _bmad/scripts/resolve_config.py is missing or fails —
    callers fall back to the YAML reads."""
    script = root / "_bmad" / "scripts" / "resolve_config.py"
    if not script.is_file():
        return {}
    cmd = ["uv", "run", str(script), "--project-root", str(root)]
    for k in _CENTRAL_KEYS:
        cmd += ["--key", k]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            return {}
        data = json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}
    return {k.rsplit(".", 1)[-1]: v for k, v in data.items() if isinstance(v, str)}


def resolve(key, value, root: Path):
    """Return (raw, resolved-abs-path-or-None). Path-type keys resolve relative
    values against the project root whether or not they carry the token."""
    if key not in PATH_KEYS or not isinstance(value, str) or not value:
        return value, None
    if "{project-root}" in value:
        value = value.replace("{project-root}/", "").replace("{project-root}", "")
    p = Path(value)
    if not p.is_absolute():
        p = root / p
    return value, str(p)


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"error: project root not found: {root}", file=sys.stderr)
        sys.exit(2)

    shared = load_yaml(root / "_bmad" / "config.yaml")
    user = load_yaml(root / "_bmad" / "config.user.yaml")
    central = load_central(root)
    cdo = shared.get("cdo") if isinstance(shared.get("cdo"), dict) else {}

    out = {"installed": bool(cdo), "config": {}, "resolved_paths": {}}

    for key, default in CORE_DEFAULTS.items():
        out["config"][key] = central.get(key) or user.get(key, shared.get(key, default))

    for key, default in DEFAULTS.items():
        value = cdo.get(key, default)
        raw, resolved = resolve(key, value, root)
        out["config"][key] = raw
        if resolved:
            out["resolved_paths"][key] = resolved

    blob = json.dumps(out, indent=2)
    if args.output:
        Path(args.output).write_text(blob, encoding="utf-8")
    else:
        print(blob)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
