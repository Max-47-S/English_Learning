"""Check completeness, original order, links, source credits and the final MP3."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'_cache/python'))
import imageio_ffmpeg
from mutagen.mp3 import MP3


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    original=load(ROOT/'data/pdf_entries.json')
    entries=load(ROOT/'data/vocabulary.json')
    audio=load(ROOT/'data/audio_timeline.json')
    assert len(entries)==len(original)==len(audio['entries'])==3306
    assert [r['id'] for r in entries]==list(range(1,3307))
    assert Counter(r['level'] for r in entries)=={'A1':899,'A2':871,'B1':809,'B2':727}
    for source,entry,track in zip(original,entries,audio['entries']):
        for key,value in source.items():assert entry[key]==value,(entry['id'],key)
        assert entry['word']==track['word'] and entry['id']==track['id']
        assert re.search(r'[\u3400-\u9fff]',entry['meaning_zh']),entry['id']
        assert entry['phrases'] and all(p.strip() for p in entry['phrases']),entry['id']
        assert entry['example']['english'].strip() and re.search(r'[\u3400-\u9fff]',entry['example']['chinese']),entry['id']
        assert track['start']<track['spoken_end']<track['end']
        if track['id']>1:assert abs(track['start']-audio['entries'][track['id']-2]['end'])<0.00002
        for sid in track['source_ids']:assert sid in audio['sources']
    for sid,source in audio['sources'].items():
        assert (ROOT/source['cache_file']).is_file(),sid
        assert source['license'] and source['license_url'],sid
        assert source.get('artist') or source.get('credit') or source.get('copyright'),sid
        assert source['kind']=='human_recording',sid
    assert audio['human_entries']==3306 and audio['ai_entries']==0
    text=(ROOT/'Oxford3000_原序学习完整版.md').read_text(encoding='utf-8')
    assert len(re.findall(r'^### [0-9]{4} ·',text,re.M))==3306
    for level,count in {'A1':899,'A2':871,'B1':809,'B2':727}.items():
        markdown=(ROOT/'分级词表'/f'{level}.md').read_text(encoding='utf-8')
        assert len(re.findall(r'^### [0-9]{4} ·',markdown,re.M))==count
    broken=[]
    for path in [ROOT/'README.md',ROOT/'Oxford3000_原序学习完整版.md',*list((ROOT/'分级词表').glob('*.md'))]:
        for link in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            link=urllib.parse.unquote(link.split('#')[0])
            if not link or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',link):continue
            if not (path.parent/link).exists():broken.append((path.name,link))
    assert not broken,broken[:5]
    pdf_hash=hashlib.sha256((ROOT.parent/'oxford-3000-by-cefr-level.pdf').read_bytes()).hexdigest()
    assert pdf_hash=='4bf5eee62b858cc970da5d209558435276c05ec3a705662d255329966b06046d'
    mp3=ROOT/audio['file']
    info=MP3(mp3).info
    assert abs(info.length-audio['duration_seconds'])<0.15
    lrc=(mp3.with_suffix('.lrc')).read_text(encoding='utf-8')
    assert len(re.findall(r'^\[[0-9]+:[0-9]{2}\.[0-9]{2}\]',lrc,re.M))==3306
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(mp3),'-f','null','-'],check=True,capture_output=True)
    report=load(ROOT/'data/validation_report.json')
    report.update(source_order='pass',markdown_entry_count='pass',complete_bilingual_examples='pass',complete_phrases='pass',audio_source_credits='pass',audio_timestamps='pass',lrc_entries=3306,mp3_full_decode='pass',broken_local_links=0,mp3_bytes=mp3.stat().st_size,mp3_sha256=hashlib.sha256(mp3.read_bytes()).hexdigest())
    (ROOT/'data/validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('VALIDATION_PASS',json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
