---
name: playwright-flaky-test-doctor
description: Diagnose and fix flaky, slow, or broken Playwright end-to-end tests at the root cause, and review test changes made by AI agents (including Playwright's own planner, generator, and healer agents) for weakened assertions. Use when a Playwright test fails randomly or only in CI, passes only on retry, when the user asks to stabilize, de-flake, or review E2E tests, or to write a new stable Playwright test from a plain-English flow. Works with TypeScript, JavaScript, and Python (pytest-playwright).
---

# Playwright Flaky Test Doctor

Goal: tests that **pass, keep passing, and still test what they claim to test**. A flaky test is fixed when its root cause is gone and repeat runs prove it, not when a retry or a sleep hides it.

Two rules that apply everywhere:
- **Measure before and after.** "It passed once" proves nothing about a flaky test.
- **Never make a test pass by testing less.** No added sleeps, `force: true`, `.skip`, swallowed errors, or loosened assertions, whether you or another agent made the change.

## 1. Reproduce and measure

```bash
npx playwright test <spec or folder> --repeat-each=20 --workers=4 --retries=0 --reporter=json > flaky.json
python3 scripts/flaky_report.py flaky.json
```
The report lists each unstable test with its failure rate, the **test.step where it breaks**, each distinct error with its count, and the **likely cause** for each error pattern: state not settled, ambiguous locator, element covered, re-render, element never appeared, network/backend, shared test data, or test ended early.

- If nothing fails, raise the load (`--repeat-each=50`, more `--workers`), run headless like CI, or try the CI `--project`. Flakes often appear only under parallel load.
- From CI: download the JSON report artifact and run the same script on it.
- Python: `pytest --count=20 -n 4` (pytest-repeat, pytest-xdist) and read the failures. The script reads Playwright's JSON reporter only.

## 2. Lint for known flaky patterns

```bash
python3 scripts/lint_spec.py <spec or folder>
```
Flags 14 brittle patterns, including fixed sleeps, XPath, `.only`, non-retrying asserts (`expect(await x.textContent())`), hardcoded secrets, `force`, positional CSS, generated class names, `networkidle`, and tests with no assertion. A finding on the failing line is usually the cause.

## 3. Diagnose the root cause

Combine the report's likely cause, the failing step and the lint findings, then confirm with one trace:
```bash
npx playwright test <spec> --repeat-each=20 --trace=retain-on-failure && npx playwright show-trace test-results/**/trace.zip
```
Match the symptom in `references/patterns.md` → "Fixing flaky tests". The most common causes, in order: acting before data has loaded, ambiguous locators, shared state between tests, overlays or animations, and real app bugs (race conditions in the app itself).

**If the app is wrong, say so.** A test that fails 10% of the time because the app has a race condition has found a bug. Report it to the user with the evidence; don't "fix" the test around it.

## 4. Fix the cause

- Wait on **conditions**: web-first assertions (`await expect(locator).toHaveCount(3)`), `waitForURL`, `waitForResponse`. Never a sleep.
- Make locators unambiguous: scope with `.filter({ has / hasText })` or use `exact: true`. Get real names from the page with `node scripts/inspect_page.mjs <url>`, which prints verified-unique locators and can walk through steps with `--fill`, `--click` and `--wait-for`.
- Isolate data: unique values per test, API seeding in `beforeEach`, and a fixed clock (`page.clock`) for dates.
- Remove overlays and animations from the path by asserting they are hidden first.
- Keep every existing assertion unless it was genuinely wrong. Explain any you change.

## 5. Prove it

```bash
npx playwright test <spec> --repeat-each=20 --workers=4 --retries=0 --reporter=json > after.json
python3 scripts/flaky_report.py after.json        # must report 0 unstable
python3 scripts/assertion_diff.py --git <spec>    # must report 0 weakening changes
```
If the before/after runs can't be done in your environment (the app is unreachable), say so and give the user these exact commands. Never claim a flaky test is fixed without the repeat run.

## Reviewing changes from other agents (including Playwright's healer)

AI agents, including Playwright's healer, fix failing tests quickly, but sometimes by loosening them. Before accepting any AI-made test change:
```bash
python3 scripts/assertion_diff.py --git tests/cart.spec.ts        # or: assertion_diff.py old.spec.ts new.spec.ts
python3 scripts/lint_spec.py tests/cart.spec.ts
```
`assertion_diff.py` flags removed assertions, a dropping assertion count, `toHaveText` → `toContainText`, removed `exact: true`, new sleeps, `force`, skips, swallowed errors, and index picks. Treat `WEAKENED` as a reject unless the old assertion was wrong, and explain why. A locator-only change that keeps every assertion is usually fine.

## Writing a new test

When the user wants a new test instead of a fix:
1. Get real locators with `scripts/inspect_page.mjs` (never invent selectors), or read the app source.
2. Write it in the project's language and style, using `templates/example.spec.ts` as the style reference: `test.step` per user step, role/label locators, web-first assertions, secrets from env vars. Copy `templates/playwright.config.ts` if there's no config yet.
3. Run it, then do steps 2 and 5 above. A new test is done when it passes 20/20 repeats with 0 lint errors.

## Report back

- **Before → after**, for example: `checkout.spec.ts: 12% failure (3/25 runs) → 0/25`.
- The root cause in one sentence, and the fix.
- Any app bug found (with evidence), and anything you couldn't verify.

## Bundled files

| File | Use |
|---|---|
| `scripts/flaky_report.py` | Playwright JSON report → failure rate, failing step, grouped errors, likely cause per test |
| `scripts/assertion_diff.py` | Detects test changes that weaken coverage (works on files or `--git`) |
| `scripts/lint_spec.py` | Flags 14 flaky/brittle patterns in TS, JS and Python specs |
| `scripts/inspect_page.mjs` | Lists a live page's interactive elements with verified-unique locators |
| `references/patterns.md` | Root-cause table for flaky tests, auth reuse, API seeding, mocking, Python mapping |
| `references/locators.md` | Locator priority and tricky cases (tables, iframes, popups, downloads) |
| `templates/` | Config and style reference spec |
| `examples/demo-shop/` | A real flaky test (failed 3 of 25 runs), its report, and the fixed test (0 of 25) |
