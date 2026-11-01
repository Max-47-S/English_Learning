const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {cueIndex,cueStop}=require('./web/timeline-core.js');
const root=path.resolve(__dirname,'../..');
const data=JSON.parse(fs.readFileSync(path.join(root,'05_听力与歌曲/雅思王听力语料库/data/mobile_study.json'),'utf8'));
const oxford=data.tracks.find(t=>t.id==='oxford3000-recording');
const phrases=data.tracks.find(t=>t.id==='phrases750-recording');
assert.equal(data.entries.length,9627);assert.equal(data.tracks.length,61);
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
console.log('PASS: 4,056 recording cues, exact boundaries, single-word stops, source credits, and human/AI labels.');
