"""Join the PDF rows to licensed dictionary and sentence data without reordering."""
from __future__ import annotations
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "_cache"
sys.path.insert(0, str(CACHE / "python"))
sys.stdout.reconfigure(encoding="utf-8")
from opencc import OpenCC
import nltk
from nltk.tag import PerceptronTagger
from nltk.tokenize import TreebankWordTokenizer

CC = OpenCC("t2s")
TOKENIZER = TreebankWordTokenizer()
US_SPELLINGS = {
    "analyse": "analyze", "behaviour": "behavior", "centre": "center", "colour": "color",
    "coloured": "colored", "defence": "defense", "dialogue": "dialog", "favour": "favor",
    "favourite": "favorite", "grey": "gray", "honour": "honor", "humour": "humor",
    "jewellery": "jewelry", "kilometre": "kilometer", "labour": "labor", "licence": "license",
    "metre": "meter", "neighbour": "neighbor", "neighbourhood": "neighborhood",
    "offence": "offense", "organise": "organize", "organisation": "organization",
    "practise": "practice", "programme": "program", "theatre": "theater", "traveller": "traveler",
    "tyre": "tire", "maths": "math", "mum": "mom", "lorry": "truck", "petrol": "gasoline",
    "cinema": "movie theater", "cooker": "stove", "bin": "trash can", "biscuit": "cookie",
    "film": "movie", "aeroplane": "airplane", "backwards": "backward", "downwards": "downward",
    "upwards": "upward", "per cent": "percent", "t-shirt": "T-shirt",
}
NAMES = {"tom", "mary", "john", "jack", "alice", "boston", "bush", "clinton", "obama", "trump", "sami", "layla"}
BAD_CONTEXT = re.compile(r"\b(?:fuck|shit|bitch|suicide|rape|naked|porno|hitler)\b", re.I)
STOP_END = {"a", "an", "the", "my", "your", "his", "her", "our", "their", "this", "that", "these", "those"}
STOP_START = {"i", "you", "he", "she", "it", "we", "they", "tom", "mary", "john", "jack"}
MONTHS = dict(zip("january february march april may june july august september october november december".split(), [f"{i}月" for i in range(1,13)]))
DAYS = dict(zip("monday tuesday wednesday thursday friday saturday sunday".split(), ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]))
FUNCTION_GLOSSES = {
    "a, an": "不定冠词：一个；某一个（an 用在元音音素开头的词前）",
    "i": "我（第一人称单数主格）", "you": "你；你们", "he": "他", "she": "她", "it": "它；这件事",
    "we": "我们", "they": "他们；她们；它们", "me": "我（宾格）", "him": "他（宾格）",
    "her": "她（宾格）；她的", "us": "我们（宾格）", "them": "他们／她们／它们（宾格）",
    "my": "我的", "your": "你的；你们的", "his": "他的", "its": "它的", "our": "我们的", "their": "他们的；她们的；它们的",
    "be": "是；处于某种状态；用于构成进行时和被动语态", "do": "做；用于疑问、否定和强调结构",
    "have": "有；拥有；经历；（助动词）构成完成时", "have to": "必须；不得不",
    "can": "能够；可以；可能", "could": "能够；可以；可能（can 的过去式或委婉形式）",
    "may": "可能；可以", "might": "可能；也许", "must": "必须；一定是", "will": "将；愿意",
    "would": "会；愿意；将会（will 的过去式或委婉形式）", "shall": "将；要不要（提出建议或询问）",
    "should": "应该；应当；按理说", "cannot": "不能；不可能", "ought to": "应该；应当",
    "o'clock": "……点钟（表示整点）", "cd": "光盘；激光唱片", "dvd": "数字影碟；DVD 光盘",
    "tv": "电视；电视节目", "ok": "好的；可以；还不错", "okay": "好的；可以；还不错",
    "mr": "先生（用于男子姓氏或全名前）", "mrs": "夫人；太太", "ms": "女士（不指明婚姻状况）",
    "become": "变成；变得；成为", "lot": "大量；许多（常用于 a lot、a lot of）",
    "per cent": "百分之……；百分比", "born": "出生；出世（常用于 be born）",
}


