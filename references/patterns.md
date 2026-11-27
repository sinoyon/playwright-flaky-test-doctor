# Patterns

## Log in once, reuse the session

Logging in through the UI in every test is slow and a common flake source. Use a setup project that saves `storageState`:

```ts
// tests/auth.setup.ts
import { test as setup, expect } from '@playwright/test';
const authFile = 'playwright/.auth/user.json';

setup('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(process.env.E2E_EMAIL!);
  await page.getByLabel('Password').fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await page.context().storageState({ path: authFile });
});
```

```ts
// playwright.config.ts (projects)
projects: [
  { name: 'setup', testMatch: /.*\.setup\.ts/ },
  { name: 'chromium', use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/user.json' }, dependencies: ['setup'] },
],
```

Add `playwright/.auth/` to `.gitignore`. Keep one UI login test that covers the login flow itself.

## Seed data through the API, not the UI

```ts
test.beforeEach(async ({ request }) => {
  const res = await request.post('/api/products', { data: { name: `Mug ${Date.now()}`, price: 12 } });
  expect(res.ok()).toBeTruthy();
});
```

## Waiting on the network (instead of sleeping)

```ts
const saved = page.waitForResponse(r => r.url().includes('/api/profile') && r.request().method() === 'PUT');
await page.getByRole('button', { name: 'Save' }).click();
expect((await saved).ok()).toBeTruthy();
```

Start waiting **before** the action that triggers the request.

## Mocking an API

Use when the backend is slow, third-party, or hard to put into a state (errors, empty lists):

```ts
await page.route('**/api/recommendations', route =>
  route.fulfill({ status: 200, json: [{ id: 1, title: 'Mocked item' }] }));
await page.route('**/api/checkout', route => route.fulfill({ status: 500 }));
```

Say in the test name or a comment that the API is mocked.

## Page objects — only when they earn it

Use a page object when the same page is driven by 3+ tests. For one test, inline locators are clearer.

```ts
export class LoginPage {
  constructor(private page: Page) {}
  email = () => this.page.getByLabel('Email');
  password = () => this.page.getByLabel('Password');
  submit = () => this.page.getByRole('button', { name: 'Sign in' });
  async login(email: string, password: string) {
    await this.email().fill(email);
    await this.password().fill(password);
    await this.submit().click();
  }
}
```

## Fixing flaky tests

Reproduce first: `npx playwright test spec --repeat-each=10 --workers=4`. Then match the symptom:

| Symptom | Usual cause | Fix |
|---|---|---|
| Passes alone, fails in suite | Shared state between tests | Independent data per test; reset in `beforeEach` |
| Search/filter results wrong (e.g. expected 2, got 3) intermittently | Typed before the initial list finished loading; the late initial load overwrote the filtered results | Assert the initial list first (`toHaveCount(3)`), then type |
| Element "not visible"/"detached" intermittently | Re-render after data load | Assert the loaded state first (`await expect(list).toHaveCount(3)`) then act |
| Click does nothing sometimes | Clicked before hydration / handler attached | Wait for a ready signal (heading, enabled button: `toBeEnabled()`), not a sleep |
| Text assertion fails with old value | Reading value with `textContent()` + `expect(...).toBe` | Use web-first `await expect(locator).toHaveText(...)` |
| "strict mode violation: resolved to 2 elements" | Ambiguous locator | Scope to a container or use `exact: true` — not `.first()` |
| Fails only in CI | Slower machine, different viewport/timezone/locale | Set `viewport`, `timezoneId`, `locale` in config; never rely on timing |
| Fails around midnight / month end | Date-dependent data | Fix the clock: `await page.clock.setFixedTime(new Date('2026-01-15T10:00:00'))` |
| Animations interfere | Element moving during click | Usually auto-handled; otherwise assert final state before clicking |

Replace `waitForTimeout(n)` with the condition it was really waiting for. Ask: "what did the developer expect to have happened after n ms?" — assert that.

## Python (pytest-playwright) mapping

| TypeScript | Python |
|---|---|
| `test('name', async ({ page }) => {...})` | `def test_name(page: Page):` |
| `page.getByRole('button', { name: 'Save' })` | `page.get_by_role("button", name="Save")` |
| `getByLabel` / `getByText` / `getByTestId` | `get_by_label` / `get_by_text` / `get_by_test_id` |
| `await expect(loc).toBeVisible()` | `expect(loc).to_be_visible()` |
| `toHaveText` / `toHaveURL` / `toHaveCount` | `to_have_text` / `to_have_url` / `to_have_count` |
| `test.step('x', async () => {...})` | no built-in; use clear comments or `allure.step` if the project uses Allure |
| `page.waitForResponse(fn)` | `with page.expect_response(fn) as r: ...` |
| `process.env.X` | `os.environ["X"]` |

```python
import os, re
from playwright.sync_api import Page, expect

def test_user_can_sign_in(page: Page):
    page.goto("/login")
    page.get_by_label("Email").fill(os.environ["E2E_EMAIL"])
    page.get_by_label("Password").fill(os.environ["E2E_PASSWORD"])
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(re.compile(r"/dashboard"))
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
```
