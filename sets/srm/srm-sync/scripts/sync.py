#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""srm-sync engine: maps external skill repos into .agents/skills/ as prefixed,
BMad-structured skills.

Never modifies source repos. The only ops run on a source are `git clone`
(first fetch into skills_repo_root) and `git pull --ff-only` when enabled.

Commands:
  sync    Materialize all (or one) registered repos into the skills dir.
          --clone-missing fetches registered repos that aren't checked out.
  detect  Inspect a repo path and print suggested registry entry as JSON.
  clone   Clone a remote URL into skills_repo_root/<owner>/<repo>.
  add     Append a repo entry to the registry (prefix must be given).
  remove  Drop a repo from the registry; with --delete-skills also removes its skills.
  list    Print the registry.
  missing Report which registered repos are/aren't checked out (read-only).
  status  Report freshness of mapped skills vs their source commit.

All commands print a JSON result to stdout. Non-zero exit = fatal error.
"""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ORIGIN = ".srm-origin"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


# ---------- config / registry ----------

def load_yaml(path):
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def save_yaml(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )


def resolve(p, vars_):
    for k, v in vars_.items():
        p = p.replace("{" + k + "}", str(v))
    return p


def module_vars(project_root):
    cfg = load_yaml(Path(project_root) / "_bmad" / "config.yaml")
    mod = cfg.get("srm", {}) or {}
    return {
        "skills_repo_root": resolve(str(mod.get("skills_repo_root", "")), {"project-root": project_root}),
        "git_pull": str(mod.get("git_pull", "yes")).lower() in ("yes", "true", "1"),
        "project-root": project_root,
    }


def registry_load(path):
    data = load_yaml(path)
    data.setdefault("repos", [])
    return data


def registry_get(data, name):
    for r in data["repos"]:
        if r["name"].lower() == name.lower():
            return r
    return None


# ---------- git ----------

def git(repo_path, *args):
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            capture_output=True, text=True, timeout=120,
        )
        return out.returncode, (out.stdout or "").strip(), (out.stderr or "").strip()
    except Exception as e:  # noqa: BLE001
        return -1, "", str(e)


def git_head(repo_path):
    rc, out, _ = git(repo_path, "rev-parse", "--short", "HEAD")
    return out if rc == 0 else None


def is_git_repo(repo_path):
    return (Path(repo_path) / ".git").exists()


# ---------- naming / frontmatter ----------

def slug(s):
    s = s.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    return re.sub(r"-{2,}", "-", s).strip("-")


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, text[m.end():]


def dump_frontmatter(fm, body):
    head = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=200).strip()
    return f"---\n{head}\n---\n\n{body.lstrip()}"


def read_text(p):
    try:
        return Path(p).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Path(p).read_text(encoding="utf-8", errors="replace")


def first_line(text):
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line and not line.startswith("---") and ":" not in line[:12]:
            return re.sub(r"[*_`>]+", "", line)[:200]
    return ""


# ---------- symlink-ish resolution (Windows checkouts materialize git
# symlinks as plain files containing the target path) ----------

def deref(path, repo_root):
    p = Path(path)
    if p.is_dir():
        return p
    if p.is_file() and p.stat().st_size < 400:
        target = read_text(p).strip()
        if target and "\n" not in target and not target.startswith("---"):
            cand = (p.parent / target).resolve()
            if cand.is_dir():
                return cand
            cand = (Path(repo_root) / target).resolve()
            if cand.is_dir():
                return cand
    return p


def copytree(src, dst):
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    def ignore(_d, names):
        return [n for n in names if n in SKIP_DIRS]
    shutil.copytree(src, dst, ignore=ignore)


# ---------- origin markers ----------

def write_origin(skill_dir, repo_name, source_rel, commit):
    marker = {
        "repo": repo_name,
        "source": source_rel,
        "commit": commit,
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    Path(skill_dir, ORIGIN).write_text(json.dumps(marker, indent=2), encoding="utf-8")


def read_origin(skill_dir):
    p = Path(skill_dir) / ORIGIN
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return None


def emit(skill_dir, files):
    """Write files {name: content} into skill_dir, replacing dir contents."""
    skill_dir = Path(skill_dir)
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True)
    for name, content in files.items():
        (skill_dir / name).write_text(content, encoding="utf-8")


def claimable(skill_dir):
    """True if the dir doesn't exist or was created by srm-sync."""
    p = Path(skill_dir)
    return not p.exists() or (p / ORIGIN).exists()


