#!/usr/bin/env bash
# Pre-push validation — the cheap gate before code leaves the machine.
# Typecheck + unit tests; the full build is CI's job.
# Every command runs under a hard timeout: a check that prints success
# but never exits (leaked handle) must fail the push loudly, not stall it.
set -e

run() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$1" "${@:2}"
  else
    echo "warning: timeout not found — running unbounded" >&2
    "${@:2}"
  fi
}

echo "==> type-check"
run 600 bun run type-check

# @flag tests
echo "==> unit tests"
run 600 bun run test:run
# @endflag tests
