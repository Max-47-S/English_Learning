"""Assemble a slow, pitch-preserving practice track from attributed recordings."""

import argparse
from array import array
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from threading import Lock
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
import wave


TOOLS = Path(__file__).resolve().parent
PACK = TOOLS.parents[1] / '01_词汇与短语/48音标_学习包'
CACHE = TOOLS / '_cache/ipa'
TRACK = 'ipa-48-follow-along.mp3'
RATE = 24000
TEMPO = 0.8
REPETITIONS = 3
SOUND_GAP = 1.8
WORD_GAP = 2.25
CARD_TAIL = 0.65
DOWNLOAD_LOCK = Lock()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fetch_recording(source, proxy):
    url = source['url']
    if urlsplit(url).scheme != 'https' or urlsplit(url).hostname != 'upload.wikimedia.org':
        raise ValueError(f'Unexpected recording host for {source["title"]}')
    key = hashlib.sha256(url.encode()).hexdigest()[:20]
    path = CACHE / 'recordings' / (key + Path(urlsplit(url).path).suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = source['bytes']
    expected_hash = source['sha1']

    def matches(content):
        return len(content) == size and hashlib.sha1(content).hexdigest() == expected_hash

    if path.is_file() and matches(path.read_bytes()):
        return path
    with DOWNLOAD_LOCK:
        if path.is_file() and matches(path.read_bytes()):
            return path
        opener = build_opener(ProxyHandler({'https': proxy}) if proxy else ProxyHandler())
        request = Request(url, headers={
            'User-Agent': 'EnglishLearningPersonal/1.0 (+https://github.com/Max-47-S/English_Learning)',
        })
        for attempt in range(4):
            time.sleep(2)
            try:
                with opener.open(request, timeout=30) as response:
                    content = response.read(size + 1)
                break
            except HTTPError as error:
                if attempt == 3 or error.code not in (429, 500, 502, 503, 504):
                    raise
                retry_after = error.headers.get('Retry-After')
                delay = 30 * (attempt + 1) if error.code == 429 else 3
                if retry_after:
                    try:
                        deadline = (float(retry_after) if retry_after.isdigit()
                                    else parsedate_to_datetime(retry_after).timestamp() - time.time())
                        delay = max(delay, deadline)
                    except (TypeError, ValueError, OverflowError):
                        pass
                if error.code == 429:
                    print(f'Wikimedia rate limit, retry in {delay:.0f}s', flush=True)
                time.sleep(delay)
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))
        if not matches(content):
            raise ValueError('Downloaded media does not match the pinned size and checksum')
        temporary = path.with_suffix(path.suffix + '.part')
        temporary.write_bytes(content)
        temporary.replace(path)
        return path


def silence(seconds):
    return bytes(round(RATE * seconds) * 2)


