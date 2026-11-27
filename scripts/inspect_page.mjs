#!/usr/bin/env node
// List the interactive elements on a page with a recommended, VERIFIED Playwright locator.
// Every locator printed has been checked to match exactly one element on the live page.
//
// Usage:
//   node inspect_page.mjs <url> [--storage-state auth.json] [--json]
//                         [--fill "Label=value"] [--click "Name"] [--wait-for "Text"] ...
//
// The --fill / --click / --wait-for steps run in order, so you can walk to a deeper page, e.g.
//   node inspect_page.mjs http://localhost:3000/login --fill "Email=$E2E_EMAIL" \
//     --fill "Password=$E2E_PASSWORD" --click "Sign in" --wait-for "Dashboard"
//
// Run it from the project folder so it can find the project's Playwright install
// (@playwright/test or playwright).

import { createRequire } from 'node:module';
import path from 'node:path';

const args = process.argv.slice(2);
const url = args.find(a => !a.startsWith('--') && !isOptValue(a));
function isOptValue(a) {
  const i = args.indexOf(a);
  return i > 0 && ['--storage-state', '--wait-for', '--fill', '--click'].includes(args[i - 1]);
}
function opt(name) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : undefined;
}
if (!url) {
  console.error('Usage: node inspect_page.mjs <url> [--storage-state auth.json] [--json] [--fill "Label=value"] [--click "Name"] [--wait-for "Text"] ...');
  process.exit(2);
}

const require = createRequire(path.join(process.cwd(), 'noop.js'));
let chromium;
for (const mod of ['@playwright/test', 'playwright']) {
  try { ({ chromium } = require(mod)); break; } catch {}
}
if (!chromium) {
  console.error('Playwright not found. Run from your project folder after: npm i -D @playwright/test && npx playwright install chromium');
  process.exit(2);
}

let browser;
try { browser = await chromium.launch(); }
catch { browser = await chromium.launch({ channel: 'chrome' }); } // fall back to installed Chrome

const context = await browser.newContext(opt('--storage-state') ? { storageState: opt('--storage-state') } : {});
const page = await context.newPage();
await page.goto(url, { waitUntil: 'domcontentloaded' });

// Optional steps to reach a deeper page, run in the order given on the command line:
//   --fill "Label=value"   fills the field with that label (or placeholder)
//   --click "Name"         clicks the button/link with that accessible name (or that text)
//   --wait-for "Text"      waits until that text is visible
for (let i = 0; i < args.length; i++) {
  const [flag, val] = [args[i], args[i + 1]];
  if (flag === '--fill') {
    const eq = val.indexOf('='); const label = val.slice(0, eq); const value = val.slice(eq + 1);
    const byLabel = page.getByLabel(label, { exact: true });
    await ((await byLabel.count()) ? byLabel : page.getByPlaceholder(label, { exact: true })).first().fill(value);
  } else if (flag === '--click') {
    // Prefer a button, then a link, then any element with that exact text.
    const options = [
      page.getByRole('button', { name: val, exact: true }),
      page.getByRole('link', { name: val, exact: true }),
      page.getByText(val, { exact: true }),
    ];
    let target = options[0];
    for (const o of options) { if (await o.count()) { target = o; break; } }
    await target.first().click();
  } else if (flag === '--wait-for') {
    await page.getByText(val).first().waitFor();
  }
}
if (!args.includes('--wait-for')) await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

