#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""acp-worker.py — run one CDO worker prompt as a local Devin ACP session.

`devin -p` needs `devin auth login` (OAuth); `devin acp` authenticates with
the API key the IDE already uses — and sessions it creates land in the same
`sessions.db` the IDE's session picker reads, so a spawned worker is visible
and resumable like any chat session.

This script is the detached supervisor spawn-dispatch launches: it owns the
`devin acp` child for the session's lifetime, speaks the ACP JSON-RPC over
stdio, streams `session/update` notifications to --log (JSONL), and writes
the terminal record — session_id, stopReason, token usage — to --session-json.

Lifecycle: initialize → authenticate (DEVIN_API_KEY) → session/new →
session/set_mode (--mode, bypass for unattended workers) → session/prompt →
wait for the prompt response or child exit.

Usage:
  uv run acp-worker.py --project-root /path/project
      --orchestration-dir /path/docs/orchestration
      --prompt-file /path/prompt.md [--devin-bin devin]
      [--mode bypass] [--session-json out.json] [--log out.log]
      [--api-key-env DEVIN_API_KEY]

Exit codes: 0=turn completed (any stopReason — the worker's own outcome
lives in the ledger, not here), 1=refused (no api key / devin missing /
handshake or spawn failure), 2=child died mid-turn
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Run a worker prompt as a local "
                                           "Devin ACP session.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--devin-bin", default="devin")
    p.add_argument("--mode", default="bypass",
                   help="ACP session modeId — bypass for unattended workers")
    p.add_argument("--session-json", required=True,
                   help="terminal record: session_id, stopReason, usage")
    p.add_argument("--log", required=True,
                   help="session/update notification stream, JSONL")
    p.add_argument("--model", default="",
                   help="model for the ACP session — passed explicitly to "
                        "`devin acp --model` (13-48; env DEVIN_MODEL still "
                        "reaches the child by inheritance as a fallback)")
    p.add_argument("--api-key-env", default="DEVIN_API_KEY")
    p.add_argument("--env-file", default="",
                   help="KEY=value file consulted when the env var is unset "
                        "(the CDO --env-file convention)")
    p.add_argument("--tab-id", default="",
                   help="IDE space id (windsurfSpace.metadata key) the "
                        "session joins — also sent as "
                        "cognition.ai/requestingTabId")
    p.add_argument("--space-db", default="",
                   help="Devin Desktop globalStorage state.vscdb path for "
                        "space membership writes (default: "
                        "%%APPDATA%%/Devin/User/globalStorage/state.vscdb)")
    p.add_argument("--echo", action="store_true",
                   help="mirror compact progress lines to stdout — the "
                        "spawn shim shows them in the external console")
    return p.parse_args()


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


