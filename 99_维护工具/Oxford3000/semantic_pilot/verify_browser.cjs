/* Real MP3, card navigation and translation checks in a local browser. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {fileURLToPath, pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

const dir = path.resolve(__dirname, '../../../_exports/Oxford3000_雅思语义试点');
const url = pathToFileURL(path.join(dir, '雅思语义试点.html')).href;
const {cards, stats} = JSON.parse(fs.readFileSync(path.join(dir, '统计与出处.json'), 'utf8'));
const positionKey = 'oxford3000-ielts-semantic-pilot-position';
const originalKey = 'oxford3000-pdf-position';

async function show(page, word) {
  const entry = cards.find(card => card.word === word);
  await page.evaluate(id => { location.hash = '#word-' + id; }, entry.id);
  await page.getByRole('heading', {name: word, exact: true}).waitFor();
  await page.waitForFunction(start => {
    const player = document.getElementById('audio');
    return player.readyState > 0 && !player.seeking && Math.abs(player.currentTime - start) < .08;
  }, entry.audio.start);
}

async function single(page, control, word) {
  const cue = cards.find(card => card.word === word).audio;
  await page.locator(control).click();
  await page.getByRole('heading', {name: word, exact: true}).waitFor();
  await page.waitForFunction(spokenEnd => {
    const audio = document.getElementById('audio');
    return audio.paused && Math.abs(audio.currentTime - spokenEnd) < .085 &&
      document.getElementById('status').textContent.includes('本条已播完');
  }, cue.spokenEnd, {timeout: 6000});
  await page.waitForTimeout(250);
  assert.equal(await page.locator('.word-heading').textContent(), word);
  assert.equal(await page.locator('#audio').evaluate(element => element.paused), true);
}

async function main() {
  const systemChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const executablePath = process.env.CHROME_PATH || (fs.existsSync(systemChrome) ? systemChrome : undefined);
  const browser = await chromium.launch({headless: true, executablePath});
  const report = {browser: browser.version(), checks: [], pageErrors: []};
  try {
    const page = await browser.newPage({viewport: {width: 1120, height: 980}});
    page.on('pageerror', error => report.pageErrors.push(error.message));
    await page.goto(url);
    await page.waitForFunction(() => document.getElementById('audio').readyState > 0);
    const duration = await page.locator('#audio').evaluate(element => element.duration);
    assert.ok(Math.abs(duration - stats.durationSeconds) < .15, String(duration));
    report.checks.push('real MP3 loaded; duration matches the cue sheet');
    assert.deepEqual(await page.locator('.entry').allTextContents(), cards.map(card => card.word));
    for (const word of cards) {
      await show(page, word.word);
      assert.equal(await page.locator('article.card').count(), 1);
      assert.equal(await page.locator('.sense[open]').count(), 1);
      assert.deepEqual(
        await page.locator('.sense').evaluateAll(items => items.map(item => item.dataset.sense)),
        word.groups.flatMap(group => group.senses.map(sense => sense.id)),
      );
    }
    report.checks.push('30 unique cards; all POS and sense groups render in ranked order');
    await page.locator('#search').fill('lives');
    assert.deepEqual(await page.locator('.entry').allTextContents(), ['life']);
    await page.locator('#search').clear();
    report.checks.push('search recognises an attested inflected form');

    await show(page, 'level');
    const collapsed = page.locator('[data-sense="level.degree"]');
    assert.equal(await collapsed.getAttribute('open'), null);
    await collapsed.locator(':scope > summary').click();
    assert.notEqual(await collapsed.getAttribute('open'), null);
    const source = page.locator('[data-sense="level.rank"] figcaption a');
    assert.equal(await source.getAttribute('href'), '来源/L05.pdf#page=1');
    assert.ok(fs.existsSync(fileURLToPath(new URL(await source.getAttribute('href'), url))));
    assert.equal(await page.locator('[data-sense="level.rank"] mark').textContent(), 'levels of importance');
    report.checks.push('additional senses fold and expand; example highlights its actual span and links to the source PDF');
    await collapsed.locator(':scope > summary').click();
    await page.mouse.move(0, 0);
    const gloss = page.locator('[data-sense="level.rank"] .translation-text');
    assert.equal(await gloss.evaluate(element => getComputedStyle(element).visibility), 'hidden');
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.locator('.word-heading').hover();
    assert.equal(await gloss.evaluate(element => getComputedStyle(element).visibility), 'visible');
    await page.screenshot({path: path.join(dir, 'level_桌面预览.png')});
    report.checks.push('Chinese gloss is hidden by default and revealed on hover');

    await show(page, 'book');
    await page.evaluate(key => localStorage.setItem(key, '321'), originalKey);
    await page.locator('#speed').selectOption('1.25');
    assert.equal(await page.locator('#audio').evaluate(element => element.playbackRate), 1.25);
    await single(page, '#nextWord', 'change');
    const box = await page.locator('#audio').boundingBox();
    await page.mouse.click(box.x + 20, box.y + box.height / 2);
    await page.waitForFunction(() => !document.getElementById('audio').paused);
    await page.getByRole('heading', {name: 'condition', exact: true}).waitFor({timeout: 6500});
    await single(page, '#prevWord', 'change');
    await single(page, '#replay', 'change');
    report.checks.push('rate, single next and previous, replay, native play and continuous card following');
    const target = cards.find(card => card.word === 'course');
    await page.locator('#audio').evaluate((element, start) => { element.currentTime = start + .07; }, target.audio.start);
    await page.waitForFunction(() => !document.getElementById('audio').paused);
    await page.getByRole('heading', {name: 'course', exact: true}).waitFor();
    await page.locator('#audio').evaluate(element => element.pause());
    const saved = await page.evaluate(key => Number(localStorage.getItem(key)), positionKey);
    assert.ok(saved >= target.audio.start && saved < target.audio.end);
    await page.reload();
    await page.locator('#resume').click();
    await page.waitForFunction(() => !document.getElementById('audio').paused);
    await page.getByRole('heading', {name: 'course', exact: true}).waitFor();
    assert.equal(await page.evaluate(key => localStorage.getItem(key), originalKey), '321');
    report.checks.push('timeline seeking resumes continuous mode; resume uses a separate saved position');
    await page.close();

    const phone = await browser.newPage({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
    phone.on('pageerror', error => report.pageErrors.push(error.message));
    await phone.goto(url);
    await show(phone, 'level');
    const phoneGloss = phone.locator('[data-sense="level.rank"] .translation-text');
    assert.equal(await phoneGloss.evaluate(element => getComputedStyle(element).visibility), 'hidden');
    await phone.getByLabel('显示中文').check();
    assert.equal(await phoneGloss.evaluate(element => getComputedStyle(element).visibility), 'visible');
    await show(phone, 'life');
    assert.equal(await phone.locator('.sense[open] .translation-text')
      .evaluate(element => getComputedStyle(element).visibility), 'visible');
    await show(phone, 'level');
    assert.equal(await phone.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await phone.screenshot({path: path.join(dir, 'level_触屏预览.png')});
    report.checks.push('390 px touch layout, translation toggle and persistence between cards');
    assert.deepEqual(report.pageErrors, []);
    report.checks.push('no browser script errors');
    report.status = 'pass';
  } catch (error) {
    report.status = 'fail';
    report.failure = error.stack;
    throw error;
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(dir, '浏览器校验.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify(report, null, 2));
  }
}

main().catch(error => {
  console.error(error.stack);
  process.exitCode = 1;
});
