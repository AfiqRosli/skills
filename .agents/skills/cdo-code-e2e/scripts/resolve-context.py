#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Resolve cdo-code-e2e activation context into one JSON blob.

Deterministic pre-pass that replaces LLM globbing/parsing at activation:
config values, newest sprint-status file, release name, story-key resolution
(--story > resumable dev log > first backlog), devlog path derivation,
pipeline resume state, and a pre-flight dependency check.

Usage: python resolve-context.py [--story KEY] [--from STEP] [--project-root PATH]
"""
import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STEPS = [
    "create-story", "wireframe", "predev-confirm", "development",
    "post-dev-sync", "audits", "remediate", "health-check",
    "review", "retrospective", "story-sync", "mark-done", "ship",
]

# Old step names from earlier layouts, for --from alias resolution.
STEP_ALIASES = {
    "alignment": "audits", "security-audit": "audits", "code-review": "audits",
    "alignment-fix": "remediate", "security-fix": "remediate",
    "review-fix": "remediate",
    "health-check-final": "health-check",
}

OWNER_SKILLS = [
    "bmad-create-story", "bmad-dev-story",
    "cdo-alignment-uncommitted-changes",
    "cdo-security-audit-uncommitted-changes",
    "bmad-code-review", "cdo-review-implement-refinement",
    "cdo-git-quick-push", "cdo-git-push", "cdo-git-pr-message",
]

# Conditional owners — only reached at specific steps/modes. Missing → warn
# and degrade (the gate adapts or skips), not a preflight halt.
CONDITIONAL_SKILLS = [
    "cdo-version-change-for-production",  # step-13 ship gate
    "bmad-retrospective",                 # step-10 epic-scope adaptation
]

FLAT_KEYS = [
    "user_name", "communication_language", "document_output_language",
    "user_skill_level", "output_folder", "planning_artifacts",
    "implementation_artifacts", "project_knowledge",
]


def find_project_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "_bmad").is_dir():
            return p
    return start


def read_flat_config(path: Path, project_root: Path) -> dict:
    """Extract top-level `key: value` pairs; resolve {project-root} placeholders."""
    out = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^([a-z_]+):\s*(.+?)\s*$", line)
        if m and m.group(1) in FLAT_KEYS:
            val = m.group(2).strip('"').strip("'")
            out[m.group(1)] = val.replace("{project-root}", str(project_root))
    return out


def parse_sprint_status(path: Path) -> dict:
    """Return story_location and ordered development_status entries."""
    story_location = None
    entries = []  # (key, status) in file order
    in_status = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if story_location is None:
            m = re.match(r"^story_location:\s*(.+?)\s*$", line)
            if m:
                story_location = m.group(1)
        if re.match(r"^development_status:\s*$", line):
            in_status = True
            continue
        if in_status:
            m = re.match(r"^\s{2}([A-Za-z0-9][\w.-]*):\s*([a-z-]+)", line)
            if m:
                entries.append((m.group(1), m.group(2)))
            elif re.match(r"^\S", line):
                in_status = False
    return {"story_location": story_location, "entries": entries}


def release_to_devlog_parts(release: str) -> tuple[str, str]:
    """Beta-2026.09.14.2 -> ("Beta", "2026-09-14.2")."""
    channel, _, rest = release.partition("-")
    segs = rest.split(".")
    date = "-".join(segs[:3]) + ("." + ".".join(segs[3:]) if len(segs) > 3 else "")
    return channel or release, date


def story_key_to_devlog_name(story_key: str) -> str:
    """11-2-foo -> 11-02-foo — pad the epic/story numbers so the devlog
    tree sorts numerically (the VitePress sidebar sorts lexically, where
    11-11 would land between 11-1 and 11-2). The index frontmatter keeps
    the raw story_key, so resume and story-file lookups are unaffected."""
    m = re.match(r"^(\d+)-(\d+)(-.*)$", story_key)
    return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}{m.group(3)}" if m else story_key


def read_devlog_state(index_md: Path) -> dict | None:
    text = index_md.read_text(encoding="utf-8", errors="replace")
    fm = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not fm:
        return None
    key = re.search(r"^\s+story_key:\s*\"?(.+?)\"?\s*$", fm.group(1), re.M)
    rel = re.search(r"^\s+release:\s*\"?(.+?)\"?\s*$", fm.group(1), re.M)
    steps_block = re.search(r"^\s+steps:[ \t]*\n((?:[ \t]+[\w-]+:[ \t]*[\w-]+[ \t]*\n?)+)", fm.group(1), re.M)
    steps = dict(re.findall(r"^\s+([\w-]+):\s*([\w-]+)\s*$",
                            steps_block.group(1) if steps_block else "", re.M))
    if not key or not steps:
        return None
    return {"story_key": key.group(1), "release": rel.group(1) if rel else None,
            "steps": steps, "index": str(index_md)}


def next_step(steps: dict) -> str | None:
    for s in STEPS:
        # Only steps recorded in the devlog count — a step absent from an
        # older-layout devlog must not read as pending, or finished logs
        # would resurface as resumable whenever the pipeline gains a step.
        if s in steps and steps[s] not in ("done", "skipped"):
            return s
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--story", help="Explicit story key")
    ap.add_argument("--from", dest="from_step", help="Resume override step")
    ap.add_argument("--lite", action="store_true",
                    help="Proportional-effort mode: auto-confirm gates, single combined audit pass")
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("-o", "--output", type=Path, help="Write JSON to file instead of stdout")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    errors = []
    root = find_project_root(args.project_root.resolve())

    config = {}
    for cfg in (root / "_bmad" / "config.yaml", root / "_bmad" / "config.user.yaml",
                root / "_bmad" / "core" / "config.yaml", root / "_bmad" / "bmm" / "config.yaml"):
        for k, v in read_flat_config(cfg, root).items():
            config.setdefault(k, v)

    # TOML overlay — on BMAD v6.12+ the installer manages config.toml layers
    # (core.* + modules.bmm.*) via _bmad/scripts/resolve_config.py; YAML files
    # above remain the module-section contract and pre-6.12 fallback. TOML
    # wins for the flat keys it carries. modules.bmm assumes the standard
    # BMAD Method module code — a renamed module misses these keys and
    # silently keeps the YAML values (fails soft by design).
    toml_keys = (
        [f"core.{k}" for k in ("user_name", "communication_language",
                               "document_output_language", "output_folder")]
        + [f"modules.bmm.{k}" for k in ("user_skill_level", "planning_artifacts",
                                        "implementation_artifacts", "project_knowledge")]
    )
    resolver = root / "_bmad" / "scripts" / "resolve_config.py"
    if resolver.is_file():
        cmd = ["uv", "run", str(resolver), "--project-root", str(root)]
        for k in toml_keys:
            cmd += ["--key", k]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode == 0:
                for dotted, v in json.loads(proc.stdout).items():
                    if isinstance(v, str) and v:
                        config[dotted.rsplit(".", 1)[-1]] = v.replace(
                            "{project-root}", str(root))
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            pass

    impl = Path(config.get("implementation_artifacts", root / "_bmad-output" / "implementation-artifacts"))

    def sprint_sort_key(p: Path) -> tuple:
        # sprint-status-Beta-2026.09.14.2.yaml -> (2026, 9, 14, 2)
        m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})(?:\.(\d+))?", p.stem)
        return tuple(int(g or 0) for g in m.groups()) if m else (0, 0, 0, 0)

    sprint_files = sorted(impl.glob("sprint-status-*.yaml"), key=sprint_sort_key, reverse=True)
    sprint_status = sprint_files[0] if sprint_files else None
    if not sprint_status:
        errors.append("no sprint-status-*.yaml found in implementation_artifacts")

    release = sprint_status.stem.replace("sprint-status-", "") if sprint_status else None
    parsed = parse_sprint_status(sprint_status) if sprint_status else {"story_location": None, "entries": []}
    story_map = dict(parsed["entries"])
    backlog = [k for k, s in parsed["entries"] if s == "backlog" and not k.startswith("epic-")]

    # Resumable dev logs
    resumable = []
    devlog_root = root / "docs" / "orchestration" / "devlog"
    if devlog_root.is_dir():
        for idx in devlog_root.glob("*/*/*/index.md"):
            st = read_devlog_state(idx)
            if st and next_step(st["steps"]) not in (None, "ship"):
                # a devlog whose only remaining step is ship was explicitly
                # deferred — resuming it would hijack the next bare invocation
                resumable.append((idx.stat().st_mtime, st))
        resumable.sort(key=lambda t: t[0], reverse=True)

    # Story resolution: --story > resumable devlog > first backlog
    story_key, source = None, None
    if args.story:
        # story keys are NN-MM-slug — epic markers live in the same map but
        # are structural, not dispatchable stories. Any real story key is
        # accepted — including `proposed`: a direct pipeline run is a
        # deliberate Operator bypass of the alignment gate (policy: allow),
        # not a hole.
        if args.story in story_map and not args.story.startswith("epic-"):
            story_key, source = args.story, "arg"
        else:
            errors.append(f"--story '{args.story}' not found in development_status "
                          f"(valid: {', '.join(k for k, _ in parsed['entries'] if not k.startswith('epic-'))[:400]})")
    elif resumable:
        story_key, source = resumable[0][1]["story_key"], "resume"
    elif backlog:
        story_key, source = backlog[0], "backlog"
    else:
        errors.append("no --story given, no resumable dev log, and no backlog stories")

    # --from validation (old 15-step names alias to the merged steps)
    if args.from_step in STEP_ALIASES:
        args.from_step = STEP_ALIASES[args.from_step]
    if args.from_step and args.from_step not in STEPS:
        errors.append(f"--from '{args.from_step}' is not a valid step (valid: {', '.join(STEPS)})")

    channel, date = release_to_devlog_parts(release) if release else (None, None)
    devlog_dir = root / "docs" / "orchestration" / "devlog" / channel / date / story_key_to_devlog_name(story_key) if (channel and story_key) else None
    story_loc = root / parsed["story_location"] if parsed["story_location"] else impl / (release or "")
    story_file = story_loc / f"{story_key}.md" if story_key else None

    resume_state = None
    if resumable:
        st = resumable[0][1]
        resume_state = {"index": st["index"], "next_step": next_step(st["steps"]),
                        "ambiguous": len(resumable) > 1,
                        "candidates": [r[1]["index"] for r in resumable]}

    # package.json scripts the health check needs — surface gaps at activation
    scripts_present = {}
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            pkg_scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
        except json.JSONDecodeError:
            pkg_scripts = {}
        scripts_present = {
            "type-check": next((s for s in ("type-check", "typecheck", "tsc") if s in pkg_scripts), None),
            "lint": "lint" if "lint" in pkg_scripts else None,
            "build": "build" if "build" in pkg_scripts else None,
            "test": "test" if "test" in pkg_scripts else None,
        }

    # current uncommitted change surface — every audit + health-check consumes this
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gitpaths import normalize_changed_paths
    changed_files = []
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=30)
    if proc.returncode == 0:
        changed_files, _unparsed = normalize_changed_paths(
            proc.stdout.splitlines())

    def skill_present(name):
        # .agents/skills is the canonical tree. `cdo-*` org skills resolve
        # ONLY there — a .devin fallback would silently run the unvendored
        # upstream copy whose internal refs point at the `code-*` chain.
        # Shared module skills (bmad-*, gds-*, wdl-*) prefer .agents and
        # tolerate a .devin fallback.
        trees = (".agents",) if name.startswith("cdo-") else (".agents", ".devin")
        return any((root / t / "skills" / name / "SKILL.md").is_file()
                   for t in trees)

    def fork_drift():
        """Diff the vendored `.agents/skills/cdo-*` owner copies against their
        `.devin/skills/code-*` originals, name-normalized. Reports pairs that
        drifted (content changes beyond retargeting) or lost their copy."""
        try:
            spec = importlib.util.spec_from_file_location(
                "fork_drift", Path(__file__).resolve().parent / "fork-drift.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.check_forks(root)
        except Exception:
            return []

    preflight = {
        "owner_skills": {s: skill_present(s) for s in OWNER_SKILLS},
        "conditional_skills": {s: skill_present(s) for s in CONDITIONAL_SKILLS},
        "fork_drift": fork_drift(),
        "bun": shutil.which("bun") is not None,
        "git_repo": (root / ".git").exists(),
        "git": shutil.which("git") is not None,
        "scripts_present": scripts_present,
        "changed_files": changed_files,
    }
    warnings = []
    missing = [s for s, ok in preflight["owner_skills"].items() if not ok]
    if missing:
        warnings.append(f"missing owner skills: {', '.join(missing)} — halt before their steps")
    missing_cond = [s for s, ok in preflight["conditional_skills"].items() if not ok]
    if missing_cond:
        warnings.append(f"conditional owner skills missing: {', '.join(missing_cond)} — install them or the steps they gate degrade")
    drifted = [d for d in preflight["fork_drift"] if d["status"] != "in-sync"]
    if drifted:
        warnings.append(
            "vendored cdo-* forks drifted from .devin originals: "
            + "; ".join(f"{d['vendored']} ({d['status']})" for d in drifted)
            + " — port fixes deliberately (scripts/fork-drift.py for detail)")
    if not preflight["bun"]:
        warnings.append("bun not on PATH — health-check script will fail")
    if not preflight["git"]:
        warnings.append("git not on PATH — preflight checks, ship, and devlog snapshot will fail")

    def rel_root(p: Path | None) -> str | None:
        # Doc-facing paths land in devlog frontmatter and journal bodies —
        # emit repo-relative POSIX paths. Windows backslashes inside a
        # double-quoted YAML scalar are invalid escapes (\C) or silent
        # corruption (\b, \t).
        if p is None:
            return None
        try:
            return p.resolve().relative_to(root).as_posix()
        except ValueError:
            return p.as_posix()

    result = {
        "script": "resolve-context", "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "fail" if errors else ("warning" if warnings else "pass"),
        "errors": errors,
        "warnings": warnings,
        "project_root": str(root),
        "config": config,
        "sprint_status": rel_root(sprint_status),
        "release": release,
        "story_location": rel_root(story_loc),
        "story_key": story_key,
        "story_source": source,
        "story_status": story_map.get(story_key),
        "story_file": rel_root(story_file),
        "devlog_dir": rel_root(devlog_dir),
        "from_step": args.from_step,
        "mode": "lite" if args.lite else "full",
        "resume": resume_state,
        "backlog": backlog,
        "steps": STEPS,
        "preflight": preflight,
    }

    out = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(out, encoding="utf-8")
    else:
        print(out)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
