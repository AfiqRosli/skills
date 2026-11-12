#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""migrate-sprint-keys.py — one-time rekey of the CDO backlog from legacy
S{n} keys to canonical sprint keys (NN-MM-slug), for the 2026-10-18
shape-at-intake redesign.

What it does (idempotent — safe to re-run; every op no-ops when already done):

  1. Scans {orch}/backlogs/code.md for `S{n}` item keys, maps each to its
     sprint key: the title's embedded `NN-MM` prefix resolves to the existing
     sprint-yaml story key; a prefix with no yaml entry mints `NN-MM-{slug}`
     at that story number; no prefix at all mints the next free `13-MM-{slug}`
     (epic-13 is the eng-hygiene catch-all).
  2. Rewrites code.md: key → sprint key, redundant `NN-MM` title prefix
     dropped, every `S{n}` token in fields (deps:, status text) re-keyed.
  3. Inserts sprint-yaml `development_status` entries for minted keys —
     `[x]` → `done`, `[-]` → `backlog` (confirmed-quarantined), else `proposed`.
  4. Creates skeleton story files at {story_location}/{key}.md for every
     migrated item missing one (epics-doc section embedded when present).
  5. Appends `### Story` sections to the epics doc for minted keys that
     lack one.
  6. Renames alignment cards: drafts/{S}.md + archived */{S}.md and
     {S}.review-*.md → sprint key; re-keys card bodies.
  7. Re-keys flow-ledger.yaml (stories.*, pool lists, manifest, doc paths,
     quarantine reasons — every mapped S{n} token).
  8. Renames sessions/{S}.* and learning/knowledge/{S}.yaml → sprint keys.
  9. Migrates devlog/CDO/<date>/<Skey|Ckey>/ dirs under the current sprint's
     devlog/<Channel>/<date>/ — merges index.md journal + frontmatter into an
     existing target, else moves the dir; removes the empty CDO tree.
 10. Re-keys cross-backlog references (content.md source:, curriculum.md
     sources:), the checklist, and handover.md.
 11. Corrects release-train.json current.sprint to the live sprint.
 12. Journals the migration: logs/chronology.md line +
     logs/sprint-key-migration-{date}.json record.

Historical journals (doctrine.md, frago-inbox.md entries, patterns.md,
atif.json contents) are left verbatim — the migration record is the
S{n}→sprint-key dictionary for resolving old references.

Usage:
  uv run migrate-sprint-keys.py --orchestration-dir /path/docs/orchestration
      --project-root /path --dry-run     # print the plan, write nothing
  uv run migrate-sprint-keys.py --orchestration-dir ... --project-root ... --apply

Exit codes: 0=ok (or dry-run), 1=validation failure, 2=runtime error
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: pyyaml is required (PEP 723 dependency)", file=sys.stderr)
    sys.exit(2)


BACKLOG_LINE_RE = re.compile(
    r"^- \[(?P<mark>.)] (?P<key>\S+) — (?P<rest>.*)$")
PREFIX_RE = re.compile(r"^(\d{1,2})-(\d{1,2})\b\s*")


def slugify(text: str, max_words: int = 8) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    parts = s.split("-")
    return "-".join(parts[:max_words]) if len(parts) > max_words else s


def mint_slug(title: str, max_words: int = 6) -> str:
    """Slug for a minted key — prefer the segment before ':'/'—'/'(' when it
    carries >=2 words ('Dry-run smoke: add a comment…' -> 'dry-run-smoke')."""
    seg = re.split(r"[:—(]", title)[0].strip()
    cand = seg if len(slugify(seg).split("-")) >= 2 else title
    return slugify(cand, max_words)


def newest_sprint_yaml(project_root: Path):
    """The live sprint = newest sprint-status-*.yaml by release-date suffix."""
    impl = project_root / "_bmad-output" / "implementation-artifacts"
    cands = sorted(impl.glob("sprint-status-*.yaml"))
    if not cands:
        return None
    def key(p):
        m = re.search(r"sprint-status-(.+)\.yaml$", p.name)
        parts = re.split(r"[.\-]", m.group(1)) if m else []
        return [int(x) if x.isdigit() else 0 for x in parts]
    return max(cands, key=key)


def release_to_devlog_parts(release: str):
    """Beta-2026.10.11 -> ('Beta', '2026-10-11'); mirrors devlog.py."""
    seg = release.split("-", 1)
    channel = seg[0]
    if len(seg) < 2:
        return channel, "undated"
    date = re.sub(r"^(\d{4})\.(\d{2})\.(\d{2})(\.|$)", r"\1-\2-\3\4", seg[1])
    date = re.sub(r"\.(\d+)$", r".\1", date)
    return channel, date


