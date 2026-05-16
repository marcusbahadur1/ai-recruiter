#!/usr/bin/env bash
# run-tests.sh — autonomous test runner
# Runs claude with --dangerously-skip-permissions, auto-restarts on session end,
# stops when TESTING_COMPLETE is found in the test plan.

set -euo pipefail

PLAN="docs/task-management/TEST_PLAN.md"
PROMPT="Find where we left off in the test plan at ${PLAN} and work through all remaining ⬜ items autonomously. For each test item: if a Playwright test already exists in e2e/tests/modules/ run it using the modules config; if not, write a new Playwright test following existing patterns and run it. Simulate a real human tester — click through flows, fill forms, validate what appears on screen against the live app at https://app.airecruiterz.com. If a test fails due to a bug, attempt to fix it and retest before moving on. After each test completes, immediately update the test plan with pass/fail, reason, and timestamp. After all tests in a section are done, clear context and move to the next section. When every single test is complete, write TESTING_COMPLETE to the test plan and output a full summary report. Never wait — work entirely autonomously from start to finish."

echo "=== run-tests.sh started at $(date) ==="

while true; do
  # Check if already complete
  if grep -q "TESTING_COMPLETE" "${PLAN}" 2>/dev/null; then
    echo "=== TESTING_COMPLETE found — stopping. ==="
    exit 0
  fi

  echo "--- Starting claude session at $(date) ---"
  claude --dangerously-skip-permissions -p "${PROMPT}" || true

  # Check again after session ends
  if grep -q "TESTING_COMPLETE" "${PLAN}" 2>/dev/null; then
    echo "=== TESTING_COMPLETE found — stopping. ==="
    exit 0
  fi

  echo "--- Session ended. Restarting in 3s... ---"
  sleep 3
done
