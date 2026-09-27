// Optional large-graph browser check. Start Orbita and set ORBITA_URL as needed.
const { chromium } = require(process.env.ORBITA_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const origin = process.env.ORBITA_URL || 'http://127.0.0.1:8787';
const artifacts = path.join(__dirname, 'artifacts');

(async () => {
  await fs.mkdir(artifacts, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.ORBITA_CHROME ? { executablePath: process.env.ORBITA_CHROME } : {}),
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(160000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const ready = () => page.locator('#workspace[aria-busy="false"]').waitFor();
  try {
    await page.goto(origin);
    await ready();
    await page.locator('.nav-items [data-view="data"]').click();
    await page.locator('[data-action="load-demo"][data-demo="facebook-large"]').click();
    await ready();

    assert.match(await page.locator('.stat-card').first().innerText(), /1.?812/u);
    assert.equal(await page.locator('.graph-scope').count(), 1);
    assert.ok(await page.locator('.graph-node').count() <= 900);
    assert.ok(await page.locator('.graph-edge').count() <= 3500);

    await page.locator('[data-action="graph-scope"][data-scope="source"]').click();
    await page.locator('.graph-scope [data-scope="source"].active').waitFor();
    await page.locator('[data-action="fit-graph"]').click();
    await page.waitForTimeout(250);
    const nodes = await page.locator('.graph-node').count();
    const edges = await page.locator('.graph-edge').count();
    const status = await page.locator('#graph-render-status').innerText();
    const detail = await page.locator('#graph-render-status').getAttribute('title');
    assert.ok(nodes > 0 && nodes <= 900, `Некорректное число отрисованных вершин: ${nodes}`);
    assert.ok(edges > 0 && edges <= 3500, `Некорректное число отрисованных рёбер: ${edges}`);
    assert.match(status, /приблизьте/u);
    assert.match(detail, /3.?963/u);
    await page.screenshot({ path: path.join(artifacts, 'large-source-desktop.png'), fullPage: true });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(250);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const mobileNodes = await page.locator('.graph-node').count();
    assert.ok(mobileNodes > 0 && mobileNodes <= 900);
    await page.screenshot({ path: path.join(artifacts, 'large-source-mobile.png'), fullPage: true });
    assert.deepEqual(errors, []);
    console.log(`PASS: large graph; SVG ${nodes} nodes / ${edges} edges; ${status}`);
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
