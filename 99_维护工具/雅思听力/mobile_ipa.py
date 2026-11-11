"""Load the 48 pronunciation cards and their finished audio into the study hub."""

import hashlib
import json
import os
from pathlib import Path
import shutil

from build_ipa_audio import PACK, read_json


GROUPS = (
    ('monophthong', '单元音', 12),
    ('diphthong', '双元音', 8),
    ('consonant', '辅音', 24),
    ('cluster', '辅音组合', 4),
)
CHAPTER = 'ipa-48'
REFERENCE = 'https://fonetika.ff.cuni.cz/o-fonetice/foneticka-transkripce/ipa-transcription-english/'


def add_ipa(collections, chapters, entries, tracks, credits, root, public):
    cards = read_json(PACK / 'data/cards.json')
    timeline = read_json(PACK / 'data/timeline.json')
    recordings = read_json(PACK / 'data/recordings.json')
    source_audio = PACK / 'audio' / timeline['file']
    if hashlib.sha256(source_audio.read_bytes()).hexdigest() != timeline['sha256']:
        raise ValueError('The IPA practice audio and timeline do not match. Run build_ipa_audio.py.')

    cue_ids = [cue['entryId'] for cue in timeline['cues']]
    expected_ids = ['ipa-' + card['id'] for card in cards]
    if cue_ids != expected_ids or len(set(cue_ids)) != 48:
        raise ValueError('The IPA timeline must match all 48 cards in order.')
    track_id = 'ipa-follow-' + timeline['sha256'][:12]
    groups = [{'id': 'ipa-all', 'title': '全部音标', 'count': len(cards),
               'all': True, 'trackIds': {'default': track_id}}]
    group_names = {}
    for key, title, expected in GROUPS:
        count = sum(card['group'] == key for card in cards)
        if count != expected:
            raise ValueError(f'Expected {expected} IPA cards in {key}, got {count}.')
        groups.append({'id': 'ipa-' + key, 'title': title, 'count': count,
                       'trackIds': {'default': track_id}})
        group_names[key] = title

    collections.append({
        'id': 'ipa', 'title': '48 音标', 'subtitle': '真人示范 · 三遍跟读',
        'defaultMode': 'original',
        'note': '20 个元音、24 个辅音和 4 个辅音组合。点按音标或例词可试听。'
                '1× 已将真人录音放慢。连续跟读时，每项示范三遍，每遍都有停顿。',
    })
    chapters.append({
        'id': CHAPTER, 'collection': 'ipa', 'title': '48 音标',
        'groups': groups, 'audioTitle': '48 音标 · 真人慢速跟读',
        'audioSubtitle': '真人录音 · 跟读三遍',
    })
    for order, (card, cue) in enumerate(zip(cards, timeline['cues']), 1):
        examples = []
        for item in card['examples']:
            prefix, target, suffix = item['spelling'].split('|')
            examples.append({'prefix': prefix, 'target': target, 'suffix': suffix,
                             'word': prefix + target + suffix, 'ipa': item['ipa'],
                             'meaning': item['meaning']})
        if not examples or len(cue['parts']) != len(examples) + 1:
            raise ValueError(f'Missing an IPA sound or example cue: {card["id"]}')
        recording_ids = [card['sound']['source'], *(item['source'] for item in card['examples'])]
        credit_ids = []
        for key in dict.fromkeys(recording_ids):
            recording = recordings[key]
            credit_id = 'ipa-source-' + key
            credits[credit_id] = {**recording, 'credit': recording['title']}
            credit_ids.append(credit_id)
        entries.append({
            'id': cue['entryId'], 'chapter': CHAPTER, 'group': 'ipa-' + card['group'],
            'collection': 'ipa', 'source': 'ipa', 'order': order,
            'word': '/' + card['symbol'] + '/', 'pos': group_names[card['group']],
            'meaning': ' · '.join(item['word'] + ' ' + item['meaning'] for item in examples),
            'ipaTip': card['tip'], 'ipaModelNote': card['sound'].get('note', ''),
            'ipaExamples': examples, 'audioKind': 'human_recording', 'audioCreditIds': credit_ids,
        })

    relative_asset = 'audio/' + timeline['file']
    hosted_audio = public / relative_asset
    hosted_audio.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_audio, hosted_audio)
    tracks.append({
        'id': track_id, 'chapter': CHAPTER, 'title': '完整 48 音标 · 每项跟读三遍',
        'file': Path(os.path.relpath(source_audio, root)).as_posix(),
        'staticUrl': '/' + relative_asset + '?v=' + timeline['sha256'][:12],
        'filename': timeline['file'], 'bytes': timeline['bytes'],
        'duration': timeline['duration'], 'cues': timeline['cues'],
        'humanEntries': len(cards), 'aiEntries': 0, 'pageUrl': REFERENCE,
    })
