"""Extract the Oxford 5000 B2-C1 supplement and attach open Chinese glosses."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / '01_词汇与短语/Oxford5000_学习包'
DEFAULT_PDF = REPO / '06_原始资料/Oxford词表/oxford-5000-by-cefr-level.pdf'
OXFORD_PDF_URL = 'https://www.oxfordlearnersdictionaries.com/external/pdf/wordlists/oxford-3000-5000/The_Oxford_5000_by_CEFR_level.pdf'
ECDICT_COMMIT = '39cfb9672c0906b63569e0453c2e6abfb9ab182a'
ECDICT_URL = f'https://github.com/skywind3000/ECDICT/tree/{ECDICT_COMMIT}'

POS = r'(?:n\.|v\.|adj\.|adv\.|prep\.|conj\.|pron\.|exclam\.|number)'
PDF_ENTRY = re.compile(rf'^(?P<head>.+?)\s+(?P<pos>{POS}(?:(?:\s*,\s*|/){POS})*)\s*$')
DICT_POS = re.compile(r'^(n|vt|vi|v|a|adj|adv|prep|pron|conj|interj|exclam)\.\s*')
ROLE = {'n': 'n', 'v': 'v', 'vt': 'v', 'vi': 'v', 'adj': 'a', 'a': 'a',
        'adv': 'adv', 'prep': 'prep', 'pron': 'pron', 'conj': 'conj',
        'exclam': 'exclam', 'interj': 'exclam'}
OXFORD_ROLE = {'n': 'n', 'v': 'v', 'adj': 'a', 'adv': 'adv', 'prep': 'prep',
               'pron': 'pron', 'conj': 'conj', 'exclam': 'exclam', 'number': 'n'}

# The pinned ECDICT export does not contain these word-form/POS combinations.
MANUAL_GLOSSES = {
    'affordable|adj.': '负担得起的；价格可承受的',
    'globalization|n.': '全球化',
    'nursing|adj.': '护理的；护理工作的',
    'screening|n.': '筛查；筛选；放映',
    'trading|n.': '贸易；交易',
    'benchmark|n.': '基准；衡量标准',
    'broadband|n.': '宽带；宽带网络',
    'communist|adj.': '共产主义的',
    'connectivity|n.': '连接能力；连通性',
    'counselling|n.': '咨询；辅导',
    'counter|v.': '反驳；抵制；应对',
    'cryptocurrency|n.': '加密货币',
    'deployment|n.': '部署；调配',
    'diplomatic|n.': '外交人员；外交使节',
    'extremist|n.': '极端分子',
    'feminist|adj.': '女权主义的',
    'listing|n.': '清单；上市',
    'processing|n.': '处理；加工',
    'regardless|adv.': '不管怎样；无论如何',
    'socialist|adj.': '社会主义的',
    'streaming|n.': '流媒体播放；流式传输',
    'trans|adj.': '跨性别的（transgender 的简称）',
    'versus|conj.': '对；与……相对',
    'whatsoever|adv.': '任何；丝毫（用于强调）',
    'trillion|number': '一万亿',
}


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def clean_key(value: str) -> str:
    return ' '.join(value.split()).casefold().replace('’', "'")


def parse_pdf(path: Path) -> list[dict]:
    from pypdf import PdfReader

    entries = []
    level = None
    level_order = Counter()
    for page_no, page in enumerate(PdfReader(str(path)).pages, 1):
        for raw in (page.extract_text() or '').splitlines():
            line = ' '.join(raw.split()).strip()
            if line in {'B2', 'C1'}:
                level = line
                continue
            if (not level or not line or line.startswith('© Oxford')
                    or line.startswith('The Oxford 5000') or re.fullmatch(r'\d+ / \d+', line)):
                continue
            match = PDF_ENTRY.fullmatch(line)
            if not match:
                raise ValueError(f'Unparsed Oxford 5000 PDF line {page_no}: {line}')
            pdf_word = match.group('head').strip()
            word = pdf_word
            qualifier = ''
            qualified = re.fullmatch(r'(.*?)\s*\((.*?)\)', word)
            if qualified:
                word, qualifier = qualified.group(1).strip(), qualified.group(2).strip()
            homograph = ''
            numbered = re.fullmatch(r'([a-z][a-z-]*)([1-9])', word, re.IGNORECASE)
            if numbered:
                word, homograph = numbered.group(1), numbered.group(2)
            level_order[level] += 1
            entries.append({
                'id': len(entries) + 1,
                'word': word,
                'lookup': clean_key(word),
                'pdf_word': pdf_word,
                'homograph': homograph,
                'pos': match.group('pos'),
                'qualifier': qualifier,
                'level': level,
                'order': level_order[level],
                'pdf_page': page_no,
            })
    expected = {'B2': 699, 'C1': 1313}
    if level_order != Counter(expected):
        raise ValueError(f'Unexpected Oxford 5000 counts: {dict(level_order)}')
    if len(entries) != 2012:
        raise ValueError(f'Expected 2012 Oxford 5000 PDF entries, got {len(entries)}')
    return entries


def load_dictionary(path: Path, entries: list[dict]) -> dict[str, dict]:
    wanted = {entry['lookup'] for entry in entries}
    selected = {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            key = clean_key(row.get('word', ''))
            if key in wanted and key not in selected:
                selected[key] = row
    return selected


def roles_for(pos: str) -> set[str]:
    tokens = re.findall(r'(?<![a-z])(n|v|adj|adv|prep|conj|pron|exclam)\.', pos)
    roles = {OXFORD_ROLE[token] for token in tokens}
    if 'number' in pos:
        roles.add('n')
    return roles


def gloss_for(entry: dict, row: dict | None) -> str:
    manual = MANUAL_GLOSSES.get(f"{entry['lookup']}|{entry['pos']}")
    if manual:
        return manual
    if not row:
        return ''
    wanted_roles = roles_for(entry['pos'])
    kept = []
    for raw in row.get('translation', '').replace('\\n', '\n').splitlines():
        text = raw.strip()
        if not text or text.startswith('['):
            continue
        match = DICT_POS.match(text)
        if match:
            role = ROLE[match.group(1)]
            if wanted_roles and role not in wanted_roles:
                continue
            text = text[match.end():]
        text = re.sub(r'\[[^]]+\]', '', text).strip(' ,，;；')
        for meaning in (part.strip() for part in re.split(r'[,，;；]', text)):
            if meaning and meaning not in kept:
                kept.append(meaning)
            if len(kept) >= 4:
                break
        if len(kept) >= 4:
            break
    return '；'.join(kept)


def dictionary_url(word: str) -> str:
    return 'https://www.oxfordlearnersdictionaries.com/definition/english/' + quote(word.casefold(), safe='-')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', type=Path, default=DEFAULT_PDF)
    parser.add_argument('--ecdict', type=Path, required=True,
                        help='Pinned ECDICT CSV; see the package README for its revision.')
    args = parser.parse_args()
    if not args.pdf.is_file() or not args.ecdict.is_file():
        raise FileNotFoundError('Both Oxford PDF and ECDICT CSV must exist.')
    entries = parse_pdf(args.pdf)
    dictionary = load_dictionary(args.ecdict, entries)
    missing = []
    for entry in entries:
        row = dictionary.get(entry['lookup'])
        meaning = gloss_for(entry, row)
        if not meaning:
            missing.append(f"{entry['word']} {entry['pos']}")
        entry.update({
            'meaning_zh': meaning,
            'ipa': (row or {}).get('phonetic', '').replace('ә', 'ə'),
            'ipa_source': 'ECDICT' if (row or {}).get('phonetic') else '',
            'reference_url': dictionary_url(entry['word']),
            'gloss_source': 'ECDICT' if row and f"{entry['lookup']}|{entry['pos']}" not in MANUAL_GLOSSES else 'English_Learning 整理',
        })
    if missing:
        raise ValueError(f'Missing Chinese glosses ({len(missing)}): {missing[:40]}')

    pdf_hash = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    data_dir = PACKAGE / 'data'
    save(data_dir / 'vocabulary.json', entries)
    level_counts = dict(Counter(entry['level'] for entry in entries))
    save(data_dir / 'pdf_metadata.json', {
        'source': 'Oxford Learner’s Dictionaries',
        'source_pdf': args.pdf.name,
        'source_url': OXFORD_PDF_URL,
        'sha256': pdf_hash,
        'pages': 8,
        'entries': len(entries),
        'unique_headwords_after_qualifier_and_homograph_normalization': len({entry['lookup'] for entry in entries}),
        'level_counts': level_counts,
        'reading_order': 'PDF page order; the B2 section followed by C1; columns top-to-bottom and left-to-right.',
        'dictionary_source': 'ECDICT, pinned Git revision ' + ECDICT_COMMIT,
        'dictionary_url': ECDICT_URL,
        'dictionary_entries_matched': len(dictionary),
        'entries_with_ipa_reference': sum(bool(entry['ipa']) for entry in entries),
        'glosses_manually_filled': sum(entry['gloss_source'] == 'English_Learning 整理' for entry in entries),
    })

    levels = {'B2': [], 'C1': []}
    for entry in entries:
        levels[entry['level']].append(entry)
    lines = [
        '# Oxford 5000 新增词表（按 CEFR 分级）', '',
        '> 这是 Oxford 5000 在 Oxford 3000 之外的 B2–C1 补充表；Oxford 3000 基础词仍在独立学习页。词头、词性、级别、顺序和页码依官方 PDF。中文参考释义取自 ECDICT；少量缺项由本项目简要补译。参考音标来自 ECDICT，未经逐条人工校音。网站使用设备系统语音连续朗读。', '',
        f'> PDF SHA-256：`{pdf_hash}`。统计为 {len(entries):,} 条词性／级别记录，B2 {level_counts["B2"]:,} 条，C1 {level_counts["C1"]:,} 条；保留 PDF 中同形词的不同记录。', '',
        '[统一手机听读页](https://ielts-listening-nov-2026-wx.nimble-goby-1176.chatgpt.site/study/?collection=oxford5000) · [Oxford 官方 Oxford 5000 PDF](../../06_原始资料/Oxford词表/oxford-5000-by-cefr-level.pdf) · [Oxford 词表说明](https://www.oxfordlearnersdictionaries.com/about/wordlists/oxford3000-5000)', '',
    ]
    for level, rows in levels.items():
        lines += [f'## {level}（{len(rows):,} 条）', '', '| 序号 | 单词 | 词性 | 中文参考释义 | 音标参考 | PDF 页 |', '| ---: | --- | --- | --- | --- | ---: |']
        for entry in rows:
            word = entry['word'] + (f"{entry['homograph']}" if entry['homograph'] else '')
            if entry['qualifier']:
                word += f"（{entry['qualifier']}）"
            safe = lambda value: str(value).replace('|', '\\|').replace('\n', '<br>')
            lines.append(f"| {entry['order']} | {safe(word)} | {safe(entry['pos'])} | {safe(entry['meaning_zh'])} | {safe(entry['ipa'])} | {entry['pdf_page']} |")
        lines.append('')
    (PACKAGE / 'Oxford5000_新增词表.md').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print('BUILT', len(entries), 'entries;', level_counts, 'dictionary matches', len(dictionary),
          'manual glosses', sum(entry['gloss_source'] == 'English_Learning 整理' for entry in entries),
          'IPA references', sum(bool(entry['ipa']) for entry in entries))
    print(PACKAGE / 'Oxford5000_新增词表.md')


if __name__ == '__main__':
    main()