# ---------- adaptation: emit BMad-structured skills ----------

def emit_flat_skill(repo, prefix, src_dir, orig_name, skills_dir, commit, report):
    """A folder containing SKILL.md -> <prefix>-<name>/ with rewritten frontmatter."""
    target = Path(skills_dir) / f"{prefix}-{slug(orig_name)}"
    if not claimable(target):
        report["skipped"].append({"target": target.name, "reason": "exists, not srm-managed"})
        return
    copytree(src_dir, target)
    skill_md = target / "SKILL.md"
    fm, body = parse_frontmatter(read_text(skill_md))
    fm["name"] = target.name
    fm.setdefault("description", first_line(body) or f"Skill imported from {repo['name']}")
    skill_md.write_text(dump_frontmatter(fm, body), encoding="utf-8")
    write_origin(target, repo["name"], str(src_dir), commit)
    report["mapped"].append({"skill": target.name, "kind": "skill"})


def emit_agent(repo, prefix, source_name, agents_dir, agent_md, router_name, skills_dir, commit, report):
    """BMad agent (<id>.md + optional <id>.agent.yaml) -> own skill folder."""
    aid = agent_md.stem
    ayaml = agents_dir / f"{aid}.agent.yaml"
    meta = {}
    if ayaml.exists():
        meta = (load_yaml(ayaml).get("agent", {}) or {}).get("metadata", {}) or {}
    text = read_text(agent_md)
    m = re.search(r'<agent[^>]*\bname="([^"]*)"', text)
    persona = m.group(1) if m else meta.get("name", aid)
    title = meta.get("title", aid.replace("-", " ").title())
    desc = meta.get("description") or parse_frontmatter(text)[0].get("description") or title
    icon = meta.get("icon", "")

    target = Path(skills_dir) / f"{prefix}-{slug(source_name)}-{slug(aid)}"
    if not claimable(target):
        report["skipped"].append({"target": target.name, "reason": "exists, not srm-managed"})
        return
    note = (
        f"\n\n---\n_Imported by srm-sync from `{repo['name']}` (`{source_name}/agents/{aid}.md`). "
        f"Module resources (workflows, tasks, templates, data) live in the sibling "
        f"skill folder `../{router_name}/`._\n"
    )
    _, body = parse_frontmatter(text)
    skill = dump_frontmatter({"name": target.name, "description": str(desc)}, (body or text) + note)
    toml = (
        "# DO NOT EDIT -- regenerated on every srm-sync run.\n\n[agent]\n"
        f'code="{aid}"\nname="{persona}"\ntitle="{title}"\nicon="{icon}"\n'
        f'description="{str(desc).replace(chr(34), chr(39))}"\n'
    )
    emit(target, {"SKILL.md": skill, "customize.toml": toml})
    write_origin(target, repo["name"], str(agent_md), commit)
    report["mapped"].append({"skill": target.name, "kind": "agent", "persona": persona})
    return {"id": aid, "persona": persona, "title": title, "desc": desc}


