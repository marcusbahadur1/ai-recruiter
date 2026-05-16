#!/usr/bin/env bash
# Root-level wrapper — delegates to e2e/run-full-test.sh
# Usage: ./run-tests.sh [--smoke-only] [--skip-pipelines] [--from N]
set -euo pipefail
cd "$(dirname "$0")/e2e"
exec ./run-full-test.sh "$@"
