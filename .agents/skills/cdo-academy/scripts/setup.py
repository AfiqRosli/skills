#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""cdo-academy department installer — deterministic half.

Seeds the academy platform tree (docs/academy/ — catalog + track dirs), the
ops-side extraction dir (orchestration/learning/knowledge/), the curriculum
backlog, merges the dept manifest, registers the help row.

Split layout:
  docs/academy/                  — the public learning platform (site nav)
    index.md                     — landing page
    catalog.yaml                 — tracks -> courses -> modules coverage map
    {track}/{course}/NN-mod.md   — published module content
  docs/orchestration/learning/   — internal evidence (not public curriculum)
    knowledge/{key}.yaml         — per-story concept extractions
    cases/                       — continuity's forensic files (its own setup)

Usage:
  uv run setup.py --project-root /path/to/project [--orchestration-dir PATH]
      [--academy-dir PATH] [--assets-dir PATH] [-o result.json]

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

DEPT = "cdo-academy"
HELP_ROW = (
    'cdo-academy,cdo-academy,Learning & Capability,LCA,'
    '"Dissect shipped work into knowledge chains (fundamentals→advanced), '
    'gap-check curriculum coverage, author academy modules.",'
    'workflow,"extract|gap-check|produce|setup",learning,,,false,'
    'docs/orchestration/capabilities.yaml,'
    '"knowledge entries, curriculum items, course modules"\n'
)

# wondelai framework skills — the pre-validated curriculum backbone
DELEGATES = [
    "wdl-clean-code", "wdl-domain-driven-design", "wdl-system-design",
    "wdl-lean-startup", "wdl-jobs-to-be-done", "wdl-lean-analytics",
    "wdl-working-with-legacy-code", "wdl-release-it", "wdl-team-topologies",
    "wdl-continuous-discovery", "wdl-drive-motivation",
]


def parse_args():
    p = argparse.ArgumentParser(description="Install the cdo-academy department.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir",
                   help="default: {project-root}/docs/orchestration")
    p.add_argument("--academy-dir",
                   help="default: {project-root}/docs/academy")
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


def seed_file(seed: Path, target: Path, seeded: list, skipped: list):
    if target.is_file():
        skipped.append(str(target.name))
    elif seed.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(seed.read_text(encoding="utf-8"), encoding="utf-8")
        seeded.append(str(target.name))


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    orch = Path(args.orchestration_dir).resolve() if args.orchestration_dir \
        else root / "docs" / "orchestration"
    academy = Path(args.academy_dir).resolve() if args.academy_dir \
        else root / "docs" / "academy"
    assets = Path(args.assets_dir)

    if not orch.is_dir():
        emit({"status": "blocked",
              "errors": [f"cdo core not installed — no orchestration dir at {orch}. "
                         "Run cdo-setup first."]}, 1, args.output)

    # ops side: knowledge extractions live under orchestration
    (orch / "learning" / "knowledge").mkdir(parents=True, exist_ok=True)

    # public side: the academy platform tree
    academy.mkdir(parents=True, exist_ok=True)

    seeded, skipped = [], []
    seeds = assets / "seeds"
    seed_file(seeds / "academy" / "index.md", academy / "index.md",
              seeded, skipped)
    seed_file(seeds / "academy" / "catalog.yaml", academy / "catalog.yaml",
              seeded, skipped)
    seed_file(seeds / "backlogs" / "curriculum.md",
              orch / "backlogs" / "curriculum.md", seeded, skipped)

    # probe delegates — persist into capabilities.yaml
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

    # backlog_map merge — curriculum.md visible to cdo-align
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
    if help_csv.is_file() and ",cdo-academy," not in \
            help_csv.read_text(encoding="utf-8"):
        with open(help_csv, "a", encoding="utf-8", newline="") as f:
            f.write(HELP_ROW)
        help_registered = True

    emit({
        "status": "installed",
        "dept": DEPT,
        "academy_dir": str(academy),
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
