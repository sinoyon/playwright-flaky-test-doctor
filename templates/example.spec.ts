import { test, expect } from '@playwright/test';

// Flow: "Sign in, add the Blue Mug to the cart, check out, see the order confirmation."
// Requires env: E2E_EMAIL, E2E_PASSWORD

test('signed-in user can buy a product and sees the order confirmation', async ({ page }) => {
  await test.step('Sign in', async () => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(process.env.E2E_EMAIL!);
    await page.getByLabel('Password').fill(process.env.E2E_PASSWORD!);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Shop' })).toBeVisible();
  });

  await test.step('Add the Blue Mug to the cart', async () => {
    const product = page.getByRole('article').filter({ hasText: 'Blue Mug' });
    await product.getByRole('button', { name: 'Add to cart' }).click();
    await expect(page.getByRole('link', { name: /Cart \(1\)/ })).toBeVisible();
  });

  await test.step('Check out', async () => {
    await page.getByRole('link', { name: /Cart/ }).click();
    await page.getByRole('button', { name: 'Place order' }).click();
  });

  await test.step('Order is confirmed', async () => {
    await expect(page).toHaveURL(/\/orders\/\d+/);
    await expect(page.getByRole('heading', { name: 'Thank you for your order' })).toBeVisible();
  });
});
