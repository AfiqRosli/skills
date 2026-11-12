#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""audit.py — docs visibility audit.

Walks the detected docs root and checks every page against the nav contract
from docs-profile.yaml:

  orphans      — pages no nav/sidebar entry can reach (exist but invisible)
  broken_nav   — nav entries pointing at files that don't exist
  covered      — pages reachable via nav entries or an auto_zone

nav_kind drives the check: config/yaml-nav/gitbook-summary get real parsing;
filesystem/none report full coverage (file presence IS visibility).

Usage:
  uv run audit.py --orchestration-dir /path/docs/orchestration \
      --project-root /path [-o result.json]

Exit codes: 0=audited, 1=no profile (run detect first), 2=runtime error
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".vitepress", "public"}

# nav references — "link:" entries (vitepress/starlight/docusaurus-style),
# markdown links (SUMMARY.md), and href-style entries
LINK_RE = re.compile(r'(?:link|href|slug)\s*:\s*["\']([^"\']+)["\']')
MD_LINK_RE = re.compile(r'\[[^\]]*\]\(([^)]+\.mdx?)\)')


def parse_args():
    p = argparse.ArgumentParser(description="Audit docs visibility vs nav.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--project-root", required=True)
    p.add_argument("-o", "--output")
    return p.parse_args()


def load_profile(orch: Path):
    ppath = orch / "docs-profile.yaml"
    if not ppath.is_file():
        return None
    return yaml.safe_load(ppath.read_text(encoding="utf-8")) or {}


def docs_files(docs_root: Path):
    """All .md/.mdx pages under docs_root, keyed by their URL-ish stem path."""
    files = {}
    for ext in ("*.md", "*.mdx"):
        for f in docs_root.glob(f"**/{ext}"):
            if any(part in SKIP_DIRS for part in f.parts):
                continue
            rel = f.relative_to(docs_root).as_posix()
            stem = rel[: -len(f.suffix)]
            files[stem] = rel
    return files


def nav_refs_vitepress(nav_path: Path):
    """link: values from a VitePress/Starlight-style TS config."""
    try:
        text = nav_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return {m for m in LINK_RE.findall(text) if m.startswith("/")}


def nav_refs_mkdocs(nav_path: Path, docs_root: Path):
    """nav: entries from mkdocs.yml — values are paths relative to docs_dir."""
    try:
        cfg = yaml.safe_load(nav_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return set()

    refs = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str) and node.endswith((".md", ".mdx")):
            refs.add("/" + node.rsplit(".", 1)[0])

    walk(cfg.get("nav") or [])
    return refs


def nav_refs_summary(nav_path: Path, docs_root: Path):
    """Markdown links in a GitBook SUMMARY.md."""
    try:
        text = nav_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    refs = set()
    for link in MD_LINK_RE.findall(text):
        link = link.lstrip("./").lstrip("/")
        stem = link.rsplit(".", 1)[0] if link.endswith((".md", ".mdx")) else link
        refs.add("/" + stem)
    return refs


def normalize(link: str):
    """'/a/b/' → 'a/b' (index-style), '/a/b' → 'a/b'. Returns stem form."""
    link = link.split("#")[0].split("?")[0].strip()
    link = link.lstrip("/")
    if link.endswith("/"):
        link = link + "index"
    if link.endswith(".mdx"):
        link = link[:-4]
    elif link.endswith(".md"):
        link = link[:-3]
    return link.rstrip("/") or "index"