def load_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_models():
    folder = CACHE / "nltk_data"
    tagger_folder = folder / "taggers"
    tagger_folder.mkdir(parents=True, exist_ok=True)
    if not (tagger_folder / "averaged_perceptron_tagger_eng").exists():
        with zipfile.ZipFile(CACHE / "averaged_perceptron_tagger_eng.zip") as archive:
            for member in archive.infolist():
                target = (tagger_folder / member.filename).resolve()
                if not target.is_relative_to(tagger_folder.resolve()):
                    raise ValueError("Unsafe model archive path")
            archive.extractall(tagger_folder)
    corpora = folder / "corpora"
    corpora.mkdir(exist_ok=True)
    target = corpora / "wordnet.zip"
    if not target.exists():
        target.write_bytes((CACHE / "wordnet.zip").read_bytes())
    nltk.data.path.insert(0, str(folder))
    return PerceptronTagger(lang="eng")


def pdf_pos(entry):
    value = entry["pos"]
    roles = set()
    if re.search(r"\bn\.", value): roles.add("n")
    if re.search(r"\bv\.", value): roles.add("v")
    if "adj." in value: roles.add("a")
    if "adv." in value: roles.add("r")
    if "prep." in value: roles.add("p")
    if "conj." in value: roles.add("c")
    if "pron." in value: roles.add("pron")
    if "det." in value or "article" in value: roles.add("det")
    if "number" in value: roles.add("num")
    if "exclam." in value: roles.add("exclam")
    return roles


