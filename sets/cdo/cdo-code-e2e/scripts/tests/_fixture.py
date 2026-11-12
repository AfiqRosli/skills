"""Shared fixture for cdo-code-e2e script tests — builds a minimal project tree."""
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent

SPRINT = """# generated: 2026-09-16T00:00:00.000Z
project: demo-app
story_location: _bmad-output/implementation-artifacts/Beta-2026.09.14.2
last_updated: 2026-09-15

development_status:
  epic-1: in-progress
  1-1-foo-story: review                        # was 1-1 in Beta-2026.09.10 -- notes
  1-2-bar-story: backlog                       # NEW -- second story
"""


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "_bmad" / "core").mkdir(parents=True)
        (self.root / "_bmad" / "bmm").mkdir(parents=True)
        (self.root / "_bmad" / "core" / "config.yaml").write_text(
            'user_name: Afiq\ncommunication_language: English\ndocument_output_language: English\n',
            encoding="utf-8")
        (self.root / "_bmad" / "bmm" / "config.yaml").write_text(
            'implementation_artifacts: "{project-root}/_bmad-output/implementation-artifacts"\n'
            'project_knowledge: "{project-root}/docs"\n', encoding="utf-8")
        impl = self.root / "_bmad-output" / "implementation-artifacts"
        (impl / "Beta-2026.09.14.2").mkdir(parents=True)
        (impl / "sprint-status-Beta-2026.09.14.2.yaml").write_text(SPRINT, encoding="utf-8")
        (impl / "sprint-status-Beta-2026.09.10.yaml").write_text(SPRINT.replace("14.2", "10"),
                                                               encoding="utf-8")
        (impl / "Beta-2026.09.14.2" / "1-2-bar-story.md").write_text(
            "# Story 1-2\n\nStatus: ready-for-dev\n\n## Change Log\n\n- 2026-09-16: created\n",
            encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()
