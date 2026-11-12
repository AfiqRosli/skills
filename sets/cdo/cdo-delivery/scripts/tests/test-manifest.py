"""Tests for manifest.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SCRIPT = Path(__file__).parent.parent / "manifest.py"


def run(orch, *args):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--orchestration-dir", str(orch), *args],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_orch(root, pool, backlog_lines):
    orch = root / "docs" / "orchestration"
    (orch / "backlogs").mkdir(parents=True)
    (orch / "backlogs" / "code.md").write_text(backlog_lines, encoding="utf-8")
    (orch / "flow-ledger.yaml").write_text(
        "pool:\n  confirmed: [%s]\n  quarantined: []\nstories: {}\n"
        % ", ".join(pool), encoding="utf-8")
    return orch


class TestManifest(unittest.TestCase):
    def test_topo_orders_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), ["S2", "S1", "S3"], (
                "- [x] S1 — base\n"
                "- [x] S2 — mid | deps: S1\n"
                "- [x] S3 — top | deps: S2,S1\n"))
            proc, data = run(orch)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["manifest"], ["S1", "S2", "S3"])

    def test_cycle_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), ["S1", "S2"], (
                "- [x] S1 | deps: S2\n- [x] S2 | deps: S1\n"))
            proc, data = run(orch)
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(data["cyclic"])

    def test_empty_pool_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), [], "")
            proc, data = run(orch)
            self.assertEqual(proc.returncode, 1)

    def test_writes_batch_to_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp), ["S1"], "- [x] S1\n")
            run(orch, "--batch-id", "b9")
            ledger = yaml.safe_load((orch / "flow-ledger.yaml").read_text(encoding="utf-8"))
            self.assertEqual(ledger["batch"]["id"], "b9")
            self.assertEqual(ledger["batch"]["manifest"], ["S1"])



    def _orch_with_story(root, key, status):
        import yaml
        orch = make_orch(root, ["S1"], "- [x] S1 — top | deps: S9\n")
        lpath = orch / "flow-ledger.yaml"
        l = yaml.safe_load(lpath.read_text(encoding="utf-8"))
        l["stories"] = {key: {"status": status}}
        lpath.write_text(yaml.safe_dump(l), encoding="utf-8")
        return orch

    def test_dead_dep_blocks_dependent(self):
        with tempfile.TemporaryDirectory() as tmp:
            # S9 quarantined → NOT in pool → S1's dep is dead, not "done"
            orch = TestManifest._orch_with_story(Path(tmp), "S9", "quarantined")
            proc, data = run(orch)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("dead_deps", data)

    def test_done_dep_satisfies(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = TestManifest._orch_with_story(Path(tmp), "S9", "done")
            proc, data = run(orch)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["manifest"], ["S1"])


if __name__ == "__main__":
    unittest.main()
