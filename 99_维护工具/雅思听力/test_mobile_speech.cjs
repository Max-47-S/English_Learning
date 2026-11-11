'use strict';
// Exercise the real app handlers with a controllable native speech/media engine.
// This catches mode races and button regressions that a queue-only test cannot.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {create}=require('./web/speech-queue.js');
const {FakeClock}=require('./test_clock.cjs');
class Element{
 constructor(){this.textContent='';this.value='';this.dataset={};this.hidden=false;this.listeners={};this.classes=new Set();this.classList={add:v=>this.classes.add(v),remove:v=>this.classes.delete(v),toggle:(v,on)=>on?this.classes.add(v):this.classes.delete(v)}}
 addEventListener(name,handler){(this.listeners[name]??=[]).push(handler)}
 emit(name,event={}){for(const handler of this.listeners[name]||[])handler(event)}
 setAttribute(name,value){this[name]=value}
 removeAttribute(name){delete this[name]}
 querySelector(){return null}
 focus(){this.focused=true}
 scrollIntoView(){}
}
class Audio extends Element{
 constructor(){super();this.paused=true;this.currentTime=0;this.readyState=0;this.playCalls=0}
 pause(){if(!this.paused){this.paused=true;this.emit('pause')}}
 play(){this.playCalls++;this.paused=false;this.emit('play');return Promise.resolve()}
 load(){}
}
class Utterance{constructor(text){this.text=text}}
class Speech{
 constructor(){this.queue=[];this.current=null;this.cancelCount=0;this.paused=false}
 getVoices(){return[{lang:'en-GB',name:'test English'}]}
 addEventListener(){}
 speak(u){this.queue.push(u)}
 cancel(){this.cancelCount++;this.current=null;this.queue=[]}
 resume(){this.paused=false}
 start(){assert.equal(this.current,null);this.current=this.queue.shift();assert.ok(this.current);this.current.onstart();return this.current}
 end(){const u=this.current;assert.ok(u);this.current=null;u.onend()}
}
const collectionIds=['oxford3000','phrases750','ielts'];
const data={collections:collectionIds.map(id=>({id,title:id,subtitle:'test',defaultMode:'word'})),
 chapters:collectionIds.map((collection,i)=>({id:String(i+1),collection,title:collection,groups:[{id:'group-'+i,title:'test',all:true,trackIds:{default:'track-'+i}}]})),
 entries:collectionIds.flatMap((collection,i)=>Array.from({length:8},(_,j)=>({id:collection+'-'+j,collection,chapter:String(i+1),group:'group-'+i,source:collection,order:j+1,word:collection+' word '+j,meaning:'测试'}))),
 tracks:collectionIds.map((id,i)=>({id:'track-'+i,chapter:String(i+1),title:'test',file:'test.mp3',cues:Array.from({length:8},(_,j)=>({entryId:id+'-'+j,start:j*5,spokenEnd:j*5+1,end:(j+1)*5}))})),audioCredits:{},entryAliases:{'old-oxford-entry':'oxford3000-0'}};
data.entries.find(e=>e.id==='ielts-3').word='word 3';
data.entries.find(e=>e.id==='phrases750-3').word='word 3 practice';
data.collections.push({id:'encounters',title:'遇词本',subtitle:'自选词条',defaultMode:'word',note:'分组听读'});
for(const [kind,title,count] of [['word','单词',1],['phrase','短语',0]]){
 const chapter='encounter-'+kind;
 data.chapters.push({id:chapter,collection:'encounters',title,groups:[
  {id:chapter+'-exam',title:'备考必记',count},
  {id:chapter+'-accumulation',title:'日常积累',count},
 ]});
}
data.entries.push(
 {id:'encounter-blink',collection:'encounters',chapter:'encounter-word',group:'encounter-word-exam',source:'encounter',order:1,word:'blink',meaning:'眨眼'},
 {id:'encounter-consignment',collection:'encounters',chapter:'encounter-word',group:'encounter-word-accumulation',source:'encounter',order:1,word:'consignment',meaning:'一票货件'}
);
data.collections.push({id:'ipa',title:'48 音标',subtitle:'真人示范',defaultMode:'original'});
data.chapters.push({id:'ipa-48',collection:'ipa',title:'48 音标',
 groups:[{id:'ipa-all',title:'全部音标',count:2,all:true,trackIds:{default:'ipa-follow'}}]});
