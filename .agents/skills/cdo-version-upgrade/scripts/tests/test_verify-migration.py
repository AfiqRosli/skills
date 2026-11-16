#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for verify-migration.py — the post-migration checklist."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixture import OLD_V, NEW_V, Fixture  # noqa: E402


class TestVerifyMigration(Fixture):
    def migrate(self):
        plan = self.resolve()
        p = self.write_plan(plan)
        proc = self.run_script("partition-renumber.py", "--plan", str(p),
                               "--apply")
        self.assertEqual(json.loads(proc.stdout)["status"], "pass")

    def verify(self):
        return self.run_script(
            "verify-migration.py", "--old-version", OLD_V,
            "--new-version", NEW_V, "--project-root", str(self.root))

    def test_clean_migration_passes(self):
        self.migrate()
        proc = self.verify()
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "pass",
                         [c for c in data["checks"] if not c["pass"]])

    def test_detects_dropped_story(self):
        self.migrate()
        impl = self.root / "_bmad-output" / "implementation-artifacts"
        # delete a migrated spec + its sprint line -> count/sets mismatch
        (impl / NEW_V / "1-1-beta-work.md").unlink()
        txt = (impl / f"sprint-status-{NEW_V}.yaml").read_text()
        txt = txt.replace("  1-1-beta-work: in-progress"
                          f"  # was 1.2 in {OLD_V}, carrying over\n", "")
        (impl / f"sprint-status-{NEW_V}.yaml").write_text(txt)
        proc = self.verify()
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "fail")
        self.assertGreater(data["failed"], 0)

    def test_detects_untouched_old_spec(self):
        self.migrate()
        impl = self.root / "_bmad-output" / "implementation-artifacts"
        # sneak a non-terminal spec back into the old folder
        (impl / OLD_V / "2-2-delta-job.md").write_text("# stray\n")
        proc = self.verify()
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "fail")
        checks = {c["check"]: c["pass"] for c in data["checks"]}
        self.assertFalse(checks["old-specs-terminal-only"])


if __name__ == "__main__":
    import unittest
    unittest.main()
