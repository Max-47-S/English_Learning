"""Validate study content, source order, links, timing, and the full encoded MP3."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import unquote,urlsplit
import hashlib,json,re,subprocess,sys

REPOSITORY=Path(__file__).resolve().parents[2]
ROOT=REPOSITORY/'01_词汇与短语'/'OxfordPhraseList_学习包'
OLD=ROOT.parent/'Oxford3000_学习包'
for folder in [ROOT/'_cache/python',OLD/'_cache/python']:
    if folder.exists():sys.path.insert(0,str(folder))
import imageio_ffmpeg
from mutagen.mp3 import MP3

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def check(value,message):
    if not value:raise AssertionError(message)

def main():
    rows=load(ROOT/'data/vocabulary.json');pdf=load(ROOT/'data/pdf_entries.json');meta=load(ROOT/'data/pdf_metadata.json');audio=load(ROOT/'data/audio_timeline.json')
    expected={'A1':200,'A2':175,'B1':175,'B2':125,'C1':75}
    check(len(rows)==len(pdf)==len(audio['entries'])==750,'entry count')
    check(Counter(x['level'] for x in rows)==expected,'level counts')
    check([x['id'] for x in rows]==list(range(1,751)),'ordered ids')
    source_hash=hashlib.sha256((REPOSITORY/'06_原始资料/Oxford词表/oxford-phrase-list.pdf').read_bytes()).hexdigest()
    check(source_hash==meta['source_sha256'],'source PDF checksum')
    chinese=lambda s:bool(re.search('[\u4e00-\u9fff]',s))
    for e,p,a in zip(rows,pdf,audio['entries']):
        check((e['id'],e['phrase'],e['level'],e['pdf_variants'])==(p['id'],p['phrase'],p['level'],p['pdf_variants']),f'source mismatch {e["id"]}')
        check(e['phrase']==a['phrase'] and e['audio']==a,f'audio mapping {e["id"]}')
        check(chinese(e['meaning_zh']),f'meaning {e["id"]}')
        check(len(e['collocations'])==2,f'two collocations {e["id"]}')
        for c in e['collocations']:check(c['english'].strip() and chinese(c['chinese']),f'collocation {e["id"]}')
        check(e['example']['english'].strip() and chinese(e['example']['chinese']),f'example {e["id"]}')
        check(e['example']['source']=='原创学习例句',f'example attribution {e["id"]}')
        check(a['source_id'] in audio['sources'],f'source missing {e["id"]}')
        check(a['start']<a['spoken_end']<a['end'],f'invalid audio interval {e["id"]}')
        check(abs(a['end']-a['spoken_end']-1.8)<.00002,f'pause {e["id"]}')
        if e['id']>1:check(abs(audio['entries'][e['id']-2]['end']-a['start'])<.00002,'non-contiguous audio')
        source=audio['sources'][a['source_id']]
        if a['kind']=='human_recording':
            check(source.get('artist') and source.get('license') and source.get('license_url') and source.get('page_url'),'human attribution')
        else:check(source['voice']=='en-GB-SoniaNeural' and a['audio_text']==source['text'],'AI labelling')
        check(not re.search(r'\b(?:sb|sth|X)\b|…|\.{3}',a['audio_text']),f'unfilled audio placeholder {e["id"]}')
    counts=Counter(e['audio']['kind'] for e in rows)
    check(counts['human_recording']==audio['human_entries'] and counts['ai_generated']==audio['ai_entries'],'audio counts')
    lrc=(ROOT/'audio/OxfordPhraseList_连续听读.lrc').read_text(encoding='utf-8')
    stamps=re.findall(r'^\[(\d+):(\d+)\.(\d+)\](\d+) ',lrc,re.M)
    check(len(stamps)==750,'LRC count')
    for stamp,a in zip(stamps,audio['entries']):
        m,s,c,i=map(int,stamp);check(i==a['id'] and abs(m*60+s+c/100-a['start'])<=.0051,'LRC timing')
    full=(ROOT/'OxfordPhraseList_原序学习版.md').read_text(encoding='utf-8')
    check(len(re.findall(r'^### \d{4}\. ',full,re.M))==750,'full Markdown count')
    for level,count in expected.items():
        text=(ROOT/f'OxfordPhraseList_{level}.md').read_text(encoding='utf-8')
        check(len(re.findall(r'^### \d{4}\. ',text,re.M))==count,'level Markdown count')
    broken=[];links=0
    for path in ROOT.glob('*.md'):
        for href in re.findall(r'\]\(([^\n)]+)\)',path.read_text(encoding='utf-8')):
            if re.match(r'^[a-z]+:',href,re.I):continue
            url=urlsplit(href);target=path.parent/unquote(url.path) if url.path else path
            links+=1
            if not target.exists():
                if target==ROOT/'data/validation_report.json':continue
                broken.append({'file':path.name,'target':href});continue
            if url.fragment and target.suffix=='.md':
                content=target.read_text(encoding='utf-8')
                if f'id="{unquote(url.fragment)}"' not in content:broken.append({'file':path.name,'anchor':href})
    check(not broken,f'broken local links: {broken[:3]}')
    mp3=ROOT/audio['file'];length=MP3(mp3).info.length
    check(abs(length-audio['duration_seconds'])<.15,'MP3 duration mismatch')
    decoded=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(mp3),'-f','null','-'],capture_output=True,text=True)
    check(decoded.returncode==0 and not decoded.stderr.strip(),'full MP3 decode: '+decoded.stderr[:300])
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'pass','entries':750,'level_counts':expected,
            'source_sha256':source_hash,'source_order':'pass','meanings_zh':750,'translated_collocations':1500,
            'original_bilingual_examples':750,'usage_notes':sum(bool(x['usage_note']) for x in rows),'human_entries':audio['human_entries'],
            'ai_entries':audio['ai_entries'],'lrc_entries':len(stamps),'timing':'pass','mp3_full_decode':'pass',
            'duration_seconds':audio['duration_seconds'],'encoded_duration_seconds':length,'mp3_bytes':mp3.stat().st_size,
            'local_links_checked':links,'broken_local_links':broken,'audio_sha256':hashlib.sha256(mp3.read_bytes()).hexdigest()}
    (ROOT/'data/validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
