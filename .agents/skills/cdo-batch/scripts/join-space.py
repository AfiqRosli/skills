#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""join-space.py — assign spawned sessions to a Devin Desktop space.

A space's contents render from two IDE-owned keys in
%APPDATA%/Devin/User/globalStorage/state.vscdb:

  windsurfSpace.resourceToSpace  {space_id: ["vscode-cascade-editor:///…/sid"]}
  windsurfSpace.editorStates     {space_id: {serializedGrid: …editor leaves…}}

Membership needs BOTH — the map is the space's contents list, the grid is
what the UI actually opens. The IDE holds this state in memory and flushes
over external writes, so run this while the IDE is closed (or right before
a restart): the values load at startup and then survive.

Space is identified by id (1792177402184-amgdw1n4p style) or title
("CDO Workers"). Sessions by explicit --session-id, or scanned from the
orchestration dir's *.acp.json records (every ACP-spawned session leaves
one). `w-*`/`r-*`/`a-*` records all carry `session_id`.

Usage:
  uv run join-space.py --list-spaces
  uv run join-space.py --space "CDO Workers"
      --orchestration-dir docs/orchestration
  uv run join-space.py --space 1792177402184-amgdw1n4p
      --session-id tasteful-eggnog --session-id trusted-dream

Exit codes: 0 ok, 1 refused
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("APPDATA", "")) / "Devin" / "User" \
    / "globalStorage" / "state.vscdb"
DEFAULT_SESSIONS_DB = Path(os.environ.get("APPDATA", "")) / "devin" \
    / "cli" / "sessions.db"


def emit(result: dict, code: int, out: str):
    blob = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


def load_space_state(db_path: Path):
    con = sqlite3.connect(str(db_path), timeout=5)
    try:
        out = {}
        for key in ("windsurfSpace.metadata", "windsurfSpace.resourceToSpace",
                    "windsurfSpace.editorStates"):
            row = con.execute(
                "select value from ItemTable where key=?", (key,)).fetchone()
            out[key] = json.loads(row[0]) if row and row[0] else {}
    finally:
        con.close()
    return (out["windsurfSpace.metadata"], out["windsurfSpace.resourceToSpace"],
            out["windsurfSpace.editorStates"])


def session_title(sessions_db: Path, session_id: str):
    try:
        con = sqlite3.connect(f"file:{sessions_db}?mode=ro", uri=True)
        row = con.execute(
            "select title from sessions where id=?", (session_id,)).fetchone()
        con.close()
        return (row[0] or session_id) if row else session_id
    except sqlite3.Error:
        return session_id


def add_to_grid(states: dict, space_id: str, uri: str, title: str) -> bool:
    """Append an editor leaf for the session into the space's grid —
    mirrors the structure the IDE writes on drag-in. Returns True when the
    editor was newly added (already-present resource → False)."""
    editor = {"id": "workbench.input.cascadeEditor",
              "value": json.dumps({"resource": uri, "options": {},
                                   "title": title})}
    st = states.setdefault(space_id, {})
    grid = st.setdefault("serializedGrid", {
        "root": {"type": "branch", "data": [], "size": 992},
        "orientation": 1, "width": 1320, "height": 992})
    leaves = grid["root"]["data"]
    for leaf in leaves:
        for ed in leaf.get("data", {}).get("editors", []):
            try:
                if json.loads(ed.get("value", "{}")).get("resource") == uri:
                    return False
            except json.JSONDecodeError:
                continue
    leaf = leaves[0] if leaves else None
    if leaf is None:
        leaf = {"type": "leaf", "data": {"id": 0, "editors": [], "mru": []},
                "size": 660}
        leaves.append(leaf)
    data = leaf["data"]
    data.setdefault("editors", []).append(editor)
    data["mru"] = list(range(len(data["editors"]) - 1, -1, -1))
    st.setdefault("activeGroup", 0)
    st.setdefault("mostRecentActiveGroups", [0])
    return True


def resolve_space(spaces: dict, want: str):
    if want in spaces:
        return want
    match = [sid for sid, m in spaces.items() if m.get("title") == want]
    return match[0] if match else None


def main():
    p = argparse.ArgumentParser(description="Assign spawned sessions to a "
                                            "Devin Desktop space.")
    p.add_argument("--orchestration-dir", default="")
    p.add_argument("--space", default="")
    p.add_argument("--session-id", action="append", default=[])
    p.add_argument("--list-spaces", action="store_true")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--sessions-db", default=str(DEFAULT_SESSIONS_DB),
                   help="devin sessions.db for editor titles")
    p.add_argument("--output", default="")
    args = p.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        emit({"errors": [f"space db not found: {db_path}"]}, 1, args.output)
    spaces, mapping, states = load_space_state(db_path)

    if args.list_spaces:
        emit({"spaces": [{"id": sid, "title": m.get("title"),
                          "is_explicit": m.get("isExplicit", False),
                          "sessions": len(mapping.get(sid, []))}
                         for sid, m in spaces.items()]}, 0, args.output)

    if not args.space:
        emit({"errors": ["--space required (id or title); --list-spaces to "
                         "discover ids"]}, 1, args.output)
    space_id = resolve_space(spaces, args.space)
    if not space_id:
        emit({"errors": [f"space not found: {args.space} — create it in the "
                         "IDE first (drag two sessions together)"]},
             1, args.output)

    session_ids = set(args.session_id)
    orch = Path(args.orchestration_dir).resolve() if args.orchestration_dir else None
    if orch:
        for f in sorted(orch.glob("sessions/*.acp.json")):
            try:
                sid = json.loads(f.read_text(
                    encoding="utf-8")).get("session_id")
            except (json.JSONDecodeError, OSError):
                continue
            if sid:
                session_ids.add(sid)
    if not session_ids:
        emit({"errors": ["no sessions — pass --session-id or "
                         "--orchestration-dir with *.acp.json records"]},
             1, args.output)

    members = mapping.setdefault(space_id, [])
    sessions_db = Path(args.sessions_db)
    added = []
    for sid in sorted(session_ids):
        uri = f"vscode-cascade-editor:///cascade-acp/devin-cli/{sid}"
        if uri not in members:
            members.append(uri)
        # editorStates is what the UI actually renders — mirror the IDE's
        # own leaf structure, title read from the session store
        if add_to_grid(states, space_id, uri,
                       session_title(sessions_db, sid)):
            added.append(sid)

    con = sqlite3.connect(str(db_path), timeout=5)
    try:
        for key, value in (("windsurfSpace.resourceToSpace", mapping),
                           ("windsurfSpace.editorStates", states)):
            con.execute(
                "insert or replace into ItemTable(key, value) values(?, ?)",
                (key, json.dumps(value)))
        con.commit()
    finally:
        con.close()

    emit({"status": "ok",
          "space_id": space_id,
          "space_title": spaces[space_id].get("title"),
          "added": added,
          "already_member": sorted(session_ids - set(added)),
          "warning": "durable only while the IDE is closed — it flushes "
                     "this map from memory over external writes"},
         0, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(1)
