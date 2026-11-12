"""Tests for spawn-dispatch.py — run: uv run -m unittest discover -s tests

Only --dry-run paths are exercised — tests never spawn a real devin process.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "spawn-dispatch.py"


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)


def run_spawn(orch: Path, root: Path, *args, env_extra=None):
    env = dict(os.environ)
    env.pop("DEVIN_MODEL", None)  # 13-48 — the caller's own env leaks into
    # the resolution chain now; tests opt back in via env_extra
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--orchestration-dir", str(orch),
         "--key", "S7", "--project-root", str(root), *args],
        capture_output=True, text=True, env=env,
    )
    return proc, json.loads(proc.stdout) if proc.stdout else None


def make_orch(root: Path):
    orch = root / "docs" / "orchestration"
    orch.mkdir(parents=True)
    return orch


class TestSpawnDispatch(unittest.TestCase):
    def test_dry_run_emits_command_and_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_spawn(orch, Path(tmp), "--dry-run", "--local")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["status"], "dry-run")
            cmd = data["spawn"]["cmd"]
            # detached acp-worker supervisor — the ACP session lands in
            # sessions.db, visible in the IDE's session list
            self.assertTrue(any("acp-worker.py" in a for a in cmd))
            self.assertIn("--mode", cmd)
            self.assertIn("--prompt-file", cmd)
            self.assertIn("--session-json", cmd)
            self.assertIn("--log", cmd)
            self.assertNotIn("-p", cmd)
            self.assertNotIn("--export", cmd)
            # prompt file written with worker identity baked in
            prompt = Path(data["spawn"]["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("S7", prompt)
            self.assertIn(data["spawn"]["session_name"], prompt)
            self.assertIn("cdo-batch", prompt)

    def test_dry_run_respects_permission_mode(self):
        """--permission-mode maps to the ACP session's --mode."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                "--permission-mode", "smart")
            cmd = data["spawn"]["cmd"]
            i = cmd.index("--mode")
            self.assertEqual(cmd[i + 1], "smart")

    def test_model_default_and_record(self):
        """13-45 — model defaults to GLM-5.3 Flash Low and lands in the
        spawn record; --model overrides."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local")
            self.assertEqual(data["spawn"]["model"], "GLM-5.3 Flash Low")
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                "--model", "GLM-5.3 Flash Low")
            self.assertEqual(data["spawn"]["model"], "GLM-5.3 Flash Low")

    def test_model_from_config(self):
        """13-45 — cdo.dispatch_model in _bmad/config.yaml wins over the
        hard default (spaces allowed)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = make_orch(root)
            (root / "_bmad").mkdir()
            (root / "_bmad" / "config.yaml").write_text(
                "cdo:\n  dispatch_model: Some Other Model\n", encoding="utf-8")
            _, data = run_spawn(orch, root, "--dry-run", "--local")
            self.assertEqual(data["spawn"]["model"], "Some Other Model")

    def test_model_inherited_from_devin_model_env(self):
        """13-48 — a worker's own DEVIN_MODEL hands down to satellites it
        spawns: --model arg > DEVIN_MODEL env > config > default."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                env_extra={"DEVIN_MODEL": "SWE-2 High"})
            self.assertEqual(data["spawn"]["model"], "SWE-2 High")
            self.assertEqual(data["spawn"]["model_source"], "env")
            cmd = data["spawn"]["cmd"]
            self.assertEqual(cmd[cmd.index("--model") + 1], "SWE-2 High")
            # explicit --model still beats the inherited env
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                "--model", "GLM-5.3 High",
                                env_extra={"DEVIN_MODEL": "SWE-2 High"})
            self.assertEqual(data["spawn"]["model"], "GLM-5.3 High")
            self.assertEqual(data["spawn"]["model_source"], "arg")
            # config only applies when no env is ambient
            (Path(tmp) / "_bmad").mkdir()
            (Path(tmp) / "_bmad" / "config.yaml").write_text(
                "cdo:\n  dispatch_model: Config Model\n", encoding="utf-8")
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local")
            self.assertEqual(data["spawn"]["model"], "Config Model")
            self.assertEqual(data["spawn"]["model_source"], "config")
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                env_extra={"DEVIN_MODEL": "SWE-2 High"})
            self.assertEqual(data["spawn"]["model"], "SWE-2 High")
            self.assertEqual(data["spawn"]["model_source"], "env")

    def test_model_env_invalid_falls_through_with_warning(self):
        """13-48 — an ambient DEVIN_MODEL failing the shim allowlist is
        skipped (warning recorded), never baked into the cmd shim."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                env_extra={"DEVIN_MODEL": "GLM&whoami"})
            self.assertEqual(data["spawn"]["model"], "GLM-5.3 Flash Low")
            self.assertEqual(data["spawn"]["model_source"], "default")
            self.assertTrue(any("DEVIN_MODEL" in w for w in
                                (data["spawn"].get("warnings") or [])))

    def test_model_coverage_note_in_record(self):
        """13-48 — spawn records carry model_coverage: lead model+source,
        sidekick registry-assigned (no per-call lever)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local")
            cov = data["spawn"]["model_coverage"]
            self.assertEqual(cov["lead"], "GLM-5.3 Flash Low")
            self.assertEqual(cov["lead_source"], "default")
            self.assertEqual(cov["sidekick"], "registry-assigned")

    def test_model_metacharacters_refused(self):
        """13-45 F2 — the model is baked into a cmd shim; cmd
        metacharacters (& | ^ > <) must refuse at spawn time."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            for bad in ("GLM&whoami", "GLM|del", 'GLM"dir', "GLM^x"):
                proc, data = run_spawn(orch, Path(tmp), "--dry-run",
                                       "--local", "--model", bad)
                self.assertEqual(proc.returncode, 1, data)
                self.assertTrue(any("invalid model" in e
                                    for e in data["errors"]))

    def test_config_str_quoted_value_with_spaces(self):
        """13-45 F4 — a quoted config value survives intact; a bare value
        with a mid-string quote no longer truncates the parse."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orch = make_orch(root)
            (root / "_bmad").mkdir()
            (root / "_bmad" / "config.yaml").write_text(
                'cdo:\n  dispatch_model: "GLM 5.3 (flash, low)"\n',
                encoding="utf-8")
            _, data = run_spawn(orch, root, "--dry-run", "--local")
            self.assertEqual(data["spawn"]["model"], "GLM 5.3 (flash, low)")

    def test_disjoint_drain_locks_spawn_in_parallel(self):
        """13-45 — the drain guard is intersection-based: a live g-lock
        holding DIFFERENT keys does not refuse a new spawn; overlapping
        keys refuse."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            locks = orch / "locks"
            locks.mkdir()
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            (locks / "g-S9-20260101000000.lock").write_text(
                f"w-other {ts} S9", encoding="utf-8")
            proc, data = run_spawn(orch, Path(tmp), "--dry-run", "--local")
            self.assertEqual(proc.returncode, 0, data)
            # refusal path needs a REAL spawn — --dry-run skips the guard
            proc, data = run_spawn(orch, Path(tmp), "--keys", "S9,S8")
            self.assertEqual(proc.returncode, 1, data)
            self.assertTrue(any("already holds" in e or "holds:" in e
                                for e in data["errors"]))

    def test_guard_checks_all_fresh_locks_not_just_first(self):
        """13-45 F1 regression — parallel groups mean MULTIPLE fresh g-locks
        coexist; the guard must examine every one. A second lock holding an
        overlapping key must refuse even when the first (sorted-earlier)
        lock is disjoint."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            locks = orch / "locks"
            locks.mkdir()
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            # sorted-earlier lock is disjoint; sorted-later lock overlaps S9
            (locks / "g-S1-20260101000000.lock").write_text(
                f"w-a {ts} S1", encoding="utf-8")
            (locks / "g-S9-20260101000000.lock").write_text(
                f"w-b {ts} S9", encoding="utf-8")
            proc, data = run_spawn(orch, Path(tmp), "--keys", "S9,S8")
            self.assertEqual(proc.returncode, 1, data)
            self.assertTrue(any("S9" in e for e in data["errors"]))

    def test_export_is_acp_session_json(self):
        """No ATIF --export under ACP — the transcript is sessions.db plus
        the session/update JSONL log; the terminal record is .acp.json."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local")
            spawn = data["spawn"]
            self.assertIsNone(spawn["export"])
            self.assertIn("S7.acp.json", spawn["session_json"])

    def test_local_is_default_target(self):
        """No flag, no config → local: detached `devin -p` sharing this
        filesystem — the safe default, no origin remote required."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_spawn(orch, Path(tmp), "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            spawn = data["spawn"]
            cmd = spawn["cmd"]
            self.assertNotIn("--cloud", cmd)
            self.assertTrue(any("acp-worker.py" in a for a in cmd))
            self.assertIn("--mode", cmd)
            self.assertEqual(spawn["target"], "local")
            self.assertIsNone(spawn["lane"])

    def test_cloud_target_via_config(self):
        """dispatch_target: cloud → `devin --cloud -p`, no local-only
        flags, lane/base/push metadata on the record. The ship lane is the
        org's single branch — no cdo/* work branches exist anymore."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            bmad = Path(tmp) / "_bmad"
            bmad.mkdir()
            (bmad / "config.yaml").write_text(
                "cdo:\n  dispatch_target: cloud\n", encoding="utf-8")
            proc, data = run_spawn(orch, Path(tmp), "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            spawn = data["spawn"]
            cmd = spawn["cmd"]
            self.assertIn("--cloud", cmd)
            self.assertIn("-p", cmd)
            self.assertIn("--prompt-file", cmd)
            self.assertNotIn("--permission-mode", cmd)
            self.assertNotIn("--export", cmd)
            self.assertEqual(spawn["target"], "cloud")
            self.assertEqual(spawn["lane"], "preview")
            self.assertEqual(spawn["base_ref"], "origin/preview")
            # the pre-spawn push is part of the cloud contract
            self.assertIn("would_run", spawn["push"])

    def test_cloud_dispatch_prompt_carries_lane_contract(self):
        """The cloud drain prompt binds the worker to the single ship lane —
        push per story to origin/{lane}, never a cdo/* branch."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--cloud")
            spawn = data["spawn"]
            prompt = Path(spawn["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("preview", prompt)
            self.assertIn("origin/preview", prompt)
            self.assertIn("git checkout -B preview", prompt)
            self.assertIn("git push origin HEAD:preview", prompt)
            self.assertNotIn("cdo/dispatch", prompt)

    def test_cloud_drain_spawn(self):
        """--keys → one w-drain session, drain lock id, sequential-drain prompt."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_spawn(orch, Path(tmp), "--dry-run", "--cloud",
                                   "--keys", "S7,S9")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            spawn = data["spawn"]
            self.assertEqual(spawn["keys"], ["S7", "S9"])
            self.assertTrue(spawn["session_name"].startswith("w-drain-"))
            self.assertTrue(spawn["drain_id"].startswith("g-s7-"))
            prompt = Path(spawn["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("S7, S9", prompt)
            self.assertIn("drain", prompt.lower())

    def test_local_drain_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                   "--keys", "S7,S9")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            spawn = data["spawn"]
            self.assertEqual(spawn["target"], "local")
            self.assertIsNone(spawn["lane"])
            self.assertTrue(spawn["session_name"].startswith("w-drain-"))
            prompt = Path(spawn["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("S7, S9", prompt)
            # local workers sit on the shared checkout — no branch prep
            self.assertNotIn("git checkout -B", prompt)

    def test_drain_prompt_carries_continuation_contract(self):
        """13-27 — budget + successor handoff lands in the drain brief."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                "--keys", "S7,S9")
            prompt = Path(data["spawn"]["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("story budget is 4", prompt)  # default budget
            self.assertIn("continuation: true", prompt)
            self.assertIn("--continuation", prompt)

    def test_story_budget_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                "--keys", "S7,S9", "--story-budget", "7")
            prompt = Path(data["spawn"]["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("story budget is 7", prompt)

    def test_local_drain_defaults_to_worktree(self):
        """13-29 — local drains get .cdo-work isolation; ship lands on the
        local cdo-lane ref (pre-deploy gate — no origin push)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                "--keys", "S7,S9")
            spawn = data["spawn"]
            self.assertIn(".cdo-work", str(spawn.get("worktree") or ""))
            prompt = Path(spawn["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("isolated git worktree", prompt)
            self.assertIn("cdo-lane", prompt)
            self.assertIn("land.py", prompt)
            self.assertNotIn("git push origin HEAD:", prompt)
            self.assertIn("MAIN checkout", prompt)

    def test_worktree_bases_on_cdo_lane_when_present(self):
        """Pre-deploy gate — a live cdo-lane ref is the worktree base, so
        landed-but-unpushed dep work is visible to later drains."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init")
            git(root, "-c", "user.email=t@t", "-c", "user.name=t",
                "commit", "--allow-empty", "-m", "init")
            git(root, "branch", "cdo-lane")
            orch = make_orch(root)
            proc, data = run_spawn(orch, root, "--dry-run", "--local",
                                   "--keys", "S7,S9")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["spawn"]["base_ref"], "refs/heads/cdo-lane")
            # the ship leg lands via land.py — the CAS old value is read
            # at ship-time inside the script, not baked at spawn
            prompt = Path(data["spawn"]["prompt_file"]).read_text(
                encoding="utf-8")
            self.assertIn("land.py", prompt)
            self.assertIn("refs/heads/cdo-lane", prompt)

    def test_worktree_bases_on_origin_lane_without_cdo_lane(self):
        """No cdo-lane yet (fresh install) — the worktree bases on
        origin/{lane} exactly as before."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init")
            git(root, "-c", "user.email=t@t", "-c", "user.name=t",
                "commit", "--allow-empty", "-m", "init")
            orch = make_orch(root)
            proc, data = run_spawn(orch, root, "--dry-run", "--local",
                                   "--keys", "S7,S9")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(data["spawn"]["base_ref"], "origin/preview")

    def test_no_worktree_escape_keeps_shared_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                "--keys", "S7,S9", "--no-worktree")
            spawn = data["spawn"]
            self.assertIsNone(spawn.get("worktree"))
            prompt = Path(spawn["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("git rev-parse --abbrev-ref HEAD", prompt)

    def test_operator_name_substitution(self):
        """user_name from config.user.yaml renders 'Operator {name}' in
        worker prompts — the human decision-maker is named, not generic."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            bmad = Path(tmp) / "_bmad"
            bmad.mkdir()
            (bmad / "config.user.yaml").write_text(
                "user_name: Afiq\n", encoding="utf-8")
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local")
            prompt = Path(data["spawn"]["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("Operator Afiq", prompt)
            self.assertNotIn("CEO", prompt)

    def test_dispatch_target_config_override(self):
        """cdo.dispatch_target in _bmad/config.yaml sets the default;
        --cloud/--local flags beat it."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            bmad = Path(tmp) / "_bmad"
            bmad.mkdir()
            (bmad / "config.yaml").write_text(
                "cdo:\n  dispatch_target: local\n", encoding="utf-8")
            _, data = run_spawn(orch, Path(tmp), "--dry-run")
            self.assertEqual(data["spawn"]["target"], "local")
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--cloud")
            self.assertEqual(data["spawn"]["target"], "cloud")

    def test_missing_devin_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            # a REAL spawn refuses outright — no binary, no worker
            proc, data = run_spawn(orch, Path(tmp),
                                   "--devin-bin", "definitely-not-devin-xyz")
            self.assertEqual(proc.returncode, 1)
            self.assertTrue(any("not found" in e for e in data["errors"]))
            # a dry-run still succeeds but warns — planning never needs the bin
            proc, data = run_spawn(orch, Path(tmp), "--dry-run",
                                   "--devin-bin", "definitely-not-devin-xyz")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("warning", data["spawn"])

    def test_review_kind_artifact_family(self):
        """--kind review → {key}.review.* artifacts, r-{key} session, and the
        fresh-eyes reviewer prompt — never clobbering dispatch records."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                   "--kind", "review")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            spawn = data["spawn"]
            self.assertEqual(spawn["kind"], "review")
            self.assertTrue(spawn["session_name"].startswith("r-S7-"))
            self.assertIn("S7.review.prompt.md", spawn["prompt_file"])
            self.assertIn("S7.review.acp.json", spawn["session_json"])
            prompt = Path(spawn["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("did NOT do", prompt)
            self.assertIn("delivery-note.py", prompt)

    def test_wave_kind(self):
        """--kind wave → w-review-* session, wave-{batch} artifacts, holistic prompt."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            # wave callers pass the batch id as --key
            proc, data = run_spawn(orch, Path(tmp), "--dry-run",
                                   "--kind", "wave")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            spawn = data["spawn"]
            self.assertEqual(spawn["kind"], "wave")
            self.assertTrue(spawn["session_name"].startswith("w-review-S7-"))
            prompt = Path(spawn["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("holistic", prompt)
            self.assertIn("file-wave", prompt)

    def test_academy_kind_artifact_family(self):
        """--kind academy → {key}.academy.* artifacts, a-{key} session, and
        the extraction prompt — the post-ship dissection leg."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_spawn(orch, Path(tmp), "--dry-run", "--local",
                                   "--kind", "academy")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            spawn = data["spawn"]
            self.assertEqual(spawn["kind"], "academy")
            self.assertTrue(spawn["session_name"].startswith("a-S7-"))
            self.assertIn("S7.academy.prompt.md", spawn["prompt_file"])
            self.assertIn("S7.academy.acp.json", spawn["session_json"])
            prompt = Path(spawn["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("cdo-academy", prompt)
            self.assertIn("gap-check", prompt)
            self.assertIn("file-extract", prompt)

    def test_manual_mode_refuses_auto_kinds(self):
        """dispatch_mode: manual — auto-triggered kinds (review/wave)
        refuse; dispatch and academy are deliberate acts and stay
        ungated (workers never auto-spawn academy, so a --kind academy
        call is by definition deliberate)."""
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            bmad = Path(tmp) / "_bmad"
            bmad.mkdir()
            (bmad / "config.yaml").write_text(
                "cdo:\n  dispatch_mode: manual\n", encoding="utf-8")
            for kind in ("review", "wave"):
                proc, data = run_spawn(orch, Path(tmp), "--dry-run",
                                       "--kind", kind)
                self.assertEqual(proc.returncode, 1, f"{kind} spawned in manual mode")
                self.assertTrue(any("manual" in e for e in data["errors"]))
            for kind in ("dispatch", "academy"):
                proc, data = run_spawn(orch, Path(tmp), "--dry-run",
                                       "--local", "--kind", kind)
                self.assertEqual(proc.returncode, 0,
                                 f"{kind} gated in manual mode")

    def test_dispatch_kind_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            _, data = run_spawn(orch, Path(tmp), "--dry-run", "--local")
            spawn = data["spawn"]
            self.assertEqual(spawn["kind"], "dispatch")
            self.assertTrue(spawn["session_name"].startswith("w-S7-"))
            self.assertIn("S7.prompt.md", spawn["prompt_file"])

    @unittest.skipUnless(shutil.which("devin"), "devin binary not on PATH")
    def test_session_record_written_on_spawn_path(self):
        # dry-run doesn't write the record; this checks resolve_devin works
        # against a real binary without spawning (still --dry-run)
        with tempfile.TemporaryDirectory() as tmp:
            orch = make_orch(Path(tmp))
            proc, data = run_spawn(orch, Path(tmp), "--dry-run")
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(data["spawn"]["session_name"].startswith("w-S7-"), True)


if __name__ == "__main__":
    unittest.main()
