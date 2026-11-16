#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Deterministic story-doc parse for cdo-code-e2e gates and exit checks.

Emits one JSON blob the pipeline consumes at steps 2/3/4/10 instead of
re-reading the whole story file: status, objective, acceptance criteria,
task completion, files mentioned, a UI-surface verdict (advisory), and
whether Dev Notes exist.

Usage: python story-brief.py <story_file>
"""
import argparse
import json
import re
import sys
from pathlib import Path

UI_TERMS = re.compile(
    r"\.vue\b|pages/|components/|layout|route|styling|css|vuetify|template|wireframe",
    re.I)


def section(text: str, title: str) -> str:
    m = re.search(rf"^##\s+{title}\s*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("story_file", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    text = args.story_file.read_text(encoding="utf-8", errors="replace")

    status = re.search(r"^Status:\s*(\S+)", text, re.M)
    title = re.search(r"^#\s+(.+)$", text, re.M)

    # Objective: the Story section, trimmed to its first paragraph/list
    story = section(text, "Story").strip()

    # Acceptance criteria: numbered/bulleted lines in the AC section
    ac_sec = section(text, "Acceptance Criteria")
    acs = [l.strip() for l in ac_sec.splitlines()
           if re.match(r"^\s*(?:\d+\.|[-*]|#{1,3}\s+AC)", l)]

    # Tasks: markdown checkboxes anywhere under Tasks / Subtasks + Review Findings
    task_sec = (section(text, r"(?:Tasks\s*/\s*Subtasks|Tasks)")
                + "\n" + section(text, "Review Findings"))
    open_items = [l.strip() for l in task_sec.splitlines()
                  if re.match(r"^\s*- \[ \]", l)]
    done_count = len(re.findall(r"^\s*- \[[xX]\]", task_sec, re.M))
    open_count = len(open_items)

    # Files mentioned: backticked paths with an extension
    files = sorted(set(
        m.group(1) for m in re.finditer(r"`([\w./-]+\.(?:vue|ts|js|sql|yaml?|css|scss|md))`", text)))

    ui_hits = sorted(set(UI_TERMS.findall(text)))

    result = {
        "script": "story-brief", "version": "1.0.0",
        "story_file": str(args.story_file),
        "title": title.group(1).strip() if title else None,
        "status": status.group(1) if status else None,
        "objective": story,
        "acceptance_criteria": acs,
        "tasks": {"total": done_count + open_count,
                  "done": done_count, "open": open_count,
                  "open_items": open_items},
        "files_mentioned": files,
        "ui_surface": {"verdict": bool(ui_hits), "matched_terms": ui_hits},
        "has_dev_notes": bool(section(text, "Dev Notes").strip()),
    }
    out = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
