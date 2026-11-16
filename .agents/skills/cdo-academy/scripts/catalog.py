#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""catalog.py — the academy's curriculum map and gap recorder.

The curriculum is structured as tracks -> courses -> modules:

  docs/academy/catalog.yaml
    tracks:
      frontend-engineering:
        title: Frontend Engineering
        summary: ...
        courses:
          typescript:
            title: TypeScript
            summary: ...
            modules:
              basic-types:
                title: Basic Types & Annotations
                level: fundamentals        # fundamentals|intermediate|advanced
                source_stories: [S3]

Actions:

  list      → emit the catalog as JSON
              --academy-dir /path/docs/academy
  add       → register a published module into the catalog:
              --track T --course C --module-id M --title T --level L
              [--track-title TT] [--course-title CT] [--source-story S]
  file-gap  → record a confirmed coverage gap into backlogs/curriculum.md
              (the LLM coverage pass decided this is a gap; this action is
              the deterministic recorder — dedup + C{n} key allocation):
              --concept-id X --title T --kind K --track T --course C
              --level L --sources s1,s2
              --orchestration-dir /path/docs/orchestration

Usage:
  uv run catalog.py --academy-dir /path/docs/academy list
  uv run catalog.py --academy-dir /path/docs/academy add --track fe ...
  uv run catalog.py --orchestration-dir /path/docs/orchestration file-gap ...

Exit codes: 0=ok, 1=usage/conflict error, 2=runtime error
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

LEVELS = ("fundamentals", "intermediate", "advanced")


def parse_args():
    p = argparse.ArgumentParser(description="Academy catalog + gap recorder.")
    p.add_argument("--academy-dir", default="",
                   help="docs/academy root — required by list/add")
    p.add_argument("--orchestration-dir", default="",
                   help="docs/orchestration root — required by file-gap")
    p.add_argument("action", choices=["list", "add", "file-gap"])
    p.add_argument("--track", default="")
    p.add_argument("--track-title", default="")
    p.add_argument("--course", default="")
    p.add_argument("--course-title", default="")
    p.add_argument("--module-id", default="")
    p.add_argument("--concept-id", default="")
    p.add_argument("--title", default="")
    p.add_argument("--level", default="")
    p.add_argument("--kind", default="concept")
    p.add_argument("--sources", default="")
    p.add_argument("--source-story", default="")
    p.add_argument("--concepts", default="",
                   help="comma-separated concept ids this module teaches")
    p.add_argument("-o", "--output")
    return p.parse_args()


def emit(result: dict, code: int, out: str):
    blob = json.dumps(result, indent=2)
    if out:
        Path(out).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    sys.exit(code)


def load_catalog(academy: Path) -> dict:
    f = academy / "catalog.yaml"
    if f.is_file():
        try:
            return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return {}
    return {}


def save_catalog(academy: Path, catalog: dict):
    academy.mkdir(parents=True, exist_ok=True)
    (academy / "catalog.yaml").write_text(
        yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8"
    )


def cmd_add(academy: Path, args) -> dict:
    for flag in ("track", "course", "module_id", "title"):
        if not getattr(args, flag):
            return {"errors": [f"--{flag.replace('_', '-')} required"]}, 1
    level = args.level or "fundamentals"
    if level not in LEVELS:
        return {"errors": [f"--level must be one of {LEVELS}"]}, 1

    catalog = load_catalog(academy)
    tracks = catalog.setdefault("tracks", {})
    track = tracks.setdefault(args.track, {
        "title": args.track_title or args.track, "courses": {},
    })
    if args.track_title:
        track["title"] = args.track_title
    courses = track.setdefault("courses", {})
    course = courses.setdefault(args.course, {
        "title": args.course_title or args.course, "modules": {},
    })
    if args.course_title:
        course["title"] = args.course_title
    modules = course.setdefault("modules", {})
    mod = modules.setdefault(args.module_id, {"title": args.title,
                                              "level": level,
                                              "source_stories": []})
    mod["title"] = args.title
    mod["level"] = level
    stories = mod.setdefault("source_stories", [])
    if args.source_story and args.source_story not in stories:
        stories.append(args.source_story)
    if args.concepts:
        concepts = mod.setdefault("concepts", [])
        for cid in (c.strip() for c in args.concepts.split(",")):
            if cid and cid not in concepts:
                concepts.append(cid)
    save_catalog(academy, catalog)
    return {"status": "added", "track": args.track, "course": args.course,
            "module_id": args.module_id}, 0


