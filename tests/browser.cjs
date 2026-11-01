const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  try {
    for (const viewport of [{width:390,height:844},{width:1280,height:900}]) {
      const page = await browser.newPage({viewport});
      const errors=[];page.on('pageerror', e=>errors.push(e.message));
      await page.goto('http://127.0.0.1:18088/login');
      await page.locator('#password').fill('ci-password-12345');
      await page.getByRole('button',{name:'Anmelden',exact:true}).click();
      await page.waitForURL('http://127.0.0.1:18088/');
      await page.getByRole('button',{name:'Scan',exact:true}).click();
      await page.locator('#targets').waitFor({state:'visible'});
      await page.getByRole('button',{name:'Admin',exact:true}).click();
      await page.locator('#settings').waitFor({state:'visible'});
      await page.locator('select[name="theme"]').selectOption('light');
      await page.locator('#settings button').click();
      await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
      await page.getByRole('button',{name:'Index',exact:true}).click();
      await page.locator('#search').fill('NAS');
      if(errors.length)throw Error(errors.join('\n'));
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Horizontal viewport overflow');
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1);});
