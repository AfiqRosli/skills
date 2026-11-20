#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""push-lane.py — the pre-deploy lane publish (cdo-platform push).

Under pre-deploy gating, ship legs land work on the local-only `cdo-lane`
ref and NOTHING pushes per story — every origin push costs a remote build
(Netlify). The Operator's `## Pre-deploy Sign-offs` signature is the only
push authorization: this script pushes the newest *signed* lane commit to
`origin/{lane}` — one push, one build, everything below it riding along
physically and reported honestly.

  pending       → signed-awaiting-push + marked-unsigned queue (read-only)
  run           → push the newest signed lane_sha to origin/{lane}, then
                  stamp stories.{key}.pushed for every story the push
                  covered (signed or carried)
    --tip         push the whole cdo-lane tip (signed or not — explicit
                  "push everything" only; carried unsigned work is named)
    --sha {sha}   push an explicit commit to origin/{lane}
    --dry-run     resolve + report the plan, touch nothing

Ledger contract (stories.{key}):
  lane_sha             — the commit the ship leg landed on cdo-lane
  pre_deploy.marked_at — Delivered-review confirm filed the sign-off item
  pre_deploy.signed_at — Operator signed it → pushable
  pushed {at, sha}     — this script's stamp: the sha is on origin/{lane}

Exit codes: 0=ok (incl. nothing-to-push), 1=refused (non-FF / unsigned),
2=error (not a repo, missing ledger, git failure).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

LANE_REF = "refs/heads/cdo-lane"
FINDINGS_SHA_RE = re.compile(r"commit=([0-9a-f]{7,40})\b")


def parse_args():
    p = argparse.ArgumentParser(description="Push signed lane work to origin.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--project-root", required=True)
    p.add_argument("--lane", default="preview")
    p.add_argument("-o", "--output")
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("pending")
    r = sub.add_parser("run")
    r.add_argument("--tip", action="store_true",
                   help="push the whole cdo-lane tip — signed or not")
    r.add_argument("--sha", default="",
                   help="push an explicit commit to origin/{lane}")
    r.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def emit(result: dict, code: int, out: str):
    blob = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)


def lane_sha_of(st: dict) -> str:
    """The story's landed commit — stories.{key}.lane_sha, else the
    `commit=` convention in the newest findings line (pre-lane_sha ships)."""
    sha = st.get("lane_sha") or ""
    if sha:
        return sha
    for line in reversed(st.get("findings") or []):
        m = FINDINGS_SHA_RE.search(str(line))
        if m:
            return m.group(1)
    return ""


def load_ledger(orch: Path):
    p = orch / "flow-ledger.yaml"
    if not p.is_file():
        return p, None
    try:
        return p, yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return p, None


def save_ledger(lpath: Path, ledger: dict):
    tmp = lpath.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
    os.replace(tmp, lpath)


def rev_list(root: Path, ref: str) -> list:
    """Newest-first shas on the ref ([] when the ref doesn't exist)."""
    proc = git(root, "rev-list", ref)
    if proc.returncode != 0:
        return []
    return [l.strip() for l in proc.stdout.splitlines() if l.strip()]


