/* Verify the same portable HTML distributed in the Windows/macOS ZIP. */
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const assert = require('node:assert/strict');
const browsers = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const scenarios = JSON.parse(fs.readFileSync(process.env.PWA_FIXTURES, 'utf8'));
const source = path.resolve(__dirname, '..', 'dist', 'Играть.html');
const url = pathToFileURL(source).href;
const evidence = path.resolve(__dirname, '..', '.publishing', 'pwa-qa');
fs.mkdirSync(evidence, {recursive:true});

async function run(name) {
  assert.ok(['webkit', 'chromium'].includes(name), 'Unsupported browser '+name);
  const browser = await browsers[name].launch({headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1280,height:900},offline:true});
    const page = await context.newPage();
    const errors = [];
    const dependencies = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.url() !== url && !request.url().startsWith('data:')) dependencies.push(request.url());
    });
    await page.goto(url);
    await page.waitForFunction(() => window.osmReady === true, null, {timeout:30000});
    assert.equal(await page.locator('.category-button').count(), 6);
    await page.locator('#next-button').click();
    const text = await page.locator('#client-request').innerText();
    const scenario = scenarios.find(item => text === '«'+item.text+'»');
    assert.ok(scenario, 'The client request must come from the current source content');
    await page.locator('#category-'+scenario.category).click();
    assert.equal(await page.locator('#score').innerText(), '1');
    assert.equal(await page.locator('#served').innerText(), '1');
    const ticket = await page.locator('#flying-ticket').innerText();
    assert.match(ticket, /^[АКВНСП]-001$/, 'The first ticket must have a Cyrillic prefix');
    assert.ok((await page.locator('#printer-label').innerText()).startsWith('Талон '+ticket+' · '));
    await page.screenshot({path:path.join(evidence,name+'-standalone.png'),fullPage:true});
    await page.locator('#next-button').click();
    assert.equal(await page.locator('#client-name').innerText().then(value => value.endsWith('КЛИЕНТ 02')), true);
    assert.deepEqual(errors, []);
    assert.deepEqual(dependencies, [], 'The HTML must not load any external files or network resources');
    const result = {browser:name,version:browser.version(),platform:process.platform,standaloneFile:true,offline:true,correctAnswer:true,ticket,nextClient:true,pageErrors:errors,externalDependencies:dependencies};
    fs.writeFileSync(path.join(evidence,name+'-standalone.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
}

(async () => {
  for (const name of (process.env.PWA_BROWSERS || 'webkit,chromium').split(',')) await run(name);
})().catch(error => { console.error(error); process.exitCode=1; });
