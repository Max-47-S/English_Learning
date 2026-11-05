'use strict';
// Exercise the real app handlers with a controllable native speech/media engine.
// This catches mode races and button regressions that a queue-only test cannot.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {create}=require('./web/speech-queue.js');
const {FakeClock}=require('./test_clock.cjs');
class Element{
 constructor(){this.textContent='';this.value='';this.dataset={};this.hidden=false;this.listeners={};this.classes=new Set();this.classList={add:v=>this.classes.add(v),remove:v=>this.classes.delete(v),toggle:(v,on)=>on?this.classes.add(v):this.classes.delete(v)}}
 addEventListener(name,handler){(this.listeners[name]??=[]).push(handler)}
 emit(name){for(const handler of this.listeners[name]||[])handler({})}
 setAttribute(name,value){this[name]=value}
 removeAttribute(name){delete this[name]}
 querySelector(){return null}
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
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
const audio=new Audio();elements.set('original-audio',audio);get('study-data').textContent=JSON.stringify(data);
const synth=new Speech(),storage=new Map(),clock=new FakeClock();
storage.set('ielts-four-chapters-v1',JSON.stringify({collection:'oxford3000',chapter:'1',group:'group-0',selected:'old-oxford-entry',mode:'word'}));
storage.set('ielts-four-chapters-v1-favorites',JSON.stringify(['old-oxford-entry']));
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
 audio.pause();
 console.log('PASS: three collections with default 1s gaps; hold current card; gap preference persistence; single-word stop; replay → continuous; hidden media isolation.');
})().catch(error=>{console.error(error);process.exitCode=1});
