"""Lossless MP3 indexing, real voice boundaries, and checked book-order alignment.

Intermediate MP3/PCM/model/ASR artifacts stay in ignored _cache/. The export only
contains small index prefixes and timing metadata; original audio frames are kept.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path
import argparse
import base64
import hashlib
import json
import re
import time
import unicodedata

import numpy as np
from ielts_text_fixes import fix_wrapped_phrases

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1] / '05_听力与歌曲/雅思王听力语料库'
CACHE = TOOLS / '_cache/alignment_v2'
MODEL = TOOLS / '_cache/models/whisper-base.en-mlx-4bit'
RATE = 16000
VERSION = 'lossless-mp3-voiced-spans-v2'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load(path):
    return json.loads(path.read_text())


def detect_spans(samples, threshold=.004, join=.4):
    size = len(samples) // 160
    frames = samples[:size * 160].reshape(size, 160).astype(np.float32) / 32768
    active = np.flatnonzero(np.sqrt((frames * frames).mean(axis=1)) > threshold)
    if not len(active):
        return []
    runs = np.split(active, np.flatnonzero(np.diff(active) > round(join * 100)) + 1)
    duration = len(samples) / RATE
    return [{'start': round(max(0., int(run[0]) / 100 - .08), 3),
             'end': round(min(duration, (int(run[-1]) + 1) / 100 + .12), 3),
             'active': round(len(run) / 100, 3)}
            for run in runs if (int(run[-1]) - int(run[0]) + 1) >= 14 and len(run) >= 6]


def decode_track(track):
    import av
    CACHE.mkdir(parents=True, exist_ok=True)
    tid = track['id']
    meta_path, pcm_path = CACHE / f'{tid}.pcm.json', CACHE / f'{tid}.npy'
    source = (ROOT / track['file']).read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    if meta_path.exists() and pcm_path.exists():
        meta = load(meta_path)
        if meta.get('sourceSha256') == source_hash and meta.get('version') == VERSION:
            return meta
    indexed = CACHE / f'{tid}.indexed.mp3'
    packets, first = [], None
    with av.open(str(ROOT / track['file'])) as inp, av.open(str(indexed), 'w', format='mp3',
            options={'write_xing': '1', 'id3v2_version': '3'}) as out:
        stream = inp.streams.audio[0]
        output = out.add_stream_from_template(stream)
        out.metadata.clear()
        output.metadata.clear()
        for packet in inp.demux(stream):
            if packet.dts is None:
                continue
            if first is None:
                first = packet.pos
            packets.append(bytes(packet))
            packet.stream = output
            out.mux(packet)
    body, fixed = b''.join(packets), indexed.read_bytes()
    prefix_length = len(fixed) - len(body)
    assert body == source[first:first + len(body)], f'{tid}: original MP3 frames are not contiguous'
    assert fixed[prefix_length:] == body, f'{tid}: remux changed original MP3 frames'
    parts = []
    with av.open(str(indexed)) as container:
        resampler = av.AudioResampler(format='s16', layout='mono', rate=RATE)
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                parts.append(converted.to_ndarray().reshape(-1))
        for converted in resampler.resample(None):
            parts.append(converted.to_ndarray().reshape(-1))
    samples = np.concatenate(parts)
    np.save(pcm_path, samples)
    meta = {'version': VERSION, 'track': tid, 'sourceSha256': source_hash,
            'sampleRate': RATE, 'duration': len(samples) / RATE, 'spans': detect_spans(samples),
            'mp3Index': {'prefixBase64': base64.b64encode(fixed[:prefix_length]).decode(),
                         'sourceOffset': first, 'bodyBytes': len(body), 'bytes': len(fixed),
                         'sha256': hashlib.sha256(fixed).hexdigest(), 'audioFramesUnchanged': True}}
    save(meta_path, meta)
    return meta


def vocabulary_spans(track, meta):
    tid = track['id']
    if track['chapter'] == 11:
        offset = 2 if tid == 'c11-01' else 1 if tid in ('c11-03', 'c11-05', 'c11-07') else 0
    elif track['direction'] == '纵向测试':
        offset = 4 if tid in ('c4-v01', 'c4-v04') else 3
    else:
        offset = 4 if tid == 'c4-h01' else 3 if tid in ('c3-h01', 'c4-h04', 'c5-h01') else 2
    end = len(meta['spans'])
    if track['chapter'] != 11 and meta['spans'][-1]['end'] - meta['spans'][-1]['start'] > 4:
        end -= 1
    return meta['spans'][offset:end], {'leadingSpans': offset, 'trailingSpans': len(meta['spans']) - end}


def ordered(track, entries):
    if track['direction'] != '纵向测试':
        return entries
    columns = 3 if track['chapter'] == 5 else 4
    return [entry for column in range(columns) for entry in entries[column::columns]]


def normalize(text):
    text = unicodedata.normalize('NFKD', text).lower()
    for a, b in [('centre', 'center'), ('colour', 'color'), ('mould', 'mold'),
                 ('licence', 'license'), ('organisation', 'organization'), ('analyse', 'analyze')]:
        text = text.replace(a, b)
    return re.sub('[^a-z0-9]', '', text)


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b), autojunk=False).ratio()


def transcribe(samples, spans):
    import mlx_whisper
    clips = []
    for span in spans:
        clips.extend([samples[int(span['start'] * RATE):int(span['end'] * RATE)].astype(np.float32) / 32768,
                      np.zeros(11200, np.float32)])
    result = mlx_whisper.transcribe(np.concatenate(clips), path_or_hf_repo=str(MODEL),
        language='en', temperature=0, without_timestamps=True, word_timestamps=False,
        condition_on_previous_text=False, no_speech_threshold=None, verbose=None)
    return result['text'].strip()


def recognize(track, meta, spans):
    target = CACHE / f'{track["id"]}.recognition.json'
    stamp = hashlib.sha256(json.dumps(spans, sort_keys=True).encode()).hexdigest()
    result = load(target) if target.exists() else {}
    if result.get('spanHash') != stamp or result.get('sourceSha256') != meta['sourceSha256']:
        result = {'spanHash': stamp, 'sourceSha256': meta['sourceSha256'], 'blocks': []}
    blocks, i = [], 0
    while i < len(spans):
        j, duration = i, 0.
        while j < len(spans) and j - i < 12 and duration + spans[j]['end'] - spans[j]['start'] + .7 <= 27:
            duration += spans[j]['end'] - spans[j]['start'] + .7
            j += 1
        j = max(i + 1, j)
        blocks.append((i, j))
        i = j
    samples = np.load(CACHE / f'{track["id"]}.npy', mmap_mode='r')
    for index, (start, end) in enumerate(blocks):
        if index < len(result['blocks']) and result['blocks'][index]['range'] == [start, end]:
            continue
        result['blocks'].append({'range': [start, end], 'text': transcribe(samples, spans[start:end])})
        save(target, result)
    return result


def align_exception(track, meta, spans, expected):
    """Resolve an extra or split voiced segment against the known word sequence."""
    path = CACHE / f'{track["id"]}.individual.json'
    result = load(path) if path.exists() else {'texts': []}
    samples = np.load(CACHE / f'{track["id"]}.npy', mmap_mode='r')
    result['texts'].extend([None] * (len(spans) - len(result['texts'])))
    for i, text in enumerate(result['texts']):
        if text is None:
            result['texts'][i] = transcribe(samples, [spans[i]])
            save(path, result)
    texts = result['texts']
    correction_file = ROOT / 'data/original_audio_alignment_corrections.json'
    corrections = load(correction_file) if correction_file.exists() else {'merges': []}
    forced = [c for c in corrections['merges'] if c['track'] == track['id']]
    if forced:
        by_id = {c['entryId']: c for c in forced}
        mapping, cursor = [], 0
        for entry in expected:
            count = 1
            if entry['id'] in by_id:
                correction = by_id[entry['id']]
                assert correction['sourceSha256'] == meta['sourceSha256']
                assert correction['spanIndices'][0] == cursor
                count = len(correction['spanIndices'])
            indices = list(range(cursor, cursor + count))
            mapping.append({'start': spans[cursor]['start'], 'end': spans[cursor + count - 1]['end'],
                            'spanIndices': indices, 'heard': ' '.join(texts[k] for k in indices)})
            cursor += count
        assert cursor == len(spans)
        return mapping, []
    n, m = len(expected), len(spans)
    costs = np.full((n + 1, m + 1), np.inf)
    costs[0, 0] = 0
    back = {}
    for i in range(n + 1):
        for j in range(m + 1):
            here = costs[i, j]
            if not np.isfinite(here):
                continue
            choices = []
            if i < n and j < m:
                choices.append((i + 1, j + 1, 1 - similarity(expected[i]['word'], texts[j]), [j]))
            if i < n and j + 1 < m:
                choices.append((i + 1, j + 2, 1.12 - similarity(expected[i]['word'], texts[j] + ' ' + texts[j + 1]), [j, j + 1]))
            if j < m:
                choices.append((i, j + 1, .8 if normalize(texts[j]) else .4, []))
            for ni, nj, extra, indices in choices:
                if here + extra < costs[ni, nj]:
                    costs[ni, nj] = here + extra
                    back[ni, nj] = (i, j, indices)
    if not np.isfinite(costs[n, m]):
        raise ValueError(f'{track["id"]}: cannot map every entry to a real voiced span')
    mapping, extra = [None] * n, []
    i, j = n, m
    while i or j:
        pi, pj, indices = back[i, j]
        if indices:
            mapping[pi] = {'start': spans[indices[0]]['start'], 'end': spans[indices[-1]]['end'],
                           'spanIndices': indices, 'heard': ' '.join(texts[k] for k in indices)}
        else:
            extra.append({'spanIndex': pj, 'heard': texts[pj], **spans[pj]})
        i, j = pi, pj
    assert all(mapping)
    return mapping, extra


def verify_irregular_order(track, spans, entries):
    """Map irregular printed columns by actual spoken phrases, one-to-one."""
    from scipy.optimize import linear_sum_assignment
    path = CACHE / f'{track["id"]}.individual.json'
    result = load(path) if path.exists() else {'texts': []}
    samples = np.load(CACHE / f'{track["id"]}.npy', mmap_mode='r')
    for i in range(len(result['texts']), len(spans)):
        result['texts'].append(transcribe(samples, [spans[i]]))
        save(path, result)
    texts = result['texts']
    baseline = ordered(track, entries)
    positions = {e['id']: i for i, e in enumerate(baseline)}
    scores = np.array([[similarity(text, e['word']) for e in entries] for text in texts])
    costs = np.array([[1 - scores[i, j] + .04 * abs(i - positions[e['id']]) / len(entries)
                       for j, e in enumerate(entries)] for i in range(len(spans))])
    rows, cols = linear_sum_assignment(costs)
    assert len(rows) == len(entries) == len(spans)
    expected = [None] * len(entries)
    checks = []
    for i, j in zip(rows, cols):
        expected[i] = entries[j]
        checks.append({'position': int(i), 'entryId': entries[j]['id'], 'word': entries[j]['word'],
                       'heard': texts[i], 'score': round(float(scores[i, j]), 4)})
    save(CACHE / f'{track["id"]}.order-review.json', checks)
    return expected, checks


def align_track(track, meta, entries):
    spans, excluded = vocabulary_spans(track, meta)
    expected = ordered(track, entries)
    recognition = recognize(track, meta, spans)
    observed = ' '.join(block['text'] for block in recognition['blocks'])
    candidates = {'horizontal': entries}
    for columns in (2, 3, 4, 5, 6):
        candidates[f'columns-{columns}'] = [e for column in range(columns) for e in entries[column::columns]]
    scores = {key: round(similarity(' '.join(e['word'] for e in value), observed), 4)
              for key, value in candidates.items()}
    selected = 'columns-' + ('3' if track['chapter'] == 5 else '4') if track['direction'] == '纵向测试' else 'horizontal'
    order_checks = []
    if track['direction'] == '纵向测试':
        best = max(scores, key=scores.get)
        if scores[best] > .85:
            selected, expected = best, candidates[best]
        elif len(spans) == len(entries):
            expected, order_checks = verify_irregular_order(track, spans, entries)
            selected = 'asr-verified'
            scores[selected] = round(similarity(' '.join(e['word'] for e in expected), observed), 4)
    correction_file = ROOT / 'data/original_audio_alignment_corrections.json'
    order_override = load(correction_file).get('orderOverrides', {}).get(track['id']) if correction_file.exists() else None
    if order_override:
        assert order_override['sourceSha256'] == meta['sourceSha256']
        start = order_override['startPosition']
        by_id = {e['id']: e for e in expected}
        reordered = [by_id[entry_id] for entry_id in order_override['entryIds']]
        assert {e['id'] for e in reordered} == {e['id'] for e in expected[start:]}
        expected = expected[:start] + reordered
        selected = 'reviewed-order'
        scores[selected] = round(similarity(' '.join(e['word'] for e in expected), observed), 4)
    mapping, extras = (spans, []) if len(spans) == len(expected) else align_exception(track, meta, spans, expected)
    cues = []
    for i, (entry, span) in enumerate(zip(expected, mapping)):
        next_start = mapping[i + 1]['start'] if i + 1 < len(mapping) else meta['duration']
        cues.append({'entryId': entry['id'], 'start': span['start'],
                     'spokenEnd': min(span['end'], next_start), 'end': round(next_start, 3)})
    assert len(cues) == len(entries) and len({c['entryId'] for c in cues}) == len(entries)
    assert all(c['start'] < c['spokenEnd'] <= c['end'] for c in cues)
    assert all(a['end'] <= b['start'] + .001 for a, b in zip(cues, cues[1:]))
    blocks = []
    if len(spans) == len(expected):
        for block in recognition['blocks']:
            a, b = block['range']
            blocks.append({'range': [a, b], 'score': round(similarity(' '.join(e['word'] for e in expected[a:b]), block['text']), 4)})
    result = {'sourceSha256': meta['sourceSha256'], 'duration': round(meta['duration'], 6),
              'direction': track['direction'], 'order': selected, 'excluded': excluded,
              'voiceSpans': len(spans), 'entryCount': len(cues), 'orderScores': scores,
              'blockScores': blocks, 'extraSpans': extras, 'orderChecks': order_checks,
              'mergedSpans': [{'entryId': e['id'], **s} for e, s in zip(expected, mapping) if len(s.get('spanIndices', [])) > 1],
              'mp3Index': meta['mp3Index'], 'cues': cues}
    save(CACHE / f'{track["id"]}.aligned.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tracks', nargs='*')
    parser.add_argument('--decode-only', action='store_true')
    args = parser.parse_args()
    data = fix_wrapped_phrases(load(ROOT / 'data/mobile_study.json'))
    tracks = [t for t in data['tracks'] if t['chapter'] in (3, 4, 5, 11) and (not args.tracks or t['id'] in args.tracks)]
    started, decoded = time.monotonic(), {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(decode_track, track): track for track in tracks}
        for future in as_completed(jobs):
            track = jobs[future]
            decoded[track['id']] = future.result()
            print('DECODED', track['id'], len(decoded[track['id']]['spans']), 'spans', flush=True)
    if args.decode_only:
        return
    results, errors = {}, []
    for track in tracks:
        group_ids = {g['id'] for c in data['chapters'] for g in c['groups'] if track['id'] in g['trackIds'].values()}
        entries = [e for e in data['entries'] if e['group'] in group_ids]
        try:
            result = align_track(track, decoded[track['id']], entries)
            results[track['id']] = result
            print('ALIGNED', track['id'], result['entryCount'], 'cues', 'score', result['orderScores'][result['order']],
                  'extras', len(result['extraSpans']), 'elapsed', round(time.monotonic() - started, 1), flush=True)
        except Exception as exc:
            errors.append({'track': track['id'], 'error': str(exc)})
            print('REVIEW', track['id'], str(exc), flush=True)
    save(CACHE / 'run-review.json', {'errors': errors, 'completed': list(results)})
    if results and not errors:
        path = ROOT / 'data/original_audio_timeline.json'
        if args.tracks and path.exists():
            previous = load(path)['tracks']
            previous.update(results)
            results_to_save = previous
        else:
            results_to_save = results
        if not args.tracks:
            assert len(results_to_save) == 59
        save(path, {'version': VERSION,
            'method': 'Lossless MP3 index; decoded voice boundaries; book row/column order; local ASR sequence checks.',
            'sampleRate': RATE, 'tracks': results_to_save})
    print('COMPLETE', len(results), 'tracks', len(errors), 'review items', round(time.monotonic() - started, 1), 'seconds', flush=True)


if __name__ == '__main__':
    main()
