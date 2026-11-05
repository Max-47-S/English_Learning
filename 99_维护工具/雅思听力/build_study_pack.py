"""Build four IELTS study chapters, local HTML and the owner-private mobile site."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import os
from urllib.parse import quote

from build_reference_texts import GROUPS, source_data, apply_corrections
from mobile_oxford import add_packs
from ielts_text_fixes import fix_wrapped_phrases

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
ROOT = REPO / '05_听力与歌曲/雅思王听力语料库'
WEB = TOOLS / 'web'
SITE_URL = 'https://ielts-listening-nov-2026-wx.nimble-goby-1176.chatgpt.site'
PROJECT_ID = 'appgprj_6ae6ef998de48191ae576308e8c9bfa1'
IELTS_SOURCE_REVISION = '560f3d2b7b475dff5657631b4f16fc60939f6b36'


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def cell(value):
    return str(value or '').replace('|', '\\|').replace('\n', '<br>')


def primary(word):
    return word.split('=')[0].strip().lower().replace('’', "'")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site-dir', type=Path, default=TOOLS / '_cache/mobile-listening-site')
    parser.add_argument('--site-url', default=SITE_URL)
    parser.add_argument('--export-pc', action='store_true')
    args = parser.parse_args()
    source = source_data()
    apply_corrections(source)
    official = fix_wrapped_phrases(load(ROOT / 'data/chapter11_transcription.json'))
    validation = load(ROOT / 'data/download_validation.json')
    tracks, chapters, entries = [], [], []
    for row in validation['entries']:
        if not row['file'].endswith('.mp3'):
            continue
        chapter = row['chapter']
        file = Path(row['file'])
        direction = file.parent.name if chapter != 11 else ''
        index = int(re.search(r'\d+', file.stem).group())
        track_id = f'c{chapter}-' + (f'{"h" if direction == "横向测试" else "v"}{index:02}' if chapter != 11 else f'{index:02}')
        tracks.append({'id': track_id, 'chapter': chapter, 'title': row['label'],
                       'direction': direction, 'file': row['file'], 'filename': file.name,
                       'bytes': row['bytes'], 'duration': row['duration_seconds'],
                       'url': row['url'], 'pageUrl': row['page_url']})
    for chapter, (folder, title, keys) in GROUPS.items():
        groups = []
        for index, key in enumerate(keys, 1):
            group_id = f'c{chapter}-p{index}'
            group_title = f'Test Paper {index}' if chapter != 4 else (f'形容词 · 第 {index} 组' if index < 4 else '副词')
            groups.append({'id': group_id, 'title': group_title,
                           'trackIds': {'横向测试': f'c{chapter}-h{index:02}', '纵向测试': f'c{chapter}-v{index:02}'}})
            for order, item in enumerate(source[key], 1):
                entries.append({'id': f'{group_id}-{order:04}', 'chapter': chapter, 'group': group_id,
                                'order': order, 'word': item['w'], 'ipa': item['p'] if '<' not in item['p'] else '',
                                'meaning': item['m'], 'source': 'reference',
                                'corrected': chapter == 3 and index == 8 and order >= 127})
        chapters.append({'id': chapter, 'title': title, 'folder': folder, 'groups': groups})
    groups = []
    for group in official['groups']:
        track_index = (group['section'] - 1) * 2 + (2 if group['part'] == 'phrases' else 1) if group['section'] < 5 else 9
        groups.append({**group, 'trackIds': {'default': f'c11-{track_index:02}'}})
    chapters.append({'id': 11, 'title': '综合测试', 'folder': 'Chapter11_综合测试', 'groups': groups})
    for item in official['entries']:
        entries.append({k: v for k, v in item.items() if k not in ('x', 'y', 'ocrWord', 'reviewIssues')})
    oxford = {}
    for v in load(REPO / '01_词汇与短语/Oxford3000_学习包/data/vocabulary.json'):
        oxford.setdefault(primary(v['word']), []).append(v)
    enriched = 0
    for entry in entries:
        candidates = oxford.get(primary(entry['word']), [])
        wanted_pos = entry.get('pos') or ('n.' if entry['chapter'] == 3 else ('adv.' if entry['group'] == 'c4-p4' else 'adj.') if entry['chapter'] == 4 else '')
        if wanted_pos:
            candidates = [v for v in candidates if wanted_pos.rstrip('.') in v.get('pos', '').split('.') or wanted_pos in v.get('pos', '')]
        meaningful = set(entry['meaning']) - set('的了一个有是和与为于在；，。 （）/、')
        match = next((v for v in candidates if meaningful & set(v.get('meaning_zh', ''))), None)
        if match:
            entry['phrases'] = match.get('phrases', [])
            if match.get('example'):
                entry['example'] = match['example']
                enriched += 1
        if entry.get('variants'):
            entry['reviewNote'] = '另一种拼写：' + ' / '.join(entry['variants'])
    assert len(tracks) == 59 and len({t['id'] for t in tracks}) == 59
    assert len({e['id'] for e in entries}) == len(entries)
    ids = {t['id'] for t in tracks}
    assert all(t in ids for c in chapters for g in c['groups'] for t in g['trackIds'].values())
    corrected = [e['word'] for e in entries if e['chapter'] == 3 and e['group'] == 'c3-p8' and e['order'] >= 127]
    assert corrected == [e['w'] for e in load(ROOT / 'data/manual_text_corrections.json')['corrections'][0]['entries']]
    collections, audio_credits = add_packs(chapters, entries, tracks, ROOT)
    timing = load(ROOT / 'data/original_audio_timeline.json')
    assert len(timing['tracks']) == 59
    for track in tracks:
        if track['id'] not in timing['tracks']:
            continue
        aligned = timing['tracks'][track['id']]
        assert hashlib.sha256((ROOT / track['file']).read_bytes()).hexdigest() == aligned['sourceSha256']
        track.update(cues=aligned['cues'], duration=aligned['duration'], mp3Index=aligned['mp3Index'],
                     playbackBytes=aligned['mp3Index']['bytes'], humanEntries=aligned['entryCount'], aiEntries=0,
                     originalDuration=track['duration'], officialUrl=track['url'])
        relative = (ROOT / track['file']).relative_to(REPO).as_posix()
        track['url'] = f'https://raw.githubusercontent.com/Max-47-S/English_Learning/{IELTS_SOURCE_REVISION}/' + quote(relative, safe='/')
    for c in chapters:
        if c['collection'] == 'ielts':
            c.update(audioTitle='王陆原版真人录音', audioSubtitle='真人 · 逐词同步')
    next(c for c in collections if c['id'] == 'ielts')['defaultMode'] = 'original'
    assert len(entries) == 9625 and len(tracks) == 61
    dataset = {'version': '2026-11-02-original-sync', 'collections': collections, 'chapters': chapters, 'entries': entries, 'tracks': tracks,
               'audioCredits': audio_credits,
               'entryAliases': official['entryAliases'],
               'pdfHref': 'Chapter11_综合测试/文本/Chapter11_综合测试_剑21版.pdf',
               'notes': ['Chapter 3/4/5 为网络参考词表；Chapter 11 为官方 PDF OCR 转写。',
                         '四章原版真人录音均有逐词时间轴，保留原声和原有停顿，卡片随原音频切换。系统朗读另行使用设备合成语音。',
                         'Oxford 3000 音轨为 3306 条真人录音；750 短语音轨含 350 条真人录音与 400 条 AI 配音，逐条标注。',
                         '扩展搭配和例句按英文词形匹配现有 Oxford 学习包，释义仍以本章为主。']}
    save(ROOT / 'data/mobile_study.json', dataset)
    # Chapter 11 original transcription: keep page references and spelling variants.
    out = ROOT / 'Chapter11_综合测试/文本/Chapter11_官方文本转写.md'
    md = ['# Chapter 11 · 综合测试（官方 PDF 转写）', '',
          '> 来源：剑21版官方 PDF，74 页；以页面 OCR 重建词表，保留 PDF 页码。原书音标难以可靠 OCR，音标列为现有词库的参考音标；空白表示未补入。', '',
          '**阅读提示：** 这是可搜索、可编辑的转写稿。已检查分组、双栏顺序、串行和明显字形错误，仍可能有个别 OCR 错字；疑问请用每行的页码回看原 PDF。', '',
          '[打开原始 PDF](Chapter11_综合测试_剑21版.pdf) · [四章手机听读](../../手机听读.html)', '',
          '## 拼写说明', '', '英式 / 美式拼写均应结合题目和录音判断，不要把等号两边当成两种不同含义。', '']
    spelling = ['centre = center', 'socialise = socialize', 'licence = license', 'archaeology = archeology',
                'maths = math', 'fertiliser = fertilizer', 'mediaeval = medieval', 'adviser = advisor',
                'verbalisation = verbalization', 'enquiry = inquiry', 'organisation = organization',
                'catalogue = catalog', 'colour = color', 'jewellery = jewelry', 'odour = odor',
                'flavour = flavor', 'rumour = rumor', 'fibre = fiber', 'tyre = tire',
                'specialised = specialized', 'manoeuvre = maneuver', 'recognisable = recognizable',
                'tranquiliser = tranquilizer', 'appetising = appetizing', 'artefact = artifact',
                'archaeologist = archeologist', 'urbanisation = urbanization', 'armour = armor',
                'mechanisation = mechanization']
    md += ['- ' + s for s in spelling]
    md += ['', '上表按常见拼写规范整理；原 PDF 个别拼写可能含排版问题，未据此改写后文词条。', '',
           '## 分组目录', '', '| 分组 | 转写条目 |', '| --- | ---: |']
    md += [f'| {g["title"]} | {g["entries"]} |' for g in official['groups']]
    for group in official['groups']:
        md += ['', f'## {group["title"]}', '', '| 序号 | 英文 | 参考音标 | 词性 | 中文提示 | PDF 页 |', '| ---: | --- | --- | --- | --- | ---: |']
        for e in official['entries']:
            if e['group'] != group['id']:
                continue
            word = e['word'] + (' = ' + ' / '.join(e['variants']) if e.get('variants') else '')
            md.append(f'| {e["order"]} | {cell(word)} | {cell(e["ipa"])} | {cell(e["pos"])} | {cell(e["meaning"])} | [第 {e["pdfPage"]} 页](Chapter11_综合测试_剑21版.pdf#page={e["pdfPage"]}) |')
    out.write_text('\n'.join(md) + '\n')
    out.with_suffix('.txt').write_text('\n'.join(f'{e["group"]}\t{e["order"]}\t{e["word"]}\t{e["ipa"]}\t{e["meaning"]}\tPDF:{e["pdfPage"]}' for e in official['entries']) + '\n')
    for chapter in chapters:
        if chapter['collection'] != 'ielts':
            continue
        md = [f'# Chapter {chapter["id"]} · {chapter["title"]} · 学习卡', '',
              '[打开四章听读页面](../手机听读.html)', '',
              '中文释义取自本章词表。搭配与双语例句按词形匹配现有 Oxford 3000 学习包，作为扩展学习；不保证与本章每个词义相同。例句保留各自来源和授权署名。', '',
              '原版真人音轨已有逐词时间轴，连续播放保持原录音节奏；系统语音可另外选用。', '']
        for g in chapter['groups']:
            md += [f'## {g["title"]}', '']
            for e in entries:
                if e['group'] != g['id']:
                    continue
                md += [f'### {e["order"]}. {e["word"]}', '', f'**中文：** {e["meaning"]}', '']
                if e.get('ipa'):
                    md += [f'**{"参考音标" if e.get("ipaSource") == "reference" else "音标"}：** /{e["ipa"]}/', '']
                if e.get('phrases'):
                    md += ['**搭配：** ' + '；'.join(e['phrases']), '']
                if e.get('example'):
                    example = e['example']
                    md += [f'> {example["english"]}', f'>', f'> {example["chinese"]}', '',
                           f'例句来源：{example.get("source", "")}；{example.get("attribution", "")}', '']
                if e.get('pdfPage'):
                    md += [f'原 PDF：第 {e["pdfPage"]} 页。', '']
        path = ROOT / chapter['folder'] / f'Chapter{chapter["id"]:02}_学习卡.md'
        path.write_text('\n'.join(md))
    shared = TOOLS.parent / '通用'
    template = (WEB / 'index.html').read_text().replace('__APP_CSS__', (WEB / 'app.css').read_text() + '\n' + (WEB / 'hub.css').read_text() + '\n' + (shared / 'hover-translations.css').read_text()).replace('__APP_JS__', (WEB / 'timeline-core.js').read_text() + '\n' + (WEB / 'speech-queue.js').read_text() + '\n' + (WEB / 'mp3-index.js').read_text() + '\n' + (shared / 'hover-translations.js').read_text() + '\n' + (WEB / 'app.js').read_text()).replace('__SITE_URL__', args.site_url)
    def page(data):
        return template.replace('__STUDY_DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c'))
    # Local pages use the same indexed audio included in the portable PC pack.
    export_root = REPO / '_exports/王陆四章PC听读'
    local_tracks = [{**t, 'file': os.path.relpath(export_root / 'audio' / (t['id'] + '.mp3'), ROOT)} if t.get('mp3Index') else t for t in tracks]
    (ROOT / '手机听读.html').write_text(page({**dataset, 'tracks': local_tracks, 'localAudioIndexed': True}))
    if args.export_pc:
        from export_pc_pack import export_pc
        export_pc(dataset, template, export_root, ROOT, REPO)
    site = args.site_dir
    hosted = {**dataset, 'pdfHref': '/source/chapter11.pdf'}
    public = site / 'public'
    (public / 'study').mkdir(parents=True, exist_ok=True)
    (public / 'study/index.html').write_text(page(hosted))
    (public / 'source').mkdir(exist_ok=True)
    shutil.copyfile(ROOT / official['sourcePdf'], public / 'source/chapter11.pdf')
    save(public / 'manifest.webmanifest', {'name': '英语听读 · Oxford 与雅思', 'short_name': '英语听读',
         'start_url': '/study/index.html', 'scope': '/', 'display': 'standalone',
         'background_color': '#f8f6f1', 'theme_color': '#17635c',
         'icons': [{'src': '/icon.svg', 'sizes': 'any', 'type': 'image/svg+xml', 'purpose': 'any'}]})
    (public / 'icon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"><rect width="192" height="192" rx="46" fill="#17635c"/><path d="M38 49q29-9 58 8 29-17 58-8v91q-29-9-58 8-29-17-58-8z" fill="#fff9ea"/><path d="M96 58v89" stroke="#17635c" stroke-width="5"/><path d="M53 76h28m-28 18h28m29-18h28m-28 18h28" stroke="#b99b56" stroke-width="5"/></svg>')
    html_hash = hashlib.sha256((public / 'study/index.html').read_bytes()).hexdigest()[:12]
    (public / 'sw.js').write_text("""const CACHE='ielts-shell-""" + html_hash + """';
