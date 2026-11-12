"""Tests for cdo-setup detect.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "detect.py"


def run_detect(root: Path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root)],
        capture_output=True,
        text=True,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def base_project(root: Path):
    """Minimal gated project: git + real BMAD config."""
    (root / ".git").mkdir()
    (root / "_bmad").mkdir()
    (root / "_bmad" / "config.yaml").write_text(
        "output_folder: x\nbmm:\n  version: 6\n", encoding="utf-8"
    )


class TestDetect(unittest.TestCase):
    def test_empty_project_fails_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = run_detect(Path(tmp))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["gate"], "fail")
            self.assertFalse(data["prerequisites"]["git_repo"])
            self.assertFalse(data["prerequisites"]["bmad_installed"])
            self.assertEqual(data["mode"], "fresh-install")

    def test_detects_git_bmad_and_bun(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_project(root)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"test": "vitest", "build": "vite build"}}),
                encoding="utf-8",
            )
            (root / "bun.lock").write_text("", encoding="utf-8")

            proc, data = run_detect(root)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["gate"], "pass")
            self.assertIn("bmm", data["prerequisites"]["bmad_modules"])
            # scalar root keys are not modules
            self.assertNotIn("output_folder", data["prerequisites"]["bmad_modules"])
            self.assertEqual(data["conventions"]["package_manager"], "bun")
            # health commands resolved through the package manager
            self.assertEqual(data["conventions"]["health_commands"]["test"], "bun run test")
            self.assertEqual(data["conventions"]["health_commands"]["build"], "bun run build")

    def test_prior_install_emits_stored_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_project(root)
            (root / "_bmad" / "config.yaml").write_text(
                "cdo:\n  version: 0.1.0\n  stall_timeout_minutes: '60'\n  custom_lane: blue\n",
                encoding="utf-8",
            )
            proc, data = run_detect(root)
            self.assertEqual(data["mode"], "upgrade")
            self.assertEqual(data["prior_cdo_config"]["stall_timeout_minutes"], "60")
            self.assertEqual(data["prior_cdo_config"]["custom_lane"], "blue")

    def test_orchestration_tree_found_by_signature(self):
        """A custom-dir install with a deleted config section is still detected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_project(root)
            tree = root / "docs" / "ops"
            tree.mkdir(parents=True)
            (tree / "doctrine.md").write_text("x", encoding="utf-8")
            (tree / "flow-ledger.yaml").write_text("x", encoding="utf-8")
            proc, data = run_detect(root)
            self.assertIn("docs/ops", data["orchestration_trees_found"])
            self.assertEqual(data["mode"], "upgrade")

    def test_dept_modules_require_skill_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_project(root)
            skills = root / ".agents" / "skills"
            (skills / "cdo-code-e2e").mkdir(parents=True)
            (skills / "cdo-code-e2e" / "SKILL.md").write_text("x", encoding="utf-8")
            (skills / "cdo-growth").mkdir()
            (skills / "cdo-growth" / "SKILL.md").write_text("x", encoding="utf-8")
            (skills / "cdo-junk").mkdir()  # no SKILL.md — not a real module
            proc, data = run_detect(root)
            self.assertIn("cdo-code-e2e", data["soft_deps"]["owner_skills_present"])
            self.assertIn("cdo-growth", data["soft_deps"]["dept_modules"])
            self.assertNotIn("cdo-junk", data["soft_deps"]["dept_modules"])

    def test_stub_config_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "_bmad").mkdir()
            (root / "_bmad" / "config.yaml").write_text("", encoding="utf-8")
            proc, data = run_detect(root)
            self.assertTrue(data["prerequisites"]["bmad_installed"])
            self.assertTrue(any("stub" in w for w in data["warnings"]))

    def test_stub_config_fails_gate(self):
        """A stub config means BMAD isn't really installed — the gate must
        not pass automation through to a merge that writes onto nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "_bmad").mkdir()
            (root / "_bmad" / "config.yaml").write_text("", encoding="utf-8")
            proc, data = run_detect(root)
            self.assertEqual(data["gate"], "fail")
            self.assertTrue(any("stub" in r for r in data["gate_reasons"]))

    def test_unparseable_config_fails_gate(self):
        """Broken YAML must fail the gate outright — merge-config would
        crash mid-write on it otherwise."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "_bmad").mkdir()
            (root / "_bmad" / "config.yaml").write_text(
                "cdo:\n  bad: [unclosed\n", encoding="utf-8")
            proc, data = run_detect(root)
            self.assertEqual(data["gate"], "fail")
            self.assertTrue(any("parseable" in r for r in data["gate_reasons"]))

    def test_core_keys_reported(self):
        """Existing core keys must surface so propose-config can protect
        them from the default core block."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_project(root)
            (root / "_bmad" / "config.yaml").write_text(
                "user_name: Afiq\noutput_folder: out\nbmm:\n  version: 6\n",
                encoding="utf-8")
            proc, data = run_detect(root)
            self.assertIn("user_name", data["core_keys_present"])
            self.assertIn("output_folder", data["core_keys_present"])

    def test_missing_project_root_errors(self):
        proc, _ = run_detect(Path("/nonexistent-xyz"))
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
