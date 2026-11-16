#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""partition-renumber.py — the sprint-upgrade transform.

Consumes the confirmed plan from resolve-upgrade.py (new_version, epic_order,
and any `reclassify` overrides the caller filled in) and performs the whole
mechanical migration:

  1. New epics file:   migrating epics in plan epic_order (Bugs & Enhancement
     forced last — sprint tooling assumes the fixed catch-all position),
     `was Epic N in {old}` injected into each heading's LAST paren group;
     story sections verbatim under renumbered `### Story P.Q` headings with
     `(was N.M in {old})` first in the was-chain.
  2. New sprint yaml:  header comments + renumbered epic markers + non-
     terminal story lines as `{new-key}: {status}  # was N.M in {old}, ...`;
     terminal stories dropped; all-terminal epics dropped.
  3. Spec files:       copy to the new folder under the new key, rewrite the
     `# Story` header + `epics-beta-{old}.md#Story` refs, verify, THEN delete
     the original. Never delete-then-recreate.
  4. Archives:         old epics + old sprint yaml rewritten via `.new`
     sibling files — verified, then renamed over the original (a mid-write
     failure never truncates the only copy of terminal-story content).

Usage:
  uv run partition-renumber.py --plan plan.json|--plan - \
      [--reclassify '{"key": "status"}'] --dry-run|--apply

Exit codes: 0=ok (or dry-run), 1=validation/verification failure, 2=runtime.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)

TERMINAL = {"done", "obsolete"}
EPIC_RE = re.compile(r"^## Epic (\d+)[:\s]", re.M)
STORY_RE = re.compile(r"^### Story (\d+)\.(\d+):")
SEP_RE = re.compile(r"^---\s*$")
BUGS_EPIC_RE = re.compile(r"bugs?.*enhance|enhance.*bugs?", re.I)


# ---------------------------------------------------------------- helpers

def inject_last_paren(line: str, note: str) -> str:
    """Insert `note` first in the LAST (...) group when it already opens a
    was/NEW chain; else append ` (note)`. Titles carry their own parens —
    the last group is the annotation slot."""
    opens = [m.start() for m in re.finditer(r"\(", line)]
    last = None
    for o in opens:
        c = line.find(")", o)
        if c != -1:
            last = (o, c)
    if last:
        inner = line[last[0] + 1:last[1]]
        if re.match(r"\s*(was |NEW )", inner):
            return line[:last[0] + 1] + f"{note}, {inner}" + line[last[1]:]
    return line.rstrip() + f" ({note})"


def parse_epics(text: str):
    """Split into head (frontmatter+title+preamble before first ## Epic) and
    epic chunks. Each epic: heading line, preamble lines (up to first story),
    story sections [(epic_n, story_n, heading_line, body_lines)], tail lines
    after the last story (e.g. trailing --- separators are dropped)."""
    head_end = EPIC_RE.search(text)
    head = text[:head_end.start()].splitlines() if head_end \
        else text.splitlines()
    epics = []
    marks = list(EPIC_RE.finditer(text))
    for i, m in enumerate(marks):
        chunk = text[m.start():marks[i + 1].start() if i + 1 < len(marks)
                     else len(text)]
        lines = chunk.splitlines()
        heading, rest = lines[0], lines[1:]
        stories = []
        preamble = []
        cur = None
        for line in rest:
            sm = STORY_RE.match(line)
            if sm:
                if cur:
                    stories.append(cur)
                cur = {"epic": int(sm.group(1)), "story": int(sm.group(2)),
                       "heading": line, "lines": []}
            elif cur is None:
                preamble.append(line)
            elif SEP_RE.match(line):
                stories.append(cur)
                cur = None
            else:
                cur["lines"].append(line)
        if cur:
            stories.append(cur)
        # strip a trailing separator/blank run from the preamble when the
        # epic has no stories (it would otherwise print inside the archive)
        while preamble and (SEP_RE.match(preamble[-1])
                            or preamble[-1].strip() == ""):
            preamble.pop()
        epics.append({"num": int(m.group(1)), "heading": heading,
                      "preamble": preamble, "stories": stories})
    return head, epics