def yaml_story_keys(text: str) -> dict:
    """{story-key: status} parsed out of the flat development_status block —
    epic markers (`  epic-N: in-progress`) and story keys
    (`  13-04-…: done`) are sibling keys at 2-space indent."""
    keys = {}
    in_dev = False
    for line in text.splitlines():
        if re.match(r"^development_status:", line):
            in_dev = True
            continue
        if re.match(r"^\S", line):           # next top-level key ends the block
            in_dev = False
            continue
        if in_dev:
            km = re.match(r"^  (\d{2}-\d{2}-\S+):\s*([^#\n]*)", line)
            if km:
                keys[km.group(1)] = km.group(2).strip()
    return keys


def insert_yaml_entry(text: str, epic: int, key: str, status: str) -> str:
    """Insert `  {key}: {status}` after the `  epic-N:` marker inside the flat
    development_status block, ordered by the story's NN-MM prefix and kept
    ahead of the next epic marker/retrospective key."""
    kn = re.match(r"(\d+)-(\d+)", key)
    if not kn:
        return text
    n_epic, n_story = int(kn.group(1)), int(kn.group(2))
    lines = text.splitlines()
    epic_line = None
    for i, line in enumerate(lines):
        if re.match(rf"^  epic-{epic}:\s", line):
            epic_line = i
            break
    if epic_line is None:
        return text
    # scan this epic's story-key lines; insert before the first with a higher
    # story number, or before the first line that isn't one of this epic's keys
    insert_at = None
    for i in range(epic_line + 1, len(lines)):
        km = re.match(rf"^  {n_epic}-(\d+)-\S+:", lines[i])
        if km:
            if int(km.group(1)) > n_story:
                insert_at = i
                break
            continue
        if re.match(r"^  \S", lines[i]):     # another key ends the block
            insert_at = i
            break
    if insert_at is None:
        insert_at = len(lines)
    lines.insert(insert_at, f"  {key}: {status}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def epics_section(epics_text: str, nn: int, mm: int):
    """Return the '### Story {n}.{m}:' section body (sans heading) or None."""
    pat = re.compile(rf"^### Story {nn}\.{mm}:.*$", re.M)
    m = pat.search(epics_text)
    if not m:
        return None
    rest = epics_text[m.end():]
    nxt = re.search(r"^#{2,3} ", rest, re.M)
    return rest[:nxt.start()].rstrip() if nxt else rest.rstrip()


STORY_SKELETON = """# Story {nn}.{mm}: {title}

**Status:** {status}

## Story

{story}

## Acceptance Criteria

{acs}

## Tasks / Subtasks

- [ ] TBD — `cdo-code-e2e` step 1 (create-story) decomposes when the produce leg runs

## Dev Notes

- CDO-migrated item — shaped spec lives in `epics-beta-{release}.md` under
  `### Story {nn}.{mm}` (mirrored below where present).
- Migrated {date} from legacy backlog key `{old_key}`.

## Shaped Spec

{spec}
"""


def story_skeleton(key: str, title: str, status: str, spec: str,
                   old_key: str, release: str, date: str,
                   backlog_approach: str) -> str:
    m = re.match(r"(\d+)-(\d+)-", key)
    nn, mm = (m.group(1), m.group(2)) if m else ("0", "0")
    story = (f"As an operator/user, I want {title}, so that the item's "
             f"acceptance criteria in the shaped spec hold.")
    acs = "- TBD — `cdo-code-e2e` step 1 enriches from the shaped spec"
    if not spec:
        spec = backlog_approach or "_no shaped spec recorded — backlog line only_"
    return STORY_SKELETON.format(nn=nn, mm=mm, title=title, status=status,
                                 story=story, acs=acs, spec=spec,
                                 release=release, date=date, old_key=old_key)


# ---------------------------------------------------------------- migration

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--project-root", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = p.parse_args()

    orch = Path(args.orchestration_dir).resolve()
    root = Path(args.project_root).resolve()
    dry = args.dry_run
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    sprint_yaml = newest_sprint_yaml(root)
    if sprint_yaml is None:
        print(json.dumps({"errors": ["no sprint-status-*.yaml under "
                                     "_bmad-output/implementation-artifacts"]}))
        sys.exit(1)
    release = re.search(r"sprint-status-(.+)\.yaml$", sprint_yaml.name).group(1)
    channel, sprint_date = release_to_devlog_parts(release)
    sprint_text = sprint_yaml.read_text(encoding="utf-8")
    yaml_keys = yaml_story_keys(sprint_text)
    story_loc = None
    m = re.search(r"^story_location:\s*(.+)$", sprint_text, re.M)
    if m:
        story_loc = root / m.group(1).strip().strip("'\"").replace(
            "{project-root}", "").lstrip("/\\")
    if story_loc is None:
        story_loc = root / "_bmad-output" / "implementation-artifacts" / release
    epics_path = root / "_bmad-output" / "planning-artifacts" / \
        f"epics-beta-{release}.md"
    epics_text = epics_path.read_text(encoding="utf-8") \
        if epics_path.is_file() else ""

    code_path = orch / "backlogs" / "code.md"
    code_text = code_path.read_text(encoding="utf-8")

    # ---- 1. build the key map ------------------------------------------
    keymap = {}          # S{n} -> sprint key
    minted = {}          # sprint key -> (epic, status, title)
    mints_used = set()
    epic_nums = re.findall(r"^### Story 13\.(\d+):", epics_text, re.M)
    next_free_13 = max(
        [int(re.match(r"13-(\d+)", k).group(1)) for k in yaml_keys
         if re.match(r"13-\d", k)] + [int(n) for n in epic_nums] + [0]) + 1

    def rekey_token(match):
        return keymap.get(match.group(0), match.group(0))

    for line in code_text.splitlines():
        lm = BACKLOG_LINE_RE.match(line)
        if not lm or not re.fullmatch(r"S\d+", lm.group("key")):
            continue
        skey = lm.group("key")
        rest = lm.group("rest")
        title = rest.split(" | ", 1)[0].strip()
        pm = PREFIX_RE.match(title)
        mapped = None
        epic_no = 13
        clean_title = title
        if pm:
            nn, mm = pm.group(1).zfill(2), pm.group(2).zfill(2)
            epic_no = int(pm.group(1))
            prefix = f"{nn}-{mm}"
            cand = [k for k in yaml_keys if k.startswith(f"{prefix}-")]
            clean_title = title[pm.end():].strip() or title
            if cand:
                mapped = cand[0]
            else:
                mapped = f"{prefix}-{mint_slug(clean_title)}"
        else:
            mm = f"{next_free_13:02d}"
            while f"13-{mm}" in mints_used or \
                    any(k.startswith(f"13-{mm}-") for k in yaml_keys):
                next_free_13 += 1
                mm = f"{next_free_13:02d}"
            mapped = f"13-{mm}-{mint_slug(title)}"
            next_free_13 += 1
            mints_used.add(mm)
        keymap[skey] = mapped
        if mapped not in yaml_keys:
            if pm:
                mints_used.add(pm.group(2).zfill(2))
            mark = lm.group("mark")
            status = ("done" if mark == "x" else
                      "backlog" if mark == "-" else "proposed")
            minted[mapped] = (epic_no, status, clean_title)

    token_re = re.compile(r"\bS\d+\b")

    def rekey(text):
        return token_re.sub(rekey_token, text)

    ops = {"keymap": keymap, "minted": {k: list(v) for k, v in minted.items()},
           "story_files": [], "renames": [], "devlog_moves": [],
           "epics_appends": []}

    # ---- 2. code.md rewrite --------------------------------------------
    new_lines = []
    for line in code_text.splitlines():
        lm = BACKLOG_LINE_RE.match(line)
        if lm and re.fullmatch(r"S\d+", lm.group("key")):
            skey = lm.group("key")
            new_key = keymap[skey]
            rest = rekey(lm.group("rest"))
            title = rest.split(" | ", 1)[0].strip()
            pm = PREFIX_RE.match(title)
            if pm and f"{pm.group(1).zfill(2)}-{pm.group(2).zfill(2)}" in new_key:
                title = title[pm.end():].strip() or title
            tail = rest.split(" | ", 1)
            rest = title + (" | " + tail[1] if len(tail) > 1 else "")
            new_lines.append(f"- [{lm.group('mark')}] {new_key} — {rest}")
        else:
            new_lines.append(rekey(line))
    new_code = "\n".join(new_lines) + ("\n" if code_text.endswith("\n") else "")

    # ---- 3/4/5. yaml inserts, story files, epics sections ---------------
    for skey, new_key in keymap.items():
        lm_title = ""
        for line in code_text.splitlines():
            lm = BACKLOG_LINE_RE.match(line)
            if lm and lm.group("key") == skey:
                lm_title = lm.group("rest").split(" | ", 1)[0].strip()
                break
        pm = PREFIX_RE.match(lm_title)
        title = lm_title[pm.end():].strip() if pm else lm_title
        if new_key in minted and new_key not in yaml_story_keys(sprint_text):
            epic_no, status, _ = minted[new_key]
            sprint_text = insert_yaml_entry(sprint_text, epic_no, new_key, status)
            ops.setdefault("yaml_inserts", []).append(f"{new_key}: {status}")
        # story file
        sfile = story_loc / f"{new_key}.md"
        if not sfile.is_file():
            mm = re.match(r"(\d+)-(\d+)", new_key)
            spec = epics_section(epics_text, int(mm.group(1)), int(mm.group(2))) \
                if mm else None
            approach = ""
            for line in code_text.splitlines():
                lm = BACKLOG_LINE_RE.match(line)
                if lm and lm.group("key") == skey:
                    approach = lm.group("rest")
                    break
            status = minted.get(new_key, (None, yaml_keys.get(new_key, "proposed"), None))[1]
            content = story_skeleton(new_key, title, status, spec or "",
                                     skey, release, date, approach)
            ops["story_files"].append(str(sfile))
            if not dry:
                sfile.write_text(content, encoding="utf-8")
        # epics section for minted keys lacking one
        mm = re.match(r"(\d+)-(\d+)", new_key)
        if mm and new_key in minted and \
                epics_section(epics_text, int(mm.group(1)), int(mm.group(2))) is None:
            sect_title = re.split(r"\s*\(", title)[0].strip()
            sect = (f"\n### Story {int(mm.group(1))}.{int(mm.group(2))}: "
                    f"{sect_title} (NEW {date}, CDO {skey} — migrated)\n\n"
                    f"**Story:** migrated CDO backlog item `{skey}` — see backlog "
                    f"line + devlog for the operational spec.\n\n"
                    f"**Description:** {title}.\n")
            ops["epics_appends"].append(f"### Story {int(mm.group(1))}.{int(mm.group(2))}: {title}")
            epics_text = epics_text.rstrip() + "\n" + sect

    # ---- 6. alignment renames ------------------------------------------
    align_files = []
    drafts = orch / "alignment" / "drafts"
    if drafts.is_dir():
        align_files += [f for f in drafts.glob("S*.md")]
    align_files += [f for f in (orch / "alignment").glob("**/S*.md")
                    if "drafts" not in f.parts]
    for f in align_files:
        km = re.match(r"(S\d+)(\..*)?$", f.name)
        if not km or km.group(1) not in keymap:
            continue
        new_name = keymap[km.group(1)] + (km.group(2) or "")
        target = f.with_name(new_name)
        ops["renames"].append(f"{f.relative_to(orch)} -> {target.relative_to(orch)}")
        if not dry:
            body = rekey(f.read_text(encoding="utf-8"))
            f.unlink()
            target.write_text(body, encoding="utf-8")

    # ---- 7/10. content rewrites on live state ---------------------------
    for rel in ["flow-ledger.yaml", "alignment-checklist.md", "handover.md",
                "backlogs/content.md", "backlogs/curriculum.md"]:
        f = orch / rel
        if not f.is_file():
            continue
        t = rekey(f.read_text(encoding="utf-8"))
        # drop now-redundant `NN-MM ` title prefix after a re-keyed item key
        t = re.sub(r"(\] \d{2}-\d{2}-[a-z0-9-]+ — )\d{1,2}-\d{1,2}\s+",
                   r"\1", t)
        if not dry:
            f.write_text(t, encoding="utf-8")

    # ---- 8. sessions + knowledge renames --------------------------------
    for f in sorted((orch / "sessions").glob("S*.*")) + \
            sorted((orch / "learning" / "knowledge").glob("S*.yaml")):
        km = re.match(r"(S\d+)(\..*)$", f.name)
        if not km or km.group(1) not in keymap:
            continue
        target = f.with_name(keymap[km.group(1)] + km.group(2))
        ops["renames"].append(f"{f.relative_to(orch)} -> {target.relative_to(orch)}")
        if not dry:
            if f.suffix == ".json" and f.name.endswith(".atif.json"):
                f.rename(target)          # transcripts: rename only, keep verbatim
            else:
                body = rekey(f.read_text(encoding="utf-8", errors="replace"))
                f.unlink()
                target.write_text(body, encoding="utf-8")

    # ---- 9. devlog migration ---------------------------------------------
    devlog_root = root / "docs" / "orchestration" / "devlog"
    cdo_root = devlog_root / "CDO"
    sprint_devlog = devlog_root / channel / sprint_date
    if cdo_root.is_dir():
        for dated_dir in sorted(cdo_root.iterdir()):
            if not dated_dir.is_dir():
                continue
            for item_dir in sorted(dated_dir.iterdir()):
                if not item_dir.is_dir():
                    continue
                old_key = item_dir.name
                new_key = keymap.get(old_key, old_key)
                target_dir = sprint_devlog / new_key
                ops["devlog_moves"].append(
                    f"{item_dir.relative_to(devlog_root)} -> "
                    f"{target_dir.relative_to(devlog_root)}")
                if dry:
                    continue
                sprint_devlog.mkdir(parents=True, exist_ok=True)
                if target_dir.is_dir():
                    # merge: graft dispatch:/cdo: frontmatter if absent,
                    # append source journal entries, move aux files
                    src_idx = item_dir / "index.md"
                    tgt_idx = target_dir / "index.md"
                    if src_idx.is_file() and tgt_idx.is_file():
                        src = rekey(src_idx.read_text(encoding="utf-8"))
                        tgt = tgt_idx.read_text(encoding="utf-8")
                        # graft frontmatter blocks
                        for block in ("dispatch:", "cdo:"):
                            if not re.search(rf"^{block}", tgt, re.M):
                                bm = re.search(
                                    rf"^{block}\n(?:  .+\n|    .+\n|      .+\n)+",
                                    src, re.M)
                                if bm:
                                    fm_end = tgt.find("\n---", 3)
                                    if fm_end > 0:
                                        tgt = tgt[:fm_end] + "\n" + \
                                            bm.group(0).rstrip() + tgt[fm_end:]
                        # append journal entries
                        sm = re.search(r"^## Journal\n(.*)$", src, re.M | re.S)
                        if sm:
                            entries = sm.group(1).strip()
                            if entries:
                                marker = (f"#### Dispatch arc merged — "
                                          f"CDO/{dated_dir.name}/{old_key} "
                                          f"({date})\n\n")
                                tgt = tgt.rstrip() + "\n\n" + marker + \
                                    entries + "\n"
                        tgt_idx.write_text(tgt, encoding="utf-8")
                    elif src_idx.is_file():
                        target_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_idx, tgt_idx)
                        tgt_idx.write_text(
                            rekey(tgt_idx.read_text(encoding="utf-8")),
                            encoding="utf-8")
                    for extra in item_dir.iterdir():
                        if extra.name == "index.md":
                            continue
                        dest = target_dir / extra.name
                        if dest.exists():
                            dest = target_dir / \
                                f"{extra.stem}-cdo{extra.suffix}"
                        shutil.copy2(extra, dest)
                    shutil.rmtree(item_dir)
                else:
                    shutil.move(str(item_dir), str(target_dir))
                    idx = target_dir / "index.md"
                    if idx.is_file():
                        idx.write_text(
                            rekey(idx.read_text(encoding="utf-8")),
                            encoding="utf-8")
            # drop the now-empty dated dir
            try:
                dated_dir.rmdir()
            except OSError:
                pass
        try:
            cdo_root.rmdir()
        except OSError:
            pass

    # ---- 11. release-train correction -------------------------------------
    rt = root / "release-train.json"
    if rt.is_file():
        rt_data = json.loads(rt.read_text(encoding="utf-8"))
        if rt_data.get("current", {}).get("sprint") != release:
            rt_data.setdefault("current", {})["sprint"] = release
            ops.setdefault("release_train", f"current.sprint -> {release}")
            if not dry:
                rt.write_text(json.dumps(rt_data, indent=2) + "\n",
                              encoding="utf-8")

    # ---- writes: code.md + sprint yaml + epics doc -------------------------
    if not dry:
        code_path.write_text(new_code, encoding="utf-8")
        sprint_yaml.write_text(sprint_text, encoding="utf-8")
        if epics_path.is_file():
            epics_path.write_text(epics_text + "\n", encoding="utf-8")

    # ---- 12. journal -------------------------------------------------------
    log_dir = orch / "logs"
    record = {"date": date, "sprint": release, "keymap": keymap,
              "minted": {k: list(v) for k, v in minted.items()},
              "ops": {k: v for k, v in ops.items() if k not in ("keymap", "minted")}}
    if not dry:
        log_dir.mkdir(exist_ok=True)
        (log_dir / f"sprint-key-migration-{date}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8")
        chrono = log_dir / "chronology.md"
        entry = (f"- {date} — sprint-key migration: {len(keymap)} legacy S-keys "
                 f"re-keyed to NN-MM-slug ({len(minted)} minted entries); CDO "
                 f"devlogs merged under devlog/{channel}/{sprint_date}; record: "
                 f"logs/sprint-key-migration-{date}.json\n")
        chrono.write_text(chrono.read_text(encoding="utf-8").rstrip() +
                          "\n" + entry, encoding="utf-8")

    print(json.dumps({"dry_run": dry, **record}, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