def emit_workflow(repo, prefix, source_name, wf_dir, router_name, skills_dir, commit, report):
    wid = wf_dir.name
    target = Path(skills_dir) / f"{prefix}-{slug(source_name)}-{slug(wid)}"
    if not claimable(target):
        report["skipped"].append({"target": target.name, "reason": "exists, not srm-managed"})
        return
    desc = f"Workflow '{wid}' imported from {repo['name']}:{source_name}"
    for cand in ("workflow.yaml",):
        wy = wf_dir / cand
        if wy.exists():
            wmeta = load_yaml(wy)
            desc = (wmeta or {}).get("description", desc)
            break
    body = (
        f"# {wid} (workflow)\n\nImported by srm-sync from `{repo['name']}` "
        f"(`{source_name}/workflows/{wid}/`).\n\n"
        f"Load and follow the workflow instructions in the sibling skill folder "
        f"`../{router_name}/workflows/{wid}/` — start with `workflow.md` or "
        f"`workflow.xml` (whichever exists); step files live under `steps/`.\n"
    )
    emit(target, {"SKILL.md": dump_frontmatter({"name": target.name, "description": str(desc)}, body)})
    write_origin(target, repo["name"], str(wf_dir), commit)
    report["mapped"].append({"skill": target.name, "kind": "workflow"})
    return {"id": wid, "desc": desc}


def emit_persona_md(repo, prefix, md_path, rel, skills_dir, commit, report):
    """Loose persona/command .md (e.g. .claude/commands/**/agents/*.md) -> agent skill."""
    pid = md_path.stem
    text = read_text(md_path)
    fm, _ = parse_frontmatter(text)
    desc = fm.get("description") or first_line(text) or f"Persona imported from {repo['name']}"
    target = Path(skills_dir) / f"{prefix}-{slug(pid)}"
    if not claimable(target):
        report["skipped"].append({"target": target.name, "reason": "exists, not srm-managed"})
        return
    note = f"\n\n---\n_Imported by srm-sync from `{repo['name']}` (`{rel}`)._\n"
    _, body = parse_frontmatter(text)
    emit(target, {"SKILL.md": dump_frontmatter({"name": target.name, "description": str(desc)}, (body or text) + note)})
    write_origin(target, repo["name"], str(md_path), commit)
    report["mapped"].append({"skill": target.name, "kind": "persona"})


def materialize_grouped(repo, src_path, rel, skills_dir, commit, report):
    """A BMad module dir (agents/ + workflows/) -> router skill + per-item skills."""
    source_name = Path(src_path).name
    router_name = f"{repo['prefix']}-{slug(source_name)}"
    router_dir = Path(skills_dir) / router_name
    if not claimable(router_dir):
        report["skipped"].append({"target": router_name, "reason": "exists, not srm-managed"})
        return
    copytree(src_path, router_dir)

    mod = load_yaml(Path(src_path) / "module.yaml")
    mod_title = mod.get("name") or source_name
    agents_dir = Path(src_path) / "agents"
    wf_root = Path(src_path) / "workflows"
    agents, workflows = [], []

    if agents_dir.is_dir():
        for amd in sorted(agents_dir.glob("*.md")):
            a = emit_agent(repo, repo["prefix"], source_name, agents_dir, amd, router_name, skills_dir, commit, report)
            if a:
                agents.append(a)
    if wf_root.is_dir():
        for wdir in sorted(p for p in wf_root.iterdir() if p.is_dir() and not p.name.startswith("_")):
            w = emit_workflow(repo, repo["prefix"], source_name, wdir, router_name, skills_dir, commit, report)
            if w:
                workflows.append(w)

    rows = "\n".join(
        f"| `{router_name}-{slug(a['id'])}` | {a['persona']} — {a['title']} |" for a in agents
    )
    wrows = "\n".join(
        f"| `{router_name}-{slug(w['id'])}` | {w['desc']} |" for w in workflows
    )
    body = (
        f"# {mod_title}\n\nImported by srm-sync from `{repo['name']}` (`{rel}`). "
        "This folder is a verbatim copy of the source module — agents, workflows, "
        "tasks, templates and config keep their original relative layout.\n\n"
        "Each agent and workflow is also installed as an individual skill.\n\n"
        f"## Agents ({len(agents)})\n\n| Skill | Persona |\n|---|---|\n{rows}\n\n"
        f"## Workflows ({len(workflows)})\n\n| Skill | Description |\n|---|---|\n{wrows}\n\n"
        "## Note\n\nAgents may reference `{project-root}/_bmad/<module>/config.yaml` at "
        "runtime — if a mapped agent asks for config that doesn't exist, register the "
        "module's config or provide values directly.\n"
    )
    desc = mod.get("description") or f"Router for the {source_name} module imported from {repo['name']} — {len(agents)} agents, {len(workflows)} workflows."
    (router_dir / "SKILL.md").write_text(
        dump_frontmatter({"name": router_name, "description": str(desc)}, body), encoding="utf-8"
    )
    write_origin(router_dir, repo["name"], str(src_path), commit)
    report["mapped"].append({"skill": router_name, "kind": "router", "agents": len(agents), "workflows": len(workflows)})