// Collect raw facts about each visible interactive element in the page.
const raw = await page.evaluate(() => {
  const SEL = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=link],[role=checkbox],[role=radio],[role=tab],[role=menuitem],[role=option],[role=combobox],[role=switch],[role=textbox],[contenteditable=""],[contenteditable=true],[data-testid]';
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const implicitRole = el => {
    const t = el.tagName.toLowerCase(); const type = (el.getAttribute('type') || 'text').toLowerCase();
    if (t === 'a') return 'link';
    if (t === 'button' || t === 'summary') return 'button';
    if (t === 'textarea') return 'textbox';
    if (t === 'select') return el.multiple || el.size > 1 ? 'listbox' : 'combobox';
    if (t === 'input') {
      if (['button', 'submit', 'reset', 'image'].includes(type)) return 'button';
      if (type === 'checkbox') return 'checkbox';
      if (type === 'radio') return 'radio';
      if (type === 'range') return 'slider';
      if (type === 'number') return 'spinbutton';
      if (type === 'search') return 'searchbox';
      if (['text', 'email', 'tel', 'url'].includes(type)) return el.getAttribute('list') ? 'combobox' : 'textbox';
      return null; // password, date, file, color... have no textbox role
    }
    return null;
  };
  const labelText = el => {
    if (el.labels && el.labels.length) return clean([...el.labels].map(l => l.innerText).join(' '));
    const by = el.getAttribute('aria-labelledby');
    if (by) return clean(by.split(/\s+/).map(id => document.getElementById(id)?.innerText || '').join(' '));
    return clean(el.getAttribute('aria-label'));
  };
  const out = [];
  document.querySelectorAll(SEL).forEach(el => {
    if (!visible(el)) return;
    const tag = el.tagName.toLowerCase();
    const isField = ['input', 'select', 'textarea'].includes(tag);
    const ownText = isField ? '' : clean(el.innerText);
    out.push({
      tag,
      type: el.getAttribute('type') || '',
      role: el.getAttribute('role') || implicitRole(el),
      label: labelText(el),
      text: ownText.slice(0, 80),
      value: tag === 'input' && ['button', 'submit', 'reset'].includes(el.type) ? clean(el.value) : '',
      alt: clean(el.getAttribute('alt') || el.querySelector?.('img[alt]')?.getAttribute('alt')),
      title: clean(el.getAttribute('title')),
      placeholder: clean(el.getAttribute('placeholder')),
      testid: el.getAttribute('data-testid') || '',
    });
  });
  return out;
});

const q = s => JSON.stringify(s).replace(/^"|"$/g, '').replace(/'/g, "\\'");
async function unique(make) { try { return (await make().count()) === 1; } catch { return false; } }

// Try candidates in Playwright's recommended priority; keep the first that resolves to exactly 1 element.
const results = [];
for (const el of raw) {
  const name = el.label || el.text || el.value || el.alt || el.title;
  const cands = [];
  if (el.role && name) {
    cands.push([`getByRole('${el.role}', { name: '${q(name)}', exact: true })`, () => page.getByRole(el.role, { name, exact: true })]);
  }
  if (el.label) cands.push([`getByLabel('${q(el.label)}', { exact: true })`, () => page.getByLabel(el.label, { exact: true })]);
  if (el.placeholder) cands.push([`getByPlaceholder('${q(el.placeholder)}', { exact: true })`, () => page.getByPlaceholder(el.placeholder, { exact: true })]);
  if (el.testid) cands.push([`getByTestId('${q(el.testid)}')`, () => page.getByTestId(el.testid)]);
  if (el.text && !el.role) cands.push([`getByText('${q(el.text)}', { exact: true })`, () => page.getByText(el.text, { exact: true })]);

  let locator = null;
  for (const [code, make] of cands) { if (await unique(make)) { locator = `page.${code}`; break; } }
  const what = `${el.role || el.tag}${el.type && el.tag === 'input' ? `[${el.type}]` : ''}`;
  results.push({ element: what, name: name || el.placeholder || el.testid || '', locator, needsScoping: !locator && cands.length > 0 });
}

// De-duplicate identical rows (same element matched by several selectors).
const seen = new Set();
const rows = results.filter(r => { const k = `${r.element}|${r.name}|${r.locator}`; if (seen.has(k)) return false; seen.add(k); return true; });

if (args.includes('--json')) {
  console.log(JSON.stringify({ url: page.url(), title: await page.title(), elements: rows }, null, 2));
} else {
  console.log(`# ${await page.title()} — ${page.url()}\n`);
  for (const r of rows) {
    const loc = r.locator ?? (r.needsScoping ? '⚠ not unique — scope to a container (row/card/dialog) with .filter()' : '⚠ no accessible name — ask for aria-label or data-testid');
    console.log(`${r.element.padEnd(18)} ${(`"${r.name}"`).padEnd(32)} ${loc}`);
  }
  console.log(`\n${rows.filter(r => r.locator).length}/${rows.length} elements have a verified unique locator.`);
}
await browser.close();
