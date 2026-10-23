"""Retrieve the openly licensed Shtooka collections from their public archive."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import tarfile
import time
import urllib.request
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '_cache'
BASE = 'https://www.yojik.eu/audiocollections/'


def download(pack):
    folder = CACHE / 'collections'
    folder.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for name, url in [
        (pack + '_README.txt', BASE + f'detailled/{pack}/readme.txt'),
        (pack + '.tar.xz', BASE + f'archives/{pack}_flac.tar.xz'),
    ]:
        target = folder / name
        if target.exists():
            print('CACHED', name, target.stat().st_size, flush=True)
            continue
        partial = target.with_suffix(target.suffix + '.part')
        with opener.open(urllib.request.Request(url, headers={'User-Agent': 'EnglishLearningPersonal/1.0'}), timeout=90) as response:
            total = int(response.headers.get('Content-Length', '0'))
            done = 0
            last = time.monotonic()
            print('START', pack, total, url, flush=True)
            with partial.open('wb') as stream:
                while block := response.read(256 * 1024):
                    stream.write(block)
                    done += len(block)
                    if time.monotonic() - last >= 15:
                        print('COLLECTION_DOWNLOAD', pack, done, '/', total, flush=True)
                        last = time.monotonic()
            if total and done != total:
                raise IOError(f'Incomplete archive: {done}/{total}')
            partial.replace(target)
        print('SAVED', name, done, flush=True)
    destination = folder / pack
    destination.mkdir(exist_ok=True)
    with tarfile.open(folder / (pack + '.tar.xz'), 'r:xz') as archive:
        members = archive.getmembers()
        for member in members:
            resolved = (destination / member.name).resolve()
            if not resolved.is_relative_to(destination.resolve()) or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe archive member: ' + member.name)
        archive.extractall(destination, members=members, filter='data')
    print('EXTRACTED', pack, len(members), flush=True)


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(download, sys.argv[1:] or ['eng-wcp-us', 'eng-wims-mary']))
