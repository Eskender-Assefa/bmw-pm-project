import { test, expect } from '@playwright/test';

test('Reddit collection form safely submits inputs and presents the completed handoff', async ({ page }) => {
  const key = 'sk-test-only-not-a-real-api-key';
  let job: Record<string, unknown> | null = null;
  let submitted = 0;
  await page.route('**/api/v1/reddit/runs', async route => {
    if (route.request().method() === 'POST') {
      submitted++;
      expect(route.request().postDataJSON()).toEqual({ api_key: key, model: 'F70', count: 5 });
      job = { id: 'test-run', kind: 'reddit_pipeline', input: { model: 'F70', count: 5 }, state: 'running', progress: '1 / 3 · Collecting Reddit quotations', error: null, result: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
      await route.fulfill({ status: 202, json: job });
    } else {
      if (job && job.state === 'running') {
        job = { ...job, state: 'succeeded', progress: 'Imported 2 categorized comments · visible in Reviews & Comments', result: { requested: 5, collected: 3, categorized: 2, discarded: 1, shortfall: 2, model: 'F70', ready_for_import: true, imported_source_id: 'mock-source', artifacts: Object.fromEntries(['categorized.jsonl', 'input.jsonl', 'manifest.json', 'import-bundle.zip'].map(name => [name, '/api/v1/reddit/runs/test-run/files/' + name])) } };
      }
      await route.fulfill({ json: job ? [job] : [] });
    }
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Reviews & Comments', exact: true }).click();
  const keyField = page.getByLabel('OpenAI API key', { exact: true });
  await expect(keyField).toHaveAttribute('type', 'password');
  await page.screenshot({ path: '.local/reddit-form-desktop.png' });
  await keyField.fill(key);
  await page.getByLabel('Reddit car model').selectOption('F70');
  await page.getByLabel('Reddit comment count').fill('0');
  await page.getByRole('button', { name: 'Collect & categorize' }).click();
  await expect(page.getByRole('region', { name: 'Reddit comment collection' }).getByRole('alert')).toContainText('whole number');
  expect(submitted).toBe(0);
  await page.getByLabel('Reddit comment count').fill('5');
  await page.getByRole('button', { name: 'Collect & categorize' }).click();
  await expect(keyField).toHaveValue('');
  await expect(page.getByRole('link', { name: 'categorized.jsonl', exact: true })).toBeVisible();
  await expect(page.getByText('collection shortfall', { exact: false })).toBeVisible();
  expect(submitted).toBe(1);
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }))).not.toContain(key);
  await expect(page.getByRole('combobox', { name: 'Model', exact: true })).toHaveValue('F70');
  await expect(page.getByRole('combobox', { name: 'Market', exact: true })).toHaveValue('all');
  await expect(page.getByRole('button', { name: 'View imported comments' })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
