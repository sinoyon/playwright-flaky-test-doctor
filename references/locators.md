# Locators

## Priority

| Rank | Locator | Use when | Example |
|---|---|---|---|
| 1 | `getByRole(role, { name })` | Almost always: buttons, links, headings, textboxes, checkboxes, rows, dialogs | `page.getByRole('button', { name: 'Sign in' })` |
| 2 | `getByLabel` | Form fields with a `<label>` or `aria-label` | `page.getByLabel('Email')` |
| 3 | `getByPlaceholder` | Inputs with no label | `page.getByPlaceholder('Search products')` |
| 4 | `getByText` | Non-interactive text (messages, paragraphs) | `page.getByText('Order confirmed')` |
| 5 | `getByAltText` / `getByTitle` | Images, icon-only elements with title | `page.getByAltText('Company logo')` |
| 6 | `getByTestId` | No accessible name, or text changes by locale | `page.getByTestId('cart-count')` |
| 7 | CSS | Nothing else works — use a stable attribute | `page.locator('[data-state="open"]')` |

Never: XPath, positional CSS (`:nth-child`, `div > div > a`), generated class names (`.css-1x2y3z`, `.sc-abc123`), or `.first()/.nth()` used to paper over an ambiguous locator.

## Exact vs. partial names

`name` matches as a case-insensitive substring by default. `{ name: 'Save' }` also matches "Save draft". Use `exact: true` when two names overlap:

```ts
page.getByRole('button', { name: 'Save', exact: true })
```

Regex for dynamic text: `page.getByRole('heading', { name: /^Welcome, / })`.

## Narrowing (scoping) instead of indexing

When the same button appears many times, scope to its container:

```ts
const row = page.getByRole('row').filter({ hasText: 'Invoice #1042' });
await row.getByRole('button', { name: 'Download' }).click();

const card = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Pro plan' }) });
await card.getByRole('button', { name: 'Choose' }).click();
```

## Tricky cases

**Tables** — `page.getByRole('row', { name: /Alice/ })` then `getByRole('cell')`. Assert counts with `await expect(page.getByRole('row')).toHaveCount(n + 1)` (header row included).

**Selects** — `await page.getByLabel('Country').selectOption('Malaysia')`. Custom dropdowns (div-based): click the trigger (`getByRole('combobox')`), then `getByRole('option', { name: 'Malaysia' })`.

**Checkbox / radio** — `.check()` / `.uncheck()`, assert with `toBeChecked()`.

**Iframes** — `page.frameLocator('iframe[title="Payment"]').getByLabel('Card number')`.

**Shadow DOM** — Playwright's role/text/CSS locators pierce open shadow roots automatically. No special syntax needed.

**New tab / popup**
```ts
const popupPromise = page.waitForEvent('popup');
await page.getByRole('link', { name: 'Open docs' }).click();
const popup = await popupPromise;
await expect(popup).toHaveURL(/docs/);
```

**File upload** — `await page.getByLabel('Upload').setInputFiles('fixtures/file.pdf')`.

**Download**
```ts
const downloadPromise = page.waitForEvent('download');
await page.getByRole('button', { name: 'Export CSV' }).click();
const download = await downloadPromise;
expect(download.suggestedFilename()).toMatch(/\.csv$/);
```

**Toasts that disappear** — assert immediately after the action; web-first assertions retry until timeout, so a toast visible for ~2 s is caught.

**Icon-only buttons with no name** — this is an accessibility bug in the app. Use `getByTestId` or `getByTitle`, and mention to the user that adding an `aria-label` would help both users and tests.

## If the app is missing accessible names

Tell the user once, briefly: adding `aria-label` / `<label>` / `data-testid` makes tests far more stable. Do not refuse to write the test — use the most stable attribute available.
