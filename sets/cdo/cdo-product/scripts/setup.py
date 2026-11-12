#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""cdo-product department installer — deterministic half.

Actions (idempotent, never overwrites):

  1. verifies the cdo core is installed (orchestration dir exists)
  2. seeds `backlogs/product.md` (skip if present)
  3. merges `assets/dept-manifest.yaml` into `{orchestration_dir}/capabilities.yaml`
     under `departments.cdo-product` — prior runs' other departments untouched
  4. reports dept delegates available (bmad-prd etc.) vs missing

Usage:
  uv run setup.py --project-root /path/to/project [--orchestration-dir PATH]
      [--assets-dir PATH] [-o result.json]

Exit codes: 0=installed/ok, 1=prereq missing, 2=runtime error
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

DEPT = "cdo-product"
DELEGATES = [
    "bmad-prd", "bmad-ux", "bmad-create-story",
    # wondelai product-framework delegates (srm-synced wdl-*)
    "wdl-mom-test", "wdl-jobs-to-be-done", "wdl-continuous-discovery",
    "wdl-inspired-product", "wdl-lean-startup", "wdl-hundred-million-offers",
    "wdl-crossing-the-chasm", "wdl-obviously-awesome", "wdl-create-app",
    "wdl-create-business", "wdl-create-website", "wdl-design-sprint",
    "wdl-lean-ux", "wdl-blue-ocean-strategy", "wdl-good-strategy-bad-strategy",
    "wdl-monetizing-innovation",
]


def parse_args():
    p = argparse.ArgumentParser(description="Install the cdo-product department.")
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

    # 1. gate — dept modules ride on the cdo core
    if not orch.is_dir():
        emit({"status": "blocked",
              "errors": [f"cdo core not installed — no orchestration dir at {orch}. "
                         "Run cdo-setup first."]}, 1, args.output)

    # 2. seed backlog
    seeded, skipped = [], []
    seed = assets / "seeds" / "backlogs" / "product.md"
    target = orch / "backlogs" / "product.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        skipped.append("backlogs/product.md")
    elif seed.is_file():
        target.write_text(seed.read_text(encoding="utf-8"), encoding="utf-8")
        seeded.append("backlogs/product.md")

    # 3. probe delegates — results persist into capabilities.yaml so runtime
    # readers (dept SKILL activation, security-audit refs) don't re-probe
    found, missing = [], []
    for skill in DELEGATES:
        hit = any((root / d / skill / "SKILL.md").is_file()
                  for d in args.skill_dirs.split(","))
        (found if hit else missing).append(skill)

    # 4. merge manifest into capabilities.yaml (probe results included)
    manifest_path = assets / "dept-manifest.yaml"
    caps_path = orch / "capabilities.yaml"
    if not manifest_path.is_file():
        emit({"errors": [f"dept-manifest.yaml missing from {assets}"]}, 2, args.output)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    manifest["delegates_probe"] = {"available": found, "missing": missing}
    if caps_path.is_file():
        caps = yaml.safe_load(caps_path.read_text(encoding="utf-8")) or {}
    else:
        caps = {}
    caps.setdefault("departments", {})[DEPT] = manifest
    caps_path.write_text(yaml.safe_dump(caps, sort_keys=False), encoding="utf-8")

    # 4b. make the dept's backlog visible to cdo-align — merge backlog_map
    cfg_path = root / "_bmad" / "config.yaml"
    if cfg_path.is_file():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        bm = cfg.setdefault("cdo", {}).setdefault("backlog_map", {})
        stem = Path(str(manifest.get("backlog", DEPT.replace("cdo-", "")))).stem
        if bm.get(stem) != f"backlogs/{stem}.md":
            bm[stem] = f"backlogs/{stem}.md"
            cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    # 4. register help row (depts install after cdo-setup — self-register)
    help_csv = root / "_bmad" / "module-help.csv"
    help_row = (
        f'{DEPT},cdo-product,Product & Design Office,PDO,'
        '"Shape intake into specced items, co-sign alignment drafts, '
        'produce PRD/UX/story artifacts.",workflow,'
        '"shape|co-sign|produce|setup",pre-dispatch,,cdo-align,false,'
        'docs/orchestration/capabilities.yaml,'
        '"specced items, co-sign verdicts, spec artifacts"\n'
    )
    help_registered = False
    if help_csv.is_file():
        existing = help_csv.read_text(encoding="utf-8")
        if ",cdo-product," not in existing:
            with open(help_csv, "a", encoding="utf-8", newline="") as f:
                f.write(help_row)
            help_registered = True

    emit({
        "status": "installed",
        "dept": DEPT,
        "seeded": seeded,
        "skipped_existing": skipped,
        "capabilities_registered": sorted(
            (manifest.get("capabilities") or {}).keys()
        ),
        "delegates": {"available": found, "missing": missing},
        "help_registered": help_registered,
    }, 0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
