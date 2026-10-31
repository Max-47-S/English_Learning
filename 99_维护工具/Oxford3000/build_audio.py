"""Decode, level and concatenate the selected licensed human clips in PDF order."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import wave

REPOSITORY=Path(__file__).resolve().parents[2]
ROOT=REPOSITORY/'01_词汇与短语'/'Oxford3000_学习包'
CACHE=ROOT/'_cache'
sys.path.insert(0,str(CACHE/'python'))
import imageio_ffmpeg
import numpy as np
import av
from mutagen.mp3 import MP3

RATE=24000
PAUSE=1.2
PART_PAUSE=0.18
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()
PCM=CACHE/'pcm'
PCM.mkdir(exist_ok=True)


def pcm_path(path):
    return PCM/(hashlib.sha256(path.encode()).hexdigest()[:24]+'.s16')


def decode(path):
    target=pcm_path(path)
    if target.exists() and target.stat().st_size>100:
        return path,target.stat().st_size//2
    chunks=[]
    resampler=av.AudioResampler(format='s16',layout='mono',rate=RATE)
    with av.open(str(ROOT/path)) as container:
        for frame in container.decode(audio=0):
            chunks.extend(part.to_ndarray().reshape(-1) for part in resampler.resample(frame))
        chunks.extend(part.to_ndarray().reshape(-1) for part in resampler.resample(None))
    if not chunks:raise ValueError('No audio frames: '+path)
    samples=np.concatenate(chunks).astype(np.float32)
    if len(samples)<RATE*0.08:raise ValueError('Audio too short: '+path)
    if len(samples)>RATE*15:raise ValueError('Unexpectedly long word clip: '+path)
    peak=float(np.max(np.abs(samples)))
    if peak<20:raise ValueError('Silent clip: '+path)
    # Retain 100 ms around audible content; never remove low-level internal sounds.
    active=np.flatnonzero(np.abs(samples)>max(25,peak*0.002))
    start=max(0,int(active[0])-int(RATE*0.1))
    stop=min(len(samples),int(active[-1])+int(RATE*0.1)+1)
    samples=samples[start:stop]*min(6.0,27852.0/peak)
    data=np.clip(samples,-32767,32767).astype('<i2').tobytes()
    target.write_bytes(data)
    return path,len(data)//2


def timecode(seconds,lrc=False):
    if lrc:
        centis=round(seconds*100)
        return f'{centis//6000:02d}:{centis//100%60:02d}.{centis%100:02d}'
    seconds=int(seconds)
    return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'


def main(available_only=False):
    plan=json.loads((ROOT/'data/audio_plan.json').read_text(encoding='utf-8'))
    paths=list(dict.fromkeys(part['cache_file'] for row in plan for part in row['parts']))
    missing=[p for p in paths if not (ROOT/p).exists()]
    if missing and not available_only:raise FileNotFoundError(f'{len(missing)} selected recordings missing: {missing[:3]}')
    available=[p for p in paths if p not in set(missing)]
    lengths={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(decode,p) for p in available]
        for done,future in enumerate(as_completed(futures),1):
            path,length=future.result();lengths[path]=length
            if done%250==0 or done==len(available):print('DECODED',done,'/',len(available),flush=True)
    if available_only:
        print('DECODE_AVAILABLE_COMPLETE','ready',len(available),'missing',len(missing),flush=True)
        return
    audio=ROOT/'audio';audio.mkdir(exist_ok=True)
    wav=CACHE/'Oxford3000_full.wav'
    gap=b'\0\0'*int(RATE*PAUSE)
    part_gap=b'\0\0'*int(RATE*PART_PAUSE)
    frames=0;timeline=[];sources={}
    with wave.open(str(wav),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(RATE)
        for row in plan:
            start=frames/RATE
            ids=[]
            for no,part in enumerate(row['parts']):
                if no:
                    stream.writeframesraw(part_gap);frames+=len(part_gap)//2
                data=pcm_path(part['cache_file']).read_bytes()
                stream.writeframesraw(data);frames+=len(data)//2
                source_id=hashlib.sha256(part['cache_file'].encode()).hexdigest()[:12]
                sources[source_id]=part;ids.append(source_id)
            spoken_end=frames/RATE
            stream.writeframesraw(gap);frames+=len(gap)//2
            timeline.append({'id':row['id'],'word':row['word'],'level':row['level'],'start':round(start,5),'spoken_end':round(spoken_end,5),'end':round(frames/RATE,5),'timecode':timecode(start),'source_ids':ids,'kind':'human_recording','notes':row['notes']})
    mp3=audio/'Oxford3000_完整连续真人音频.mp3'
    subprocess.run([FFMPEG,'-y','-v','error','-i',str(wav),'-codec:a','libmp3lame','-b:a','64k','-ac','1','-ar',str(RATE),'-map_metadata','-1','-metadata','title=Oxford 3000 — PDF order human pronunciation','-metadata','artist=Various credited speakers; see audio source manifest',str(mp3)],check=True)
    duration=MP3(mp3).info.length
    output={'sample_rate':RATE,'pause_seconds':PAUSE,'duration_seconds':frames/RATE,'encoded_duration_seconds':duration,'file':mp3.relative_to(ROOT).as_posix(),'human_entries':len(timeline),'ai_entries':0,'entries':timeline,'sources':sources}
    (ROOT/'data/audio_timeline.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lrc=['[ti:Oxford 3000 PDF 原序真人连续音频]','[ar:多位真人朗读者；逐段署名见来源文件]']
    for row in timeline:lrc.append(f"[{timecode(row['start'],True)}]{row['id']:04d} {row['level']} {row['word']}")
    (audio/(mp3.stem+'.lrc')).write_text('\n'.join(lrc)+'\n',encoding='utf-8')
    print('AUDIO_COMPLETE',json.dumps({'entries':len(timeline),'unique_clips':len(sources),'human':len(timeline),'ai':0,'duration':timecode(frames/RATE),'bytes':mp3.stat().st_size,'encoded_duration':duration},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--decode-available',action='store_true')
    main(p.parse_args().decode_available)
