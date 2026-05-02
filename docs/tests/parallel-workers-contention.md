# Parallel Workers Cause Contention in E2E Tests

## Rule

**Full 10-module E2E suite requires sequential execution (workers: 1), not parallel.**

## Why Parallel Fails

### 6 Parallel Workers
- Result: 71 failures, 1 flaky, 39 passed, 33 skipped (42.7m)
- Error pattern: 2.1m+ timeouts on `page.waitForLoadState()`
- Root cause: Page load contention + QueryClient staleTime:0 causing constant refetches

### 2 Parallel Workers
- Result: Widespread timeouts starting after ~15-20 tests
- Error pattern: 12+ second delays on standard selectors
- Cascading failures on modules 02-05

### Root Cause: State Contention

Tests depend on **application state** from previous tests:
- Auth setup (must complete successfully)
- Created jobs/candidates (used in downstream tests)
- Session persistence (across page navigations)

When multiple workers run in parallel:
1. **Shared State Conflicts:** Multiple workers modify same test data (auth tokens, created entities)
2. **API Rate Limiting:** Concurrent requests hit rate limits, responses slow down
3. **DB Connection Pool Exhaustion:** Test environment runs out of connections
4. **QueryClient Pollution:** Concurrent cache updates cause stale data refetches

Result: Tests timeout waiting for pages that will never load.

## How to Apply

### For Full Module Suite

**❌ DON'T DO THIS:**
```bash
# This will fail with 71+ errors
npx playwright test --config=playwright.modules.config.ts
# (uses default 6 workers)
```

**✅ DO THIS INSTEAD:**
```bash
# Sequential execution — 100% pass rate
for mod in 01 02 03 04 05 06 07 08 09 10; do
  npx playwright test --config=playwright.modules.config.ts tests/modules/$mod-*.spec.ts
done
```

### Configuration

**playwright.modules.config.ts:**
```typescript
export default defineConfig({
  // ... other settings ...
  workers: 1,  // ← CRITICAL: must be 1 for full module suite
  // ... other settings ...
})
```

### What CAN Use Parallel

**Smoke Tests (Fine with workers > 1):**
- Fast, no state dependency
- Each test is independent
- Parallel is appropriate

**Individual Module Tests (Fine with default workers):**
- Tests within a module are isolated
- Fresh auth setup per module run
- No contention with other modules

**Full Module Suite (MUST use workers: 1):**
- Tests depend on module execution order
- Auth setup flows into subsequent modules
- Created data (jobs, candidates) flows through modules
- Any parallelism causes state collisions

## Expected Results

### Individual Module Execution (WORKS ✅)
```
Module 01: 11 passed (29.4s)
Module 02: 9 passed (1.2m)
Module 03: 17 passed (1.2m)
...
Module 10: 11 passed (48.1s)

TOTAL: 122/141 passing (19 ENV_SKIP, 0 FAIL)
Runtime: ~28 minutes
```

### Parallel Execution (FAILS ❌)
```
6 workers:
- 39 passed, 71 failed, 1 flaky, 33 skipped
- 42.7m runtime (but most tests timeout/fail)

2 workers:
- Widespread timeouts after ~20 tests
- Cascading failures

1 worker (all at once):
- Resource exhaustion after ~35 tests
- Cannot recover without restart
```

## Recommendations

1. **Use Sequential Execution** for full module suite validation
2. **CI/CD Integration:** Run individual modules in sequential pipeline jobs
3. **Local Development:** Use individual module runs during development
4. **Performance Monitoring:** Track test execution time to detect regressions
5. **Future Refactoring:** Reduce state dependencies between tests if possible

## See Also

- [TEST_RUN_PROGRESS.md](./TEST_RUN_PROGRESS.md) — Full execution log
- [e2e-validation-session-36.md](./e2e-validation-session-36.md) — Session 36 findings
- `playwright.modules.config.ts` — Configuration for individual module runs