def materialize_flat(repo, path, rel, repo_root, skills_dir, commit, report):
    """A dir of */SKILL.md skills -> prefixed copies."""
    path = Path(path)
    count = 0
    for child in sorted(path.iterdir()):
        real = deref(child, repo_root)
        if real.is_dir() and (real / "SKILL.md").exists():
            emit_flat_skill(repo, repo["prefix"], real, child.name, skills_dir, commit, report)
            count += 1
    if count == 0:
        report["warnings"].append(f"{repo['name']}:{rel} — no */SKILL.md children found")


def materialize_claude(repo, claude_dir, rel, repo_root, skills_dir, commit, report):
    """A `.claude` skills path (e.g. Finance-Guru): flat skills/ + loose personas."""
    skills_sub = Path(claude_dir) / "skills"
    if skills_sub.is_dir():
        materialize_flat(repo, skills_sub, f"{rel}/skills", repo_root, skills_dir, commit, report)
    seen = set()
    agents_sub = Path(claude_dir) / "agents"
    if agents_sub.is_dir():
        for md in sorted(agents_sub.glob("*.md")):
            emit_persona_md(repo, repo["prefix"], md, f"{rel}/agents/{md.name}", skills_dir, commit, report)
            seen.add(md.stem)
    cmd_root = Path(claude_dir) / "commands"
    if cmd_root.is_dir():
        for md in sorted(cmd_root.rglob("*.md")):
            if "agents" in md.parts and md.stem not in seen:
                prel = md.relative_to(repo_root)
                emit_persona_md(repo, repo["prefix"], md, str(prel), skills_dir, commit, report)


# ---------- help csv ----------

def update_help_csv(csv_path, repo_label, rows):
    """Anti-zombie merge: drop rows where module == repo_label, append new ones."""
    csv_path = Path(csv_path)
    existing = []
    header = None
    if csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            for row in r:
                if header is None:
                    header = row
                    continue
                if row and row[0] != repo_label:
                    existing.append(row)
    if header is None:
        header = ["module", "skill", "display-name", "menu-code", "description",
                  "action", "args", "phase", "after", "before", "required",
                  "output-location", "outputs"]
    existing = [r for r in existing if r[:1] != [repo_label]]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(existing)
        for r in rows:
            w.writerow(r)


def help_rows_for(repo, report):
    label = repo["name"]
    rows = [[label, "_meta"] + [""] * 9 + ["false", "", ""]]
    for m in report["mapped"]:
        rows.append([
            label, m["skill"], m["skill"], "",
            f"{m['kind'].title()} imported from {label}.", "", "", "anytime",
            "", "", "false", "", "",
        ])
    return rows


# ---------- commands ----------

