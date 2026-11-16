#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for resolve-upgrade.py — version-pair resolution, partition,
pre-flight validation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixture import OLD_V, NEW_V, Fixture  # noqa: E402


class TestResolveUpgrade(Fixture):
    def test_partition_and_renumber(self):
        plan = self.resolve()
        self.assertEqual(plan["old_version"], OLD_V)
        self.assertEqual(plan["new_version"], NEW_V)
        self.assertEqual(plan["skew_case"], "arg")
        self.assertEqual([s["key"] for s in plan["terminal"]],
                         ["1-1-alpha-thing"])
        self.assertEqual(len(plan["non_terminal"]), 4)
        # compaction: 1-2 -> 1-1; epic 9 -> position 3
        self.assertEqual(plan["renumber_map"]["1-2-beta-work"]["key"],
                         "1-1-beta-work")
        self.assertEqual(plan["renumber_map"]["9-1-bug-fix-one"]["key"],
                         "3-1-bug-fix-one")

    def test_mid_sprint_deploy_detected(self):
        plan = self.run_script(
            "resolve-upgrade.py", "--project-root", str(self.root))
        import json
        data = json.loads(plan.stdout)
        # current.sprint == old_version -> current is a deploy tag, not a
        # sprint target; suggested new version is channel + today's date
        self.assertEqual(data["skew_case"], "mid-sprint-deploy")
        self.assertTrue(data["new_version"].startswith("Beta-2"))
        self.assertEqual(data["deploys_under_old"], ["2026.10.25"])

    def test_catch_up_when_current_names_other_sprint(self):
        import json as j
        train = j.loads((self.root / "release-train.json").read_text())
        train["current"] = {"name": "Beta", "version": "2026.11.01",
                            "sprint": NEW_V}
        (self.root / "release-train.json").write_text(j.dumps(train))
        plan = self.run_script("resolve-upgrade.py", "--project-root",
                               str(self.root))
        data = j.loads(plan.stdout)
        self.assertEqual(data["skew_case"], "catch-up")
        self.assertEqual(data["new_version"], NEW_V)

    def test_epic_order_validation(self):
        proc = self.run_script(
            "resolve-upgrade.py", "--project-root", str(self.root),
            "--new-version", NEW_V, "--epic-order", "2,1")
        import json
        data = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any("epic" in e for e in data["errors"]))

    def test_target_collision_flagged(self):
        impl = self.root / "_bmad-output" / "implementation-artifacts"
        (impl / f"sprint-status-{NEW_V}.yaml").write_text("x: 1\n")
        proc = self.run_script(
            "resolve-upgrade.py", "--project-root", str(self.root),
            "--new-version", NEW_V)
        import json
        data = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any("already exists" in e for e in data["errors"]))


if __name__ == "__main__":
    import unittest
    unittest.main()
