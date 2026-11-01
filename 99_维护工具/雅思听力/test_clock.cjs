'use strict';
class FakeClock{
 constructor(){this.now=0;this.nextId=1;this.timers=new Map()}
 set=(fn,delay)=>{const id=this.nextId++;this.timers.set(id,{fn,at:this.now+delay});return id};
 clear=id=>this.timers.delete(id);
 advance(ms){
  const target=this.now+ms;
  for(;;){
   const next=[...this.timers].sort((a,b)=>a[1].at-b[1].at).find(([,t])=>t.at<=target);
   if(!next)break;
   this.now=next[1].at;this.timers.delete(next[0]);next[1].fn();
  }
  this.now=target;
 }
}
module.exports={FakeClock};