def cmd_detect(args):
    root = Path(args.path).resolve()
    if not root.is_dir():
        return {"status": "error", "message": f"not a directory: {root}"}
    cands = []
    for sub in ("skills", ".claude/skills", ".agents/skills", ".claude"):
        d = root / sub
        if d.is_dir():
            flat = [c for c in d.iterdir() if deref(c, root).is_dir() and (deref(c, root) / "SKILL.md").exists()]
            if flat:
                cands.append({"path": sub, "layout": "flat", "skills": len(flat)})
    grouped = []
    for src in sorted(root.glob("src/*")):
        if src.is_dir() and (
            (src / "module.yaml").exists()
            or ((src / "agents").is_dir() and (src / "workflows").is_dir())
        ):
            grouped.append(f"src/{src.name}")
    if (root / "module.yaml").exists() or (
        (root / "agents").is_dir() and (root / "workflows").is_dir()
    ):
        grouped.append(".")
    personas = list(root.glob(".claude/agents/*.md")) + [
        p for p in root.glob(".claude/commands/**/*.md") if "agents" in p.parts
    ]
    return {
        "status": "ok",
        "repo": str(root),
        "is_git": is_git_repo(root),
        "suggested": {
            "layout": "grouped" if grouped else ("flat" if cands else "unknown"),
            "skills_paths": grouped or [c["path"] for c in cands],
        },
        "flat_candidates": cands,
        "grouped_sources": grouped,
        "persona_files": len(personas),
    }


GIT_URL_RE = re.compile(
    r"^(?:https?://|git@)[^/]+[/:](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def clone_into(url, vars_):
    """Clone a remote repo into <skills_repo_root>/<owner>/<repo>.

    Returns the registry-form path (with the literal {skills_repo_root} token)
    so `detect`/`add` can be fed straight from this output. Never overwrites an
    existing checkout — reports `exists` instead.
    """
    url = (url or "").strip()
    m = GIT_URL_RE.match(url)
    if not m:
        return {"status": "error",
                "message": f"--url '{url}' is not a recognized git URL "
                           "(https://host/owner/repo or git@host:owner/repo)"}
    owner, repo = m.group("owner"), m.group("repo")
    root = vars_.get("skills_repo_root")
    if not root:
        return {"status": "error",
                "message": "srm.skills_repo_root is not configured in _bmad/config.yaml"}
    target = Path(root) / owner / repo
    reg_rel = "{skills_repo_root}/" + owner + "/" + repo
    if target.exists():
        if is_git_repo(target):
            return {"status": "exists", "path": reg_rel,
                    "resolved": str(target), "name": repo, "url": url}
        return {"status": "error",
                "message": f"{target} exists but is not a git repo — refusing to clobber"}
    target.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "clone", url, str(target)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"status": "error", "message": "git clone failed",
                "stderr": (r.stderr or "")[-500:]}
    return {"status": "cloned", "path": reg_rel,
            "resolved": str(target), "name": repo, "url": url}


def cmd_clone(args, vars_):
    return clone_into(args.url, vars_)


def cmd_add(args, reg_path):
    data = registry_load(reg_path)
    if registry_get(data, args.name):
        return {"status": "error", "message": f"repo '{args.name}' already registered"}
    if not args.prefix:
        return {"status": "error", "message": "--prefix is required (ask the user)"}
    entry = {
        "name": args.name,
        "url": args.url or "",
        "path": args.path,
        "prefix": slug(args.prefix),
        "layout": args.layout,
        "git_pull": not args.no_pull,
        "skills_paths": [s.strip() for s in args.skills_paths.split(",") if s.strip()],
    }
    data["repos"].append(entry)
    save_yaml(reg_path, data)
    return {"status": "ok", "added": entry}


def cmd_remove(args, reg_path, skills_dir):
    data = registry_load(reg_path)
    repo = registry_get(data, args.name)
    if not repo:
        return {"status": "error", "message": f"repo '{args.name}' not in registry"}
    data["repos"] = [r for r in data["repos"] if r["name"].lower() != args.name.lower()]
    save_yaml(reg_path, data)
    removed = []
    if args.delete_skills:
        removed = prune_repo(skills_dir, args.name)
    return {"status": "ok", "removed": repo["name"], "skills_deleted": removed}


def cmd_list(reg_path):
    data = registry_load(reg_path)
    return {"status": "ok", "repos": data["repos"]}


def prune_repo(skills_dir, repo_name):
    removed = []
    for d in Path(skills_dir).iterdir():
        o = read_origin(d)
        if o and o["repo"].lower() == repo_name.lower():
            shutil.rmtree(d)
            removed.append(d.name)
    return removed


