"""Download the remaining selected public files, honoring server retry delays."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import argparse
import json
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'_cache'
lock=Lock()
next_request=0.0


def one(row,proxy):
    global next_request
    target=ROOT/row['cache_file']
    if target.exists() and target.stat().st_size>100:return None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':proxy,'http':proxy}))
    error='Retry limit reached'
    for attempt in range(6):
        with lock:
            delay=max(0,next_request-time.monotonic())
            if delay:time.sleep(delay)
            next_request=time.monotonic()+0.8
        try:
            request=urllib.request.Request(row['url'],headers={'User-Agent':'EnglishLearningPersonal/1.0 (+https://github.com/Max-47-S/English_Learning)'})
            with opener.open(request,timeout=30) as response:
                data=response.read()
            if len(data)<100:raise IOError('Empty sound')
            target.write_bytes(data)
            return None
        except urllib.error.HTTPError as exc:
            error=f'HTTP {exc.code}'
            if exc.code not in {429,500,502,503,504}:break
            delay=max(float(exc.headers.get('Retry-After','0')), min(45,2**(attempt+2)))
            with lock:next_request=max(next_request,time.monotonic()+delay)
            print('SERVER_RETRY',row['spoken_word'],error,delay,flush=True)
        except Exception as exc:
            error=repr(exc)
            time.sleep(min(10,attempt+2))
    result={'word':row['spoken_word'],'url':row['url'],'error':error}
    print('FAILED',result,flush=True)
    return result


def main(proxy):
    rows=json.loads((CACHE/'required_audio_downloads.json').read_text(encoding='utf-8'))
    failures=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(one,row,proxy) for row in rows]
        for done,future in enumerate(as_completed(futures),1):
            failure=future.result()
            if failure:failures.append(failure)
            if done%20==0 or done==len(rows):
                print('REQUIRED_AUDIO',done,'/',len(rows),'failures',len(failures),flush=True)
                (CACHE/'required_download_failures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proxy',required=True)
    main(p.parse_args().proxy)
