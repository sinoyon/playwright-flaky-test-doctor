import { test, expect } from '@playwright/test';

// Flow: "Sign in, search for mugs, add the Blue Mug to the cart, check out, and see the order confirmation."
// Requires env: E2E_EMAIL, E2E_PASSWORD

test('signed-in user can buy the Blue Mug and sees an order confirmation', async ({ page }) => {
  await test.step('Sign in', async () => {
    await page.goto('/');
    await page.getByRole('textbox', { name: 'Email' }).fill(process.env.E2E_EMAIL!);
    await page.getByLabel('Password').fill(process.env.E2E_PASSWORD!);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Shop' })).toBeVisible();
  });

  await test.step('Search for mugs', async () => {
    await page.getByPlaceholder('Search products').fill('mug');
    await expect(page.getByRole('article')).toHaveCount(2);
  });

  const blueMug = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Blue Mug' }) });

  await test.step('Add the Blue Mug to the cart', async () => {
    await blueMug.getByRole('button', { name: 'Add to cart' }).click();
    await expect(page.getByRole('link', { name: 'Cart (1)' })).toBeVisible();
  });

  await test.step('Review the cart and place the order', async () => {
    await page.getByRole('link', { name: 'Cart (1)' }).click();
    await expect(page.getByRole('listitem')).toHaveText(['Blue Mug — RM 12']);
    await expect(page.getByText('Total: RM 12')).toBeVisible();
    await page.getByRole('button', { name: 'Place order' }).click();
  });

  await test.step('Order is confirmed', async () => {
    await expect(page.getByRole('heading', { name: 'Thank you for your order' })).toBeVisible();
    await expect(page).toHaveURL(/\/orders\/\d+$/);
  });
});

test('sign-in is rejected with a short password', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox', { name: 'Email' }).fill('someone@example.test');
  await page.getByLabel('Password').fill('123'); // lint-ok: intentionally invalid password
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toHaveText('Invalid email or password');
  await expect(page.getByRole('heading', { name: 'Shop' })).toBeHidden();
});
