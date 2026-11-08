let singleIndex=null,stopTimer=null,scriptedPlay=false,scriptedSeek=null,nativeSeek=false,singleFinished=false;
function clearStopTimer(){if(stopTimer!==null){clearTimeout(stopTimer);stopTimer=null}}
function setPlaybackMode(index){clearStopTimer();singleIndex=index;singleFinished=false}
function singleEndTime(){
  const a=words[singleIndex].audio;
  const spoken=Number.isFinite(speechEnds[singleIndex])?speechEnds[singleIndex]:a.end;
  return Math.min(spoken+.03,a.end-.02);
}
function seekAudio(time){
  const t=Math.max(0,Math.min(Number.isFinite(time)?time:0,words[words.length-1].audio.end-.001));
  if(audio.readyState===0){pendingSeek=t;return}
  scriptedSeek=t;audio.currentTime=t;
}
function showPlayingStatus(){
  $('status').textContent=singleIndex===null?'连续播放中 · 每条后有跟读停顿。':'单条播放中 · 本条读完后自动暂停。';
}
function finishSingle(){
  clearStopTimer();singleFinished=true;
  const end=singleEndTime();audio.pause();seekAudio(end);
  current=singleIndex;renderCard();savePosition();
  $('status').textContent='本条已播完。点击音频栏播放按钮或拖动进度条，恢复连续播放。';
}
function checkSingleBoundary(){
  if(singleIndex===null||audio.paused||audio.seeking||audio.readyState===0)return;
  if(audio.currentTime>=singleEndTime()-.005)finishSingle();
}
function armSingleStop(){
  clearStopTimer();
  if(singleIndex===null||audio.paused||audio.seeking||audio.readyState===0)return;
  const remaining=(singleEndTime()-audio.currentTime)/audio.playbackRate;
  if(remaining<=.005){checkSingleBoundary();return}
  stopTimer=setTimeout(()=>{stopTimer=null;checkSingleBoundary();armSingleStop()},Math.max(10,Math.min(100,remaining*1000)));
}
function playAudio(){
  interacted=true;
  if(!audio.paused){showPlayingStatus();armSingleStop();return}
  scriptedPlay=true;
  audio.play().catch(error=>{
    scriptedPlay=false;
    if(error.name!=='AbortError')$('status').textContent='已定位，请点击音频栏的播放按钮。';
  });
}
audio.addEventListener('play',()=>{
  interacted=true;
  if(!scriptedPlay)setPlaybackMode(null);
  scriptedPlay=false;showPlayingStatus();armSingleStop();
});
audio.addEventListener('playing',()=>{showPlayingStatus();armSingleStop()});
audio.addEventListener('pause',()=>{
  clearStopTimer();scriptedPlay=false;
  if(audio.error)return;
  savePosition();
  $('status').textContent=singleFinished?'本条已播完。点击音频栏播放按钮或拖动进度条，恢复连续播放。':'已暂停；点击音频栏播放按钮可继续连续播放。';
});
// App seeks are marked; a native timeline seek switches back to continuous playback.
audio.addEventListener('seeking',()=>{
  clearStopTimer();
  const own=scriptedSeek!==null&&Math.abs(audio.currentTime-scriptedSeek)<.05;
  if(!own){interacted=true;scriptedSeek=null;nativeSeek=true;setPlaybackMode(null)}
});
audio.addEventListener('seeked',()=>{
  const own=scriptedSeek!==null&&Math.abs(audio.currentTime-scriptedSeek)<.05;
  scriptedSeek=null;
  if(!own&&nativeSeek){nativeSeek=false;setPlaybackMode(null);playAudio()}
  else{nativeSeek=false;armSingleStop()}
});
audio.addEventListener('ratechange',armSingleStop);
audio.addEventListener('waiting',clearStopTimer);
audio.addEventListener('ended',clearStopTimer);
function jump(i,autoplay=true,single=singleIndex!==null){interacted=true;current=Math.max(0,Math.min(words.length-1,i));setPlaybackMode(single?current:null);seekAudio(words[current].audio.start+.001);renderCard();history.replaceState(null,'','#word-'+words[current].id);if(autoplay)playAudio();}
function indexAt(time){let lo=0,hi=words.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(words[mid].audio.start<=time)lo=mid;else hi=mid-1}return lo;}
audio.addEventListener('loadedmetadata',()=>{if(pendingSeek!==null){const t=pendingSeek;pendingSeek=null;seekAudio(t)}$('status').textContent='已载入完整真人音频。上一词、下一词和重听会在本条读完后暂停。'});
audio.addEventListener('timeupdate',()=>{checkSingleBoundary();const i=singleIndex===null?indexAt(audio.currentTime):singleIndex;if(i!==current){current=i;renderCard()}const n=Math.floor(audio.currentTime/2);if(n!==lastSaved){savePosition();lastSaved=n}});
audio.addEventListener('error',()=>{$('status').textContent='未找到音频。请保留本页与 audio 文件夹的相对位置，再用浏览器打开。'});
list.addEventListener('click',event=>{const item=event.target.closest('.entry');if(item)jump(Number(item.dataset.index))});
$('prevWord').onclick=()=>jump(current-1,true,true);$('nextWord').onclick=()=>jump(current+1,true,true);$('replay').onclick=()=>jump(current,true,true);$('speed').onchange=()=>{audio.playbackRate=Number($('speed').value)};
$('resume').onclick=()=>{const time=saved();jump(indexAt(time),false,false);seekAudio(time);playAudio()};
