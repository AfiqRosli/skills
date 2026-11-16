#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""advance-lane.py — keep the local ship-target branch abreast of the lane.

Model B (Operator-confirmed 2026-10-23): the local `{ship_target}` branch
means "shipped, pending deploy" — every ship leg advances it to the
integration tip so the Operator's checkout always sees landed work.
`cdo-lane` stays the ref workers CAS against; `{lane}` is its mirror.
Unpushed work is `origin/{lane}..{lane}`; nothing here pushes.

  run --to {ref|sha} [--lane {ship_target}] [--reconcile] [--dry-run]
      [--state-root {path} ...]

Plain run:
  - --to must resolve to a commit; missing/unresolvable → error
  - {to} already an ancestor of {lane} → no-op ("already-abreast")
  - {lane} checked out → `git merge --ff-only {to}` — the working tree
    fast-forwards too; a dirty tree only refuses when it overlaps the
    incoming diff (reported, never forced) — --reconcile checkpoints
    the WIP and merges anyway
  - {lane} not checked out → `git branch -f {lane} {to}`
  - {lane} missing → created at {to}
  - non-FF ({lane} carries commits {to} lacks) → refused unless
    checked-out + --reconcile (merged in place); otherwise reconcile
    by hand — the branch is never moved backward or sideways silently

