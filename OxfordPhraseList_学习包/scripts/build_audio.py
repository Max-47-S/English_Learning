"""Select complete phrase clips, normalize volume and assemble the PDF-order track."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import Counter
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys,wave
from human_audio import ROOT,OLD,CACHE,load,save,query,norm,license_link
import av
import imageio_ffmpeg
import numpy as np
from mutagen.mp3 import MP3

RATE=24000
PAUSE=1.8
PCM=CACHE/'phrase_pcm'
PCM.mkdir(parents=True,exist_ok=True)

def pcm_path(path):
    return PCM/(hashlib.sha256(path.encode()).hexdigest()[:24]+'.s16')

def decode(path):
    target=pcm_path(path)
    if target.exists() and target.stat().st_size>100:return path,target.stat().st_size//2
    chunks=[]
    resampler=av.AudioResampler(format='s16',layout='mono',rate=RATE)
    with av.open(str(ROOT/path)) as container:
        for frame in container.decode(audio=0):
            chunks.extend(x.to_ndarray().reshape(-1) for x in resampler.resample(frame))
        chunks.extend(x.to_ndarray().reshape(-1) for x in resampler.resample(None))
    if not chunks:raise ValueError('No audio frames: '+path)
    samples=np.concatenate(chunks).astype(np.float32)
    if not .15*RATE<=len(samples)<=20*RATE:raise ValueError('Unexpected phrase clip length: '+path)
    peak=float(np.max(np.abs(samples)))
    if peak<20:raise ValueError('Silent clip: '+path)
    active=np.flatnonzero(np.abs(samples)>max(25,peak*.002))
    start=max(0,int(active[0])-int(RATE*.1));stop=min(len(samples),int(active[-1])+int(RATE*.1)+1)
    samples=samples[start:stop]*min(6.,27852./peak)
    data=np.clip(samples,-32767,32767).astype('<i2').tobytes()
    target.write_bytes(data)
    return path,len(data)//2

def timecode(value,lrc=False):
    if lrc:
        n=round(value*100);return f'{n//6000:02d}:{n//100%60:02d}.{n%100:02d}'
    n=int(value);return f'{n//3600:02d}:{n//60%60:02d}:{n%60:02d}'

def rank(row):
    artist=row.get('artist','').lower();title=row.get('title','').lower()
    # Prefer a clear English recording when several exact phrase recordings exist.
    if 'judith' in artist or 'dvortygirl' in artist:return (0,title)
    if title.startswith(('file:en-uk-','file:en-us-')):return (1,title)
    if row.get('collection')=='eng-balm-emmanuel':return (4,title)
    return (2,title)

def public_source(row):
    keys=['kind','recorded_text','text','title','artist','credit','copyright','license','license_url',
          'page_url','archive_url','url','collection','source_url','voice','rate','engine','created_at']
    result={k:row[k] for k in keys if row.get(k)}
    if row['kind']=='human_recording':
        result['license_url']=license_link(row['license'],row.get('license_url'),row.get('page_url'))
        result['processing']='格式转换为单声道 24 kHz；保留发音，轻微修整首尾静音并调整峰值音量。'
    else:result['processing']='神经网络合成；轻微修整首尾静音并调整峰值音量。'
    result['cache_filename']=Path(row['cache_file']).name
    if row.get('available_path'):result['original_filename']=Path(row['available_path']).name
    result['sha256_original']=hashlib.sha256((ROOT/row['cache_file']).read_bytes()).hexdigest()
    return result

def main(prepare_only=False):
    entries=load(ROOT/'data/pdf_entries.json');humans=load(CACHE/'human_sources.json');tts=load(CACHE/'tts_sources.json',{})
    candidates={p['cache_file']:p for rows in humans.values() for p in rows if p.get('cache_file') and (ROOT/p['cache_file']).exists()}
    candidates.update({p['cache_file']:p for p in tts.values() if (ROOT/p['cache_file']).exists()})
    lengths={};bad={}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(decode,path):path for path in candidates}
        for count,f in enumerate(as_completed(futures),1):
            try:path,n=f.result();lengths[path]=n
            except Exception as exc:bad[futures[f]]=str(exc)
            if count%200==0 or count==len(futures):print('DECODED',count,'/',len(futures),'bad',len(bad),flush=True)
    save(CACHE/'decode_errors.json',bad)
    plan=[];missing=[]
    for entry in entries:
        rows=humans.get(query(entry['phrase']),[])
        usable=[r for r in rows if r.get('cache_file') in lengths and norm(r.get('recorded_text',r.get('text','')))==query(entry['phrase'])]
        if usable:chosen=sorted(usable,key=rank)[0]
        else:
            chosen=tts.get(str(entry['id']))
            if not chosen or chosen['cache_file'] not in lengths:
                missing.append({'id':entry['id'],'phrase':entry['phrase']});continue
        spoken=chosen.get('recorded_text',chosen.get('text'))
        notes=[]
        if chosen['kind']=='ai_generated':notes.append('AI 配音：'+chosen['voice']+'；朗读内容见音频示范。')
        if re.search(r'\b(?:sb|sth|X|A|B|yourself)\b|…|\.{3}',entry['phrase']):
            notes.append('原表含可替换成分；录音朗读固定短语部分或具体用法示范，不朗读 sb/sth 字母。')
        plan.append({**entry,'source':chosen,'audio_text':spoken,'audio_notes':notes})
    save(CACHE/'audio_plan.json',plan)
    if missing:
        save(CACHE/'missing_audio.json',missing)
        raise ValueError(f'{len(missing)} entries need fallback audio: {missing[:3]}')
    if prepare_only:
        print('PLAN_READY',len(plan),dict(Counter(x['source']['kind'] for x in plan)),flush=True);return
    audio=ROOT/'audio';audio.mkdir(exist_ok=True)
    wav=CACHE/'OxfordPhraseList_full.wav';gap=b'\0\0'*int(RATE*PAUSE)
    frames=0;timeline=[];sources={}
    with wave.open(str(wav),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(RATE)
        for row in plan:
            source=row['source'];path=source['cache_file'];start=frames/RATE
            data=pcm_path(path).read_bytes();stream.writeframesraw(data);frames+=len(data)//2
            spoken_end=frames/RATE;stream.writeframesraw(gap);frames+=len(gap)//2
            sid=hashlib.sha256(path.encode()).hexdigest()[:12]
            sources[sid]=public_source(source)
            timeline.append({'id':row['id'],'phrase':row['phrase'],'level':row['level'],'start':round(start,5),
                             'spoken_end':round(spoken_end,5),'end':round(frames/RATE,5),'timecode':timecode(start),
                             'source_id':sid,'kind':source['kind'],'audio_text':row['audio_text'],'notes':row['audio_notes']})
    target=audio/'OxfordPhraseList_连续听读.mp3'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(wav),'-codec:a','libmp3lame',
                    '-b:a','64k','-ac','1','-ar',str(RATE),'-map_metadata','-1',
                    '-metadata','title=Oxford Phrase List — PDF-order continuous study audio',
                    '-metadata','artist=Credited human speakers and labelled AI voices; see source manifest',str(target)],check=True)
    counts=Counter(x['kind'] for x in timeline)
    result={'sample_rate':RATE,'pause_seconds':PAUSE,'duration_seconds':round(frames/RATE,5),'encoded_duration_seconds':MP3(target).info.length,
            'file':target.relative_to(ROOT).as_posix(),'human_entries':counts['human_recording'],'ai_entries':counts['ai_generated'],
            'entries':timeline,'sources':sources}
    save(ROOT/'data/audio_timeline.json',result)
    lrc=['[ti:Oxford Phrase List PDF 原序连续听读]','[ar:真人录音与明确标注的 AI 配音；详见来源文件]']
    for row in timeline:
        label='真人' if row['kind']=='human_recording' else 'AI'
        lrc.append(f"[{timecode(row['start'],True)}]{row['id']:04d} {row['level']} {row['phrase']} [{label}] | {row['audio_text']}")
    (audio/(target.stem+'.lrc')).write_text('\n'.join(lrc)+'\n',encoding='utf-8')
    print('AUDIO_COMPLETE',json.dumps({'entries':len(timeline),'human':counts['human_recording'],'ai':counts['ai_generated'],
                                     'duration':timecode(frames/RATE),'bytes':target.stat().st_size,'sources':len(sources)},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');main(parser.parse_args().prepare_only)
