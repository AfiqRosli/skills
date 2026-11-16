#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""cdo-continuity department installer — deterministic half.

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

DEPT = "cdo-continuity"
HELP_ROW = (
    'cdo-continuity,cdo-continuity,Continuity & Recovery,CRO,'
    '"Forensic case files, post-crash state recovery, incident response via '
    'cybersec IR delegates.",workflow,"forensic|recover|incident|setup",'
    'recovery,,,false,docs/orchestration/capabilities.yaml,'
    '"case files, recovery reports, IR coordination"\n'
)

DELEGATES = [
    "bmad-bus-cybersec-team-incident-commander",
    "bmad-bus-cybersec-team-incident-response-playbook",
    "bmad-bus-cybersec-team-blue-team-lead",
    "bmad-bus-cybersec-team-forensic-investigator",
    # wondelai resilience/repair method sources
    "wdl-release-it", "wdl-working-with-legacy-code",
]


def parse_args():
    p = argparse.ArgumentParser(description="Install the cdo-continuity department.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir",
                   help="default: {project-root}/docs/orchestration")
    p.add_argument("--assets-dir",
                   default=str(Path(__file__).parent.parent / "assets"))
    p.add_argument("--skill-dirs", default=".agents/skills,.devin/skills")
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

    seeded, skipped = [], []
    seed = assets / "seeds" / "backlogs" / "continuity.md"
    target = orch / "backlogs" / "continuity.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        skipped.append("backlogs/continuity.md")
    elif seed.is_file():
        target.write_text(seed.read_text(encoding="utf-8"), encoding="utf-8")
        seeded.append("backlogs/continuity.md")
    (orch / "learning" / "cases").mkdir(parents=True, exist_ok=True)

    found, missing = [], []
    for skill in DELEGATES:
        hit = any((root / d / skill / "SKILL.md").is_file()
                  for d in args.skill_dirs.split(","))
        (found if hit else missing).append(skill)

    manifest_path = assets / "dept-manifest.yaml"
    if not manifest_path.is_file():
        emit({"errors": ["dept-manifest.yaml missing"]}, 2, args.output)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    manifest["delegates_probe"] = {"available": found, "missing": missing}
    caps_path = orch / "capabilities.yaml"
    caps = yaml.safe_load(caps_path.read_text(encoding="utf-8")) or {} \
        if caps_path.is_file() else {}
    caps.setdefault("departments", {})[DEPT] = manifest
    caps_path.write_text(yaml.safe_dump(caps, sort_keys=False), encoding="utf-8")

    # backlog_map merge — continuity.md visible to cdo-align
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
    if help_csv.is_file() and ",cdo-continuity," not in \
            help_csv.read_text(encoding="utf-8"):
        with open(help_csv, "a", encoding="utf-8", newline="") as f:
            f.write(HELP_ROW)
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
        "ir_ready": bool(found),
        "help_registered": help_registered,
    }, 0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