def is_ancestor(root: Path, anc: str, desc: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", anc, desc).returncode == 0


def story_views(ledger: dict) -> list:
    """{key, status, sha, marked, signed, pushed} per story — the queue
    surface `pending` and the coverage pass both read off this."""
    out = []
    for key, st in (ledger.get("stories") or {}).items():
        if not isinstance(st, dict):
            continue
        pd = st.get("pre_deploy") or {}
        pv = st.get("pushed") or {}
        pushed = pv if isinstance(pv, dict) else {"at": pv}
        out.append({
            "key": key,
            "status": st.get("status"),
            "sha": lane_sha_of(st),
            "marked": bool(pd.get("marked_at")),
            "signed": bool(pd.get("signed_at")),
            "pushed": bool(pushed.get("sha") or pushed.get("at")),
        })
    return out


def cmd_pending(root: Path, orch: Path, lane: str):
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        emit({"status": "error",
              "errors": ["flow-ledger.yaml missing/unparseable"]}, 2,
             args.output)
    views = story_views(ledger)
    unpushed = git(root, "rev-list", "--count",
                   f"origin/{lane}..{LANE_REF}")
    emit({
        "status": "ok",
        "lane": lane,
        "cdo_lane": (git(root, "rev-parse", "--short", LANE_REF)
                     .stdout.strip() or None),
        "unpushed_commits": int(unpushed.stdout.strip() or 0)
        if unpushed.returncode == 0 else None,
        "signed_awaiting_push": [v["key"] for v in views
                                 if v["signed"] and not v["pushed"]],
        "marked_unsigned": [v["key"] for v in views
                            if v["marked"] and not v["signed"]
                            and not v["pushed"]],
        "landed_unmarked": [v["key"] for v in views
                            if v["status"] == "shipped" and v["sha"]
                            and not v["marked"] and not v["pushed"]],
    }, 0, args.output)


def cmd_run(root: Path, orch: Path, lane: str):
    lpath, ledger = load_ledger(orch)
    if ledger is None:
        emit({"status": "error",
              "errors": ["flow-ledger.yaml missing/unparseable"]}, 2,
             args.output)
    views = story_views(ledger)
    warnings = []
    pushable = [v for v in views if v["signed"] and not v["pushed"]]
    # a signed story whose status regressed (killed/deferred between sign
    # and push) is no longer pushable — the signature asked for shipped work
    regressed = [v["key"] for v in pushable if v["status"] != "shipped"]
    if regressed:
        print(f"warning: signed but status regressed: {', '.join(regressed)}",
              file=sys.stderr)
    pushable = [v for v in pushable if v["status"] == "shipped"]
    missing_sha = [v["key"] for v in pushable if not v["sha"]]
    pushable = [v for v in pushable if v["sha"]]

    origin_ref = f"origin/{lane}"
    fetch = git(root, "fetch", "origin", lane)
    origin_tip = git(root, "rev-parse", "--verify",
                     origin_ref).stdout.strip()
    if fetch.returncode != 0:
        if not origin_tip:
            # no remote at all (or unreachable) — that's an environment
            # error, not a policy refusal; don't masquerade as one
            emit({"errors": [f"git fetch origin {lane} failed: "
                             f"{fetch.stderr.strip()[:200]}"]},
                 2, args.output)
        warnings.append(
            f"git fetch failed ({fetch.stderr.strip()[:120]}) — "
            f"{origin_ref} is stale; the non-FF check below may refuse")

    # already-on-origin signed items heal themselves — stamp pushed, no
    # push needed (legacy ships predating the gate land here)
    healed = []
    if origin_tip and not args.sha and not args.tip:
        healed = [v for v in pushable
                  if is_ancestor(root, resolve_sha(root, v["sha"]),
                                 origin_ref)]
        pushable = [v for v in pushable if v not in healed]

    target = None
    signed_target = None
    if args.sha:
        target = args.sha
    elif args.tip:
        target = git(root, "rev-parse", LANE_REF).stdout.strip()
        if not target:
            emit({"status": "error",
                  "errors": [f"{LANE_REF} doesn't exist — nothing has "
                             "landed on the local lane"]}, 2, args.output)
    elif pushable:
        # newest signed commit on the lane — lowest rev-list index wins
        order = {sha: i for i, sha in enumerate(rev_list(root, LANE_REF))}
        for v in pushable:
            v["resolved"] = resolve_sha(root, v["sha"])
        not_on_lane = [v["key"] for v in pushable
                       if v["resolved"] not in order]
        if not_on_lane:
            emit({"status": "refused",
                  "errors": [f"signed lane_sha not on {LANE_REF}: "
                             f"{', '.join(not_on_lane)} — lane integrity "
                             "finding, reconcile before pushing"]}, 1,
                 args.output)
        best = min(pushable, key=lambda v: order[v["resolved"]])
        target = best["resolved"]
        signed_target = best["key"]

    covered = [] if target is None else [
        v for v in views
        if v["sha"] and not v["pushed"]
        and is_ancestor(root, resolve_sha(root, v["sha"]), target)]
    carried = [v["key"] for v in covered if not v["signed"]]
    plan = {"lane": lane, "target": target, "signed_target": signed_target,
            "covers": [v["key"] for v in covered],
            "carried_unsigned": carried,
            "healed": [v["key"] for v in healed] or None,
            "missing_sha": missing_sha}
    if args.dry_run:
        plan["status"] = "dry-run"
        emit(plan, 0, args.output)

    if target is None:
        # nothing signed to push — only heals (or nothing at all)
        at = now_iso()
        for v in healed:
            ledger["stories"][v["key"]]["pushed"] = {
                "at": at, "sha": v["sha"], "push": "already-on-origin"}
        if healed:
            save_ledger(lpath, ledger)
        plan.update({
            "status": "healed" if healed else "nothing-to-push",
            "reason": None if healed else
            "no signed pre-deploy items with a lane sha",
            "stamped": [v["key"] for v in healed] or None})
        emit(plan, 0, args.output)

    # non-FF guard — the publish never rewrites the remote lane
    if origin_tip and not is_ancestor(root, origin_ref, target):
        emit({"status": "refused",
              "errors": [f"non-fast-forward: origin/{lane} has commits not "
                         f"in {target[:12]} — fetch + rebase cdo-lane onto "
                         "origin first, then re-sign"]}, 1, args.output)

    push = git(root, "push", "origin", f"{target}:{lane}")
    if push.returncode != 0:
        err = push.stderr.strip()
        emit({"status": "refused",
              "errors": [f"push to origin/{lane} refused: {err}"],
              "plan": plan}, 1, args.output)

    at = now_iso()
    for v in covered:
        st = ledger["stories"][v["key"]]
        st["pushed"] = {"at": at, "sha": v["sha"], "push": target}
    save_ledger(lpath, ledger)

    # model B heal — the local lane branch should already hold this target
    # (ship legs advance it), but a missed/failed advance leaves it stale;
    # re-assert best-effort. A refusal (dirty checkout overlap, non-FF)
    # reports only — the push already landed.
    heal = subprocess.run(
        # __file__ sibling — push-lane is Operator-invoked in the main
        # checkout, never snapshot-copied into a worktree (unlike the
        # worker-facing scripts, which resolve root-relative for that reason)
        [sys.executable, str(Path(__file__).with_name("advance-lane.py")),
         "--project-root", str(root), "run", "--to", LANE_REF,
         "--lane", lane, "--reconcile"],
        capture_output=True, text=True)
    try:
        plan["lane_advance"] = json.loads(heal.stdout or "{}")
    except json.JSONDecodeError:
        plan["lane_advance"] = {"status": "error",
                                "raw": (heal.stdout or heal.stderr)[:200]}
    if plan["lane_advance"].get("status") not in \
            ("advanced", "already-abreast", "reconciled"):
        warnings.append(
            "lane advance refused: "
            + "; ".join(plan["lane_advance"].get("errors",
                        [plan["lane_advance"].get("status", "?")])[:2]))
    pop = plan["lane_advance"].get("stash_pop") or {}
    if pop.get("status") == "conflicts":
        warnings.append(
            "ad-hoc WIP stash pop conflicted on "
            + ", ".join(pop.get("files") or ["(see stash)"])
            + f" — WIP kept in {pop.get('ref', 'stash')}")
    elif pop.get("status") == "deferred":
        warnings.append(
            "ad-hoc WIP stayed stashed (merge unresolved): "
            + pop.get("ref", "stash"))
    if warnings:
        plan["warnings"] = warnings

    plan.update({"status": "pushed", "at": at,
                 "stamped": [v["key"] for v in covered],
                 "staged_behind_target": [
                     v["key"] for v in views
                     if v["sha"] and not v["pushed"]
                     and not is_ancestor(root, resolve_sha(root, v["sha"]),
                                         target)]})
    emit(plan, 0, args.output)


def resolve_sha(root: Path, sha: str) -> str:
    """Full sha for merge-base/rev-list checks — the ledger may carry the
    short form from findings or a worker's `git rev-parse --short`."""
    return git(root, "rev-parse", sha).stdout.strip() or sha


def main():
    global args
    args = parse_args()
    root = Path(args.project_root).resolve()
    orch = Path(args.orchestration_dir).resolve()
    probe = git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        emit({"status": "error",
              "errors": [f"not a git work tree: {root}"]}, 2, args.output)
    if args.action == "pending":
        cmd_pending(root, orch, args.lane)
    else:
        cmd_run(root, orch, args.lane)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
