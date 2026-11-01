(()=>{
'use strict';
const data=JSON.parse(document.getElementById('study-data').textContent),$=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const KEY='ielts-four-chapters-v1',audio=$('original-audio'),SPEECH_GAPS=[0,500,1000,1500,2000,3000];
const read=(key,fallback)=>{try{const value=localStorage.getItem(key);return value?JSON.parse(value):fallback}catch{return fallback}};
const write=(key,value)=>{try{localStorage.setItem(key,JSON.stringify(value))}catch{}};
const entryMap=new Map(data.entries.map(e=>[e.id,e])),trackMap=new Map(data.tracks.map(t=>[t.id,t]));
const saved=read(KEY,{}),requested=new URLSearchParams(location.search).get('collection');
const inferred=data.chapters.find(c=>String(c.id)===String(saved.chapter))?.collection;
if(saved.chapter&&inferred&&!read(KEY+'-collection-'+inferred,null))write(KEY+'-collection-'+inferred,{...saved,collection:inferred});
const initialCollection=data.collections.some(c=>c.id===requested)?requested:(saved.collection||inferred||'oxford3000');
const initial=data.collections.find(c=>c.id===initialCollection)||data.collections[0];
const initialPrefs=read(KEY+'-collection-'+initial.id,initial.id===(saved.collection||inferred)?saved:{});
const favorites=new Set(read(KEY+'-favorites',[])),positions=read(KEY+'-audio',{});
const state={collection:initial.id,chapter:String(initialPrefs.chapter||''),group:initialPrefs.group||'',selected:initialPrefs.selected||'',mode:initialPrefs.mode||initial.defaultMode,direction:initialPrefs.direction||'横向测试',rate:Number(saved.rate)||1,gapMs:SPEECH_GAPS.includes(Number(saved.gapMs))?Number(saved.gapMs):1000,hide:!!saved.hide,query:'',onlyFavorites:false,limit:100,track:'',cached:new Set(),cacheBusy:false};
let speechContinuous=false,voices=[];
let audioContinuous=false,scriptedPlay=false,seekGuard=null,currentBlobUrl=null,trackGeneration=0,trackLoading=false,pendingPosition=0,trackReady=Promise.resolve();
let singleWordStop=null,animationFrame=0,lastSavedTime=-10,lastCueId='';
const collection=()=>data.collections.find(c=>c.id===state.collection)||data.collections[0];
const collectionChapters=()=>data.chapters.filter(c=>c.collection===state.collection);
const chapter=()=>collectionChapters().find(c=>String(c.id)===state.chapter)||collectionChapters()[0];
const group=()=>chapter().groups.find(g=>g.id===state.group)||chapter().groups[0];
const chapterEntries=()=>data.entries.filter(e=>String(e.chapter)===state.chapter);
const groupEntries=()=>{const selectedGroup=group();return chapterEntries().filter(e=>selectedGroup.all||e.group===state.group)};
const entries=()=>groupEntries().filter(e=>(!state.onlyFavorites||favorites.has(e.id))&&(!state.query||(e.word+' '+e.meaning).toLowerCase().includes(state.query)));
const current=()=>entryMap.get(state.selected);
const chapterTracks=()=>data.tracks.filter(t=>String(t.chapter)===state.chapter&&(!t.direction||t.direction===state.direction));
const track=()=>trackMap.get(state.track);
const cues=()=>track()?.cues||[];
const selectedCueIndex=()=>cues().findIndex(c=>c.entryId===state.selected);
const status=(id,text)=>{$(id).textContent=text};
function save(){const pref={collection:state.collection,chapter:state.chapter,group:state.group,selected:state.selected,mode:state.mode,direction:state.direction,rate:state.rate,gapMs:state.gapMs,hide:state.hide};write(KEY,pref);write(KEY+'-collection-'+state.collection,pref)}
const speechQueue=StudySpeechQueue.create({
 synth:window.speechSynthesis,Utterance:window.SpeechSynthesisUtterance,
 prepare:e=>({text:(e.audioText||e.word).split('=')[0].replace(/\(s\)/g,'s').trim(),lang:'en-GB',rate:state.rate,voice:voices.find(v=>/^en-GB$/i.test(v.lang))||voices[0]||null}),
 onState:({continuous})=>{speechContinuous=continuous;$('continuous-words').classList.toggle('active',continuous);$('continuous-words').textContent=continuous?'暂停连续朗读':'▶ 连续朗读'},
 onStart:(e,{continuous})=>{selectEntry(e.id);status('speech-status',continuous?'连续朗读中 · 系统合成语音':'本词朗读中 · 系统合成语音 · 读完后暂停')},
 onGap:(e,{gapMs})=>status('speech-status',`词间停顿 ${gapMs/1000} 秒 · 可以跟读本词`),
 onFinish:({continuous})=>status('speech-status',continuous?'本组已读完，已暂停。':'本词已读完，已暂停。点击“连续朗读”可依次读词。'),
 onError:error=>status('speech-status',error==='unsupported'?'当前浏览器没有系统朗读功能，请切换到学习包音频。':['interrupted','canceled'].includes(error)?'系统朗读已暂停。点击“连续朗读”可继续。':'系统语音暂不可用。可重试，或切换到学习包音频。')
});
function stopSpeech(message){speechQueue.stop();if(message)status('speech-status',message)}
function voiceList(){if('speechSynthesis'in window)voices=speechSynthesis.getVoices().filter(v=>/^en[-_]/i.test(v.lang))}
voiceList();if('speechSynthesis'in window)speechSynthesis.addEventListener('voiceschanged',voiceList);
function speakCurrent(continuous=false){
 const e=current();if(!e)return;
 audio.pause();audioContinuous=false;singleWordStop=null;stopAnimation();
 const list=entries(),index=list.findIndex(item=>item.id===e.id);
 status('speech-status',continuous?'连续朗读中 · 系统合成语音':'本词朗读中 · 系统合成语音 · 读完后暂停');
 speechQueue.play(continuous&&index>=0?list.slice(index):[e],{continuous,gapMs:state.gapMs});
}
function normalizeSelection(){state.chapter=String(chapter().id);if(!chapter().groups.some(g=>g.id===state.group))state.group=chapter().groups[0].id;const list=entries();if(!list.some(e=>e.id===state.selected))state.selected=list[0]?.id||''}
function sourceLabel(e){return e.source==='oxford3000'?'Oxford 3000 词表':e.source==='phrases750'?'Oxford 短语词表':e.source==='pdf'?'Chapter 11 · 原书转写':e.corrected?'已按照片校订':'网络参考词表'}
function audioCredits(e){
 const sources=(e.audioCreditIds||[]).map(id=>data.audioCredits[id]).filter(Boolean);if(!sources.length)return'';
 return `<details class="audio-credit"><summary>学习包音频来源与许可</summary>${sources.map(s=>`<p>${esc(s.kind==='ai_generated'?'AI 配音':s.credit||s.artist||'真人录音')}${s.artist&&s.credit&&!s.credit.includes(s.artist)?' · '+esc(s.artist):''}${s.copyright?' · '+esc(s.copyright):''}${s.voice?' · '+esc(s.voice):''}${s.license?' · '+esc(s.license):''}${s.page_url?` · <a href="${esc(s.page_url)}" target="_blank" rel="noopener">来源页面</a>`:''}${s.license_url?` · <a href="${esc(s.license_url)}" target="_blank" rel="noopener">许可</a>`:''}${s.processing?'<br>'+esc(s.processing):''}</p>`).join('')}</details>`;
}
function renderCard(){
 const e=current(),list=entries(),i=list.findIndex(x=>x.id===state.selected);
 $('position').textContent=e?`${e.level?e.level+' · ':''}第 ${e.order} ${e.source==='phrases750'?'条':'词'} · 本组 ${groupEntries().length} 条`:'';
 $('source-label').textContent=e?sourceLabel(e):'';
 $('prev-word').disabled=!e||i<=0;$('next-word').disabled=!e||i<0||i>=list.length-1;$('replay-word').disabled=!e;$('continuous-words').disabled=!e;
 if(!e){$('word-card').innerHTML='<p class="empty">没有匹配的词条。试试其他关键词，或关闭“只看收藏”。</p>';renderAudioState();return}
 const example=e.example,tag=e.level?`${e.level} · ${e.order}`:`${group().title} · ${e.order}`;
 $('word-card').innerHTML=`<span class="source-pill">${esc(tag)}</span><button class="favorite-button ${favorites.has(e.id)?'active':''}" id="favorite-word" aria-label="${favorites.has(e.id)?'取消收藏':'收藏本词'}" aria-pressed="${favorites.has(e.id)}">${favorites.has(e.id)?'★':'☆'}</button><h1 class="word">${esc(e.word)}${e.homograph?`<sup>${esc(e.homograph)}</sup>`:''}</h1>${e.pos||e.qualifier?`<p class="word-meta">${esc([e.pos,e.qualifier].filter(Boolean).join(' · '))}</p>`:''}${e.ipa?`<div class="ipa">/${esc(e.ipa)}/${e.ipaSource==='reference'?' <small>参考音标</small>':''}</div>`:''}<div class="meaning">${state.hide?'<button id="reveal-meaning">显示中文</button>':esc(e.meaning)}</div>${e.phrases?.length?`<p class="details-label">常用搭配${e.collection==='ielts'?' · 扩展学习':''}</p><div class="phrases">${e.phrases.slice(0,4).map(p=>`<span class="phrase">${esc(p)}</span>`).join('')}</div>`:''}${example?`<p class="details-label">放进句子里${e.collection==='ielts'?' · Oxford 学习参考':''}</p><div class="example"><p>${esc(example.english)}</p>${!state.hide?`<p class="translation">${esc(example.chinese)}</p>`:''}<details><summary>例句来源</summary>${esc(example.attribution||example.source||'原创学习例句')}</details></div>`:''}${e.wordForms?`<p class="word-forms">词形参考：${esc(e.wordForms)}</p>`:''}${e.usageNote?`<p class="usage-note">用法：${esc(e.usageNote)}</p>`:''}${e.audioText&&e.audioText!==e.word?`<p class="status">音频示范：${esc(e.audioText)}</p>`:''}${e.audioNotes?.length?`<p class="status">${e.audioNotes.map(esc).join(' ')}</p>`:''}${audioCredits(e)}${e.referenceUrl?`<a class="paper-link" href="${esc(e.referenceUrl)}" target="_blank" rel="noopener">查看词典参考</a>`:''}${e.pdfPage?`<a class="paper-link" href="${esc(data.pdfHref)}#page=${e.pdfPage}" target="_blank" rel="noopener">查看原书页 · PDF 第 ${e.pdfPage} 页</a>`:''}${e.reviewNote?`<p class="status">${esc(e.reviewNote)}</p>`:''}`;
 $('favorite-word').onclick=()=>{favorites.has(e.id)?favorites.delete(e.id):favorites.add(e.id);write(KEY+'-favorites',[...favorites]);if(state.onlyFavorites){stopSpeech();normalizeSelection()}renderCard();renderList()};
 if($('reveal-meaning'))$('reveal-meaning').onclick=()=>{$('reveal-meaning').parentElement.textContent=e.meaning};
 document.querySelectorAll('.entry').forEach(el=>el.classList.toggle('current',el.dataset.id===state.selected));renderAudioState();save();
}
function renderList(){
 const list=entries();$('result-count').textContent=`${list.length.toLocaleString()} 条${state.onlyFavorites?'收藏':''}${state.query?'匹配':''}`;
 $('word-list').innerHTML=list.slice(0,state.limit).map(e=>`<button class="entry ${e.id===state.selected?'current':''}" data-id="${esc(e.id)}"><small>${e.order}</small><span><strong>${esc(e.word)}${e.homograph?' '+esc(e.homograph):''}</strong>${!state.hide?`<span class="zh">${esc(e.meaning)}</span>`:''}</span><span class="star">${favorites.has(e.id)?'★':''}</span></button>`).join('')||'<p class="empty">还没有匹配的词条。</p>';
 $('more-words').hidden=state.limit>=list.length;$('favorites-only').setAttribute('aria-pressed',String(state.onlyFavorites));
}
function renderNavigation(){
 normalizeSelection();$('collections').innerHTML=data.collections.map(c=>`<button class="collection-button" data-collection="${c.id}" aria-pressed="${c.id===state.collection}"><b>${esc(c.title)}</b><small>${esc(c.subtitle)}</small></button>`).join('');
 status('collection-note',state.collection==='oxford3000'?'保留词性、词形、搭配与双语例句。学习包音频全部为真人发音，播放时自动换词。':state.collection==='phrases750'?'750 条短语均有搭配、例句和用法提示。现有音轨含 350 条真人录音、400 条 AI 配音，每条标明来源。':'四章词表与官网真人录音。系统朗读会逐词切换；官网录音目前仍为整段播放。');
 $('chapters').hidden=state.collection!=='ielts';$('chapters').innerHTML=collectionChapters().map(c=>`<button class="chapter-button ${String(c.id)===state.chapter?'selected':''}" data-chapter="${c.id}" aria-pressed="${String(c.id)===state.chapter}"><span>CHAPTER ${c.id}</span><b>${esc(c.title)}</b></button>`).join('');
 $('group-select').innerHTML=chapter().groups.map(g=>`<option value="${esc(g.id)}">${esc(g.title)}</option>`).join('');$('group-select').value=state.group;
 $('speed').value=String(state.rate);$('speech-gap').value=String(state.gapMs);$('hide-meaning').checked=state.hide;$('direction').value=state.direction;$('direction').hidden=state.collection!=='ielts'||state.chapter==='11';
 status('recording-mode-title',state.collection==='ielts'?'原版录音':'学习包音频');status('recording-mode-subtitle',chapter().audioSubtitle||'真人整段');status('recording-heading',chapter().audioTitle||'官网真人整段录音');
 $('track-select').innerHTML=chapterTracks().map(t=>`<option value="${t.id}">${esc(t.title)}</option>`).join('');$('track-controls').hidden=state.collection!=='ielts';
 renderCard();renderList();syncTrack(false);setMode(state.mode,false);
}
function scrollCurrent(){const row=$('word-list').querySelector('.entry.current');if(!row)return;const container=$('word-list'),top=row.offsetTop-container.offsetTop;if(top<container.scrollTop||top+row.offsetHeight>container.scrollTop+container.clientHeight)container.scrollTop=Math.max(0,top-container.clientHeight*.35)}
function selectEntry(id,play=false){
 if(!entryMap.has(id))return;state.selected=id;const i=entries().findIndex(e=>e.id===id);if(i>=state.limit){state.limit=i+30;renderList()}renderCard();scrollCurrent();
 if(play){if(state.mode==='original'&&cues().length)playCue(id,true);else if(state.mode==='word')speakCurrent(false)}
}
function moveWord(offset){stopSpeech();const list=entries(),i=list.findIndex(e=>e.id===state.selected),e=list[Math.max(0,Math.min(list.length-1,i+offset))];if(e)selectEntry(e.id,true)}
function setMode(mode,stop=true){
 if(stop){stopSpeech();audio.pause();audioContinuous=false;singleWordStop=null}
 state.mode=mode;$('word-mode').classList.toggle('selected',mode==='word');$('original-mode').classList.toggle('selected',mode==='original');$('word-mode').setAttribute('aria-pressed',String(mode==='word'));$('original-mode').setAttribute('aria-pressed',String(mode==='original'));$('word-player').hidden=mode!=='word';$('original-player').hidden=mode!=='original';
 if(mode==='original'){syncTrack(false);if(stop&&cues().length&&current())seekToEntry(current().id,false)}renderAudioState();save();
}
function renderAudioState(){
 const e=current(),hasCues=!!cues().length,index=selectedCueIndex();$('recording-word-controls').hidden=!hasCues;$('audio-now-playing').hidden=!hasCues||!e;
 $('prev-recording-word').disabled=index<=0;$('next-recording-word').disabled=index<0||index>=cues().length-1;$('replay-recording-word').disabled=index<0;
 if(hasCues&&e){status('audio-now-word',e.word);status('audio-now-meaning',state.hide?'中文已遮住':e.meaning);status('audio-now-position',`${e.level} · 第 ${e.order} 条 · 音频逐词同步`)}
 const ai=hasCues&&e?.audioKind==='ai_generated';$('recording-kind').dataset.kind=ai?'ai':'human';status('recording-kind',hasCues?(!e?'请选择词条':ai?'当前词：AI 配音':'当前词：真人录音'):'官网真人录音 · 整段播放');
 $('continuous-audio').classList.toggle('active',audioContinuous&&!audio.paused);$('continuous-audio').textContent=audioContinuous&&!audio.paused?'暂停连续播放':state.collection==='ielts'?'本章连续播放':'连续播放学习包音频';
}
function db(){return new Promise((resolve,reject)=>{if(!window.indexedDB){reject(new Error('本浏览器不支持本机音频存储'));return}const r=indexedDB.open('ielts-study-audio-v1',1);r.onupgradeneeded=()=>r.result.createObjectStore('tracks');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}
async function stored(id){const database=await db();return new Promise((resolve,reject)=>{const tx=database.transaction('tracks','readonly'),r=tx.objectStore('tracks').get(id);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);tx.oncomplete=()=>database.close()})}
async function storeAudio(t,blob){const database=await db();return new Promise((resolve,reject)=>{const tx=database.transaction('tracks','readwrite');tx.objectStore('tracks').put({blob,name:t.filename,saved:Date.now()},t.id);tx.oncomplete=()=>{database.close();state.cached.add(t.id);resolve()};tx.onerror=()=>{database.close();reject(tx.error)}})}
async function cacheKeys(){try{const database=await db();const keys=await new Promise((resolve,reject)=>{const tx=database.transaction('tracks','readonly'),r=tx.objectStore('tracks').getAllKeys();r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);tx.oncomplete=()=>database.close()});state.cached=new Set(keys);renderOffline()}catch{status('offline-status','可直接播放；本浏览器暂不能保存离线音频。')}}
function renderOffline(){const t=track();$('cache-audio').disabled=state.cacheBusy||!t||state.cached.has(t.id);$('cache-audio').textContent=state.cacheBusy?'正在保存…':t&&state.cached.has(t.id)?'本段已保存到本机':'保存本段，供离线播放';status('offline-status',`已保存 ${state.cached.size} 段音频${t&&state.cached.has(t.id)?' · 当前音轨可离线播放':''}。导入与保存仅使用本机浏览器空间。`)}
function saveAudioPosition(){if(!trackLoading&&audio.dataset.track===state.track&&audio.readyState>0&&!audio.ended&&Number.isFinite(audio.currentTime)){positions[state.track]=audio.currentTime;lastSavedTime=audio.currentTime;write(KEY+'-audio',positions)}}
function loadTrack(id,autoplay=false,single=true,reset=false){
 const t=trackMap.get(id);if(!t)return Promise.resolve();saveAudioPosition();trackLoading=true;stopSpeech();audio.pause();stopAnimation();singleWordStop=null;seekGuard=null;lastCueId='';if(reset)positions[id]=0;
 pendingPosition=Number(positions[id]||0);state.track=id;const generation=++trackGeneration;if(single)audioContinuous=false;$('track-select').value=id;
 const tracks=chapterTracks(),i=tracks.findIndex(x=>x.id===id);$('prev-track').disabled=i<=0;$('next-track').disabled=i<0||i>=tracks.length-1;
 audio.removeAttribute('src');audio.load();if(currentBlobUrl){URL.revokeObjectURL(currentBlobUrl);currentBlobUrl=null}renderAudioState();
 trackReady=(async()=>{
  let local=null;try{local=await stored(id)}catch{}if(generation!==trackGeneration)return;
  if(local?.blob){currentBlobUrl=URL.createObjectURL(local.blob);audio.src=currentBlobUrl;status('audio-status','使用本机保存的学习音频。')}
  else{audio.src=location.protocol==='file:'?t.file:'/api/audio/'+encodeURIComponent(id);status('audio-status',t.cues?.length?'学习包音频已就绪 · 播放时词卡自动跟随。':'官网原版录音 · 整段播放。')}
  audio.dataset.track=id;audio.preload=t.cues?.length?'metadata':'none';audio.playbackRate=state.rate;audio.load();renderOffline();
  if(autoplay&&state.mode==='original'){scriptedPlay=true;try{await audio.play()}catch{scriptedPlay=false;status('audio-status','音频已就绪，请点击音频栏播放。')}}
 })();return trackReady;
}
function syncTrack(autoplay){const wanted=group().trackIds?.[state.direction]||group().trackIds?.default||chapterTracks()[0]?.id;if(wanted&&wanted!==state.track)return loadTrack(wanted,autoplay,true);if(state.track)$('track-select').value=state.track;return trackReady}
function setAudioTime(time){pendingPosition=time;seekGuard={target:time};try{audio.currentTime=time}catch{}}
function seekToEntry(id,play=true){const cue=cues().find(c=>c.entryId===id);if(!cue)return;setAudioTime(cue.start);lastCueId='';syncAudioWord();if(play){scriptedPlay=true;audio.play().catch(()=>{scriptedPlay=false;status('audio-status','已定位本词，请点击音频栏播放。')})}}
async function playCue(id,single=true){
 const requestedTrack=state.track;if(state.mode!=='original')return;
 if(audio.dataset.track!==requestedTrack)await trackReady;
 if(state.mode!=='original'||state.track!==requestedTrack)return;
 const t=track(),cue=t?.cues?.find(c=>c.entryId===id);if(!cue)return;
 stopSpeech();audioContinuous=!single;singleWordStop=single?{track:t.id,entryId:id,end:StudyTimeline.cueStop(cue)}:null;seekToEntry(id,true);renderAudioState();status('audio-status',single?'本词播放中 · 读完即停。':'连续播放中 · 词卡自动跟随。');
}
function moveRecordingWord(offset){const list=cues(),i=selectedCueIndex(),cue=list[Math.max(0,Math.min(list.length-1,i+offset))];if(cue){selectEntry(cue.entryId);playCue(cue.entryId,true)}}
function syncAudioWord(){
 if(state.mode!=='original'||!cues().length||trackLoading)return;const index=StudyTimeline.cueIndex(cues(),audio.currentTime),cue=cues()[index];if(!cue)return;
 if(cue.entryId!==lastCueId||state.selected!==cue.entryId){lastCueId=cue.entryId;const e=entryMap.get(cue.entryId);if(!e)return;if(!group().all&&state.group!==e.group){state.group=e.group;$('group-select').value=state.group;renderList()}selectEntry(cue.entryId)}
}
function checkSingleStop(){if(singleWordStop&&singleWordStop.track===state.track&&audio.currentTime>=singleWordStop.end){singleWordStop=null;audioContinuous=false;audio.pause();renderAudioState();status('audio-status','本词已播放完毕，已暂停。点击连续播放或音频进度条可继续。')}}
function animate(){animationFrame=0;syncAudioWord();checkSingleStop();if(!audio.paused&&!audio.ended)animationFrame=requestAnimationFrame(animate)}
function startAnimation(){if(!animationFrame)animationFrame=requestAnimationFrame(animate)}
function stopAnimation(){if(animationFrame)cancelAnimationFrame(animationFrame);animationFrame=0}
function moveTrack(offset){const tracks=chapterTracks(),i=tracks.findIndex(t=>t.id===state.track),t=tracks[Math.max(0,Math.min(tracks.length-1,i+offset))];if(t)loadTrack(t.id,true,true)}
audio.addEventListener('play',()=>{if(state.mode!=='original'){scriptedPlay=false;audio.pause();return}stopSpeech();if(!scriptedPlay){audioContinuous=true;singleWordStop=null}scriptedPlay=false;renderAudioState();status('audio-status',singleWordStop?'本词播放中 · 读完即停。':audioContinuous?'连续播放中 · '+(cues().length?'词卡自动跟随。':'官网真人整段音频。'):'本段播放中 · 结束后暂停。');startAnimation()});
audio.addEventListener('pause',()=>{saveAudioPosition();stopAnimation();renderAudioState()});
audio.addEventListener('timeupdate',()=>{syncAudioWord();checkSingleStop();if(Math.abs(audio.currentTime-lastSavedTime)>=3)saveAudioPosition()});
audio.addEventListener('loadedmetadata',()=>{trackLoading=false;setAudioTime(Math.min(pendingPosition,Math.max(0,audio.duration-.1)));syncAudioWord()});
audio.addEventListener('seeked',()=>{if(seekGuard&&Math.abs(audio.currentTime-seekGuard.target)<.35){seekGuard=null;syncAudioWord();return}seekGuard=null;if(state.mode!=='original')return;singleWordStop=null;audioContinuous=true;syncAudioWord();renderAudioState();if(audio.paused){scriptedPlay=true;audio.play().catch(()=>{scriptedPlay=false})}});
audio.addEventListener('ended',()=>{stopAnimation();if(state.mode!=='original')return;singleWordStop=null;positions[state.track]=0;write(KEY+'-audio',positions);if(audioContinuous){const list=chapterTracks(),i=list.findIndex(t=>t.id===state.track);if(i+1<list.length){loadTrack(list[i+1].id,true,false);return}}audioContinuous=false;renderAudioState();status('audio-status','本段已播放完毕，已暂停。')});
audio.addEventListener('error',()=>{trackLoading=false;status('audio-status','音频暂时无法载入。请检查网络，或导入已下载的本地 MP3。')});
$('collections').onclick=event=>{
 const button=event.target.closest('[data-collection]');if(!button||button.dataset.collection===state.collection)return;save();saveAudioPosition();stopSpeech();audio.pause();singleWordStop=null;state.collection=button.dataset.collection;
 const prefs=read(KEY+'-collection-'+state.collection,{});state.chapter=String(prefs.chapter||'');state.group=prefs.group||'';state.selected=prefs.selected||'';state.mode=prefs.mode||collection().defaultMode;state.direction=prefs.direction||'横向测试';state.query='';state.onlyFavorites=false;state.limit=100;$('search').value='';
 if(location.protocol!=='file:'){const url=new URL(location.href);url.searchParams.set('collection',state.collection);history.replaceState(null,'',url)}renderNavigation();
};
$('chapters').onclick=event=>{const button=event.target.closest('[data-chapter]');if(!button)return;stopSpeech();audio.pause();state.chapter=button.dataset.chapter;state.group='';state.query='';$('search').value='';state.limit=100;renderNavigation()};
$('group-select').onchange=()=>{stopSpeech();audio.pause();singleWordStop=null;state.group=$('group-select').value;state.selected='';state.limit=100;normalizeSelection();renderCard();renderList();syncTrack(false);if(state.mode==='original'&&cues().length&&current())seekToEntry(current().id,false)};
$('search').oninput=()=>{stopSpeech();state.query=$('search').value.trim().toLowerCase();state.limit=100;normalizeSelection();renderCard();renderList()};
$('favorites-only').onclick=()=>{stopSpeech();state.onlyFavorites=!state.onlyFavorites;normalizeSelection();renderCard();renderList()};
$('hide-meaning').onchange=()=>{state.hide=$('hide-meaning').checked;renderCard();renderList()};
$('word-list').onclick=event=>{const row=event.target.closest('[data-id]');if(row){stopSpeech();selectEntry(row.dataset.id,true)}};
$('more-words').onclick=()=>{state.limit+=100;renderList()};
$('prev-word').onclick=()=>moveWord(-1);$('next-word').onclick=()=>moveWord(1);$('replay-word').onclick=()=>speakCurrent(false);
$('continuous-words').onclick=()=>{if(speechContinuous)stopSpeech('已暂停。点击“连续朗读”可继续。');else speakCurrent(true)};
$('speed').onchange=()=>{state.rate=Number($('speed').value);audio.playbackRate=state.rate;if(speechQueue.active)speakCurrent(speechContinuous);save()};
$('speech-gap').onchange=()=>{const gap=Number($('speech-gap').value);if(!SPEECH_GAPS.includes(gap))return;state.gapMs=gap;if(speechContinuous)speakCurrent(true);save()};
$('word-mode').onclick=()=>setMode('word');$('original-mode').onclick=()=>setMode('original');
$('direction').onchange=()=>{state.direction=$('direction').value;$('track-select').innerHTML=chapterTracks().map(t=>`<option value="${t.id}">${esc(t.title)}</option>`).join('');syncTrack(false);save()};
$('track-select').onchange=()=>loadTrack($('track-select').value,false,true);
$('prev-track').onclick=()=>moveTrack(-1);$('next-track').onclick=()=>moveTrack(1);$('replay-track').onclick=()=>loadTrack(state.track,true,true,true);
$('prev-recording-word').onclick=()=>moveRecordingWord(-1);$('next-recording-word').onclick=()=>moveRecordingWord(1);$('replay-recording-word').onclick=()=>playCue(state.selected,true);
$('continuous-audio').onclick=()=>{if(audioContinuous&&!audio.paused){audioContinuous=false;singleWordStop=null;audio.pause();renderAudioState();return}singleWordStop=null;audioContinuous=true;scriptedPlay=true;audio.play().catch(()=>{scriptedPlay=false;status('audio-status','请点击音频栏播放按钮。')});renderAudioState()};
$('cache-audio').onclick=async()=>{
 const t=track();if(!t||state.cacheBusy)return;state.cacheBusy=true;renderOffline();status('offline-status',`正在保存本段音频（约 ${(t.bytes/1024/1024).toFixed(1)} MB），请保持页面打开。`);
 try{const response=await fetch(location.protocol==='file:'?t.file:'/api/audio/'+encodeURIComponent(t.id));if(!response.ok)throw new Error('下载未完成');const blob=await response.blob();if(blob.size!==t.bytes)throw new Error('音频大小不符');await storeAudio(t,blob);status('audio-status','本段音频已保存，可离线播放。')}
 catch(error){status('audio-status',error?.name==='QuotaExceededError'?'本机空间不足，未保存本段。':'保存未完成，可重试或导入已下载的 MP3。')}
 finally{state.cacheBusy=false;renderOffline()}
};
$('import-audio').onclick=()=>$('audio-files').click();
$('audio-files').onchange=async()=>{
 const files=[...$('audio-files').files];let count=0,unmatched=0;status('offline-status','正在导入到本机浏览器…');
 for(const file of files){let matches=data.tracks.filter(t=>t.bytes===file.size);if(matches.length>1)matches=matches.filter(t=>t.filename===file.name);if(matches.length!==1){unmatched++;continue}try{await storeAudio(matches[0],file);count++}catch{unmatched++}}
 $('audio-files').value='';renderOffline();status('offline-status',`已导入 ${count} 段到本机浏览器${unmatched?`，${unmatched} 个文件未匹配或空间不足`:''}。`);if(state.cached.has(state.track))loadTrack(state.track,false,true);
};
$('help-toggle').onclick=()=>{$('help').hidden=!$('help').hidden;$('help-toggle').setAttribute('aria-expanded',String(!$('help').hidden))};
window.addEventListener('pagehide',()=>{saveAudioPosition();stopSpeech()});
document.addEventListener('visibilitychange',()=>{if(document.hidden)saveAudioPosition();else if(!audio.paused){syncAudioWord();startAnimation()}});
if(location.protocol==='file:')$('file-help').hidden=false;
if(location.protocol==='https:'||location.hostname==='localhost'||location.hostname==='127.0.0.1'){
 if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').then(()=>navigator.serviceWorker.ready).then(()=>status('app-offline-status','词表已准备离线使用；音频需单独保存或导入。')).catch(()=>status('app-offline-status','可正常联网使用，当前浏览器未开启离线页面。'));
}
$('pack-count').textContent=`${data.entries.length.toLocaleString()} 条学习条目 · Oxford 3000 / 750 短语 / 雅思听力`;
renderNavigation();cacheKeys();
})();
