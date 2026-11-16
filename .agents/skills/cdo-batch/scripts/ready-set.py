#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""ready-set.py — partition the confirmed pool into dispatchable vs waiting.

The deterministic half of auto-dispatch. A key is dispatchable when:

  1. it sits in pool.confirmed and a confirmed card exists
     (alignment/YYYY/MM/DD/ — never drafts/)
  2. it is not in-flight and holds no fresh lock (locks/{key}.lock)
  3. every `deps:` entry on its backlog line has finished
     (ledger status done/verified/shipped) — a dep still confirmed-but-
     undispatched orders first when it rides the same drain; quarantined
     or absent deps block
  4. the owning dept declares a `produce` capability (dispatch wouldn't
     dead-end on a missing entry)
  5. card externals are present in the env (--env-file or project .env)

Usage:
  uv run ready-set.py --orchestration-dir /path/docs/orchestration
      [--keys k1,k2] [--env-file /path/.env]
      [--stall-timeout-minutes 45] [-o result.json]

Dispatch is LINEAR: one worker session drains the pool, key by key, on a
single branch. `dispatch_now` is therefore one topo-ordered list — in-pool
dep edges order dependencies first, pool order breaks ties. `touches:` is
advisory context for reviewers, not a gate — sequential execution can't
conflict with itself.