def dictionary(entries):
    wanted = {e["lookup"] for e in entries}
    wanted.update(US_SPELLINGS.values())
    selected = {}
    with (CACHE / "ecdict.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = row["word"].lower().replace("’", "'")
            if key in wanted:
                selected[key] = row
    print("DICTIONARY_ROWS", len(selected), flush=True)
    return selected


def glossary(entry, row):
    key = entry["lookup"]
    if entry["word"][:1].isupper() and key in MONTHS: return MONTHS[key]
    if key in DAYS: return DAYS[key]
    if key in FUNCTION_GLOSSES and not (key == "can" and "modal" not in entry["pos"]): return FUNCTION_GLOSSES[key]
    qualifier = entry["qualifier"].lower()
    if key == "bank": return "银行；银行营业处" if "money" in qualifier else "河岸；岸边"
    if key == "kind" and "type" in qualifier: return "种类；类别"
    if key == "like": return "喜欢；喜爱" if "v" in pdf_pos(entry) else "像；类似；比如"
    if key == "lie": return "躺；平卧；位于" if entry["homograph"] == "1" else "说谎；谎言"
    if key == "live": return "居住；生活；活着" if "v" in pdf_pos(entry) else "现场的；现场直播的；活的"
    if key == "close": return "关闭；合上；结束" if "v" in pdf_pos(entry) else "近的；亲密的；接近地"
    if key == "lead": return "铅（金属）" if entry["homograph"] == "2" else "引领；带领；导致；领先"
    if key == "minute": return "分钟；片刻" if entry["homograph"] != "2" else "极小的；微小的"
    if key == "match" and "contest" in qualifier: return "比赛；对手；相匹配；相配"
    if key == "right" and "correct" in qualifier: return "正确的；合适的；正确地"
    if key == "light" and "sun" in qualifier: return "光；光线；明亮的"
    if key == "mean" and "adj." in entry["pos"]: return "吝啬的；刻薄的"
    if not row: return None
    roles = pdf_pos(entry)
    parts = row.get("translation", "").replace("\\n", "\n").splitlines()
    keep = []
    for text in parts:
        if text.startswith("[") or re.search(r"\[(?:医|计|化|法|经|电|机|数|网络)\]", text): continue
        role_match = re.match(r"^(n|v[ti]?|a|adj|adv|prep|pron|conj|num|det|interj)\.\s*", text)
        if role_match:
            label = role_match.group(1)
            category = {"n":"n","v":"v","vi":"v","vt":"v","a":"a","adj":"a","adv":"r","prep":"p","pron":"pron","conj":"c","num":"num","det":"det","interj":"exclam"}[label]
            if roles and category not in roles: continue
            text = text[role_match.end():]
        meanings = [x.strip() for x in re.split(r"[,，;；]", text) if x.strip()]
        for meaning in meanings[:2]:
            if meaning not in keep: keep.append(meaning)
    if not keep:
        raw = re.sub(r"\[[^]]+\]", "", parts[0] if parts else "")
        keep = [re.sub(r"^[a-z. ]+", "", raw).strip()]
    return CC.convert("；".join(keep[:4]))


def tokenize(text):
    return TOKENIZER.tokenize(text)


def sentences(tagger):
    target = CACHE / "tagged_sentences.json"
    if target.exists(): return load_json(target)
    with zipfile.ZipFile(CACHE / "cmn-eng.zip") as archive:
        lines = archive.read("cmn.txt").decode("utf-8-sig").splitlines()
    chosen = {}
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3: continue
        english, chinese, attribution = parts[:3]
        if english in chosen: continue
        tokens = tokenize(english)
        if not (4 <= len(tokens) <= 20) or BAD_CONTEXT.search(english): continue
        chosen[english] = {"english": english, "chinese": CC.convert(chinese), "attribution": attribution,
                           "source": "Tatoeba/ManyThings", "tokens": tokens}
    rows = list(chosen.values())
    print("TAGGING_SENTENCES", len(rows), flush=True)
    for start in range(0, len(rows), 1000):
        batch = rows[start:start+1000]
        tagged = tagger.tag_sents([r["tokens"] for r in batch])
        for row, tags in zip(batch, tagged): row["tags"] = [tag for _,tag in tags]
        if start % 5000 == 0: print("TAGGED", min(start+1000,len(rows)), flush=True)
    save(target, rows)
    return rows


def role_of(tag):
    if tag.startswith("NN"): return "n"
    if tag.startswith("VB") or tag == "MD": return "v"
    if tag.startswith("JJ"): return "a"
    if tag.startswith("RB") or tag == "WRB": return "r"
    if tag == "IN": return "p"
    if tag == "CC": return "c"
    if tag.startswith("PRP") or tag.startswith("WP"): return "pron"
    if tag in {"DT","PDT","WDT","PRP$"}: return "det"
    if tag == "CD": return "num"
    if tag == "UH": return "exclam"
    if tag == "TO": return "p"
    return ""


def forms(key, row):
    variants = {key}
    if row:
        for part in row.get("exchange", "").split("/"):
            if ":" not in part: continue
            label, value = part.split(":",1)
            if label in {"s","3","p","d","i","r","t"}:
                variants.update(value.lower().split("/"))
    variants.add(US_SPELLINGS.get(key,key).lower())
    return {v for v in variants if v}


def curated_patterns():
    patterns = {}
    path = ROOT.parent / "高频通用词补充.md"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\| `([a-z]+)` \| .*? \| (.*?) \|$", line)
            if match:
                patterns[match[1]] = re.findall(r"`([^`]+)`", match[2])[:2]
    return patterns


def score_sentence(row, positions, roles, exact, entry):
    tokens = row["tokens"]
    score = abs(len(tokens)-9)*0.8
    score += 5*sum(t.lower() in NAMES for t in tokens)
    score += 4*sum(t in {"n't", "ca", "wo"} for t in tokens)
    if not exact: score += 3
    if roles:
        if any(role_of(row["tags"][p]) in roles for p in positions): score -= 8
        else: score += 9
    if len(tokens) > 15: score += 8
    if row["english"].endswith("!"): score += 3
    if entry["lookup"] in {"a, an", "a", "an"} and row["english"].startswith(("This is a", "It is a", "I have a")): score -= 4
    return score


def context_phrases(row, position, entry):
    tokens = row["tokens"]
    tags = row["tags"]
    target = entry["lookup"]
    roles = pdf_pos(entry)
    phrases = []
    actual_role=role_of(tags[position])
    context_role=actual_role if actual_role in roles else ''
    for length in [2,3,4,5,6]:
        for start in range(max(0,position-length+1), min(position+1,len(tokens)-length+1)):
            chunk=tokens[start:start+length]
            if any(not re.fullmatch(r"[A-Za-z]+(?:['’-][A-Za-z]+)?",t) for t in chunk): continue
            lower=[t.lower() for t in chunk]
            if any(t in NAMES for t in lower): continue
            if lower[-1] in STOP_END and not(context_role=='v' and tags[start+length-1] in {'PRP','WP'}): continue
            if role_of(tags[start+length-1]) not in {'n','a','v','r','pron','num'}: continue
            if tags[start+length-1] in {'VBG','VBN'} and 'v' not in roles: continue
            if lower[0] in {'is','am','are','was','were','be','been','being','has','have','had','could','should','would','will','can','may','might','must'} and lower[0]!=target: continue
            chunk_tags=tags[start:start+length]
            if context_role=='n':
                if any(t.startswith('VB') or t in {'PRP','MD'} or (t=='PRP$' and i>0) for i,t in enumerate(chunk_tags)):continue
                if not chunk_tags[-1].startswith('NN'):continue
                if any(t in {'DT','PRP$'} and i>0 for i,t in enumerate(chunk_tags)):continue
                if position!=start+length-1 and not(start==position and all(t.startswith(('NN','JJ')) for t in chunk_tags)):continue
            if context_role=='a' and not(start==position and chunk_tags[-1].startswith('NN')):continue
            if context_role=='v':
                if start!=position:continue
                if role_of(chunk_tags[-1]) not in {'n','pron','v'} and chunk_tags[-1]!='RP':continue
            if lower[0] in STOP_START and lower[0] != target: continue
            if tags[start+length-1].startswith('NN') and start+length<len(tokens) and tags[start+length].startswith('NN'):continue
            phrase = " ".join(chunk)
            if phrase.lower().startswith("i "): phrase = "I " + phrase[2:]
            else: phrase = phrase[:1].lower() + phrase[1:]
            score = 0
            tg = tags[start:start+length]
            if tg[-1].startswith("NN"): score += 3
            if roles & {"v"} and start==position: score += 4
            if roles & {"n"} and position==start+length-1: score += 4
            if roles & {"a"} and tg[-1].startswith("NN"): score += 4
            if length==2: score += 2
            if context_role=='n' and length==2 and chunk_tags[0] in {'DT','IN'}:score-=2
            score-=max(0,length-3)*0.7
            if lower[-1] in {"to","of","in","on","at","for","with"}: score -= 1
            phrases.append((score,phrase))
    phrases.sort(key=lambda p:(-p[0],len(p[1])))
    result=[]
    for _, phrase in phrases:
        if any(phrase.lower() in other.lower() or other.lower() in phrase.lower() for other in result): continue
        result.append(phrase)
        if len(result)==2: break
    return result


def wordnet_candidate(entry, row, tagger):
    from nltk.corpus import wordnet as wn
    key = entry["lookup"].replace(" ","_")
    acceptable = forms(entry["lookup"],row)
    candidates=[]
    allowed = pdf_pos(entry) & {"n","v","a","r"}
    for synset in wn.synsets(key):
        role="a" if synset.pos()=="s" else synset.pos()
        if allowed and role not in allowed: continue
        for text in synset.examples():
            text=text.strip()
            tokens=tokenize(text)
            positions=[i for i,t in enumerate(tokens) if t.lower() in acceptable]
            if not positions or not(4<=len(tokens)<=20) or BAD_CONTEXT.search(text): continue
            if text[:1].islower(): text=text[:1].upper()+text[1:]
            if text[-1] not in ".!?": text+="."
            tags=tagger.tag(tokens)
            candidate={"english":text,"chinese":"","attribution":"Princeton University WordNet 3.0; "+synset.name(),"source":"WordNet","tokens":tokens,"tags":[t for _,t in tags],"synset":synset.name()}
            score=score_sentence(candidate,positions,allowed,True,entry)
            if not any(tag.startswith("VB") for _,tag in tags):score+=20
            candidates.append((score,candidate,positions[0]))
    return min(candidates,key=lambda x:x[0])[1:] if candidates else None


def main():
    entries=load_json(ROOT/"data/pdf_entries.json")
    tagger=prepare_models()
    dictionary_rows=dictionary(entries)
    sentence_rows=sentences(tagger)
    index=defaultdict(list)
    for no,row in enumerate(sentence_rows):
        for token in {t.lower() for t in row["tokens"]}:index[token].append(no)
    manual=load_json(ROOT/"data/manual_enrichment.json",{})
    manual.update(load_json(ROOT/"data/sense_overrides.json",{}))
    manual.update(load_json(ROOT/"data/pos_overrides.json",{}))
    manual.update(load_json(ROOT/"data/qa_overrides.json",{}))
    patterns=curated_patterns()
    translations=load_json(ROOT/'data/example_translations.json',{})
    common_glosses=load_json(ROOT/'data/common_glosses.json',{})
    phrase_overrides=load_json(ROOT/'data/phrase_overrides.json',{})
    missing_examples=[]
    missing_definitions=[]
    missing_phrases=[]
    wordnet_examples=[]
    for no,entry in enumerate(entries,1):
        key=entry['lookup']
        drow=dictionary_rows.get(key) or dictionary_rows.get(US_SPELLINGS.get(key))
        entry['meaning_zh']=glossary(entry,drow)
        entry['meaning_zh']=common_glosses.get('@'+str(entry['id']),entry['meaning_zh'])
        entry['phonetic']=(drow or {}).get('phonetic','')
        entry['exchange']=(drow or {}).get('exchange','')
        custom=(manual.get(f"@{entry['id']}") or manual.get(f"{key}#{entry['homograph']}|{entry['pos']}")
                or manual.get(f"{key}#{entry['homograph']}")
                or manual.get(f"{key}({entry['qualifier']})")
                or manual.get(f"{key}|{entry['pos']}") or manual.get(key))
        if custom and custom.get('meaning_zh'):entry['meaning_zh']=custom['meaning_zh']
        if not entry['meaning_zh']:missing_definitions.append(entry)
        acceptable=forms(key,drow)
        if key=='a, an':acceptable={'a','an'}
        roles=pdf_pos(entry)
        candidates=[]
        for variant in acceptable:
            if ' ' in variant:
                first=variant.split()[0]
                sentence_ids=index.get(first,[])
            else:sentence_ids=index.get(variant,[])
            for sent_no in sentence_ids:
                row=sentence_rows[sent_no]
                positions=[i for i,t in enumerate(row['tokens']) if t.lower()==variant]
                if ' ' in variant:
                    text=' '.join(row['tokens']).lower()
                    if variant not in text:continue
                    positions=[i for i,t in enumerate(row['tokens']) if t.lower()==variant.split()[0]]
                if not positions:continue
                open_roles = roles & {'n','v','a','r'}
                if open_roles and not (roles - open_roles):
                    compatible = any(role_of(row['tags'][p]) in open_roles for p in positions)
                    # Participles can act as adjectives; the curated overrides resolve sense differences.
                    if not compatible and 'a' in open_roles:
                        compatible = any(row['tags'][p] in {'VBN','VBG'} for p in positions)
                    if not compatible:continue
                score=score_sentence(row,positions,roles,variant==key,entry)
                if key=='bank' and 'money' in entry['qualifier'] and not re.search(r'money|account|bank|cash|loan',row['english'],re.I):score+=20
                if key=='bank' and 'river' in entry['qualifier'] and not re.search(r'river|bank|water|lake',row['english'],re.I):score+=20
                candidates.append((score,row,positions[0],variant))
        if custom and custom.get('english'):
            tokens=tokenize(custom['english'])
            row={'english':custom['english'],'chinese':custom.get('chinese',''),'source':'原创学习例句','attribution':'本学习包编写','tokens':tokens,'tags':[t for _,t in tagger.tag(tokens)]}
            pos=next((i for i,t in enumerate(tokens) if t.lower() in acceptable),0)
            entry['example']=row
            entry['example_form']=next((t for t in tokens if t.lower() in acceptable),key)
            entry['phrases']=custom.get('phrases') or patterns.get(key) or context_phrases(row,pos,entry)
        elif candidates:
            _,row,pos,variant=min(candidates,key=lambda x:x[0])
            alias=US_SPELLINGS.get(key)
            if alias and alias.lower()!=key and variant==alias.lower():
                row=dict(row)
                replacement=entry['word']
                row['english']=re.sub(r'\b'+re.escape(alias)+r'\b',replacement,row['english'],flags=re.I)
                row['english']=row['english'][:1].upper()+row['english'][1:]
                row['tokens']=tokenize(row['english'])
                row['tags']=[t for _,t in tagger.tag(row['tokens'])]
                row['adaptation_note']='英文词形依 PDF 调整；保留原句作者署名。'
                pos=next((i for i,t in enumerate(row['tokens']) if t.lower()==key.split()[0]),pos)
                variant=key
            entry['example']=row
            entry['example_form']=variant
            entry['phrases']=(custom or {}).get('phrases') or patterns.get(key) or context_phrases(row,pos,entry)
        else:
            candidate=wordnet_candidate(entry,drow,tagger)
            if candidate:
                row,pos=candidate
                entry['example']=row
                entry['example_form']=row['tokens'][pos]
                entry['phrases']=(custom or {}).get('phrases') or patterns.get(key) or context_phrases(row,pos,entry)
                wordnet_examples.append({'id':entry['id'],'word':key,'pos':entry['pos'],'english':row['english'],'phrases':entry['phrases']})
            else:
                entry['example']=None
                entry['phrases']=(custom or {}).get('phrases') or patterns.get(key) or []
                missing_examples.append({'id':entry['id'],'word':key,'pos':entry['pos'],'meaning':entry['meaning_zh']})
        if entry.get('example'):
            entry['phrases']=phrase_overrides.get('@'+str(entry['id']),entry['phrases'])
            if not entry['phrases']:
                for _,crow,cpos,cvariant in sorted(candidates,key=lambda item:item[0])[:40]:
                    if cvariant==US_SPELLINGS.get(key) and cvariant!=key:continue
                    found=context_phrases(crow,cpos,entry)
                    if found:
                        entry['phrases']=found
                        break
            if not entry['phrases']:missing_phrases.append({'id':entry['id'],'word':entry['word'],'pos':entry['pos']})
            if entry['example']['english'] in translations:
                entry['example']['chinese']=translations[entry['example']['english']]
                entry['example']['translation_note']='中文译文为本学习包整理'
        if no%500==0:print('ENRICHED',no,'/',len(entries),flush=True)
    save(CACHE/'enriched_entries_draft.json',entries)
    save(CACHE/'missing_examples.json',missing_examples)
    save(CACHE/'wordnet_examples_for_review.json',wordnet_examples)
    save(CACHE/'missing_definitions.json',missing_definitions)
    save(CACHE/'missing_phrases.json',missing_phrases)
    print('ENRICHMENT_SUMMARY',json.dumps({'entries':len(entries),'missing_examples':len(missing_examples),'wordnet_examples':len(wordnet_examples),'missing_definitions':len(missing_definitions)},ensure_ascii=False),flush=True)
    print('MISSING_EXAMPLES',json.dumps(missing_examples,ensure_ascii=False),flush=True)
    print('MISSING_PHRASES',json.dumps(missing_phrases,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