self.addEventListener('install',event=>event.waitUntil((async()=>{const cache=await caches.open(CACHE);const response=await fetch('/study/index.html',{cache:'reload'});if(!response.ok)throw new Error('Shell unavailable');/* Store a fresh Response: the host redirects index.html to /study/. A redirected response cannot safely answer every offline navigation. */await cache.put('/study/index.html',new Response(await response.text(),{headers:{'Content-Type':'text/html; charset=utf-8'}}));await cache.addAll(['/manifest.webmanifest','/icon.svg']);await self.skipWaiting()})()));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('ielts-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{const url=new URL(event.request.url);if(url.origin!==location.origin||event.request.method!=='GET'||url.pathname.startsWith('/api/')||url.pathname.startsWith('/source/'))return;if(event.request.mode==='navigate'){event.respondWith(fetch(event.request).catch(()=>caches.match('/study/index.html')));return}if(['/manifest.webmanifest','/icon.svg'].includes(url.pathname))event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request)))});
""")
    route = site / 'app/api/audio/[id]'
    route.mkdir(parents=True, exist_ok=True)
    save(route / 'sources.json', {t['id']: {'url': t['url'], 'pageUrl': t['pageUrl'], **({'mp3Index': t['mp3Index']} if t.get('mp3Index') else {})} for t in tracks})
    shutil.copyfile(WEB / 'audio-route.ts', route / 'route.ts')
    shutil.copyfile(WEB / 'audio-range.ts', route / 'audio-range.ts')
    (site / 'app/page.tsx').write_text('import { redirect } from "next/navigation";\nexport default function Page(){redirect("/study/index.html")}\n')
    (site / 'app/layout.tsx').write_text('import type { Metadata } from "next";\nimport "./globals.css";\nexport const metadata:Metadata={title:"英语听读 · Oxford 与雅思",description:"Oxford 3000、750 常用短语与雅思听力，同一入口学习",icons:{icon:"/icon.svg"}};\nexport default function RootLayout({children}:{children:React.ReactNode}){return <html lang="zh-CN"><body>{children}</body></html>}\n')
    save(WEB / 'site.json', {'project_id': PROJECT_ID, 'url': args.site_url, 'access': 'private'})
    save(ROOT / 'data/study_build_report.json', {'entries': len(entries), 'chapters': {c['id']: sum(e['chapter'] == c['id'] for e in entries) for c in chapters}, 'collections': {c['id']: sum(e['collection'] == c['id'] for e in entries) for c in collections}, 'audioTracks': len(tracks), 'ieltsSyncedTracks': len(timing['tracks']), 'ieltsAudioCues': sum(len(t['cues']) for t in timing['tracks'].values()), 'totalAudioCues': sum(len(t['cues']) for t in tracks), 'originalFramesUnchanged': all(t['mp3Index']['audioFramesUnchanged'] for t in timing['tracks'].values()), 'ieltsAudioSourceRevision': IELTS_SOURCE_REVISION, 'oxfordExampleMatches': enriched, 'chapter3PhotoCorrectionPreserved': True, 'htmlBytes': (ROOT / '手机听读.html').stat().st_size})
    print('BUILT', len(entries), 'entries;', len(tracks), 'original tracks;', enriched, 'extension examples')
    print(out)


if __name__ == '__main__':
    main()
