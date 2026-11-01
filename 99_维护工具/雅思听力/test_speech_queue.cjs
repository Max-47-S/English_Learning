'use strict';
const assert=require('node:assert/strict');
const {create}=require('./web/speech-queue.js');
const {FakeClock}=require('./test_clock.cjs');
class FakeUtterance{constructor(text){this.text=text}}
class NativeQueue{
 constructor(){this.queue=[];this.current=null;this.cancelCount=0;this.resumeCount=0;this.paused=false;this.submitted=[]}
 speak(u){this.queue.push(u);this.submitted.push(u)}
 cancel(){this.cancelCount++;this.current=null;this.queue=[]}
 resume(){this.resumeCount++;this.paused=false}
 get speaking(){return!!this.current}
 get pending(){return this.queue.length>0}
 start({omit=false}={}){assert.equal(this.current,null);assert.ok(!this.paused);this.current=this.queue.shift();assert.ok(this.current,'native queue must already contain the next word');if(!omit)this.current.onstart();return this.current}
 end({omit=false}={}){const u=this.current;assert.ok(u);this.current=null;if(!omit)u.onend();return u}
}
// Desktop/native voices may provide end without start. They must also read the
// whole group, with one UI transition per entry and no timer-based advancement.
{
 const f=fixture();f.controller.play(f.items,{continuous:true});
 for(let i=0;i<f.items.length;i++){f.synth.start({omit:true});f.synth.end()}
 assert.deepEqual(f.starts,f.items.map(item=>item.id));
 assert.equal(f.synth.cancelCount,0);assert.equal(f.finishes.length,1);
 assert.equal(f.controller.active,false);assert.deepEqual(f.errors,[]);
}
function fixture(clock){
 const synth=new NativeQueue(),starts=[],finishes=[],errors=[],states=[],gaps=[];
 const controller=create({synth,Utterance:FakeUtterance,
  prepare:item=>({text:item.word,lang:'en-GB',rate:1.25}),
  ...(clock?{setTimer:clock.set,clearTimer:clock.clear}:{}),onGap:(_,gap)=>gaps.push(gap.gapMs),
  onStart:item=>starts.push(item.id),onFinish:state=>finishes.push(state),
  onError:error=>errors.push(error),onState:state=>states.push(state)});
 const items=Array.from({length:17},(_,id)=>({id,word:'word '+id}));
 return{synth,controller,items,starts,finishes,errors,states,gaps};
}
// Continuous reading relies on an already pending native utterance. End callbacks
// are deliberately omitted for several middle words, as can happen on mobile.
{
 const f=fixture();f.controller.play(f.items,{continuous:true});
 assert.equal(f.synth.queue.length,4);assert.equal(f.synth.cancelCount,0);
 for(let i=0;i<f.items.length;i++){
  const u=f.synth.start();assert.equal(u.text,'word '+i);assert.equal(u.rate,1.25);
  assert.ok(f.synth.queue.length<=4,'bounded lookahead');
  assert.equal(f.synth.cancelCount,0,'automatic advance must never cancel speech');
  f.synth.end({omit:i%3===0&&i!==f.items.length-1});
 }
 assert.deepEqual(f.starts,f.items.map(item=>item.id));assert.equal(f.finishes.length,1);
 assert.deepEqual(f.finishes[0],{continuous:true});assert.equal(f.controller.active,false);
 assert.deepEqual(f.errors,[]);assert.equal(f.synth.queue.length,0);
}
// Stop, next/replay, and restarting continuous reading invalidate delayed events
// from the old queue and preserve single-item-then-stop behavior.
{
 const f=fixture();f.controller.play(f.items,{continuous:true});
 const old=f.synth.start(),oldPending=f.synth.queue[0];
 f.controller.stop();f.controller.stop();assert.equal(f.synth.cancelCount,1);
 old.onend();oldPending.onstart();assert.deepEqual(f.starts,[0]);
 f.controller.play(f.items.slice(1));assert.equal(f.synth.queue.length,1);
 f.synth.start();f.synth.end();assert.deepEqual(f.starts,[0,1]);
 assert.deepEqual(f.finishes,[{continuous:false}]);assert.equal(f.controller.active,false);
 // Clicking continuous while the replay is still speaking starts a new queue.
 f.controller.play(f.items.slice(2));const replay=f.synth.start();
 f.controller.play(f.items.slice(2),{continuous:true});
 assert.equal(f.synth.cancelCount,2);assert.equal(f.controller.continuous,true);
 replay.onend();replay.onerror({error:'interrupted'});
 for(let i=2;i<f.items.length;i++){f.synth.start();f.synth.end()}
 assert.deepEqual(f.starts,[0,1,2,...f.items.slice(2).map(item=>item.id)]);
 assert.deepEqual(f.errors,[]);assert.deepEqual(f.finishes.at(-1),{continuous:true});
}
// A paused engine is resumed in the initiating gesture, and real errors cancel
// pending speech instead of silently switching cards without sound.
{
 const f=fixture();f.synth.paused=true;f.controller.play(f.items,{continuous:true});
 assert.equal(f.synth.resumeCount,1);const u=f.synth.start();
 u.onerror({error:'synthesis-failed'});
 assert.equal(f.controller.active,false);assert.equal(f.synth.queue.length,0);
 assert.deepEqual(f.errors,['synthesis-failed']);assert.deepEqual(f.finishes,[]);
 u.onend();assert.deepEqual(f.finishes,[]);
}
{
 const errors=[];const queue=create({onError:error=>errors.push(error)});
 assert.equal(queue.supported,false);assert.equal(queue.play([{word:'test'}]),false);
 assert.deepEqual(errors,['unsupported']);
}
// A gap starts only after confirmed completion, holds the old card, and neither
// cancels speech nor relies on native pause/resume behavior between utterances.
for(const gapMs of [500,1000,1500,2000,3000]){
 const clock=new FakeClock(),f=fixture(clock);
 f.controller.play(f.items.slice(0,3),{continuous:true,gapMs});
 assert.equal(f.synth.queue.length,1);
 f.synth.start();clock.advance(2500);
 assert.deepEqual(f.starts,[0],'a long word must finish before its gap begins');
 f.synth.end();assert.equal(f.synth.queue.length,0);assert.deepEqual(f.starts,[0]);
 clock.advance(gapMs-1);assert.equal(f.synth.queue.length,0);
 clock.advance(1);assert.equal(f.synth.queue.length,1);assert.deepEqual(f.starts,[0,1]);
 // Missing end is recovered from the real native busy -> idle transition.
 f.synth.start();f.synth.end({omit:true});clock.advance(100);
 assert.deepEqual(f.starts,[0,1]);clock.advance(gapMs-1);assert.equal(f.synth.queue.length,0);
 clock.advance(1);f.synth.start();f.synth.end();
 assert.deepEqual(f.starts,[0,1,2]);assert.deepEqual(f.gaps,[gapMs,gapMs]);
 assert.equal(f.finishes.length,1);assert.equal(clock.timers.size,0);
 assert.equal(f.synth.cancelCount,0);assert.equal(f.synth.resumeCount,0);
}
{
 const clock=new FakeClock(),f=fixture(clock);
 f.controller.play(f.items,{continuous:true,gapMs:1000});
 const old=f.synth.start();f.synth.end();f.controller.stop();
 clock.advance(5000);old.onend();assert.deepEqual(f.starts,[0]);assert.equal(f.synth.queue.length,0);
 assert.equal(clock.timers.size,0);
 // Replay/next remains immediate and single-item even with a saved gap value.
 f.controller.play(f.items.slice(1),{continuous:false,gapMs:3000});f.synth.start();f.synth.end();
 assert.equal(clock.timers.size,0);assert.deepEqual(f.finishes,[{continuous:false}]);
}
console.log('PASS: native queue; missing start/end; 0.5–3s gaps after completion; idle recovery; stop during gap; single-word replay; stale events; errors.');
