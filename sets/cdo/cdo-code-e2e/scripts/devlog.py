#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Dev-log bookkeeping for cdo-code-e2e: init, state get/set, journal append.

Replaces LLM frontmatter surgery on docs/orchestration/devlog/<Channel>/<date>/<story>/index.md.
Run `python devlog.py <command> --help` for per-command usage.

Commands:
  init      Create the story devlog folder + index.md from the template
  get       Emit the pipeline state block as JSON
  set       Update one pipeline step's status
  append    Append a journal entry to index.md
  metrics   Journal mining + prior retro Carry Forward digest (step 10)
  snapshot  Store/check a git-status hash (post-dev change baseline)
  coverage  Tally check: code files in the delta vs `**File:**` lines
  sweep     One-call step-9 bundle: state + coverage + audits + vitepress
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def cmd_init(args) -> dict:
    d = Path(args.dir)
    d.mkdir(parents=True, exist_ok=True)
    index = d / "index.md"
    created = []
    if not index.exists():
        tpl = read(SKILL_ROOT / "assets" / "dev-log-template.md")
        tpl = (tpl.replace("{story-key}", args.story_key)
                  .replace("{release}", args.release)
                  # POSIX paths only — backslashes inside the template's
                  # double-quoted YAML scalars are invalid/silent escapes.
                  .replace("{sprint_status_path}", args.sprint_status.replace("\\", "/"))
                  .replace("{story_file_path}", args.story_file.replace("\\", "/")))
        write(index, tpl)
        created.append(str(index))

    # docs/orchestration/devlog landing page
    landing = Path(args.dir).parents[2] / "index.md"
    if not landing.exists():
        write(landing, "# Dev Logs\n\nPer-story pipeline logs, organized by release channel, date, and story.\n\nThese are teaching artifacts, not just audit trails — each change records its context, reasoning, and rejected alternatives so a new engineer can onboard to the work from the journal alone.\n")
        created.append(str(landing))

    # VitePress registration check (report only — config edits stay with the LLM)
    vp = Path(args.dir).parents[4] / ".vitepress" / "config.ts"
    registered = vp.is_file() and "devlog" in read(vp)
    return {"status": "pass", "created": created, "index": str(index),
            "vitepress_registered": registered}


STEPS_BLOCK_RE = re.compile(
    r"(^\s+steps:[ \t]*\n)((?:[ \t]+[\w-]+:[ \t]*[\w-]+[ \t]*\n?)+)", re.M)


def steps_block(text: str) -> tuple[re.Match, re.Match, dict] | None:
    """Return (fm_match, steps_match, parsed-steps) for the frontmatter
    `steps:` sub-block.

    Scoped to the steps block only — journal body lines that happen to look
    like `key: value` must never be parsed or rewritten as pipeline state.
    `steps_match` offsets are relative to `fm_match.group(1)`; add
    `fm_match.start(1)` to splice into the full document.
    """
    fm = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not fm:
        return None
    m = STEPS_BLOCK_RE.search(fm.group(1))
    if not m:
        return None
    steps = dict(re.findall(r"^\s+([\w-]+):\s*([\w-]+)\s*$", m.group(2), re.M))
    return fm, m, steps


def cmd_get(args) -> dict:
    text = read(Path(args.dir) / "index.md")
    parsed = steps_block(text)
    if not parsed:
        return {"status": "fail", "error": "no frontmatter steps block"}
    return {"status": "pass", "steps": parsed[2]}


def cmd_set(args) -> dict:
    index = Path(args.dir) / "index.md"
    text = read(index)
    parsed = steps_block(text)
    if not parsed:
        return {"status": "fail", "error": "no frontmatter steps block"}
    fm, m = parsed[0], parsed[1]
    pattern = rf"^(\s+{re.escape(args.step)}:\s*)([\w-]+)(\s*)$"
    new_block, n = re.subn(pattern, rf"\g<1>{args.status}\g<3>",
                           m.group(2), count=1, flags=re.M)
    if n == 0:
        return {"status": "fail", "error": f"step '{args.step}' not found in pipeline block"}
    base = fm.start(1)
    write(index, text[:base + m.start(2)] + new_block + text[base + m.end(2):])
    return {"status": "pass", "step": args.step, "value": args.status}


