// Full end-to-end check for the bundled 10,000-vertex example.
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
    await page.locator('[data-action="load-demo"][data-demo="social-10000"]').click();
    await ready();

    assert.match(await page.locator('.stat-card').first().innerText(), /10.?000/u);
    assert.match(await page.locator('.stat-card').nth(2).innerText(), /91/u);
    assert.equal(await page.locator('#root-select').evaluate(element => element.tagName), 'INPUT');
    const coverage = await page.locator('.pair-coverage').innerText();
    assert.match(coverage, /все 10.?000 вершин/iu);
    assert.match(coverage, /49.?995.?000 возможных пар/iu);
    assert.match(coverage, /подробного расчёта[^—]+— 91/iu);
    assert.match(coverage, /0,67–1,00/u);

    await page.locator('[data-action="fit-graph"]').click();
    await page.waitForTimeout(300);
    const nodes = await page.locator('.graph-node').count();
    const edges = await page.locator('.graph-edge').count();
    assert.ok(nodes > 0 && nodes <= 900, `Некорректное число SVG-вершин: ${nodes}`);
    assert.ok(edges >= 0 && edges <= 3500, `Некорректное число SVG-рёбер: ${edges}`);
    assert.match(await page.locator('#graph-render-status').innerText(), /приблизьте/u);
    await page.screenshot({ path: path.join(artifacts, 'social-10000-desktop.png'), fullPage: true });

    await page.locator('.nav-items [data-view="candidates"]').click();
    assert.equal(await page.locator('tr[data-pair]').count(), 20);
    assert.match(await page.locator('#workspace').innerText(), /Точная копия u00199/u);
    assert.match(await page.locator('#workspace').innerText(), /Смежный двойник A · 8 общих соседей/u);
    await page.screenshot({ path: path.join(artifacts, 'social-10000-candidates.png'), fullPage: true });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.nav-items [data-view="graph"]').click();
    await page.waitForTimeout(300);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.ok((await page.locator('.graph-node').count()) <= 900);
    await page.screenshot({ path: path.join(artifacts, 'social-10000-mobile.png'), fullPage: true });
    assert.deepEqual(errors, []);
    console.log(`PASS: 10,000 vertices analyzed; 91 varied candidates; 49,995,000 pairs covered; SVG ${nodes} nodes / ${edges} edges.`);
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
