# Playwright Flaky Test Doctor: free agent skill

Fix flaky Playwright tests at the root cause, and stop AI agents from "fixing" tests by testing less.

> "checkout.spec.ts fails randomly in CI."
>
> → Your agent reruns it 25 times: **12% failure rate (3/25), always at step "Search for mugs"**, error `toHaveCount expected 2, received 3`. Likely cause: state not settled (it searched before the product list loaded). It fixes the cause and reruns: **0/25 failures, 0 weakened assertions.**

## What your agent gets

| Script | What it does |
|---|---|
| `flaky_report.py` | Reads Playwright's JSON report from repeated runs and shows the failure rate per test, the `test.step` where it breaks, grouped errors and the **likely root cause** |
| `assertion_diff.py` | Reviews any test change, including those from Playwright's healer agent or other AI tools, and flags removed or loosened assertions, new sleeps, `force`, skips and swallowed errors |
| `lint_spec.py` | Catches 14 brittle patterns in TS, JS and Python specs |
| `inspect_page.mjs` | Prints the live page's elements with Playwright locators verified to match exactly one element |

It also gives your agent a workflow (measure → lint → diagnose → fix → prove) and a root-cause table for the common types of flakiness.

## Works with

Claude Code, Codex, OpenClaw and other agents that support `SKILL.md` skills. Playwright Test (TS/JS) and pytest-playwright. It complements Playwright's built-in planner, generator and healer agents by reviewing and stabilizing what they produce.

## Install

Copy the `playwright-flaky-test-doctor` folder into your agent's skills folder (Claude Code: `~/.claude/skills/`).

## Use

- "This test fails randomly in CI, fix it properly: tests/cart.spec.ts"
- "The healer changed our tests. Did it weaken anything?"
- "Write a stable Playwright test for signup → verify email banner → logout."

## Try it without an app

```bash
python3 scripts/flaky_report.py examples/demo-shop/flaky-report.json
python3 scripts/assertion_diff.py examples/demo-shop/checkout.flaky.spec.ts examples/demo-shop/checkout.fixed.spec.ts
```

---
Made by **shariful Labs**. More agent skills for AI engineers (MCP Server Builder, LLM Eval Builder): https://mcpmarket.com/sellers/shariful-labs