def parse_sprint(text: str):
    """development_status -> {header_lines, epic_groups, post_lines}.
    A run of comments/blank lines is attributed to the NEXT epic marker;
    `epic-N-retrospective:` attaches to epic N."""
    lines = text.splitlines()
    dev_i = next((i for i, l in enumerate(lines)
                  if re.match(r"^development_status:", l)), None)
    if dev_i is None:
        return lines, [], {}, []
    end = next((i for i in range(dev_i + 1, len(lines))
                if re.match(r"^\S", lines[i])), len(lines))
    dev = lines[dev_i + 1:end]
    groups, order, pending, cur = {}, [], [], None
    for line in dev:
        em = re.match(r"^  epic-(\d+)(-retrospective)?:", line)
        sm = re.match(r"^  (\d+)-(\d+)-([a-z0-9-]+):\s*(\S+)\s*(#.*)?$", line)
        if em and not em.group(2):
            n = int(em.group(1))
            cur = {"num": n, "marker": line, "comments": pending,
                   "stories": [], "retro": [], "other": []}
            groups[n] = cur
            order.append(n)
            pending = []
        elif em:
            n = int(em.group(1))
            groups.setdefault(n, {"num": n, "marker": None, "comments": [],
                                  "stories": [], "retro": [], "other": []})
            groups[n]["retro"].append(line)
            if n not in order:
                order.append(n)
        elif sm:
            if cur is None:
                cur = {"num": int(sm.group(1)), "marker": None,
                       "comments": [], "stories": [], "retro": [],
                       "other": []}
                groups[cur["num"]] = cur
                order.append(cur["num"])
            cur["stories"].append(
                {"line": line, "key": f"{sm.group(1)}-{sm.group(2)}-{sm.group(3)}",
                 "epic": int(sm.group(1)), "story": int(sm.group(2)),
                 "status": sm.group(4), "comment": sm.group(5) or ""})
        elif line.strip() == "" or line.lstrip().startswith("#"):
            pending.append(line)
        elif cur is not None:
            cur["other"].append(line)
        else:
            pending.append(line)
    epics = [groups[n] for n in order]
    post = lines[end:]
    return lines[:dev_i + 1], epics, pending, post


# ---------------------------------------------------------------- transform

def build_new_epics(head, epics, plan, omap, old_v, new_v, date):
    """Emit the new epics file lines."""
    out, seen_fm = [], False
    old_core = old_v.split("-", 1)[-1]
    new_core = new_v.split("-", 1)[-1]
    for line in head:
        if re.match(r"^beta:", line):
            out.append(f"beta: {new_v}")
            seen_fm = True
        elif re.match(r"^(source|predecessor|superseded):", line):
            continue
        elif re.match(r"^# ", line) and old_core in line:
            out.append(line.replace(old_core, new_core))
        else:
            out.append(line)
    if seen_fm:
        # splice source/predecessor right after the beta line
        i = next(i for i, l in enumerate(out) if l == f"beta: {new_v}")
        out[i + 1:i + 1] = [f"source: epics-beta-{old_v}.md",
                            f"predecessor: {old_v}"]
    out += [
        "",
        f"> Sprint boundary {date}: migrated from `epics-beta-{old_v}.md` — "
        f"epics renumbered into confirmed priority order, stories renumbered "
        f"1..n within each epic (compacted). Traceability: `(was X.Y in "
        f"{old_v})` on every migrated heading; terminal stories stayed "
        f"behind in the archived source file.",
    ]
    for pos, e in enumerate(epics, start=1):
        oe = e["num"]
        ne = omap[oe]
        out.append("")
        heading = re.sub(r"^## Epic \d+", f"## Epic {ne}", e["heading"])
        out.append(inject_last_paren(heading, f"was Epic {oe} in {old_v}"))
        out += e["preamble"]
        if e["preamble"] and e["stories"]:
            out.append("")
        for ns, s in enumerate(e["stories"], start=1):
            new_num = f"{ne}.{ns}"
            heading = re.sub(r"^### Story \d+\.\d+:",
                             f"### Story {new_num}:", s["heading"])
            out.append(inject_last_paren(
                heading, f"was {s['epic']}.{s['story']} in {old_v}"))
            out += s["lines"]
        if pos < len(epics):
            out += ["", "---"]
    return "\n".join(out) + "\n"


