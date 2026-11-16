#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Shared `git status --porcelain` path parsing + directory expansion for
cdo-code-e2e scripts.

Both health-check.py (--changed-files) and devlog.py coverage accept
porcelain output verbatim. A raw line like ` M server/areas.ts` or a
rename `R  old -> new` must normalize to `server/areas.ts` / `new` —
otherwise the file never resolves on disk and prefix checks
(`server/**` build-critical detection) silently misfire.
"""
import re
from pathlib import Path

# Porcelain status columns: 2 chars where space means "unmodified" —
# " M file" is a valid line whose leading space MUST NOT be stripped
# before the position check.
_STATUS_RE = re.compile(r"^[A-Z?! ]{2}$")
# A line that STILL starts with a two-letter status code after parsing is
# un-normalizable input — the caller should surface it, not silently drop.
_RESIDUAL_STATUS_RE = re.compile(r"^[A-Z?!]{1,2}\s+\S")


def parse_porcelain_line(line: str) -> str | None:
    """Normalize one porcelain/status line (or plain path) to a repo-relative
    path. Returns None for blank input."""
    s = line.rstrip()
    if not s.strip():
        return None
    # XY status prefix is exactly 2 chars + space (" M ", "?? ", "R  ")
    if len(s) > 3 and s[2] == " " and _STATUS_RE.match(s[:2]):
        s = s[3:].strip()
    if " -> " in s:  # rename: keep the destination path
        s = s.split(" -> ")[-1].strip()
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s or None


def normalize_changed_paths(lines: list[str]) -> tuple[list[str], list[str]]:
    """(paths, unparsed) — unparsed lines still contain a status prefix
    after normalization; callers must not silently drop them."""
    paths: list[str] = []
    unparsed: list[str] = []
    for line in lines:
        p = parse_porcelain_line(line)
        if p is None:
            continue
        if _RESIDUAL_STATUS_RE.match(p):
            unparsed.append(line)
        else:
            paths.append(p.replace("\\", "/"))
    return paths, unparsed


def expand_dirs(root: Path, paths: list[str],
                ignored_parts: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Directory args expand to the files they contain; paths under
    ignored_parts are dropped."""
    out: list[str] = []
    for f in paths:
        norm = f.replace("\\", "/")
        if any(part in ignored_parts for part in Path(norm).parts):
            continue
        p = root / norm
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and not any(
                    part in ignored_parts
                    for part in child.relative_to(root).parts
                ):
                    out.append(child.relative_to(root).as_posix())
        else:
            out.append(norm)
    return out