Emits {dispatch_now: [...], waiting: {key: [reasons]}}.
Exit codes: 0=ok (even when dispatch_now is empty — that's a result), 2=error
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from cardlayout import confirmed_card as _confirmed_card  # noqa: E402

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

DEPS_RE = re.compile(r"\bdeps:\s*([^|\n]+)")
TOUCHES_RE = re.compile(r"\btouches:\s*([^|]+)")
KEY_LINE_RE = re.compile(r"^- \[[ xA\-]\] ([A-Za-z0-9][A-Za-z0-9._-]*)\b")
KEY_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DEP_NOISE = {"none", "-", "—", "{keys}"}
ENV_IN_CARD_RE = re.compile(r"^- `?([A-Z][A-Z0-9_]+)`?\b", re.M)
DONE_STATUSES = {"done", "verified", "shipped"}
# A drain lock (locks/g-{...}.lock, written at spawn time) marks every queued
# key as held by the running drain session. It outlives a story lock's stall
# window because a cloud drain can't be heartbeated — 24h is the janitor's
# horizon for deciding the spawn never delivered.
GROUP_LOCK_TTL_MINUTES = 24 * 60


def parse_args():
    p = argparse.ArgumentParser(description="Compute the linear dispatch set.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--keys", default="",
                   help="comma list — default: entire pool.confirmed")
    p.add_argument("--env-file", help=".env path (default: {project-root}/.env)")
    p.add_argument("--project-root", default="",
                   help="project root — default: orchestration-dir's "
                        "grandparent (the standard install layout)")
    p.add_argument("--stall-timeout-minutes", type=int, default=45)
    p.add_argument("-o", "--output")
    return p.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def lock_age_minutes(ts: str):
    if not ts:
        return None
    try:
        t = datetime.strptime(ts, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 60
    except ValueError:
        return None


def locked_keys(orch: Path, stall_minutes: int) -> set:
    """Keys with a FRESH lock — stale locks don't block (janitor breaks them)."""
    held = set()
    ld = orch / "locks"
    files = list(ld.glob("*.lock")) if ld.is_dir() else []
    legacy = orch / "dispatch.lock"
    if legacy.is_file():
        files.append(legacy)
    for f in files:
        parts = f.read_text(encoding="utf-8", errors="replace").split()
        ts = parts[1] if len(parts) > 1 else None
        age = lock_age_minutes(ts)
        if f.parent.name == "locks" and f.stem.startswith("g-"):
            # drain spawn lock — holds every key in its comma-list for up to
            # GROUP_LOCK_TTL_MINUTES (a cloud drain can't be heartbeated)
            if age is None or age <= GROUP_LOCK_TTL_MINUTES:
                keys = parts[2].split(",") if len(parts) > 2 else []
                held.update(k for k in keys if k)
            continue
        key = f.stem if f.parent.name == "locks" else (parts[2] if len(parts) > 2 else None)
        if key and (age is None or age <= stall_minutes * 2):
            held.add(key)
    return held


def backlog_fields(orch: Path) -> dict:
    """key -> {deps, touches, backlog} parsed from all backlog lines."""
    out = {}
    bd = orch / "backlogs"
    if not bd.is_dir():
        return out
    for f in bd.glob("*.md"):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = KEY_LINE_RE.match(line.strip())
            if not m:
                continue
            key = m.group(1)
            deps, touches = [], []
            dm = DEPS_RE.search(line)
            if dm:
                for raw in dm.group(1).split(","):
                    words = raw.strip().split()
                    tok = words[0] if words else ""
                    if tok and tok.lower() not in DEP_NOISE \
                            and KEY_TOKEN_RE.match(tok):
                        deps.append(tok)
            tm = TOUCHES_RE.search(line)
            if tm:
                touches = [t.strip().rstrip("*") for t in
                           tm.group(1).split(",") if t.strip()]
            out[key] = {"deps": deps, "touches": touches, "backlog": f.stem}
    return out


def newest_sprint_statuses(root: Path) -> dict:
    """development_status from the newest sprint-status-*.yaml — {key:
    status}. Second source for dep satisfaction: shipped work predating a
    ledger entry (pre-CDO runs, migration) still counts as done."""
    impl = root / "_bmad-output" / "implementation-artifacts"
    if not impl.is_dir():
        return {}
    yamls = sorted(impl.glob("sprint-status-*.yaml"))
    if not yamls:
        return {}
    out = {}
    in_dev = False
    for line in yamls[-1].read_text(encoding="utf-8",
                                   errors="replace").splitlines():
        if line.startswith("development_status:"):
            in_dev = True
            continue
        if in_dev:
            if line and not line.startswith((" ", "\t")):
                break
            m = re.match(r"^\s+([\w][\w.-]*):\s*(\S+)", line)
            if m and re.match(r"^\d{2}-\d{2}-", m.group(1)):
                out[m.group(1)] = m.group(2).split("#")[0].strip()
    return out


def confirmed_card(orch: Path, key: str):
    """Confirmed cards live under alignment/YYYY/MM/DD/. Rejected cards are
    archived there too (audit trail) but carry `<!-- reject` on line 1 —
    they do NOT authorize dispatch. No verdict comment → treated confirmed.
    Implementation: cardlayout.confirmed_card (vendored single source)."""
    return _confirmed_card(orch, key)


def card_externals(orch: Path, key: str) -> list:
    f = confirmed_card(orch, key)
    if not f:
        return []
    text = f.read_text(encoding="utf-8", errors="replace")
    env_block = text.split("## Externals Needed")[-1].split("## ")[0] \
        if "## Externals Needed" in text else ""
    return ENV_IN_CARD_RE.findall(env_block)


def env_keys_present(env_file: Path) -> set:
    if not env_file or not env_file.is_file():
        return set()
    keys = set()
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^\s*([A-Z][A-Z0-9_]+)\s*=", line)
        if m:
            keys.add(m.group(1))
    return keys


def dept_produce_entry(orch: Path, backlog_stem: str):
    caps_path = orch / "capabilities.yaml"
    if not caps_path.is_file():
        return None, None
    try:
        caps = yaml.safe_load(caps_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None, None
    for dept, info in (caps.get("departments") or {}).items():
        if not isinstance(info, dict):
            continue
        if Path(str(info.get("backlog", ""))).stem != backlog_stem:
            continue
        produce = (info.get("capabilities") or {}).get("produce")
        return dept, (produce or {}).get("entry")
    return None, None


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    if not orch.is_dir():
        print(json.dumps({"errors": [f"orchestration dir not found: {orch}"]}))
        sys.exit(2)
    lpath = orch / "flow-ledger.yaml"
    ledger = {}
    if lpath.is_file():
        try:
            ledger = yaml.safe_load(lpath.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            print(json.dumps({"errors": ["flow-ledger.yaml unparseable"]}))
            sys.exit(2)

    pool = (ledger.get("pool") or {}).get("confirmed") or []
    quarantined = {q.get("key") for q in
                   (ledger.get("pool") or {}).get("quarantined") or []
                   if isinstance(q, dict)}
    stories = ledger.get("stories") or {}
    candidates = [k.strip() for k in args.keys.split(",") if k.strip()] or list(pool)

    proj_root = Path(args.project_root).resolve() if args.project_root \
        else orch.parent.parent
    fields = backlog_fields(orch)
    sprint_status = newest_sprint_statuses(proj_root)
    held = locked_keys(orch, args.stall_timeout_minutes)
    env_path = Path(args.env_file) if args.env_file else proj_root / ".env"
    have_env = env_keys_present(env_path)

    waiting, eligible, pending_dep_edges = {}, [], {}
    candidate_set = set(candidates)
    for key in candidates:
        reasons = []
        if key not in pool:
            reasons.append("not in pool.confirmed")
        if not confirmed_card(orch, key):
            reasons.append("no confirmed alignment card")
        if (stories.get(key) or {}).get("status") == "in-flight":
            reasons.append("already in-flight")
        if key in held:
            reasons.append(f"fresh lock held for {key}")
        for dep in fields.get(key, {}).get("deps", []):
            dep_status = (stories.get(dep) or {}).get("status")
            yaml_status = sprint_status.get(dep)
            if dep_status in DONE_STATUSES or yaml_status in ("done", "obsolete"):
                # dep finished — satisfied. The sprint yaml is the second
                # source: work shipped before this ledger entry existed
                # (pre-CDO pipeline runs, migrated items) still counts done.
                continue
            if dep in quarantined:
                reasons.append(f"dep {dep} quarantined")
            elif dep_status == "in-flight":
                reasons.append(f"dep {dep} in-flight")
            elif dep in pool and dep in candidate_set:
                # confirmed and being dispatched this pass — an ordering edge,
                # not a blocker: the drain runs dep first
                pending_dep_edges.setdefault(key, []).append(dep)
            elif dep in pool:
                reasons.append(f"dep {dep} confirmed but not yet shipped")
            else:
                reasons.append(f"dep {dep} never finished (absent/unaligned)")
        meta = fields.get(key)
        dept, produce_entry = dept_produce_entry(orch, meta["backlog"]) if meta else (None, None)
        if meta and dept and not produce_entry:
            reasons.append(f"dept {dept} declares no `produce` capability")
        missing_env = [e for e in card_externals(orch, key) if e not in have_env]
        if missing_env:
            reasons.append(f"missing env: {', '.join(missing_env)}")
        if reasons:
            waiting[key] = reasons
        else:
            eligible.append(key)

    # An eligible key whose pending dep landed in `waiting` can't ride the
    # drain either — demote it with the dep's reasons made legible
    for key in list(eligible):
        bad_deps = [d for d in pending_dep_edges.get(key, []) if d in waiting]
        if bad_deps:
            eligible.remove(key)
            waiting[key] = [f"dep {d} pooled but undispatchable"
                            for d in bad_deps]

    # Linear dispatch: one topo-ordered drain list. A dep edge dep→key orders
    # dep first; pool order breaks ties; cycle leftovers append in pool order.
    pool_order = {k: i for i, k in enumerate(candidates)}
    indeg = {k: 0 for k in eligible}
    edges = {k: [] for k in eligible}
    for key in eligible:
        for dep in pending_dep_edges.get(key, []):
            if dep in indeg:
                edges[dep].append(key)
                indeg[key] += 1
    dispatch_now = []
    queue = sorted([k for k, d in indeg.items() if d == 0],
                   key=pool_order.get)
    while queue:
        node = queue.pop(0)
        dispatch_now.append(node)
        for nxt in sorted(edges[node], key=pool_order.get):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
        queue.sort(key=pool_order.get)
    dispatch_now += [k for k in sorted(eligible, key=pool_order.get)
                     if k not in dispatch_now]

    # 13-45 — deterministic spawn plan: partition eligible keys into
    # dependency groups (connected components over the in-pool dep edges).
    # A multi-key group = ONE linear session (topo order preserved from
    # dispatch_now); a key with no dep edges to any other eligible key =
    # its own session. Pure graph math — no LLM judgment anywhere.
    parent = {k: k for k in eligible}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for key in eligible:
        for dep in pending_dep_edges.get(key, []):
            if dep in parent:
                a, b = find(dep), find(key)
                if a != b:
                    parent[b] = a
    groups = {}
    for k in eligible:
        groups.setdefault(find(k), []).append(k)
    # group members in dispatch_now (topo) order; groups ordered by their
    # first member's pool position — stable across runs
    spawn_plan = []
    for root_key in sorted(groups, key=lambda r: pool_order[sorted(
            groups[r], key=pool_order.get)[0]]):
        members = sorted(groups[root_key], key=dispatch_now.index)
        spawn_plan.append({
            "keys": members,
            "mode": "linear" if len(members) > 1 else "solo",
        })

    emit = {
        "status": "ok",
        "dispatch_now": dispatch_now,
        "spawn_plan": spawn_plan,
        "waiting": waiting,
        "computed_at": now_iso(),
    }
    out = json.dumps(emit, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
