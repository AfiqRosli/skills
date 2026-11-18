#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
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

Preferred inputs (set the args, skip the transcription):
  --answers answers.json    proposed config — resolves orchestration_dir +
                          backlog_map (dept seed set) + configured dirs
  --detect detect.json      detected state — dept modules when --answers is absent
  --module-yaml module.yaml module_version for the setup-log line
  --report proposal.report.json   copied to <orch>/setup-report.json — the
                          source-of-value trail (override|stored|detected|default)

Explicit flags always win over --answers/--detect values.

Output: JSON {created, existing, skipped, errors}
Exit codes: 0=ok, 1=validation error, 2=runtime error
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # dept-manifest overrides degrade to name-stripping
    yaml = None

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
        default=None,
        help="Orchestration home, relative to project root or absolute "
             "(default: answers.module.orchestration_dir, else docs/orchestration)",
    )
    p.add_argument("--answers", default="",
                   help="propose-config answers.json — orchestration_dir, "
                        "backlog_map, and configured directories")
    p.add_argument("--detect", default="",
                   help="detect.json — dept module list when --answers is absent")
    p.add_argument("--module-yaml", default="",
                   help="module.yaml — module_version for the setup-log line")
    p.add_argument("--report", default="",
                   help="proposal report — copied to <orch>/setup-report.json")
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


def reject_unresolved_paths(args) -> None:
    """An unresolved `{project-root}` literal in a path arg would silently
    create a directory literally named `{project-root}` — refuse first."""
    bad = [n for n, v in vars(args).items()
           if isinstance(v, str) and "{project-root}" in v]
    if bad:
        print(json.dumps({"errors": [
            f"--{b.replace('_', '-')} still holds a literal "
            "'{project-root}' token — resolve it against the project root "
            "before calling" for b in sorted(bad)]}))
        sys.exit(2)


def _rel_to_root(root: Path, value: str) -> Path:
    """answers values carry a literal '{project-root}/' prefix — strip it."""
    v = value.replace("\\", "/")
    if v.startswith("{project-root}/"):
        v = v[len("{project-root}/"):]
    p = Path(v)
    return p if p.is_absolute() else root / p


def _looks_dir(value: str) -> bool:
    """A configured path to create: directory-shaped, not a file or glob."""
    leaf = Path(value).name
    return "*" not in value and "." not in leaf


def main():
    args = parse_args()
    reject_unresolved_paths(args)
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(json.dumps({"errors": [f"project root not found: {root}"]}))
        sys.exit(1)

    answers = {}
    if args.answers:
        answers = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    module_answers = answers.get("module") or {}
    detect = {}
    if args.detect:
        detect = json.loads(Path(args.detect).read_text(encoding="utf-8"))

    if args.orchestration_dir:
        orch = Path(args.orchestration_dir)
        if not orch.is_absolute():
            orch = root / orch
    elif module_answers.get("orchestration_dir"):
        orch = _rel_to_root(root, str(module_answers["orchestration_dir"]))
    else:
        orch = root / "docs" / "orchestration"

    seeds = Path(args.seeds).resolve()
    if not seeds.is_dir():
        print(json.dumps({"errors": [f"seeds dir not found: {seeds}"]}))
        sys.exit(1)

    seed_files = list(ALWAYS_SEED)
    skipped = []
    backlog_map = module_answers.get("backlog_map") or {}
    if backlog_map:
        # propose-config owns dept→backlog resolution — seed exactly the map
        seed_files += [v for v in backlog_map.values()
                       if isinstance(v, str) and v not in seed_files]
    else:
        dept_modules = [d.strip() for d in args.dept_modules.split(",")
                        if d.strip()]
        if not dept_modules and detect:
            dept_modules = sorted({
                n for names in (detect.get("skills") or {}).values()
                for n in names
                if n.startswith("cdo-") and n != "cdo-setup"})
        for dept, rel in DEPT_SEED.items():
            if dept in dept_modules:
                seed_files.append(rel)
            else:
                skipped.append(rel)

        # unknown dept modules get a bare backlog file — resolve via the
        # dept's own dept-manifest.yaml `backlog:` field (cdo-eng → code.md,
        # NOT eng.md) before falling back to name-stripping
        for dept in dept_modules:
            if dept not in DEPT_SEED:
                stem = dept.replace("cdo-", "")
                mpath = (root / ".agents" / "skills" / dept / "assets"
                         / "dept-manifest.yaml")
                if mpath.is_file() and yaml is not None:
                    try:
                        stem = Path(str(
                            (yaml.safe_load(
                                mpath.read_text(encoding="utf-8")) or {})
                            .get("backlog") or stem)).stem
                    except yaml.YAMLError:
                        pass
                if f"backlogs/{stem}.md" not in seed_files:
                    seed_files.append(f"backlogs/{stem}.md")

    created, existing, errors = [], [], []
    configured_dirs = {"created": [], "existing": []}

    # configured directories from the proposal — every {project-root}/-rooted
    # directory value gets created so config never points at a missing tree
    dir_values = {
        v for sect in (answers.get("core") or {}, module_answers)
        for v in sect.values()
        if isinstance(v, str) and v.startswith("{project-root}/")
        and _looks_dir(v)}
    for v in sorted(dir_values):
        target = _rel_to_root(root, v)
        try:
            rel_out = str(target.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel_out = str(target)
        if target.exists():
            configured_dirs["existing"].append(rel_out)
        else:
            target.mkdir(parents=True)
            configured_dirs["created"].append(rel_out)

    version = args.version
    if not version and args.module_yaml and yaml is not None:
        try:
            version = str((yaml.safe_load(
                Path(args.module_yaml).read_text(encoding="utf-8")) or {})
                .get("module_version") or "")
        except yaml.YAMLError:
            version = ""

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

        # proposal report persists the source trail (override|stored|
        # detected|default) — which values were decided vs defaulted
        if args.report:
            rsrc = Path(args.report)
            if rsrc.is_file():
                shutil.copyfile(rsrc, orch / "setup-report.json")
                rel_out = str((orch / "setup-report.json").relative_to(root)) \
                    .replace("\\", "/")
                created.append(rel_out)

        # setup-log.md appends — provenance across installs
        log_path = orch / SETUP_LOG
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = (f"- {stamp} | mode={args.mode or 'unknown'} | "
                 f"version={version or 'unknown'}"
                 f"{' | report=setup-report.json' if args.report else ''}\n")
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
        {"created": created, "existing": existing, "skipped": skipped,
         "configured_dirs": configured_dirs, "errors": errors},
        indent=2,
    ))
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
