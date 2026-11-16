"""One-shot gap-check driver for cdo-academy — walks learning/knowledge/*.yaml
against docs/academy/catalog.yaml and files confirmed gaps via catalog.py file-gap.
All file IO is explicit UTF-8. Safe to delete after the run.
Usage: _gapcheck_run.py <project-root> [summary-out.json]"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("CDO_PROJECT_ROOT") or (sys.argv[1] if len(sys.argv) > 1 else ".")).resolve()
ORCH = ROOT / "docs" / "orchestration"
KNOW = ORCH / "learning" / "knowledge"
CATALOG = ROOT / "docs" / "academy" / "catalog.yaml"
CATALOG_PY = ROOT / ".agents" / "skills" / "cdo-academy" / "scripts" / "catalog.py"

LEVELS = {"fundamentals": 1, "intermediate": 2, "advanced": 3}

# ── 1. catalog coverage map: concept-id -> highest taught level ──────────
cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
covered: dict[str, int] = {}
for track in (cat.get("tracks") or {}).values():
    for course in (track.get("courses") or {}).values():
        for mid, mod in (course.get("modules") or {}).items():
            lvl = LEVELS.get((mod or {}).get("level") or "fundamentals", 1)
            covered[mid] = max(covered.get(mid, 0), lvl)
            for cid in (mod or {}).get("concepts") or []:
                covered[cid] = max(covered.get(cid, 0), lvl)

existing_courses = set()
for tid, track in (cat.get("tracks") or {}).items():
    for coid in (track.get("courses") or {}).keys():
        existing_courses.add((tid, coid))

# ── 2. knowledge extractions: defined concepts + requires ids ────────────
defined: dict[str, dict] = {}
undefined_reqs: dict[str, set] = {}  # id -> set of (track, course) hints
req_sources: dict[str, set] = {}

for kf in sorted(KNOW.glob("*.yaml")):
    story = kf.stem
    data = yaml.safe_load(kf.read_text(encoding="utf-8")) or {}
    for c in data.get("concepts") or []:
        cid = c.get("id")
        if not cid:
            continue
        entry = defined.setdefault(cid, {
            "id": cid, "name": c.get("name") or cid.replace("-", " "),
            "kind": c.get("kind") or "concept",
            "level": c.get("level") or "fundamentals",
            "track": c.get("track") or "delivery-org",
            "course": c.get("course") or "general",
            "sources": set(), "evidence": bool(c.get("evidence")),
        })
        entry["sources"].add(story)
        # keep the highest demanded level for the coverage test + filing
        if LEVELS.get(c.get("level") or "fundamentals", 1) > LEVELS.get(entry["level"], 1):
            entry["level"] = c["level"]
        if c.get("evidence") and not entry["evidence"]:
            entry["evidence"] = True
            for k in ("name", "kind", "track", "course"):
                if c.get(k):
                    entry[k] = c[k]
        for req in c.get("requires") or []:
            req_sources.setdefault(req, set()).add(story)
            undefined_reqs.setdefault(req, set()).add(
                (c.get("track") or "", c.get("course") or ""))

# requires ids never defined as concepts — still chain rungs to check
for rid, hints in undefined_reqs.items():
    if rid in defined or rid in covered:
        continue
    # infer placement from the majority of requiring concepts
    (tr, co), *_ = sorted(hints, key=lambda h: (-list(hints).count(h), h))
    defined[rid] = {
        "id": rid, "name": rid.replace("-", " "),
        "kind": "concept", "level": "fundamentals",
        "track": tr or "delivery-org", "course": co or "general",
        "sources": req_sources.get(rid, set()), "evidence": False,
        "chain_stub": True,
    }

# ── 3. coverage verdict ──────────────────────────────────────────────────
cov, gaps = [], []
for cid, e in defined.items():
    need = LEVELS.get(e["level"], 1)
    have = covered.get(cid, 0)
    (cov if have >= need else gaps).append(e)

print(f"catalog covered ids: {len(covered)}")
print(f"defined concept ids: {len(defined)}")
print(f"covered at needed level: {len(cov)}")
print(f"gap candidates: {len(gaps)}")

# ── 4. file confirmed gaps ───────────────────────────────────────────────
filed, already, errors = [], [], []
for e in sorted(gaps, key=lambda x: x["id"]):
    cmd = [
        sys.executable, str(CATALOG_PY),
        "--orchestration-dir", str(ORCH),
        "file-gap",
        "--concept-id", e["id"],
        "--title", e["name"],
        "--kind", e["kind"],
        "--track", e["track"],
        "--course", e["course"],
        "--level", e["level"],
        "--sources", ",".join(sorted(e["sources"])),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        out = json.loads(r.stdout.strip())
    except Exception:
        out = {"status": "error", "raw": r.stdout[-300:] + r.stderr[-300:]}
    st = out.get("status")
    if st == "filed":
        filed.append(out)
    elif st == "already-filed":
        already.append(out)
    else:
        errors.append({"id": e["id"], "out": out, "rc": r.returncode})

print(f"filed: {len(filed)}  already-filed: {len(already)}  errors: {len(errors)}")
summary = {
    "checked": len(defined),
    "covered": sorted(e["id"] for e in cov),
    "gaps_filed": [{"key": f.get("key"), "concept_id": f.get("concept_id")} for f in filed],
    "already_known": sorted(a.get("concept_id") for a in already),
    "errors": errors,
}
Path(sys.argv[2] if len(sys.argv) > 2 else "gapcheck-summary.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8")
for e in errors:
    print("ERR", e)
