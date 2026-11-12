#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""detect-docs.py — detect the project's documentation stack.

Probes the codebase for the docs framework (VitePress, Docusaurus, MkDocs,
Astro Starlight, Nuxt Content, GitBook, or plain markdown) and emits a
**docs profile**: the contract for how a page becomes *visible* — docs root,
the file that controls nav/sidebar, and the commands that verify it.

Writes `{orchestration_dir}/docs-profile.yaml` when --orchestration-dir is
given. Read-only on the project otherwise.

Usage:
  uv run detect-docs.py --project-root /path [--orchestration-dir PATH]
      [-o result.json]

Exit codes: 0=detected (framework may be 'none'), 2=runtime error
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

PM_LOCKFILES = {
    "bun.lock": "bun",
    "bun.lockb": "bun",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "package-lock.json": "npm",
}
PM_RUN = {"bun": "bun run", "pnpm": "pnpm", "yarn": "yarn", "npm": "npm run"}

# dirs that never hold a docs framework config — keeps glob probes fast and
# vendor-junk free. (.vitepress is deliberately NOT here: it's the signal.)
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".output"}

# A config that glob-reads a docs subdir (readdirSync + new URL) generates its
# own nav for that dir — pages there are visible with no manual registration.
AUTO_ZONE_RE = re.compile(
    r'new URL\(\s*["\']\.\./([^"\']+)["\']\s*,\s*import\.meta\.url\s*\)')


def parse_args():
    p = argparse.ArgumentParser(description="Detect the project docs stack.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir",
                   help="when given, writes docs-profile.yaml here")
    p.add_argument("-o", "--output")
    return p.parse_args()


def find(root: Path, patterns):
    """First existing match of glob patterns under root, skipping junk dirs."""
    hits = find_all(root, patterns)
    return hits[0] if hits else None


def find_all(root: Path, patterns):
    """All existing matches across all patterns, sorted — for multi-tree
    awareness (don't stop at the first matching depth)."""
    hits = set()
    for pat in patterns:
        hits.update(p for p in root.glob(pat)
                    if not any(part in SKIP_DIRS for part in p.parts))
    return sorted(hits)


