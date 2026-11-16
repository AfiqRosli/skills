#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Tests for resolve-context.py."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixture import SCRIPTS, Fixture  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestResolveContext(Fixture):
    def test_release_to_devlog_parts(self):
        rc = load("resolve-context")
        self.assertEqual(rc.release_to_devlog_parts("Beta-2026.09.14.2"), ("Beta", "2026-09-14.2"))
        self.assertEqual(rc.release_to_devlog_parts("Beta-2026.09.14"), ("Beta", "2026-09-14"))

    def test_parse_sprint_status(self):
        rc = load("resolve-context")
        p = self.root / "_bmad-output" / "implementation-artifacts" / "sprint-status-Beta-2026.09.14.2.yaml"
        parsed = rc.parse_sprint_status(p)
        self.assertIn("Beta-2026.09.14.2", parsed["story_location"])
        self.assertEqual(dict(parsed["entries"])["1-2-bar-story"], "backlog")

    def test_resolves_first_backlog_and_devlog_dir(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "resolve-context.py"),
             "--project-root", str(self.root)],
            capture_output=True, text=True)
        data = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(data["story_key"], "1-2-bar-story")
        self.assertEqual(data["story_source"], "backlog")
        # newest sprint picked by release version, not mtime
        self.assertTrue(data["sprint_status"].endswith("Beta-2026.09.14.2.yaml"))
        self.assertTrue(data["devlog_dir"].replace("\\", "/").endswith(
            "docs/orchestration/devlog/Beta/2026-09-14.2/01-02-bar-story"))

    def test_owner_skills_resolve_agents_tree_first(self):
        # .agents/skills is the canonical tree: shared module skills
        # (bmad-*) probe both trees with .agents preferred, but cdo-* org
        # skills resolve ONLY under .agents — a .devin-only cdo-* is the
        # unvendored upstream copy and must probe false (halt), not pass.
        sk = self.root / ".agents" / "skills" / "bmad-create-story"
        sk.mkdir(parents=True)
        (sk / "SKILL.md").write_text("---\nname: bmad-create-story\n---\n",
                                   encoding="utf-8")
        sk2 = self.root / ".devin" / "skills" / "cdo-git-push"
        sk2.mkdir(parents=True)
        (sk2 / "SKILL.md").write_text("---\nname: cdo-git-push\n---\n",
                                    encoding="utf-8")
        sk3 = self.root / ".devin" / "skills" / "bmad-dev-story"
        sk3.mkdir(parents=True)
        (sk3 / "SKILL.md").write_text("---\nname: bmad-dev-story\n---\n",
                                    encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "resolve-context.py"),
             "--project-root", str(self.root)],
            capture_output=True, text=True)
        data = json.loads(proc.stdout)
        owners = data["preflight"]["owner_skills"]
        self.assertTrue(owners["bmad-create-story"])   # found in .agents
        self.assertTrue(owners["bmad-dev-story"])      # .devin fallback ok for non-cdo
        self.assertFalse(owners["cdo-git-push"])       # cdo-* needs .agents, not .devin
        self.assertFalse(owners["cdo-git-quick-push"]) # absent in both
        self.assertIn("conditional_skills", data["preflight"])
        self.assertIn("cdo-version-change-for-production",
                      data["preflight"]["conditional_skills"])
        self.assertIn("fork_drift", data["preflight"])

    def test_invalid_story_and_from_flag(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "resolve-context.py"),
             "--project-root", str(self.root), "--story", "9-9-nope", "--from", "bogus"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        data = json.loads(proc.stdout)
        self.assertTrue(any("9-9-nope" in e for e in data["errors"]))
        self.assertTrue(any("bogus" in e for e in data["errors"]))

    def test_resume_from_devlog(self):
        devlog = self.root / "docs" / "orchestration" / "devlog" / "Beta" / "2026-09-14.2" / "1-1-foo-story"
        devlog.mkdir(parents=True)
        (devlog / "index.md").write_text(
            "---\npipeline:\n  story_key: \"1-1-foo-story\"\n  release: \"Beta-2026.09.14.2\"\n"
            "  steps:\n    create-story: done\n    wireframe: pending\n---\n# log\n",
            encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "resolve-context.py"),
             "--project-root", str(self.root)],
            capture_output=True, text=True)
        data = json.loads(proc.stdout)
        self.assertEqual(data["story_key"], "1-1-foo-story")
        self.assertEqual(data["story_source"], "resume")
        self.assertEqual(data["resume"]["next_step"], "wireframe")


if __name__ == "__main__":
    import unittest
    unittest.main()
