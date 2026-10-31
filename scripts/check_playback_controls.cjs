/* Browser checks for single-entry buttons and native continuous-play controls. */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {pathToFileURL}=require('node:url'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const screenshots=fs.mkdtempSync(path.join(os.tmpdir(),'english-player-controls-'));
const packs=[
 {dir:'Oxford3000_学习包',hash:'word',prev:'prevWord',next:'nextWord',key:'oxford3000-pdf-position',count:3306},
 {dir:'OxfordPhraseList_学习包',hash:'phrase',prev:'prevPhrase',next:'nextPhrase',key:'oxford-phrase-list-pdf-v1-position',count:750}
];
const check=(report,name,ok,details)=>{report.checks[name]={status:ok?'pass':'fail',...(details===undefined?{}:{details})};if(!ok)throw Error(name)};
async function nativePlay(page){
 const box=await page.locator('#audio').boundingBox();
 await page.mouse.click(box.x+20,box.y+box.height/2);
 await page.waitForFunction(()=>!document.getElementById('audio').paused,null,{timeout:5000});
}
async function suite(browser,pack){
 const dir=path.join(root,pack.dir),html=path.join(dir,'连续听读.html');
 const rows=JSON.parse(fs.readFileSync(path.join(dir,'data/vocabulary.json'),'utf8'));
 const timeline=JSON.parse(fs.readFileSync(path.join(dir,'data/audio_timeline.json'),'utf8')).entries;
 const report={checked_at:new Date().toISOString(),browser:browser.version(),html_sha256:crypto.createHash('sha256').update(fs.readFileSync(html)).digest('hex'),checks:{},page_errors:[]};
 const context=await browser.newContext({viewport:{width:1100,height:1000}}),page=await context.newPage();
 page.on('pageerror',error=>report.page_errors.push(error.message));
 const base=timeline.findIndex((r,i)=>i>=5&&i<30&&[i-1,i,i+1,i+2].every(j=>timeline[j].spoken_end-timeline[j].start>.55&&timeline[j].spoken_end-timeline[j].start<3));
 if(base<0)throw Error('No suitable real-audio fixture');
 const fileUrl=pathToFileURL(html).href;
 const state=()=>page.locator('#audio').evaluate(a=>({paused:a.paused,time:a.currentTime,rate:a.playbackRate}));
 async function currentId(){
  const label=pack.hash==='phrase'?await page.locator('#position').innerText():await page.locator('#card .tag').first().innerText();
  return Number(label.match(/(\d+)\s*\/\s*\d+/)[1]);
 }
 async function openAt(i){
  await page.goto('about:blank');
  await page.goto(fileUrl+'#'+pack.hash+'-'+(i+1));
  await page.waitForFunction(t=>{const a=document.getElementById('audio');return a.readyState>=1&&!a.seeking&&Math.abs(a.currentTime-t)<.2},timeline[i].start);
  await page.selectOption('#speed','1.5');
  check(report,'loaded_'+(i+1),await currentId()===i+1);
 }
 async function stoppedAt(i,name){
  await page.waitForFunction(()=>document.getElementById('audio').paused,null,{timeout:12000});
  const a=await state(),r=timeline[i];
  check(report,name+'_voice_finished',a.time>=r.spoken_end-.06&&a.time<r.end-.2,{time:a.time,spoken_end:r.spoken_end,next_start:r.end});
  check(report,name+'_selection',await currentId()===i+1);
  await page.waitForTimeout(350);
  const later=await state();
  check(report,name+'_stays_paused',later.paused&&Math.abs(later.time-a.time)<.02);
 }
 try{
  for(const running of [false,true]){
   for(const [button,offset] of [[pack.prev,-1],[pack.next,1],['replay',0]]){
    await openAt(base);
    if(running)await nativePlay(page);
    else check(report,button+'_initially_paused',(await state()).paused);
    await page.click('#'+button);
    await page.waitForFunction(()=>!document.getElementById('audio').paused);
    await stoppedAt(base+offset,(running?'playing_':'paused_')+button);
   }
  }
  console.log(pack.dir+': previous/next/replay pass from playing and paused states');

  await openAt(base);
  await page.click('#replay');
  await page.waitForFunction(()=>!document.getElementById('audio').paused);
  await page.selectOption('#speed','0.75');
  await page.waitForTimeout(80);
  await page.selectOption('#speed','1.5');
  await stoppedAt(base,'rate_change');
  await nativePlay(page);
  await page.waitForFunction(t=>document.getElementById('audio').currentTime>t,timeline[base+1].start+.08);
  // Native time advances between timeupdate events; wait for the visible card too.
  await page.waitForFunction(({id,phrase})=>{
   const label=document.querySelector(phrase?'#position':'#card .tag').textContent;
   return !document.getElementById('audio').paused&&Number(label.match(/(\d+)\s*\/\s*\d+/)[1])>=id;
  },{id:base+2,phrase:pack.hash==='phrase'},{timeout:5000});
  check(report,'native_play_restores_continuous',!(await state()).paused&&await currentId()>=base+2);
  await page.locator('#audio').evaluate(a=>a.pause());

  await openAt(base);
  await page.click('#replay');
  await page.waitForFunction(()=>!document.getElementById('audio').paused);
  await stoppedAt(base,'before_native_seek');
  const box=await page.locator('#audio').boundingBox();
  await page.mouse.click(box.x+box.width*.55,box.y+box.height/2);
  await page.waitForFunction(()=>{const a=document.getElementById('audio');return !a.seeking&&!a.paused&&a.currentTime>100},null,{timeout:10000});
  const seekState=await state();
  const seekIndex=timeline.findLastIndex(r=>r.start<=seekState.time);
  await page.waitForFunction(t=>document.getElementById('audio').currentTime>t,timeline[seekIndex+1].start+.08,{timeout:12000});
  check(report,'native_timeline_restores_continuous',!(await state()).paused);
  await page.locator('#audio').evaluate(a=>a.pause());

  await openAt(base);
  for(const button of [pack.next,pack.next,pack.prev,'replay'])await page.click('#'+button);
  await page.waitForFunction(()=>!document.getElementById('audio').paused);
  await stoppedAt(base+1,'rapid_navigation');
  const savedTime=timeline[base+3].start+.1;
  await page.evaluate(({key,time})=>localStorage.setItem(key,String(time)),{key:pack.key,time:savedTime});
  await page.click('#resume');
  await page.waitForFunction(t=>document.getElementById('audio').currentTime>t,timeline[base+4].start+.08,{timeout:12000});
  check(report,'resume_is_continuous',!(await state()).paused);
  await page.locator('#audio').evaluate(a=>a.pause());

  await openAt(0);
  check(report,'first_entry_previous_disabled',await page.locator('#'+pack.prev).isDisabled());
  await openAt(rows.length-1);
  check(report,'last_entry_next_disabled',await page.locator('#'+pack.next).isDisabled());
  await page.click('#replay');
  await page.waitForFunction(()=>!document.getElementById('audio').paused);
  await stoppedAt(rows.length-1,'last_entry_replay');

  if(process.env.PLAYER_TEST_BASE_URL){
   await page.route('**/*.mp3',async route=>{await new Promise(r=>setTimeout(r,800));await route.continue()});
   const url=process.env.PLAYER_TEST_BASE_URL.replace(/\/$/,'')+'/'+encodeURIComponent(pack.dir)+'/'+encodeURIComponent('连续听读.html');
   await page.goto(url+'#'+pack.hash+'-'+(base+1),{waitUntil:'domcontentloaded'});
   check(report,'metadata_initially_pending',await page.locator('#audio').evaluate(a=>a.readyState===0));
   await page.click('#'+pack.next);
   await page.waitForFunction(()=>!document.getElementById('audio').paused);
   await stoppedAt(base+1,'navigation_before_metadata');
   await page.unroute('**/*.mp3');
  }

  const phoneContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const phone=await phoneContext.newPage();
  phone.on('pageerror',e=>report.page_errors.push(e.message));
  await phone.goto(fileUrl+'#'+pack.hash+'-'+(base+1));
  await phone.waitForFunction(()=>document.getElementById('audio').readyState>=1);
  await phone.locator('#replay').tap();
  await phone.waitForFunction(()=>!document.getElementById('audio').paused);
  await phone.waitForFunction(()=>document.getElementById('audio').paused,null,{timeout:12000});
  const mobileTime=await phone.locator('#audio').evaluate(a=>a.currentTime);
  check(report,'mobile_single_entry',mobileTime>=timeline[base].spoken_end-.06&&mobileTime<timeline[base].end-.2);
  check(report,'mobile_no_horizontal_overflow',await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await phone.screenshot({path:path.join(screenshots,pack.hash+'-mobile.png')});
  await phoneContext.close();
  check(report,'no_page_errors',report.page_errors.length===0);
  report.status='pass';
  report.limitations='Real local MP3 tested in desktop Chrome; mobile uses viewport/touch emulation. Safari and physical phones were not exercised.';
 }catch(error){report.status='fail';report.failure=error.stack;throw error}
 finally{
  fs.writeFileSync(path.join(dir,'data/playback_controls_validation.json'),JSON.stringify(report,null,2)+'\n');
  await context.close();
  console.log(JSON.stringify({pack:pack.dir,status:report.status,checks:Object.keys(report.checks).length,failure:report.failure,screenshots}));
 }
}
async function main(){
 const options={headless:true};
 const system=process.platform==='darwin'?'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome':process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':null;
 if(process.env.CHROME_PATH)options.executablePath=process.env.CHROME_PATH;
 else if(system&&fs.existsSync(system))options.executablePath=system;
 const browser=await chromium.launch(options);
 try{for(const pack of packs)await suite(browser,pack)}
 finally{await browser.close()}
}
main().catch(error=>{console.error(error.stack);process.exitCode=1});