def emit(result: dict, code: int, out: str):
    Path(out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    sys.exit(code)


def join_space(db_path: str, space_id: str, session_id: str) -> str:
    """Register the session's resource into `resourceToSpace[space_id]` —
    the IDE's own session→space map. Returns '' on success else the reason.

    The IDE may hold ItemTable in memory and overwrite on a later flush —
    best-effort; callers should note the result, not depend on it."""
    if not db_path or not space_id:
        return "no space db / tab id"
    if not Path(db_path).is_file():
        return f"space db not found: {db_path}"
    uri = f"vscode-cascade-editor:///cascade-acp/devin-cli/{session_id}"
    try:
        con = sqlite3.connect(db_path, timeout=5)
        try:
            meta = con.execute(
                "select value from ItemTable where key='windsurfSpace.metadata'"
            ).fetchone()
            spaces = json.loads(meta[0]) if meta and meta[0] else {}
            if space_id not in spaces:
                # accept a space title too — ids are machine-generated
                # ({ts}-{rand}), humans name spaces
                match = [sid for sid, m in spaces.items()
                         if m.get("title") == space_id]
                if match:
                    space_id = match[0]
                elif spaces:
                    # the logical name doesn't exist as a space — fall back
                    # to the most-recently-active one so the session still
                    # lands where the human is actually looking
                    space_id = max(
                        spaces.items(),
                        key=lambda kv: kv[1].get("lastAccessed", 0))[0]
                else:
                    return f"space not in windsurfSpace.metadata: {space_id}"
            row = con.execute(
                "select value from ItemTable where key='windsurfSpace.resourceToSpace'"
            ).fetchone()
            r2s = json.loads(row[0]) if row and row[0] else {}
            members = r2s.setdefault(space_id, [])
            if uri not in members:
                members.append(uri)
                con.execute(
                    "insert or replace into ItemTable(key, value) "
                    "values('windsurfSpace.resourceToSpace', ?)",
                    (json.dumps(r2s),))
                con.commit()
        finally:
            con.close()
    except (sqlite3.Error, json.JSONDecodeError, OSError) as e:
        return f"space write failed: {e}"
    return ""


def resolve_devin(name: str):
    """devin binary; .cmd/.bat shims need cmd /c on Windows."""
    resolved = shutil.which(name)
    if not resolved:
        return None
    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", resolved]
    return [resolved]


class AcpClient:
    """Minimal newline-delimited JSON-RPC client over the child's stdio."""

    def __init__(self, argv, cwd):
        kwargs = {}
        if os.name == "nt":
            # the supervisor is consoleless, so Windows would allocate a
            # visible console for devin acp — closing that window kills the
            # child mid-turn and orphans the session
            kwargs["creationflags"] = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        env = dict(os.environ)
        # the child's JSON-RPC stream is UTF-8 — text=True alone defaults to
        # cp1252 on Windows and the first smart-quote/0x9d byte crashes the
        # supervisor mid-turn; PYTHONIOENCODING propagates the same fix into
        # python subprocesses the agent itself spawns
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        self.proc = subprocess.Popen(
            argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, encoding="utf-8", errors="replace",
            bufsize=1, env=env, **kwargs)
        self.next_id = 0
        self.notifications = []

    def call(self, method: str, params: dict):
        mid = self.next_id
        self.next_id += 1
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": mid, "method": method,
             "params": params}) + "\n")
        self.proc.stdin.flush()
        return mid

    def wait(self, mid: int):
        """Read until the response for `mid`; buffer notifications."""
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise EOFError("devin acp child exited")
            msg = json.loads(line)
            if msg.get("id") == mid:
                return msg
            self.notifications.append(msg)

    def drain(self):
        try:
            for line in self.proc.stdout:
                try:
                    self.notifications.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass


def main():
    args = parse_args()
    root = Path(args.project_root).resolve()
    orch = Path(args.orchestration_dir).resolve()
    prompt_path = Path(args.prompt_file).resolve()
    record = {"started": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M"),
              "prompt_file": str(prompt_path), "mode": args.mode,
              "tab_id": args.tab_id or None,
              "model": args.model or os.environ.get("DEVIN_MODEL") or None}

    api_key = (os.environ.get(args.api_key_env, "").strip()
               or env_value(args.env_file, args.api_key_env))
    if not api_key:
        emit({**record, "errors": [f"{args.api_key_env} unset in env and "
                                   f"{args.env_file or 'no env-file'} — ACP "
                                   "workers authenticate per-session"]},
             1, args.session_json)
    if not prompt_path.is_file():
        emit({**record, "errors": [f"prompt file not found: {prompt_path}"]},
             1, args.session_json)
    argv = resolve_devin(args.devin_bin)
    if not argv:
        emit({**record, "errors": [f"devin binary not found "
                                   f"({args.devin_bin})"]}, 1, args.session_json)

    log_f = open(args.log, "a", encoding="utf-8")
    log_f.write(f"--- acp-worker started {record['started']} "
                f"mode={args.mode} ---\n")

    prompt_text = prompt_path.read_text(encoding="utf-8")

    def fail(errors, code=2):
        record["errors"] = errors
        record["finished"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M")
        log_f.write(f"--- failed: {'; '.join(errors)} ---\n")
        log_f.close()
        emit(record, code, args.session_json)

    # handshake — initialize → authenticate → session/new. A child that dies
    # during this window is a transient startup race (bursty spawns land
    # in the same second); retry once after a beat, then give up honestly.
    client = session = None
    for attempt in (1, 2):
        try:
            acp_argv = argv + ["acp"] + (["--model", args.model]
                                         if args.model else [])
            client = AcpClient(acp_argv, str(root))
            r = client.wait(client.call("initialize", {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": False}}))
            if "error" in r:
                raise RuntimeError(f"initialize: {r['error']}")
            methods = (r["result"].get("authMethods")
                       or [{"id": "devin-browser"}])
            r = client.wait(client.call("authenticate", {
                "methodId": methods[0]["id"],
                "meta": {"api_key": api_key}}))
            if "error" in r:
                raise RuntimeError(f"authenticate: {r['error']}")
            new_params = {"cwd": str(root), "mcpServers": []}
            if args.tab_id:
                new_params["_meta"] = {
                    "cognition.ai/requestingTabId": args.tab_id}
            r = client.wait(client.call("session/new", new_params))
            if "error" in r:
                raise RuntimeError(f"session/new: {r['error']}")
            session = r["result"]
            break
        except (EOFError, RuntimeError, BrokenPipeError, OSError) as e:
            log_f.write(f"--- handshake attempt {attempt} failed: {e} ---\n")
            log_f.flush()
            if client:
                client.proc.kill()
            if attempt == 2:
                fail([f"handshake: {e}"])
            time.sleep(2)

    record["session_id"] = session["sessionId"]
    record["modes"] = session.get("modes")
    log_f.write(f"session_id: {record['session_id']}\n")

    # join the named IDE space — requestingTabId tags the session but the
    # IDE's own resourceToSpace map is authoritative for placement
    if args.tab_id:
        space_db = args.space_db or str(
            Path(os.environ.get("APPDATA", ""))
            / "Devin" / "User" / "globalStorage" / "state.vscdb")
        space_err = join_space(space_db, args.tab_id, record["session_id"])
        record["space_joined"] = not space_err
        if space_err:
            record["space_error"] = space_err
            log_f.write(f"space join failed: {space_err}\n")

    try:
        # bypass so the unattended worker never stalls on a permission prompt
        avail = [m.get("id") for m in
                 ((session.get("modes") or {}).get("availableModes") or [])]
        current = (session.get("modes") or {}).get("currentModeId")
        if args.mode not in avail:
            record["mode_warning"] = (f"mode {args.mode} not offered — "
                                      f"session stays {current} (avail: "
                                      f"{','.join(avail) or 'none'})")
        elif current != args.mode:
            mr = client.wait(client.call("session/set_mode", {
                "sessionId": record["session_id"], "modeId": args.mode}))
            if "error" in mr:
                record["mode_warning"] = mr["error"]
            else:
                # reflect the applied mode — session/new reported pre-set state
                (record.get("modes") or {}).update(
                    {"currentModeId": args.mode})

        mid = client.call("session/prompt", {
            "sessionId": record["session_id"],
            "prompt": [{"type": "text", "text": prompt_text}]})
        _buf = []

        def _flush():
            if _buf:
                text = " ".join("".join(_buf).split())[:160]
                if text:
                    print(f"[{datetime.now(timezone.utc):%H:%M}] {text}",
                          flush=True)
                _buf.clear()

        def _echo(msg: dict):
            """Compact console line per notification — fully guarded: a
            closed console must never kill the worker. Chunked text
            accumulates into one line; per-token noise (usage etc.) is
            dropped."""
            try:
                u = (msg.get("params") or {}).get("update") or {}
                k = u.get("sessionUpdate")
                if k in ("agent_message_chunk", "agent_thought_chunk"):
                    _buf.append(
                        (u.get("content") or {}).get("text") or "")
                    if sum(map(len, _buf)) >= 120:
                        _flush()
                elif k in ("tool_call", "tool_call_update"):
                    _flush()
                    text = (f"{u.get('status') or ''} "
                            f"{u.get('title') or u.get('toolCallId') or ''}")
                    print(f"[{datetime.now(timezone.utc):%H:%M}] "
                          f"{' '.join(str(text).split())[:160]}",
                          flush=True)
                elif k == "plan":
                    _flush()
                    print(f"[{datetime.now(timezone.utc):%H:%M}] plan:",
                          flush=True)
                    for e in (u.get("entries") or [])[:12]:
                        print(f"  {e.get('status','?')} "
                              f"{(e.get('content') or '')[:120]}",
                              flush=True)
                elif "error" in msg:
                    _flush()
                    print(f"[{datetime.now(timezone.utc):%H:%M}] error "
                          f"{msg['error']}", flush=True)
            except Exception:
                pass

        while True:
            line = client.proc.stdout.readline()
            if not line:
                client.drain()
                raise EOFError("devin acp child exited mid-turn")
            msg = json.loads(line)
            log_f.write(json.dumps(msg) + "\n")
            log_f.flush()
            if args.echo:
                _echo(msg)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"session/prompt: {msg['error']}")
                result = msg["result"]
                record["stop_reason"] = result.get("stopReason")
                record["usage"] = result.get("usage")
                _flush()
                break
    except (EOFError, RuntimeError, BrokenPipeError, OSError) as e:
        client.proc.kill()
        fail([str(e)])

    record["finished"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    log_f.write(f"--- finished stop_reason={record.get('stop_reason')} ---\n")
    log_f.close()
    client.proc.kill()
    emit(record, 0, args.session_json)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
