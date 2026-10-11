import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:net';
import path from 'node:path';
import { chromium } from '@playwright/test';

// Exercise real decision persistence against a disposable SQLite backup.
const root = process.cwd();
const dataDir = path.join(root, '.local', 'studio-test-' + Date.now());
execFileSync(path.join(root, '.venv/bin/python'), ['-c',
  'import pathlib,sqlite3,sys; p=pathlib.Path(sys.argv[2]); p.mkdir(parents=True); src=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); dst=sqlite3.connect(p/"cockpit.sqlite"); src.backup(dst); dst.close(); src.close()',
  path.join(root, '.local/cockpit.sqlite'), dataDir]);
const socket = createServer(); socket.listen(0, '127.0.0.1'); await once(socket, 'listening');
const port = socket.address().port; await new Promise(resolve => socket.close(resolve));
const apiUrl = `http://127.0.0.1:${port}`;
const backend = spawn(path.join(root, '.venv/bin/python'), ['-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', String(port)], {
  cwd: root, env: {...process.env, BMWPM_DATA_DIR: dataDir, BMWPM_DATABASE_URL: `sqlite:///${dataDir}/cockpit.sqlite`}, stdio: 'ignore',
});
let browser;
try {
  let ready = false;
  for (let i = 0; i < 50; i++) {
    try { ready = (await fetch(apiUrl + '/api/v1/health')).ok; } catch {}
    if (ready) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(ready, 'Disposable API starts');
  browser = await chromium.launch({executablePath: path.join(root, '.local/browser-cache/chromium-1248/chrome-linux64/chrome'), headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  page.setDefaultTimeout(15000);
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url());
    const response = await route.fetch({url: apiUrl + url.pathname + url.search});
    await route.fulfill({response});
  });
  await page.goto('http://127.0.0.1:3001/studio.html');
  console.log('Studio opened');
  await page.waitForFunction(() => document.querySelector('#k-total')?.textContent === '216');
  assert.equal(await page.locator('#k-evidence').textContent(), '3610');
  assert.equal(await page.locator('#sources a').count(), 4);
  console.log('Live data loaded');
  await page.locator('#search').fill('touch screen');
  assert.ok(await page.locator('#requirements [data-id]').count() > 0);
  await page.locator('#search').fill('');
  await page.locator('#requirements [data-id]').first().click();
  const id = await page.locator('#requirements [data-id]').first().getAttribute('data-id');
  console.log('Selected requirement', id);
  page.once('dialog', dialog => dialog.accept('Browser rehearsal verifies persistent decisions.'));
  await page.getByRole('button', {name: 'Approve', exact: true}).click();
  console.log('Approval submitted');
  await page.waitForFunction(id => document.querySelector(`[data-id="${id}"] .status-approved`), id);
  await page.reload();
  await page.waitForFunction(id => document.querySelector(`[data-id="${id}"] .status-approved`), id);
  assert.ok((await page.locator('#audit').textContent()).includes('Browser rehearsal'));
  await page.locator('#country').selectOption('GB');
  await page.waitForFunction(() => document.querySelector('#status')?.textContent.includes('Decisions save') && document.querySelector('#k-evidence')?.textContent !== '3610');
  await page.locator('#country').selectOption('US');
  await page.waitForFunction(() => document.querySelector('#k-evidence')?.textContent === '3610');
  await page.screenshot({path: path.join(dataDir, 'studio.png'), fullPage: true});
  assert.deepEqual(errors, []);
  console.log('Passed: live data, search, approval persistence, audit, market filters, browser errors. Screenshot: ' + path.join(dataDir, 'studio.png'));
} finally {
  await browser?.close();
  backend.kill('SIGTERM');
}
