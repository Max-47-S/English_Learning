import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import {fileURLToPath} from "node:url";
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const dataFile=path.join(root,"data/母句.json");
const b=JSON.parse(fs.readFileSync(dataFile,"utf8"));
const readJSON=p=>JSON.parse(fs.readFileSync(p,"utf8"));
const wordFile=path.resolve(path.dirname(dataFile),b.sourceFiles.words);
const phraseFile=path.resolve(path.dirname(dataFile),b.sourceFiles.phrases);
const words=readJSON(wordFile),phrases=readJSON(phraseFile);
const phraseMap=new Map(phrases.map(p=>[p.id,p]));
const norm=s=>s.toLowerCase().replace(/[’‘]/g,"'").replace(/\s+/g," ").trim();
const head=s=>norm(s).replace(/[¹²³⁴⁵⁶⁷⁸⁹⁰]/g,"").trim();
const aliases={realise:["realize"],realize:["realise"],neighbour:["neighbor"],neighbor:["neighbour"],practise:["practice"],practice:["practise"],centre:["center"],center:["centre"]};
const esc=s=>String(s).replace(/\|/g,"\\|").replace(/\n/g," ");
const pad=n=>String(n).padStart(3,"0");
const main="01_120句母体详解.md";
const mlink=id=>"["+id+"]("+main+"#"+id.toLowerCase()+")";
const unique=a=>[...new Set(a)];
const write=(file,text)=>fs.writeFileSync(path.join(root,file),text.trimEnd()+"\n","utf8");
const lines=b.scenes.flatMap(s=>s.lines);
const allItems=[...lines,...b.tools];
const errors=[];
const keywordIndex=new Map(),phraseIndex=new Map(),grammarIndex=new Map();
const resolveWord=k=>{
 const direct=words.filter(w=>head(w.word)===head(k.lemma)||head(w.lookup)===head(k.lemma));
 if(direct.length)return direct;
 const names=aliases[head(k.lemma)]||[];
 return words.filter(w=>names.includes(head(w.word))||names.includes(head(w.lookup)));
};
for(const scene of b.scenes){
 if(scene.lines.length!==4)errors.push("D"+scene.id+" 不是四轮");
 for(const [i,l] of scene.lines.entries()){
  const expected="M"+pad((scene.id-1)*4+i+1);
  if(l.id!==expected)errors.push("编号不连续："+l.id);
  if(l.transfers.length!==2)errors.push(l.id+" 缺迁移例句");
  for(const g of l.grammar){
   if(!b.grammar[g])errors.push(l.id+" 未知语法："+g);
   if(!grammarIndex.has(g))grammarIndex.set(g,[]);
   grammarIndex.get(g).push(l.id);
  }
  for(const k of l.keywords){
   const found=resolveWord(k);
   if(!found.length)errors.push(l.id+" 词头未匹配："+k.lemma);
   if(!norm(l.english).includes(norm(k.surface)))errors.push(l.id+" 词形未出现："+k.surface);
   const key=found.length?head(found[0].word):head(k.lemma);
   if(!keywordIndex.has(key))keywordIndex.set(key,{lemma:found[0]?.word||k.lemma,entries:found,uses:[]});
   keywordIndex.get(key).uses.push({id:l.id,surface:k.surface});
  }
 }
}
for(const l of allItems){
 for(const use of l.phraseUses){
  const p=phraseMap.get(use.id);
  if(!p)errors.push(l.id+" 未知短语编号："+use.id);
  if(!norm(l.english).includes(norm(use.surface)))errors.push(l.id+" 短语用法未出现："+use.surface);
  if(!phraseIndex.has(use.id))phraseIndex.set(use.id,{entry:p,uses:[]});
  phraseIndex.get(use.id).uses.push({id:l.id,surface:use.surface});
 }
}
if(lines.length!==120||b.scenes.length!==30)errors.push("母句或场景数量错误");
if(new Set(lines.map(l=>norm(l.english))).size!==lines.length)errors.push("母句出现完全重复");
if(grammarIndex.size!==Object.keys(b.grammar).length)errors.push("有未使用的语法标签");
if(errors.length)throw new Error(errors.join("\n"));
const corePhraseIds=new Set(lines.flatMap(l=>l.phraseUses.map(p=>p.id)));
const phraseLevels={};
for(const {entry:p} of phraseIndex.values())phraseLevels[p.level]=(phraseLevels[p.level]||0)+1;
const extraLink=id=>id.startsWith("E")?"["+id+"](05_接话工具条.md#"+id.toLowerCase()+")":mlink(id);
const totalTransfers=lines.reduce((n,l)=>n+l.transfers.length,0);
let text="# 日常对话母体 · 120 个可迁移话轮\n\n";
text+="编写日期："+b.createdDate+"。30 段原创四轮对话，120 个编号母句，"+totalTransfers+" 个换话题例句，另配 20 个接话工具句。\n\n";
text+="每段对话是独立的练习情境。A、B 不限定性别或真实身份。编号按可练习的话轮划分，包含并列分句和自然省略式回答。\n\n";
text+="读法：先看四轮问答，再选一个编号看骨架和迁移。起步、巩固、扩展是本包练习顺序，不是整句的官方 CEFR 评级。\n\n## 场景目录\n\n| 场景 | 练什么 | 顺序 |\n| --- | --- | --- |\n";
for(const s of b.scenes){
 const d="D"+String(s.id).padStart(2,"0");
 const anchor=(d+" "+s.title).toLowerCase().replace(/[^\p{L}\p{N}\p{M}_\-\s]/gu,"").replace(/\s/g,"-");
 text+="| ["+d+" "+s.title+"](#"+anchor+") | "+s.goal+" | "+s.priority+" |\n";
}
for(const s of b.scenes){
 const d="D"+String(s.id).padStart(2,"0");
 text+="\n## "+d+" "+s.title+"\n\n**交际目标：**"+s.goal+"\n\n| 编号 | 角色 | 英文 | 中文 |\n| --- | --- | --- | --- |\n";
 for(const l of s.lines)text+="| "+l.id+" | "+l.speaker+" | "+esc(l.english)+" | "+esc(l.chinese)+" |\n";
 for(const l of s.lines){
  const phraseText=l.phraseUses.length?l.phraseUses.map(u=>{const p=phraseMap.get(u.id);return "**"+p.phrase+"** → "+u.surface;}).join("；"):"本句侧重句式，词汇见下方重点词。";
  text+="\n### "+l.id+"\n\n**骨架：** "+l.frame+"\n\n**注意：** "+l.tip+"\n\n**语法：** "+l.grammar.map(g=>b.grammar[g].label).join("；")+"\n\n**词块对照：** "+phraseText+"\n\n**重点词：** "+l.keywords.map(k=>k.lemma+(norm(k.lemma)!==norm(k.surface)?" → "+k.surface:"")).join(" · ")+"\n\n";
  for(const [i,t] of l.transfers.entries())text+="**迁移 "+(i+1)+"：** "+t.english+"  \n"+t.chinese+"\n\n";
 }
}
write(main,text);
text="# 纯对话跟读稿\n\n这里只保留英文话轮。先与搭档轮流读，再遮住主文件里的英文、按中文意思复述。遇到不懂的句式，按编号返回[母句详解]("+main+")。\n\n";
for(const s of b.scenes){
 text+="## D"+String(s.id).padStart(2,"0")+" "+s.title+"\n\n";
 for(const l of s.lines)text+="**"+l.speaker+" · "+l.id+"**  \n"+l.english+"\n\n";
}
write("02_纯对话跟读稿.md",text);
text="# 句式地图与变形练习\n\n下面的 "+grammarIndex.size+" 项是本包的教学观察标签，彼此可能交叉；不是声称已经覆盖全部英语语法。每个标签都对应实际母句。\n\n";
text+="## 按表达需求找母句\n\n| 想做什么 | 可以先练 |\n| --- | --- |\n";
const needs=[
["问发生什么、怎么处理",["M001","M003","M053"]],
["问平时怎么做",["M005","M007"]],
["问当前活动与提供帮助",["M009","M011","M012"]],
["问数量、作比较",["M017","M019","M041","M042"]],
["邀请、请求与商量",["M025","M027","M037","M038"]],
["说过去与持续到现在的经历",["M049","M057","M061","M065"]],
["说条件、假设与复盘",["M073","M077","M079","M083"]],
["交代进度与转述",["M085","M088","M090","M092"]],
["描述人或物",["M093","M094","M095","M096"]],
["没听懂时继续聊",["M101","M102","M103","M104"]],
["表达感受与共同决定",["M109","M113","M117","M119"]]
];
for(const [need,ids] of needs)text+="| "+need+" | "+ids.map(mlink).join(" · ")+" |\n";
text+="\n## 逐项语法地图\n\n| 观察点 | 提醒 | 母句 |\n| --- | --- | --- |\n";
for(const [g,ids] of grammarIndex){
 const item=b.grammar[g];
 text+="| "+item.label+" | "+item.note+" | "+unique(ids).map(mlink).join(" · ")+" |\n";
}
text+="\n"+fs.readFileSync(path.join(root,"data/练习说明.md"),"utf8");
write("03_句式地图与变形练习.md",text);
text="# Oxford 词汇与短语对照索引\n\n";
text+="本包从项目现有的 Oxford 3000 整理数据（"+words.length+" 个含分级/词性重复的条目）和 Oxford Phrase List "+phrases.length+" 个条目中选择材料。英文母句、迁移例句及其中文均为本包新编，未复制词表里的整句例句。\n\n";
text+="**重点词头："+keywordIndex.size+" 个；核心母句对应短语原表条目："+corePhraseIds.size+" 条；加上接话工具句后对应："+phraseIndex.size+" 条。** 这些是有明确对照的重点项，不是全文所有单词的覆盖率。不同编号可能是同一词块的不同结构或义项，不能把条目数当作互不重复的语义数量。\n\n";
text+="词形、时态、人称、单复数和语序可按句法变化；索引同时给出原表词块与本句的实际表达。get back to you 等补充口语表达不借用原表其他义项凑数。词/短语级别沿用本地源表标签，不据此给整句重新定级。\n\n";
text+="## 短语原表对照\n\n| 原表条目 | 级别 | 原表中文提示 | 本包中的实际用法与编号 |\n| --- | --- | --- | --- |\n";
for(const [id,{entry:p,uses}] of [...phraseIndex].sort((a,b)=>a[0]-b[0])){
 const href="../OxfordPhraseList_学习包/OxfordPhraseList_原序学习版.md#phrase-"+id;
 text+="| [P"+pad(id)+" · "+esc(p.phrase)+"]("+href+") | "+p.level+" | "+esc(p.meaning_zh)+" | "+uses.map(u=>extraLink(u.id)+"："+esc(u.surface)).join("<br>")+" |\n";
}
text+="\n## 重点词头对照\n\n等级与词性列保留原表中匹配词头的多个条目，供进一步查义；本表没有把某个词头的最低级别强行当成本句义项的级别。少量专名和场景词不在重点词头统计内。\n\n| 词头 | 原表级别与词性 | 本包词形与母句 |\n| --- | --- | --- |\n";
for(const [key,item] of [...keywordIndex].sort((a,b)=>a[0].localeCompare(b[0],"en"))){
 const refs=item.entries.map(w=>"["+w.level+" · "+esc(w.pos)+"](../Oxford3000_学习包/Oxford3000_原序学习完整版.md#word-"+String(w.id).padStart(4,"0")+")");
 text+="| "+esc(item.lemma)+" | "+refs.join("<br>")+" | "+item.uses.map(u=>mlink(u.id)+"："+u.surface).join(" · ")+" |\n";
}
write("04_Oxford词汇短语索引.md",text);
text="# 接话、确认与换话题工具条\n\n这些短句单独练，不挤占 120 个母句的编号。先选 5 个最常用的，每次对话主动用上其中一两个。\n\n";
for(const item of b.tools){
 text+="## "+item.id+"\n\n**"+item.english+"**  \n"+item.chinese+"\n\n"+item.note+"\n\n";
 if(item.phraseUses.length)text+="原表对照："+item.phraseUses.map(u=>"P"+pad(u.id)+" "+phraseMap.get(u.id).phrase).join("；")+"。\n\n";
 else text+="本包补充的常用说法。\n\n";
}
write("05_接话工具条.md",text);
const priorityOrder=["起步","巩固","扩展"].map(label=>({label,scenes:b.scenes.filter(s=>s.priority===label).map(s=>"D"+String(s.id).padStart(2,"0"))}));
text="# 日常对话母体 · 从这里开始\n\n编写日期："+b.createdDate+"。\n\n";
text+="这套材料把日常沟通拆成可反复使用的句法与话轮：先知道自己要问什么、说明什么，再替换人物、动作、时间和话题。主文件提供 30 段四轮对话、120 个母句和 240 个换话题例句，另有 20 个接话工具句。\n\n";
text+="## 文件入口\n\n| 想做什么 | 打开 |\n| --- | --- |\n| 看完整对话、骨架和中文解释 | [01 · 120句母体详解]("+main+") |\n| 只看英文，轮流开口练 | [02 · 纯对话跟读稿](02_纯对话跟读稿.md) |\n| 按语法找句子，练肯定/否定/疑问与换话题 | [03 · 句式地图与变形练习](03_句式地图与变形练习.md) |\n| 回查 Oxford 原表与本句用法 | [04 · 词汇短语索引](04_Oxford词汇短语索引.md) |\n| 听不清、想确认、想转话题时接住对话 | [05 · 接话工具条](05_接话工具条.md) |\n\n";
text+="## 第一回就这样练\n\n先练 D01 的 M001—M004：问发生什么、说原因、问怎么解决、说自己的行动。再把通勤换成学习或设备问题。每天可以用 12—15 分钟练一段；句式不熟时，多留几次练习，不必按天数赶进度。\n\n";
text+="搭档提示：**你问一句，我答一句；先让我回答，再给提示；练完后换一个话题，骨架尽量保持，必要的语法跟着变。**\n\n";
text+="## 建议顺序\n\n";
for(const p of priorityOrder)text+="- **"+p.label+"**："+p.scenes.join("、")+"。\n";
text+="\n这个顺序由本包编排，不是官方整句等级。每句只先抓一个语法重点；遇到熟悉的简单结构，尽快尝试换主题。\n\n";
text+="## 这次实际用了什么\n\n| 项目 | 数量与口径 |\n| --- | --- |\n| 核心对话 | 30 段，120 个编号话轮 |\n| 配套迁移 | 240 个双语例句，每个母句 2 个 |\n| 接话工具 | 20 个补充话轮 |\n| 语法地图 | "+grammarIndex.size+" 个教学观察标签，存在交叉 |\n| 词汇重点 | "+keywordIndex.size+" 个能在本地 Oxford 3000 数据中匹配的词头 |\n| 短语重点 | 核心母句对应 "+corePhraseIds.size+" 个原表条目；加工具句共 "+phraseIndex.size+" 个 |\n\n";
text+="本版选用的短语条目分布："+Object.entries(phraseLevels).sort().map(([level,n])=>level+" "+n+" 条").join("，")+"。选择以可迁移性和自然对话为先，不为了覆盖条目数硬塞词块。\n\n";
text+="## 怎样理解‘套用’\n\n可以保留提问、解释、比较等功能和句法关系。更换人称、时态、名词的数或动词搭配时，相应形式也要一起调整。主文件里的槽位写明应放名词、完整句子、动词原形还是 V-ing；例句演示怎样换，不建议整句只做字面替词。\n\n";
text+="## 来源与维护\n\n词头、短语及源表级别对照本项目的 [Oxford 3000 学习包](../Oxford3000_学习包/README.md) 和 [750 条短语学习包](../OxfordPhraseList_学习包/README.md)。这些整理材料和本包均不是牛津官方配套课程。英文对话、中文及迁移句为此次新编。\n\n";
text+="词头与短语音频可从原学习包复习；本包的纯对话稿供朗读、角色练习和复述使用。\n\n";
text+="后续改母句，编辑 data/母句.json；修改练习说明，编辑 data/练习说明.md。需要重新生成时，在本目录使用 Node.js 18 或以上运行：\n\n    node scripts/build.mjs\n\n";
text+="核对记录见 [data/覆盖核对.json](data/覆盖核对.json)，包括源文件校验值、条目映射、计数和各母句的来源编号。现有两个词表学习包保持原位即可重建。\n";
write("README.md",text);
const hash=p=>crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
const report={
date:b.createdDate,
sources:{words:{path:b.sourceFiles.words,entries:words.length,sha256:hash(wordFile)},phrases:{path:b.sourceFiles.phrases,entries:phrases.length,sha256:hash(phraseFile)}},
counts:{scenes:b.scenes.length,coreTurns:lines.length,transferExamples:totalTransfers,conversationTools:b.tools.length,grammarTags:grammarIndex.size,selectedWordHeads:keywordIndex.size,corePhraseEntries:corePhraseIds.size,phraseEntriesIncludingTools:phraseIndex.size},
phraseLevels,selectedPhraseIds:[...phraseIndex.keys()].sort((a,b)=>a-b),
selectedWordEntries:[...keywordIndex.values()].map(x=>({word:x.lemma,sourceIds:x.entries.map(w=>w.id),uses:unique(x.uses.map(u=>u.id))})),
grammarUses:Object.fromEntries(grammarIndex),errors
};
fs.writeFileSync(path.join(root,"data/覆盖核对.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({written:true,counts:report.counts,phraseLevels,errors}));
