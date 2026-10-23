"""Build an offline, phone-friendly index for the continuous audiobook."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

TEMPLATE=r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oxford 3000 · 原序连续听读</title>
<style>
:root{color-scheme:light;--ink:#203344;--muted:#5e7180;--line:#dae2e8;--accent:#17635c;--soft:#eef6f4}*{box-sizing:border-box}body{margin:0;background:#f6f7f9;color:var(--ink);font:16px/1.65 system-ui,-apple-system,"Microsoft YaHei",sans-serif}.wrap{max-width:900px;margin:auto;padding:22px 18px 60px}h1{font-size:27px;line-height:1.3;margin:0 0 8px}h2{font-size:20px;margin:0}p{margin:8px 0}.muted{color:var(--muted);font-size:14px}.player{position:sticky;top:0;z-index:2;background:#fff;padding:14px 16px;border:1px solid var(--line);border-radius:14px;box-shadow:0 4px 20px #20334408;margin:18px 0}audio{display:block;width:100%;height:42px}.tools{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-top:10px}button,select,input{font:inherit;border:1px solid #c6d2d9;border-radius:8px;background:#fff;padding:7px 11px;color:var(--ink)}button{cursor:pointer}button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}button:disabled{opacity:.45;cursor:default}button:hover:not(:disabled){filter:brightness(.96)}input{min-width:140px;flex:1}select{max-width:130px}a{color:var(--accent)}.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px;margin-bottom:20px}.word{font-size:30px;font-weight:700;margin:0}.tag{display:inline-block;background:var(--soft);color:var(--accent);font-size:13px;padding:2px 8px;border-radius:6px}.meaning{font-size:19px}.phrases{font-size:15px}.example{padding:12px 14px;background:#f4f7fa;border-radius:8px;margin-top:10px}.example p{margin:2px 0}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.list{margin-top:12px;display:grid;gap:5px}.entry{display:grid;grid-template-columns:52px 1fr auto;gap:10px;text-align:left;align-items:center;border:1px solid var(--line);padding:9px 12px;border-radius:8px;width:100%}.entry.current{background:var(--soft);border-color:var(--accent)}.entry small{color:var(--muted)}.entry .zh{font-size:13px;color:var(--muted);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:580px}.row{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:14px 0}.notice{font-size:13px;color:var(--muted)}@media(max-width:540px){.wrap{padding:16px 12px 40px}.card{padding:16px}.player{padding:10px}.word{font-size:27px}.entry{grid-template-columns:40px 1fr auto;gap:7px}.entry .zh{max-width:210px}button,select,input{font-size:14px}.tools{gap:6px}}
</style></head><body><main class="wrap">
<h1>Oxford 3000 · 原序连续听读</h1>
<p class="muted">3,306 个 PDF 学习条目 · 真人录音拼接 · 英文词头＋跟读停顿</p>
<p class="notice">将本页与 audio 文件夹保存在同一目录，直接用浏览器打开即可。不同朗读者的口音有所不同。<a href="README.md">使用说明</a> · <a href="来源与许可.md">来源与署名</a></p>
<div class="player"><audio id="audio" controls preload="metadata" src="audio/Oxford3000_完整连续真人音频.mp3"></audio>
<div class="tools"><button id="prevWord">上一词</button><button id="nextWord">下一词</button><button id="replay">重听本词</button><label>速度 <select id="speed"><option value="0.75">0.75×</option><option value="1" selected>1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option></select></label><button id="resume">继续上次进度</button></div><p class="notice" id="status" role="status">音频正在载入；点击播放开始连续听读。</p></div>
<section id="card" class="card" aria-live="polite"></section>
<div class="controls"><input id="search" aria-label="搜索单词或中文" placeholder="搜索单词、中文或序号"><select id="level" aria-label="筛选级别"><option value="">全部级别</option><option>A1</option><option>A2</option><option>B1</option><option>B2</option></select></div>
<p class="notice">点击词条即可从该词继续播放。筛选只改变列表，连续音频仍按完整 PDF 顺序播放。</p>
<div class="row"><span id="count" class="muted"></span><div><button id="prevPage">上一页</button> <button id="nextPage">下一页</button></div></div>
<div id="list" class="list"></div>
</main><script type="application/json" id="vocabulary">__DATA__</script>
<script>
'use strict';
const words=JSON.parse(document.getElementById('vocabulary').textContent);
const audio=document.getElementById('audio'), card=document.getElementById('card'), list=document.getElementById('list');
const $=id=>document.getElementById(id);let current=0,page=0,filtered=words.map((_,i)=>i),lastSaved=-1,pendingSeek=null;
const escapeHtml=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const saved=()=>{try{return Number(localStorage.getItem('oxford3000-pdf-position')||0)}catch{return 0}};
function renderCard(){const w=words[current];card.innerHTML=`<span class="tag">${escapeHtml(w.level)} · ${w.id} / 3306 · PDF 第 ${w.pdf_page} 页</span><p class="word">${escapeHtml(w.word)}<sup>${escapeHtml(w.homograph||'')}</sup></p><p class="muted">${escapeHtml(w.pos)}${w.qualifier?' · '+escapeHtml(w.qualifier):''}</p><p class="meaning">${escapeHtml(w.meaning_zh)}</p><p class="phrases">${w.phrases.map(escapeHtml).join('；')}</p><div class="example"><p>${escapeHtml(w.example.english)}</p><p>${escapeHtml(w.example.chinese)}</p></div>${w.word_forms?'<p class="muted">词形参考：'+escapeHtml(w.word_forms)+'</p>':''}${w.audio.notes.length?'<p class="notice">发音提示：'+w.audio.notes.map(escapeHtml).join(' ')+'</p>':''}<p class="notice">真人录音 · ${escapeHtml(w.audio.timecode)}${w.example.source==='原创学习例句'?' · 原创学习例句':` · <a href="来源与许可.md#example-${String(w.id).padStart(4,'0')}">例句署名</a>`}</p>`;$('prevWord').disabled=current===0;$('nextWord').disabled=current===words.length-1;document.querySelectorAll('.entry').forEach(el=>el.classList.toggle('current',Number(el.dataset.index)===current));}
function renderList(){const start=page*80,ids=filtered.slice(start,start+80);list.innerHTML=ids.map(i=>{const w=words[i];return `<button class="entry ${i===current?'current':''}" data-index="${i}"><small>${String(w.id).padStart(4,'0')}</small><span><strong>${escapeHtml(w.word)}</strong> <small>${escapeHtml(w.pos)}</small><span class="zh">${escapeHtml(w.meaning_zh)}</span></span><span class="tag">${w.level}</span></button>`}).join('');$('count').textContent=`${filtered.length} 条 · 第 ${filtered.length?page+1:0} / ${Math.ceil(filtered.length/80)} 页`;$('prevPage').disabled=page===0;$('nextPage').disabled=start+80>=filtered.length;}
function filter(){const q=$('search').value.trim().toLowerCase(),level=$('level').value;filtered=words.map((_,i)=>i).filter(i=>{const w=words[i];return (!level||w.level===level)&&(!q||w.word.toLowerCase().includes(q)||w.meaning_zh.includes(q)||String(w.id)===q)});page=0;renderList();}
function jump(i,play=true){current=Math.max(0,Math.min(words.length-1,i));const t=words[current].audio.start;if(audio.readyState>0){audio.currentTime=t+.001}else{pendingSeek=t+.001}renderCard();history.replaceState(null,'','#word-'+words[current].id);if(play)audio.play().catch(()=>{$('status').textContent='已定位。请点击音频的播放按钮。'});}
function indexAt(time){let lo=0,hi=words.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(words[mid].audio.start<=time)lo=mid;else hi=mid-1}return lo;}
audio.addEventListener('loadedmetadata',()=>{if(pendingSeek!==null){audio.currentTime=pendingSeek;pendingSeek=null}$('status').textContent='已载入完整真人音频。可播放、调速或点击词条定位。'});
audio.addEventListener('timeupdate',()=>{const i=indexAt(audio.currentTime);if(i!==current){current=i;renderCard()}const n=Math.floor(audio.currentTime/2);if(n!==lastSaved){try{localStorage.setItem('oxford3000-pdf-position',String(audio.currentTime))}catch{}lastSaved=n}});
audio.addEventListener('error',()=>{$('status').textContent='未找到音频。请保留本页与 audio 文件夹的相对位置，再用浏览器打开。'});
list.addEventListener('click',event=>{const item=event.target.closest('.entry');if(item)jump(Number(item.dataset.index))});
$('prevWord').onclick=()=>jump(current-1);$('nextWord').onclick=()=>jump(current+1);$('replay').onclick=()=>jump(current);$('speed').onchange=()=>{audio.playbackRate=Number($('speed').value)};
$('resume').onclick=()=>{const time=saved();jump(indexAt(time),false);if(audio.readyState>0)audio.currentTime=time;else pendingSeek=time;audio.play().catch(()=>{})};
$('search').oninput=filter;$('level').onchange=filter;$('prevPage').onclick=()=>{page--;renderList()};$('nextPage').onclick=()=>{page++;renderList()};
function fromHash(){const match=location.hash.match(/^#word-([0-9]+)$/);if(match)jump(Number(match[1])-1,false)}
renderCard();renderList();fromHash();window.addEventListener('hashchange',fromHash);
</script></body></html>
'''


if __name__=='__main__':
    data=json.loads((ROOT/'data/vocabulary.json').read_text(encoding='utf-8'))
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    (ROOT/'连续听读.html').write_text(TEMPLATE.replace('__DATA__',payload),encoding='utf-8')
    print('PLAYER_COMPLETE',len(data),flush=True)