def build_new_sprint(pre, epics, pending, post, plan, omap, smap, old_v,
                     new_v, date, spec_rel, status_map=None):
    """Emit the new sprint-status yaml lines."""
    out = [f"# sprint-status-{new_v}.yaml — generated {date}",
           f"# migrated from sprint-status-{old_v}.yaml "
           f"(sprint boundary upgrade)",
           f"# stories renumbered; `# was N.M in {old_v}` = origin in the "
           f"archived release"]
    for line in pre:
        if re.match(r"^story_location:", line):
            out.append(f"story_location: {spec_rel}")
        elif re.match(r"^(generated|last_updated):", line):
            out.append(re.sub(r":.*", f": {date}", line))
        else:
            out.append(line)
    for e in epics:
        oe = e["num"]
        if oe not in omap:
            continue  # all-terminal epic stays behind in the old file
        ne = omap[oe]
        out += e["comments"]
        if e["marker"]:
            out.append(re.sub(r"epic-\d+", f"epic-{ne}", e["marker"]))
        for s in e["stories"]:
            if (s["epic"], s["story"]) not in smap:
                continue  # terminal — stays in the old file
            nk = smap[(s["epic"], s["story"])]
            st = (status_map or {}).get((s["epic"], s["story"]),
                                        s["status"])
            tail = f"  # was {s['epic']}.{s['story']} in {old_v}"
            if s["comment"]:
                tail += ", " + s["comment"].lstrip("# ")
            out.append(f"  {nk['key']}: {st}{tail}")
        for r in e["retro"]:
            out.append(re.sub(r"epic-\d+", f"epic-{ne}", r))
        out += e["other"]
    out += pending + post
    return "\n".join(out) + "\n"


def build_old_epics(head, epics, smap, moved, old_v, new_v, date):
    """Archive the old epics file: keep terminal stories verbatim, replace
    removed story runs with `<!-- moved -->` comments, drop empty epics."""
    out = []
    in_fm = False
    for i, line in enumerate(head):
        if i == 0 and line.strip() == "---":
            in_fm = True
            out.append(line)
            continue
        if in_fm:
            if line.strip() == "---":
                out.append(f"superseded: {new_v} by "
                           f"epics-beta-{new_v}.md")
                out.append(line)
                in_fm = False
                continue
            out.append(line)
            continue
        if re.match(r"^# ", line) and "-- ARCHIVED" not in line:
            out.append(line.rstrip() + " -- ARCHIVED")
            out += [
                "",
                f"> **ARCHIVED {date}** — superseded by "
                f"`epics-beta-{new_v}.md`. Terminal (done/obsolete) stories "
                f"are retained below; non-done stories migrated to "
                f"{new_v} under new numbers (see `<!-- moved -->` markers).",
            ]
            continue
        out.append(line)
    for e in epics:
        kept = [s for s in e["stories"]
                if (s["epic"], s["story"]) not in smap]
        if not kept and e["stories"]:
            out += ["", f"<!-- Epic {e['num']} ({e['heading'].split(':',1)[-1].strip()[:60]}) — all stories moved to {new_v} -->"]
            continue
        out += ["", e["heading"]] + e["preamble"]
        last = None
        if e["preamble"] and e["stories"]:
            out.append("")
        for s in e["stories"]:
            onum = f"{s['epic']}.{s['story']}"
            if (s["epic"], s["story"]) in smap:
                if last != "moved":
                    out.append("")
                tgt = smap[(s["epic"], s["story"])]
                out.append(f"<!-- Story {onum} moved to {new_v} as "
                           f"{tgt['new_num']} -->")
                last = "moved"
            else:
                if last == "moved":
                    out.append("")
                out += [s["heading"]] + s["lines"]
                last = "kept"
    return "\n".join(out) + "\n"


def build_old_sprint(pre, epics, pending, post, smap, new_v, date):
    """Archive the old sprint yaml: terminal lines verbatim, each migrated
    line becomes a `# key: status -> moved` comment."""
    out = pre[:]
    out.insert(0, f"# superseded: {date} by sprint-status-{new_v}.yaml "
                  f"(archived release — terminal stories retained)")
    for e in epics:
        out += e["comments"]
        if e["marker"]:
            out.append(e["marker"])
        for s in e["stories"]:
            onum = (s["epic"], s["story"])
            if onum in smap:
                out.append(f"  # {s['key']}: {s['status']} -> moved to "
                           f"{new_v} as {smap[onum]['key']}")
            else:
                out.append(s["line"])
        out += e["retro"] + e["other"]
    out += pending + post
    return "\n".join(out) + "\n"


