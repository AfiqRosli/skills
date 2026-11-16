#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""spawn-dispatch.py — launch a dispatch as its own Devin session.

Confirmed alignment IS the dispatch order: nobody asks before spawning.
Dispatch is LINEAR — one worker session (`w-drain-{ts}`) drains the pool,
key by key, on a single branch (the ship lane, `preview` by default). The
session keeps working while the org has work: the confirmed queue, then
review mop-ups, then a clean exit — alignment drafting is
explicit-command only and knowledge extraction is manual-only, never
drain work.

  local (default):  detached acp-worker supervisor → `devin acp` ACP
                    session — visible + resumable in the IDE's session list
                    (auth: DEVIN_API_KEY env, per-session authenticate)
  cloud (--cloud):  devin --cloud -p --prompt-file {prompt}

Cloud sessions run on a fresh clone — they see only what was PUSHED. For
kind=dispatch this script first runs push-state.py: dirty orchestration
state is committed and HEAD goes to origin/{ship lane} so the worker's
checkout carries the confirmed pool it was spawned for. The worker commits
per story and pushes `HEAD:{lane}` directly — there are no cdo/* branches
and nothing to merge; verify happens BEFORE each push so unverified code
never lands on the lane.

Local drains are pre-deploy gated instead: each story's ship lands on the
local-only `cdo-lane` ref (never pushed — worktrees base on it), and the
origin push happens later via cdo-platform push when the Operator signs a
`## Pre-deploy Sign-offs` item. Cloud drains can't hold that gate — the
clone's only way home is pushing.

Spawn-time lock: locks/g-{first}-{ts}.lock holds every queued key locally —
written BEFORE the process launches (the guard can't race a second spawn),
and a fresh g-* lock refuses a new dispatch outright unless --force
(GROUP_LOCK_TTL — see ready-set.py).

Per-spawn artifacts under {orchestration_dir}/sessions/:
  {stem}.prompt.md   — the worker's dispatch prompt
  {stem}.json        — spawn record {keys, pid, session_name, lane, cmd}
  {stem}.log         — supervisor stdout + session/update JSONL stream
  {stem}.acp.json    — ACP terminal record {session_id, stop_reason, usage}
                       (local mode; the session is also resumable in the
                       IDE by its session_id)
  stem = `drain` for a queued dispatch (--keys), else the single key

A dead worker leaves its lock to go stale — the watchdog breaks it and
recovery marks the story orphaned. Spawn itself never supervises.

Usage:
  uv run spawn-dispatch.py --orchestration-dir /path/docs/orchestration
      --project-root /path/project [--key 13-08-… | --keys k1,k2]
      [--kind dispatch|review|wave|academy] [--cloud|--local]
      [--session-name w-drain-...] [--base-ref origin/preview] [--no-push]
      [--permission-mode bypass] [--prompt "..."] [--devin-bin devin]
      [--dry-run] [-o result.json]

Exit codes: 0=spawned, 1=refused (devin missing / bad args / push refused),
2=runtime error
"""

import argparse
import json
import os
import re
import subprocess
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "references" / "prompts"


def _load_prompt(name: str) -> str:
    """13-30 — prompts live as versioned files (references/prompts/*.md) so
    reviewers can cite contract versions; the header comment is stripped."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return re.sub(r"^<!--.*?-->\s*", "", text, flags=re.S)

PROMPT_TEMPLATE = _load_prompt("dispatch")

# One shared drain contract — local and cloud differ only in environment
# setup, the per-story ship step, and the drain-lock epilogue. Any drift
# between the two variants is a defect, not a choice.
DRAIN_BODY_TEMPLATE = _load_prompt("drain-body")

LOCAL_ENV_NOTE = _load_prompt("local-env-note")

WORKTREE_ENV_NOTE = _load_prompt("worktree-env-note")

LOCAL_SHIP_STEP = _load_prompt("local-ship-step")

WORKTREE_SHIP_STEP = _load_prompt("worktree-ship-step")

LOCAL_LOCK_NOTE = _load_prompt("local-lock-note")

LOCAL_CONTINUATION = _load_prompt("local-continuation")

CLOUD_CONTINUATION = LOCAL_CONTINUATION

CLOUD_ENV_NOTE = _load_prompt("cloud-env-note")

CLOUD_SHIP_STEP = _load_prompt("cloud-ship-step")

CLOUD_RECOMPUTE_CAVEAT = _load_prompt("cloud-recompute-caveat")

CLOUD_FINAL_PUSH = _load_prompt("cloud-final-push")

CLOUD_LOCK_NOTE = _load_prompt("cloud-lock-note")


def drain_prompt(cloud: bool, worktree: bool = False, **fmt) -> str:
    """Compose the drain brief — shared body, lane-specific inserts. The
    inserts are pre-formatted with the same context so `{lane}`/`{drain_id}`
    resolve and `{{key}}` collapses to the literal `{key}` the worker fills."""
    pick = lambda local, cloud_: (cloud_ if cloud else local).format(**fmt)
    env_note = (WORKTREE_ENV_NOTE if worktree else LOCAL_ENV_NOTE) if not cloud         else CLOUD_ENV_NOTE
    ship_step = (WORKTREE_SHIP_STEP if worktree else LOCAL_SHIP_STEP) if not cloud         else CLOUD_SHIP_STEP
    return DRAIN_BODY_TEMPLATE.format(
        environment_note=env_note.format(**fmt),
        ship_step=ship_step.format(**fmt),
        recompute_caveat=pick("", CLOUD_RECOMPUTE_CAVEAT),
        final_push=pick("", CLOUD_FINAL_PUSH),
        continuation_clause=pick(LOCAL_CONTINUATION, CLOUD_CONTINUATION),
        lock_note=pick(LOCAL_LOCK_NOTE, CLOUD_LOCK_NOTE),
        **fmt)

CLOUD_PREAMBLE = _load_prompt("cloud-preamble")

REVIEW_PROMPT_TEMPLATE = _load_prompt("review")

ACADEMY_PROMPT_TEMPLATE = _load_prompt("academy")

WAVE_PROMPT_TEMPLATE = _load_prompt("wave")


TEMPLATES = {"dispatch": PROMPT_TEMPLATE, "review": REVIEW_PROMPT_TEMPLATE,
             "wave": WAVE_PROMPT_TEMPLATE, "academy": ACADEMY_PROMPT_TEMPLATE}


def parse_args():
    p = argparse.ArgumentParser(description="Spawn a dispatch worker session.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--key", default="",
                   help="single story key (or batch id for --kind wave)")
    p.add_argument("--keys", default="",
                   help="comma list — the drain queue: one linear session "
                        "runs the keys in emitted order (ready-set.py's "
                        "dispatch_now)")
    p.add_argument("--project-root", required=True)
    p.add_argument("--kind", choices=["dispatch", "review", "wave", "academy"],
                   default="dispatch",
                   help="dispatch = story worker(s) (w-drain for a queue or "
                        "cloud, w-{key} for a lone local story); review = "
                        "per-story delivered-review (r-{key}, {key}.review.* "
                        "artifacts); wave = batch-drain holistic read "
                        "(--key {batch_id}); academy = post-ship extraction "
                        "worker (a-{key}, {key}.academy.* artifacts — "
                        "manual leg: Marshal/Operator-invoked only, never "
                        "auto-spawned on ship)")
    target = p.add_mutually_exclusive_group()
    target.add_argument("--cloud", action="store_true",
                        help="spawn a Devin Cloud session (default when "
                             "cdo.dispatch_target is cloud)")
    target.add_argument("--local", action="store_true",
                        help="spawn a detached local `devin -p` worker")
    p.add_argument("--base-ref", default="",
                   help="git ref the cloud worker checks out (default: "
                        "origin/{ship lane})")
    p.add_argument("--no-push", action="store_true",
                   help="skip the pre-spawn push-state (dispatch+cloud only)")
    p.add_argument("--session-name", default="",
                   help="lock/session identity the worker uses (default: "
                        "w-drain-{ts} for a queue, w-{key}-{ts} single, "
                        "r-{key}-{ts} for --kind review)")
    p.add_argument("--tab-id", default="",
                   help="IDE space the session joins "
                        "(cognition.ai/requestingTabId; default cdo-{kind} "
                        "so workers/reviews cluster by family)")
    p.add_argument("--permission-mode", default="",
                   help="devin --permission-mode for LOCAL workers "
                        "(default: cdo.dispatch_permission_mode, else bypass; "
                        "ignored for cloud)")
    p.add_argument("--prompt", default="", help="override the dispatch prompt")
    p.add_argument("--prompt-file", default="", help="use an existing prompt file")
    p.add_argument("--devin-bin", default="devin")
    p.add_argument("--model", default="",
                   help="worker model — baked into the shim as DEVIN_MODEL "
                        "(default: DEVIN_MODEL env > cdo.dispatch_model > "
                        "GLM-5.3 Flash Low; 13-45)")
    p.add_argument("--env-file", default="",
                   help="env file for DEVIN_API_KEY when the env var is unset "
                        "(default: {project-root}/.env if present)")
    p.add_argument("--force", action="store_true",
                   help="spawn a drain even while a fresh g-* drain lock "
                        "exists — breaks the one-drain invariant by hand")
    p.add_argument("--continuation", action="store_true",
                   help="successor drain spawned by a continuing drain — "
                        "bypasses the fresh g-* check (caller exits once this "
                        "spawn lands); no double-drain window")
    p.add_argument("--story-budget", type=int, default=0,
                   help="stories this drain may complete before it hands the "
                        "queue to a successor (default cdo.drain_story_budget)")
    p.add_argument("--no-worktree", action="store_true",
                   help="local drains spawn in the shared checkout instead of "
                        "an isolated .cdo-work/{drain_id} git worktree "
                        "(debug escape hatch; worktree is the default)")
    p.add_argument("--dry-run", action="store_true",
                   help="emit the command + prompt + push plan, spawn nothing")
    p.add_argument("-o", "--output")
    return p.parse_args()


def ref_exists(root: Path, ref: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", "--quiet", ref],
        capture_output=True).returncode == 0


def emit(result: dict, code: int, out: str):
    blob = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


def resolve_devin(name: str):
    """Resolve the devin binary; .cmd/.bat shims need cmd /c on Windows."""
    resolved = shutil.which(name)
    if not resolved:
        return None, None
    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", resolved], resolved
    return [resolved], resolved


def config_scalar(root: Path, name: str, default: str) -> str:
    """cdo.{name} from _bmad/config.yaml — no pyyaml dep, scan the scalar."""
    cfg = root / "_bmad" / "config.yaml"
    if cfg.is_file():
        try:
            m = re.search(rf"^\s*{re.escape(name)}:\s*['\"]?([\w-]+)",
                          cfg.read_text(encoding="utf-8"), re.M)
            if m:
                return m.group(1)
        except OSError:
            pass
    return default


def config_str(root: Path, name: str, default: str) -> str:
    """cdo.{name} as a free string (spaces allowed, quoted or bare to EOL).
    config_scalar's \\w- pattern can't carry 'GLM-5.3 Flash Low' (13-45).
    Quoted values may contain any chars incl. quotes' neighbors; bare
    values stop at # (comment) or EOL (F4 — a mid-string quote no longer
    truncates)."""
    cfg = root / "_bmad" / "config.yaml"
    if cfg.is_file():
        try:
            m = re.search(
                rf"^\s*{re.escape(name)}:\s*(?:['\"]([^'\"\n]*)['\"]"
                rf"|([^#'\"\n]*?))\s*$",
                cfg.read_text(encoding="utf-8"), re.M)
            if m and (m.group(1) or m.group(2) or "").strip():
                return (m.group(1) or m.group(2) or "").strip()
        except OSError:
            pass
    return default


# 13-45 F2 — the model string is interpolated into a cmd shim
# (`set DEVIN_MODEL=...`); a hostile or careless value containing cmd
# metacharacters could break or inject into the shim. Allowlist: word
# chars, spaces, dots, dashes, slashes, underscores, parens.
MODEL_RE = re.compile(r"^[\w .()/+,+-]+$")


def model_valid(model: str) -> bool:
    return bool(model) and MODEL_RE.match(model) is not None


def env_value(env_file: str, key: str):
    """KEY=value from an env-file — blank lines/# comments skipped."""
    if not env_file:
        return ""
    try:
        for line in Path(env_file).read_text(
                encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def user_name(root: Path) -> str:
    """Operator identity — TOML core.user_name via the installer's resolver
    (canonical on BMAD v6.12+), then _bmad/config.user.yaml `user_name`,
    then the shared config's root key, else a bare 'Operator'."""
    script = root / "_bmad" / "scripts" / "resolve_config.py"
    if script.is_file():
        try:
            proc = subprocess.run(
                ["uv", "run", str(script), "--project-root", str(root),
                 "--key", "core.user_name"],
                capture_output=True, text=True, timeout=60)
            if proc.returncode == 0:
                name = json.loads(proc.stdout).get("core.user_name", "")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            pass
    for cfg in (root / "_bmad" / "config.user.yaml",
                root / "_bmad" / "config.yaml"):
        if cfg.is_file():
            try:
                m = re.search(r"^\s*user_name:\s*['\"]?([^'\"\n]+)",
                              cfg.read_text(encoding="utf-8"), re.M)
                if m and m.group(1).strip():
                    return m.group(1).strip()
            except OSError:
                pass
    return ""


DRAIN_LOCK_TTL_MINUTES = 24 * 60  # mirrors ready-set.py GROUP_LOCK_TTL_MINUTES


def fresh_drain_lock(orch: Path):
    """ALL live g-* drain locks — the per-key-set drain guard. Fresh =
    younger than the 24h TTL; older markers are stale work for the janitor.
    13-45 makes the guard intersection-based: parallel group drains with
    DISJOINT key sets are the deterministic spawn plan, only overlapping
    keys refuse — so EVERY fresh lock must be examined, not just the first
    (two locks coexist by design under parallel groups)."""
    locks_dir = orch / "locks"
    if not locks_dir.is_dir():
        return []
    live = []
    for f in sorted(locks_dir.glob("g-*.lock")):
        parts = f.read_text(encoding="utf-8", errors="replace").split()
        try:
            ts = datetime.strptime(parts[1] if len(parts) > 1 else "",
                                   "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        age = (datetime.now(timezone.utc) - ts).total_seconds() / 60
        if age < DRAIN_LOCK_TTL_MINUTES and not _drain_terminal(
                orch, parts[0] if parts else None, f.stem, ts):
            live.append({"path": f, "session": parts[0] if parts else None,
                         "age_minutes": age,
                         "keys": set(parts[2].split(",")) if len(parts) > 2 else set()})
    return live


def _drain_terminal(orch: Path, session: str | None, drain_id: str,
                    lock_ts: datetime) -> bool:
    """A g-* marker is stale the moment its worker provably ended — the
    session's ACP terminal record exists, or the drain's final report
    (sessions/drain.md or sessions/{drain_id}.md) is newer than the lock.
    The 24h TTL is the backstop for a lost marker, not the primary signal —
    a dead drain's leftover lock must never refuse a new spawn for
    confirmations that landed after it exited."""
    sess = orch / "sessions"
    if session and (sess / f"{session}.acp.json").is_file():
        return True
    for name in (sess / "drain.md", sess / f"{drain_id}.md"):
        try:
            if name.is_file() and datetime.fromtimestamp(
                    name.stat().st_mtime, timezone.utc) > lock_ts:
                return True
        except OSError:
            pass
    return False


def mint_batch(orch: Path, batch_id: str, keys: list):
    """Stamp ledger.batch — the batch the wave review closes over. Nothing
    else in the linear flow writes it; a failure here is bookkeeping, not
    a dispatch defect, so it degrades to a warning."""
    try:
        import yaml
        lpath = orch / "flow-ledger.yaml"
        ledger = yaml.safe_load(lpath.read_text(encoding="utf-8"))
        ledger["batch"] = {"id": batch_id, "manifest": keys}
        lpath.write_text(yaml.safe_dump(ledger, sort_keys=False),
                         encoding="utf-8")
        return True
    except Exception:
        return False


def push_state(root: Path, orch: Path, lane: str, message: str):
    """Commit + push orchestration state so a cloud clone sees the pool."""
    script = Path(__file__).parent / "push-state.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--project-root", str(root),
         "--orchestration-dir", str(orch), "--lane", lane,
         "--message", message],
        capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"errors": [proc.stderr.strip() or
                                            "push-state produced no output"]}


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    root = Path(args.project_root).resolve()
    if not orch.is_dir():
        emit({"errors": [f"orchestration dir not found: {orch}"]}, 2, args.output)
    if not root.is_dir():
        emit({"errors": [f"project root not found: {root}"]}, 2, args.output)

    kind = args.kind
    keys = [k.strip() for k in (args.keys or args.key).split(",") if k.strip()]
    if not keys:
        emit({"errors": ["no key(s) — pass --key or --keys"]}, 1, args.output)
    if kind != "dispatch" and len(keys) > 1:
        emit({"errors": [f"--kind {kind} takes a single --key"]}, 1, args.output)
    key = keys[0]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    lane = config_scalar(root, "ship_target", "preview")
    target = ("cloud" if args.cloud else "local" if args.local
              else config_scalar(root, "dispatch_target", "local"))
    use_cloud = target == "cloud"

    # ACP workers authenticate per-session with the API key — refuse early
    # when neither the env nor the env-file can provide it
    env_file = args.env_file or str(root / ".env")
    api_key_missing = (
        not use_cloud
        and not os.environ.get("DEVIN_API_KEY", "").strip()
        and not env_value(env_file, "DEVIN_API_KEY"))

    # auto-triggered kinds (review/wave) honor dispatch_mode: manual —
    # dispatch and academy kinds are Marshal's deliberate acts and stay
    # ungated (extraction is never auto-spawned by workers, so a --kind
    # academy call is by definition deliberate)
    if kind not in ("dispatch", "academy") and \
            config_scalar(root, "dispatch_mode", "auto") == "manual":
        emit({"errors": [f"dispatch_mode is manual — {kind} sessions are not "
                         "auto-spawned; run the leg inline or by hand"]},
             1, args.output)

    # one drain per key-set — a fresh g-* lock whose keys OVERLAP this spawn's
    # keys means a drain already owns them; disjoint groups spawn in parallel
    # (13-45 deterministic spawn plan). Stale markers are the janitor's.
    if kind == "dispatch" and not args.force and not args.continuation             and not args.dry_run:
        overlaps = []
        for held in fresh_drain_lock(orch):
            hit = sorted(held["keys"] & set(keys))
            if hit:
                overlaps.append(f"{held['path'].name} ({held['age_minutes']:.0f}m "
                                f"old, held by {held['session']}) holds: "
                                f"{', '.join(hit)}")
        if overlaps:
            emit({"errors": [
                "drain lock conflict — the org runs ONE drain per key-set; "
                "--force overrides"] + overlaps}, 1, args.output)

    drain_id = f"g-{key.lower()}-{ts}"
    drain = kind == "dispatch" and (use_cloud or len(keys) > 1)
    stem = "drain" if drain else \
        (f"wave-{key}" if kind == "wave" else
         (key if kind == "dispatch" else f"{key}.{kind}"))
    session_name = args.session_name or {
        "dispatch": f"w-drain-{ts}" if drain else f"w-{key}-{ts}",
        "review": f"r-{key}-{ts}",
        "wave": f"w-review-{key}-{ts}",
        "academy": f"a-{key}-{ts}",
    }[kind]
    operator = f"Operator {n}" if (n := user_name(root)) else "the Operator"
    permission_mode = args.permission_mode or config_scalar(
        root, "dispatch_permission_mode", "bypass")
    # 13-45 — explicit model capability: arg > config > hard default. Baked
    # into the Windows shim as DEVIN_MODEL so the external console carries
    # it deterministically (env inheritance dies at the WMI boundary).
    # 13-48 — the caller's own DEVIN_MODEL sits between arg and config: a
    # worker spawning satellites (academy extract, delivery review,
    # continuation drain) hands down ITS effective model instead of
    # silently re-resolving to the config default — the gap that ran
    # GLM-5.3 Flash Low satellites inside an SWE-2 High drain. An env
    # value failing the shim allowlist is skipped with a warning, never
    # baked — env is ambient, not caller-controlled.
    env_model = os.environ.get("DEVIN_MODEL", "").strip()
    config_model = config_str(root, "dispatch_model", "")
    spawn_warnings = []
    if args.model:
        model, model_source = args.model, "arg"
    elif env_model and model_valid(env_model):
        model, model_source = env_model, "env"
    else:
        if env_model:
            spawn_warnings.append(
                f"DEVIN_MODEL env {env_model!r} failed the shim allowlist "
                "— skipped, not inherited")
        if config_model:
            model, model_source = config_model, "config"
        else:
            model, model_source = "GLM-5.3 Flash Low", "default"
    if not model_valid(model):
        emit({"errors": [f"invalid model {model!r} — allowed chars: "
                         "letters, digits, spaces, . ( ) / + - _ "
                         "(the value is baked into a cmd shim; F2)"]},
             1, args.output)

    # base ref: explicit arg wins, else the freshest local integration
    # state — cdo-lane first (the lane tip the mirror may lag behind),
    # then the local {lane} branch, then origin/{lane} as the last
    # fallback (fresh repo, pre-first-ship)
    base_ref = args.base_ref
    if not base_ref:
        for cand in (f"refs/heads/cdo-lane", f"refs/heads/{lane}"):
            if subprocess.run(
                    ["git", "-C", str(root), "show-ref", "--verify",
                     "--quiet", cand]).returncode == 0:
                base_ref = cand
                break
        base_ref = base_ref or f"origin/{lane}"

    sessions_dir = orch / "sessions"
    sessions_dir.mkdir(exist_ok=True)

    # 13-29 — local drains run isolated: .cdo-work/{drain_id} worktree, the
    # worker's cwd + code live there, while {orch} (sessions/locks/ledger)
    # stays in the main checkout — the prompt pins the absolute orch path
    # so state never forks. Base ref: the local integration lane `cdo-lane`
    # when it exists (pre-deploy gating — landed-but-unpushed work lives
    # there, so dependents and later drains still see it); else origin/lane.
    use_worktree = drain and not use_cloud and not args.no_worktree
    work_dir = None
    worktree_warnings = []
    if use_worktree:
        work_dir = Path(root) / ".cdo-work" / drain_id
        if not args.dry_run:
            subprocess.run(["git", "-C", str(root), "fetch", "origin", lane],
                           capture_output=True)
        # base: freshest integration point first — cdo-lane (shipped,
        # unpushed), then local {lane} mirror, then the remote tracking ref
        if args.base_ref:
            base = args.base_ref
        elif ref_exists(root, "refs/heads/cdo-lane"):
            base = "refs/heads/cdo-lane"
        elif ref_exists(root, f"refs/heads/{lane}"):
            base = f"refs/heads/{lane}"
        else:
            base = f"origin/{lane}"
        behind = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count",
             f"cdo-lane..origin/{lane}"], capture_output=True, text=True)
        if base == "refs/heads/cdo-lane" and \
                behind.stdout.strip() not in ("", "0"):
            worktree_warnings.append(
                f"origin/{lane} is {behind.stdout.strip()} commit(s) ahead "
                "of cdo-lane — reconcile before the pre-deploy push "
                "(non-FF will refuse)")
        base_ref = base
        if not args.dry_run:
            wt = subprocess.run(
                ["git", "-C", str(root), "worktree", "add", "--detach",
                 str(work_dir), base],
                capture_output=True, text=True)
            if wt.returncode != 0:
                emit({"errors": [f"worktree add failed: {wt.stderr.strip()}"]},
                     1, args.output)
        work_dir = work_dir.resolve()

    # the prompt — caller-supplied, a file, or the kind's standard brief
    if args.prompt_file:
        prompt_path = Path(args.prompt_file).resolve()
        if not prompt_path.is_file():
            emit({"errors": [f"prompt file not found: {prompt_path}"]}, 1, args.output)
    else:
        prompt_path = sessions_dir / f"{stem}.prompt.md"
        if kind == "dispatch" and drain:
            story_budget = args.story_budget or int(config_scalar(
                root, "drain_story_budget", "4") or "4")
            prompt_text = args.prompt or drain_prompt(
                use_cloud, worktree=use_worktree,
                keys_csv=", ".join(keys), session=session_name,
                drain_id=drain_id, orch=orch, lane=lane, operator=operator,
                project_root=root, story_budget=story_budget,
                work_dir=work_dir or "")
        else:
            prompt_text = args.prompt or TEMPLATES[kind].format(
                key=key, session=session_name, orch=orch, drain_id=drain_id,
                operator=operator)
            if use_cloud:
                prompt_text = CLOUD_PREAMBLE.format(
                    base_ref=base_ref, lane=lane,
                    kind=kind, stem=stem) + prompt_text
        prompt_path.write_text(prompt_text, encoding="utf-8")

    log_path = sessions_dir / f"{stem}.log"
    record_path = sessions_dir / f"{stem}.json"

    argv_prefix, resolved = resolve_devin(args.devin_bin)
    if not resolved:
        if not args.dry_run:
            emit({"errors": [f"devin binary not found on PATH ({args.devin_bin}) — "
                             "dispatch workers can't spawn without it"]},
                 1, args.output)
        argv_prefix = [args.devin_bin]
        record_devin_missing = True
    else:
        record_devin_missing = False
    if api_key_missing and not args.dry_run:
        emit({"errors": ["DEVIN_API_KEY unset — local ACP workers "
                         "authenticate per-session with it; set it in the "
                         "environment before dispatching"]}, 1, args.output)

    # cloud dispatch: the clone must see the confirmed pool — commit dirty
    # orchestration state and push HEAD to the ship lane BEFORE spawning
    push_result = None
    if use_cloud and kind == "dispatch" and not args.no_push:
        if args.dry_run:
            push_result = {"would_run": f"push-state.py → origin/{lane}"}
        else:
            rc, push_result = push_state(
                root, orch, lane, f"dispatch pool: {', '.join(keys)}")
            if rc != 0:
                emit({"errors": ["pre-spawn state push failed — the cloud "
                                 "worker would clone a pool that doesn't "
                                 "exist"] + push_result.get("errors", []),
                      "push": push_result}, 1, args.output)

    acp_record_path = sessions_dir / f"{stem}.acp.json"
    if use_cloud:
        cmd = argv_prefix + ["--cloud", "-p", "--prompt-file", str(prompt_path)]
    else:
        # detached supervisor → `devin acp` ACP session; the session lands in
        # sessions.db, so the worker is visible + resumable in the IDE list
        worker = Path(__file__).parent / "acp-worker.py"
        cmd = [sys.executable, str(worker),
               "--project-root", str(work_dir or root),
               "--orchestration-dir", str(orch),
               "--prompt-file", str(prompt_path),
               "--devin-bin", args.devin_bin,
               "--env-file", env_file,
               "--model", model,
               "--mode", permission_mode,
               "--tab-id", args.tab_id or f"cdo-{kind}",
               "--session-json", str(acp_record_path),
               "--log", str(log_path),
               "--echo"]

    record = {
        "key": key,
        "keys": keys,
        "kind": kind,
        "target": target,
        "drain_id": drain_id if kind == "dispatch" else None,
        "session_name": session_name,
        "lane": lane if use_cloud else None,
        "base_ref": base_ref if (use_cloud or work_dir) else None,
        "worktree": str(work_dir) if work_dir else None,
        "warnings": (worktree_warnings + spawn_warnings) or None,
        "push": push_result,
        "started": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M"),
        "permission_mode": None if use_cloud else permission_mode,
        "model": model,
        "model_source": model_source,
        # 13-48 — which calls ran on/off the Operator's model. `lead` is the
        # worker session's model (devin acp --model + DEVIN_MODEL shim);
        # `sidekick` is the intra-session subagent (Devin "sidekick") whose
        # model the server-side assignment service picks per the harness
        # pairing — no per-call lever exists (DEVIN_HARNESS* envs propagate
        # by inheritance but select registry bundles, not arbitrary models).
        "model_coverage": {
            "lead": model,
            "lead_source": model_source,
            "sidekick": "registry-assigned",
            **({"harness_env": os.environ["DEVIN_HARNESS"]}
               if os.environ.get("DEVIN_HARNESS") else {}),
        },
        "prompt_file": str(prompt_path),
        "session_json": None if use_cloud else str(acp_record_path),
        "export": None,
        "log": str(log_path),
        "cmd": cmd,
    }

    if args.dry_run:
        record["dry_run"] = True
        if record_devin_missing:
            record["warning"] = f"devin binary not resolved ({args.devin_bin})"
        if api_key_missing:
            record["warning"] = (record.get("warning", "") +
                                 " DEVIN_API_KEY unset").strip()
        emit({"status": "dry-run", "spawn": record}, 0, args.output)

    # drain lock BEFORE the process exists — a post-spawn write re-opens the
    # exact double-dispatch race the marker guards. Local-only (uncommitted);
    # the drain's final act removes it, or the janitor expires it on the
    # pushed sessions/drain.md / the 24h TTL.
    lock_path = None
    if kind == "dispatch":
        (orch / "locks").mkdir(exist_ok=True)
        lock_path = orch / "locks" / f"{drain_id}.lock"
        lock_path.write_text(
            f"{session_name} "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')} "
            f"{','.join(keys)}",
            encoding="utf-8")

    log_f = open(log_path, "ab")
    try:
        if os.name == "nt":
            # WMI spawn — the worker is parented to the WMI service host,
            # outside the caller's job object / shell session tree. A
            # detached Popen still gets reaped when the spawning context
            # exits (Task Scheduler job close, exec-session cleanup).
            # The shim runs VISIBLE (default startup) with the worker's
            # --echo progress tee'd to a side log — the operator watches
            # the console; drain.log/acp.json stay the durable record.
            shim = orch / "sessions" / f"{session_name}.cmd"
            shim.write_text(
                "@echo off\r\n"
                "set PYTHONIOENCODING=utf-8\r\n"
                "set PYTHONUTF8=1\r\n"
                f"set DEVIN_MODEL={model}\r\n"
                f"{subprocess.list2cmdline(cmd)} 2>&1 | "
                "powershell -NoProfile -Command \"$input | "
                "Tee-Object -FilePath '"
                f"{orch / 'sessions' / f'{session_name}.out.log'}'\"\r\n",
                encoding="utf-8")
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "$r = Invoke-CimMethod -ClassName Win32_Process "
                 "-MethodName Create -Arguments @{ CommandLine = "
                 f"'cmd.exe /c \"{shim}\"'; CurrentDirectory = "
                 f"'{work_dir or root}' }}; if ($r.ReturnValue -eq 0) "
                 "{ Write-Output $r.ProcessId } else { exit 1 }"],
                capture_output=True, text=True, timeout=30)
            if r.returncode != 0 or not r.stdout.strip():
                raise OSError("WMI spawn failed: "
                              f"{r.stderr.strip() or r.stdout.strip()}")
            # the tracked pid is cmd.exe /c — lives exactly as long as
            # the worker it wraps
            proc = type("_Proc", (),
                        {"pid": int(r.stdout.strip().splitlines()[-1])})()
        else:
            env = dict(os.environ)
            env["DEVIN_MODEL"] = model
            proc = subprocess.Popen(
                cmd, cwd=str(work_dir or root), stdout=log_f,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                close_fds=True, start_new_session=True, env=env)
    except OSError as e:
        log_f.close()
        if lock_path:
            lock_path.unlink(missing_ok=True)
        emit({"errors": [f"spawn failed: {e}"]}, 2, args.output)
    finally:
        if not log_f.closed:
            log_f.close()

    # mint the batch — the wave review reads ledger.batch.id; nothing else
    # in the linear flow writes it
    if kind == "dispatch":
        record["batch"] = f"b{ts}" if mint_batch(orch, f"b{ts}", keys) \
            else {"warning": "flow-ledger batch stamp failed — wave "
                             "review won't auto-fire"}

    record["pid"] = proc.pid
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    emit({"status": "spawned", "keys": keys, "pid": proc.pid,
          "session_name": session_name, "target": target,
          "model": model, "model_source": model_source,
          "lane": lane if use_cloud else None,
          "warnings": (worktree_warnings + spawn_warnings) or None,
          "record": str(record_path)},
         0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
