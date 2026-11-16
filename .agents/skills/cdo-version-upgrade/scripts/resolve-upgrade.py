#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""resolve-upgrade.py — pre-flight + plan for a sprint-boundary version upgrade.

Resolves the old->new version pair, partitions terminal/non-terminal stories,
and validates inputs BEFORE anything is rewritten — the human 'y' is no longer
the only pre-mutation validator. Emits the plan as JSON; the prompt renders the
single confirmation gate from it, or a headless caller consumes it directly.

Version resolution (mirrors references/workflow.md INITIALIZATION):
  old_version = newest version possessing all three artifacts
    (epics-beta-{v}.md + sprint-status-{v}.yaml + {v}/ spec folder) —
    never blindly release-train.current.
  new_version, in order:
    1. --new-version argument
    2. catch-up: release-train.current's version core ahead of old_version's
       AND its candidate sprint id (current.sprint, else {name}-{version})
       differs from old_version -> that sprint id
    3. otherwise -> {Channel}-{today} (suggestion only; caller confirms)

The plan JSON carries a `reclassify` object the caller may fill
{story-key: status} for done-vs-spec disagreements, plus `epic_order` and
`new_version` fields to confirm/edit before handing to partition-renumber.py.

Usage:
  uv run resolve-upgrade.py --project-root PATH [--new-version ID]
      [--epic-order "3,1,2"|preserve] [--today YYYY-MM-DD]
      [--release-train PATH] [--planning-artifacts DIR]
      [--implementation-artifacts DIR]

Exit codes: 0=plan emitted (check .errors), 1=hard failure, 2=runtime error.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

TERMINAL = {"done", "obsolete"}
STATUSES = {"proposed", "backlog", "ready-for-dev", "in-progress", "review",
            "done", "obsolete"}
BUGS_EPIC_RE = re.compile(r"bugs?.*enhance|enhance.*bugs?", re.I)


def sprint_parts(v: str):
    """'Beta-2026.10.20' -> ('Beta', '2026.10.20'); bare version -> ('', v)."""
    m = re.match(r"^([A-Za-z][A-Za-z0-9]*)-(\d[\d.]*)$", v)
    if m:
        return m.group(1), m.group(2).rstrip(".")
    return "", v.rstrip(".")


def core_key(core: str):
    return tuple(int(x) for x in core.split(".") if x.isdigit())


def story_lines(text: str):
    """[(key, epic_n, story_n, slug, status, comment)] from the flat
    development_status block — 2-space `NN-MM-slug: status` entries."""
    out = []
    in_dev = False
    for line in text.splitlines():
        if re.match(r"^development_status:", line):
            in_dev = True
            continue
        if re.match(r"^\S", line):
            in_dev = False
            continue
        if in_dev:
            m = re.match(r"^  (\d+)-(\d+)-([a-z0-9-]+):\s*(\S+)\s*(#.*)?$",
                         line)
            if m:
                out.append({"key": f"{m.group(1)}-{m.group(2)}-{m.group(3)}",
                            "epic": int(m.group(1)),
                            "story": int(m.group(2)),
                            "slug": m.group(3),
                            "status": m.group(4),
                            "comment": m.group(5) or ""})
    return out


def epic_markers(text: str):
    """Ordered epic numbers from `  epic-N:` markers in development_status."""
    return [int(m.group(1)) for line in text.splitlines()
            if (m := re.match(r"^  epic-(\d+):\s*\S", line))]


def spec_status(path: Path):
    """`Status:` value from a spec file's `**Status:** x` line, or None."""
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^\s*\*{0,2}Status:\*{0,2}\s*([a-z-]+)", line)
        if m:
            return m.group(1)
    return None


