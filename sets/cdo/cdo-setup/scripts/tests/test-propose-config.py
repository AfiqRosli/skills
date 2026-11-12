"""Tests for cdo-setup propose-config.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "propose-config.py"
MODULE_YAML = Path(__file__).parent.parent.parent / "assets" / "module.yaml"

DETECT = {
    "mode": "upgrade",
    "prior_cdo_config": {"stall_timeout_minutes": "60", "custom_lane": "blue"},
    "conventions": {
        "sprint_status_files": ["_bmad-output/impl/sprint-status.yaml"],
        "story_dir": "_bmad-output/implementation-artifacts/stories",
        "devlog_dir": "docs/orchestration/devlog",
        "package_manager": "bun",
        "health_commands": {"test": "bun run test", "build": "bun run build"},
    },
    "soft_deps": {"dept_modules": ["cdo-growth"]},
}


def run_propose(detect=None, extra_args=()):
    with tempfile.TemporaryDirectory() as tmp:
        dpath = Path(tmp) / "detect.json"
        dpath.write_text(json.dumps(detect or DETECT), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--detect", str(dpath),
             "--module-yaml", str(MODULE_YAML), *extra_args],
            capture_output=True, text=True,
        )
        return proc, json.loads(proc.stdout) if proc.stdout else None


class TestProposeConfig(unittest.TestCase):
    def test_detected_values_win_over_defaults(self):
        proc, data = run_propose()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        mod = data["answers"]["module"]
        self.assertEqual(mod["sprint_status_path"],
                         "_bmad-output/impl/sprint-status.yaml")
        self.assertEqual(mod["package_manager"], "bun")
        self.assertIn("bun run test", mod["health_commands"])

    def test_stored_prior_beats_detected(self):
        detect = dict(DETECT)
        detect["prior_cdo_config"] = {"package_manager": "pnpm"}
        proc, data = run_propose(detect)
        self.assertEqual(data["answers"]["module"]["package_manager"], "pnpm")

    def test_set_override_beats_everything(self):
        proc, data = run_propose(extra_args=["--set", "stall_timeout_minutes=90"])
        self.assertEqual(data["answers"]["module"]["stall_timeout_minutes"], "90")

    def test_stored_extra_keys_preserved(self):
        proc, data = run_propose()
        self.assertEqual(data["answers"]["module"]["custom_lane"], "blue")

    def test_backlog_map_derived(self):
        proc, data = run_propose()
        bm = data["answers"]["module"]["backlog_map"]
        self.assertEqual(bm["code"], "backlogs/code.md")
        # keyed by backlog stem — cdo-growth's manifest backlog is content.md
        self.assertEqual(bm["content"], "backlogs/content.md")

    def test_no_core_omits_core(self):
        proc, data = run_propose(extra_args=["--no-core"])
        self.assertNotIn("core", data["answers"])

    def test_existing_core_keys_auto_omit_core(self):
        """core_keys_present from detect → the default core block (which
        would reset user_name to 'BMad') is omitted automatically."""
        detect = dict(DETECT)
        detect["core_keys_present"] = ["user_name", "output_folder"]
        proc, data = run_propose(detect)
        self.assertNotIn("core", data["answers"])
        self.assertTrue(data["core_auto_omitted"])

    def test_core_set_overrides_auto_omit(self):
        """An explicit --core-set means the caller intends to change that
        value — the core block is emitted despite existing keys."""
        detect = dict(DETECT)
        detect["core_keys_present"] = ["user_name"]
        proc, data = run_propose(detect, extra_args=[
            "--core-set", "user_name=Afiq"])
        self.assertEqual(data["answers"]["core"]["user_name"], "Afiq")
        self.assertFalse(data["core_auto_omitted"])

    def test_proposed_table_has_sources(self):
        proc, data = run_propose()
        sources = {p["key"]: p["source"] for p in data["proposed"]}
        self.assertEqual(sources["package_manager"], "detected")
        self.assertEqual(sources["stall_timeout_minutes"], "stored")
        self.assertEqual(sources["earned_autonomy"], "default")


if __name__ == "__main__":
    unittest.main()
