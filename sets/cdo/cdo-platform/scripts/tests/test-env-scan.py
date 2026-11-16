"""Tests for env-scan.py — run: uv run -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENVSCAN = Path(__file__).parent.parent / "env-scan.py"


def run(*args):
    proc = subprocess.run([sys.executable, str(ENVSCAN), *args],
                          capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


class TestEnvScan(unittest.TestCase):
    def test_reports_real_temp_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            (orch / "alignment" / "2026" / "10" / "14").mkdir(parents=True)
            (orch / "alignment" / "2026" / "10" / "14" / "S1.md").write_text(
                "## Externals Needed\n\n- `STRIPE_KEY` — pay\n- `MAIL_KEY` — mail\n",
                encoding="utf-8")
            (orch / "alignment-checklist.md").write_text(
                "## Requisitions\n\n- [ ] MAIL_KEY — needed by S1\n", encoding="utf-8")
            env = root / ".env"
            env.write_text("STRIPE_KEY=t  # TEMP-CDO\nREAL_OK=x\n", encoding="utf-8")
            proc, data = run("--orchestration-dir", str(orch), "--env-file", str(env))
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(data["coverage"]["temp_placeholders"], ["STRIPE_KEY"])
            self.assertEqual(data["coverage"]["missing"], ["MAIL_KEY"])
            self.assertEqual(data["requisitions"]["pending"], ["MAIL_KEY"])

    def test_all_covered(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Path(tmp) / "docs" / "orchestration"
            orch.mkdir(parents=True)
            env = Path(tmp) / ".env"
            env.write_text("A_KEY=1\n", encoding="utf-8")
            proc, data = run("--orchestration-dir", str(orch), "--env-file", str(env))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["status"], "ok")

    def test_file_requisitions_appends_and_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            (orch / "alignment" / "2026" / "10" / "14").mkdir(parents=True)
            (orch / "alignment" / "2026" / "10" / "14" / "S1.md").write_text(
                "## Externals Needed\n\n- `NEW_KEY` — x\n- `ASKED_KEY` — y\n",
                encoding="utf-8")
            checklist = orch / "alignment-checklist.md"
            checklist.write_text(
                "## Requisitions\n\n- [ ] ASKED_KEY — needed by S1\n\n"
                "## Other\n\n- keep me\n", encoding="utf-8")
            env = root / ".env"
            env.write_text("", encoding="utf-8")
            proc, data = run("--orchestration-dir", str(orch),
                             "--env-file", str(env), "--file-requisitions")
            self.assertEqual(data["filed_requisitions"], ["NEW_KEY"])
            text = checklist.read_text(encoding="utf-8")
            # the new line lands inside the Requisitions section,
            # before the next heading; the pending one is not re-filed
            req_block = text.split("## Requisitions")[1].split("## ")[0]
            self.assertIn("- [ ] NEW_KEY — needed by S1", req_block)
            self.assertEqual(req_block.count("- [ ]"), 2)
            self.assertIn("## Other", text)

    def test_file_requisitions_creates_section_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = root / "docs" / "orchestration"
            (orch / "alignment" / "2026" / "10" / "14").mkdir(parents=True)
            (orch / "alignment" / "2026" / "10" / "14" / "S2.md").write_text(
                "## Externals Needed\n\n- `LONE_KEY` — x\n", encoding="utf-8")
            checklist = orch / "alignment-checklist.md"
            checklist.write_text("# checklist\n", encoding="utf-8")
            env = root / ".env"
            env.write_text("", encoding="utf-8")
            proc, data = run("--orchestration-dir", str(orch),
                             "--env-file", str(env), "--file-requisitions")
            self.assertEqual(data["filed_requisitions"], ["LONE_KEY"])
            text = checklist.read_text(encoding="utf-8")
            self.assertIn("## Requisitions", text)
            self.assertIn("- [ ] LONE_KEY — needed by S2", text)


if __name__ == "__main__":
    unittest.main()