--reconcile (checked-out lane only): when FF is blocked by uncommitted
files that overlap the incoming diff — or the lane itself carries
commits {to} lacks (e.g. an earlier reconcile checkpoint survived a
crash/abort, or the Operator committed ad-hoc work on the lane) —
  1. staged index → refused: don't compound a half-staged state
  2. ad-hoc WIP (dirty paths outside the state roots) → `git stash
     push -u` aside — Operator work never rides the lane and never
     reaches origin; popped back after the merge resolves, with pop
     conflicts keeping the stash entry and reporting, never dropping
  3. remaining dirty paths (org-state churn) → `cdo state: checkpoint`
     commit (hooks bypassed — bookkeeping commits shouldn't pay the
     repo's eslint gate; ephemeral `locks/` dirs under the state roots
     and Windows reserved names are excluded so they never ride the
     lane to origin)
  4. `git merge --no-ff {to}`, resolve state-root conflicts --ours
     (live state is always newer than the lane's ship-time snapshot);
     conflicts outside the state roots → abort + report — the ad-hoc
     WIP is restored from the stash, a human merges by hand
  5. when --to names a refs/heads/* ref, FF it to the merge result
     (CAS against the resolved target) so cdo-lane stays abreast

Stdlib only — callable via sys.executable from sibling scripts (push-lane).
Exit 0 ok (incl. no-op) / 1 refused / 2 error.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_STATE_ROOTS = ["docs/orchestration", "_bmad-output"]
# Windows device names git can't index — keep them out of checkpoints
RESERVED_NAMES = ["nul", "con", "prn", "aux"] + \
    [f"com{i}" for i in range(1, 10)] + [f"lpt{i}" for i in range(1, 10)]


def parse_args():
    p = argparse.ArgumentParser(
        description="Fast-forward the local ship-target branch.")
    p.add_argument("--project-root", required=True)
    p.add_argument("-o", "--output")
    sub = p.add_subparsers(dest="action", required=True)
    r = sub.add_parser("run")
    r.add_argument("--to", required=True,
                   help="ref or sha the lane branch should reach")
    r.add_argument("--lane", default="preview")
    r.add_argument("--reconcile", action="store_true",
                   help="checkpoint org-state churn + merge when FF is "
                        "blocked by dirty state-root paths")
    r.add_argument("--state-root", action="append", default=None,
                   help="path root whose churn may be checkpointed "
                        "(repeatable; default docs/orchestration, "
                        "_bmad-output)")
    r.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def emit(result: dict, code: int, out: str):
    blob = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


def git(root: Path, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)


def resolve(root: Path, ref: str) -> str:
    return git(root, "rev-parse", "--verify", f"{ref}^{{commit}}") \
        .stdout.strip()


def is_ancestor(root: Path, anc: str, desc: str) -> bool:
    return git(root, "merge-base", "--is-ancestor", anc, desc) \
        .returncode == 0


def checked_out_branch(root: Path) -> str:
    return git(root, "symbolic-ref", "--quiet", "--short", "HEAD") \
        .stdout.strip()


def under_roots(path: str, roots: list) -> bool:
    p = path.rstrip("/")
    return any(p == r or p.startswith(r.rstrip("/") + "/") for r in roots)


def dirty_paths(root: Path) -> list:
    """Working-tree paths git would refuse to overwrite — modified,
    deleted, and untracked entries from status --porcelain."""
    proc = git(root, "status", "--porcelain")
    out = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        p = line[3:]
        if " -> " in p:
            p = p.split(" -> ", 1)[1]
        out.append(p.strip('"'))
    return out


def blocking_paths(root: Path, frm: str, to: str, dirty: list) -> list:
    """Dirty paths that intersect the incoming diff — these are what a
    merge --ff-only actually refuses on."""
    proc = git(root, "diff", "--name-only", frm, to)
    incoming = {l.strip() for l in proc.stdout.splitlines() if l.strip()}
    out = []
    for d in dirty:
        if d.endswith("/"):
            if any(ip.startswith(d) for ip in incoming):
                out.append(d)
        elif d in incoming:
            out.append(d)
    return out


def staged_paths(root: Path) -> list:
    proc = git(root, "diff", "--cached", "--name-only")
    return [l.strip() for l in proc.stdout.splitlines() if l.strip()]


def cmd_run(root: Path):
    target = resolve(root, args.to)
    if not target:
        emit({"status": "error",
              "errors": [f"--to {args.to!r} does not resolve to a commit"]},
             2, args.output)
    roots = args.state_root or DEFAULT_STATE_ROOTS
    # normalize --to to a full refname when it names a ref — short forms
    # like `cdo-lane` resolve for reading but must not slip past the
    # ref-advance check below
    if not args.to.startswith("refs/"):
        full = git(root, "rev-parse", "--symbolic-full-name", args.to) \
            .stdout.strip()
        if full.startswith("refs/"):
            args.to = full
    lane_ref = f"refs/heads/{args.lane}"
    lane_tip = git(root, "rev-parse", "--verify", lane_ref).stdout.strip()
    checked_out = checked_out_branch(root) == args.lane
    plan = {"lane": args.lane, "to": target, "lane_tip": lane_tip or None,
            "checked_out": checked_out}

    if lane_tip and is_ancestor(root, target, lane_ref):
        plan["status"] = "dry-run" if args.dry_run else "already-abreast"
        plan["action"] = "none"
        emit(plan, 0, args.output)
    diverged = bool(lane_tip) and not is_ancestor(root, lane_ref, target)

    # checked-out lane: pre-compute what a merge --ff-only would refuse on
    blocking = []
    if checked_out and lane_tip:
        blocking = blocking_paths(root, lane_ref, target, dirty_paths(root))
    if args.dry_run:
        plan["status"] = "dry-run"
        plan["action"] = ("merge --ff-only" if checked_out
                          else "branch -f" if lane_tip else "branch create")
        if blocking:
            plan["blocking"] = blocking
        if diverged:
            plan["diverged"] = True
        if (blocking or diverged) and checked_out:
            plan["reconcile"] = args.reconcile
        emit(plan, 0, args.output)

    if not lane_tip:
        r = git(root, "branch", args.lane, target)
        action = "created"
    elif diverged and not (checked_out and args.reconcile):
        emit({**plan, "status": "refused",
              "errors": [f"non-fast-forward: {args.lane} has commits "
                         f"{args.to} lacks — "
                         + ("pass --reconcile to merge them in, or "
                            if checked_out else
                            "check the branch out and pass --reconcile, or ")
                         + "reconcile by hand; the branch is never moved "
                         "sideways"]}, 1, args.output)
    elif not checked_out:
        r = git(root, "branch", "-f", args.lane, target)
        action = "branch-f"
    else:
        if (blocking or diverged) and args.reconcile:
            reconcile(root, target, lane_ref, roots, plan, blocking)
            return
        if blocking:
            emit({**plan, "status": "refused", "action": "refused",
                  "blocking": blocking,
                  "errors": [f"merge --ff-only would overwrite uncommitted "
                             f"files (--reconcile not passed): "
                             f"{', '.join(blocking[:12])}"
                             + (" …" if len(blocking) > 12 else "")]},
                 1, args.output)
        r = git(root, "merge", "--ff-only", target)
        action = "merged-ff"

    if r.returncode != 0:
        emit({**plan, "status": "refused", "action": action,
              "errors": [(r.stderr or r.stdout).strip()]}, 1, args.output)
    emit({**plan, "status": "advanced", "action": action}, 0, args.output)


RECONCILE_LOCK = "cdo-advance.lock"
RECONCILE_LOCK_TTL = 1800          # a crashed reconcile never wedges the lane


def git_common_dir(root: Path) -> Path:
    """The shared .git dir — works from linked worktrees too, where
    `{root}/.git` is a FILE pointing here."""
    p = git(root, "rev-parse", "--git-common-dir").stdout.strip()
    gd = Path(p) if p else root / ".git"
    return gd if gd.is_absolute() else (root / gd).resolve()


def acquire_reconcile_lock(root: Path):
    """Serialize reconciles (13-45 parallel drains) — a pid+ts lockfile in
    the common gitdir. Stale (>TTL) locks break themselves on next entry;
    stale-checks re-read before unlinking to narrow the TOCTOU window."""
    lock = git_common_dir(root) / RECONCILE_LOCK
    for _ in range(2):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as f:
                f.write(f"{os.getpid()} {int(time.time())}\n")
            return lock
        except FileExistsError:
            pass
        except OSError:
            return None          # can't lock → proceed; git serializes anyway
        try:
            content = lock.read_text()
            ts = int(content.split()[-1])
        except (OSError, ValueError, IndexError):
            ts = 0
        if time.time() - ts <= RECONCILE_LOCK_TTL:
            return False         # live holder — genuinely locked
        # stale — but a contender may have just refreshed it; only break
        # the lock we actually read
        try:
            if lock.read_text() != content:
                continue
        except OSError:
            continue
        lock.unlink(missing_ok=True)
    return None


def reconcile(root: Path, target: str, lane_ref: str, roots: list,
              plan: dict, blocking: list):
    lock = acquire_reconcile_lock(root)
    if lock is False:
        emit({**plan, "status": "refused", "action": "reconcile",
              "errors": [f"another reconcile holds {RECONCILE_LOCK} — "
                         "retry after it finishes"]}, 1, args.output)
    try:
        _reconcile_locked(root, target, lane_ref, roots, plan, blocking)
    finally:
        if lock:
            lock.unlink(missing_ok=True)


WIP_STASH_MSG = "cdo reconcile: ad-hoc WIP aside"
# linked worktrees surface as untracked dirs — a stash add would record
# a gitlink and the pop could fight the live tree; org machinery, not WIP
SKIP_STASH_ROOTS = [".cdo-work"]


def _wip_stash_ref(root: Path) -> str:
    """Our stash entry's ref (stash@{n}) or "" — matched by message so a
    crash-left entry from an earlier reconcile is found too."""
    for line in git(root, "stash", "list").stdout.splitlines():
        if WIP_STASH_MSG in line:
            return line.split(":", 1)[0].strip()
    return ""


def _pop_wip(root: Path) -> dict:
    """Restore the stashed ad-hoc WIP after the merge settles. A clean
    pop drops the entry; a conflicted one keeps it (git never drops on a
    conflicted pop) — the WIP is safe either way. Deferred while a merge
    is still unresolved. No-op when nothing of ours is stashed."""
    ref = _wip_stash_ref(root)
    if not ref:
        return None
    if (git_common_dir(root) / "MERGE_HEAD").exists():
        return {"status": "deferred", "ref": ref,
                "reason": "merge still unresolved — WIP stays stashed"}
    pop = git(root, "stash", "pop", ref)
    if pop.returncode == 0:
        return {"status": "restored", "ref": ref}
    conflicts = [l for l in
                 git(root, "diff", "--name-only", "--diff-filter=U")
                 .stdout.splitlines() if l.strip()]
    return {"status": "conflicts", "ref": ref,
            "files": conflicts or None,
            "detail": (pop.stderr or pop.stdout).strip()[:300]}


def _reconcile_locked(root: Path, target: str, lane_ref: str,
                      roots: list, plan: dict, blocking: list):
    """FF blocked by dirty paths or a diverged lane: stash ad-hoc WIP
    aside, checkpoint the remaining dirty paths on the lane branch
    (org-state churn), merge the target, resolve state-root conflicts
    --ours, abort on anything else — then pop the WIP back so it returns
    uncommitted, whatever the merge did."""
    merge_msg = (f"Merge {args.to} into {args.lane} — reconcile shipped "
                 "work with local state checkpoint")
    conflicts = []
    checkpoint = None
    merged = False

    # a wedged merge of OUR OWN (marker in MERGE_MSG) self-heals: finish
    # --ours resolution if every conflict is state-root, else abort and
    # re-run fresh — a foreign merge is still a hard refusal
    common = git_common_dir(root)
    if (common / "MERGE_HEAD").exists():
        msg_file = common / "MERGE_MSG"
        ours = msg_file.is_file() and "reconcile shipped work" in \
            msg_file.read_text(encoding="utf-8", errors="replace")
        if not ours:
            emit({**plan, "status": "refused", "action": "reconcile",
                  "errors": ["merge already in progress — finish or "
                             "abort it first"]}, 1, args.output)
        conflicts = [l for l in
                     git(root, "diff", "--name-only", "--diff-filter=U")
                     .stdout.splitlines() if l.strip()]
        bad = [c for c in conflicts if not under_roots(c, roots)]
        if bad:
            git(root, "merge", "--abort")
            plan["wedged_merge"] = ("aborted — conflicts outside state "
                                    "roots; fresh merge retries")
        else:
            for c in conflicts:
                git(root, "checkout", "--ours", "--", c)
                git(root, "add", "--", c)
            git(root, "commit", "--no-verify", "-qm", merge_msg)
            merged = not (common / "MERGE_HEAD").exists()
            plan["wedged_merge"] = "resumed — --ours on state-root " \
                                   "conflicts"

    if staged_paths(root):
        emit({**plan, "status": "refused", "action": "reconcile",
              "errors": ["index already staged — refusing to compound a "
                         "half-staged state"]}, 1, args.output)

    failure = None
    if not merged:
        # ad-hoc WIP (outside the state roots) goes aside into a stash —
        # Operator work is never committed onto the lane and never
        # pushes; org-state churn still checkpoints so live state
        # converges (it is always newer than the ship-time snapshot)
        stashed = [d for d in dirty_paths(root)
                   if not under_roots(d, roots)
                   and not under_roots(d, SKIP_STASH_ROOTS)
                   and Path(d).name not in RESERVED_NAMES]
        if stashed:
            sp = git(root, "stash", "push", "-u", "-m", WIP_STASH_MSG,
                     "--", *stashed)
            if sp.returncode != 0 or not _wip_stash_ref(root):
                emit({**plan, "status": "refused", "action": "reconcile",
                      "errors": ["ad-hoc WIP stash failed: "
                                 + (sp.stderr or sp.stdout)
                                 .strip()[:300]]}, 1, args.output)
            plan["adhoc_stashed"] = stashed

        # checkpoint the remaining dirty tree — org-state churn only,
        # now that ad-hoc WIP is stashed; locks dirs + reserved names
        # stay out so they never ride the lane to origin
        addable = [r for r in roots if (root / r).exists()]
        excludes = [f":(exclude)**/{n}" for n in RESERVED_NAMES] + \
            [f":(exclude){r}/locks" for r in addable]
        add = git(root, "add", "-A", "--", ".", *excludes)
        if add.returncode != 0:
            failure = ({"status": "error", "action": "reconcile",
                        "errors": [f"state checkpoint add failed: "
                                   f"{add.stderr.strip()[:200]}"]}, 2)
        else:
            # --no-verify + hooks-off merge: bookkeeping commits
            # shouldn't pay the repo's ~2min eslint gate twice per event
            ck = git(root, "commit", "--no-verify", "-qm",
                     "cdo state: checkpoint — org-state churn"
                     " ahead of lane advance")
            checkpoint = git(root, "rev-parse", "HEAD").stdout.strip() \
                if ck.returncode == 0 else None

            with tempfile.TemporaryDirectory(
                    prefix="cdo-hooks-") as hooks_off:
                mg = git(root, "-c", f"core.hooksPath={hooks_off}",
                         "merge", "--no-ff", "-m", merge_msg, target)
            merged = mg.returncode == 0
            if not merged:
                conflicts = [l for l in
                             git(root, "diff", "--name-only",
                                 "--diff-filter=U")
                             .stdout.splitlines() if l.strip()]
                bad = [c for c in conflicts
                       if not under_roots(c, roots)]
                if bad:
                    git(root, "merge", "--abort")
                    failure = (
                        {"status": "refused", "action": "reconcile",
                         "checkpoint": checkpoint, "blocking": blocking,
                         "errors": ["merge conflicts outside state "
                                    "roots — aborted; ad-hoc WIP "
                                    "restores from the stash, "
                                    "reconcile by hand: "
                                    + ", ".join(bad[:12])]}, 1)
                else:
                    for c in conflicts:
                        git(root, "checkout", "--ours", "--", c)
                        git(root, "add", "--", c)
                    git(root, "commit", "--no-verify", "-qm", merge_msg)
                    merged = not (common / "MERGE_HEAD").exists()
            if not merged and failure is None:
                failure = (
                    {"status": "refused", "action": "reconcile",
                     "checkpoint": checkpoint,
                     "errors": [(mg.stderr or mg.stdout).strip()[:400]]},
                    1)

    # WIP comes home regardless of how the merge went — restored
    # uncommitted, or kept in the stash with the conflict named
    pop = _pop_wip(root)
    if pop:
        plan["stash_pop"] = pop
    if failure:
        emit({**plan, **failure[0]}, failure[1], args.output)

    new_head = git(root, "rev-parse", "HEAD").stdout.strip()
    ref_advanced = None
    if args.to.startswith("refs/heads/") and args.to != lane_ref:
        adv = git(root, "update-ref", args.to, new_head, target)
        ref_advanced = adv.returncode == 0

    emit({**plan, "status": "reconciled", "checkpoint": checkpoint,
          "merge": new_head, "conflicts_ours": conflicts or None,
          "ref_advanced": ref_advanced}, 0, args.output)


def main():
    global args
    args = parse_args()
    root = Path(args.project_root).resolve()
    probe = git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        emit({"status": "error",
              "errors": [f"not a git work tree: {root}"]}, 2, args.output)
    cmd_run(root)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