def cmd_append(args) -> dict:
    index = Path(args.dir) / "index.md"
    text = read(index)
    body = args.text
    if body is None:
        # Force UTF-8 on stdin — Windows defaults stdin to the console
        # codepage (cp1252), which decodes piped UTF-8 into mojibake
        # (e.g. "—" becomes "â€"") that then gets written to the journal.
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        body = sys.stdin.read()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    # --step stamps '(step N/13)' into the title so `metrics` can attribute
    # durations deterministically instead of free-text title parsing.
    title = f"{args.title} (step {args.step}/13)" if args.step else args.title
    # h4 titles — h2/h3 inside Journal would flood the VitePress On-This-Page
    # outline, which should show `## Journal` alone.
    entry = f"\n#### {stamp} — {title}\n\n{body.rstrip()}\n"
    write(index, text.rstrip() + "\n" + entry)
    return {"status": "pass", "appended": args.title}


# Coverage tally (step 4 coverage check + step 9 sweep): which files count
# as development changes vs docs/bookkeeping. Every code file the change
# touched must be named in at least one decision entry — docs, sprint yaml,
# and devlog artifacts don't count.
CODE_EXTENSIONS = {
    ".ts", ".tsx", ".vue", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".sh", ".sql", ".css", ".scss", ".html",
}
COVERAGE_EXCLUDED_PREFIXES = ("docs/", "_bmad-output/")
COVERAGE_IGNORED_PARTS = {"node_modules", ".git", ".nuxt", ".output", "dist", ".netlify"}


def is_code_change(path: str) -> bool:
    norm = path.replace("\\", "/")
    if norm.startswith(COVERAGE_EXCLUDED_PREFIXES):
        return False
    if any(part in COVERAGE_IGNORED_PARTS for part in Path(norm).parts):
        return False
    return Path(norm).suffix in CODE_EXTENSIONS


sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitpaths import expand_dirs, normalize_changed_paths  # noqa: E402

# `**File:**` group lines — the only places a file counts as "journaled".
# A casual mention elsewhere in the journal must not satisfy coverage.
FILE_GROUP_RE = re.compile(r"^\s*\*\*File:\*\*\s*(.+)$", re.M)
_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./@\[\]-]+\.[A-Za-z0-9]+")


def journal_file_names(text: str) -> set[str]:
    """Basenames of every path named on a `**File:**` group line."""
    names: set[str] = set()
    for m in FILE_GROUP_RE.finditer(text):
        for tok in _PATH_TOKEN_RE.findall(m.group(1)):
            names.add(Path(tok).name)
    return names


def cmd_coverage(args) -> dict:
    """Tally check — every code file in the changed set must be named on a
    `**File:**` group line in the journal. Docs changes are excluded by
    is_code_change. Pass --files with the post-dev change list so files
    committed mid-run can't drop out of the tally."""
    import subprocess
    index = Path(args.dir) / "index.md"
    text = read(index)
    root = Path(args.project_root) if args.project_root \
        else Path(args.dir).resolve().parents[5]

    if args.files is not None:
        changed, unparsed = normalize_changed_paths(args.files)
    else:
        proc = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
        changed, unparsed = normalize_changed_paths(
            proc.stdout.splitlines())
    if unparsed:
        return {"status": "error",
                "error": "un-parsable changed-file lines: "
                         + "; ".join(unparsed)}

    code_files = [f for f in expand_dirs(root, changed,
                                         COVERAGE_IGNORED_PARTS)
                  if is_code_change(f)]
    journaled = journal_file_names(text)
    missing = [f for f in code_files if Path(f).name not in journaled]
    # Test-adequacy signal: source files changed with zero spec files in
    # the delta is a warning the sweep surfaces, not a coverage failure.
    test_files = [f for f in code_files
                  if Path(f).name.endswith((".spec.ts", ".test.ts", ".spec.js"))]
    warnings = []
    if code_files and not test_files:
        warnings.append("no spec files in the change set — verify the story's test coverage is real")
    return {"status": "pass" if not missing else "fail",
            "checked": len(code_files),
            "covered": len(code_files) - len(missing),
            "missing": missing,
            "test_files": len(test_files),
            "warnings": warnings}


