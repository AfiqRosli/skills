"""Smoke tests for merge-config.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "merge-config.py"
MODULE_YAML = Path(__file__).parent.parent.parent / "assets" / "module.yaml"


def run_merge(config, answers):
    """Returns (proc, config.yaml text or None, config.user.yaml text or None)."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "config.yaml"
        ucfg = Path(tmp) / "config.user.yaml"
        ans = Path(tmp) / "answers.json"
        if config is not None:
            cfg.write_text(config, encoding="utf-8")
        ans.write_text(json.dumps(answers), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--config-path", str(cfg),
                "--user-config-path", str(ucfg),
                "--module-yaml", str(MODULE_YAML),
                "--answers", str(ans),
                "--legacy-dir", tmp,
            ],
            capture_output=True,
            text=True,
        )
        cfg_text = cfg.read_text(encoding="utf-8") if cfg.exists() else None
        ucfg_text = ucfg.read_text(encoding="utf-8") if ucfg.exists() else None
        return proc, cfg_text, ucfg_text


class TestMergeConfig(unittest.TestCase):
    def test_fresh_write_creates_cdo_section(self):
        proc, cfg_text, ucfg_text = run_merge(
            None,
            {"core": {"user_name": "Afiq", "communication_language": "English"},
             "module": {"orchestration_dir": "{project-root}/docs/orchestration",
                        "earned_autonomy": "off"}},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("cdo:", cfg_text)
        self.assertIn("docs/orchestration", cfg_text)
        # user-only keys must land in config.user.yaml, not config.yaml
        self.assertNotIn("user_name", cfg_text)
        self.assertIn("Afiq", ucfg_text)

    def test_result_template_applies_project_root(self):
        proc, cfg_text, _ = run_merge(
            None, {"module": {"orchestration_dir": "docs/orchestration"}}
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("{project-root}/docs/orchestration", cfg_text)

    def test_re_run_replaces_module_section_not_others(self):
        existing = "other_mod:\n  version: 1\ncdo:\n  name: old\n"
        proc, cfg_text, _ = run_merge(existing, {"module": {"earned_autonomy": "on"}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("other_mod:", cfg_text)
        self.assertIn("on", cfg_text)
        self.assertNotIn("name: old", cfg_text)

    def test_upgrade_preserves_unrecognized_cdo_keys(self):
        """Hand-tuned / newer-version keys must survive an upgrade."""
        existing = (
            "cdo:\n  name: Autonomous Delivery Org\n  version: 0.1.0\n"
            "  custom_lane: blue\n  stall_timeout_minutes: '60'\n"
        )
        proc, cfg_text, _ = run_merge(existing, {"module": {"earned_autonomy": "on"}})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("custom_lane: blue", cfg_text)
        self.assertIn("stall_timeout_minutes", cfg_text)
        self.assertIn("earned_autonomy", cfg_text)

    def test_answers_override_preserved_keys(self):
        existing = "cdo:\n  stall_timeout_minutes: '60'\n"
        proc, cfg_text, _ = run_merge(
            existing, {"module": {"stall_timeout_minutes": "30"}}
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("30", cfg_text)
        self.assertNotIn("60", cfg_text)


if __name__ == "__main__":
    unittest.main()
