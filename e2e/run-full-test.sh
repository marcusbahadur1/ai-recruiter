#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run-full-test.sh — Master production readiness test
#
# Runs the complete test suite against production (https://app.airecruiterz.com).
# When all groups pass, the system is confirmed READY FOR LIVE.
#
# Groups (run sequentially — a group failure stops subsequent groups):
#   Group 1: Production smoke test     smoke.spec.ts            ~3 min   47 checks
#   Group 2: Module suite 01–10        playwright.modules        ~15 min  standard UI + API
#   Group 3: Pipeline modules 11–12    playwright.modules        ~20 min  Scout + Screener E2E
#   Group 4: New tenant E2E            module 13                 ~25 min  full lifecycle
#
# Total estimated runtime: 60–70 minutes (pipeline polls dominate).
#
# Usage:
#   ./run-full-test.sh                   Run all groups
#   ./run-full-test.sh --smoke-only      Group 1 only (quick health check)
#   ./run-full-test.sh --skip-pipelines  Groups 1 + 2 only (no long pipeline polls)
#   ./run-full-test.sh --from 3          Start from group 3
#
# Output:
#   Console: live test output with pass/fail per test
#   File:    e2e/results/full-test-YYYYMMDD-HHMMSS.txt
#
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail
cd "$(dirname "$0")"

# ── Args ──────────────────────────────────────────────────────────────────────

SMOKE_ONLY=false
SKIP_PIPELINES=false
FROM_GROUP=1

for arg in "$@"; do
  case "$arg" in
    --smoke-only)      SMOKE_ONLY=true ;;
    --skip-pipelines)  SKIP_PIPELINES=true ;;
    --from)            shift; FROM_GROUP="${1:-1}" ;;
    --from=*)          FROM_GROUP="${arg#--from=}" ;;
  esac
done

# ── Setup ─────────────────────────────────────────────────────────────────────

mkdir -p results
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
REPORT="results/full-test-${TIMESTAMP}.txt"
START_TIME=$(date +%s)

# ── Colour codes ──────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ── Logging ───────────────────────────────────────────────────────────────────

log() { echo -e "$1" | tee -a "$REPORT"; }

# ── State ─────────────────────────────────────────────────────────────────────

GROUPS_RUN=0
GROUPS_PASSED=0
GROUPS_FAILED=0
FAILED_GROUPS=()

# ── Helper: run a playwright command and record pass/fail ──────────────────────

run_group() {
  local group_num="$1"
  local group_name="$2"
  shift 2
  local pw_cmd=("$@")

  if [[ "$group_num" -lt "$FROM_GROUP" ]]; then
    log "${YELLOW}⏭  Group ${group_num} — ${group_name} — SKIPPED (--from ${FROM_GROUP})${RESET}"
    return 0
  fi

  log ""
  log "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  log "${CYAN}${BOLD}  Group ${group_num}: ${group_name}${RESET}"
  log "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  log "  Command: ${pw_cmd[*]}"
  log "  Started: $(date)"
  log ""

  GROUPS_RUN=$((GROUPS_RUN + 1))
  local group_start=$(date +%s)

  # Run playwright — always capture output to file, also stream to console
  if "${pw_cmd[@]}" 2>&1 | tee -a "$REPORT"; then
    local group_end=$(date +%s)
    local elapsed=$((group_end - group_start))
    GROUPS_PASSED=$((GROUPS_PASSED + 1))
    log ""
    log "${GREEN}  ✅  Group ${group_num} PASSED (${elapsed}s)${RESET}"
    return 0
  else
    local group_end=$(date +%s)
    local elapsed=$((group_end - group_start))
    GROUPS_FAILED=$((GROUPS_FAILED + 1))
    FAILED_GROUPS+=("$group_name")
    log ""
    log "${RED}  ❌  Group ${group_num} FAILED (${elapsed}s)${RESET}"
    return 1
  fi
}

# ── Header ────────────────────────────────────────────────────────────────────

log ""
log "${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
log "${BOLD}║          AIRecruiterz — Full Production Readiness Test              ║${RESET}"
log "${BOLD}║          Target: https://app.airecruiterz.com                       ║${RESET}"
log "${BOLD}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
log "  Started  : $(date)"
log "  Report   : ${REPORT}"
log "  Smoke only: ${SMOKE_ONLY}"
log "  Skip pipelines: ${SKIP_PIPELINES}"
log "  From group: ${FROM_GROUP}"
log ""

# ── Group 1: Smoke test ───────────────────────────────────────────────────────