def cmd_sync(args, reg_path, skills_dir, project_root, vars_):
    data = registry_load(reg_path)
    repos = data["repos"]
    if args.repo:
        r = registry_get(data, args.repo)
        if not r:
            return {"status": "error", "message": f"repo '{args.repo}' not in registry"}
        repos = [r]
    report = {"status": "ok", "repos": {}, "mapped": [], "skipped": [], "warnings": [], "missing": []}
    for repo in repos:
        rroot = Path(resolve(repo["path"], vars_))
        rrep = {"path": str(rroot), "pulled": None, "commit": None, "mapped": 0}
        if not rroot.is_dir():
            missing = {"name": repo["name"], "path": str(rroot), "url": repo.get("url", "")}
            if args.clone_missing and repo.get("url"):
                cl = clone_into(repo["url"], vars_)
                if cl["status"] == "error":
                    rrep["error"] = cl["message"]
                    missing["reason"] = "clone failed"
                    missing["error"] = cl["message"]
                    report["repos"][repo["name"]] = rrep
                    report["missing"].append(missing)
                    report["warnings"].append(f"{repo['name']}: clone failed — {cl['message']}")
                    continue
                rrep["cloned"] = cl["status"]
                if Path(cl["resolved"]) != rroot:
                    rrep["path_repointed"] = {"from": str(rroot), "to": cl["resolved"]}
                    repo["path"] = cl["path"]
                    save_yaml(reg_path, data)
                    rrep["path"] = cl["resolved"]
                rroot = Path(cl["resolved"])
            else:
                rrep["error"] = "path not found"
                missing["reason"] = "not cloned"
                report["repos"][repo["name"]] = rrep
                report["missing"].append(missing)
                report["warnings"].append(
                    f"{repo['name']}: {rroot} not found"
                    + ("" if repo.get("url") else " (no url — cannot clone)"))
                continue
        if repo.get("git_pull", True) and vars_["git_pull"] and not args.no_pull and is_git_repo(rroot):
            rc, out, err = git(rroot, "pull", "--ff-only")
            rrep["pulled"] = {"rc": rc, "out": out[-300:], "err": err[-300:]}
            if rc != 0:
                report["warnings"].append(f"{repo['name']}: git pull failed (rc={rc}) — {err[-120:]}")
        commit = git_head(rroot)
        rrep["commit"] = commit

        sub = {"mapped": [], "skipped": [], "warnings": []}
        for rel in repo.get("skills_paths", []):
            src = rroot / rel
            if not src.is_dir():
                sub["warnings"].append(f"{rel}: not found")
                continue
            is_grouped = (src / "module.yaml").exists() or (
                (src / "agents").is_dir() and (src / "workflows").is_dir()
            )
            if src.name == ".claude":
                materialize_claude(repo, src, rel, rroot, skills_dir, commit, sub)
            elif repo.get("layout") == "grouped" or is_grouped:
                materialize_grouped(repo, src, rel, skills_dir, commit, sub)
            else:
                materialize_flat(repo, src, rel, rroot, skills_dir, commit, sub)
        rrep["mapped"] = len(sub["mapped"])
        report["mapped"].extend(sub["mapped"])
        report["skipped"].extend(sub["skipped"])
        report["warnings"].extend(sub["warnings"])
        csv_path = Path(project_root) / "_bmad" / "module-help.csv"
        rows = help_rows_for(repo, sub)
        update_help_csv(csv_path, repo["name"], rows)
        rrep["help_rows"] = len(rows) - 1
        report["repos"][repo["name"]] = rrep

    # staleness scan (never auto-deletes)
    stale = []
    managed = {m["skill"] for m in report["mapped"]}
    skipped = {s["target"] for s in report["skipped"]}
    for d in Path(skills_dir).iterdir():
        o = read_origin(d)
        if not o:
            continue
        repo = registry_get(data, o["repo"])
        if repo is None:
            stale.append({"skill": d.name, "reason": "repo unregistered"})
        elif o["repo"] in report["repos"] and d.name not in managed and d.name not in skipped:
            # its repo was synced this run but nothing re-emitted this skill
            stale.append({"skill": d.name, "reason": "source removed or renamed in repo"})
    report["stale"] = stale
    if args.prune:
        deleted = [s["skill"] for s in stale]
        for s in stale:
            shutil.rmtree(Path(skills_dir) / s["skill"], ignore_errors=True)
        report["pruned"] = deleted
    return report


