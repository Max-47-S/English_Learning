"""Build a self-contained, mobile-friendly player for the local MP3."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=r'''<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Oxford Phrase List 750 条短语：原序连续音频、中文释义、双语搭配与例句。">
<title>Oxford Phrase List · 原序连续听读</title>
<style>
:root{color-scheme:light;--ink:#203344;--muted:#627480;--line:#d9e3e7;--accent:#17675f;--soft:#eaf5f1;--ai:#94621e;--ai-bg:#fff2dc}*{box-sizing:border-box}body{margin:0;background:#f4f7f8;color:var(--ink);font:16px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Microsoft YaHei",sans-serif}.wrap{max-width:960px;margin:auto;padding:26px 22px 56px}h1{font-size:30px;line-height:1.25;margin:4px 0 12px;letter-spacing:-.6px}h2{font-size:21px;line-height:1.3;margin:0}p{margin:8px 0}a{color:var(--accent);text-underline-offset:3px}.eyebrow{color:var(--accent);font-size:12px;font-weight:700;letter-spacing:2px}.intro{font-size:14px;color:var(--muted)}.stats{display:flex;gap:8px;flex-wrap:wrap;margin:15px 0}.chip,.tag{display:inline-block;font-size:12px;border-radius:5px;padding:2px 8px;background:var(--soft);color:var(--accent);font-weight:600}.chip{background:#fff;border:1px solid var(--line);color:var(--muted);font-weight:400;padding:3px 10px}.tag.ai{background:var(--ai-bg);color:var(--ai)}.notice{font-size:13px;color:var(--muted)}.player{position:sticky;top:8px;z-index:2;background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 15px;box-shadow:0 6px 26px #183e4b0a;margin:18px 0}.player-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:7px;font-size:13px;color:var(--muted)}#currentTitle{color:var(--ink);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}audio{width:100%;display:block;height:40px}.tools{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-top:10px}button,select,input{font:inherit;color:var(--ink);border:1px solid #c4d4da;border-radius:7px;padding:7px 10px;background:white;min-height:39px}button{cursor:pointer}button:hover:not(:disabled){background:#f0f6f5}button:focus-visible,select:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #58a899;outline-offset:2px}button:disabled{opacity:.4;cursor:default}.tools button{font-size:14px}.tools .primary{background:var(--accent);color:#fff;border-color:var(--accent)}.tools .primary:hover{background:#10574f}.tools label{font-size:13px;color:var(--muted)}#speed{font-size:14px;padding:7px 4px;min-width:70px}#status{margin:7px 0 0}.card{border:1px solid var(--line);border-radius:12px;background:white;padding:25px;margin-bottom:22px}.card-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.phrase{font-size:32px;font-weight:700;line-height:1.35;margin:14px 0 7px;overflow-wrap:anywhere;letter-spacing:-.5px}.meaning{font-size:20px;line-height:1.5}.label{font-size:12px;color:var(--muted);font-weight:600;letter-spacing:.5px;margin-top:20px;margin-bottom:7px}.collocations{display:grid;gap:5px;font-size:15px}.collocation{display:grid;grid-template-columns:1fr 1fr;gap:16px}.translation{color:var(--muted)}.example{border-left:3px solid #84b8aa;background:#f3f8f6;border-radius:0 6px 6px 0;padding:12px 15px;margin-top:5px}.example p{margin:0 0 3px}.example p:last-child{font-size:15px;color:#57736b}.note{font-size:14px;padding:10px 12px;background:#f5f7fa;border-radius:6px;margin-top:15px}.audio-line{padding-top:15px;border-top:1px solid #e6edef;margin-top:19px;font-size:14px}.audio-line b{font-weight:500}.audio-line .tag{margin-left:6px}.source-details{font-size:12px;color:var(--muted);margin-top:9px;overflow-wrap:anywhere}.source-details summary{cursor:pointer}.source-details p{margin:5px 0}.filters{display:flex;gap:9px;flex-wrap:wrap}#search{flex:1;min-width:180px}#level{width:125px}.list-header{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:15px 0 8px}.list-header button{font-size:13px;min-height:34px;padding:5px 9px}.list{display:grid;gap:6px}.entry{display:grid;grid-template-columns:40px 1fr auto;align-items:center;gap:13px;text-align:left;width:100%;padding:11px 13px;min-height:64px;background:#fff;border:1px solid var(--line);border-radius:7px}.entry.current{background:var(--soft);border-color:#6aa89c}.entry-id{font-variant-numeric:tabular-nums;font-size:12px;color:var(--muted)}.entry-body{min-width:0}.entry strong{font-size:15px;font-weight:600;display:block;overflow-wrap:anywhere}.entry .zh{font-size:12px;color:var(--muted);display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.entry-tags{display:flex;gap:5px}.entry-tags .tag{padding:2px 5px;font-size:11px}footer{margin-top:25px;border-top:1px solid var(--line);padding-top:15px;font-size:12px;color:var(--muted)}@media(max-width:560px){.wrap{padding:19px 12px 35px}h1{font-size:27px}.card{padding:18px 16px}.phrase{font-size:28px}.meaning{font-size:18px}.collocation{grid-template-columns:1fr;gap:0}.player{padding:11px 10px;top:4px}.tools{gap:5px}.tools button{font-size:12px;padding:6px 8px;min-height:35px}#speed{font-size:12px;min-height:35px}.entry{grid-template-columns:31px 1fr auto;gap:8px;padding:9px}.entry-tags{flex-direction:column;gap:3px}.list-header{align-items:flex-start}.intro{font-size:13px}input,select{font-size:14px}.stats{gap:5px}.chip{font-size:11px}}
</style></head>
<body><main class="wrap">
<header><div class="eyebrow">OXFORD PHRASE LIST</div><h1>把短语放进句子里。</h1>
<p class="intro">750 条常用短语 · 遵循原 PDF 顺序 · 读懂、听熟，再跟着说。</p>
<div class="stats"><span class="chip">A1 → C1</span><span class="chip">__HUMAN__ 条真人</span><span class="chip">__AI__ 条 AI 补音</span><span class="chip">__DURATION__ · 含跟读停顿</span></div>
<p class="notice"><a href="OxfordPhraseList_原序学习版.md">完整学习笔记</a> · <a href="README.md">使用说明</a> · <a href="来源与许可.md">录音来源与署名</a></p></header>
<section class="player" aria-label="连续音频播放器"><div class="player-head"><span id="currentTitle"></span><span id="position"></span></div>
<audio id="audio" controls preload="metadata" src="audio/OxfordPhraseList_连续听读.mp3"></audio>
<div class="tools"><button id="prevPhrase">上一条</button><button id="nextPhrase">下一条</button><button id="replay" class="primary">重听本条</button><label>速度 <select id="speed" aria-label="播放速度"><option value="0.75">0.75×</option><option value="1" selected>1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option></select></label><button id="resume">继续上次进度</button></div>
<p id="status" class="notice" role="status">点击播放开始连续听读，每条后留 1.8 秒跟读。</p></section>
<section id="card" class="card" aria-live="polite" aria-label="当前短语详情"></section>
<section aria-label="短语目录"><div class="filters"><input id="search" type="search" aria-label="搜索英文、中文或序号" placeholder="搜索英文、中文或序号"><select id="level" aria-label="筛选级别"><option value="">全部级别</option><option>A1</option><option>A2</option><option>B1</option><option>B2</option><option>C1</option></select></div>
<p class="notice">点击条目，从这里继续听。筛选只改变目录，音频仍按完整 PDF 顺序连续播放。</p>
<div class="list-header"><span id="count" class="notice"></span><div><button id="prevPage">上一页</button> <button id="nextPage">下一页</button></div></div><div id="list" class="list"></div></section>
<footer>sb = 某人；sth = 某物或某事；X 与省略号表示可替换成分。请按“音频示范”中的实际表达跟读。<br>词头与级别来自原表；中文资料与双语例句由本学习包编写。音频为开放真人录音与明确标注的 AI 配音。</footer>
</main>
<script id="vocabulary" type="application/json">__DATA__</script>
<script id="audioSources" type="application/json">__SOURCES__</script>
<script>
'use strict';
const $=id=>document.getElementById(id),words=JSON.parse($('vocabulary').textContent),sources=JSON.parse($('audioSources').textContent);
const audio=$('audio'),card=$('card'),list=$('list'),KEY='oxford-phrase-list-pdf-v1-position',SIZE=60;
let current=0,page=0,filtered=words.map((_,i)=>i),lastSaved=-1,pendingSeek=null,interacted=false;
const speechEnds=words.map(w=>w.audio.spoken_end);
const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const human=w=>w.audio.kind==='human_recording';
function renderCard(){const w=words[current],a=w.audio,s=sources[a.source_id],isHuman=human(w);card.innerHTML=`<div class="card-meta"><span class="tag">${w.level}</span><span class="tag ${isHuman?'':'ai'}">${isHuman?'真人录音':'AI 配音'}</span><span class="notice">PDF 第 ${w.pdf_page} 页 · 第 ${w.pdf_column} 栏</span></div><h2 class="phrase">${esc(w.phrase)}</h2><p class="meaning">${esc(w.meaning_zh)}</p><p class="label">常用搭配 / 用法示范</p><div class="collocations">${w.collocations.map(c=>`<div class="collocation"><span>${esc(c.english)}</span><span class="translation">${esc(c.chinese)}</span></div>`).join('')}</div><p class="label">放进句子里</p><div class="example"><p>${esc(w.example.english)}</p><p>${esc(w.example.chinese)}</p></div>${w.usage_note?`<p class="note">${esc(w.usage_note)}</p>`:''}<div class="audio-line"><span class="notice">音频示范</span><br><b>${esc(a.audio_text)}</b> <span class="tag ${isHuman?'':'ai'}">${a.timecode} · ${isHuman?'真人':'AI'}</span></div><details class="source-details"><summary>原表附列与音频来源</summary>${w.pdf_variants.length?`<p>原表附列：${w.pdf_variants.map(esc).join('；')}</p>`:''}<p>${isHuman?'原站署名：'+esc(s.artist):'AI 语音：'+esc(s.voice)+'；语速 '+esc(s.rate)}</p>${a.notes.map(n=>'<p>'+esc(n)+'</p>').join('')}<p><a href="来源与许可.md#source-${a.source_id}">查看该录音的来源与许可</a> · 原创双语学习例句</p></details>`;
$('currentTitle').textContent=w.phrase;$('position').textContent=`${w.id} / ${words.length}`;$('prevPhrase').disabled=current===0;$('nextPhrase').disabled=current===words.length-1;
document.querySelectorAll('.entry').forEach(el=>el.classList.toggle('current',Number(el.dataset.index)===current));}
function renderList(){const start=page*SIZE,ids=filtered.slice(start,start+SIZE);list.innerHTML=ids.length?ids.map(i=>{const w=words[i];return `<button class="entry ${i===current?'current':''}" data-index="${i}"><span class="entry-id">${String(w.id).padStart(3,'0')}</span><span class="entry-body"><strong>${esc(w.phrase)}</strong><span class="zh">${esc(w.meaning_zh)}</span></span><span class="entry-tags"><span class="tag">${w.level}</span><span class="tag ${human(w)?'':'ai'}">${human(w)?'真人':'AI'}</span></span></button>`}).join(''):'<p class="notice">没有匹配的条目，试试更短的关键词。</p>';$('count').textContent=`${filtered.length} 条 · 第 ${filtered.length?page+1:0} / ${Math.ceil(filtered.length/SIZE)} 页`;$('prevPage').disabled=page===0;$('nextPage').disabled=start+SIZE>=filtered.length;}
function filter(){const q=$('search').value.trim().toLowerCase(),level=$('level').value;filtered=words.map((_,i)=>i).filter(i=>{const w=words[i];return(!level||w.level===level)&&(!q||String(w.id)===q||[w.phrase,w.meaning_zh,...w.collocations.flatMap(c=>[c.english,c.chinese])].some(x=>x.toLowerCase().includes(q)))});page=0;renderList();}
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
function jump(i,autoplay=true,single=singleIndex!==null){interacted=true;current=Math.max(0,Math.min(words.length-1,i));setPlaybackMode(single?current:null);seekAudio(words[current].audio.start+.001);renderCard();try{history.replaceState(null,'','#phrase-'+words[current].id)}catch{}if(autoplay)playAudio();}
function indexAt(t){let lo=0,hi=words.length-1;while(lo<hi){const m=Math.ceil((lo+hi)/2);if(words[m].audio.start<=t)lo=m;else hi=m-1}return lo;}
function saved(){try{const x=Number(localStorage.getItem(KEY)||0);return Number.isFinite(x)?Math.max(0,Math.min(x,words[words.length-1].audio.end-.1)):0}catch{return 0}}
function savePosition(){if(!interacted)return;try{localStorage.setItem(KEY,String(audio.currentTime))}catch{}}
audio.addEventListener('loadedmetadata',()=>{if(pendingSeek!==null){const t=pendingSeek;pendingSeek=null;seekAudio(t)}$('status').textContent='完整音频已就绪。上一条、下一条和重听会在本条读完后暂停。'});
audio.addEventListener('timeupdate',()=>{checkSingleBoundary();const i=singleIndex===null?indexAt(audio.currentTime):singleIndex;if(i!==current){current=i;renderCard()}const n=Math.floor(audio.currentTime/2);if(n!==lastSaved){savePosition();lastSaved=n}});
audio.addEventListener('error',()=>{$('status').textContent='音频未能载入。请保留本页和 audio 文件夹的位置；也可按使用说明通过本地网页服务打开。'});
audio.addEventListener('ended',()=>{$('status').textContent='已听完全部 750 条。可以选择任意条目重新开始。'});
list.addEventListener('click',e=>{const item=e.target.closest('.entry');if(item)jump(Number(item.dataset.index))});
$('prevPhrase').onclick=()=>jump(current-1,true,true);$('nextPhrase').onclick=()=>jump(current+1,true,true);$('replay').onclick=()=>jump(current,true,true);
$('speed').onchange=()=>{audio.playbackRate=Number($('speed').value)};$('resume').onclick=()=>{const t=saved();jump(indexAt(t),false,false);seekAudio(t);playAudio()};
$('search').oninput=filter;$('level').onchange=filter;$('prevPage').onclick=()=>{page--;renderList()};$('nextPage').onclick=()=>{page++;renderList()};
function fromHash(){const m=location.hash.match(/^#phrase-([0-9]+)$/);if(m)jump(Number(m[1])-1,false)}
renderCard();renderList();fromHash();window.addEventListener('hashchange',fromHash);window.addEventListener('pagehide',savePosition);
</script></body></html>'''

def main():
    data=json.loads((ROOT/'data/vocabulary.json').read_text(encoding='utf-8'))
    timeline=json.loads((ROOT/'data/audio_timeline.json').read_text(encoding='utf-8'))
    payload=lambda value:json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    duration=int(timeline['duration_seconds']);clock=f'{duration//60:02d}:{duration%60:02d}'
    text=TEMPLATE.replace('__DATA__',payload(data)).replace('__SOURCES__',payload(timeline['sources'])).replace('__HUMAN__',str(timeline['human_entries'])).replace('__AI__',str(timeline['ai_entries'])).replace('__DURATION__',clock)
    (ROOT/'连续听读.html').write_text(text,encoding='utf-8')
    print('PLAYER_COMPLETE',len(data),flush=True)

if __name__=='__main__':main()