def trim_and_level(raw):
    samples = array('h')
    samples.frombytes(raw)
    if sys.byteorder != 'little':
        samples.byteswap()
    window = RATE // 100
    levels = [
        (sum(x * x for x in samples[i:i + window]) / window) ** 0.5
        for i in range(0, len(samples), window)
    ]
    if not levels or max(levels) < 10:
        raise ValueError('Decoded recording contains no audible speech')
    threshold = max(10, max(levels) * 0.02)
    audible = [i for i, rms in enumerate(levels) if rms >= threshold]
    start = max(0, audible[0] * window - 3 * window)
    end = min(len(samples), (audible[-1] + 1) * window + 4 * window)
    samples = samples[start:end]
    peak = max(abs(x) for x in samples)
    gain = min(26000 / peak, 4200 / max(levels))
    fade = max(1, min(RATE // 200, len(samples) // 4))
    for i, value in enumerate(samples):
        edge = min(1, i / fade, (len(samples) - i - 1) / fade)
        samples[i] = round(value * gain * edge)
    if sys.byteorder != 'little':
        samples.byteswap()
    return silence(0.05) + samples.tobytes() + silence(0.05)


def prepare_clip(ffmpeg, path, excerpt):
    filters = ['highpass=f=65']
    if excerpt:
        filters.extend((f'atrim=start={excerpt[0]}:end={excerpt[1]}', 'asetpts=PTS-STARTPTS'))
    filters.append(f'atempo={TEMPO}')
    raw = subprocess.run(
        [ffmpeg, '-v', 'error', '-i', str(path), '-vn', '-af', ','.join(filters),
         '-f', 's16le', '-ac', '1', '-ar', str(RATE), 'pipe:1'],
        check=True, stdout=subprocess.PIPE,
    ).stdout
    return trim_and_level(raw)


def seconds(frames):
    return round(frames / RATE, 6)


def build(ffmpeg, proxy):
    cards = read_json(PACK / 'data/cards.json')
    sources = read_json(PACK / 'data/recordings.json')
    if len(cards) != 48 or len({card['symbol'] for card in cards}) != 48:
        raise ValueError('Expected 48 different IPA teaching items')
    specs = {}
    for card in cards:
        for item in [card['sound'], *card['examples']]:
            key = item['source'], tuple(item.get('excerpt', ()))
            specs[key] = sources[item['source']]
    for source in specs.values():
        if source['kind'] != 'human_recording' or not source['artist'] or not source['license_url']:
            raise ValueError(f'Recording lacks human attribution or reuse terms: {source["title"]}')

    def load_sample(pair):
        key, source = pair
        try:
            path = fetch_recording(source, proxy)
            return key, prepare_clip(ffmpeg, path, key[1]), None
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            return key, None, f'{source["title"]}: {error}'

    print(f'Preparing {len(specs)} human clips', flush=True)
    clips = {}
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, (key, clip, error) in enumerate(pool.map(load_sample, specs.items()), 1):
            if error:
                errors.append(error)
            else:
                clips[key] = clip
            if index % 24 == 0 or index == len(specs):
                print(f'Processed {index}/{len(specs)} clips', flush=True)
    if errors:
        raise RuntimeError('Unable to prepare these source recordings:\n' + '\n'.join(errors))

    def append_clip(out, item, gap, label, frames):
        start = frames
        pcm = clips[item['source'], tuple(item.get('excerpt', ()))]
        padding = silence(gap)
        step = (len(pcm) + len(padding)) // 2
        for _ in range(REPETITIONS):
            out.writeframesraw(pcm)
            out.writeframesraw(padding)
        part = {'label': label, 'start': seconds(start),
                'spokenEnd': seconds(start + len(pcm) // 2), 'step': seconds(step)}
        return part, start + step * REPETITIONS

    wav_path = CACHE / 'ipa-48-practice.wav'
    cues = []
    frames = 0
    with wave.open(str(wav_path), 'wb') as out:
        out.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        for card in cards:
            start = frames
            part, frames = append_clip(out, card['sound'], SOUND_GAP, f'/{card["symbol"]}/', frames)
            parts = [part]
            for item in card['examples']:
                part, frames = append_clip(out, item, WORD_GAP, item['spelling'].replace('|', ''), frames)
                parts.append(part)
            practice_end = frames
            tail = silence(CARD_TAIL)
            out.writeframesraw(tail)
            frames += len(tail) // 2
            cues.append({'entryId': 'ipa-' + card['id'], 'start': seconds(start),
                         'spokenEnd': round(part['spokenEnd'] + (REPETITIONS - 1) * part['step'], 6),
                         'practiceEnd': seconds(practice_end), 'end': seconds(frames), 'parts': parts})

    destination = PACK / 'audio' / TRACK
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.mp3.part')
    subprocess.run(
        [ffmpeg, '-v', 'error', '-y', '-i', str(wav_path), '-codec:a', 'libmp3lame',
         '-b:a', '48k', '-metadata', 'title=48 English IPA cards - listen and repeat',
         '-metadata', 'artist=Wikimedia Commons contributors (see recordings.json)',
         '-metadata', 'comment=Edited audio: CC BY-SA 4.0. Source and license per recording in the cards.',
         '-f', 'mp3', str(temporary)],
        check=True,
    )
    payload = temporary.read_bytes()
    timeline = {'file': TRACK, 'duration': seconds(frames), 'bytes': len(payload),
                'sha256': hashlib.sha256(payload).hexdigest(), 'baseTempo': TEMPO,
                'repetitions': REPETITIONS, 'soundGap': SOUND_GAP, 'wordGap': WORD_GAP, 'cues': cues}
    temporary.replace(destination)
    (PACK / 'data/timeline.json').write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + '\n',
                                             encoding='utf-8', newline='\n')
    wav_path.unlink()
    print(f'Built {len(cues)} cards, {timeline["duration"]:.1f}s, {len(payload):,} bytes', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--proxy')
    args = parser.parse_args()
    build(args.ffmpeg, args.proxy)
