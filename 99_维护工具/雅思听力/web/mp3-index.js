(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudyMP3Index=api})(globalThis,function(){
'use strict';
function prefix(index){return Uint8Array.from(atob(index.prefixBase64),c=>c.charCodeAt(0))}
function wrapOriginal(blob,index){return new Blob([prefix(index),blob.slice(index.sourceOffset,index.sourceOffset+index.bodyBytes)],{type:'audio/mpeg'})}
async function isIndexed(blob,index){const head=prefix(index);if(blob.size!==index.bytes)return false;const bytes=new Uint8Array(await blob.slice(0,head.length).arrayBuffer());return head.every((byte,i)=>bytes[i]===byte)}
return{prefix,wrapOriginal,isIndexed};
});
