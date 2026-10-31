"""Find complete, reusable human phrase recordings, with per-file attribution."""
from collections import defaultdict
from pathlib import Path
import argparse,asyncio,configparser,hashlib,html,json,re,shutil,sys,time,urllib.parse

REPOSITORY=Path(__file__).resolve().parents[2]
ROOT=REPOSITORY/'01_词汇与短语'/'OxfordPhraseList_学习包'
OLD=ROOT.parent/'Oxford3000_学习包'
CACHE=ROOT/'_cache'
for dependency_path in [OLD/'_cache/python',CACHE/'python']:
    if dependency_path.exists():sys.path.insert(0,str(dependency_path))
import aiohttp

UA='EnglishLearningPersonal/1.0 (+https://github.com/Max-47-S/English_Learning)'

def load(path,default=None):return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    partial=path.with_name(path.name+'.part')
    for attempt in range(8):
        try:
            partial.write_text(payload,encoding='utf-8')
            partial.replace(path)
            return
        except OSError:
            if attempt==7:raise
            time.sleep(.15*(attempt+1))
def norm(value):
    value=value.replace('’',"'").replace('_',' ').replace('…','').lower()
    value=re.sub(r'[.!?,]+$','',value.strip())
    return re.sub(r'\s+',' ',value)
def query(phrase):
    value=re.sub(r'\([^)]*\)','',phrase)
    value=re.sub(r'\b(?:sb|sth|yourself)(?:/(?:sb|sth|yourself))*\b','',value)
    value=re.sub(r'\bX\b','',value)
    return norm(value)
def cased_query(phrase):
    value=re.sub(r'\([^)]*\)','',phrase)
    value=re.sub(r'\b(?:sb|sth|yourself)(?:/(?:sb|sth|yourself))*\b','',value)
    value=re.sub(r'\bX\b','',value).replace('’',"'").replace('…','')
    return re.sub(r'\s+',' ',value).strip(' .!?,')
def license_link(label,current,page):
    if current and not ('zero/1.0' in current and label!='CC0'):return current
    if 'public domain' in label.lower():return 'https://creativecommons.org/publicdomain/mark/1.0/'
    if label=='CC0':return 'https://creativecommons.org/publicdomain/zero/1.0/'
    match=re.search(r'(\d+\.\d+)',label)
    if match:
        category='by-sa' if 'by-sa' in label.lower() else 'by'
        locale='us/' if re.search(r'\bus\b',label,re.I) else 'fr/' if re.search(r'\bfr\b',label,re.I) else ''
        return f'https://creativecommons.org/licenses/{category}/{match[1]}/{locale}'
    return page
def plain(value):return html.unescape(re.sub('<[^>]+>','',value or '')).strip()


