"""Shared fixture for cdo-version-upgrade tests — a two-epic sprint with
terminal + non-terminal stories, specs, epics doc, and release train."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent

OLD_V = "Beta-2026.10.20"
NEW_V = "Beta-2026.11.01"

SPRINT = f"""# sprint-status-{OLD_V}.yaml
generated: 2026-10-20
project: fixture
story_location: _bmad-output/implementation-artifacts/{OLD_V}
last_updated: 2026-10-25
development_status:
  # Epic 1 — Platform
  epic-1: in-progress
  1-1-alpha-thing: done
  1-2-beta-work: in-progress  # carrying over
  epic-1-retrospective: pending
  epic-2: backlog
  2-1-gamma-feature: review
  2-2-delta-job: backlog
  epic-9: backlog
  9-1-bug-fix-one: backlog
"""

EPICS = f"""---
beta: {OLD_V}
title: Beta Epics
---
# Epics — Beta Release 2026.10.20

## Epic 1: Platform Work (Core)

Preamble for epic 1.

### Story 1.1: Alpha thing (Optional)

Body of story 1.1 — shipped.

### Story 1.2: Beta work

Body of 1.2, references Story 1.1 upstream.

---

## Epic 2: Feature Work

Preamble for epic 2.

### Story 2.1: Gamma feature (Admin)

Body 2.1.

### Story 2.2: Delta job

Body 2.2.

---

## Epic 9: Bugs & Enhancement

Catch-all epic.

### Story 9.1: Bug fix one

Body 9.1.
"""

TRAIN = {
    "current": {"name": "Beta", "version": "2026.10.25", "sprint": OLD_V},
    "releases": [{"version": "2026.10.25", "sprint": OLD_V,
                  "tag": "v2026.10.25"}],
}

SPECS = {
    "1-1-alpha-thing": ("1.1", "Alpha thing", "done"),
    "1-2-beta-work": ("1.2", "Beta work", "backlog"),
    "2-1-gamma-feature": ("2.1", "Gamma feature", "backlog"),
    "2-2-delta-job": ("2.2", "Delta job", "backlog"),
    "9-1-bug-fix-one": ("9.1", "Bug fix one", "backlog"),
}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        impl = self.root / "_bmad-output" / "implementation-artifacts"
        plan = self.root / "_bmad-output" / "planning-artifacts"
        (impl / OLD_V).mkdir(parents=True)
        plan.mkdir(parents=True)
        (self.root / "release-train.json").write_text(
            json.dumps(TRAIN), encoding="utf-8")
        (impl / f"sprint-status-{OLD_V}.yaml").write_text(
            SPRINT, encoding="utf-8")
        (plan / f"epics-beta-{OLD_V}.md").write_text(EPICS, encoding="utf-8")
        for key, (num, title, status) in SPECS.items():
            (impl / OLD_V / f"{key}.md").write_text(
                f"# Story {num}: {title}\n\n**Status:** {status}\n\n"
                f"Spec body for {key}. See epics-beta-{OLD_V}.md#Story {num}.\n",
                encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, name, *cli, stdin=None):
        # `uv run` resolves each script's PEP723 deps (pyyaml) — needed
        # because tests themselves run under uv's ephemeral interpreter.
        return subprocess.run(
            ["uv", "run", str(SCRIPTS / name), *cli],
            input=stdin, capture_output=True, text=True)

    def resolve(self, *extra):
        proc = self.run_script(
            "resolve-upgrade.py", "--project-root", str(self.root),
            "--new-version", NEW_V, *extra)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def write_plan(self, plan):
        p = self.root / "plan.json"
        p.write_text(json.dumps(plan), encoding="utf-8")
        return p
