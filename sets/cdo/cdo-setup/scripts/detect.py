#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""cdo-setup project pre-pass — one JSON blob replacing manual globbing.

Scans a project for everything cdo-setup needs to decide fresh-install vs
upgrade and to propose configuration defaults:

  prerequisites    : git repo, official BMAD install, python/uv availability
  soft_deps        : cdo-code-e2e + owner skills, wiretext MCP, cdo-* dept modules
  conventions      : sprint yaml, story/devlog dirs, package manager, health cmds
  git_lane         : branch topology for ship-lane setup (read-only probes)
  prior_install    : existing cdo config section or orchestration tree
  prior_cdo_config : the stored cdo: section verbatim (upgrade defaults)
  gate             : "pass" | "fail" — hard prerequisite verdict for headless use

Read-only — never writes to the project.

Usage:
  uv run detect.py --project-root /path/to/project [--verbose]

Exit codes: 0=ok, 2=runtime error
"""

import argparse
import glob
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

OWNER_SKILLS = [
    "cdo-code-e2e",
    "bmad-create-story",
    "bmad-dev-story",
    "bmad-retrospective",
    "bmad-sprint-planning",
]

SKILL_TREES = [".agents/skills", "skills", ".devin/skills", ".claude/skills"]

# Root-level config keys that are settings, not module sections
NON_MODULE_KEYS = {
    "user_name",
    "communication_language",
    "document_output_language",
    "output_folder",
    "project_name",
}

PM_LOCKFILES = {
    "bun.lock": "bun",
    "bun.lockb": "bun",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "package-lock.json": "npm",
}

PM_RUN = {"bun": "bun run", "pnpm": "pnpm", "yarn": "yarn", "npm": "npm run"}

# Directories that make an orchestration tree recognizable wherever it lives
SIGNATURE_FILES = ("doctrine.md", "flow-ledger.yaml")

STORY_DIR_CANDIDATES = [
    "_bmad-output/implementation-artifacts/stories",
    "_bmad-output/stories",
    "docs/stories",
]
DEVLOG_DIR_CANDIDATES = [
    "docs/orchestration/devlog",
    "docs.orchestration.devlog",  # pre-0.2 dotted convention — detect, don't seed
    "docs/devlog",
    "devlog",
]


def parse_args():
    p = argparse.ArgumentParser(
        description="Scan a project for cdo prerequisites, conventions, and prior install state."
    )
    p.add_argument("--project-root", required=True, help="Absolute path to the project root")
    p.add_argument("-o", "--output", help="Write JSON to file instead of stdout")
    p.add_argument("--verbose", action="store_true", help="Diagnostics to stderr")
    return p.parse_args()


def list_skill_dirs(root: Path) -> dict:
    """Collect skill directory names per known skill tree — dirs with SKILL.md only."""
    found = {}
    for tree in SKILL_TREES:
        tree_path = root / tree
        if tree_path.is_dir():
            names = sorted(
                d.name for d in tree_path.iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()
            )
            if names:
                found[tree] = names
    return found


def detect_package_manager(root: Path) -> tuple:
    for lockfile, pm in PM_LOCKFILES.items():
        if (root / lockfile).exists():
            return pm, lockfile
    if (root / "package.json").exists():
        return "npm", "package.json (no lockfile)"
    return None, None


def detect_health_commands(root: Path, pm: str) -> dict:
    """Return runnable commands resolved through the detected package manager."""
    pkg = root / "package.json"
    if not pkg.exists() or not pm:
        return {}
    try:
        scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
    except (json.JSONDecodeError, OSError):
        return {}
    runner = PM_RUN.get(pm, "npm run")
    return {k: f"{runner} {k}" for k in ("test", "build", "lint", "dev") if k in scripts}


def detect_wiretext(root: Path) -> bool:
    """Look for a wiretext MCP registration in common config locations."""
    candidates = [
        ".mcp.json",
        ".cursor/mcp.json",
        ".vscode/mcp.json",
        ".windsurf/mcp_config.json",
        ".codeium/windsurf/mcp_config.json",
        "mcp_config.json",
    ]
    for rel in candidates:
        f = root / rel
        if f.is_file():
            try:
                if "wiretext" in f.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                continue
    devin = root / ".devin"
    if devin.is_dir():
        for f in devin.rglob("*.json"):
            try:
                if "wiretext" in f.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                continue
    return False


def detect_sprint_status(root: Path) -> list:
    """Scoped to _bmad-output — a bare **/ glob walks node_modules on big repos."""
    hits = []
    for pat in ("_bmad-output/**/sprint-status*.yaml", "_bmad-output/**/sprint-status*.yml"):
        for match in glob.glob(str(root / pat), recursive=True):
            p = str(Path(match).relative_to(root)).replace("\\", "/")
            if p not in hits:
                hits.append(p)
    return hits


def detect_bmad(root: Path) -> dict:
    """Parse _bmad/config.yaml properly — top-level dict keys are module sections."""
    config = root / "_bmad" / "config.yaml"
    result = {
        "installed": config.exists(),
        "modules": [],
        "has_cdo_section": False,
        "prior_cdo_config": {},
        "config_is_stub": False,
        "config_unparseable": False,
        "core_keys_present": [],
        "toml_config_present": (root / "_bmad" / "config.toml").exists(),
    }
    if not config.exists():
        return result
    try:
        data = yaml.safe_load(config.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as e:
        print(f"warn: could not parse config.yaml: {e}", file=sys.stderr)
        result["config_unparseable"] = True
        return result
    if not isinstance(data, dict) or not data:
        result["config_is_stub"] = True
        return result
    result["core_keys_present"] = sorted(
        k for k in NON_MODULE_KEYS if k in data)
    result["modules"] = sorted(
        k for k, v in data.items()
        if isinstance(v, dict) and k not in NON_MODULE_KEYS
    )
    cdo = data.get("cdo")
    if isinstance(cdo, dict):
        result["has_cdo_section"] = True
        result["prior_cdo_config"] = cdo
    return result


def detect_orchestration_tree(root: Path, bmad: dict) -> dict:
    """Find an existing orchestration tree — by configured dir or file signature.

    A prior install at a custom orchestration_dir with a deleted config section
    must still be found: any directory containing doctrine.md + flow-ledger.yaml
    is an orchestration home.
    """
    candidates = [root / "docs" / "orchestration"]
    prior_dir = (bmad.get("prior_cdo_config") or {}).get("orchestration_dir")
    if isinstance(prior_dir, str) and prior_dir:
        candidates.append(root / prior_dir.replace("{project-root}/", ""))
    candidates.extend(root.glob("docs/*"))

    found = []
    for cand in candidates:
        if cand.is_dir() and all((cand / sig).exists() for sig in SIGNATURE_FILES):
            rel = str(cand.relative_to(root)).replace("\\", "/")
            if rel not in found:
                found.append(rel)
    return {"found": found}


def detect_git_lane(root: Path) -> dict:
    """Branch topology for ship-lane setup — read-only git probes.

    ensure-lane.py (and the setup prompt) use this to decide whether the
    configured ship_target branch needs creating, whether checking it out
    is safe, and whether a remote already carries it."""
    out = {
        "current_branch": None,
        "local_branches": [],
        "remote_branches": [],
        "remotes": [],
        "has_commits": False,
    }
    if not (root / ".git").exists() or not shutil.which("git"):
        return out
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            capture_output=True, text=True,
        )
        out["has_commits"] = head.returncode == 0
        cur = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        out["current_branch"] = cur.stdout.strip() or None
        lbs = subprocess.run(
            ["git", "-C", str(root), "branch", "--format=%(refname:short)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        out["local_branches"] = lbs.stdout.split()
        rbs = subprocess.run(
            ["git", "-C", str(root), "branch", "-r", "--format=%(refname:short)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        out["remote_branches"] = [
            b for b in rbs.stdout.split()
            if "/" in b and not b.endswith("/HEAD")
        ]
        rem = subprocess.run(
            ["git", "-C", str(root), "remote"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        out["remotes"] = rem.stdout.split()
    except OSError:
        pass
    return out


def first_existing(root: Path, candidates: list) -> str:
    for c in candidates:
        if (root / c).exists():
            return c
    return ""


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"error: project root not found: {root}", file=sys.stderr)
        sys.exit(2)

    skills = list_skill_dirs(root)
    all_skills = sorted({s for names in skills.values() for s in names})
    owner_present = [s for s in OWNER_SKILLS if s in all_skills]
    CORE_CDO = {"cdo-setup", "cdo-orchestrator", "cdo-align", "cdo-review",
                "cdo-batch", "cdo-watch", "cdo-handoff"}
    dept_modules = sorted(
        s for s in all_skills if s.startswith("cdo-") and s not in CORE_CDO
    )
    # srm-synced external modules are dept delegate pools — group bmad-bus-*
    # skills by their module segment; other prefixes (wdl-*, etc.) report as
    # their own source family
    synced_modules = sorted({
        s.split("-")[2] for s in all_skills
        if s.startswith("bmad-bus-") and len(s.split("-")) > 2
    })
    if any(s.startswith("wdl-") for s in all_skills):
        synced_modules.append("wondelai")
    synced_skills = sorted(s for s in all_skills
                           if s.startswith("bmad-bus-") or s.startswith("wdl-"))

    pm, pm_evidence = detect_package_manager(root)
    bmad = detect_bmad(root)
    orch = detect_orchestration_tree(root, bmad)
    prior_install = bmad["has_cdo_section"] or bool(orch["found"])

    git_ok = (root / ".git").exists()
    warnings = []
    if bmad["installed"] and bmad["config_is_stub"]:
        warnings.append("_bmad/config.yaml exists but has no module sections (stub)")
    if bmad["toml_config_present"]:
        warnings.append("_bmad/config.toml also present — confirm which config format BMAD reads")

    gate_reasons = []
    if not git_ok:
        gate_reasons.append("no .git directory — cdo requires a git repo")
    if not bmad["installed"]:
        gate_reasons.append("_bmad/config.yaml missing — install official BMAD first")
    elif bmad["config_unparseable"]:
        gate_reasons.append("_bmad/config.yaml is not parseable YAML — fix it before installing")
    elif bmad["config_is_stub"]:
        gate_reasons.append("_bmad/config.yaml has no module sections (stub) — install official BMAD first")

    result = {
        "script": "cdo-detect",
        "version": "1.1.0",
        "project_root": str(root),
        "gate": "fail" if gate_reasons else "pass",
        "gate_reasons": gate_reasons,
        "prerequisites": {
            "git_repo": git_ok,
            "bmad_installed": bmad["installed"],
            "bmad_modules": bmad["modules"],
            "python": bool(shutil.which("python3") or shutil.which("python")),
            "uv": bool(shutil.which("uv")),
            "bun": bool(shutil.which("bun")),
        },
        "soft_deps": {
            "owner_skills_present": owner_present,
            "owner_skills_missing": [s for s in OWNER_SKILLS if s not in owner_present],
            "wiretext_mcp": detect_wiretext(root),
            "dept_modules": dept_modules,
            "synced_modules": synced_modules,
            "synced_skills": synced_skills,
        },
        "conventions": {
            "sprint_status_files": detect_sprint_status(root),
            "story_dir": first_existing(root, STORY_DIR_CANDIDATES),
            "devlog_dir": first_existing(root, DEVLOG_DIR_CANDIDATES),
            "package_manager": pm,
            "pm_evidence": pm_evidence,
            "health_commands": detect_health_commands(root, pm),
            "has_package_json": (root / "package.json").exists(),
        },
        "git_lane": detect_git_lane(root),
        "prior_install": prior_install,
        "prior_cdo_config": bmad["prior_cdo_config"],
        "core_keys_present": bmad["core_keys_present"],
        "orchestration_trees_found": orch["found"],
        "warnings": warnings,
        "mode": "upgrade" if prior_install else "fresh-install",
        "status": "pass",
    }

    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        if args.verbose:
            print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