def cmd_sweep(args) -> dict:
    """Step-9 sweep bundle — pipeline state, coverage tally, audit reports
    present, index exists, VitePress registration — one call instead of five."""
    d = Path(args.dir)
    index = d / "index.md"
    state = steps_block(read(index)) if index.exists() else None
    audits = sorted(p.name for p in d.glob("audit-*.md"))
    vp = d.parents[4] / ".vitepress" / "config.ts" if len(d.parents) >= 5 else None
    vitepress_registered = bool(vp and vp.is_file() and "devlog" in read(vp))
    return {
        "status": "pass",
        "index_exists": index.exists(),
        "steps": state[2] if state else {},
        "audit_reports": audits,
        "audit_reports_present": len(audits) > 0,
        "vitepress_registered": vitepress_registered,
        "retrospective_exists": (d / "retrospective.md").exists(),
        "lint": {"status": "pass" if not (lv := lint_violations(read(index)) if index.exists() else []) else "fail",
                 "violations": lv},
    }


ENTRY_RE = re.compile(r"^#{3,4} (\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z) — (.+?)(?:\(step (\d+)/\d+\))?\s*$", re.M)


# Journal format contract — verified by `lint`. Entries are `####` so the
# VitePress On-This-Page outline shows `## Journal` alone; every field label
# sits on its own line; every fence carries a language tag; each **File:**
# group carries **Goal:** + **Gap:** and at least one of **Before**/**After**
# followed by a real code fence; no bare `<word>` tokens outside fences or
# inline backticks — VitePress compiles .md as Vue SFC, so an unclosed
# `<Foo>` (TS generics, placeholders, stray tokens) breaks docs:build with
# "Element is missing end tag". Carried-forward lesson 14-01→14-05.
FILE_FIELD_LABEL_RE = re.compile(
    r"\*\*(?:File|Goal|Gap|Context|Why this approach|Alternatives considered"
    r"|Watch out for):\*\*|\*\*(?:Before|After)\*\*")
GROUP_LABEL_RES = {
    "Goal": re.compile(r"^\s*\*\*Goal:\*\*", re.M),
    "Gap": re.compile(r"^\s*\*\*Gap:\*\*", re.M),
    "Before": re.compile(r"^\s*\*\*Before\*\*", re.M),
    "After": re.compile(r"^\s*\*\*After\*\*", re.M),
}
INLINE_CODE_RE = re.compile(r"`[^`]*`")
VPRE_SPAN_RE = re.compile(r"<(?:code|span) v-pre>.*?</(?:code|span)>")
BARE_TAG_RE = re.compile(r"<([A-Za-z_][A-Za-z0-9_.-]*)")


