(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.StudyTimeline=api})(globalThis,function(){
'use strict';
function cueIndex(cues,time){let lo=0,hi=cues.length;while(lo<hi){const mid=(lo+hi)>>1;if(cues[mid].start<=time)lo=mid+1;else hi=mid}return lo-1}
function cueStop(cue){return Math.min(cue.end,cue.spokenEnd+.055)}
return{cueIndex,cueStop};
});
