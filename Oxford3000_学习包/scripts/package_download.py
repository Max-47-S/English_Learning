"""Create a portable study bundle, excluding raw downloads and build caches."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    target=ROOT.parent/'Oxford3000_学习包.zip'
    paths=[p for p in ROOT.rglob('*') if p.is_file() and not any(part in {'_cache','__pycache__'} for part in p.relative_to(ROOT).parts)]
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for path in paths:archive.write(path,path.relative_to(ROOT.parent).as_posix())
        source=ROOT.parent/'oxford-3000-by-cefr-level.pdf'
        archive.write(source,source.name)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert archive.getinfo('Oxford3000_学习包/audio/Oxford3000_完整连续真人音频.mp3').file_size==(ROOT/'audio/Oxford3000_完整连续真人音频.mp3').stat().st_size
        print('BUNDLE_COMPLETE',target,'files',len(archive.infolist()),'bytes',target.stat().st_size,flush=True)
