#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""verify-migration.py — post-migration verification for cdo-version-upgrade.

Runs the step-8 checklist as deterministic pass/fail checks and emits
{check, pass, details} JSON — the prompt renders the report from it instead
of eyeballing counts. Safe to run standalone or right after
partition-renumber.py --apply.

Checks (mirrors references/workflow.md step 8):
  1  story count in new epics == story lines in new sprint yaml
  2  story number sets identical across both new files, no duplicates
  3  epic counts match; Bugs & Enhancement epic is last in both files
  4  every new spec header matches its filename + carries (was N.M in {old})
  5  old spec folder holds only terminal-story spec files
  6  old epics/yaml hold only terminal stories (+ move comments)
  7  every new heading/line carries `was` traceability to {old_version}
  8  old files still parse; nothing outside _bmad-output touched (git
     check, best effort — skipped cleanly when not a repo)

Usage:
  uv run verify-migration.py --old-version V --new-version V
      [--project-root PATH] [--planning-artifacts DIR]
      [--implementation-artifacts DIR]

Exit codes: 0=all checks pass, 1=one or more failures, 2=runtime error.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

TERMINAL = {"done", "obsolete"}
EPIC_RE = re.compile(r"^## Epic (\d+)[:\s]", re.M)
STORY_RE = re.compile(r"^### Story (\d+)\.(\d+):", re.M)
BUGS_EPIC_RE = re.compile(r"bugs?.*enhance|enhance.*bugs?", re.I)
KEY_RE = re.compile(r"^(\d+)-(\d+)-[a-z0-9-]+$")


def sprint_entries(text: str):
    """(story_lines, epic_markers) inside the development_status block."""
    stories, epics = [], []
    in_dev = False
    for line in text.splitlines():
        if re.match(r"^development_status:", line):
            in_dev = True
            continue
        if re.match(r"^\S", line):
            in_dev = False
            continue
        if not in_dev:
            continue
        sm = re.match(r"^  (\d+)-(\d+)-([a-z0-9-]+):\s*(\S+)", line)
        em = re.match(r"^  epic-(\d+)(-retrospective)?:", line)
        if sm:
            stories.append({"key": f"{sm.group(1)}-{sm.group(2)}-{sm.group(3)}",
                            "epic": int(sm.group(1)),
                            "story": int(sm.group(2)),
                            "status": sm.group(4), "line": line})
        elif em and not em.group(2):
            epics.append(int(em.group(1)))
    return stories, epics


