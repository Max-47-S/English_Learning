"""Build bilingual Markdown, source credits and the portable reader dataset."""
from collections import Counter
from pathlib import Path
import json,re
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
LEVELS=['A1','A2','B1','B2','C1']
SOURCE='https://www.oxfordlearnersdictionaries.com/external/pdf/wordlists/oxford-phrase-list/Oxford%20Phrase%20List.pdf'
FULL='OxfordPhraseList_原序学习版.md'

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write(name,text):(ROOT/name).write_text(text,encoding='utf-8')
def sentence(value):return value.replace('\n',' ').strip()

def main():
    original=load(ROOT/'data/pdf_entries.json');timeline=load(ROOT/'data/audio_timeline.json')
    notes=load(ROOT/'data/usage_notes.json');enriched={}
    for path in sorted((ROOT/'data').glob('enrichment_*.json')):enriched.update(load(path))
    assert len(enriched)==len(original)==len(timeline['entries'])==750
    entries=[]
    for source,audio in zip(original,timeline['entries']):
        assert source['id']==audio['id'] and source['phrase']==audio['phrase']
        row={**source,**enriched[str(source['id'])],'usage_note':notes.get(str(source['id']),''),'audio':audio}
        row['reference_url']='https://www.oxfordlearnersdictionaries.com/search/english/?q='+quote(source['phrase'])
        entries.append(row)
    save(ROOT/'data/vocabulary.json',entries)
    save(ROOT/'data/audio_sources.json',timeline['sources'])
    duration=int(timeline['duration_seconds']);duration_text=f'{duration//3600:02d}:{duration//60%60:02d}:{duration%60:02d}'
    metadata=load(ROOT/'data/pdf_metadata.json');counts=Counter(e['level'] for e in entries)
    common=(f'按 [Oxford 官方 PDF]({SOURCE}) 的主条目顺序整理，共 **750 条**：A1 200、A2 175、B1 175、B2 125、C1 75。\n\n'
            f'音频总长 **{duration_text}**，其中 **{timeline["human_entries"]} 条真人录音、{timeline["ai_entries"]} 条 AI 配音**；每条后留 {timeline["pause_seconds"]} 秒跟读停顿。\n\n'
            '[打开连续播放器](连续听读.html) · [完整 MP3](audio/OxfordPhraseList_连续听读.mp3) · [音频来源与署名](来源与许可.md)\n\n'
            '词头、级别及顺序来自原表；中文释义、搭配翻译及双语例句为本学习包编写，例句均为原创学习例句，不冒充牛津词典例句。\n\n'
            '`sb` = somebody（某人）；`sth` = something（某物或某事）；`X`、`A/B` 是可替换成分；`…` 表示后续成分可按语境补充。录音朗读固定短语部分或具体用法，实际内容列在“音频示范”中。\n\n'
            '原表缩进的变体和示例保留在对应主条目下，未另计为新条目。相同固定部分可能共用录音，但不同主条目和用法仍分别保留。这里的 750 条是独立的 Oxford Phrase List，不是 Oxford 3000 统计中额外的 306 条。\n\n')
    def block(e):
        audio=e['audio'];label='真人录音' if audio['kind']=='human_recording' else 'AI 配音'
        result=[f'<a id="phrase-{e["id"]}"></a>',f'### {e["id"]:04d}. {e["phrase"]} · {e["level"]}',
                f'**中文释义：** {e["meaning_zh"]}', '**常用搭配／用法示范：**']
        result+=['- '+c['english']+' — '+c['chinese'] for c in e['collocations']]
        result+=['**例句：** '+sentence(e['example']['english']),sentence(e['example']['chinese'])]
        if e['usage_note']:result+=['**用法提示：** '+e['usage_note']]
        if e['pdf_variants']:result+=['**原表附列：** '+'；'.join(e['pdf_variants'])]
        result+=[f'**音频示范：** {audio["audio_text"]}',
                 f'**听读：** [{audio["timecode"]} · {label}](连续听读.html#phrase-{e["id"]}) · [逐段来源](来源与许可.md#source-{audio["source_id"]})',
                 f'来源定位：PDF 第 {e["pdf_page"]} 页，第 {e["pdf_column"]} 栏；{e["level"]} 级第 {e["level_index"]} 条。']
        return '\n\n'.join(result)+'\n\n'
    full=['# Oxford Phrase List · 原序双语学习版\n\n',common,'## 级别目录\n\n']
    full+=['- ['+level+f' · {counts[level]} 条](#level-{level.lower()})\n' for level in LEVELS]
    full+=['\n']
    for level in LEVELS:
        full+=[f'<a id="level-{level.lower()}"></a>\n\n## {level} · {counts[level]} 条\n\n']
        rows=[e for e in entries if e['level']==level]
        full.extend(block(e) for e in rows)
        write(f'OxfordPhraseList_{level}.md',f'# Oxford Phrase List · {level} 双语学习版\n\n'+common+f'本文件包含 {counts[level]} 条，序号保留完整 PDF 中的位置。\n\n'+''.join(block(e) for e in rows))
    write(FULL,''.join(full))
    credits=['# 来源与许可\n\n','## 原表与编辑内容\n\n',
             f'- 主条目、级别与顺序：[Oxford Phrase List 官方 PDF]({SOURCE})。原 PDF 保存在 [source/](source/oxford-phrase-list.pdf)，版权归原出版方。\n',
             '- [Oxford 官方说明](https://www.oxfordlearnersdictionaries.com/about/wordlists/oxford-phrase-list)。\n',
             '- 中文释义、两组用法搭配的中文翻译及双语例句由本学习包编写；所有例句均标为“原创学习例句”。它们用于说明常见用法，并非穷尽词典中的全部义项。\n',
             '- 部分“常用搭配”是将原表 sb/sth 等成分填成自然表达的句型示范。原表缩进内容另列为“原表附列”。\n\n',
             '## 音频制作\n\n',
             f'- 共 {len(entries)} 条：真人 {timeline["human_entries"]} 条，AI {timeline["ai_entries"]} 条。不同条目可复用同一完整短语录音。\n',
             '- 真人素材取自 Wikimedia Commons / Wiktionary 链接的开放录音，以及 Shtooka / SWAC 开放录音集；每个实际使用的片段均在下面注明朗读者、来源页与许可链接。\n',
             '- 没有通过拼接单个单词来冒充真人连读。原表含占位成分时，真人录音可能只读固定部分；具体朗读文字见各条“音频示范”。\n',
             '- AI 素材：Microsoft Edge 在线神经网络语音 en-GB-SoniaNeural，rate=-5%，通过 [edge-tts](https://github.com/rany2/edge-tts) 生成。明确标为 AI，未标为真人或牛津官方录音。\n',
             '- 音频内容是英文短语或具体用法示范，例句与中文释义供同步阅读，未加入主音轨。\n',
             '- 制作处理：解码后转为 24 kHz 单声道、轻微修整首尾静音、调整峰值音量；完整 MP3 为 64 kbps，每条后加入 1.8 秒停顿。未改变真人片段中的词语。\n',
             '- 各真人片段保留其原始许可及署名；整段 MP3 是按 PDF 顺序编排的片段合集。各 CC BY-SA 片段的格式转换版本继续沿用对应 CC BY-SA 许可；AI 部分不归入这些第三方真人素材的 CC 许可。\n',
             '- 逐条音频时间、朗读内容及来源编号见 [audio_timeline.json](data/audio_timeline.json)；独立来源记录见 [audio_sources.json](data/audio_sources.json)。\n\n',
             '## 实际使用的录音\n\n']
    uses={}
    for e in entries:uses.setdefault(e['audio']['source_id'],[]).append(e['id'])
    for sid,s in timeline['sources'].items():
        credits+=[f'<a id="source-{sid}"></a>\n\n### {sid} · {sentence(s.get("recorded_text",s.get("text","")))}\n\n',
                  '对应条目：'+', '.join(f'{i:04d}' for i in uses[sid])+'。\n\n']
        if s['kind']=='human_recording':
            credits+=['- 类型：真人录音。\n','- 朗读者／原站署名：'+sentence(s['artist'])+'。\n']
            if s.get('credit'):credits+=['- 原署名补充：'+sentence(s['credit'])+'。\n']
            credits+=['- 许可：['+s['license']+']('+s['license_url']+')。\n',
                      '- 来源页：['+sentence(s.get('title',s.get('collection','录音集')))+']('+s['page_url']+')。\n']
            if s.get('archive_url'):credits+=['- [原始录音集压缩包]('+s['archive_url']+')'+('；原文件 '+s['original_filename'] if s.get('original_filename') else '')+'。\n']
            if s.get('url'):credits+=['- [原始音频文件]('+s['url']+')。\n']
        else:credits+=['- 类型：AI 配音。\n','- 引擎：'+s['engine']+'；语音 '+s['voice']+'；语速 '+s['rate']+'。\n','- 合成时间：'+s['created_at']+'。\n']
        credits+=['- 原始片段 SHA-256：'+s['sha256_original']+'。\n\n']
    write('来源与许可.md',''.join(credits))
    readme=f'''# Oxford Phrase List · 连续听读学习包

750 条短语，按原 PDF 的级别与四栏阅读顺序整理。每条配有中文释义、两组中英用法搭配、原创双语例句；其中 {len(notes)} 条另有语法或辨析提示。

| 级别 | 条数 | 学习文件 |
| --- | ---: | --- |
'''+''.join(f'| {level} | {counts[level]} | [{level} 学习版](OxfordPhraseList_{level}.md) |\n' for level in LEVELS)+f'''
## 开始使用

1. 打开 [连续听读网页](连续听读.html)，点击播放，从第一条连续听到最后一条。
2. 点击列表里的短语可从该条开始，支持上一条、下一条、重听、0.75–1.5 倍速、按英文或中文搜索及按级别筛选。
3. 点击“继续上次进度”恢复同一浏览器保存的位置。级别筛选只改变列表，连续音轨仍按完整 PDF 顺序播放。
4. 阅读 [完整 Markdown 学习版]({FULL})，或上表中的分级文件；其中的时间链接可打开网页并定位。

网页与音频使用本地文件，不加载在线字体或外部脚本。解压后保留整个文件夹结构，使用支持本地音频的浏览器打开 HTML。移动端具体的本地文件打开方式取决于系统与浏览器；同一局域网也可以由电脑运行下面的本地服务器，再用手机浏览器访问。

音频也可直接用任意支持 MP3 的播放器播放：[{duration_text} 完整连续音频](audio/OxfordPhraseList_连续听读.mp3)，配套 [LRC 时间标签](audio/OxfordPhraseList_连续听读.lrc)。

## 内容与音频

- A1 200、A2 175、B1 175、B2 125、C1 75，共 750 个主条目；原表附列的缩进示例未额外计数。
- 真人录音 **{timeline['human_entries']} 条**，AI 补音 **{timeline['ai_entries']} 条**；AI 使用 en-GB-SoniaNeural。每条和播放器中均有明确标记，实际朗读内容列在“音频示范”中。
- 音频朗读英文短语或具体用法，条间停顿 **1.8 秒**；中文、搭配和例句供同步阅读。真人录音包含不同朗读者与口音。
- 对含 sb/sth、X 或省略号的句型，用固定短语部分或具体填充后的表达来示范，不把这些占位字母作为正常单词跟读。
- 这份表是独立的 Oxford Phrase List；750 条不等于 Oxford 3000 里多出的 306 条，不能据此直接相加计算去重词汇量。
- 词头与级别取自原表，学习释义及双语例句由本包编写；不是牛津官方音频、释义或例句产品。来源与逐段署名见 [来源与许可](来源与许可.md)。

## 本地网页服务（可选）

直接打开 HTML 即可先试用。若系统限制本地 HTML 读取旁边的音频，电脑安装 Python 后，在本学习包文件夹运行：

```powershell
python scripts/serve.py
```

电脑访问 http://127.0.0.1:8767/连续听读.html 。如要让同一局域网的手机访问：

```powershell
python scripts/serve.py --host 0.0.0.0
```

在手机浏览器中把 127.0.0.1 换成电脑的局域网 IP，并保留端口 8767。系统询问防火墙权限时，仅在你需要局域网访问的网络环境中放行。服务支持 MP3 Range 请求，可直接跳转时间点；Ctrl+C 结束服务。播放器本身不依赖 Python。

## 数据与校验

- [vocabulary.json](data/vocabulary.json)：750 条完整双语学习资料。
- [audio_timeline.json](data/audio_timeline.json)：逐条时间轴、类型、朗读文字、来源。
- [pdf_metadata.json](data/pdf_metadata.json)：原 PDF URL、SHA-256、页数及提取数量。
- [validation_report.json](data/validation_report.json)：自动校验结果；[browser_validation.json](data/browser_validation.json)：浏览器交互校验结果。
- 脚本用于重新生成资料；中间下载、合成缓存及本机依赖放在被忽略的 _cache/，成品播放不需要这些缓存。

原 PDF SHA-256：`{metadata['source_sha256']}`。
'''
    write('README.md',readme)
    print('MATERIALS_COMPLETE',len(entries),'notes',len(notes),'sources',len(timeline['sources']),flush=True)

if __name__=='__main__':main()
