"""Produce the complete Markdown study edition and source/attribution records."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import shutil

REPOSITORY=Path(__file__).resolve().parents[2]
ROOT=REPOSITORY/'01_词汇与短语'/'Oxford3000_学习包'


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf-8')


def word_forms(entry):
    if 'modal' in entry['pos'] or entry['lookup'] in {'can','may','might','must','shall','should','will','would','could','ought to','have to','used to'}:
        return ''
    if entry['lookup']=='lie':
        return '过去式 lay；过去分词 lain；现在分词 lying' if entry['homograph']=='1' else '过去式/过去分词 lied；现在分词 lying'
    labels={}
    if re.search(r'\bv\.',entry['pos']):labels.update(p='过去式',d='过去分词',i='现在分词',**{'3':'第三人称单数'})
    if re.search(r'\bn\.',entry['pos']):labels['s']='复数'
    if 'adj.' in entry['pos'] or 'adv.' in entry['pos']:labels.update(r='比较级',t='最高级')
    items=[]
    for item in entry.get('exchange','').split('/'):
        if ':' not in item:continue
        key,value=item.split(':',1)
        if key in labels and value and value not in {'0','1'}:
            items.append(labels[key]+' '+value)
    return '；'.join(items)


def block(entry,timing,prefix):
    i=entry['id'];word=entry['word']+entry['homograph'].translate(str.maketrans('12','¹²'))
    ex=entry['example'];lines=[f'<a id="word-{i:04d}"></a>',f'### {i:04d} · {word}','',
        f"**{entry['level']} · 本级第 {entry['level_index']} 项 · {entry['pos']} · PDF 第 {entry['pdf_page']} 页**",'']
    if entry['qualifier']:lines += [f"PDF 义项限定：{entry['qualifier']}",'']
    lines += [f"**中文**：{entry['meaning_zh']}",'',
              '**搭配／语境用法**：'+'；'.join('`'+p+'`' for p in entry['phrases']),'',
              f"**例句**：{ex['english']}  ",ex['chinese'],'']
    forms=word_forms(entry)
    if forms:lines += [f'**词形参考**：{forms}','']
    if timing:
        start=timing['start']
        lines += [f"**听读**：[{timing['timecode']}]({prefix}audio/Oxford3000_完整连续真人音频.mp3#t={start:.2f}) · [播放器定位]({prefix}连续听读.html#word-{i})",'']
        if timing['notes']:lines += ['**发音提示**：'+' '.join(timing['notes']),'']
    if ex['source']=='原创学习例句':lines += ['例句：本学习包原创。','']
    else:
        suffix='；英文已按 PDF 词形调整' if ex.get('adaptation_note') else ''
        lines += [f"[例句署名与许可]({prefix}来源与许可.md#example-{i:04d}){suffix}。",'']
    lines += ['---','']
    return '\n'.join(lines)


def main():
    entries=load(ROOT/'_cache/enriched_entries_draft.json')
    meta=load(ROOT/'data/pdf_metadata.json')
    audio=load(ROOT/'data/audio_timeline.json')
    planned={part['cache_file']:part for row in load(ROOT/'data/audio_plan.json') for part in row['parts']}
    # Refresh attribution without changing the already encoded audio or its timestamps.
    audio['sources']={sid:planned[row['cache_file']] for sid,row in audio['sources'].items()}
    write(ROOT/'data/audio_timeline.json',json.dumps(audio,ensure_ascii=False,indent=2))
    timing={r['id']:r for r in audio['entries']}
    original=load(ROOT/'data/pdf_entries.json')
    assert [(r['id'],r['pdf_text']) for r in entries]==[(r['id'],r['pdf_text']) for r in original]
    assert len(entries)==3306 and len(timing)==3306
    for e in entries:
        assert e['meaning_zh'] and e['phrases'] and e['example'] and e['example']['english'] and e['example']['chinese'],e['id']
    compact=[]
    for e in entries:
        row={k:v for k,v in e.items() if k!='phonetic'}
        row['example']={k:v for k,v in e['example'].items() if k not in {'tokens','tags'}}
        row['audio']={k:timing[e['id']][k] for k in ['start','end','timecode','kind','notes']}
        row['word_forms']=word_forms(e)
        compact.append(row)
    write(ROOT/'data/vocabulary.json',json.dumps(compact,ensure_ascii=False,indent=2))
    intro=['# Oxford 3000 · 按 PDF 原序学习完整版','',
        '来源：`oxford-3000-by-cefr-level.pdf`。按每页从左列到右列、每列从上到下读取，保留分级、词性、义项编号和重复条目。','',
        '**共 3,306 个学习条目**：A1 899；A2 871；B1 809；B2 727。条目数包含同词在不同词性、级别下的重复，不等同于 3,306 个独立单词。','',
        '[使用说明](README.md) · [连续听读](连续听读.html) · [完整 MP3](audio/Oxford3000_完整连续真人音频.mp3) · [来源与许可](来源与许可.md)','',
        '中文释义优先呈现常用含义；搭配包括人工整理的常用结构和例句中的语境用法，后者不一定是固定短语。词形只作参考，适用义项仍需结合上下文。','',
        '双语例句来自署名的 Tatoeba/ManyThings 语料及本学习包原创例句。为对应词头，部分原句的美式拼写或词语已按 PDF 调整。此为学习整理版。','',
        '## 按级别阅读','',
        '- [A1 · 899 条](分级词表/A1.md)','- [A2 · 871 条](分级词表/A2.md)','- [B1 · 809 条](分级词表/B1.md)','- [B2 · 727 条](分级词表/B2.md)','']
    all_parts=['\n'.join(intro)]
    for level in ['A1','A2','B1','B2']:
        rows=[e for e in entries if e['level']==level]
        all_parts += [f'## {level}','']+[block(e,timing[e['id']],'') for e in rows]
        head=f'# Oxford 3000 · {level} · PDF 原序\n\n共 {len(rows)} 个学习条目。[返回总表](../Oxford3000_原序学习完整版.md) · [使用说明](../README.md)\n\n搭配包含常用结构与例句中的语境用法；词形参考需结合本条义项。\n\n'
        write(ROOT/'分级词表'/f'{level}.md',head+'\n'.join(block(e,timing[e['id']],'../') for e in rows))
    write(ROOT/'Oxford3000_原序学习完整版.md','\n'.join(all_parts))
    license_dir=ROOT/'licenses';license_dir.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'_cache/ECDICT_LICENSE.txt',license_dir/'ECDICT-MIT.txt')
    for path in (ROOT/'_cache/collections').glob('*_README.txt'):
        shutil.copyfile(path,license_dir/path.name)
    credits=['# 来源、署名与许可','',
        '## 词序来源','',
        '原文件：[原始 PDF](../../06_原始资料/Oxford词表/oxford-3000-by-cefr-level.pdf)，Oxford University Press。仅以用户提供的 PDF 确定词头、词性、分级和顺序；中文释义、例句和音频不是牛津官方配套内容。','',
        '源文件 SHA-256：`4bf5eee62b858cc970da5d209558435276c05ec3a705662d255329966b06046d`。','',
        '## 词典与例句','',
        '- [ECDICT](https://github.com/skywind3000/ECDICT)：中文释义、词形基础资料，MIT 许可；[保留的许可](licenses/ECDICT-MIT.txt)。常用义项另经人工精简和补充。',
        '- [ManyThings 英中句对](https://www.manythings.org/anki/)／[Tatoeba](https://tatoeba.org/)：CC BY 2.0 FR。中文转为简体，部分英语词形按 PDF 调整；下方逐句保留原始作者及句子编号。',
        '- 标为“本学习包原创”的例句、中文翻译和新整理内容按 CC BY 4.0 提供，署名“English_Learning 学习包整理”。','',
        '## 真人音频','',
        f"连续音频包含 {audio['human_entries']} 个条目，AI 配音 {audio['ai_entries']} 个条目。不同录音者、口音和录音环境会有差别。所有片段仅作首尾静音修整、音量统一、采样率转换和顺序拼接。CD、DVD、IT 等用真人字母片段拼接；ought to 用真人单词片段拼接；used¹ 读 used to 以保留相应读音。",'',
        '拼接音频与字幕整体按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 分享；原始片段保留逐条标明的原许可。应同时保留本署名文件及 `data/audio_timeline.json`。','',
        '合集：[Yojik / Shtooka 真人录音归档](https://www.yojik.eu/audiocollections/audiocollections.html)。保留各合集 README 于 `licenses/`。逐段来源还包括 Wikimedia Commons／Lingua Libre；以下清单以实际使用片段为准。','',
        '| 录音编号 | 词／片段 | 朗读者／署名 | 许可 | 原来源 |','|---|---|---|---|---|']
    for sid,row in audio['sources'].items():
        clean=lambda text:str(text or '').replace('|','／').replace('\n',' ').replace('\r',' ')
        artist=clean(row.get('artist') or row.get('credit') or row.get('copyright'))
        if row.get('credit') and clean(row['credit']) not in artist:artist+='；'+clean(row['credit'])
        url=row.get('page_url') or row.get('archive_url')
        credits.append(f"| `{sid}` | {clean(row.get('spoken_word') or row.get('text'))} | {artist} | [{clean(row['license'])}]({row['license_url']}) | [来源]({url}) |")
    credits += ['','## 逐句署名','', '编号对应学习总表的全局条目编号。中文繁简转换和必要词形调整属于本学习包的编辑改动。','']
    for e in entries:
        ex=e['example']
        if ex['source']=='原创学习例句':continue
        credits += [f"<a id=\"example-{e['id']:04d}\"></a>",f"- **{e['id']:04d} · {e['word']}**：{ex['attribution']}"]
    write(ROOT/'来源与许可.md','\n'.join(credits))
    summary={
        'source_pdf_sha256':hashlib.sha256((REPOSITORY/'06_原始资料/Oxford词表/oxford-3000-by-cefr-level.pdf').read_bytes()).hexdigest(),
        'entries':len(entries),'levels':dict(Counter(e['level'] for e in entries)),
        'examples_by_source':dict(Counter(e['example']['source'] for e in entries)),
        'human_entries':audio['human_entries'],'ai_entries':audio['ai_entries'],
        'duration_seconds':audio['duration_seconds'],'missing_definitions':0,'missing_examples':0,
    }
    write(ROOT/'data/validation_report.json',json.dumps(summary,ensure_ascii=False,indent=2))
    print('MATERIALS_COMPLETE',json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
