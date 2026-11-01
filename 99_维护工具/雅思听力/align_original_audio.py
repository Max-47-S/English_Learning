"""Detect real utterance boundaries and align official recordings with study entries.

Intermediate PCM and recognition output remain in the ignored _cache directory.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import json
import subprocess
import wave

import numpy as np

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1] / '05_听力与歌曲/雅思王听力语料库'
CACHE = TOOLS / '_cache/alignment_audio'
RATE = 16000


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def read_pcm(track):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f'{track["id"]}.wav'
    if not path.exists():
        subprocess.run(['/usr/bin/afconvert', '-f', 'WAVE', '-d', 'LEI16@16000', '-c', '1',
                        str(ROOT / track['file']), str(path)], check=True, capture_output=True)
    with wave.open(str(path)) as reader:
        assert reader.getframerate() == RATE and reader.getnchannels() == 1
        return np.frombuffer(reader.readframes(reader.getnframes()), '<i2')


def detect_spans(samples, threshold=.004, join=.4, minimum=.14):
    # 10 ms RMS frames; only the actual voiced samples set timing, never duration/count.
    size = len(samples) // 160
    chunks = samples[:size * 160].reshape(size, 160).astype(np.float32) / 32768
    energy = np.sqrt((chunks * chunks).mean(axis=1))
    active = np.flatnonzero(energy > threshold)
    if not len(active):
        return []
    runs = np.split(active, np.flatnonzero(np.diff(active) > round(join * 100)) + 1)
    return [{'start': round(max(0., (int(run[0]) / 100) - .08), 3),
             'end': round((int(run[-1]) + 1) / 100 + .12, 3),
             'active': len(run) / 100}
            for run in runs if (int(run[-1]) - int(run[0]) + 1) / 100 >= minimum and len(run) >= 6]


def detect_track(track):
    target = CACHE / f'{track["id"]}.boundaries.json'
    if target.exists():
        return json.loads(target.read_text())
    samples = read_pcm(track)
    spans = detect_spans(samples)
    result = {'track': track['id'], 'duration': len(samples) / RATE, 'spans': spans}
    save(target, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tracks', nargs='*')
    args = parser.parse_args()
    data = json.loads((ROOT / 'data/mobile_study.json').read_text())
    tracks = [t for t in data['tracks'] if not args.tracks or t['id'] in args.tracks]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(detect_track, t): t for t in tracks}
        for future in as_completed(jobs):
            result = future.result()
            t = jobs[future]
            group_ids = {g['id'] for c in data['chapters'] for g in c['groups']
                         if t['id'] in g['trackIds'].values()}
            expected = sum(e['group'] in group_ids for e in data['entries'])
            print(t['id'], 'expected', expected, 'voiced spans', len(result['spans']),
                  'first', [(s['start'], s['end']) for s in result['spans'][:6]],
                  'last', [(s['start'], s['end']) for s in result['spans'][-3:]], flush=True)


if __name__ == '__main__':
    main()
