/* Functional checks against the actual local page and audio, including file://. */
const fs=require('fs'),path=require('path'),crypto=require('crypto'),{pathToFileURL}=require('url');
const fallback='C:/Users/Max/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright';
let chromium;try{({chromium}=require('playwright'))}catch{({chromium}=require(fallback))}
const root=path.resolve(__dirname,'..'),rows=JSON.parse(fs.readFileSync(path.join(root,'data/vocabulary.json'),'utf8'));
const base=process.env.PLAYER_BASE_URL||'http://127.0.0.1:8767/',url=base+encodeURIComponent('连续听读.html');
const result={checked_at:new Date().toISOString(),html_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'连续听读.html'))).digest('hex'),checks:{},page_errors:[]};
const check=(ok,name)=>{if(!ok)throw Error(name);result.checks[name]='pass'};
async function main(){
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  result.browser=await browser.version();
  const context=await browser.newContext({viewport:{width:1100,height:1120}}),page=await context.newPage();
  page.on('pageerror',e=>result.page_errors.push(e.message));
  await page.goto(url);await page.waitForFunction(()=>document.getElementById('audio').readyState>=1);
  check(await page.locator('#position').innerText()==='1 / 750','initial_entry');
  check(Math.abs(await page.locator('#audio').evaluate(a=>a.duration)-rows[749].audio.end)<.15,'audio_metadata');
  const range=await context.request.get(base+encodeURI('audio/OxfordPhraseList_连续听读.mp3'),{headers:{Range:'bytes=1000-1999'}});
  check(range.status()===206&&(await range.body()).length===1000,'http_range_206');
  await page.selectOption('#level','C1');check((await page.locator('#count').innerText()).startsWith('75 条'),'level_filter');
  await page.fill('#search','750');check(await page.locator('.entry').count()===1,'id_search');
  await page.locator('.entry').click();await page.waitForFunction(()=>!document.getElementById('audio').paused);
  check((await page.locator('#position').innerText())==='750 / 750','seek_last_entry');await page.locator('#audio').evaluate(a=>a.pause());
  await page.selectOption('#level','');await page.fill('#search','期待');check(await page.locator('.entry[data-index="475"]').count()===1,'chinese_search');
  await page.fill('#search','look forward');await page.locator('.entry[data-index="475"]').click();
  await page.waitForFunction(t=>Math.abs(document.getElementById('audio').currentTime-t)<1,rows[475].audio.start);
  await page.locator('#audio').evaluate(a=>a.pause());check((await page.locator('.phrase').innerText())==='look forward to sth','english_search_and_seek');
  check((await page.locator('#card').innerText()).includes('期待')&&(await page.locator('#card').innerText()).includes('seeing'),'bilingual_content');
  await page.selectOption('#speed','1.25');check(await page.locator('#audio').evaluate(a=>a.playbackRate)===1.25,'speed_control');
  await page.click('#prevPhrase');await page.locator('#audio').evaluate(a=>a.pause());check((await page.locator('#position').innerText())==='475 / 750','previous_control');
  await page.click('#nextPhrase');await page.locator('#audio').evaluate(a=>a.pause());check((await page.locator('#position').innerText())==='476 / 750','next_control');
  await page.locator('#audio').evaluate(a=>{a.currentTime+=.5});await page.click('#replay');await page.locator('#audio').evaluate(a=>a.pause());
  check(Math.abs(await page.locator('#audio').evaluate(a=>a.currentTime)-rows[475].audio.start)<.4,'replay_control');
  await page.selectOption('#speed','1');
  await page.locator('#audio').evaluate((a,t)=>{a.currentTime=t-.18;return a.play()},rows[475].audio.start);
  await page.waitForFunction(()=>document.getElementById('position').textContent==='476 / 750');
  check(await page.locator('#audio').evaluate(a=>!a.paused),'continuous_boundary_and_highlight');await page.locator('#audio').evaluate(a=>a.pause());
  await page.screenshot({path:path.join(root,'_cache/player-desktop.png')});
  const target=rows[449].audio.start+.2;
  await page.evaluate(t=>localStorage.setItem('oxford-phrase-list-pdf-v1-position',String(t)),target);
  await page.click('#resume');await page.waitForFunction(t=>Math.abs(document.getElementById('audio').currentTime-t)<1,target);
  check((await page.locator('#position').innerText())==='450 / 750','resume_progress');await page.locator('#audio').evaluate(a=>a.pause());
  await page.goto(url+'#phrase-700');await page.waitForFunction(()=>document.getElementById('audio').readyState>=1);
  await page.waitForFunction(t=>Math.abs(document.getElementById('audio').currentTime-t)<.2,rows[699].audio.start);
  check((await page.locator('#position').innerText())==='700 / 750','deep_link_before_metadata');
  await page.fill('#search','');await page.selectOption('#level','');await page.click('#nextPage');check((await page.locator('#count').innerText()).includes('第 2 /'),'pagination');
  const mobile=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1,isMobile:true,hasTouch:true});
  const phone=await mobile.newPage();phone.on('pageerror',e=>result.page_errors.push(e.message));
  await phone.goto(url+'#phrase-440');await phone.waitForFunction(()=>document.getElementById('audio').readyState>=1);
  check(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile_no_horizontal_overflow');
  await phone.screenshot({path:path.join(root,'_cache/player-mobile.png')});
  await phone.click('#replay');await phone.waitForFunction(()=>!document.getElementById('audio').paused);check(true,'mobile_playback_emulation');await phone.locator('#audio').evaluate(a=>a.pause());
  const offline=await context.newPage();offline.on('pageerror',e=>result.page_errors.push(e.message));
  await offline.goto(pathToFileURL(path.join(root,'连续听读.html')).href+'#phrase-742');
  await offline.waitForFunction(()=>document.getElementById('audio').readyState>=1);
  await offline.waitForFunction(t=>Math.abs(document.getElementById('audio').currentTime-t)<.2,rows[741].audio.start);
  await offline.click('#replay');await offline.waitForFunction(()=>!document.getElementById('audio').paused);
  check((await offline.locator('#position').innerText())==='742 / 750','file_url_playback_and_seek');await offline.locator('#audio').evaluate(a=>a.pause());
  check(result.page_errors.length===0,'no_page_errors');result.status='pass';
  result.limitations='手机尺寸与触控行为在桌面 Chromium 中模拟；未在用户的真实手机或 Safari 中验证。';
 }finally{await browser.close();fs.writeFileSync(path.join(root,'data/browser_validation.json'),JSON.stringify(result,null,2)+'\n')}
 console.log(JSON.stringify(result));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});
