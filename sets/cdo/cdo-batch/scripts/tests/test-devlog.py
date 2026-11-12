"""Tests for devlog.py — run: uv run -m unittest discover -s tests"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "devlog.py"


def run_devlog(*args, stdin: str | None = None):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, input=stdin,
        encoding="utf-8",
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_root(root: Path, sprint_keys=()):
    """Project root with a sprint yaml + docs tree for path/attach tests."""
    impl = root / "_bmad-output" / "implementation-artifacts"
    impl.mkdir(parents=True)
    if sprint_keys is not None:
        entries = "\n".join(f"  {k}: done" for k in sprint_keys)
        (impl / "sprint-status-Beta-2026.10.11.yaml").write_text(
            "story_location: _bmad-output/implementation-artifacts\n"
            f"development_status:\n{entries}\n",
            encoding="utf-8",
        )
    (root / "docs" / "orchestration" / "devlog").mkdir(parents=True)
    return root


META = ["--story-key", "S1", "--release", "CDO-2026-10-16",
        "--session", "w-S1-x", "--dept", "cdo-growth", "--backlog", "growth",
        "--card", "docs/orchestration/alignment/2026/10/14/S1.md"]


class TestPath(unittest.TestCase):
    def test_sprint_key_derives_channel_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), sprint_keys=["14-1-some-story"])
            proc, data = run_devlog("path", "--key", "14-1-some-story",
                                    "--project-root", str(root))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["channel"], "Beta")
            self.assertEqual(data["date"], "2026-10-11")
            self.assertTrue(data["shared_with_pipeline"])
            self.assertTrue(data["dir"].endswith("14-01-some-story"))

    def test_org_key_follows_current_sprint(self):
        """A key absent from every sprint yaml still lands under the CURRENT
        sprint's Channel/date — devlogs follow the sprint cycle, so a
        hotfix bumping the app version mid-sprint never relocates the log."""
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), sprint_keys=["14-1-some-story"])
            proc, data = run_devlog("path", "--key", "ORG-9",
                                    "--project-root", str(root))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["channel"], "Beta")
            self.assertEqual(data["date"], "2026-10-11")
            self.assertEqual(data["source"], "current-sprint")
            self.assertFalse(data["shared_with_pipeline"])
            self.assertTrue(data["dir"].endswith("ORG-9"))

    def test_cdo_channel_only_without_any_sprint_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp), sprint_keys=None)
            for f in (root / "_bmad-output" / "implementation-artifacts").glob("*.yaml"):
                f.unlink()
            proc, data = run_devlog("path", "--key", "CT1",
                                    "--project-root", str(root))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["source"], "cdo")


class TestAttach(unittest.TestCase):
    def test_attach_creates_index_with_dispatch_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "devlog" / "CDO" / "2026-10-16" / "S1"
            proc, data = run_devlog("attach", str(d), *META)
            self.assertEqual(proc.returncode, 0)
            text = (d / "index.md").read_text(encoding="utf-8")
            self.assertIn("dispatch:", text)
            self.assertIn("readiness: pending", text)
            self.assertIn('session: "w-S1-x"', text)

    def test_attach_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "S1"
            run_devlog("attach", str(d), *META)
            proc, data = run_devlog("attach", str(d), *META)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["dispatch_block"], "present")
            self.assertEqual(data["created"], [])

    def test_attach_pipeline_renders_e2e_steps(self):
        """Sprint-derived stories attach BEFORE cdo-code-e2e runs — the index
        must carry pipeline.steps so the pipeline's set/resume contract
        holds when produce invokes it mid-arc."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "story"
            proc, _ = run_devlog("attach", str(d), *META, "--pipeline",
                                 "--sprint-status", "x.yaml")
            self.assertEqual(proc.returncode, 0)
            text = (d / "index.md").read_text(encoding="utf-8")
            for step in ("create-story", "development", "ship"):
                self.assertIn(f"{step}: pending", text)
            self.assertIn("readiness: pending", text)
            # cdo-code-e2e-style writes land in pipeline.steps, batch's in dispatch
            proc, _ = run_devlog("set", str(d), "development", "in-progress",
                                 "--block", "steps")
            self.assertEqual(proc.returncode, 0)
            proc, _ = run_devlog("set", str(d), "produce", "done")
            self.assertEqual(proc.returncode, 0)
            text = (d / "index.md").read_text(encoding="utf-8")
            self.assertIn("development: in-progress", text)
            self.assertIn("produce: done", text)

    def test_attach_pipeline_grafts_steps_into_existing_index(self):
        """Re-attach with --pipeline after a plain attach must graft
        pipeline.steps — cdo-code-e2e's set contract can't silently degrade."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "story"
            run_devlog("attach", str(d), *META)          # plain attach first
            proc, _ = run_devlog("attach", str(d), *META, "--pipeline")
            self.assertEqual(proc.returncode, 0)
            text = (d / "index.md").read_text(encoding="utf-8")
            self.assertIn("create-story: pending", text)
            self.assertIn("readiness: pending", text)
            proc, _ = run_devlog("set", str(d), "development", "done",
                                 "--block", "steps")
            self.assertEqual(proc.returncode, 0)

    def test_attach_grafts_onto_pipeline_index(self):
        """cdo-code-e2e already owns index.md — attach adds dispatch state
        without touching pipeline.steps."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "story"
            d.mkdir(parents=True)
            (d / "index.md").write_text(
                "---\ndepartment: engineering\npipeline:\n"
                '  story_key: "14-01-x"\n  steps:\n'
                "    create-story: done\n    development: pending\n"
                "---\n\n# Dev Log — 14-01-x\n\n## Journal\n",
                encoding="utf-8",
            )
            proc, data = run_devlog("attach", str(d), *META)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["dispatch_block"], "attached")
            text = (d / "index.md").read_text(encoding="utf-8")
            self.assertIn("create-story: done", text)   # pipeline untouched
            self.assertIn("readiness: pending", text)   # dispatch grafted

            # Both blocks independently writable
            proc, _ = run_devlog("set", str(d), "produce", "in-progress")
            self.assertEqual(proc.returncode, 0)
            proc, _ = run_devlog("set", str(d), "development", "done",
                                 "--block", "steps")
            self.assertEqual(proc.returncode, 0)
            text = (d / "index.md").read_text(encoding="utf-8")
            self.assertIn("produce: in-progress", text)
            self.assertIn("development: done", text)
            self.assertIn("create-story: done", text)


