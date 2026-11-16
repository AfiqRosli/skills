"""Tests for ship-commit.py — run: python test-ship-commit.py

Covers the --require-status gate (the structural cardinal-sin check);
the sweep/stage/commit internals are exercised by the ship-step
prompts' consumers.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SHIP = Path(__file__).parent.parent / "ship-commit.py"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args],
                          capture_output=True, text=True)


def run(*args):
    proc = subprocess.run([sys.executable, str(SHIP), *args],
                          capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = None
    return proc, data


LEDGER = """\
stories:
  {key}:
    status: {status}
"""


class TestRequireStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.orch = self.root / "docs" / "orchestration"
        self.orch.mkdir(parents=True)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@t")
        git(self.root, "config", "user.name", "t")
        (self.root / "f.txt").write_text("x\n", encoding="utf-8")
        git(self.root, "add", "f.txt")
        git(self.root, "commit", "-qm", "init")
        # ship-commit resolves ship-artifacts at
        # {root}/.agents/skills/cdo-platform/scripts/ — stage the real
        # pair there (ship-artifacts imports the vendored cardlayout)
        scripts = self.root / ".agents" / "skills" / "cdo-platform" / \
            "scripts"
        scripts.mkdir(parents=True)
        src = Path(__file__).parent.parent
        for name in ("ship-artifacts.py", "cardlayout.py"):
            (scripts / name).write_text(
                (src / name).read_text(encoding="utf-8"), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def write_ledger(self, key, status):
        self.orch.joinpath("flow-ledger.yaml").write_text(
            LEDGER.format(key=key, status=status), encoding="utf-8")

    def args(self, key):
        return ["--project-root", str(self.root),
                "--orchestration-dir", str(self.orch),
                "--keys", key, "--message", f"cdo {key}: shipped",
                "--require-status", "verified"]

    def test_refuses_unverified_story(self):
        self.write_ledger("9-1", "aligned")
        proc, data = run(*self.args("9-1"))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(data["status"], "refused")
        self.assertIn("9-1", data["errors"][0])
        self.assertIn("verified", data["errors"][0])

    def test_refuses_missing_story(self):
        self.orch.joinpath("flow-ledger.yaml").write_text(
            "stories: {}\n", encoding="utf-8")
        proc, data = run(*self.args("9-9"))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(data["status"], "refused")
        self.assertIn("9-9", data["errors"][0])

    def test_verified_story_passes_gate(self):
        self.write_ledger("9-2", "verified")
        proc, data = run(*self.args("9-2"))
        # gate passed — outcome depends on the sweep (nothing to
        # commit or committed), never a status refusal
        self.assertNotEqual(data["status"], "refused")
        self.assertIn(data["status"], ("committed", "nothing-to-commit"))

    def test_gate_off_by_default_for_sweeps(self):
        # the drain-end artifact sweep ships keys already 'shipped' —
        # without --require-status it must not refuse on the ledger
        self.write_ledger("9-3", "shipped")
        proc, data = run(*[a for a in self.args("9-3")
                           if a != "--require-status" and a != "verified"])
        self.assertIn(data["status"], ("committed", "nothing-to-commit"))


if __name__ == "__main__":
    unittest.main()
