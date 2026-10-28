"""Generate clearly labelled AI fallbacks for phrases lacking complete human audio."""
from pathlib import Path
import argparse,asyncio,hashlib,json,re,sys,time
from datetime import datetime,timezone

from human_audio import ROOT,OLD,CACHE,query,load,save
import edge_tts
from mutagen.mp3 import MP3

VOICE='en-GB-SoniaNeural'
RATE='-5%'

def enrichment():
    rows={}
    for path in sorted((ROOT/'data').glob('enrichment_*.json')):rows.update(load(path,{}))
    return rows

def spoken(entry,content):
    phrase=entry['phrase']
    if re.search(r'\b(?:sb|sth|X|A|B|yourself)\b|…|\.{3}',phrase):
        return content['collocations'][0]['english']
    return phrase.replace('’',"'")

def human_possible(entry,sources):
    rows=sources.get(query(entry['phrase']),[])
    for row in rows:
        if row.get('cache_file') and (ROOT/row['cache_file']).exists():return True
        if row.get('available_path') and Path(row['available_path']).exists():return True
    # Before a download batch ends, its metadata is already available, but cache paths
    # have not yet been published. Avoid synthesizing those phrases prematurely.
    if rows and not (CACHE/'human_download_errors.json').exists():return True
    return False

async def run(proxy,watch):
    entries=load(ROOT/'data/pdf_entries.json');manifest=load(CACHE/'tts_sources.json',{})
    folder=CACHE/'ai';folder.mkdir(parents=True,exist_ok=True)
    sem=asyncio.Semaphore(3);failures=[]
    async def one(entry,content):
        key=str(entry['id']);text=spoken(entry,content)
        name=hashlib.sha256((VOICE+'|'+RATE+'|'+text).encode()).hexdigest()[:24]+'.mp3'
        target=folder/name
        async with sem:
            if not target.exists():
                error='retry limit'
                for attempt in range(4):
                    partial=target.with_suffix('.mp3.part')
                    try:
                        await edge_tts.Communicate(text,voice=VOICE,rate=RATE,proxy=proxy).save(str(partial))
                        info=MP3(partial).info
                        if info.length<.15:raise ValueError('empty AI clip')
                        partial.replace(target);break
                    except Exception as exc:
                        error=type(exc).__name__+': '+str(exc)[:140]
                        await asyncio.sleep(min(20,3*(attempt+1)))
                if not target.exists():
                    failures.append({'id':entry['id'],'phrase':entry['phrase'],'error':error})
                    print('AI_FAILED',entry['id'],error,flush=True);return
            manifest[key]={'kind':'ai_generated','text':text,'voice':VOICE,'rate':RATE,'engine':'Microsoft Edge online TTS via edge-tts '+edge_tts.__version__,
                           'cache_file':target.relative_to(ROOT).as_posix(),'source_url':'https://github.com/rany2/edge-tts',
                           'created_at':datetime.now(timezone.utc).isoformat()}
            save(CACHE/'tts_sources.json',manifest)
    while True:
        content=enrichment();humans=load(CACHE/'human_sources.json',{})
        pending=[e for e in entries if str(e['id']) in content and not human_possible(e,humans)
                 and (str(e['id']) not in manifest or not (ROOT/manifest[str(e['id'])]['cache_file']).exists()
                      or manifest[str(e['id'])].get('text')!=spoken(e,content[str(e['id'])]))]
        for start in range(0,len(pending),18):
            await asyncio.gather(*(one(e,content[str(e['id'])]) for e in pending[start:start+18]))
            print('AI_READY',len(manifest),'content_entries',len(content),flush=True)
        save(CACHE/'tts_errors.json',failures)
        if not watch or len(content)==len(entries):break
        await asyncio.sleep(12)
    print('AI_FALLBACK_COMPLETE',len(manifest),'errors',len(failures),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proxy');p.add_argument('--watch',action='store_true');a=p.parse_args()
    asyncio.run(run(a.proxy,a.watch))