def covers(stem: str, ref_stems: set, auto_zones):
    """Is docs file `stem` reachable? Nav ref match, index-match, or under an
    auto_zone (a dir the config reads from disk to generate nav)."""
    if any(stem == z or stem.startswith(z + "/") for z in auto_zones):
        return True
    if stem in ref_stems:
        return True
    # 'a/b/index' and 'a/b/README' are the directory index — covered by a
    # nav ref to 'a/b' or 'a/b/index'; 'a/b' likewise covered by 'a/b/index'
    for suffix in ("/index", "/README"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem in ref_stems or stem + "/index" in ref_stems or \
            stem + "/README" in ref_stems:
        return True
    return False


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    root = Path(args.project_root).resolve()

    profile = load_profile(orch)
    if not profile:
        print(json.dumps({
            "status": "blocked",
            "errors": ["docs-profile.yaml missing — run cdo-docs detect first"],
        }))
        sys.exit(1)

    framework = profile.get("framework")
    docs_root_rel = profile.get("docs_root")
    nav_kind = profile.get("nav_kind")
    auto_zones = [z.strip("/") for z in (profile.get("auto_zones") or [])]

    if framework in (None, "none") or not docs_root_rel:
        result = {"status": "no_docs", "framework": framework,
                  "orphans": [], "broken_nav": [],
                  "note": "no docs stack detected — nothing to audit"}
        print(json.dumps(result, indent=2))
        return

    docs_root = root / docs_root_rel
    if not docs_root.is_dir():
        print(json.dumps({"errors": [
            f"profile docs_root missing on disk: {docs_root_rel}"]}))
        sys.exit(2)

    files = docs_files(docs_root)

    # internal zones — dirs that live under docs_root but aren't pages:
    # _/.-prefixed dirs (templates, drafts), plus the orchestration home when
    # the nav doesn't surface it. Once nav links reach into orchestration it
    # stops being internal and its unlinked files count as real orphans.
    nav_path = root / str(profile.get("nav_config") or "")
    if nav_kind == "yaml-nav":
        refs = nav_refs_mkdocs(nav_path, docs_root)
    elif nav_kind == "gitbook-summary":
        refs = nav_refs_summary(nav_path, docs_root)
    elif nav_kind in ("filesystem", "none"):
        refs = set()
    else:  # config (vitepress, docusaurus custom, starlight)
        refs = nav_refs_vitepress(nav_path)
    ref_stems = {normalize(r) for r in refs}

    internal_zones = {
        rel.split("/")[0] for rel in files.values()
        if rel.split("/")[0].startswith(("_", "."))}
    try:
        rel_orch = orch.relative_to(docs_root).as_posix().strip("/")
        orch_in_nav = any(
            s == rel_orch or s.startswith(rel_orch + "/") for s in ref_stems)
        if rel_orch and not rel_orch.startswith("..") and not orch_in_nav:
            internal_zones.add(rel_orch)
    except ValueError:
        pass

    def is_internal(stem):
        return stem == "index" or any(
            stem == z or stem.startswith(z + "/") for z in internal_zones)

    files = {s: r for s, r in files.items() if not is_internal(s)}

    if nav_kind in ("filesystem", "none"):
        result = {"status": "audited", "framework": framework,
                  "nav_kind": nav_kind, "total_pages": len(files),
                  "covered": len(files), "orphans": [], "broken_nav": [],
                  "internal_zones": sorted(internal_zones),
                  "note": "filesystem nav — page presence is visibility"}
        print(json.dumps(result, indent=2))
        return

    orphans = sorted(
        rel for stem, rel in files.items()
        if not covers(stem, ref_stems, auto_zones))

    def resolves(link):
        stem = normalize(link)
        # dir-index links normalize to a/b/index — also accept README as the
        # directory index (VitePress serves it that way)
        if stem.endswith("/index"):
            base = stem[:-6]
            return (base in files or stem in files
                    or base + "/README" in files)
        return (stem in files or stem + "/index" in files
                or stem + "/README" in files)

    broken_nav = sorted(r for r in refs if not resolves(r))

    result = {
        "status": "audited",
        "framework": framework,
        "docs_root": docs_root_rel,
        "total_pages": len(files),
        "covered": len(files) - len(orphans),
        "orphans": orphans,
        "broken_nav": sorted(set(broken_nav)),
        "auto_zones": auto_zones,
        "internal_zones": sorted(internal_zones),
    }
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