def lint_violations(text: str) -> list[dict]:
    m = re.search(r"^##\s+Journal\b.*$", text, re.M | re.S)
    body = m.group(0) if m else text
    base = text[: m.start()].count("\n") + 1 if m else 1
    lines = body.splitlines()
    violations = []

    in_fence = False
    for i, ln in enumerate(lines):
        if i == 0 and m:
            continue  # lines[0] is the `## Journal` section header itself
        s = ln.strip()
        if s.startswith("```"):
            if not in_fence and s == "```":
                violations.append({"line": base + i, "rule": "fence-lang",
                                   "detail": "opening fence has no language tag"})
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,3}\s", s):
            violations.append({"line": base + i, "rule": "heading-depth",
                               "detail": "h1–h3 inside Journal — entries use #### so On-This-Page shows only Journal"})
        # Bare `<word` outside fences/inline code is a VitePress landmine:
        # it compiles as an unclosed Vue element. A tag is excused only
        # when its own `</tag>` appears on the same line (paired markup
        # like `<code v-pre>…</code>` is intentional).
        no_code = INLINE_CODE_RE.sub("", ln)
        for tm in BARE_TAG_RE.finditer(no_code):
            tag = tm.group(1)
            if f"</{tag}>" not in no_code:
                violations.append({"line": base + i, "rule": "bare-tag",
                                   "detail": f"bare `<{tag}` outside fences/backticks — compiles as unclosed element in docs:build; wrap it in backticks"})
                break
        # Bare `{{` is a VitePress landmine even inside inline code — braces
        # aren't entity-escaped, so `<code>{{ x }}</code>` still compiles the
        # mustache and `x` throws at SSR. Only fences or <code v-pre>/<span
        # v-pre> protect it. (Story 13.11: audit pages broke docs:build SSR.)
        no_vpre = VPRE_SPAN_RE.sub("", ln)
        if "{{" in no_vpre:
            violations.append({"line": base + i, "rule": "bare-mustache",
                               "detail": "bare `{{` outside fences/v-pre — compiles as a Vue interpolation and can throw during docs:build SSR; wrap it in `<code v-pre>`"})
        if len(FILE_FIELD_LABEL_RE.findall(s)) > 1:
            violations.append({"line": base + i, "rule": "fields-own-line",
                               "detail": "multiple field labels on one line"})

    starts = [g.start() for g in FILE_GROUP_RE.finditer(body)]
    bounds = [b.start() for b in re.finditer(r"^####\s", body, re.M)]
    for st in starts:
        en = min([b for b in bounds + [s for s in starts if s > st] if b > st],
                 default=len(body))
        seg = body[st:en]
        ln_no = base + body[:st].count("\n")
        for name in ("Goal", "Gap"):
            if not GROUP_LABEL_RES[name].search(seg):
                violations.append({"line": ln_no, "rule": "file-group-fields",
                                   "detail": f"File group missing **{name}:**"})
        if not (GROUP_LABEL_RES["Before"].search(seg)
                or GROUP_LABEL_RES["After"].search(seg)):
            violations.append({"line": ln_no, "rule": "file-group-fields",
                               "detail": "File group has no **Before** or **After** block"})

    for bm in re.finditer(r"^\s*\*\*(Before|After)\*\*\s*$", body, re.M):
        tail = body[bm.end():bm.end() + 300]
        if not re.search(r"^```\S", tail, re.M):
            ln_no = base + body[:bm.start()].count("\n")
            violations.append({"line": ln_no, "rule": "before-after-fence",
                               "detail": f"**{bm.group(1)}** not followed by a language-tagged fence"})

    return violations


def cmd_lint(args) -> dict:
    """Format check on the journal — deterministic mechanics (heading depth,
    fence language tags, fields on own lines, File-group completeness, bare
    `<word>` tokens that break VitePress' Vue-SFC compile)."""
    text = read(Path(args.dir) / "index.md")
    violations = lint_violations(text)
    return {"status": "pass" if not violations else "fail",
            "violations": violations}


def cmd_metrics(args) -> dict:
    """Journal mining + prior-retro Carry Forward digest for the retro step."""
    d = Path(args.dir)
    text = read(d / "index.md")
    entries = ENTRY_RE.findall(text)
    step_entries = {}  # step number -> [timestamps]
    for stamp, _title, stepno in entries:
        if stepno:
            step_entries.setdefault(int(stepno), []).append(stamp)

    fmt = "%Y-%m-%d %H:%MZ"
    durations = {}
    for step, stamps in sorted(step_entries.items()):
        ts = [datetime.strptime(s, fmt) for s in stamps]
        durations[step] = {
            "entries": len(stamps),
            "first": stamps[0], "last": stamps[-1],
            "span_min": round((ts[-1] - ts[0]).total_seconds() / 60, 1),
        }

    fix_iters = len(re.findall(r"attempt|fix loop|iteration", text, re.I))
    gates = re.findall(r"gate|confirmed|waived|deferred", text, re.I)

    # Prior retros' Carry Forward / Action items (bounded: 3 most recent)
    carry = []
    devlog_root = d.parents[2] if len(d.parents) >= 3 else d
    retros = sorted(devlog_root.glob("*/*/*/retrospective.md"),
                    key=lambda p: p.stat().st_mtime, reverse=True)[:3]
    for r in retros:
        if r.resolve() == (d / "retrospective.md").resolve():
            continue
        rt = read(r)
        m = re.search(r"^##\s+Carry Forward.*?\n(.*?)(?=^##\s|\Z)", rt, re.M | re.S)
        if not m:
            m = re.search(r"^##\s+Action items.*?\n(.*?)(?=^##\s|\Z)", rt, re.M | re.S | re.I)
        if m:
            carry.append({"retro": str(r), "carry_forward": m.group(1).strip()})

    return {"status": "pass", "script": "devlog-metrics",
            "entries": len(entries), "steps": durations,
            "fix_loop_signals": fix_iters, "gate_signals": len(gates),
            "prior_carry_forward": carry}


