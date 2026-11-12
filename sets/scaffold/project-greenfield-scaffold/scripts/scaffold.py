#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
project-greenfield-scaffold — renders the spine template into a target
directory with flag-driven module filtering.

Copies assets/template/ → TARGET, substituting {{PROJECT_NAME}},
{{PROJECT_SLUG}}, and {{SITE_URL}} tokens; removes // @flag <module>
blocks for disabled modules; drops excluded paths; renders package.json
dependencies from assets/versions.json minus flag-stripped deps; and
copies assets/rules/ → TARGET/.devin/rules unless the rules module is
off.

Modules (all ON by default): core, rules, tests, db, auth, billing,
email, redis, sentry, seo, docs, deploy. Disable with --skip <module>
(repeatable) or --minimal (keeps core+rules+tests).

Flag-block syntax inside template files — marker lines are comments and
are never emitted; the lines between them are emitted only when the
named module is enabled:

    // @flag auth            // or: /* @flag auth */, # @flag auth,
    <emitted iff auth on>    <!-- @flag auth -->
    // @endflag auth

Outputs a JSON report to stdout (or -o FILE). Exit 0 on success,
1 on validation failure, 2 on error.
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSETS = SKILL_DIR / "assets"
TEMPLATE_DIR = ASSETS / "template"
RULES_DIR = ASSETS / "rules"
FLAGS_FILE = ASSETS / "flags.json"
VERSIONS_FILE = ASSETS / "versions.json"

FLAG_OPEN = re.compile(r"@flag\s+([A-Za-z0-9_-]+)")
FLAG_CLOSE = re.compile(r"@endflag\s+([A-Za-z0-9_-]+)")
TOKEN = re.compile(r"\{\{(PROJECT_NAME|PROJECT_SLUG|SITE_URL)\}\}")


def log(msg: str, verbose: bool) -> None:
    if verbose:
        print(msg, file=sys.stderr)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_modules(flags: dict, skips: set[str], minimal: bool) -> tuple[set[str], list[str], list[str]]:
    """Return (enabled, auto_disabled, warnings). Cascade: a module whose
    requires are disabled is itself disabled."""
    modules = set(flags["modules"].keys()) - {"core"}
    disabled = set(skips) & modules
    unknown = set(skips) - modules - {"minimal"}
    warnings = [f"unknown --skip value '{s}' ignored" for s in sorted(unknown)]

    if minimal:
        disabled |= set(flags.get("expansions", {}).get("minimal", [])) & modules

    auto_disabled: list[str] = []
    changed = True
    while changed:
        changed = False
        for mod, meta in flags["modules"].items():
            if mod in disabled or mod == "core":
                continue
            reqs = set(meta.get("requires", []))
            if reqs & disabled:
                disabled.add(mod)
                auto_disabled.append(mod)
                changed = True

    enabled = modules - disabled
    return enabled, auto_disabled, warnings


def render_flags(text: str, enabled: set[str]) -> tuple[str, int]:
    """Strip flag markers + drop blocks for disabled modules. Returns
    (rendered_text, lines_removed)."""
    out: list[str] = []
    open_flags: list[str] = []
    removed = 0
    for line in text.splitlines(keepends=True):
        if m := FLAG_OPEN.search(line):
            open_flags.append(m.group(1))
            removed += 1
            continue
        if m := FLAG_CLOSE.search(line):
            if open_flags and open_flags[-1] == m.group(1):
                open_flags.pop()
            removed += 1
            continue
        if any(f not in enabled for f in open_flags):
            removed += 1
            continue
        out.append(line)
    return "".join(out), removed


def substitute(text: str, tokens: dict[str, str]) -> str:
    return TOKEN.sub(lambda m: tokens[m.group(1)], text)


def is_excluded(rel: Path, excluded: set[str]) -> bool:
    parts = rel.as_posix()
    for ex in excluded:
        if parts == ex or parts.startswith(ex.rstrip("/") + "/"):
            return True
    return False


