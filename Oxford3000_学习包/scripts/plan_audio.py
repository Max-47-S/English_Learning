"""Assign a human pronunciation to each PDF row; preserve order and homographs."""
from collections import Counter
from pathlib import Path
import asyncio
import argparse
import hashlib
import json
import re
import urllib.parse

from fetch_human_audio import Fetcher, ROOT, CACHE, UA, save, ALIASES
import aiohttp


def cached_path(row):
    if row.get('cache_file'):
        return row['cache_file']
    suffix = Path(urllib.parse.urlparse(row['url']).path).suffix
    return (Path('_cache/human_audio') / (hashlib.sha256(row['url'].encode()).hexdigest()[:20]+suffix)).as_posix()


def main_plan():
    entries = json.loads((ROOT/'data/pdf_entries.json').read_text(encoding='utf-8'))
    commons = json.loads((ROOT/'data/human_audio_sources_v2.json').read_text(encoding='utf-8'))
    credit_overrides = json.loads((ROOT/'data/source_credit_overrides.json').read_text(encoding='utf-8'))
    for rows in commons.values():
        for row in rows:
            if row['title'] in credit_overrides:row.update(credit_overrides[row['title']])
            if row['license']=='Public domain' and not row.get('license_url'):
                row['license_url']='https://creativecommons.org/publicdomain/mark/1.0/'
    components = json.loads((ROOT/'data/human_audio_components.json').read_text(encoding='utf-8'))
    collections = json.loads((CACHE/'collection_index.json').read_text(encoding='utf-8'))
    for rows in commons.values():
        for row in rows:
            row['cache_file'] = cached_path(row)
    downloaded = {p.name for p in (CACHE/'human_audio').iterdir() if p.is_file()}
    def available(row):
        return row.get('collection') or Path(row['cache_file']).name in downloaded
    def choose(key, wanted='', prefer=''):
        rows = [dict(r) for r in collections.get(key,[]) if not r.get('excluded_license')]
        rows += [dict(r) for r in commons.get(key,[])]
        rows += [dict(r) for r in components.get(key,[])]
        alias = ALIASES.get(key)
        if alias and alias != key:
            rows += [dict(r) for r in collections.get(alias,[]) if not r.get('excluded_license')]
        if not rows:
            raise LookupError(key)
        def score(row):
            label = (row.get('title','')+' '+Path(row.get('cache_file','')).stem).lower().replace('_',' ')
            value = 40 if row.get('collection')=='eng-wims-mary' else 25 if row.get('collection') else 0
            if available(row):value += 10
            labels={'n':r'\bnoun\b|\(noun\)', 'v':r'\bverb\d*\b|\(verb\)', 'a':r'\badj(?:ective)?\b'}
            for role,pattern in labels.items():
                if re.search(pattern,label):value += 500 if role==wanted else -1000
            if prefer:value += 1500 if re.search(prefer,label) else -1500
            return value
        selected = max(rows,key=score)
        selected['cache_file']=cached_path(selected)
        if selected['license']=='Public domain' and not selected.get('license_url'):
            selected['license_url']='https://creativecommons.org/publicdomain/mark/1.0/'
        if selected['license']=='CC0' and not selected.get('license_url'):
            selected['license_url']='https://creativecommons.org/publicdomain/zero/1.0/'
        selected['spoken_word']=key
        return selected

    varying = {'record','conduct','conflict','contrast','decrease','estimate','excuse','export','graduate','import','increase','permit','protest','suspect','transfer'}
    noun_verb = {'object','house','present','produce','progress','project','survey','transport','separate'}
    plans=[]
    requests={}
    for entry in entries:
        key=entry['lookup'];pos=entry['pos'];h=entry['homograph'];notes=[]
        roles=[]
        if re.search(r'\bn\.',pos):roles.append('n')
        if re.search(r'\bv\.',pos):roles.append('v')
        if 'adj.' in pos:roles.append('a')
        parts=[]
        if key=='a, an':
            parts=[choose('a'),choose('an')]
        elif entry['word']=='IT':
            parts=[choose('letter_i'),choose('letter_t')]
            notes.append('逐字母读 I T；与代词 it 区分。')
        elif key in {'cd','dvd'}:
            parts=[choose('letter_'+x) for x in key]
            notes.append('由真人字母录音拼接。')
        elif key=='per cent':
            parts=[choose('percent')]
        elif key=='ought to':
            parts=[choose('ought'),choose('to')]
            notes.append('由真人单词录音拼接。')
        elif key=='used' and h=='1':
            parts=[choose('used to')]
            notes.append('为体现习惯于的 /juːst/ 读音，录音读 used to；PDF 词头为 used¹。')
        elif key=='close':
            parts=[choose(key,'v' if h=='1' else 'a')]
        elif key=='live':
            parts=[choose(key,'v' if h=='1' else 'a')]
        elif key=='lead':
            parts=[choose(key,prefer=r'lead-guide|lead-present')]
        elif key=='tear':
            parts=[choose(key,'v' if h=='1' else 'n')]
        elif key=='wind':
            parts=[choose(key,prefer='wind-air' if h=='1' else 'wind-turn')]
        elif key=='content':
            parts=[choose(key,'n',prefer=r'content \(noun\)')]
        elif key=='subject':
            parts=[choose(key,'v' if 'adj.' in pos else 'n')]
        elif key=='use':
            parts=[choose(key,'n' if roles==['n'] else 'v',prefer=r'use-noun' if roles==['n'] else r'en-us-use\.')]
        elif key=='row':
            parts=[choose(key,prefer=r'en-us-row\.')]
        elif key=='wound':
            parts=[choose(key,prefer='wound-injury')]
        elif key=='minute':
            parts=[choose(key,'n')]
        elif key in varying | noun_verb:
            for role in roles:
                if key=='present' and role=='n':role='a'
                row=choose(key,role)
                if row['cache_file'] not in {p['cache_file'] for p in parts}:parts.append(row)
            if len(parts)>1:notes.append('本条同时列出多种词性，依次读对应读音。')
        elif key in {'appropriate','perfect','deliberate'}:
            parts=[choose(key,'a')]
        elif key=='refuse':
            parts=[choose(key,'v',prefer=r'en-us-refuse\.')]
        elif key=='read':
            parts=[choose(key,prefer=r'en-us-read\.|read-present')]
        else:
            parts=[choose(key)]
        for part in parts:
            if not part.get('collection') and Path(part['cache_file']).name not in downloaded:
                requests[part['url']]=part
        plans.append({'id':entry['id'],'word':entry['word'],'level':entry['level'],'parts':parts,'notes':notes})
    save(ROOT/'data/audio_plan.json',plans)
    save(CACHE/'required_audio_downloads.json',list(requests.values()))
    print('AUDIO_PLAN',len(plans),'UNIQUE_DOWNLOADS_NEEDED',len(requests), 'PART_SOURCES',dict(Counter(p.get('collection','Commons') for r in plans for p in r['parts'])),flush=True)
    print('DOWNLOAD_WORDS', [r['spoken_word'] for r in requests.values()],flush=True)
    return requests


async def download(proxy):
    requests=main_plan()
    fetcher=Fetcher(proxy)
    fetcher.sources['required']=list(requests.values())
    async with aiohttp.ClientSession(headers={'User-Agent':UA},connector=aiohttp.TCPConnector(limit=3)) as session:
        await fetcher.downloads(session)
    print('REQUIRED_DOWNLOADS_FINISHED',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--download',action='store_true');p.add_argument('--proxy')
    args=p.parse_args()
    if args.download:asyncio.run(download(args.proxy))
    else:main_plan()