def cmd_missing(reg_path, vars_):
    """Read-only clone-status check: which registered repos are/aren't checked
    out. No pulls, no writes — used by srm-setup and by humans before sync."""
    data = registry_load(reg_path)
    cloned, missing = [], []
    for repo in data["repos"]:
        rroot = Path(resolve(repo["path"], vars_))
        if rroot.is_dir():
            cloned.append({"name": repo["name"], "path": str(rroot)})
        else:
            missing.append({"name": repo["name"], "path": str(rroot),
                            "url": repo.get("url", "")})
    return {"status": "ok", "cloned": cloned, "missing": missing,
            "counts": {"cloned": len(cloned), "missing": len(missing),
                       "total": len(cloned) + len(missing)}}


def cmd_status(reg_path, skills_dir, vars_):
    data = registry_load(reg_path)
    rows = []
    for d in sorted(Path(skills_dir).iterdir()):
        o = read_origin(d)
        if not o:
            continue
        repo = registry_get(data, o["repo"])
        head = git_head(resolve(repo["path"], vars_)) if repo else None
        rows.append({
            "skill": d.name,
            "repo": o["repo"],
            "synced_commit": o.get("commit"),
            "repo_head": head,
            "state": "current" if head and o.get("commit") == head else
                     ("behind" if head else "unknown"),
        })
    return {"status": "ok", "skills": rows}


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(prog="srm-sync")
    ap.add_argument("command", choices=["sync", "detect", "clone", "add", "remove", "list", "missing", "status"])
    ap.add_argument("--registry", required=False)
    ap.add_argument("--skills-dir", required=False)
    ap.add_argument("--config-root", default=".", help="project root (for _bmad/config.yaml)")
    ap.add_argument("--repo")
    ap.add_argument("--path")
    ap.add_argument("--name")
    ap.add_argument("--url")
    ap.add_argument("--prefix")
    ap.add_argument("--layout", default="flat", choices=["flat", "grouped", "auto"])
    ap.add_argument("--skills-paths", default="")
    ap.add_argument("--no-pull", action="store_true")
    ap.add_argument("--clone-missing", action="store_true",
                    help="clone registered repos not yet checked out (uses each entry's url)")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--delete-skills", action="store_true")
    args = ap.parse_args()

    project_root = str(Path(args.config_root).resolve())
    vars_ = module_vars(project_root)
    reg_path = Path(args.registry or Path(project_root) / "_bmad" / "srm" / "sources.yaml")
    skills_dir = Path(args.skills_dir or Path(project_root) / ".agents" / "skills")

    if args.command == "detect":
        out = cmd_detect(args)
    elif args.command == "clone":
        out = cmd_clone(args, vars_)
    elif args.command == "add":
        out = cmd_add(args, reg_path)
    elif args.command == "remove":
        out = cmd_remove(args, reg_path, skills_dir)
    elif args.command == "list":
        out = cmd_list(reg_path)
    elif args.command == "missing":
        out = cmd_missing(reg_path, vars_)
    elif args.command == "status":
        out = cmd_status(reg_path, skills_dir, vars_)
    else:
        out = cmd_sync(args, reg_path, skills_dir, project_root, vars_)

    print(json.dumps(out, indent=2, ensure_ascii=False))
    sys.exit(0 if out.get("status") in ("ok", "cloned", "exists") else 1)


if __name__ == "__main__":
    main()