if ! run_group 1 "Production Smoke Test (47 checks)" \
  npx playwright test \
    --config=playwright.production.config.ts \
    "tests/production/smoke.spec.ts" \
    --workers=1 \
    --reporter=list; then
  log ""
  log "${RED}${BOLD}Group 1 (smoke) failed — environment may be down. Stopping.${RESET}"
  exit 1
fi

[[ "$SMOKE_ONLY" == "true" ]] && { log "\n--smoke-only: stopping after Group 1."; true; } && exit 0

# ── Group 2: Module suite 01–10 ───────────────────────────────────────────────

if [[ "$FROM_GROUP" -le 2 ]]; then
  run_group 2 "Module Suite 01–10 (auth, billing, settings, KB, chat, jobs, candidates, apps, marketing, super-admin)" \
    npx playwright test \
      --config=playwright.modules.config.ts \
      --ignore-glob="**/11-scout-pipeline*" \
      --ignore-glob="**/12-screener-pipeline*" \
      --ignore-glob="**/13-new-tenant-e2e*" \
      --workers=1 \
      --reporter=list || true  # non-fatal: continue to pipelines even if some UI tests flake
fi

[[ "$SKIP_PIPELINES" == "true" ]] && {
  log "\n--skip-pipelines: stopping after Group 2."
  exit 0
}

# ── Group 3: Pipeline modules 11–12 ──────────────────────────────────────────

if [[ "$FROM_GROUP" -le 3 ]]; then
  run_group 3 "Scout Pipeline E2E — Module 11 (PL-01–21)" \
    npx playwright test \
      --config=playwright.modules.config.ts \
      "tests/modules/11-scout-pipeline.spec.ts" \
      --workers=1 \
      --reporter=list || true

  run_group 3 "Screener Pipeline E2E — Module 12 (SC-01–25)" \
    npx playwright test \
      --config=playwright.modules.config.ts \
      "tests/modules/12-screener-pipeline.spec.ts" \
      --workers=1 \
      --reporter=list || true
fi

# ── Group 4: New tenant E2E — Module 13 ──────────────────────────────────────

if [[ "$FROM_GROUP" -le 4 ]]; then
  run_group 4 "New Tenant Full E2E — Module 13 (Signup → Quickstart → Scout → Screener)" \
    npx playwright test \
      --config=playwright.modules.config.ts \
      "tests/modules/13-new-tenant-e2e.spec.ts" \
      --workers=1 \
      --reporter=list || true
fi

# ── Summary ───────────────────────────────────────────────────────────────────

END_TIME=$(date +%s)
TOTAL_ELAPSED=$((END_TIME - START_TIME))
TOTAL_MIN=$((TOTAL_ELAPSED / 60))
TOTAL_SEC=$((TOTAL_ELAPSED % 60))

log ""
log "${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
log "${BOLD}║                          FULL TEST SUMMARY                          ║${RESET}"
log "${BOLD}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
log "  Completed : $(date)"
log "  Duration  : ${TOTAL_MIN}m ${TOTAL_SEC}s"
log "  Groups run: ${GROUPS_RUN}"
log "  Passed    : ${GROUPS_PASSED}"
log "  Failed    : ${GROUPS_FAILED}"

if [[ "${#FAILED_GROUPS[@]}" -gt 0 ]]; then
  log ""
  log "${RED}  Failed groups:${RESET}"
  for g in "${FAILED_GROUPS[@]}"; do
    log "${RED}    • ${g}${RESET}"
  done
fi

log ""
if [[ "$GROUPS_FAILED" -eq 0 ]]; then
  log "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
  log "${GREEN}${BOLD}║                                                                      ║${RESET}"
  log "${GREEN}${BOLD}║   ✅  ALL GROUPS PASSED — SYSTEM READY FOR LIVE                      ║${RESET}"
  log "${GREEN}${BOLD}║                                                                      ║${RESET}"
  log "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
  log ""
  log "  Full report: ${REPORT}"
  exit 0
else
  log "${RED}${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
  log "${RED}${BOLD}║                                                                      ║${RESET}"
  log "${RED}${BOLD}║   ❌  ${GROUPS_FAILED} GROUP(S) FAILED — SYSTEM NOT READY                       ║${RESET}"
  log "${RED}${BOLD}║                                                                      ║${RESET}"
  log "${RED}${BOLD}╚══════════════════════════════════════════════════════════════════════╝${RESET}"
  log ""
  log "  Full report: ${REPORT}"
  exit 1
fi
