"""Download the official phrase-list PDF and inspect its column layout."""
from pathlib import Path
import argparse
import hashlib
import json
import urllib.request
from collections import Counter,defaultdict
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = 'https://www.oxfordlearnersdictionaries.com/external/pdf/wordlists/oxford-phrase-list/Oxford%20Phrase%20List.pdf'


def download(proxy=None):
    target=ROOT/'source/oxford-phrase-list.pdf'
    target.parent.mkdir(parents=True,exist_ok=True)
    proxies={'https':proxy,'http':proxy} if proxy else {}
    opener=urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    with opener.open(urllib.request.Request(SOURCE_URL,headers={'User-Agent':'Mozilla/5.0'}),timeout=45) as response:
        data=response.read()
    if not data.startswith(b'%PDF'):raise ValueError('Response is not a PDF')
    target.write_bytes(data)
    print('PDF_SAVED',len(data),hashlib.sha256(data).hexdigest(),flush=True)


def inspect():
    import pdfplumber
    with pdfplumber.open(ROOT/'source/oxford-phrase-list.pdf') as pdf:
        print('PAGES',len(pdf.pages),flush=True)
        for no,page in enumerate(pdf.pages,1):
            print('PAGE',no,page.width,page.height,flush=True)
            print(page.extract_text(x_tolerance=1.5,y_tolerance=3),flush=True)
            if no==1:
                folder=ROOT/'_cache';folder.mkdir(exist_ok=True)
                page.to_image(resolution=140).save(folder/'source-page-01.png')
                (folder/'page01_words.json').write_text(json.dumps(page.extract_words(),ensure_ascii=False,indent=2),encoding='utf-8')


def extract():
    import pdfplumber
    entries=[];level=None;level_counts=Counter();line_dump=[]
    with pdfplumber.open(ROOT/'source/oxford-phrase-list.pdf') as pdf:
        for page_no,page in enumerate(pdf.pages,1):
            for col,(left,right,base) in enumerate([(40,170,42.5197),(170,300,172.91),(300,431,303.31),(431,559,433.70)],1):
                words=page.crop((left,140 if page_no==1 else 25,right,800)).extract_words(x_tolerance=1.1,y_tolerance=2,extra_attrs=['fontname','size'])
                groups=[]
                for word in sorted(words,key=lambda w:(round(w['top']/2)*2,w['x0'])):
                    if not groups or abs(groups[-1][0]['top']-word['top'])>2:groups.append([])
                    groups[-1].append(word)
                for group in groups:
                    group.sort(key=lambda w:w['x0'])
                    text=' '.join(w['text'] for w in group)
                    if re.fullmatch('[ABC][12]',text):
                        level=text;continue
                    regular=sum(len(w['text']) for w in group if 'MyriadPro-Regular' in w['fontname'])
                    total=sum(len(w['text']) for w in group)
                    is_head=regular>total*.5
                    x0=group[0]['x0']
                    line_dump.append({'page':page_no,'column':col,'text':text,'head_font':is_head,'x0':round(x0,2),'top':round(group[0]['top'],2)})
                    if is_head:
                        if x0>base+3 and entries:
                            entries[-1]['phrase']+=' '+text
                            entries[-1]['pdf_text']+=' '+text
                        else:
                            if not level:raise ValueError('Missing CEFR heading before '+text)
                            level_counts[level]+=1
                            entries.append({'id':len(entries)+1,'level':level,'level_index':level_counts[level],'phrase':text,'pdf_page':page_no,'pdf_column':col,'pdf_text':text,'pdf_variants':[]})
                    elif entries:
                        if x0>base+9 and entries[-1]['pdf_variants']:
                            entries[-1]['pdf_variants'][-1]+=' '+text
                        else:
                            entries[-1]['pdf_variants'].append(text)
    folder=ROOT/'data';folder.mkdir(exist_ok=True)
    (folder/'pdf_entries.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'_cache/pdf_lines.json').write_text(json.dumps(line_dump,ensure_ascii=False,indent=2),encoding='utf-8')
    metadata={'source_url':SOURCE_URL,'source_sha256':hashlib.sha256((ROOT/'source/oxford-phrase-list.pdf').read_bytes()).hexdigest(),'pages':4,'entries':len(entries),'levels':dict(level_counts),'reading_order':'page; left-to-right columns; top-to-bottom within each column; regular-font main entries; indented light-font text retained as source variants'}
    (folder/'pdf_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('EXTRACTED',json.dumps(metadata,ensure_ascii=False),flush=True)
    for e in entries:print(str(e['id'])+'|'+e['level']+'|'+e['phrase'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['download','inspect','extract']);p.add_argument('--proxy')
    args=p.parse_args()
    if args.action=='download':download(args.proxy)
    elif args.action=='inspect':inspect()
    else:extract()