class Finder:
    def __init__(self,proxy):
        self.proxy=proxy;self.rows=defaultdict(list)
        self.words={query(r['phrase']) for r in load(ROOT/'data/pdf_entries.json')}
        self.words={q for q in self.words if len(q.split())>=2}
        self.cased={query(r['phrase']):cased_query(r['phrase']) for r in load(ROOT/'data/pdf_entries.json')}
        self.sem=asyncio.Semaphore(3)
    async def api(self,session,host,params):
        url=host+'?'+urllib.parse.urlencode(params)
        cache=CACHE/'metadata'/(hashlib.sha256(url.encode()).hexdigest()+'.json')
        if cache.exists():return load(cache)
        async with self.sem:
            for attempt in range(5):
                try:
                    async with session.get(url,proxy=self.proxy,timeout=aiohttp.ClientTimeout(total=45)) as response:
                        if response.status in {429,500,502,503,504}:
                            await asyncio.sleep(max(float(response.headers.get('Retry-After','0')),2**(attempt+1)));continue
                        response.raise_for_status();data=await response.json(content_type=None)
                        if 'error' in data:raise RuntimeError(data['error'])
                        save(cache,data);return data
                except Exception as exc:
                    if attempt==4:print('METADATA_ERROR',str(exc)[:180],flush=True)
                    else:await asyncio.sleep(attempt+2)
        return {}
    def local(self):
        index=load(OLD/'_cache/collection_index.json',{})
        for word in self.words:
            for old_row in index.get(word,[]):
                if old_row.get('excluded_license'):continue
                row=dict(old_row);path=OLD/row['cache_file']
                row.update(available_path=str(path),recorded_text=row.get('text',word))
                self.rows[word].append(row)
        for pack in ['eng-wims-mary-conversation','eng-balm-judith-proverbs']:
            folder=CACHE/'collections'/pack/'flac'
            path=folder/'index.tags.txt'
            if not path.exists():continue
            text=path.read_text(encoding='utf-8-sig');cfg=configparser.ConfigParser(interpolation=None,strict=False)
            cfg.read_string(text[text.index('[GLOBAL]'):])
            for filename in cfg.sections():
                if not filename.endswith('.flac'):continue
                get=lambda key:cfg.get(filename,key,fallback=cfg.get('GLOBAL',key,fallback='')).strip()
                text=get('SWAC_TEXT');word=norm(text)
                if word not in self.words:continue
                row={'kind':'human_recording','collection':pack,'artist':get('SWAC_SPEAK_NAME'),
                     'credit':get('SWAC_COLL_AUTHORS'),'license':'CC BY 3.0 US','license_url':'https://creativecommons.org/licenses/by/3.0/us/',
                     'page_url':'https://www.yojik.eu/audiocollections/audiocollections.html',
                     'archive_url':f'https://www.yojik.eu/audiocollections/archives/{pack}_flac.tar.xz',
                     'available_path':str(folder/filename),'recorded_text':text}
                self.rows[word].append(row)
    async def titles(self,session,mapping):
        keys=list(mapping);batches=[keys[i:i+45] for i in range(0,len(keys),45)]
        async def one(group):
            data=await self.api(session,'https://commons.wikimedia.org/w/api.php',{'action':'query','format':'json','titles':'|'.join(group),'prop':'imageinfo','iiprop':'url|extmetadata','redirects':'1'})
            aliases={norm(x['from']):norm(x['to']) for x in data.get('query',{}).get('normalized',[])+data.get('query',{}).get('redirects',[])}
            resolved=defaultdict(set)
            for title in group:
                target=norm(title);seen=set()
                while target in aliases and target not in seen:seen.add(target);target=aliases[target]
                resolved[target].update(mapping[title])
            for page in data.get('query',{}).get('pages',{}).values():
                if not page.get('imageinfo'):continue
                info=page['imageinfo'][0];meta=info.get('extmetadata',{});get=lambda k:plain(meta.get(k,{}).get('value',''))
                license=get('LicenseShortName');description=get('ImageDescription')
                if not any(s in license.lower() for s in ['cc by','cc0','public domain']):continue
                if re.search(r'text.to.speech|speech synthesis|espeak|synthetic|AI.generated',description,re.I):continue
                row={'kind':'human_recording','title':page['title'],'url':info['url'].split('?')[0],
                     'page_url':info.get('descriptionurl'),'artist':get('Artist'),'credit':get('Credit'),'license':license,
                     'license_url':license_link(license,get('LicenseUrl'),info.get('descriptionurl')),
                     'description':description}
                for word in resolved.get(norm(page['title']),[]):
                    copy=dict(row);copy['recorded_text']=word
                    if row['url'] not in {r.get('url') for r in self.rows[word]}:self.rows[word].append(copy)
        for start in range(0,len(batches),3):
            await asyncio.gather(*(one(g) for g in batches[start:start+3]))
            print('COMMONS_BATCHES',min(start+3,len(batches)),'/',len(batches),'covered',len(self.rows),flush=True)
            save(CACHE/'human_sources.json',dict(self.rows))
    async def discover(self,session,words):
        mapping=defaultdict(set)
        for start in range(0,len(words),25):
            group=words[start:start+25]
            data=await self.api(session,'https://en.wiktionary.org/w/api.php',{'action':'query','format':'json','titles':'|'.join(group),'prop':'images','imlimit':'max','redirects':'1'})
            for page in data.get('query',{}).get('pages',{}).values():
                word=norm(page['title'])
                if word not in self.words:continue
                for image in page.get('images',[]):
                    title=image['title'];stem=re.sub(r'\.(?:ogg|oga|wav|mp3)$','',title[5:],flags=re.I)
                    if stem==title[5:]:continue
                    name=norm(stem)
                    match=False
                    if re.match(r'en[-_ ]',name,re.I):
                        core=re.sub(r'^en[-_ ](?:us|uk|gb|ca|au)?[-_ ]?','',name,flags=re.I)
                        core=re.sub(r'\s*\((?:noun|verb|phrase)\)$','',core)
                        match=core.replace('-',' ')==word
                    elif name.startswith('ll-q1860 (eng)'):
                        match=any(name.endswith('-'+ending) for ending in [word,word+' (phrase)',word.replace(' ','-')])
                    if match:mapping[title].add(word)
            if start%100==0:print('WIKTIONARY',start,'/',len(words),'files',len(mapping),flush=True)
        await self.titles(session,mapping)
    async def downloads(self,session):
        folder=CACHE/'human';folder.mkdir(exist_ok=True)
        distinct={}
        for rows in self.rows.values():
            for row in rows:
                if row.get('available_path'):
                    source=Path(row['available_path']);key=hashlib.sha256(str(source).encode()).hexdigest()[:20];dest=folder/(key+source.suffix)
                    if not dest.exists():shutil.copyfile(source,dest)
                    row['cache_file']=dest.relative_to(ROOT).as_posix();continue
                suffix=Path(urllib.parse.urlparse(row['url']).path).suffix
                dest=folder/(hashlib.sha256(row['url'].encode()).hexdigest()[:20]+suffix)
                row['cache_file']=dest.relative_to(ROOT).as_posix();distinct[row['url']]=row
        errors=[]
        for done,row in enumerate(distinct.values(),1):
            path=ROOT/row['cache_file']
            if not path.exists():
                error='retry limit';ok=False
                for attempt in range(5):
                    try:
                        async with session.get(row['url'],proxy=self.proxy,timeout=aiohttp.ClientTimeout(total=45)) as response:
                            if response.status in {429,500,502,503,504}:
                                await asyncio.sleep(max(float(response.headers.get('Retry-After','0')),2**(attempt+2)));continue
                            response.raise_for_status();data=await response.read()
                            if len(data)<100:raise ValueError('empty sound')
                            path.write_bytes(data);ok=True;break
                    except Exception as exc:error=repr(exc);await asyncio.sleep(attempt+2)
                if not ok:errors.append({'url':row['url'],'error':error})
                await asyncio.sleep(.65)
            if done%20==0 or done==len(distinct):print('HUMAN_DOWNLOAD',done,'/',len(distinct),'errors',len(errors),flush=True)
        save(CACHE/'human_download_errors.json',errors)
        save(CACHE/'human_sources.json',dict(self.rows))
    async def run(self):
        self.rows.update(load(CACHE/'human_sources.json',{}));self.local()
        for rows in self.rows.values():
            for row in rows:row['license_url']=license_link(row['license'],row.get('license_url'),row.get('page_url'))
        connector=aiohttp.TCPConnector(limit=5)
        async with aiohttp.ClientSession(headers={'User-Agent':UA},connector=connector) as session:
            mapping=defaultdict(set)
            for word in sorted(self.words):
                for prefix in ['En-us-','En-uk-','En-']:
                    for variant in {word,self.cased.get(word,word),word.replace(' ','-')}:
                        mapping['File:'+prefix+variant+'.ogg'].add(word)
            await self.titles(session,mapping)
            missing=sorted(self.words-self.rows.keys())
            titles=sorted({title for word in missing for title in [word,self.cased.get(word,word)]})
            await self.discover(session,titles)
            await self.downloads(session)
        print('HUMAN_SEARCH_COMPLETE',len(self.rows),'/',len(self.words),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--proxy');args=p.parse_args()
    asyncio.run(Finder(args.proxy).run())
