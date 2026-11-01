"""Adapt existing Oxford packs without changing their content, audio or timing."""
from collections import Counter
from pathlib import Path
from urllib.parse import quote
import json
import os

REPO = Path(__file__).resolve().parents[2]
PINNED_REVISION = '3a5c95b9647b24abdcfa72eed1c423718b7b4adb'
PACKS = [
    ('oxford3000', 'Oxford 3000', 'Oxford3000_学习包', 3306),
    ('phrases750', '750 常用短语', 'OxfordPhraseList_学习包', 750),
]


def add_packs(chapters, entries, tracks, local_html_root):
    credits = {}
    for chapter in chapters:
        chapter['collection'] = 'ielts'
    for entry in entries:
        entry['collection'] = 'ielts'
    for pack_id, title, folder, expected in PACKS:
        root = REPO / '01_词汇与短语' / folder
        vocab = json.loads((root / 'data/vocabulary.json').read_text())
        timeline = json.loads((root / 'data/audio_timeline.json').read_text())
        assert len(vocab) == len(timeline['entries']) == expected
        counts = Counter(v['level'] for v in vocab)
        track_id = pack_id + '-recording'
        groups = [{'id': pack_id + '-all', 'title': f'全部 · {expected:,} 条', 'all': True,
                   'trackIds': {'default': track_id}}]
        groups += [{'id': pack_id + '-' + level, 'title': f'{level} · {count} 条',
                    'trackIds': {'default': track_id}} for level, count in counts.items()]
        chapters.append({'id': pack_id, 'title': title, 'collection': pack_id, 'groups': groups,
                         'audioTitle': '真人词典发音' if pack_id == 'oxford3000' else '短语学习包音频',
                         'audioSubtitle': '真人 · 逐词同步' if pack_id == 'oxford3000' else '真人 / AI · 逐词同步'})
        audio_file = root / timeline['file']
        relative = audio_file.relative_to(REPO).as_posix()
        cues = []
        for v, cue in zip(vocab, timeline['entries']):
            assert v['id'] == cue['id'] and v['level'] == cue['level']
            entry_id = f'{pack_id}-{v["id"]:04}'
            source_ids = cue.get('source_ids') or [cue['source_id']]
            credit_ids = []
            for source_id in source_ids:
                key = pack_id + ':' + source_id
                source = timeline['sources'][source_id]
                credits[key] = {k: source[k] for k in ['title', 'artist', 'credit', 'copyright', 'license',
                                 'license_url', 'page_url', 'collection', 'kind', 'processing', 'voice'] if source.get(k)}
                credit_ids.append(key)
            phrase = v.get('phrase') or v.get('word')
            entries.append({'id': entry_id, 'chapter': pack_id, 'collection': pack_id,
                'group': pack_id + '-' + v['level'], 'order': v['id'], 'level': v['level'],
                'levelOrder': v['level_index'], 'word': phrase, 'meaning': v['meaning_zh'],
                'source': pack_id, 'pos': v.get('pos', ''), 'ipa': v.get('ipa', ''),
                'homograph': v.get('homograph', ''), 'qualifier': v.get('qualifier', ''),
                'phrases': v.get('phrases') or [f'{p["english"]}（{p["chinese"]}）' for p in v.get('collocations', [])],
                'example': v['example'], 'wordForms': v.get('word_forms', ''),
                'usageNote': v.get('usage_note', ''), 'referenceUrl': v.get('reference_url', ''),
                'audioKind': cue['kind'], 'audioNotes': cue.get('notes', []),
                'audioText': cue.get('audio_text', phrase), 'audioCreditIds': credit_ids,
                'sourcePage': v['pdf_page']})
            cues.append({'entryId': entry_id, 'start': cue['start'],
                         'spokenEnd': cue['spoken_end'], 'end': cue['end']})
        tracks.append({'id': track_id, 'chapter': pack_id, 'direction': '', 'title': title + ' · 完整连续音频',
            'file': os.path.relpath(audio_file, local_html_root), 'filename': audio_file.name,
            'bytes': audio_file.stat().st_size, 'duration': timeline['encoded_duration_seconds'],
            'url': f'https://raw.githubusercontent.com/Max-47-S/English_Learning/{PINNED_REVISION}/' + quote(relative, safe='/'),
            'pageUrl': f'https://github.com/Max-47-S/English_Learning/tree/{PINNED_REVISION}/' + quote(root.relative_to(REPO).as_posix(), safe='/'),
            'cues': cues, 'humanEntries': timeline['human_entries'], 'aiEntries': timeline['ai_entries']})
        assert all(a['start'] < a['spokenEnd'] <= a['end'] and a['end'] <= b['start'] + .001
                   for a, b in zip(cues, cues[1:]))
    collections = [
        {'id': 'oxford3000', 'title': 'Oxford 3000', 'subtitle': '3,306 条 · 真人发音', 'defaultMode': 'original'},
        {'id': 'phrases750', 'title': '750 常用短语', 'subtitle': '搭配 · 例句 · 用法', 'defaultMode': 'original'},
        {'id': 'ielts', 'title': '雅思听力', 'subtitle': 'Chapter 3 / 4 / 5 / 11', 'defaultMode': 'word'},
    ]
    return collections, credits
