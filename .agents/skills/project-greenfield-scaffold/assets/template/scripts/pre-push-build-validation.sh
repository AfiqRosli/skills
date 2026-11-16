#!/usr/bin/env bash
# Pre-push validation — the cheap gate before code leaves the machine.
# Typecheck + unit tests; the full build is CI's job.
set -e

echo "==> type-check"
bun run type-check

# @flag tests
echo "==> unit tests"
bun run test:run
# @endflag tests