def bmm_config_dirs(root: Path):
    """implementation/planning artifact dirs + release-train path from
    _bmad/bmm/config.yaml when present (placeholders resolved)."""
    out = {}
    cfg = root / "_bmad" / "bmm" / "config.yaml"
    if cfg.is_file():
        try:
            data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            data = {}
        def resolve(v):
            p = str(v).replace("{project-root}", "").lstrip("/\\")
            return root / p
        for key, name in (("implementation_artifacts", "implementation"),
                          ("planning_artifacts", "planning"),
                          ("release_train", "release_train"),
                          ("release_train_file", "release_train")):
            if data.get(key):
                out[name] = resolve(data[key])
    out.setdefault("implementation",
                   root / "_bmad-output" / "implementation-artifacts")
    out.setdefault("planning", root / "_bmad-output" / "planning-artifacts")
    out.setdefault("release_train", root / "release-train.json")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project-root", required=True, type=Path)
    ap.add_argument("--new-version")
    ap.add_argument("--epic-order", default="preserve",
                    help="'preserve' or comma list of OLD epic numbers "
                         "in desired new order")
    ap.add_argument("--today",
                    default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--release-train", type=Path)
    ap.add_argument("--planning-artifacts", type=Path)
    ap.add_argument("--implementation-artifacts", type=Path)
    args = ap.parse_args()

    root = args.project_root.resolve()
    dirs = bmm_config_dirs(root)
    impl = (args.implementation_artifacts or dirs["implementation"]).resolve()
    plan_dir = (args.planning_artifacts or dirs["planning"]).resolve()
    train_file = (args.release_train or dirs["release_train"]).resolve()

    errors, warnings = [], []

    # ---- old_version: newest version with all three artifacts -----------
    cands = {}
    for f in impl.glob("sprint-status-*.yaml"):
        v = re.search(r"sprint-status-(.+)\.yaml$", f.name).group(1)
        epics = plan_dir / f"epics-beta-{v}.md"
        specs = impl / v
        if epics.is_file() and specs.is_dir():
            cands[v] = {"epics": epics, "sprint": f, "specs": specs}
    if not cands:
        print(json.dumps({"status": "fail", "errors": [
            "no version under implementation-artifacts has all three "
            "artifacts (sprint-status + epics-beta + spec folder)"]}))
        return 1
    old_version = max(cands, key=lambda v: core_key(sprint_parts(v)[1]))
    old = cands[old_version]
    old_channel, old_core = sprint_parts(old_version)

    # ---- release train / skew detection ---------------------------------
    train = {}
    if train_file.is_file():
        try:
            train = json.loads(train_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{train_file.name} does not parse: {e}")
    else:
        warnings.append(f"{train_file} missing — skew detection skipped")
    current = train.get("current") or {}
    channel = current.get("name") or old_channel
    candidate_id = current.get("sprint") or (
        f"{current.get('name')}-{current.get('version')}"
        if current.get("name") and current.get("version") else None)
    cur_core = (current.get("version") or "").rstrip(".")
    deploys = [e.get("version") or e.get("tag")
               for e in (train.get("releases") or train.get("entries") or [])
               if isinstance(e, dict) and e.get("sprint") == old_version]

    if args.new_version:
        new_version, skew = args.new_version, "arg"
    elif cur_core and core_key(cur_core) > core_key(old_core) \
            and candidate_id and candidate_id != old_version:
        new_version, skew = candidate_id, "catch-up"
    elif cur_core and core_key(cur_core) > core_key(old_core) \
            and candidate_id == old_version:
        new_version = f"{channel}-{args.today.replace('-', '.')}"
        skew = "mid-sprint-deploy"
    else:
        new_version = f"{channel}-{args.today.replace('-', '.')}"
        skew = "confirm"
    if sprint_parts(new_version)[1] and \
            core_key(sprint_parts(new_version)[1]) <= core_key(old_core):
        warnings.append(
            f"new_version {new_version} core is not ahead of {old_version}")

    # ---- paths -----------------------------------------------------------
    paths = {
        "old_epics": str(old["epics"]),
        "new_epics": str(plan_dir / f"epics-beta-{new_version}.md"),
        "old_sprint": str(old["sprint"]),
        "new_sprint": str(impl / f"sprint-status-{new_version}.yaml"),
        "old_spec_folder": str(old["specs"]),
        "new_spec_folder": str(impl / new_version),
        "release_train": str(train_file),
    }

    # ---- pre-flight: inputs exist + parse --------------------------------
    sprint_text = old["sprint"].read_text(encoding="utf-8", errors="replace")
    try:
        loaded = yaml.safe_load(sprint_text)
        if not isinstance((loaded or {}).get("development_status"), dict):
            errors.append(f"{old['sprint'].name}: development_status is not "
                          "a mapping")
    except yaml.YAMLError as e:
        errors.append(f"{old['sprint'].name} does not parse as YAML: {e}")
    epics_text = old["epics"].read_text(encoding="utf-8", errors="replace")
    if not re.search(r"^## Epic ", epics_text, re.M):
        warnings.append(f"{old['epics'].name}: no '## Epic' headings found")

    stories = story_lines(sprint_text)
    keys = [s["key"] for s in stories]
    if len(keys) != len(set(keys)):
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        errors.append(f"duplicate story keys in sprint status: {dupes}")
    bad = [s for s in stories if s["status"] not in STATUSES]
    for s in bad:
        errors.append(f"unknown status '{s['status']}' on {s['key']}")

    # ---- partition + specs ----------------------------------------------
    terminal = [s for s in stories if s["status"] in TERMINAL]
    non_terminal = [s for s in stories if s["status"] not in TERMINAL]
    mismatch = []
    for s in stories:
        s["spec"] = (old["specs"] / f"{s['key']}.md").is_file()
        ss = spec_status(old["specs"] / f"{s['key']}.md")
        if s["status"] == "done" and ss and ss != "done":
            mismatch.append({"key": s["key"], "yaml_status": "done",
                             "spec_status": ss})
        if s["status"] not in TERMINAL and not s["spec"]:
            warnings.append(f"{s['key']}: non-terminal story has no spec file")

    # ---- epic order -------------------------------------------------------
    epics_in_yaml = epic_markers(sprint_text)
    epics_migrating = sorted({s["epic"] for s in non_terminal})
    if args.epic_order in ("", "preserve"):
        epic_order = epics_migrating
    else:
        try:
            epic_order = [int(x) for x in args.epic_order.split(",") if x.strip()]
        except ValueError:
            errors.append(f"--epic-order '{args.epic_order}' is not a "
                          "comma list of epic numbers")
            epic_order = []
        if epic_order and sorted(epic_order) != epics_migrating:
            errors.append(
                f"--epic-order {epic_order} does not cover exactly the "
                f"migrating epics {epics_migrating}")

    # ---- renumber map (width preserved from each old key) -----------------
    def new_key(s, ne, ns):
        kd = re.match(r"^(\d+)-(\d+)-", s["key"])
        ew, sw = len(kd.group(1)), len(kd.group(2))
        return f"{ne:0{ew}d}-{ns:0{sw}d}-{s['slug']}"

    renumber = {}
    for pos, oe in enumerate(epic_order, start=1):
        for ns, s in enumerate(
                [x for x in non_terminal if x["epic"] == oe], start=1):
            renumber[s["key"]] = {"key": new_key(s, pos, ns),
                                  "old_num": f"{s['epic']}.{s['story']}",
                                  "new_num": f"{pos}.{ns}"}
    new_keys = [v["key"] for v in renumber.values()]
    if len(new_keys) != len(set(new_keys)):
        errors.append("renumber map produced duplicate target keys")

    # ---- target collision -------------------------------------------------
    if Path(paths["new_epics"]).is_file():
        errors.append(f"target already exists: {paths['new_epics']}")
    if Path(paths["new_sprint"]).is_file():
        errors.append(f"target already exists: {paths['new_sprint']}")
    nsf = Path(paths["new_spec_folder"])
    if nsf.is_dir() and any(nsf.iterdir()):
        errors.append(f"target spec folder exists and is not empty: {nsf}")

    result = {
        "script": "resolve-upgrade",
        "status": "fail" if errors else "pass",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "old_version": old_version,
        "new_version": new_version,
        "channel": channel,
        "skew_case": skew,
        "candidate_sprint_id": candidate_id,
        "deploys_under_old": [d for d in deploys if d],
        "terminal": [{k: s[k] for k in ("key", "status", "spec")}
                     for s in terminal],
        "non_terminal": [{k: s[k] for k in ("key", "status", "spec")}
                         for s in non_terminal],
        "status_mismatch": mismatch,
        "epics_migrating": epics_migrating,
        "epics_staying": [e for e in epics_in_yaml if e not in epics_migrating],
        "epic_order": epic_order,
        "renumber_map": renumber,
        "reclassify": {},
        "counts": {"stories": len(stories), "terminal": len(terminal),
                   "non_terminal": len(non_terminal),
                   "specs": sum(1 for s in non_terminal if s["spec"]),
                   "epics": len(epic_order)},
        "paths": paths,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