const ipaCards=[['/iː/','see','green'],['/ɪ/','sit','fish']].map(([word,...examples],index)=>({
 id:'ipa-'+index,collection:'ipa',chapter:'ipa-48',group:'ipa-all',source:'ipa',order:index+1,
 word,meaning:examples.join(' · '),ipaTip:'发音提示',
 ipaExamples:examples.map(word=>({word,prefix:'',target:word,suffix:'',ipa:'',meaning:'例词'})),
}));
data.entries.push(...ipaCards);
data.tracks.push({id:'ipa-follow',chapter:'ipa-48',title:'真人录音',staticUrl:'/audio/ipa.mp3',
 cues:ipaCards.map((card,index)=>{
  const start=index*34;
  return {entryId:card.id,start,spokenEnd:start+30,practiceEnd:start+33,end:start+34,
   parts:[
    {label:card.word,start,spokenEnd:start+1,step:3},
    {label:card.ipaExamples[0].word,start:start+9,spokenEnd:start+10,step:4},
    {label:card.ipaExamples[1].word,start:start+21,spokenEnd:start+22,step:4},
   ]};
 }),
});
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
const audio=new Audio();elements.set('original-audio',audio);get('study-data').textContent=JSON.stringify(data);
get('search').value='word 3';
const synth=new Speech(),storage=new Map(),clock=new FakeClock();
storage.set('ielts-four-chapters-v1',JSON.stringify({collection:'oxford3000',chapter:'1',group:'group-0',selected:'old-oxford-entry',mode:'word'}));
storage.set('ielts-four-chapters-v1-favorites',JSON.stringify(['old-oxford-entry']));
storage.set('ielts-four-chapters-v1-audio',JSON.stringify({'track-2':35}));
const context={console,JSON,Map,Set,URL,URLSearchParams,Promise,Number,String,Math,
 document:{body:get('body'),getElementById:get,querySelectorAll:()=>[],addEventListener:()=>{}},
 location:{search:'?collection=oxford3000',protocol:'https:',hostname:'test.invalid',href:'https://test.invalid/study/?collection=oxford3000'},
 navigator:{},history:{replaceState:()=>{}},localStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
 StudySpeechQueue:{create:options=>create({...options,setTimer:clock.set,clearTimer:clock.clear})},StudyTimeline:require('./web/timeline-core.js'),
 SpeechSynthesisUtterance:Utterance,speechSynthesis:synth,
 addEventListener:()=>{},requestAnimationFrame:()=>1,cancelAnimationFrame:()=>{}};