KEY_RE = re.compile(r"^- \[.\] (C\d+)\b", re.M)


def _acquire_lock(bfile: Path, stale_seconds: float = 120.0) -> Path:
    """Sentinel lockfile — O_EXCL create is atomic on both POSIX and Windows.
    Parallel a-{key} sessions file-gap concurrently; without this the
    read-compute-write of curriculum.md races on C{n} allocation."""
    lock = bfile.with_name(bfile.name + ".lock")
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lock
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue
            if age > stale_seconds:
                try:
                    lock.unlink()   # stale holder — break and retry
                except OSError:
                    pass
            else:
                time.sleep(0.05)


def cmd_file_gap(orch: Path, args) -> dict:
    for flag in ("concept_id", "title", "track", "course"):
        if not getattr(args, flag):
            return {"errors": [f"--{flag.replace('_', '-')} required"]}, 1
    level = args.level or "fundamentals"
    if level not in LEVELS:
        return {"errors": [f"--level must be one of {LEVELS}"]}, 1

    bfile = orch / "backlogs" / "curriculum.md"
    bfile.parent.mkdir(parents=True, exist_ok=True)
    lock = _acquire_lock(bfile)
    try:
        return _cmd_file_gap_locked(bfile, args, level)
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _cmd_file_gap_locked(bfile: Path, args, level: str) -> dict:
    if not bfile.is_file():
        bfile.write_text("# Curriculum Backlog\n\n## Items\n\n",
                         encoding="utf-8")
    existing = bfile.read_text(encoding="utf-8")
    # token-boundary match — a backlog carrying 'graphql-api' must not
    # swallow a new 'api' concept
    pat = re.compile(rf"concept-id:\s*{re.escape(args.concept_id)}\b")
    lines = existing.splitlines(keepends=True)
    for i, l in enumerate(lines):
        if not pat.search(l):
            continue
        # already filed — merge any new source keys so provenance stays true
        new_srcs = [s.strip() for s in args.sources.split(",") if s.strip()]
        sm = re.search(r"sources:\s*([^|\n]+)", l)
        cur = set(s.strip() for s in sm.group(1).split(",")) if sm else set()
        added = [s for s in new_srcs if s not in cur]
        if added:
            merged = ",".join(sorted(cur | set(added)))
            if sm:
                lines[i] = l[:sm.start()] + f"sources: {merged}" + l[sm.end():]
            else:
                lines[i] = l.rstrip("\n") + f" | sources: {merged}\n"
            bfile.write_text("".join(lines), encoding="utf-8")
        return {"status": "already-filed", "concept_id": args.concept_id,
                "sources_added": added}, 0
    n = 0
    for m in KEY_RE.finditer(existing):
        n = max(n, int(m.group(1)[1:]))
    key = f"C{n + 1}"
    sources = args.sources or ""
    line = (f"- [ ] {key} — teach: {args.title} | kind: {args.kind} "
            f"| track: {args.track} | course: {args.course} "
            f"| level: {level} | concept-id: {args.concept_id}"
            + (f" | sources: {sources}" if sources else ""))
    text = existing if existing.endswith("\n") else existing + "\n"
    bfile.write_text(text + line + "\n", encoding="utf-8")
    return {"status": "filed", "key": key, "concept_id": args.concept_id}, 0


def main():
    args = parse_args()

    if args.action == "file-gap":
        if not args.orchestration_dir:
            emit({"errors": ["--orchestration-dir required for file-gap"]},
                 1, args.output)
        orch = Path(args.orchestration_dir).resolve()
        result, code = cmd_file_gap(orch, args)
        emit(result, code, args.output)

    if not args.academy_dir:
        emit({"errors": [f"--academy-dir required for {args.action}"]},
             1, args.output)
    academy = Path(args.academy_dir).resolve()

    if args.action == "list":
        emit({"status": "ok", "catalog": load_catalog(academy)},
             0, args.output)
    if args.action == "add":
        result, code = cmd_add(academy, args)
        emit(result, code, args.output)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
