"""Extract static reference vocabulary without running the third-party HTML app."""
from pathlib import Path
from urllib.request import Request, urlopen
import base64
import hashlib
import html
import json
import re

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1] / '05_听力与歌曲/雅思王听力语料库'
CACHE = TOOLS / '_cache/third_party_vocabulary.html'
SOURCE = 'https://github.com/PipiTang233/wanglu-dictation-app'
BLOB = '2004d5360af631d562e72238449b93c0d608b4eb'
CORRECTIONS = ROOT / 'data/manual_text_corrections.json'
GROUPS = {
    3: ('Chapter03_特别名词', '特别名词', [f'3.3-{i}' for i in range(1, 10)]),
    4: ('Chapter04_形容词副词', '形容词副词', ['4.3-1', '4.3-2', '4.3-3', '4.4']),
    5: ('Chapter05_吞音连读', '吞音连读', [f'5.3-{i}' for i in range(1, 13)]),
}


def source_data():
    if not CACHE.exists():
        url = f'https://api.github.com/repos/PipiTang233/wanglu-dictation-app/git/blobs/{BLOB}'
        request = Request(url, headers={'User-Agent': 'English-learning-personal-download',
                                       'Accept': 'application/vnd.github+json'})
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_bytes(base64.b64decode(payload['content']))
    raw = CACHE.read_bytes()
    assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == BLOB
    text = raw.decode('utf-8')
    marker = re.search(r'const\s+VOCAB\s*=\s*', text)
    if not marker:
        raise ValueError('Static vocabulary data not found')
    # Parse only the JSON literal. Never evaluate JavaScript or open the HTML app.
    data, _ = json.JSONDecoder().raw_decode(text[marker.end():])
    return data


def clean(value):
    return str(value).replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')


def md(value):
    return html.escape(clean(value), quote=False).replace('|', r'\|').replace('[', r'\[').replace(']', r'\]')


def apply_corrections(data):
    if not CORRECTIONS.exists():
        return []
    applied = []
    for patch in json.loads(CORRECTIONS.read_text(encoding='utf-8'))['corrections']:
        rows = data[patch['group']]
        start = patch['start_index'] - 1
        assert len(rows) == patch['expected_original_count'], patch['group']
        assert 0 < start < len(rows), patch['group']
        assert rows[start - 1]['w'] == patch['expected_previous_word'], patch['group']
        assert rows[start]['w'] == patch['expected_start_word'], patch['group']
        replacement = patch['entries']
        assert replacement and all(all(isinstance(r.get(k), str) for k in ['w', 'p', 'm'])
                                   for r in replacement), patch['group']
        data[patch['group']] = rows[:start] + replacement
        applied.append({key: value for key, value in patch.items() if key != 'entries'} | {
            'original_entries': len(rows), 'corrected_entries': len(data[patch['group']]),
            'corrected_range': [patch['start_index'], len(data[patch['group']])]})
    return applied


def main():
    data = source_data()
    source_counts = {key: len(rows) for key, rows in data.items()}
    applied = apply_corrections(data)
    report = {'retrieved_date': '2026-11-01', 'source_repository': SOURCE,
              'source_blob_sha': BLOB, 'source_file': '王陆语料库听写练习_v5.html',
              'edition': '网络整理参考版；来源采用旧版分节编号，未声明确切剑桥版次',
              'alignment': '未与 20260920 官方音频逐词核对；不可当作剑21官方原书扫描件',
              'chapters': []}
    if applied:
        report['manual_corrections'] = {
            'file': CORRECTIONS.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(CORRECTIONS.read_bytes()).hexdigest(),
            'applied': applied}
    for chapter, (folder, title, keys) in GROUPS.items():
        directory = ROOT / folder / '文本'
        directory.mkdir(parents=True, exist_ok=True)
        count = sum(len(data[key]) for key in keys)
        heading = f'Chapter {chapter} · {title} · 网络整理参考词表'
        notice = ('本文件为网络整理参考版，含英文、音标和中文提示。'
                  '未与本次官方音频逐词核对，拼写、释义及顺序可能存在差异；'
                  '原书小节编号随版本变化，请按 Test Paper 对照。'
                  '不包含旧版预测试，不代替官方原书文本。')
        markdown = [f'# {heading}', '', notice, '',
                    f'共 {len(keys)} 组、{count} 条。词汇原作者：王陆；网络整理来源：[PipiTang233/wanglu-dictation-app]({SOURCE})。',
                    '', f'来源文件校验值（Git blob SHA）：`{BLOB}`。', '']
        plain = [heading, '', notice, '', f'来源：{SOURCE}', f'条目数：{count}', '']
        for patch in applied:
            if patch['chapter'] == chapter:
                line = f"人工校订：Test Paper {patch['test_paper']} — {patch['note']}"
                markdown += [line, '']
                plain += [line, '']
        for i, key in enumerate(keys, 1):
            name = f'Test Paper {i}' + (' · 副词' if chapter == 4 and i == 4 else '')
            markdown += [f'## {name}', '', f'来源小节：`{key}`；{len(data[key])} 条。', '',
                         '| 序号 | 英文 | 音标 | 中文提示 |', '| ---: | --- | --- | --- |']
            plain += [f'{name}（来源小节 {key}；{len(data[key])} 条）', '']
            for n, row in enumerate(data[key], 1):
                assert all(isinstance(row.get(k), str) for k in ['w', 'p', 'm'])
                markdown.append(f"| {n} | {md(row['w'])} | {md(row['p'])} | {md(row['m'])} |")
                plain.append(f"{n}. {clean(row['w'])} /{clean(row['p'])}/ — {clean(row['m'])}")
            markdown.append('')
            plain.append('')
        stem = f'Chapter{chapter:02d}_网络整理参考词表'
        outputs = []
        for suffix, lines in [('.md', markdown), ('.txt', plain)]:
            file = directory / (stem + suffix)
            file.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
            outputs.append({'file': file.relative_to(ROOT).as_posix(),
                            'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
        report['chapters'].append({'chapter': chapter, 'entries': count, 'groups': len(keys),
                                   'source_groups': {key: len(data[key]) for key in keys},
                                   'original_source_groups': {key: source_counts[key] for key in keys},
                                   'outputs': outputs})
    (ROOT / 'data/reference_text_sources.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('REFERENCE_TEXTS_COMPLETE', [(c['chapter'], c['entries']) for c in report['chapters']])


if __name__ == '__main__':
    main()