def check(name, ok, details):
    return {"check": name, "pass": bool(ok), "details": details}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--old-version", required=True)
    ap.add_argument("--new-version", required=True)
    ap.add_argument("--project-root", type=Path)
    ap.add_argument("--planning-artifacts", type=Path)
    ap.add_argument("--implementation-artifacts", type=Path)
    args = ap.parse_args()

    root = (args.project_root or Path.cwd()).resolve()
    impl = (args.implementation_artifacts
            or root / "_bmad-output" / "implementation-artifacts").resolve()
    plan_dir = (args.planning_artifacts
                or root / "_bmad-output" / "planning-artifacts").resolve()
    ov, nv = args.old_version, args.new_version

    p = {"new_epics": plan_dir / f"epics-beta-{nv}.md",
         "new_sprint": impl / f"sprint-status-{nv}.yaml",
         "new_specs": impl / nv,
         "old_epics": plan_dir / f"epics-beta-{ov}.md",
         "old_sprint": impl / f"sprint-status-{ov}.yaml",
         "old_specs": impl / ov}
    checks = []
    for k, f in p.items():
        ok = f.is_dir() if k.endswith("specs") else f.is_file()
        checks.append(check(f"exists:{k}", ok, str(f)))
    if not all(c["pass"] for c in checks):
        print(json.dumps({"script": "verify-migration", "status": "fail",
                          "checks": checks}, indent=2))
        return 1

    ne_txt = p["new_epics"].read_text(encoding="utf-8", errors="replace")
    ns_txt = p["new_sprint"].read_text(encoding="utf-8", errors="replace")
    oe_txt = p["old_epics"].read_text(encoding="utf-8", errors="replace")
    os_txt = p["old_sprint"].read_text(encoding="utf-8", errors="replace")

    ne_stories = STORY_RE.findall(ne_txt)
    ne_epics = EPIC_RE.findall(ne_txt)
    ns_stories, ns_epics = sprint_entries(ns_txt)
    os_stories, _ = sprint_entries(os_txt)
    oe_stories = STORY_RE.findall(oe_txt)

    # 1-2 counts + sets ------------------------------------------------------
    checks.append(check(
        "story-count-equal",
        len(ne_stories) == len(ns_stories),
        f"new epics {len(ne_stories)} vs new sprint {len(ns_stories)}"))
    ne_nums = [(int(a), int(b)) for a, b in ne_stories]
    ns_nums = [(s["epic"], s["story"]) for s in ns_stories]
    dupes = len(ne_nums) != len(set(ne_nums)) or \
        len(ns_nums) != len(set(ns_nums))
    checks.append(check(
        "story-sets-identical",
        sorted(ne_nums) == sorted(ns_nums) and not dupes,
        f"epics {sorted(ne_nums)[:8]}… vs yaml {sorted(ns_nums)[:8]}…"
        + (" (DUPLICATES FOUND)" if dupes else "")))

    # 3 epic counts + B&E last ------------------------------------------------
    be_last_epics = bool(ne_epics) and bool(
        BUGS_EPIC_RE.search(
            [l for l in ne_txt.splitlines() if EPIC_RE.match(l)][-1]))
    be_last_yaml = bool(ns_epics) and bool(
        BUGS_EPIC_RE.search(
            [l for l in ne_txt.splitlines()
             if EPIC_RE.match(l) and int(EPIC_RE.match(l).group(1))
             == ns_epics[-1]][0] if ne_epics else ""))
    checks.append(check(
        "epics-match-and-be-last",
        len(ne_epics) == len(ns_epics) and be_last_epics and be_last_yaml,
        f"epics {len(ne_epics)} vs {len(ns_epics)}; "
        f"B&E last: epics={be_last_epics} yaml={be_last_yaml}"))

    # 4 spec headers ----------------------------------------------------------
    spec_bad = []
    spec_files = sorted(p["new_specs"].glob("*.md"))
    for f in spec_files:
        km = KEY_RE.match(f.stem)
        head = f.read_text(encoding="utf-8", errors="replace")[:3000]
        hm = re.search(r"^# Story (\d+)\.(\d+):[^\n]*", head, re.M)
        if not km or not hm:
            spec_bad.append(f"{f.name}: no key/header match")
            continue
        if (int(km.group(1)), int(km.group(2))) != \
                (int(hm.group(1)), int(hm.group(2))):
            spec_bad.append(f"{f.name}: header {hm.group(1)}.{hm.group(2)}")
        if ov not in hm.group(0):
            spec_bad.append(f"{f.name}: no (was … in {ov}) traceability")
    checks.append(check("spec-headers-traceable", not spec_bad,
                        "; ".join(spec_bad) or
                        f"{len(spec_files)} spec files OK"))

    # 5 old spec folder = terminal only --------------------------------------
    old_terminal = {s["key"] for s in os_stories if s["status"] in TERMINAL}
    stray = [f.name for f in p["old_specs"].glob("*.md")
             if KEY_RE.match(f.stem) and f.stem not in old_terminal]
    checks.append(check("old-specs-terminal-only", not stray,
                        "non-terminal specs left behind: " + ", ".join(stray)
                        if stray else f"{len(old_terminal)} terminal specs"))

    # 6 old files hold only terminal entries ----------------------------------
    oe_nonterm = [f"{a}.{b}" for a, b in oe_stories
                  if (int(a), int(b)) not in
                  {(int(re.match(r'(\d+)-', k).group(1)),
                    int(re.match(r'\d+-(\d+)-', k).group(1)))
                   for k in old_terminal}]
    os_nonterm = [s["key"] for s in os_stories
                  if s["status"] not in TERMINAL]
    moved_ok = all(
        re.match(r"^  # \d+-\d+-[a-z0-9-]+: \S+ -> moved", l)
        for l in os_txt.splitlines()
        if re.match(r"^  # \d+-\d+", l))
    checks.append(check(
        "old-files-terminal-only",
        not oe_nonterm and not os_nonterm and moved_ok,
        f"epics stray {oe_nonterm[:5]}; yaml stray {os_nonterm[:5]}; "
        f"move comments well-formed={moved_ok}"))

    # 7 was-traceability on every new heading/line ----------------------------
    no_was = [f"{a}.{b}" for a, b in ne_stories
              if ov not in "".join(
                  [l for l in ne_txt.splitlines()
                   if l.startswith(f"### Story {a}.{b}:")])]
    no_was += [s["key"] for s in ns_stories if f"was " not in s["line"]
               or ov not in s["line"]]
    checks.append(check("was-traceability", not no_was,
                        "missing was-chain: " + ", ".join(no_was[:8])
                        if no_was else "all migrated entries traceable"))

    # 8 parse + containment ----------------------------------------------------
    errs = []
    for f in (p["old_sprint"], p["new_sprint"]):
        try:
            yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            errs.append(f"{f.name}: {e}")
    for f, need in ((p["old_epics"], "-- ARCHIVED"),
                    (p["new_epics"], "## Epic")):
        if need not in f.read_text(encoding="utf-8", errors="replace"):
            errs.append(f"{f.name}: missing '{need}'")
    try:
        r = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            outside = [l[3:] for l in r.stdout.splitlines()
                       if l.strip() and "_bmad-output" not in l[3:]
                       and not l[3:].startswith(("docs/orchestration",))]
            if outside:
                errs.append("touched outside _bmad-output: "
                            + ", ".join(outside[:8]))
    except (OSError, subprocess.TimeoutExpired):
        pass
    checks.append(check("parse-and-containment", not errs,
                        "; ".join(errs) or "files parse, changes contained"))

    failed = [c for c in checks if not c["pass"]]
    print(json.dumps({"script": "verify-migration",
                      "status": "fail" if failed else "pass",
                      "old_version": ov, "new_version": nv,
                      "checks": checks,
                      "failed": len(failed)}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
