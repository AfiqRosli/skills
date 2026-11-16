#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""cdo-eng department installer — deterministic half.

  1. verifies the cdo core is installed (orchestration dir exists)
  2. ensures `backlogs/code.md` exists (cdo-setup usually seeds it; harmless skip)
  3. merges `assets/dept-manifest.yaml` into `{orchestration_dir}/capabilities.yaml`
  4. registers the dept help row
  5. probes delegate skills (cdo-code-e2e is THE critical one)

Usage:
  uv run setup.py --project-root /path/to/project [--orchestration-dir PATH]
      [--assets-dir PATH] [-o result.json]

Exit codes: 0=installed, 1=prereq missing, 2=runtime error
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

DEPT = "cdo-eng"
HELP_ROW = (
    'cdo-eng,cdo-eng,Software Engineering,ENG,'
    '"Shape code items, dispatch confirmed cards to cdo-code-e2e, repair '
    'blocked stories.",workflow,"shape|produce|repair|setup",dispatch,'
    'cdo-batch,,false,docs/orchestration/capabilities.yaml,'
    '"code pipeline results, repair patches"\n'
)

# cdo-code-e2e is the pipeline produce delegates to — its absence is a hard gap
DELEGATES = [
    "cdo-code-e2e", "bmad-create-story", "bmad-dev-story", "bmad-code-review",
    # wondelai engineering-method delegates (srm-synced wdl-*)
    "wdl-clean-code", "wdl-clean-architecture", "wdl-domain-driven-design",
    "wdl-pragmatic-programmer", "wdl-system-design", "wdl-ddia-systems",
    "wdl-software-design-philosophy", "wdl-design-code-architecture",
    "wdl-working-with-legacy-code", "wdl-remove-technical-debt",
    "wdl-refactoring-patterns", "wdl-37signals-way",
]
CRITICAL_DELEGATE = "cdo-code-e2e"


def parse_args():
    p = argparse.ArgumentParser(description="Install the cdo-eng department.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir",
                   help="default: {project-root}/docs/orchestration")
    p.add_argument("--assets-dir",
                   default=str(Path(__file__).parent.parent / "assets"))
    p.add_argument("--skill-dirs", default=".agents/skills,.devin/skills",
                   help="comma-separated dirs to probe for delegate skills")
    p.add_argument("-o", "--output")
    return p.parse_args()


def emit(result: dict, code: int, out: str):
    blob = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    orch = Path(args.orchestration_dir).resolve() if args.orchestration_dir \
        else root / "docs" / "orchestration"
    assets = Path(args.assets_dir)

    if not orch.is_dir():
        emit({"status": "blocked",
              "errors": [f"cdo core not installed — no orchestration dir at {orch}. "
                         "Run cdo-setup first."]}, 1, args.output)

    # probe delegates first — persist into capabilities.yaml
    found, missing = [], []
    for skill in DELEGATES:
        hit = any((root / d / skill / "SKILL.md").is_file()
                  for d in args.skill_dirs.split(","))
        (found if hit else missing).append(skill)

    manifest_path = assets / "dept-manifest.yaml"
    if not manifest_path.is_file():
        emit({"errors": [f"dept-manifest.yaml missing from {assets}"]}, 2, args.output)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    manifest["delegates_probe"] = {"available": found, "missing": missing}

    caps_path = orch / "capabilities.yaml"
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8")) or {} \
        if caps_path.is_file() else {}
    caps.setdefault("departments", {})[DEPT] = manifest
    caps_path.write_text(yaml.safe_dump(caps, sort_keys=False), encoding="utf-8")

    # backlog_map merge — makes code.md visible to cdo-align
    cfg_path = root / "_bmad" / "config.yaml"
    if cfg_path.is_file():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        bm = cfg.setdefault("cdo", {}).setdefault("backlog_map", {})
        stem = Path(str(manifest.get("backlog", DEPT.replace("cdo-", "")))).stem
        if bm.get(stem) != f"backlogs/{stem}.md":
            bm[stem] = f"backlogs/{stem}.md"
            cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    help_csv = root / "_bmad" / "module-help.csv"
    help_registered = False
    if help_csv.is_file() and ",cdo-eng," not in \
            help_csv.read_text(encoding="utf-8"):
        with open(help_csv, "a", encoding="utf-8", newline="") as f:
            f.write(HELP_ROW)
        help_registered = True

    emit({
        "status": "installed",
        "dept": DEPT,
        "capabilities_registered": sorted(
            (manifest.get("capabilities") or {}).keys()
        ),
        "delegates": {"available": found, "missing": missing},
        "help_registered": help_registered,
        "code_pipeline_ready": CRITICAL_DELEGATE in found,
        "warnings": [] if CRITICAL_DELEGATE in found else
            [f"{CRITICAL_DELEGATE} not installed — produce capability degraded"],
    }, 0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
