#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Build the cdo answers JSON — the deterministic merge of four value layers.

Priority (highest wins):
  1. --set key=value overrides (explicit user/automator edits)
  2. prior stored cdo: config (upgrade path — never silently resets)
  3. detected conventions (sprint path, package manager, health commands…)
  4. module.yaml defaults

Emits {"core": {...}, "module": {...}} ready to feed merge-config.py, plus a
human-facing `proposed` table showing where each value came from — the same
data the skill renders as the single config-confirmation table.

Usage:
  uv run propose-config.py --detect <detect.json> --module-yaml ./assets/module.yaml
      [--set orchestration_dir=docs/ops ...] [-o answers.json] [--no-core]

Exit codes: 0=ok, 1=validation error, 2=runtime error
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

# How detection maps onto module.yaml variables. Values are (detect path, transform).
DETECTION_MAP = {
    "sprint_status_path": ("conventions.sprint_status_files", "first"),
    "story_location": ("conventions.story_dir", "prefix"),
    "devlog_dir": ("conventions.devlog_dir", "prefix"),
    "package_manager": ("conventions.package_manager", "raw"),
    "health_commands": ("conventions.health_commands", "join"),
}

# dept skill -> backlog file convention (depts whose backlog name ≠ dept stem)
DEPT_BACKLOG = {
    "cdo-product": "backlogs/product.md",
    "cdo-eng": "backlogs/code.md",
    "cdo-growth": "backlogs/content.md",
    "cdo-academy": "backlogs/curriculum.md",
}

CORE_VARS = {
    "user_name": "BMad",
    "communication_language": "English",
    "document_output_language": "English",
    "output_folder": "{project-root}/_bmad-output",
}


def parse_args():
    p = argparse.ArgumentParser(description="Build cdo answers JSON from layered sources.")
    p.add_argument("--detect", required=True, help="Path to detect.py JSON output")
    p.add_argument("--module-yaml", required=True, help="Path to assets/module.yaml")
    p.add_argument("--set", dest="overrides", action="append", default=[],
                   metavar="KEY=VALUE", help="Override a module variable (repeatable)")
    p.add_argument("--core-set", dest="core_overrides", action="append", default=[],
                   metavar="KEY=VALUE", help="Override a core config value (repeatable)")
    p.add_argument("--no-core", action="store_true",
                   help="Omit core block (core config already exists)")
    p.add_argument("-o", "--output", help="Write answers JSON to file (default stdout)")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def dig(data: dict, dotted: str):
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def apply_transform(value, how: str):
    if value is None:
        return None
    if how == "first":
        return value[0] if isinstance(value, list) and value else None
    if how == "join":
        return ", ".join(v for v in value.values()) if isinstance(value, dict) else None
    if how == "prefix":
        return f"{{project-root}}/{value}" if value else None
    return value  # raw


def parse_kv(pairs: list) -> dict:
    out = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"error: --set needs KEY=VALUE, got {pair!r}", file=sys.stderr)
            sys.exit(1)
        k, v = pair.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main():
    args = parse_args()
    try:
        detect = json.loads(Path(args.detect).read_text(encoding="utf-8"))
        module_yaml = yaml.safe_load(Path(args.module_yaml).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

    prior = detect.get("prior_cdo_config") or {}
    overrides = parse_kv(args.overrides)
    core_overrides = parse_kv(args.core_overrides)

    # variable keys = dict-valued entries in module.yaml
    var_keys = [k for k, v in module_yaml.items()
                if isinstance(v, dict) and ("prompt" in v or "default" in v)]

    # unknown override keys never match a var and silently no-op — name them
    unknown = sorted(set(overrides) - set(var_keys))
    if unknown:
        print(json.dumps({"errors": [
            f"unknown --set key(s): {', '.join(unknown)} — "
            f"valid: {', '.join(var_keys)}"]}))
        sys.exit(1)
    unknown_core = sorted(set(core_overrides) - set(CORE_VARS))
    if unknown_core:
        print(json.dumps({"errors": [
            f"unknown --core-set key(s): {', '.join(unknown_core)} — "
            f"valid: {', '.join(CORE_VARS)}"]}))
        sys.exit(1)

    proposed = []   # [(key, value, source)]
    module_answers = {}

    for key in var_keys:
        var_def = module_yaml[key]
        detected = None
        if key in DETECTION_MAP:
            path, how = DETECTION_MAP[key]
            detected = apply_transform(dig(detect, path), how)

        if key in overrides:
            value, source = overrides[key], "override"
        elif key in prior:
            value, source = prior[key], "stored"
        elif detected:
            value, source = detected, "detected"
        else:
            value, source = var_def.get("default"), "default"

        if value is not None and value != "":
            module_answers[key] = value
        proposed.append({"key": key, "value": value, "source": source})

    # carry stored module keys not defined in module.yaml (hand-tuned values)
    for key, value in prior.items():
        if key not in module_answers and key not in ("name", "description", "version", "default_selected"):
            module_answers[key] = value
            proposed.append({"key": key, "value": value, "source": "stored (extra)"})

    # backlog_map — keyed by backlog stem; value is the file. Dept keys resolve
    # via their manifest `backlog:` convention (cdo-growth → content, not growth)
    backlog_map = {"code": "backlogs/code.md"}
    for dept in detect.get("soft_deps", {}).get("dept_modules", []):
        stem = Path(DEPT_BACKLOG.get(dept,
                        f"backlogs/{dept.replace('cdo-', '')}.md")).stem
        backlog_map[stem] = f"backlogs/{stem}.md"
    module_answers["backlog_map"] = backlog_map
    proposed.append({"key": "backlog_map", "value": backlog_map, "source": "derived"})

    # Core keys already live in config.yaml — omitting the core block protects
    # the user's configured identity from being reset to defaults. Explicit
    # --core-set still wins (the caller means to change that value).
    core_present = detect.get("core_keys_present") or []
    skip_core = args.no_core or (core_present and not core_overrides)
    answers = {"module": module_answers}
    if not skip_core:
        core = {**CORE_VARS, **core_overrides}
        answers["core"] = core
        for k, v in core.items():
            proposed.append({"key": f"core.{k}", "value": v,
                             "source": "override" if k in core_overrides else "default"})

    report = {
        "script": "cdo-propose-config",
        "mode": detect.get("mode"),
        "proposed": proposed,
        "answers": answers,
        "core_auto_omitted": bool(core_present and not args.no_core
                                  and not core_overrides),
    }
    if report["core_auto_omitted"]:
        report["note"] = ("core block omitted — existing core keys detected "
                          f"({', '.join(core_present)}); pass --core-set to "
                          "override a value explicitly")
    out = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(json.dumps(answers, indent=2), encoding="utf-8")
        Path(str(args.output) + ".report.json").write_text(out, encoding="utf-8")
        if args.verbose:
            print(f"wrote {args.output} (+ .report.json)", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
