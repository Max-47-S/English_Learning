"""Download observed official IELTS resources and verify media/file integrity."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json
import sys
import time

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS / '_cache/python'))
from mutagen.mp3 import MP3
from pypdf import PdfReader

ROOT = TOOLS.parents[1] / '05_听力与歌曲/雅思王听力语料库'
MANIFEST = ROOT / 'data/official_downloads.json'
REPORT = ROOT / 'data/download_validation.json'


def inspect_file(path):
    if path.suffix == '.mp3':
        audio = MP3(path)
        if audio.info.length <= 0:
            raise ValueError('Invalid MP3 duration')
        extra = {'duration_seconds': round(audio.info.length, 3),
                 'bitrate': audio.info.bitrate, 'sample_rate': audio.info.sample_rate}
    else:
        with path.open('rb') as stream:
            if not stream.read(1024).lstrip().startswith(b'%PDF'):
                raise ValueError('Response is not a PDF')
        pdf = PdfReader(path)
        if not len(pdf.pages):
            raise ValueError('Empty PDF')
        extra = {'pages': len(pdf.pages)}
    return {'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **extra}


def download(row):
    path = ROOT / row['file']
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return {**row, **inspect_file(path), 'status': 'pass', 'reused': True}
    error = None
    for attempt in range(3):
        part = path.with_suffix(path.suffix + '.part')
        try:
            request = Request(row['url'], headers={
                'User-Agent': 'Mozilla/5.0', 'Referer': row['page_url']})
            with urlopen(request, timeout=30) as response:
                kind = response.headers.get('Content-Type', '')
                if response.status != 200 or 'text/html' in kind.lower():
                    raise ValueError(f'Unexpected response: {response.status} {kind}')
                expected = response.headers.get('Content-Length')
                with part.open('wb') as stream:
                    while block := response.read(256 * 1024):
                        stream.write(block)
                if expected and part.stat().st_size != int(expected):
                    raise ValueError('Incomplete HTTP response')
            # Inspect under the correct suffix before moving the new file in place.
            if path.suffix == '.mp3':
                info = MP3(part).info
                if info.length <= 0:
                    raise ValueError('Invalid MP3')
            elif not part.read_bytes().lstrip().startswith(b'%PDF'):
                raise ValueError('Invalid PDF')
            part.replace(path)
            return {**row, **inspect_file(path), 'status': 'pass', 'reused': False}
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            if attempt < 2:
                time.sleep(attempt + 1)
    return {**row, 'status': 'fail', 'error': error}


def main():
    rows = json.loads(MANIFEST.read_text(encoding='utf-8'))['entries']
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(download, row) for row in rows]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"{len(results)}/{len(rows)} {result['status']} {result['file']}", flush=True)
            report = {'checked_at': datetime.now(timezone.utc).isoformat(),
                      'expected_files': len(rows), 'completed_files': len(results),
                      'entries': sorted(results, key=lambda x: x['file'])}
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    failures = [r for r in results if r['status'] != 'pass']
    if failures:
        raise SystemExit(json.dumps(failures, ensure_ascii=False))
    print('DOWNLOAD_COMPLETE', len(results), 'verified files', flush=True)


if __name__ == '__main__':
    main()
