const { chromium } = require('playwright');
const assert = require('node:assert/strict');

async function waitForTheme(page, expected) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    if (await page.locator('html').getAttribute('data-theme') === expected) return;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw Error('Theme did not change to ' + expected);
}

(async () => {
  const browser = await chromium.launch();
  try {
    for (const viewport of [{width:390,height:844},{width:1280,height:900}]) {
      const context = await browser.newContext({viewport, bypassCSP:false});
      const page = await context.newPage();
      const errors=[];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto('http://127.0.0.1:18088/login');
      await page.locator('#password').fill('ci-password-12345');
      await page.getByRole('button',{name:'Anmelden',exact:true}).click();
      await page.waitForURL('http://127.0.0.1:18088/');
      await page.getByRole('button',{name:'Scan',exact:true}).click();
      await page.locator('#targets').waitFor({state:'visible'});
      await page.getByRole('button',{name:'Admin',exact:true}).click();
      await page.locator('#settings').waitFor({state:'visible'});
      const current = await page.locator('html').getAttribute('data-theme');
      const target = current === 'light' ? 'dark' : 'light';
      await page.locator('select[name="theme"]').selectOption(target);
      const saved = page.waitForResponse(response =>
        new URL(response.url()).pathname === '/api/settings' &&
        response.request().method() === 'POST'
      );
      await page.locator('#settings button').click();
      assert.equal((await saved).status(), 200, 'Settings save failed');
      await waitForTheme(page, target);
      await page.getByRole('button',{name:'Index',exact:true}).click();
      await page.locator('#search').fill('NAS');
      const cdp = await context.newCDPSession(page);
      const metrics = await cdp.send('Page.getLayoutMetrics');
      const contentWidth = (metrics.cssContentSize || metrics.contentSize).width;
      assert.ok(contentWidth <= viewport.width + 1, 'Horizontal viewport overflow');
      await cdp.detach();
      assert.deepEqual(errors, [], 'Unexpected browser JavaScript errors');
      await context.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
