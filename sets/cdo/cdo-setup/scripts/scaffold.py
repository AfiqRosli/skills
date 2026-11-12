#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Scaffold the cdo orchestration tree — idempotent, never overwrites.

Creates the orchestration home directory layout and seeds each file from
assets/seeds/ when it doesn't already exist. Existing files are reported as
`existing`, never touched — safe to re-run for upgrades/repairs.

Department backlogs are conditional: `backlogs/code.md` always seeds; dept
backlogs seed only when their cdo-* modules are passed via --dept-modules.

`setup-log.md` is the one file that APPENDS — each run records a line so future
upgrades have provenance.

Usage:
  uv run scaffold.py --project-root /path [--orchestration-dir docs/orchestration]
      [--seeds ../assets/seeds] [--dept-modules cdo-growth,cdo-academy]
      [--version 0.1.0] [--mode fresh-install|upgrade] [--reseed doctrine.md]
      [--verbose]

Output: JSON {created, existing, skipped, errors}
Exit codes: 0=ok, 1=validation error, 2=runtime error
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ALWAYS_SEED = [
    "doctrine.md",
    "intent.md",
    "patterns.md",
    "alignment-checklist.md",
    "frago-inbox.md",
    "handover.md",
    "flow-ledger.yaml",
    "backlogs/README.md",
    "backlogs/code.md",
    "signals/README.md",
]

# dept module -> backlog seed file
DEPT_SEED = {
    "cdo-growth": "backlogs/content.md",
    "cdo-academy": "backlogs/curriculum.md",
}

SEED_DIRS = [
    "alignment",  # completed-alignment archive, YYYY/MM/DD inside
    "signals",    # frontline agents drop LINE_STOP etc. here; cdo-watch intake consumes
    "logs",       # chronology.md + autonomous-wake.log — the org's narrative
]

SETUP_LOG = "setup-log.md"
SETUP_LOG_HEADER = "# Setup Log\n\n<!-- One line per cdo-setup run — provenance for future upgrades. -->\n\n"


def parse_args():
    p = argparse.ArgumentParser(
        description="Scaffold the cdo orchestration tree idempotently."
    )
    p.add_argument("--project-root", required=True, help="Absolute project root")
    p.add_argument(
        "--orchestration-dir",
        default="docs/orchestration",
        help="Orchestration home, relative to project root or absolute",
    )
    p.add_argument(
        "--seeds",
        default=str(Path(__file__).parent.parent / "assets" / "seeds"),
        help="Seed directory (defaults to the skill's assets/seeds)",
    )
    p.add_argument("--dept-modules", default="",
                   help="Comma-separated installed cdo-* dept modules — gates their backlogs")
    p.add_argument("--version", default="", help="Module version recorded in setup-log.md")
    p.add_argument("--mode", default="", help="fresh-install|upgrade recorded in setup-log.md")
    p.add_argument("--reseed", metavar="FILE",
                   help="Overwrite one specific seed file (repairs corruption)")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(json.dumps({"errors": [f"project root not found: {root}"]}))
        sys.exit(1)

    orch = Path(args.orchestration_dir)
    if not orch.is_absolute():
        orch = root / orch
    seeds = Path(args.seeds).resolve()
    if not seeds.is_dir():
        print(json.dumps({"errors": [f"seeds dir not found: {seeds}"]}))
        sys.exit(1)

    dept_modules = [d.strip() for d in args.dept_modules.split(",") if d.strip()]
    seed_files = list(ALWAYS_SEED)
    skipped = []
    for dept, rel in DEPT_SEED.items():
        if dept in dept_modules:
            seed_files.append(rel)
        else:
            skipped.append(rel)

    # unknown dept modules get a bare backlog file — resolve via the dept's own
    # dept-manifest.yaml `backlog:` field (cdo-eng → code.md, NOT eng.md) before
    # falling back to name-stripping
    for dept in dept_modules:
        if dept not in DEPT_SEED:
            stem = dept.replace("cdo-", "")
            mpath = root / ".agents" / "skills" / dept / "assets" / "dept-manifest.yaml"
            if mpath.is_file():
                try:
                    import yaml
                    stem = Path(str(
                        (yaml.safe_load(mpath.read_text(encoding="utf-8")) or {})
                        .get("backlog") or stem)).stem
                except (yaml.YAMLError, ImportError):
                    pass
            seed_files.append(f"backlogs/{stem}.md")

    created, existing, errors = [], [], []

    try:
        orch.mkdir(parents=True, exist_ok=True)
        for d in SEED_DIRS:
            target = orch / d
            if target.exists():
                existing.append(str(target.relative_to(root)).replace("\\", "/"))
            else:
                target.mkdir(parents=True)
                created.append(str(target.relative_to(root)).replace("\\", "/"))

        reseed_rel = args.reseed.replace("\\", "/").lstrip("/") if args.reseed else None
        for rel in seed_files:
            src = seeds / rel
            dst = orch / rel
            dst_rel = str(dst.relative_to(root)).replace("\\", "/")
            is_reseed = reseed_rel == rel
            if dst.exists() and not is_reseed:
                existing.append(dst_rel)
                continue
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
            else:
                # unknown dept backlog — no seed on disk, write a minimal header
                if rel.startswith("backlogs/"):
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_text(
                        f"# {Path(rel).stem.title()} Backlog\n\n"
                        "<!-- Queue for this department. Feeds the align → dispatch → produce machinery. -->\n",
                        encoding="utf-8",
                    )
                else:
                    errors.append(f"missing seed: {rel}")
                    continue
            created.append(dst_rel + (" (reseeded)" if is_reseed else ""))
            if args.verbose:
                print(f"seeded {dst_rel}", file=sys.stderr)

        # setup-log.md appends — provenance across installs
        log_path = orch / SETUP_LOG
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"- {stamp} | mode={args.mode or 'unknown'} | version={args.version or 'unknown'}\n"
        if not log_path.exists():
            log_path.write_text(SETUP_LOG_HEADER + entry, encoding="utf-8")
            created.append(str(log_path.relative_to(root)).replace("\\", "/"))
        else:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(entry)
            existing.append(str(log_path.relative_to(root)).replace("\\", "/"))
    except OSError as e:
        print(json.dumps({"errors": [str(e)], "created": created, "existing": existing}))
        sys.exit(2)

    print(json.dumps(
        {"created": created, "existing": existing, "skipped": skipped, "errors": errors},
        indent=2,
    ))
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
