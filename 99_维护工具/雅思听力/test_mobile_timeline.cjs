const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {cueIndex,cueStop}=require('./web/timeline-core.js');
const root=path.resolve(__dirname,'../..');
const data=JSON.parse(fs.readFileSync(path.join(root,'05_听力与歌曲/雅思王听力语料库/data/mobile_study.json'),'utf8'));
const oxford=data.tracks.find(t=>t.id==='oxford3000-recording');
const phrases=data.tracks.find(t=>t.id==='phrases750-recording');
assert.equal(data.entries.length,9625);assert.equal(data.tracks.length,61);
assert.equal(oxford.cues.length,3306);assert.equal(phrases.cues.length,750);
assert.equal(cueIndex(oxford.cues,-.1),-1);
assert.equal(cueIndex(oxford.cues,0),0);
assert.equal(cueIndex(oxford.cues,2.61928),0);
assert.equal(cueIndex(oxford.cues,2.61929),1);
assert.equal(cueIndex(oxford.cues,7425),3305);
assert.ok(cueStop(oxford.cues[0])>1.41929&&cueStop(oxford.cues[0])<1.50);
for(const track of [oxford,phrases]){
 const matched=data.entries.filter(e=>String(e.chapter)===String(track.chapter));
 assert.equal(new Set(track.cues.map(c=>c.entryId)).size,matched.length);
 for(let index=0;index<track.cues.length;index++){
  const cue=track.cues[index];assert.equal(cue.entryId,matched[index].id);
  assert.equal(cueIndex(track.cues,cue.start),index);
  assert.equal(cueIndex(track.cues,Math.max(cue.start,cue.spokenEnd-.01)),index);
  assert.ok(cueStop(cue)<cue.end);
  for(const id of matched[index].audioCreditIds)assert.ok(data.audioCredits[id]);
 }
}
assert.equal(data.entries.filter(e=>e.collection==='oxford3000'&&e.audioKind==='human_recording').length,3306);
assert.equal(data.entries.filter(e=>e.collection==='phrases750'&&e.audioKind==='human_recording').length,350);
assert.equal(data.entries.filter(e=>e.collection==='phrases750'&&e.audioKind==='ai_generated').length,400);
const ielts=data.tracks.filter(t=>[3,4,5,11].includes(t.chapter));
assert.equal(ielts.length,59);assert.equal(ielts.reduce((n,t)=>n+t.cues.length,0),8620);
const entryMap=new Map(data.entries.map(e=>[e.id,e]));
for(const track of ielts){
 assert.ok(track.mp3Index.audioFramesUnchanged);assert.equal(track.playbackBytes,track.mp3Index.bytes);
 assert.equal(track.aiEntries,0);assert.equal(track.humanEntries,track.cues.length);
 const groups=new Set(data.chapters.flatMap(c=>c.groups.filter(g=>Object.values(g.trackIds).includes(track.id)).map(g=>g.id)));
 const expected=data.entries.filter(e=>groups.has(e.group));
 assert.equal(track.cues.length,expected.length);assert.equal(new Set(track.cues.map(c=>c.entryId)).size,expected.length);
 for(let i=0;i<track.cues.length;i++){
  const cue=track.cues[i];assert.ok(entryMap.has(cue.entryId));
  assert.ok(cue.start<cue.spokenEnd&&cue.spokenEnd<=cue.end&&cue.end<=track.duration+.001);
  assert.equal(cueIndex(track.cues,cue.start),i);
  assert.equal(cueIndex(track.cues,(cue.spokenEnd+cue.end)/2),i,'keep card through the real recording gap');
  assert.ok(cueStop(cue)<=cue.spokenEnd+.056);
  if(i){assert.ok(track.cues[i-1].end<=cue.start+.001)}
 }
 assert.ok(track.url.includes('560f3d2b7b475dff5657631b4f16fc60939f6b36'));
}
const words=id=>data.tracks.find(t=>t.id===id).cues.map(c=>entryMap.get(c.entryId).word);
assert.deepEqual(words('c3-h01').slice(0,3),['ability','abstract','accountant']);
assert.deepEqual(words('c3-v01').slice(0,3),['ability','acid','adult']);
assert.deepEqual(words('c5-v01').slice(0,3),['a great variety of','a pair of glasses','a series of']);
assert.deepEqual(words('c5-v12').slice(0,3),['abbreviation','affair','recommendation']);
assert.deepEqual(words('c5-v09').slice(6,10),['recreation therapy','Red Flag','reference books','refresher course']);
assert.equal(words('c11-01')[0],'caravan');assert.equal(words('c11-07')[0],'code');
assert.ok(words('c11-08').includes('rubber-wood furniture business'));
assert.ok(words('c11-08').includes('digital marketing service providers'));
assert.ok(!words('c11-08').includes('business'));
assert.equal(words('c11-08').length,470);
assert.equal(data.entryAliases['c11-s4-phrases-0447'],'c11-s4-phrases-0445');
assert.equal(data.entryAliases['c11-s4-phrases-0456'],'c11-s4-phrases-0454');
assert.equal(entryMap.has('c11-s4-phrases-0447'),false);
assert.equal(entryMap.has('c11-s4-phrases-0456'),false);
console.log('PASS: 12,676 cues in 61 tracks; four IELTS chapters; row/column orders, complete wrapped phrases, recording gaps, and single-word stops.');