context.window=context;
vm.runInNewContext(fs.readFileSync(__dirname+'/../通用/hover-translations.js','utf8'),context);
vm.runInNewContext(fs.readFileSync(__dirname+'/web/app.js','utf8'),context,{filename:'app.js'});
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const selected=()=>JSON.parse(storage.get('ielts-four-chapters-v1')).selected;
(async()=>{
 await flush();
 assert.equal(selected(),'oxford3000-0');assert.deepEqual(JSON.parse(storage.get('ielts-four-chapters-v1-favorites')),['oxford3000-0']);
 assert.equal(get('search-count').textContent,'找到 3 条词条','input entered during loading is searched at startup');
 get('search').value='';get('search').oninput({isComposing:false});
 for(const id of collectionIds){
  get('collections').onclick({target:{closest:()=>({dataset:{collection:id}})}});await flush();
  assert.equal(get('speech-gap').value,'1000');
  get('continuous-words').onclick();assert.equal(synth.queue.length,1);
  for(let j=0;j<6;j++){
   synth.start();assert.equal(selected(),id+'-'+j);synth.end();
   assert.equal(synth.queue.length,0);assert.match(get('speech-status').textContent,/词间停顿 1 秒/);
   clock.advance(999);assert.equal(selected(),id+'-'+j);assert.equal(synth.queue.length,0);clock.advance(1);
  }
  // Delayed events from a hidden original recording must not cancel or play it.
  const cancelCount=synth.cancelCount,playCalls=audio.playCalls;
  audio.currentTime=17;audio.emit('seeked');assert.equal(audio.playCalls,playCalls);
  audio.paused=false;audio.emit('play');assert.equal(audio.paused,true);
  audio.emit('ended');assert.equal(synth.cancelCount,cancelCount);
  synth.start();assert.equal(selected(),id+'-6');synth.end();clock.advance(1000);synth.start();synth.end();
  assert.equal(get('speech-status').textContent,'本组已读完，已暂停。');assert.equal(synth.queue.length,0);
  get('prev-word').onclick();assert.equal(synth.queue.length,1);synth.start();synth.end();
  assert.equal(synth.queue.length,0);assert.match(get('speech-status').textContent,/本词已读完/);
  get('replay-word').onclick();const replay=synth.start();
  // The visible continuous button must start continuity during a single replay.
  get('continuous-words').onclick();assert.equal(get('continuous-words').textContent,'暂停连续朗读');
  replay.onend();assert.equal(synth.queue.length,1);synth.start();synth.end();clock.advance(1000);synth.start();synth.end();
  assert.equal(get('speech-status').textContent,'本组已读完，已暂停。');
  get('replay-word').onclick();synth.start();get('original-mode').onclick();
  assert.equal(synth.queue.length,0);assert.equal(synth.current,null);
  assert.equal(get('continuous-words').textContent,'▶ 连续朗读');
 }
 // Gap and pronunciation speed are separate preferences, saved across groups.
 get('word-mode').onclick();get('speech-gap').value='2000';get('speech-gap').onchange();
 const prefs=JSON.parse(storage.get('ielts-four-chapters-v1'));assert.equal(prefs.gapMs,2000);assert.equal(prefs.rate,1);
 get('collections').onclick({target:{closest:()=>({dataset:{collection:'oxford3000'}})}});await flush();
 assert.equal(get('speech-gap').value,'2000');
 assert.equal(clock.timers.size,0);
 // Native recording time, including its silence, drives the card at every rate.
 get('original-mode').onclick();await flush();audio.duration=40;audio.readyState=1;audio.emit('loadedmetadata');
 get('word-list').onclick({target:{closest:()=>({dataset:{id:'oxford3000-0'}})}});
 assert.equal(audio.currentTime,0);audio.currentTime=.7;audio.emit('timeupdate');assert.equal(selected(),'oxford3000-0');
 audio.currentTime=1.06;audio.emit('timeupdate');assert.equal(audio.paused,true);
 get('continuous-audio').onclick();audio.currentTime=4.99;audio.emit('timeupdate');assert.equal(selected(),'oxford3000-0');
 audio.currentTime=5;audio.emit('timeupdate');assert.equal(selected(),'oxford3000-1');assert.equal(audio.paused,false);
 get('speed').value='2';get('speed').onchange();assert.equal(audio.playbackRate,2);
 audio.currentTime=10;audio.emit('timeupdate');assert.equal(selected(),'oxford3000-2');
 assert.equal(clock.timers.size,0,'original recording never uses a synthetic word-gap timer');
 console.log('PASS: three collections with default 1s gaps; hold current card; gap preference persistence; single-word stop; replay → continuous; hidden media isolation.');
 const input=get('search'),hits=get('search-hits'),playCalls=audio.playCalls;
 input.value='  WoRd   3 ';
 input.oninput({isComposing:true});assert.equal(hits.innerHTML,'');
 input.oncompositionend();
 assert.deepEqual([...hits.innerHTML.matchAll(/data-search-id="([^"]+)"/g)].map(m=>m[1]),['ielts-3','phrases750-3','oxford3000-3']);
 assert.equal(selected(),'oxford3000-2');assert.equal(audio.paused,false);
 input.value='测试';input.oninput({isComposing:false});
 assert.match(get('search-count').textContent,/24/);
 assert.equal([...hits.innerHTML.matchAll(/data-search-id=/g)].length,18);
 get('search-more').onclick();assert.equal([...hits.innerHTML.matchAll(/data-search-id=/g)].length,24);
 input.value='word 3';input.oninput({isComposing:false});
 const ieltsPrefs=JSON.parse(storage.get('ielts-four-chapters-v1-collection-ielts'));
 storage.set('ielts-four-chapters-v1-collection-ielts',JSON.stringify({...ieltsPrefs,mode:'original'}));
 hits.onclick({target:{closest:()=>({dataset:{searchId:'ielts-3'}})}});
 assert.equal(selected(),'ielts-3');assert.equal(get('group-select').value,'group-2');
 assert.equal(get('search-results').hidden,true);assert.equal(get('word-card').focused,true);
 await flush();audio.emit('loadedmetadata');audio.emit('seeked');
 assert.equal(audio.currentTime,15);assert.equal(selected(),'ielts-3');
 assert.equal(audio.paused,true);assert.equal(audio.playCalls,playCalls);
 assert.equal(JSON.parse(storage.get('ielts-four-chapters-v1-collection-oxford3000')).selected,'oxford3000-2');
 console.log('PASS: global search ranks all three collections; Chinese IME, additional results and quiet audio positioning work across collections.');
 input.value='货件';input.oninput({isComposing:false});
 assert.match(hits.innerHTML,/遇词本 · 单词 · 日常积累/);
 hits.onclick({target:{closest:()=>({dataset:{searchId:'encounter-consignment'}})}});
 assert.equal(selected(),'encounter-consignment');assert.equal(get('group-select').value,'encounter-word-accumulation');
 assert.equal(get('mode-switch').hidden,true);assert.equal(get('original-player').hidden,true);
 get('continuous-words').onclick();assert.equal(synth.start().text,'consignment');synth.end();
 assert.equal(synth.queue.length,0,'continuous playback stays within the selected group');
 assert.match(get('speech-status').textContent,/本组已读完/);
 get('chapters').onclick({target:{closest:()=>({dataset:{chapter:'encounter-phrase'}})}});
 assert.equal(get('group-select').value,'encounter-phrase-exam');
 assert.match(get('word-card').innerHTML,/还没有收录短语/);assert.equal(get('replay-word').disabled,true);
 get('group-select').value='encounter-phrase-accumulation';get('group-select').onchange();
 const personal=JSON.parse(storage.get('ielts-four-chapters-v1-collection-encounters'));
 assert.equal(personal.group,'encounter-phrase-accumulation');assert.equal(personal.selected,'');
 get('collections').onclick({target:{closest:()=>({dataset:{collection:'ielts'}})}});await flush();
 assert.equal(get('mode-switch').hidden,false);assert.equal(get('original-player').hidden,false);
 assert.equal(selected(),'ielts-3');assert.equal(audio.playCalls,playCalls);
 console.log('PASS: encounter search, group-scoped speech, both empty phrase groups and restored IELTS mode.');
 get('collections').onclick({target:{closest:()=>({dataset:{collection:'ipa'}})}});await flush();
 audio.duration=68;audio.emit('loadedmetadata');audio.emit('seeked');
 assert.equal(selected(),'ipa-0');assert.equal(audio.src,'/audio/ipa.mp3');
 assert.equal(get('mode-switch').hidden,true);assert.equal(get('original-player').hidden,false);
 assert.equal(audio.playbackRate,1,'IPA starts at the slow baseline');
 assert.equal([...get('word-card').innerHTML.matchAll(/data-ipa-part=/g)].length,3);
 const clickPart=index=>get('word-card').emit('click',{target:{closest:()=>({dataset:{ipaPart:String(index)}})}});
 clickPart(0);audio.emit('seeked');assert.equal(audio.currentTime,0);
 assert.match(get('ipa-follow').textContent,/试听 · \/iː\//);
 audio.currentTime=1.06;audio.emit('timeupdate');assert.equal(audio.paused,true);
 clickPart(2);audio.emit('seeked');assert.equal(audio.currentTime,21);
 assert.match(get('ipa-follow').textContent,/试听 · green/);
 audio.currentTime=22.06;audio.emit('timeupdate');assert.equal(audio.paused,true);
 get('replay-recording-word').onclick();audio.emit('seeked');assert.equal(audio.currentTime,0);
 audio.currentTime=7.2;audio.emit('timeupdate');assert.match(get('ipa-follow').textContent,/跟读 3 \/ 3/);
 audio.currentTime=33;audio.emit('timeupdate');assert.equal(audio.paused,true);
 assert.equal(selected(),'ipa-0');assert.match(get('audio-status').textContent,/三遍跟读结束/);
 get('continuous-audio').onclick();audio.emit('seeked');assert.equal(audio.currentTime,0);
 get('speed').value='1.5';get('speed').onchange();assert.equal(audio.playbackRate,1.5);
 audio.currentTime=34.05;audio.emit('timeupdate');assert.equal(selected(),'ipa-1');
 get('continuous-audio').onclick();assert.equal(audio.paused,true);
 get('continuous-audio').onclick();assert.equal(audio.paused,false);assert.equal(audio.currentTime,34.05);
 assert.equal(synth.queue.length,0);
 get('collections').onclick({target:{closest:()=>({dataset:{collection:'oxford3000'}})}});await flush();
 assert.equal(audio.playbackRate,2,'IPA speed does not overwrite the general speed');
 console.log('PASS: IPA sound and word previews, three-round card playback, continuous switching and pause, and independent speed.');
})().catch(error=>{console.error(error);process.exitCode=1});