class TestJournal(unittest.TestCase):
    def test_append_step_stamp_and_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "S1"
            run_devlog("attach", str(d), *META)
            proc, _ = run_devlog("set", str(d), "claim", "done")
            self.assertEqual(proc.returncode, 0)
            proc, _ = run_devlog("append", str(d), "--title", "Dispatch opened",
                                 "--step", "2", "--of", "8",
                                 stdin="Card claimed, produce routed.")
            self.assertEqual(proc.returncode, 0)
            text = (d / "index.md").read_text(encoding="utf-8")
            self.assertIn("claim: done", text)
            self.assertIn("(step 2/8)", text)
            self.assertIn("Card claimed", text)

    def test_get_dispatch_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "S1"
            run_devlog("attach", str(d), *META)
            run_devlog("set", str(d), "readiness", "done")
            proc, data = run_devlog("get", str(d))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["steps"]["readiness"], "done")
            self.assertEqual(data["steps"]["release"], "pending")


class TestLint(unittest.TestCase):
    def test_lint_passes_clean_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "S1"
            run_devlog("attach", str(d), *META)
            proc, data = run_devlog("lint", str(d))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["violations"], [])

    def test_lint_catches_bare_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "S1"
            run_devlog("attach", str(d), *META)
            run_devlog("append", str(d), "--title", "bad",
                       stdin="Generics like Array<string> break VitePress")
            proc, data = run_devlog("lint", str(d))
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any(v["rule"] == "bare-tag"
                                for v in data["violations"]))


if __name__ == "__main__":
    unittest.main()