def cmd_snapshot(args) -> dict:
    """Store/compare a hash of `git status --porcelain` in pipeline frontmatter —
    the post-dev change baseline that ship's story-scope routing compares against."""
    import hashlib
    import subprocess
    index = Path(args.dir) / "index.md"
    root = Path(args.project_root) if args.project_root else Path(args.dir).resolve().parents[3]
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=30)
    digest = hashlib.sha256(proc.stdout.encode()).hexdigest()[:16]

    if args.check:
        text = read(index)
        m = re.search(r"^\s+change_snapshot:\s*\"?([0-9a-f]+)\"?\s*$", text, re.M)
        stored = m.group(1) if m else None
        return {"status": "pass", "stored": stored, "current": digest,
                "changed": stored is not None and stored != digest}

    text = read(index)
    fm = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not fm:
        return {"status": "fail", "error": "no frontmatter"}
    if re.search(r"^\s+change_snapshot:", fm.group(1), re.M):
        new = re.sub(r"^(\s+change_snapshot:)\s*.*$",
                     rf'\g<1> "{digest}"', text, flags=re.M)
    else:
        # insert right after the steps block inside `pipeline:`
        parsed = steps_block(text)
        if not parsed:
            return {"status": "fail", "error": "no frontmatter steps block"}
        fmm, m = parsed[0], parsed[1]
        pos = fmm.start(1) + m.end(2)
        # fm.group(1) excludes the \n before the closing --- — lead with \n.
        # m.end(2) also consumes the last step line's \n, so when the next
        # key starts immediately (`dispatch:` or `  story_key:`) a missing
        # trailing \n glues the digest onto it — invalid YAML that kills
        # the VitePress frontmatter parse.
        new = text[:pos] + f'\n  change_snapshot: "{digest}"\n' + text[pos:]
    write(index, new)
    return {"status": "pass", "change_snapshot": digest}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Create devlog folder + index.md from template")
    p.add_argument("dir")
    p.add_argument("--story-key", required=True)
    p.add_argument("--release", required=True)
    p.add_argument("--sprint-status", required=True)
    p.add_argument("--story-file", required=True)
    p.set_defaults(fn=cmd_init)

    for name, fn, helptext in (
        ("get", cmd_get, "Emit pipeline state as JSON"),
        ("set", cmd_set, "Update a pipeline step status"),
        ("append", cmd_append, "Append a journal entry"),
        ("metrics", cmd_metrics, "Journal mining + prior retro Carry Forward digest"),
        ("snapshot", cmd_snapshot, "Store/check a git-status hash for the post-dev change baseline"),
        ("coverage", cmd_coverage, "Tally check: every code file in the change set must be named in a decision entry"),
        ("lint", cmd_lint, "Format check: heading depth, fence language tags, fields on own lines, File-group completeness"),
        ("sweep", cmd_sweep, "Step-9 bundle: pipeline state + audit reports + VitePress registration"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("dir")
        if name == "set":
            p.add_argument("step")
            p.add_argument("status", choices=["pending", "in-progress", "done", "skipped", "blocked"])
        if name == "append":
            p.add_argument("--title", required=True)
            p.add_argument("--text", help="Entry body; reads stdin if omitted")
            p.add_argument("--step", type=int, default=None,
                           help="Pipeline step number (1-13) — stamps '(step N/13)' so metrics attributes durations")
        if name == "snapshot":
            p.add_argument("--check", action="store_true",
                           help="Compare current git state to the stored snapshot")
            p.add_argument("--project-root", type=Path, default=None)
        if name == "coverage":
            p.add_argument("--files", nargs="*", default=None,
                           help="Changed files to check (dirs expanded; default: git status --porcelain)")
            p.add_argument("--project-root", type=Path, default=None)
        p.set_defaults(fn=fn)

    args = ap.parse_args()
    result = args.fn(args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
