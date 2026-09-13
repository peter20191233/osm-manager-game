/* Run with Node + Playwright. PWA_FIXTURES is a JSON export of content.SCENARIOS. */
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const assert = require('node:assert/strict');
const {webkit, chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..', 'dist', 'ios');
const evidence = path.resolve(__dirname, '..', '.publishing', 'pwa-qa');
fs.mkdirSync(evidence, {recursive: true});
const scenarios = JSON.parse(fs.readFileSync(process.env.PWA_FIXTURES, 'utf8'));
const types = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8', '.css':'text/css', '.png':'image/png', '.webmanifest':'application/manifest+json'};
const names = new Set(fs.readdirSync(root));
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const relative = url.pathname.replace(/^\/games\/osm\//, '') || 'index.html';
  if (!url.pathname.startsWith('/games/osm/') || !names.has(relative)) {res.writeHead(404).end(); return;}
  res.setHeader('Content-Type', types[path.extname(relative)] || 'application/octet-stream');
  res.end(fs.readFileSync(path.join(root, relative)));
});
async function ready(page) {
  await page.waitForFunction(() => window.osmReady === true, {timeout:30000});
  await page.locator('#offline-status[data-ready="true"]').waitFor({timeout:30000});
}
async function run(name, browserType, base) {
  // Windows WebKit loses localStorage when its profile path contains Cyrillic.
  const profile = path.join(os.tmpdir(), 'osm-pwa-'+name+'-'+Date.now());
  const options = {headless:true,viewport:{width:390,height:844},hasTouch:true,isMobile:true};
  let context = await browserType.launchPersistentContext(profile, options);
  const version = context.browser().version();
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const requests = [];
  page.on('request', req => { if (/^https?:/.test(req.url()) && !req.url().startsWith(base)) requests.push(req.url()); });
  try {
    await page.goto(base);
    await ready(page);
    assert.equal(await page.locator('.category-button').count(), 6);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.locator('#install-help summary').tap();
    await page.screenshot({path:path.join(evidence, name+'-install.png'),fullPage:true});
    await page.evaluate(async () => {
      const cache = await caches.open('unrelated-site-cache');
      await cache.put('/unrelated-test', new Response('preserve'));
    });
    await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
    if (process.env.PWA_URL) await context.setOffline(true);
    else await new Promise(resolve => server.close(resolve));
    // New page, query string and index.html all have to work from the saved cache.
    await page.close();
    const offline = await context.newPage();
    offline.on('pageerror', e => errors.push(e.message));
    await offline.goto(base + 'index.html?offline-test=1');
    await ready(offline);
    await offline.locator('#next-button').tap();
    await offline.waitForFunction(() => {
      const audio = document.getElementById('background-music');
      return audio.readyState >= 2 && !audio.paused && audio.currentTime > .1;
    }, {timeout:15000});
    assert.ok(await offline.locator('#background-music').evaluate(el => el.duration > 79 && el.loop && el.src.startsWith('data:audio/mpeg;base64,')));
    await offline.locator('#sound-button').tap();
    assert.equal(await offline.locator('#background-music').evaluate(el => el.paused), true);
    await offline.locator('#sound-button').tap();
    await offline.waitForFunction(() => !document.getElementById('background-music').paused);
    let score = 0;
    for (let i=0; i<12; i++) {
      const text = await offline.locator('#client-request').innerText();
      const scenario = scenarios.find(s => s.text === text || '«'+s.text+'»' === text);
      assert.ok(scenario, 'Displayed client must match source content: '+text);
      const category = i % 2 === 0 ? scenario.category : ['accounts','credit'].find(c => c !== scenario.category);
      await offline.locator('#category-'+category).tap();
      score += i % 2 === 0 ? 1 : -1;
      assert.equal(await offline.locator('#score').innerText(), String(score));
      assert.equal(await offline.locator('#served').innerText(), String(i+1));
      if (i === 0) await offline.screenshot({path:path.join(evidence,name+'-offline-game.png'),fullPage:true});
      await offline.locator('#next-button').tap();
    }
    await offline.screenshot({path:path.join(evidence,name+'-result.png'),fullPage:true});
    const saved = await offline.locator('#best-label').innerText();
    assert.equal(saved, 'Рекорд смены: '+score);
    await offline.reload();
    await ready(offline);
    assert.equal(await offline.locator('#best-label').innerText(), saved, 'The record must survive a full offline reload');
    assert.ok(await offline.evaluate(() => caches.has('unrelated-site-cache')));
    await offline.locator('#next-button').tap();
    await offline.locator('#pause-button').tap();
    assert.equal(await offline.locator('#background-music').evaluate(el => el.paused), true);
    const paused = await offline.locator('#patience-label').innerText();
    await offline.waitForTimeout(1200);
    assert.equal(await offline.locator('#patience-label').innerText(), paused);
    await offline.locator('#guide-button').tap();
    assert.equal(await offline.locator('#modal').evaluate(el => el.open), true);
    await offline.locator('#modal-close').tap();
    await offline.setViewportSize({width:844,height:390});
    assert.equal(await offline.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await offline.setViewportSize({width:320,height:568});
    assert.equal(await offline.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    assert.deepEqual(requests, []);
    await context.close();
    context = await browserType.launchPersistentContext(profile, options);
    if (process.env.PWA_URL) await context.setOffline(true);
    const restarted = await context.newPage();
    await restarted.goto(base);
    await ready(restarted);
    assert.equal(await restarted.locator('#best-label').innerText(), saved, 'The record must survive closing the whole browser');
    const result = {browser:name,version,offlineShiftClients:12,score,recordPersisted:true,offlineReload:true,offlineColdStart:true,bundledMusicPlaybackMutePause:true,unrelatedCachePreserved:true,portraitAndLandscape:true,pageErrors:errors};
    fs.writeFileSync(path.join(evidence,name+'.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally { await context.close(); }
}
(async () => {
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const base = process.env.PWA_URL || `http://127.0.0.1:${server.address().port}/games/osm/`;
  try {
    const browsers = {webkit, chromium};
    for (const name of (process.env.PWA_BROWSERS || 'webkit,chromium').split(',')) {
      if (!browsers[name]) throw new Error('Unsupported browser '+name);
      if (!server.listening) await new Promise(resolve => server.listen(Number(new URL(base).port),'127.0.0.1',resolve));
      await run(name,browsers[name],base);
    }
  }
  finally {server.close();}
})().catch(error => { console.error(error); process.exitCode=1; });