def verify_write(path: Path, kind: str) -> str | None:
    """Post-write sanity for `.new` siblings: parses or None->error string."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return f"{path}: unreadable after write: {e}"
    if kind == "yaml":
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as e:
            return f"{path}: YAML no longer parses: {e}"
    if kind == "epics" and ("-- ARCHIVED" not in text
                            and "## Epic" not in text):
        # an archive where every story migrated legitimately keeps no epic
        # headings — require the archived marker instead of epics presence
        return f"{path}: archive has neither epics nor ARCHIVED marker"
    return None


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True,
                    help="plan JSON from resolve-upgrade.py, or '-' for stdin")
    ap.add_argument("--reclassify",
                    help="JSON object {story-key: status} merged into "
                         "plan.reclassify")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run

    plan = json.loads(sys.stdin.read() if args.plan == "-"
                      else Path(args.plan).read_text(encoding="utf-8"))
    if plan.get("status") == "fail":
        print(json.dumps({"status": "fail", "errors":
                          ["plan carries errors — resolve them first"]
                          + plan.get("errors", [])}))
        return 1
    rec = dict(plan.get("reclassify") or {})
    if args.reclassify:
        rec.update(json.loads(args.reclassify))
    for k, st in rec.items():
        if st in TERMINAL:
            print(json.dumps({"status": "fail", "errors": [
                f"reclassify {k}: '{st}' is terminal — only done->non-done "
                "reclassification is supported"]}))
            return 1

    old_v, new_v = plan["old_version"], plan["new_version"]
    paths = plan["paths"]
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    old_epics_p = Path(paths["old_epics"])
    old_sprint_p = Path(paths["old_sprint"])
    old_specs = Path(paths["old_spec_folder"])
    new_specs = Path(paths["new_spec_folder"])

    # ---- effective story set + maps --------------------------------------
    # epic/story numbers derive from the key itself (NN-MM-slug), so the
    # plan JSON stays lean — only key/status/spec need to cross the gate.
    terminal_keys = {s["key"] for s in plan["terminal"]}
    stories = []
    for s in plan["terminal"] + plan["non_terminal"]:
        m = re.match(r"^(\d+)-(\d+)-", s["key"])
        if not m:
            print(json.dumps({"status": "fail", "errors": [
                f"story key '{s['key']}' is not NN-MM-slug"]}))
            return 1
        st = rec.get(s["key"], s["status"])
        stories.append({**s, "status": st,
                        "epic": int(m.group(1)), "story": int(m.group(2))})
        if s["key"] in rec:
            terminal_keys.discard(s["key"])
    non_terminal = [s for s in stories if s["key"] not in terminal_keys]

    epic_order = plan["epic_order"]
    epics_in_plan = sorted({s["epic"] for s in non_terminal})
    if sorted(epic_order) != epics_in_plan:
        print(json.dumps({"status": "fail", "errors": [
            f"plan epic_order {epic_order} != migrating epics "
            f"{epics_in_plan}"]}))
        return 1

    # Bugs & Enhancement forced last — sprint tooling assumes the catch-all
    # sits in the fixed final position.
    epics_text = old_epics_p.read_text(encoding="utf-8", errors="replace")
    head, doc_epics = parse_epics(epics_text)
    be = [e["num"] for e in doc_epics
          if BUGS_EPIC_RE.search(e["heading"]) and e["num"] in epic_order]
    if be and epic_order[-1] != be[0]:
        epic_order = [e for e in epic_order if e != be[0]] + [be[0]]

    omap = {oe: i for i, oe in enumerate(epic_order, start=1)}
    smap = {}       # (old_epic, old_story) -> {key, new_num}
    kd = {}
    for s in non_terminal:
        m = re.match(r"^(\d+)-(\d+)-", s["key"])
        kd[s["key"]] = (len(m.group(1)), len(m.group(2)))
    for pos, oe in enumerate(epic_order, start=1):
        for ns, s in enumerate(
                [x for x in non_terminal if x["epic"] == oe], start=1):
            ew, sw = kd[s["key"]]
            smap[(s["epic"], s["story"])] = {
                "key": f"{pos:0{ew}d}-{ns:0{sw}d}-"
                       + s["key"].split("-", 2)[2],
                "new_num": f"{pos}.{ns}"}

    # migrating epics only, in confirmed order
    mig_epics = []
    for oe in epic_order:
        e = next(e for e in doc_epics if e["num"] == oe)
        keep = [s for s in e["stories"]
                if (s["epic"], s["story"]) in smap]
        mig_epics.append({**e, "stories": keep})

    # ---- sprint yaml groups ----------------------------------------------
    sprint_text = old_sprint_p.read_text(encoding="utf-8", errors="replace")
    pre, groups, pending, post = parse_sprint(sprint_text)
    for g in groups:
        g["stories"] = [s for s in g["stories"]
                        if (s["epic"], s["story"]) in smap
                        or s["key"] in terminal_keys
                        or s["status"] in TERMINAL]
    # order groups by epic_order for the new file
    ordered = [next((g for g in groups if g["num"] == oe), None)
               for oe in epic_order]
    ordered = [g for g in ordered if g] + \
              [g for g in groups if g["num"] not in epic_order]

    # story_location for the new yaml: reuse the old file's value with the
    # version swapped (preserves relative/absolute style); fall back to a
    # conventional relative path.
    spec_rel = None
    for line in pre:
        m = re.match(r"^story_location:\s*['\"]?(.+?)['\"]?\s*$", line)
        if m:
            spec_rel = m.group(1).replace(old_v, new_v)
            break
    if spec_rel is None:
        spec_rel = f"_bmad-output/implementation-artifacts/{new_v}"

    status_map = {(s["epic"], s["story"]): s["status"] for s in stories}
    new_epics = build_new_epics(head, mig_epics, plan, omap, old_v, new_v,
                                date)
    new_sprint = build_new_sprint(pre, ordered, pending, post, plan, omap,
                                  smap, old_v, new_v, date, spec_rel,
                                  status_map)
    arch_epics = build_old_epics(head, doc_epics, smap, {}, old_v, new_v,
                                 date)
    arch_sprint = build_old_sprint(pre, groups, pending, post, smap, new_v,
                                   date)

    # ---- spec-file bodies -------------------------------------------------
    spec_ops = []
    for (oe, os_), tgt in smap.items():
        old_key = next(s["key"] for s in non_terminal
                       if s["epic"] == oe and s["story"] == os_)
        src = old_specs / f"{old_key}.md"
        dst = new_specs / f"{tgt['key']}.md"
        spec_ops.append({"src": str(src), "dst": str(dst), "exists": src.is_file(),
                         "old_key": old_key, "new_key": tgt["key"],
                         "old_num": f"{oe}.{os_}", "new_num": tgt["new_num"]})

    result = {"script": "partition-renumber", "status": "pass", "dry_run": dry,
              "timestamp": datetime.now(timezone.utc).isoformat(),
              "old_version": old_v, "new_version": new_v,
              "epic_order": epic_order, "reclassified": rec,
              "keymap": {v["old_key"]: v["new_key"] for v in spec_ops},
              "files": {"new_epics": paths["new_epics"],
                        "new_sprint": paths["new_sprint"],
                        "new_spec_folder": str(new_specs),
                        "archived_epics": str(old_epics_p),
                        "archived_sprint": str(old_sprint_p)},
              "counts": {"migrating": len(non_terminal),
                         "terminal": len(terminal_keys),
                         "specs": sum(1 for o in spec_ops if o["exists"]),
                         "spec_missing": [o["old_key"] for o in spec_ops
                                          if not o["exists"]]},
              "preview": {"new_sprint": new_sprint[:4000]},
              "errors": []}

    if dry:
        print(json.dumps(result, indent=2))
        return 0

    # ---- apply: write new files first, archives via .new, then specs -----
    Path(paths["new_epics"]).write_text(new_epics, encoding="utf-8")
    Path(paths["new_sprint"]).write_text(new_sprint, encoding="utf-8")
    new_specs.mkdir(parents=True, exist_ok=True)

    for o in spec_ops:
        if not o["exists"]:
            continue
        body = Path(o["src"]).read_text(encoding="utf-8", errors="replace")
        body = re.sub(
            rf"^(# Story {re.escape(o['old_num'])}:.*)$",
            lambda m: inject_last_paren(
                re.sub(rf"# Story {re.escape(o['old_num'])}:",
                       f"# Story {o['new_num']}:", m.group(1)),
                f"was {o['old_num']} in {old_v}"),
            body, count=1, flags=re.M)
        for (oe2, os2), t2 in smap.items():
            body = body.replace(
                f"epics-beta-{old_v}.md#Story {oe2}.{os2}",
                f"epics-beta-{new_v}.md#Story {t2['new_num']}")
        Path(o["dst"]).write_text(body, encoding="utf-8")
        # copy-verify-then-delete: confirm the copy reads back before unlink
        back = Path(o["dst"]).read_text(encoding="utf-8", errors="replace")
        if f"# Story {o['new_num']}:" not in back:
            result["errors"].append(
                f"{o['dst']}: copied spec header mismatch — original kept")
            continue
        Path(o["src"]).unlink()

    # archives last: .new sibling -> verify -> rename over original
    for arch_path, content, kind in (
            (old_epics_p, arch_epics, "epics"),
            (old_sprint_p, arch_sprint, "yaml")):
        tmp = arch_path.with_name(arch_path.name + ".new")
        tmp.write_text(content, encoding="utf-8")
        err = verify_write(tmp, kind)
        if err:
            tmp.unlink(missing_ok=True)
            result["errors"].append(err + " — original untouched")
        else:
            tmp.replace(arch_path)

    result["status"] = "fail" if result["errors"] else "pass"
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
