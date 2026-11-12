#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""backlog-add.py — the canonical backlog append. Every dept intake-shape routes
through this instead of hand-writing lines — key allocation, marker, and field
order stop drifting.

Usage:
  uv run backlog-add.py --orchestration-dir /path/docs/orchestration
      --backlog product --key-prefix P --title "..." [--field name=value ...]
      [--key NN-MM-slug]

Emits {"key": "P7", "line": "..."}. Fields are appended in the canonical order:
pipe-separated `name: value` pairs. Key = next integer under the prefix scanned
from the backlog — OR an explicit `--key` for prefixed-key formats like the
code backlog's sprint keys (`13-20-unify-db-script-prod-semantics`), which
carry their own numbering scheme minted from the sprint yaml.

Exit codes: 0=appended, 1=validation, 2=runtime error
"""

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Append a canonically-formatted backlog item.")
    p.add_argument("--orchestration-dir", required=True)
    p.add_argument("--backlog", required=True,
                   help="backlog stem (product|code|content|curriculum|...) or dept name")
    p.add_argument("--key-prefix", help="P|CT|C|PL|D|Q|RC... — mints {prefix}{n+1}")
    p.add_argument("--key", default="",
                   help="explicit key — wins over --key-prefix (sprint keys "
                        "like NN-MM-slug carry their own numbering)")
    p.add_argument("--title", required=True)
    p.add_argument("--field", action="append", default=[],
                   metavar="NAME=VALUE", help="field pair (repeatable; order preserved)")
    p.add_argument("-o", "--output")
    return p.parse_args()


def main():
    args = parse_args()
    orch = Path(args.orchestration_dir).resolve()
    stem = Path(str(args.backlog).replace(".md", "")).stem
    if stem.startswith("cdo-"):
        stem = stem.replace("cdo-", "")
    bfile = orch / "backlogs" / f"{stem}.md"
    bfile.parent.mkdir(parents=True, exist_ok=True)
    if not bfile.is_file():
        bfile.write_text(f"# {stem.title()} Backlog\n\n## Items\n\n",
                         encoding="utf-8")

    if args.key:
        key = args.key.strip()
        if re.match(r"^S\d+$", key):
            # S{n} keys died in the sprint-key migration — canonical keys
            # are NN-MM-slug minted from the sprint yaml
            print(json.dumps({"errors": [
                f"key {key} uses the retired S{{n}} format — new work takes "
                "sprint keys (NN-MM-slug); see intake-shape"]}))
            sys.exit(1)
        if re.search(rf"^- \[.\] {re.escape(key)}\b",
                     bfile.read_text(encoding="utf-8"), re.M):
            print(json.dumps({"errors": [f"key {key} already exists in "
                                         f"backlogs/{stem}.md"]}))
            sys.exit(1)
    elif args.key_prefix:
        # next key under the prefix — digits only, no substring collisions
        n = 0
        key_re = re.compile(rf"^- \[.\] {re.escape(args.key_prefix)}(\d+)\b", re.M)
        for m in key_re.finditer(bfile.read_text(encoding="utf-8")):
            n = max(n, int(m.group(1)))
        key = f"{args.key_prefix}{n + 1}"
    else:
        print(json.dumps({"errors": ["--key or --key-prefix required"]}))
        sys.exit(1)

    fields = ""
    for pair in args.field:
        if "=" not in pair:
            print(json.dumps({"errors": [f"--field needs name=value, got {pair!r}"]}))
            sys.exit(1)
        name, value = pair.split("=", 1)
        fields += f" | {name.strip()}: {value.strip()}"

    line = f"- [ ] {key} — {args.title}{fields}"
    with open(bfile, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    out = json.dumps({"status": "added", "key": key, "backlog": f"backlogs/{stem}.md",
                      "line": line}, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"errors": [f"runtime error: {e}"]}))
        sys.exit(2)
