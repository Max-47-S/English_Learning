"""Build ordered Chapter 11 tables from local OCR, keeping page provenance."""
from collections import Counter
from pathlib import Path
import hashlib
import html
import importlib.util
import json
import re

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1] / '05_听力与歌曲/雅思王听力语料库'
PDF = ROOT / 'Chapter11_综合测试/文本/Chapter11_综合测试_剑21版.pdf'


def norm(s):
    s = s.lower().replace('’', "'").replace('‐', '-').replace('–', '-')
    return re.sub(r'\s+', ' ', s).strip()


def reference():
    spec = importlib.util.spec_from_file_location('reference_builder', TOOLS / 'build_reference_texts.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = module.source_data()
    module.apply_corrections(data)
    lookup = {}
    for key, rows in data.items():
        for row in rows:
            lookup.setdefault(norm(row['w']), row)
    return data, lookup


def text(row):
    return row['text'].replace('\n', ' ').strip()


def headword(value, lookup):
    raw = value
    value = re.sub(r'^[•●○□■口ロ☐◯]+\s*', '', value).strip()
    value = re.sub(r'^[oOU]\s+(?=[a-z])', '', value)
    value = re.split(r'\s*[\[［]', value, maxsplit=1)[0].strip()
    if value == raw and len(value) > 1 and value[0] in 'ODQa0':
        candidate = value[1:].strip()
        if norm(value) not in lookup and norm(candidate) in lookup:
            value = candidate
    value = re.sub(r'^[^A-Za-z0-9]+', '', value).strip()
    value = value.replace('（', '(').replace('）', ')')
    if value.endswith('s)') and '(' not in value:
        value = value[:-2] + '(s)'
    return value


def meaning_rows(rows):
    return [r for r in rows if re.search(r'[\u3400-\u9fff]', text(r)) and
            '版权所有' not in text(r) and '中国人民' not in text(r)]


def pairs(words, meanings, lookup, phrase=False):
    words = sorted(words, key=lambda r: -(r['y'] + r['h']))
    normalized = []
    for r in words:
        w = headword(text(r), lookup)
        if not w or re.search(r'[\u3400-\u9fff]', w) or re.match(r'^(?:Chapter|Section)\b|^11[.．]', w, re.I):
            continue
        row = {**r, 'word': w, 'raw_word': text(r)}
        if not phrase and normalized and (text(r).lstrip().startswith('=') or normalized[-1]['word'].endswith('=')):
            normalized[-1]['variants'] = [w.lstrip('=')]
            normalized[-1]['word'] = normalized[-1]['word'].rstrip('=')
            continue
        if phrase and normalized:
            previous = normalized[-1]
            joined = previous['word'] + ' ' + w
            gap = previous['y'] - r['y']
            if norm(joined) in lookup or (0 < gap < .025 and norm(previous['word']) not in lookup):
                previous['word'] = joined
                previous['raw_word'] += ' / ' + text(r)
                previous['bottom'] = r['y']
                continue
        normalized.append(row)
    output = []
    for i, row in enumerate(normalized):
        # English and Chinese share a baseline, but their OCR box heights differ.
        # Comparing box tops accidentally attaches the next Chinese definition.
        top = row['y'] + .012
        bottom = normalized[i + 1]['y'] + .010 if i + 1 < len(normalized) else .061
        selected = [r for r in meanings if bottom < r['y'] <= top]
        selected.sort(key=lambda r: (-(r['y'] + r['h']), r['x']))
        meaning = ''.join(text(r) for r in selected)
        meaning = re.sub(r'^(?:ad[ij]?\.?|аdj\.)\s*', 'adj. ', meaning) if meaning.startswith(('ad.', 'adi.', 'аdj.')) else meaning
        pos = re.match(r'^(adj|adv|n|v|vt|vi|prep|pron|num|conj|int|det|abbr)\.?\s*', meaning, re.I)
        word_pos = pos.group(1).lower() if pos else ''
        if pos:
            meaning = meaning[pos.end():].strip()
        issues = []
        raw_word = row['word']
        w = raw_word
        ref = lookup.get(norm(w))
        ipa = ref['p'] if ref and not any(c in ref['p'] for c in '<>') else ''
        if not meaning:
            issues.append('中文待核对')
        output.append({'word': w, 'meaning': meaning, 'pos': word_pos,
                       'ipa': ipa, 'ipaSource': 'reference' if ipa else '',
                       'ocrWord': raw_word, 'y': row['y'], 'x': row['x'],
                       'variants': row.get('variants', []), 'reviewIssues': issues})
    return output


def main():
    source, lookup = reference()
    raw = json.loads((ROOT / 'data/chapter11_ocr_pages.json').read_text())
    columns = {p['pdf_page']: p for p in json.loads((ROOT / 'data/chapter11_ocr_columns.json').read_text())['pages']}
    assert raw['completed_pages'] == raw['pdf_pages'] == 74
    entries, groups, introductory = [], {}, []
    section, part = 1, 'words'
    group_titles = {'words': '单词训练', 'phrases': '吞音连读', 'ance': 'ance 总结', 'ence': 'ence 总结', 'nn': 'nn 总结'}
    for page in raw['pages']:
        n, observations = page['pdf_page'], page['observations']
        if n <= 2:
            introductory.append({'pdfPage': n, 'lines': [text(r) for r in sorted(observations, key=lambda r: (-r['y'], r['x']))]})
            continue
        heads = [r for r in observations if r['x'] < .65 and
                 (re.match(r'^11[.．]\s*[1-5]', text(r)) or
                  ('训练' in text(r) and ('吞音' in text(r) or '连读' in text(r))) or
                  re.match(r'^[123][.．]\s*(?:ance|ence|nn)', text(r), re.I))]
        phrase_heading = next((r for r in heads if '训练' in text(r)), None)
        events = [{'kind': 'heading', **r} for r in heads]
        # The first part of a mixed page retains the single vocabulary column.
        if n not in columns or phrase_heading:
            minimum = phrase_heading['y'] + phrase_heading['h'] + .008 if phrase_heading else .067
            words = [r for r in observations if .11 < r['x'] < .355 and minimum < r['y'] < .925]
            meanings = meaning_rows([r for r in observations if r['x'] > .60 and minimum < r['y'] < .925])
            events += [{'kind': 'entry', **r} for r in pairs(words, meanings, lookup)]
        if n in columns:
            c = columns[n]['columns']
            left = pairs(c['left_word'], meaning_rows(c['left_meaning']), lookup, True)
            right = pairs(c['right_word'], meaning_rows(c['right_meaning']), lookup, True)
            # The printed tables and the available reference follow horizontal rows.
            for i in range(max(len(left), len(right))):
                for side, rows in enumerate([left, right]):
                    if i < len(rows):
                        r = rows[i]
                        # Pair by row first, even when wrapped lines have different heights.
                        events.append({'kind': 'phrase', **r, 'row_index': i, 'side': side})
        word_events = [e for e in events if e['kind'] != 'phrase']
        word_events.sort(key=lambda r: (-r['y'], r['x']))
        phrase_events = sorted((e for e in events if e['kind'] == 'phrase'), key=lambda r: (r['row_index'], r['side']))
        events = word_events + phrase_events
        for event in events:
            if event['kind'] == 'heading':
                title = text(event)
                match = re.match(r'^11[.．]\s*([1-5])', title)
                if match:
                    section = int(match.group(1));part = 'ance' if section == 5 else 'words'
                elif '训练' in title:
                    part = 'phrases'
                else:
                    match = re.match(r'^[123][.．]\s*(ance|ence|nn)', title, re.I)
                    if match:part = match.group(1).lower()
                continue
            if event['kind'] == 'phrase':
                part = 'phrases'
            group = f'c11-s{section}-{part}'
            group_title = f'Section {section} · {group_titles[part]}' if section < 5 else group_titles[part]
            if group not in groups:groups[group] = {'id': group, 'title': group_title, 'section': section, 'part': part, 'entries': 0}
            groups[group]['entries'] += 1
            entries.append({k: v for k, v in event.items() if k not in ['kind', 'row_index', 'side']} | {
                'id': f'{group}-{groups[group]["entries"]:04d}', 'chapter': 11, 'group': group,
                'order': groups[group]['entries'], 'pdfPage': n, 'bookPage': n + 218, 'source': 'pdf'})
    manual_path = ROOT / 'data/chapter11_manual_corrections.json'
    if manual_path.exists():
        patches = json.loads(manual_path.read_text())
        for patch in patches:
            matched = [e for e in entries if e['pdfPage'] == patch['pdfPage'] and e['ocrWord'] == patch['ocrWord']]
            assert len(matched) == 1, patch
            matched[0].update(patch['set'])
    report = {'sourcePdf': PDF.relative_to(ROOT).as_posix(),
              'sourceSha256': hashlib.sha256(PDF.read_bytes()).hexdigest(), 'pdfPages': 74,
              'engine': raw['engine'], 'entries': entries, 'groups': list(groups.values()),
              'introductory': introductory,
              'notes': ['英文和中文按 PDF 页面 OCR 后分列重组；双栏词组按横向逐行排列。',
                        '音标列优先使用现有参考词库，标记为参考音标；原书音标请对照 PDF。']}
    (ROOT / 'data/chapter11_transcription.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    issues = [e for e in entries if e['reviewIssues'] or not e['meaning']]
    (ROOT / 'data/chapter11_transcription_review.json').write_text(json.dumps(
        {'entries': len(entries), 'groups': report['groups'], 'review': issues}, ensure_ascii=False, indent=2) + '\n')
    print('CHAPTER11_TRANSCRIBED', len(entries), 'entries;', len(issues), 'review records')
    print([(g['title'], g['entries']) for g in report['groups']])
    for e in issues:print(e['pdfPage'],e['ocrWord'],'->',e['word'],e['meaning'],e['reviewIssues'])


if __name__ == '__main__':
    main()
