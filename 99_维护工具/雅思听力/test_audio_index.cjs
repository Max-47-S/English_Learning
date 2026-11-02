'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {pathToFileURL}=require('node:url');
const {wrapOriginal,isIndexed}=require('./web/mp3-index.js');
const root=path.resolve(__dirname,'../..'),materials=path.join(root,'05_听力与歌曲/雅思王听力语料库');
const data=JSON.parse(fs.readFileSync(path.join(materials,'data/mobile_study.json'),'utf8'));
const sha=value=>crypto.createHash('sha256').update(value).digest('hex');
(async()=>{
 const {parseRange,spliceAudio}=await import(pathToFileURL(path.join(__dirname,'web/audio-range.ts')));
 for(const track of data.tracks.filter(t=>t.mp3Index)){
  const index=track.mp3Index,original=fs.readFileSync(path.join(materials,track.file));
  const prefix=Buffer.from(index.prefixBase64,'base64');
  const indexed=Buffer.concat([prefix,original.subarray(index.sourceOffset,index.sourceOffset+index.bodyBytes)]);
  assert.equal(indexed.length,index.bytes);assert.equal(sha(indexed),index.sha256);
  assert.ok(prefix.includes(Buffer.from('Info'))||prefix.includes(Buffer.from('Xing')),'accurate MP3 seek index');
  if(track.id!=='c3-h01')continue;
  const blob=wrapOriginal(new Blob([original]),index);
  assert.equal(sha(Buffer.from(await blob.arrayBuffer())),index.sha256);
  assert.equal(await isIndexed(blob,index),true);assert.equal(await isIndexed(new Blob([original]),index),false);
  for(const request of [null,'bytes=0-0',`bytes=${prefix.length-3}-${prefix.length+17}`,'bytes=10000-10512','bytes=-128','bytes=10000-',`bytes=-${index.bytes+200}`]){
   const range=parseRange(request,index.bytes);assert.ok(range);
   const {start,end}=range,head=start<prefix.length?prefix.subarray(start,Math.min(end+1,prefix.length)):Buffer.alloc(0);
   const bodyStart=Math.max(start,prefix.length),length=Math.max(0,end-bodyStart+1);
   const originalStart=index.sourceOffset+bodyStart-prefix.length;
   // Test both a Range-respecting origin and one that sends a full 200 body.
   for(const ignoresRange of [false,true]){
    const bytes=ignoresRange?original:original.subarray(originalStart,originalStart+length);
    const stream=spliceAudio(head,new Blob([bytes]).stream(),ignoresRange?originalStart:0,length);
    const actual=Buffer.from(await new Response(stream).arrayBuffer());
    assert.deepEqual(actual,indexed.subarray(start,end+1));
   }
  }
 }
 for(const value of ['bytes=-','bytes=-0','bytes=9-1','bytes=999-','bytes=0-1,2-3','bytes=Infinity-'])assert.equal(parseRange(value,100),null);
 assert.equal(parseRange('bytes=0-999',100).end,99);
 await assert.rejects(new Response(spliceAudio(new Uint8Array(),new Blob([new Uint8Array(2)]).stream(),0,4)).arrayBuffer(),/Incomplete/);
 console.log('PASS: 59 lossless MP3 index reconstructions, original frame hashes, imported blobs, prefix/body/suffix ranges, ignored ranges, and truncated streams.');
})().catch(error=>{console.error(error);process.exitCode=1});
