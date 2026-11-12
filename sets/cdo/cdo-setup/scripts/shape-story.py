#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""shape-story.py — the intake-shape four-write, scripted.

A shaped code item is born with all four artifacts or none:

  1. sprint yaml   — `{NN-MM-slug}: proposed` inserted under its epic-N
                     marker (the FALLIBLE write — runs first; a missing
                     epic block refuses before any file exists)
  2. story file    — {story_location}/{key}.md skeleton, Status: proposed
  3. epics doc     — `### Story {N}.{M}:` section appended when absent
  4. backlog line  — `- [ ] {key} — {title} | approach: … | touches: … |
                     size: …` appended via backlog-add.py (single writer)

`proposed` is the shaped-but-unaligned state: the Operator confirm flips it
to `backlog` (apply-decisions.py), reject flips it to `obsolete`.

`--split-from {parent}` is the split path — same four writes for the child,
plus lineage both ways: the child's yaml entry / story skeleton / epics
section carry `split from {parent}`, and the parent's yaml line and epics
`### Story` section get annotated `split → {child}`. The parent key must
already exist in the sprint yaml. `--deps` defaults to the parent when
unset. Run once per child when a story fans out into siblings.

"Current sprint" = the newest sprint-status-*.yaml by release-date suffix —
never release-train.json (its current.sprint lags). Story dir comes from
the yaml's `story_location`, else the release-named sibling dir.

Usage:
  uv run shape-story.py --project-root /path --orchestration-dir /path/docs/orchestration \
      --title "Unify db layer" [--epic 13] [--approach "..."] [--touches "..."] \
      [--size lite|full] [--deps "..."] [--backlog code] \
      [--split-from NN-MM-parent-slug] [--dry-run] [-o result.json]

Exit codes: 0=shaped, 1=refused (bad args / epic block missing / dup key),
2=runtime error
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ------------------------------------------------------------------ helpers
# (vendored from migrate-sprint-keys.py — same mint semantics, same parsers)

def slugify(text: str, max_words: int = 8) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    parts = s.split("-")
    return "-".join(parts[:max_words]) if len(parts) > max_words else s


def mint_slug(title: str, max_words: int = 6) -> str:
    seg = re.split(r"[:—(]", title)[0].strip()
    cand = seg if len(slugify(seg).split("-")) >= 2 else title
    return slugify(cand, max_words)


def newest_sprint_yaml(project_root: Path):
    impl = project_root / "_bmad-output" / "implementation-artifacts"
    cands = sorted(impl.glob("sprint-status-*.yaml"))
    if not cands:
        return None
    def key(p):
        m = re.search(r"sprint-status-(.+)\.yaml$", p.name)
        parts = re.split(r"[.\-]", m.group(1)) if m else []
        return [int(x) if x.isdigit() else 0 for x in parts]
    return max(cands, key=key)


def yaml_story_keys(text: str) -> dict:
    keys = {}
    in_dev = False
    for line in text.splitlines():
        if re.match(r"^development_status:", line):
            in_dev = True
            continue
        if re.match(r"^\S", line):
            in_dev = False
            continue
        if in_dev:
            km = re.match(r"^  (\d{2}-\d{2}-\S+):\s*([^#\n]*)", line)
            if km:
                keys[km.group(1)] = km.group(2).strip()
    return keys