def package_json(root: Path):
    pj = root / "package.json"
    if not pj.is_file():
        return {}
    try:
        return json.loads(pj.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def detect_pm(root: Path):
    for lockfile, pm in PM_LOCKFILES.items():
        if (root / lockfile).is_file():
            return pm
    return "npm" if (root / "package.json").is_file() else None


def detect_commands(root: Path, pm: str, framework: str):
    """Docs dev/build commands — package.json scripts first, framework
    CLIs as fallback. Values stay run-book ready (e.g. 'bun run docs:build')."""
    scripts = (package_json(root).get("scripts") or {})
    run = PM_RUN.get(pm, "npm run")

    def script_matching(*needles):
        for name, cmd in scripts.items():
            if all(n in f"{name} {cmd}" for n in needles):
                return f"{run} {name}"
        return None

    dev = build = None
    if framework == "vitepress":
        dev = script_matching("vitepress", "dev") or script_matching("docs", "dev")
        build = script_matching("vitepress", "build") or script_matching("docs", "build")
    elif framework == "docusaurus":
        dev = script_matching("docusaurus", "start") or script_matching("docs", "dev")
        build = script_matching("docusaurus", "build") or script_matching("docs", "build")
    elif framework == "mkdocs":
        dev, build = "mkdocs serve", "mkdocs build"
    elif framework == "astro-starlight":
        dev = script_matching("astro", "dev") or ("npm run dev" if pm else None)
        build = script_matching("astro", "build") or ("npm run build" if pm else None)
    elif framework == "nuxt-content":
        dev = script_matching("nuxt", "dev") or ("npm run dev" if pm else None)
        build = script_matching("nuxt", "build") or ("npm run build" if pm else None)
    else:
        dev = script_matching("docs", "dev") or script_matching("docs", "serve")
        build = script_matching("docs", "build")
    return dev, build


def vitepress_auto_zones(config_path: Path, docs_root: Path):
    """Dirs a VitePress config reads from disk to generate nav — pages under
    them are visible without a manual sidebar entry."""
    try:
        text = config_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if "readdirSync" not in text:
        return []
    zones = []
    for rel in AUTO_ZONE_RE.findall(text):
        # "../orchestration/devlog" is relative to the .vitepress dir → docs_root
        resolved = (config_path.parent / ".." / rel).resolve()
        try:
            zones.append(str(resolved.relative_to(docs_root.resolve()))
                         .replace("\\", "/").rstrip("/"))
        except ValueError:
            continue
    return sorted(set(zones))


def detect(root: Path):
    """Probe in framework-priority order; first hit wins."""
    evidence = []
    pj = package_json(root)
    deps = {**(pj.get("dependencies") or {}), **(pj.get("devDependencies") or {})}

    # VitePress — the .vitepress/config.* file is the tell; the dir holding
    # .vitepress is the docs root (VitePress source dir). Multiple configs
    # mean multiple docs trees (monorepo) — first is primary, rest reported.
    vps = find_all(root, ["*/.vitepress/config.*", ".vitepress/config.*",
                          "*/*/.vitepress/config.*",
                          "*/*/*/.vitepress/config.*"])
    if vps:
        vp = vps[0]
        docs_root = vp.parent.parent
        evidence.append(f"vitepress config: {vp.relative_to(root)}")
        if "vitepress" not in deps:
            evidence.append("note: 'vitepress' not in package.json deps")
        extra = [str(c.parent.parent.relative_to(root)).replace("\\", "/")
                 for c in vps[1:]]
        if extra:
            evidence.append(
                f"additional docs trees not covered by this profile: {extra}")
        return {
            "framework": "vitepress",
            "docs_root": str(docs_root.relative_to(root)).replace("\\", "/"),
            "nav_config": str(vp.relative_to(root)).replace("\\", "/"),
            "nav_kind": "config",
            "auto_zones": vitepress_auto_zones(vp, docs_root),
            "additional_roots": extra,
        }, evidence

    # Docusaurus — config file + dep. Custom sidebars.* means manual nav;
    # absent means autogenerated filesystem nav.
    dc = find(root, ["docusaurus.config.*", "*/docusaurus.config.*"])
    if dc and any(d.startswith("@docusaurus/") for d in deps):
        sidebars = find(root, ["sidebars.*", "*/sidebars.*"])
        evidence.append(f"docusaurus config: {dc.relative_to(root)}")
        return {
            "framework": "docusaurus",
            "docs_root": "docs",
            "nav_config": str(sidebars.relative_to(root)).replace("\\", "/")
                          if sidebars else None,
            "nav_kind": "config" if sidebars else "filesystem",
            "auto_zones": [] if sidebars else ["docs"],
            "additional_roots": [],
        }, evidence

    # MkDocs — mkdocs.yml at root; nav lives inside it.
    mk = find(root, ["mkdocs.yml", "mkdocs.yaml", "*/mkdocs.yml", "*/mkdocs.yaml"])
    if mk:
        docs_dir = "docs"
        try:
            cfg = yaml.safe_load(mk.read_text(encoding="utf-8")) or {}
            docs_dir = str(cfg.get("docs_dir") or "docs")
        except yaml.YAMLError:
            pass
        evidence.append(f"mkdocs config: {mk.relative_to(root)}")
        return {
            "framework": "mkdocs",
            "docs_root": docs_dir,
            "nav_config": str(mk.relative_to(root)).replace("\\", "/"),
            "nav_kind": "yaml-nav",
            "auto_zones": [],
            "additional_roots": [],
        }, evidence

    # Astro Starlight — astro config + starlight dep; sidebar lives in the
    # astro config (or is filesystem-autogenerated per dir).
    ac = find(root, ["astro.config.*", "*/astro.config.*"])
    if ac and "@astrojs/starlight" in deps:
        evidence.append(f"astro config: {ac.relative_to(root)}")
        return {
            "framework": "astro-starlight",
            "docs_root": "src/content/docs",
            "nav_config": str(ac.relative_to(root)).replace("\\", "/"),
            "nav_kind": "config",
            "auto_zones": [],
            "additional_roots": [],
        }, evidence

    # Nuxt Content — filesystem nav; page presence is visibility.
    if "@nuxt/content" in deps and (root / "content").is_dir():
        evidence.append("@nuxt/content dep + content/ dir")
        return {
            "framework": "nuxt-content",
            "docs_root": "content",
            "nav_config": None,
            "nav_kind": "filesystem",
            "auto_zones": ["content"],
            "additional_roots": [],
        }, evidence

    # GitBook — SUMMARY.md is the nav contract.
    gb = find(root, ["SUMMARY.md", "docs/SUMMARY.md", "*/SUMMARY.md"])
    if gb and (root / ".gitbook.yaml").is_file():
        evidence.append(f"gitbook summary: {gb.relative_to(root)}")
        return {
            "framework": "gitbook",
            "docs_root": str(gb.parent.relative_to(root)).replace("\\", "/") or ".",
            "nav_config": str(gb.relative_to(root)).replace("\\", "/"),
            "nav_kind": "gitbook-summary",
            "auto_zones": [],
            "additional_roots": [],
        }, evidence

    # Plain markdown — any docs dir with .md/.mdx files; no visibility contract.
    for cand in ("docs", "documentation", "doc"):
        d = root / cand
        if d.is_dir() and any(
                p for ext in ("*.md", "*.mdx") for p in d.glob(f"**/{ext}")
                if not any(part in SKIP_DIRS for part in p.parts)):
            evidence.append(f"markdown dir: {cand}/")
            return {
                "framework": "plain",
                "docs_root": cand,
                "nav_config": None,
                "nav_kind": "none",
                "auto_zones": [cand],
                "additional_roots": [],
            }, evidence

    return {"framework": "none", "docs_root": None, "nav_config": None,
            "nav_kind": "none", "auto_zones": [], "additional_roots": []}, evidence


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(json.dumps({"errors": [f"project root not found: {root}"]}))
        sys.exit(2)

    base, evidence = detect(root)
    pm = detect_pm(root)
    dev, build = detect_commands(root, pm, base["framework"])

    profile = {
        **base,
        "dev_command": dev,
        "build_command": build,
        "package_manager": pm,
        "detected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evidence": evidence,
    }

    written = None
    if args.orchestration_dir:
        orch = Path(args.orchestration_dir)
        if not orch.is_absolute():
            orch = root / orch
        orch.mkdir(parents=True, exist_ok=True)
        target = orch / "docs-profile.yaml"
        target.write_text(
            "# Docs profile — detected by cdo-docs detect-docs.py.\n"
            "# Re-run `cdo-docs detect` when the docs stack changes.\n"
            + yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
        written = str(target)

    result = {"status": "detected", "profile": profile, "profile_path": written}
    blob = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(blob, encoding="utf-8")
    else:
        print(blob)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