def build_package_json(tokens: dict[str, str], enabled: set[str], flags: dict, versions: dict) -> tuple[str, int]:
    pkg = json.loads(
        substitute((TEMPLATE_DIR / "package.json").read_text(encoding="utf-8"), tokens)
    )
    disabled = set(flags["modules"]) - enabled - {"core"}

    stripped_deps: set[str] = set()
    for mod in disabled:
        stripped_deps.update(versions.get("flag_stripped_deps", {}).get(mod, []))

    pkg["dependencies"] = dict(sorted(
        (k, v) for k, v in versions["dependencies"].items() if k not in stripped_deps
    ))
    pkg["devDependencies"] = dict(sorted(
        (k, v) for k, v in versions["devDependencies"].items() if k not in stripped_deps
    ))

    removed = 0
    for mod in disabled:
        for script in flags.get("excluded_scripts", {}).get(mod, []):
            if pkg["scripts"].pop(script, None) is not None:
                removed += 1

    return json.dumps(pkg, indent=2) + "\n", removed


def scaffold(target: Path, name: str, site_url: str, enabled: set[str], flags: dict, versions: dict, verbose: bool) -> dict:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    tokens = {
        "PROJECT_NAME": name,
        "PROJECT_SLUG": slug,
        "SITE_URL": site_url,
    }

    excluded_paths: set[str] = set()
    for mod in set(flags["modules"]) - enabled - {"core"}:
        excluded_paths.update(flags.get("excluded_paths", {}).get(mod, []))

    written: list[str] = []
    excluded: list[str] = []
    flag_lines_removed = 0

    for src in sorted(TEMPLATE_DIR.rglob("*")):
        rel = src.relative_to(TEMPLATE_DIR)
        if src.is_dir():
            continue
        if is_excluded(rel, excluded_paths):
            excluded.append(rel.as_posix())
            continue

        # .tmpl suffix marks payload files that IDEs would misparsed as
        # real configs (e.g. tsconfig.json extends ./.nuxt which only
        # exists post-render) — strip the suffix on copy.
        if rel.suffix == ".tmpl":
            rel = rel.with_suffix("")
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        raw = src.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            dest.write_bytes(raw)  # binary asset — copy verbatim
            written.append(rel.as_posix())
            continue

        text = substitute(text, tokens)
        if rel.as_posix() == "package.json":
            text, removed = build_package_json(tokens, enabled, flags, versions)
        else:
            text, removed = render_flags(text, enabled)
        flag_lines_removed += removed

        dest.write_text(text, encoding="utf-8")
        written.append(rel.as_posix())
        log(f"  wrote {rel}", verbose)

    # Rules set → .devin/rules
    if "rules" in enabled and RULES_DIR.is_dir():
        for src in sorted(RULES_DIR.rglob("*")):
            if src.is_dir():
                continue
            rel = Path(".devin/rules") / src.relative_to(RULES_DIR)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            written.append(rel.as_posix())
            log(f"  wrote {rel}", verbose)

    # Residue check — a surviving {{TOKEN}} or @flag marker means a
    # template bug or a typo'd marker; surface it rather than shipping
    # placeholder text into a fresh repo.
    residue: list[dict] = []
    leftover_token = re.compile(r"\{\{[A-Z_]+\}\}")
    leftover_flag = re.compile(r"@(end)?flag\s+[A-Za-z0-9_-]+")
    for rel in written:
        f = target / rel
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits = leftover_token.findall(text) + leftover_flag.findall(text)
        if hits:
            residue.append({"file": rel, "hits": len(hits)})

    return {
        "tokens": tokens,
        "files_written": written,
        "files_excluded": excluded,
        "flag_lines_removed": flag_lines_removed,
        "residue": residue,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the greenfield spine template into TARGET.",
        epilog="Modules: core(always) rules tests db auth billing email redis sentry seo docs deploy",
    )
    parser.add_argument("target", nargs="?", default=".", help="Target directory (must be empty or nonexistent unless --force)")
    parser.add_argument("--name", help="Project display name (default: target dir name)")
    parser.add_argument("--site-url", default="http://localhost:3000", help="Canonical site URL")
    parser.add_argument("--skip", action="append", default=[], metavar="MODULE", help="Disable a module (repeatable)")
    parser.add_argument("--minimal", action="store_true", help="Core + rules + tests only")
    parser.add_argument("--force", action="store_true", help="Allow scaffolding into a non-empty directory")
    parser.add_argument("--dry-run", action="store_true", help="Compute the plan without writing files")
    parser.add_argument("--status", action="store_true", help="Report existing scaffold state in TARGET (.scaffold-report.json + key files) and exit")
    parser.add_argument("--init-env", action="store_true", help="Create TARGET/.env from .env.example (if absent) with a generated BETTER_AUTH_SECRET, then exit")
    parser.add_argument("-o", "--output", help="Write JSON report to file instead of stdout")
    parser.add_argument("--verbose", action="store_true", help="Diagnostics to stderr")
    args = parser.parse_args()

    try:
        flags = load_json(FLAGS_FILE)
        versions = load_json(VERSIONS_FILE)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot load assets: {e}", file=sys.stderr)
        return 2

    target = Path(args.target).resolve()

    if args.status:
        state_file = target / ".scaffold-report.json"
        prior = None
        if state_file.exists():
            try:
                prior = json.loads(state_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                prior = {"error": "unparseable .scaffold-report.json"}
        key_files = {
            p: (target / p).exists()
            for p in ("package.json", "nuxt.config.ts", "bun.lock",
                      "node_modules", ".env", ".git", ".nuxt")
        }
        verify_status = (prior or {}).get("verify", {}).get("status")
        _emit({
            "script": "scaffold",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "pass" if prior else "warning",
            "target": str(target),
            "prior_report": prior,
            "key_files": key_files,
            "verify_status": verify_status,
            "resume_hint": (
                "scaffold rendered" if (target / "package.json").exists()
                and not (target / "node_modules").exists()
                else "run full scaffold" if not (target / "package.json").exists()
                else "verify passed — done" if verify_status == "pass"
                else "verify failed — inspect .scaffold-report.json"
                if verify_status == "fail"
                else "scaffold + install done — verify next"
            ),
        }, args.output)
        return 0

    if args.init_env:
        example = target / ".env.example"
        env_file = target / ".env"
        result = {"script": "scaffold", "action": "init-env", "target": str(target)}
        if env_file.exists():
            result.update(status="skipped", reason=".env already exists")
        elif not example.exists():
            result.update(status="fail", reason="no .env.example in target")
        else:
            import secrets
            content = example.read_text(encoding="utf-8").replace(
                "generate-a-long-random-string", secrets.token_hex(32)
            )
            env_file.write_text(content, encoding="utf-8")
            result.update(status="pass", reason=".env created with generated BETTER_AUTH_SECRET")
        _emit(result, args.output)
        return 0 if result["status"] != "fail" else 1

    name = args.name or target.name.replace("-", " ").replace("_", " ").title()

    enabled, auto_disabled, warnings = resolve_modules(flags, set(args.skip), args.minimal)

    report = {
        "script": "scaffold",
        "version": "1.0.0",
        "skill_path": str(SKILL_DIR),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "target": str(target),
        "dry_run": args.dry_run,
        "modules": {
            "enabled": sorted(enabled | {"core"}),
            "disabled": sorted(set(flags["modules"]) - enabled - {"core"}),
            "auto_disabled": sorted(auto_disabled),
        },
        "warnings": warnings,
        "result": None,
    }

    non_empty = target.exists() and any(target.iterdir())
    if non_empty and not args.force:
        report["status"] = "fail"
        report["warnings"].append(
            f"target '{target}' is not empty — pass --force to scaffold anyway"
        )
        _emit(report, args.output)
        return 1

    if args.dry_run:
        _emit(report, args.output)
        return 0

    try:
        target.mkdir(parents=True, exist_ok=True)
        report["result"] = scaffold(target, name, args.site_url, enabled, flags, versions, args.verbose)
        if report["result"]["residue"]:
            report["status"] = "warning"
            report["warnings"].append(
                f"{len(report['result']['residue'])} file(s) contain unrendered tokens/flag markers"
            )
    except OSError as e:
        print(f"error: scaffold failed: {e}", file=sys.stderr)
        return 2

    # State artifact — lets a later session/pipeline resume from state
    # (--status reads it back; verify appends its results alongside).
    try:
        (target / ".scaffold-report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    except OSError as e:
        print(f"warning: could not write .scaffold-report.json: {e}", file=sys.stderr)

    _emit(report, args.output)
    return 0


def _emit(report: dict, output: str | None) -> None:
    payload = json.dumps(report, indent=2)
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    sys.exit(main())
