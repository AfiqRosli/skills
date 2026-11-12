"""Tests for advance-lane.py — run: uv run -m unittest discover -s tests

Exercises the merge-back primitive against real scratch repos: plain FF
paths, non-FF refusal, and the --reconcile checkpoint+merge contract.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "advance-lane.py"


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)


def run_al(root: Path, *args):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--project-root", str(root),
         "run", *args],
        capture_output=True, text=True)
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_repo(tmp: Path, checked_out_lane: bool = True) -> Path:
    """Repo on `preview` at c1; `cdo-lane` points at a child commit c2
    made on a sibling branch (like a worktree ship CAS'd onto the lane)."""
    root = tmp / "repo"
    root.mkdir(parents=True)
    git(root, "init", "-b", "preview")
    orch = root / "docs" / "orchestration"
    orch.mkdir(parents=True)
    (orch / "ledger.yaml").write_text("v1\n")
    git(root, "add", ".")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-qm", "c1")
    git(root, "branch", "cdo-lane")
    git(root, "checkout", "-qb", "ship")
    (orch / "session.md").write_text("sess\n")
    git(root, "add", ".")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-qm", "ship")
    git(root, "update-ref", "refs/heads/cdo-lane", "HEAD")
    if checked_out_lane:
        git(root, "checkout", "-q", "preview")
    return root


class TestAdvanceLane(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="alane-test-"))

    def test_ff_merge_when_checked_out(self):
        root = make_repo(self.tmp)
        _, res = run_al(root, "--to", "refs/heads/cdo-lane")
        self.assertEqual(res["status"], "advanced")
        self.assertEqual(res["action"], "merged-ff")
        self.assertTrue((root / "docs/orchestration/session.md").exists())

    def test_branch_f_when_not_checked_out(self):
        root = make_repo(self.tmp, checked_out_lane=False)
        _, res = run_al(root, "--to", "refs/heads/cdo-lane")
        self.assertEqual(res["status"], "advanced")
        self.assertEqual(res["action"], "branch-f")
        self.assertEqual(
            git(root, "rev-parse", "preview").stdout.strip(),
            git(root, "rev-parse", "cdo-lane").stdout.strip())

    def test_already_abreast_is_noop(self):
        root = make_repo(self.tmp)
        run_al(root, "--to", "refs/heads/cdo-lane")
        _, res = run_al(root, "--to", "refs/heads/cdo-lane")
        self.assertEqual(res["status"], "already-abreast")

    def test_non_ff_refused_without_reconcile(self):
        root = make_repo(self.tmp)
        # local commit cdo-lane lacks → divergence, not a blocking case
        (root / "local.txt").write_text("x")
        git(root, "add", ".")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "local")
        proc, res = run_al(root, "--to", "refs/heads/cdo-lane")
        self.assertEqual(res["status"], "refused")
        self.assertNotEqual(proc.returncode, 0)

    def test_reconcile_checkpoints_org_churn_and_merges(self):
        root = make_repo(self.tmp)
        # dirty org-state overlapping the incoming diff
        (root / "docs/orchestration/ledger.yaml").write_text("v2-local\n")
        (root / "docs/orchestration/session.md").write_text("local-new\n")
        _, res = run_al(root, "--to", "refs/heads/cdo-lane", "--reconcile")
        self.assertEqual(res["status"], "reconciled")
        self.assertTrue(res["ref_advanced"])
        # local live state won the conflict resolution
        self.assertEqual(
            (root / "docs/orchestration/session.md").read_text().strip(),
            "local-new")
        self.assertEqual(
            git(root, "rev-parse", "cdo-lane").stdout.strip(),
            git(root, "rev-parse", "HEAD").stdout.strip())

    def test_dirty_non_blocking_file_survives_ff(self):
        root = make_repo(self.tmp)
        (root / "code.ts").write_text("local wip\n")
        _, res = run_al(root, "--to", "refs/heads/cdo-lane")
        self.assertEqual(res["status"], "advanced")
        self.assertEqual((root / "code.ts").read_text().strip(),
                         "local wip")

    def test_reconcile_checkpoints_code_wip_then_conflicts(self):
        """Ad-hoc WIP outside state roots gets checkpointed instead of
        refused; only the real merge conflict (add/add) still refuses —
        with the WIP preserved in the checkpoint commit."""
        root = make_repo(self.tmp)
        # lane adds a top-level file the local tree also dirtied
        git(root, "checkout", "-qb", "ship2", "cdo-lane")
        (root / "hotfix.ts").write_text("shipped\n")
        git(root, "add", ".")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "ship2")
        git(root, "update-ref", "refs/heads/cdo-lane", "HEAD")
        git(root, "checkout", "-q", "preview")
        (root / "hotfix.ts").write_text("local conflicting\n")
        proc, res = run_al(root, "--to", "refs/heads/cdo-lane",
                           "--reconcile")
        self.assertEqual(res["status"], "refused")
        self.assertIn("hotfix.ts", res.get("blocking", []))
        # the WIP was committed into the checkpoint before the merge
        # aborted — nothing lost, a human reconciles the conflict
        self.assertTrue(res.get("checkpoint"))
        self.assertIn("hotfix.ts", res.get("adhoc_checkpointed", []))
        self.assertEqual(
            (root / "hotfix.ts").read_text().strip(),
            "local conflicting")
        self.assertIn("cdo state: checkpoint",
                      git(root, "log", "-1", "--format=%s").stdout)

    def test_reconcile_checkpoints_adhoc_wip_and_merges(self):
        """Dirty ad-hoc file overlapping the incoming diff in a
        disjoint region → checkpointed, then merges clean."""
        root = make_repo(self.tmp)
        (root / "code.ts").write_text("l1\nl2\nl3\n")
        git(root, "add", ".")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "add code.ts")  # preview diverges
        git(root, "checkout", "-qb", "ship2")
        (root / "code.ts").write_text("L1-shipped\nl2\nl3\n")
        git(root, "add", ".")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "ship code.ts")
        git(root, "update-ref", "refs/heads/cdo-lane", "HEAD")
        git(root, "checkout", "-q", "preview")
        (root / "code.ts").write_text("l1\nl2\nl3-local-wip\n")
        proc, res = run_al(root, "--to", "refs/heads/cdo-lane",
                           "--reconcile")
        self.assertEqual(res["status"], "reconciled")
        self.assertEqual(res["adhoc_checkpointed"], ["code.ts"])
        self.assertEqual((root / "code.ts").read_text(),
                         "L1-shipped\nl2\nl3-local-wip\n")
        self.assertTrue(res["ref_advanced"])

    def test_reconcile_recovers_from_diverged_lane(self):
        """Crash-resume: lane holds a checkpoint commit the target lacks —
        --reconcile merges instead of dead-ending on non-FF."""
        root = make_repo(self.tmp)
        (root / "docs/orchestration/ledger.yaml").write_text("v2\n")
        git(root, "add", ".")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "--no-verify", "-qm", "cdo state: checkpoint")
        proc, res = run_al(root, "--to", "refs/heads/cdo-lane",
                           "--reconcile")
        self.assertEqual(res["status"], "reconciled")
        self.assertTrue(res["ref_advanced"])

    def test_unresolvable_to_is_error(self):
        root = make_repo(self.tmp)
        proc, res = run_al(root, "--to", "refs/heads/nope")
        self.assertEqual(res["status"], "error")
        self.assertEqual(proc.returncode, 2)

    def test_reconcile_resumes_wedged_own_merge(self):
        """A crashed reconcile left MERGE_HEAD with only state-root
        conflicts → resume resolves --ours and completes."""
        root = make_repo(self.tmp)
        git(root, "checkout", "-qb", "ship3", "cdo-lane")
        (root / "docs/orchestration/x.yaml").write_text("lane v2\n")
        git(root, "add", ".")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "ship3")
        lane_sha = git(root, "rev-parse", "HEAD").stdout.strip()
        git(root, "update-ref", "refs/heads/cdo-lane", lane_sha)
        git(root, "checkout", "-q", "preview")
        # hand-stage the wedged state: checkpoint + conflicted merge
        (root / "docs/orchestration/x.yaml").write_text("local v3\n")
        git(root, "add", "docs/orchestration/x.yaml")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
            "--no-verify", "-qm", "ckpt")
        merge = subprocess.run(
            ["git", "-C", str(root), "-c", "core.hooksPath=/dev/null",
             "merge", "--no-ff", "-m",
             "Merge refs/heads/cdo-lane into preview — reconcile shipped "
             "work with local state checkpoint", lane_sha],
            capture_output=True, text=True)
        self.assertNotEqual(merge.returncode, 0)  # wedged mid-merge
        proc, res = run_al(root, "--to", "refs/heads/cdo-lane",
                           "--reconcile")
        self.assertEqual(res["status"], "reconciled")
        self.assertIn("wedged_merge", res)
        self.assertEqual(res["conflicts_ours"],
                         ["docs/orchestration/x.yaml"])
        self.assertEqual(
            (root / "docs/orchestration/x.yaml").read_text(), "local v3\n")

    def test_wedged_foreign_merge_refuses(self):
        """A MERGE_HEAD not written by reconcile → still a hard refusal."""
        root = make_repo(self.tmp)
        git(root, "checkout", "-qb", "side")
        (root / "docs/orchestration/x.yaml").write_text("side\n")
        git(root, "add", ".")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "side")
        git(root, "checkout", "-q", "preview")
        (root / "docs/orchestration/x.yaml").write_text("main\n")
        git(root, "add", ".")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-qm", "main")
        subprocess.run(["git", "-C", str(root), "merge", "side"],
                       capture_output=True, text=True)  # wedge
        proc, res = run_al(root, "--to", "refs/heads/cdo-lane",
                           "--reconcile")
        self.assertEqual(res["status"], "refused")
        self.assertIn("merge already in progress",
                      res["errors"][0])
        subprocess.run(["git", "-C", str(root), "merge", "--abort"])

    def test_diverged_unchecked_out_lane_refuses(self):
        """A non-checked-out lane with commits the target lacks refuses —
        never a sideways branch -f."""
        root = make_repo(self.tmp)
        git(root, "checkout", "-qb", "other")
        git(root, "checkout", "-q", "preview")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
            "--allow-empty", "-m", "local-ahead")
        local_tip = git(root, "rev-parse", "preview").stdout.strip()
        git(root, "checkout", "-q", "other")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
            "--allow-empty", "-m", "side")
        side = git(root, "rev-parse", "HEAD").stdout.strip()
        # preview (unchecked out) and side now diverge
        proc, res = run_al(root, "--to", side, "--lane", "preview")
        self.assertEqual(res["status"], "refused")
        self.assertIn("never moved sideways", res["errors"][0])
        self.assertEqual(
            git(root, "rev-parse", "preview").stdout.strip(), local_tip)

    def test_to_shortname_advances_ref(self):
        """--to cdo-lane (no refs/ prefix) still advances the ref —
        symbolic-full-name normalization."""
        root = make_repo(self.tmp)
        (root / "docs/orchestration/x.yaml").write_text("v2\n")
        git(root, "add", ".")
        git(root, "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "--no-verify", "-qm", "cdo state: checkpoint")
        proc, res = run_al(root, "--to", "cdo-lane", "--reconcile")
        self.assertEqual(res["status"], "reconciled")
        self.assertTrue(res["ref_advanced"])


if __name__ == "__main__":
    unittest.main()
