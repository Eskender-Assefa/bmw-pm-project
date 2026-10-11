import { test, expect } from '@playwright/test';

test('comments workspace navigation, filters, pagination and source inspection', async ({ page }) => {
  await page.goto('/');
  const nav = page.locator('nav');
  const buttons = await nav.getByRole('button').allTextContents();
  expect(buttons).toEqual(expect.arrayContaining(['Reviews & Comments', 'Document intelligence', '3D model', 'Decisions & audit']));
  await nav.getByRole('button', { name: 'Reviews & Comments', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Reviews & Comments', level: 1 })).toBeVisible();
  await expect(page.locator('.review-comment').first()).toBeVisible();
  const firstId = await page.locator('.review-comment h3').first().textContent();
  await page.getByRole('button', { name: 'Next comments page' }).click();
  await expect(page.locator('.review-comment h3').first()).not.toHaveText(firstId!);
  await page.getByRole('button', { name: 'Previous comments page' }).click();
  await expect(page.locator('.review-comment h3').first()).toHaveText(firstId!);
  await page.getByRole('button', { name: 'View original', exact: true }).first().click();
  await expect(page.getByRole('dialog', { name: 'Original evidence', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close dialog', exact: true }).click();
  await page.getByLabel('Search reviews and comments').fill('no-such-comment-7b1f9a');
  await expect(page.getByRole('heading', { name: 'No comments match this view' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters', exact: true }).first().click();
  await expect(page.locator('.review-comment').first()).toBeVisible();
  await page.getByLabel('Comment category', { exact: true }).selectOption('C07');
  await expect(page.locator('.review-comment').first()).toBeVisible();
  await expect(page.locator('.review-comment-tags').first()).toContainText('C07');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(nav.getByRole('button', { name: 'Reviews & Comments', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