def insert_yaml_entry(text: str, epic: int, key: str, status: str) -> str:
    """`  {key}: {status}` after the epic-N marker, ordered by story number —
    empty string when the epic block doesn't exist (the refusal signal)."""
    kn = re.match(r"(\d+)-(\d+)", key)
    if not kn:
        return ""
    n_epic, n_story = int(kn.group(1)), int(kn.group(2))
    lines = text.splitlines()
    epic_line = None
    for i, line in enumerate(lines):
        if re.match(rf"^  epic-{epic}:\s", line):
            epic_line = i
            break
    if epic_line is None:
        return ""
    insert_at = None
    for i in range(epic_line + 1, len(lines)):
        km = re.match(rf"^  {n_epic}-(\d+)-\S+:", lines[i])
        if km:
            if int(km.group(1)) > n_story:
                insert_at = i
                break
            continue
        if re.match(r"^  \S", lines[i]):
            insert_at = i
            break
    if insert_at is None:
        insert_at = len(lines)
    lines.insert(insert_at, f"  {key}: {status}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def epics_section_present(epics_text: str, nn: int, mm: int) -> bool:
    return bool(re.search(rf"^### Story {nn}\.{mm}:", epics_text, re.M))


def annotate_parent_yaml(text: str, parent: str, child: str, date: str) -> str:
    """Append `split → {child}` to the parent's sprint-yaml line."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"^  {re.escape(parent)}:\s", line):
            if child in line:
                return text
            lines[i] = line.rstrip() + (
                f" | split → {child} {date}" if "#" in line
                else f" # split → {child} {date}")
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    return text


def annotate_parent_epics(text: str, parent: str, child: str,
                          date: str) -> str:
    """Append a `- Split: {child}` line at the end of the parent's
    `### Story N.M:` section (before the next heading or EOF)."""
    pm = re.match(r"^(\d+)-(\d+)-", parent)
    if not pm:
        return text
    pn, pmn = int(pm.group(1)), int(pm.group(2))
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^### Story {pn}\.{pmn}:", line):
            start = i
            break
    if start is None:
        return text
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^#{1,3} ", lines[i]):
            end = i
            break
    if any(child in line for line in lines[start:end]):
        return text
    j = end
    while j > start + 1 and not lines[j - 1].strip():
        j -= 1
    lines.insert(j, f"- Split: {child} carved out {date}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


STORY_SKELETON = """# Story {nn}.{mm}: {title}

**Status:** proposed

## Story

As an operator/user, I want {title}, so that the item's acceptance
criteria in the shaped spec hold.

## Acceptance Criteria

- TBD — alignment resolves; `cdo-code-e2e` step 1 (create-story) enriches
  when the produce leg runs

## Tasks / Subtasks

- [ ] TBD — `cdo-code-e2e` step 1 decomposes when the produce leg runs

## Dev Notes

- CDO-shaped item — seeded from the approach sketch + AC hints; the full
  spec lands at alignment.
- Shaped {date} by the intake-shape capability.{split_line}

## Shaped Spec

{spec}
"""


# -------------------------------------------------------------------- main

def parse_args():
    p = argparse.ArgumentParser(description="Shape a backlog ask into the "
                                          "four sprint artifacts.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--epic", type=int, default=None,
                   help="epic number (default: title's `NN-` prefix, else 13 "
                        "— the eng-hygiene catch-all)")
    p.add_argument("--key", default="",
                   help="explicit NN-MM-slug — skips minting entirely")
    p.add_argument("--approach", default="")
    p.add_argument("--touches", default="")
    p.add_argument("--size", default="lite", choices=["lite", "full"])
    p.add_argument("--deps", default="")
    p.add_argument("--backlog", default="code")
    p.add_argument("--split-from", default="",
                   help="parent story key — the child gets the same four "
                        "writes plus split lineage, and the parent's yaml "
                        "line + epics section get annotated. --deps defaults "
                        "to the parent when unset")
    p.add_argument("--spec", default="",
                   help="shaped-spec body for the story file / epics section "
                        "(default: approach field)")
    p.add_argument("--dry-run", action="store_true")
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
    orch = Path(args.orchestration_dir).resolve()
    if not root.is_dir() or not orch.is_dir():
        emit({"errors": ["--project-root and --orchestration-dir must exist"]},
             2, args.output)

    sprint_yaml = newest_sprint_yaml(root)
    if sprint_yaml is None:
        emit({"errors": ["no sprint-status-*.yaml under "
                         "_bmad-output/implementation-artifacts"]},
             1, args.output)
    release = re.search(r"sprint-status-(.+)\.yaml$", sprint_yaml.name).group(1)
    sprint_text = sprint_yaml.read_text(encoding="utf-8")
    yaml_keys = yaml_story_keys(sprint_text)

    # --- key -------------------------------------------------------------
    if args.key:
        if not re.match(r"^\d{2}-\d{2}-[a-z0-9-]+$", args.key):
            emit({"errors": [f"--key {args.key} isn't an NN-MM-slug sprint "
                             "key"]}, 1, args.output)
        key = args.key
        epic_no = int(key.split("-")[0])
    else:
        pm = re.match(r"^(\d{1,2})-\s", args.title) or \
            re.match(r"^(\d{1,2})-(\d{1,2})\s", args.title)
        epic_no = args.epic or (int(pm.group(1)) if pm else 13)
        title_clean = re.sub(r"^\d{1,2}(-\d{1,2})?\s*[-—]?\s*", "",
                             args.title).strip() or args.title
        used = [int(re.match(rf"{epic_no:02d}-(\d+)-", k).group(1))
                for k in yaml_keys if re.match(rf"{epic_no:02d}-\d+-", k)]
        mm = max(used + [0]) + 1
        key = f"{epic_no:02d}-{mm:02d}-{mint_slug(title_clean)}"
    if key in yaml_keys:
        emit({"errors": [f"{key} already exists in {sprint_yaml.name} — "
                         "don't re-shape; update the backlog line"]},
             1, args.output)
    km = re.match(r"(\d+)-(\d+)-", key)
    nn, mm = int(km.group(1)), int(km.group(2))
    epic_no = epic_no or nn
    title_clean = re.sub(r"^\d{1,2}(-\d{1,2})?\s*[-—]?\s*", "",
                         args.title).strip() or args.title

    # --- split lineage -----------------------------------------------------
    parent = args.split_from
    if parent:
        if parent == key:
            emit({"errors": ["--split-from can't be the key being minted"]},
                 1, args.output)
        if parent not in yaml_keys:
            emit({"errors": [f"parent {parent} not in {sprint_yaml.name} — "
                             "split needs a real sibling; nothing was "
                             "written"]}, 1, args.output)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    deps = args.deps or parent

    # --- 1. sprint yaml FIRST — the fallible write ------------------------
    status = (f"proposed # NEW {today} — split from {parent}" if parent
              else "proposed")
    new_text = insert_yaml_entry(sprint_text, epic_no, key, status)
    if not new_text:
        emit({"errors": [f"no `epic-{epic_no}:` block in {sprint_yaml.name} — "
                         "the epic must exist before a story can shape "
                         "under it; nothing was written"]}, 1, args.output)
    if parent:
        new_text = annotate_parent_yaml(new_text, parent, key, today)

    # --- resolve the sibling paths ----------------------------------------
    sm = re.search(r"^story_location:\s*(.+)$", sprint_text, re.M)
    story_loc = (root / sm.group(1).strip().strip("'\"").replace(
        "{project-root}", "").lstrip("/\\")) if sm else \
        root / "_bmad-output" / "implementation-artifacts" / release
    epics_path = root / "_bmad-output" / "planning-artifacts" / \
        f"epics-beta-{release}.md"

    spec = args.spec or args.approach or \
        "_no shaped spec recorded — alignment resolves_"
    split_line = (f"\n- Split from `{parent}` — sibling carved out {today}; "
                  "the parent keeps its reduced scope." if parent else "")
    story_body = STORY_SKELETON.format(nn=nn, mm=mm, title=title_clean,
                                     spec=spec, date=today,
                                     split_line=split_line)

    split_tag = f", split from {parent}" if parent else ""
    epics_sect = (f"\n### Story {nn}.{mm}: {title_clean} "
                  f"(NEW {today}, CDO-shaped{split_tag})\n\n"
                  f"**Story:** As an operator/user, I want {title_clean}.\n\n"
                  f"**Description:** {spec}\n\n"
                  f"**AC:** TBD — alignment resolves; story file carries the "
                  f"working spec.\n")

    fields = []
    if args.approach:
        fields.append(("approach", args.approach))
    if args.touches:
        fields.append(("touches", args.touches))
    fields.append(("size", args.size))
    if deps:
        fields.append(("deps", deps))

    plan = {
        "key": key, "release": release, "sprint_yaml": str(sprint_yaml),
        "story_file": str(story_loc / f"{key}.md"),
        "epics_doc": str(epics_path),
        "epics_section_exists": epics_section_present(
            epics_path.read_text(encoding="utf-8")
            if epics_path.is_file() else "", nn, mm),
        "backlog": args.backlog,
        "backlog_line": f"- [ ] {key} — {title_clean}"
                        + "".join(f" | {n}: {v}" for n, v in fields),
    }
    if parent:
        plan["split_from"] = parent
        plan["parent_annotated"] = {"sprint_yaml": True,
                                    "epics_doc": epics_path.is_file()}
    if args.dry_run:
        emit({"status": "dry-run", **plan}, 0, args.output)

    # write 1 — the yaml (fail before files exist)
    sprint_yaml.write_text(new_text, encoding="utf-8")

    # write 2 — the story file
    sfile = story_loc / f"{key}.md"
    sfile.parent.mkdir(parents=True, exist_ok=True)
    if not sfile.is_file():
        sfile.write_text(story_body, encoding="utf-8")

    # write 3 — the epics section (only when absent) + parent's split note
    if epics_path.is_file():
        epics_text = epics_path.read_text(encoding="utf-8")
        if not epics_section_present(epics_text, nn, mm):
            epics_text = epics_text.rstrip() + "\n" + epics_sect
        if parent:
            epics_text = annotate_parent_epics(epics_text, parent, key,
                                               today)
        epics_path.write_text(epics_text, encoding="utf-8")

    # write 4 — the backlog line via backlog-add (single writer, dedupes)
    add = Path(__file__).parent / "backlog-add.py"
    cmd = [sys.executable, str(add), "--orchestration-dir", str(orch),
           "--backlog", args.backlog, "--key", key, "--title", title_clean]
    for n, v in fields:
        cmd += ["--field", f"{n}={v}"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        emit({"errors": ["yaml + story + epics written but the backlog "
                         "write failed — fix backlog-add's complaint, don't "
                         "re-run shape (the key now exists)",
                         proc.stdout.strip() or proc.stderr.strip()]},
             2, args.output)

    emit({"status": "shaped", **plan}, 0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
