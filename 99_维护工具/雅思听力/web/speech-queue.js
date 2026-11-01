(function(root,factory){
 'use strict';
 if(typeof module==='object'&&module.exports)module.exports=factory();
 else root.StudySpeechQueue=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 function create({synth,Utterance,prepare,onState=()=>{},onStart=()=>{},onGap=()=>{},onFinish=()=>{},onError=()=>{},lookAhead=4,setTimer=setTimeout,clearTimer=clearTimeout}){
  let session=null,generation=0;
  const supported=!!synth&&typeof Utterance==='function';
  function stop(){
   const active=!!session;
   if(session){clearTimer(session.gapTimer);clearTimer(session.watchTimer)}
   session=null;generation++;
   // Cancel only for a user action, never between automatically read words.
   if(supported&&active)synth.cancel();
   onState({active:false,continuous:false});
  }
  function fail(s,error){
   if(session!==s)return;
   stop();onError(error);
  }
  function show(s,index){
   if(session!==s||index<=s.shown||index>=s.items.length)return;
   s.shown=index;onStart(s.items[index],{continuous:s.continuous,index});
  }
  function ended(s,index){
   if(session!==s||s.generation!==generation||index<=s.completed)return;
   s.completed=index;s.refs.delete(index);
   if(s.gapMs)clearTimer(s.watchTimer);
   if(index===s.items.length-1){
    session=null;onState({active:false,continuous:false});
    onFinish({continuous:s.continuous});return;
   }
   s.started=Math.max(s.started,index);
   if(s.gapMs){
    // Keep this word visible during the listening/echo gap. Leave the engine
    // idle; automatic continuation never cancels or pauses its native session.
    s.waiting=true;onGap(s.items[index],{gapMs:s.gapMs});
    s.gapTimer=setTimer(()=>{
     if(session!==s||s.generation!==generation)return;
     s.waiting=false;show(s,index+1);fill(s);
    },s.gapMs);
   }else{show(s,index+1);fill(s)}
  }
  function watchEnd(s,index){
   // Some mobile voices omit end. An observed busy -> idle transition is a
   // completion signal too; never guess the spoken word's duration.
   let observedBusy=!!(synth.speaking||synth.pending);
   const check=()=>{
    if(session!==s||index<=s.completed)return;
    if(synth.speaking||synth.pending)observedBusy=true;
    else if(observedBusy){ended(s,index);return}
    s.watchTimer=setTimer(check,100);
   };
   s.watchTimer=setTimer(check,100);
  }
  function fill(s){
   if(session!==s||s.filling||s.waiting)return;
   s.filling=true;
   try{
    // Keep a small native queue alive. Either start or end can replenish it:
    // some voices omit start events, while mobile engines can omit end events.
    while(session===s&&!s.waiting&&s.next<s.items.length&&s.next<s.started+1+lookAhead&&(!s.gapMs||s.next===s.completed+1)){
     const index=s.next++,item=s.items[index],settings=prepare(item);
     const utterance=new Utterance(settings.text);
     utterance.lang=settings.lang||'en-GB';utterance.rate=settings.rate||1;
     utterance.volume=1;utterance.voice=settings.voice||null;
     s.refs.set(index,utterance);
     utterance.onstart=()=>{
      if(session!==s||s.generation!==generation||index<=s.started)return;
      s.started=index;
      // Retain pending/current utterances strongly; older end events are optional.
      for(const key of s.refs.keys())if(key<index)s.refs.delete(key);
      show(s,index);fill(s);
     };
     utterance.onend=()=>ended(s,index);
     utterance.onerror=event=>{
      if(session!==s||s.generation!==generation||index<s.started)return;
      fail(s,event.error||'synthesis-failed');
     };
     synth.speak(utterance);
     if(s.gapMs&&session===s&&index>s.completed)watchEnd(s,index);
    }
   }catch{fail(s,'synthesis-failed')}
   finally{s.filling=false}
  }
  function play(items,{continuous=false,gapMs=0}={}){
   stop();
   if(!supported){onError('unsupported');return false}
   if(!items.length)return false;
   const s={generation,items:continuous?[...items]:[items[0]],continuous,
    gapMs:continuous?Math.max(0,Math.min(5000,Number(gapMs)||0)):0,
    next:0,started:-1,shown:-1,completed:-1,refs:new Map(),filling:false,waiting:false,gapTimer:null,watchTimer:null};
   session=s;onState({active:true,continuous});
   // Both resume and the first queue submission stay inside the user's gesture.
   if(synth.paused)synth.resume();
   show(s,0);
   fill(s);return session===s;
  }
  return{play,stop,get supported(){return supported},get active(){return!!session},get continuous(){return!!session?.continuous}};
 }
 return{create};
});
