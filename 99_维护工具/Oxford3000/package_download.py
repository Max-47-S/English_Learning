"""Create a portable study bundle, excluding raw downloads and build caches."""
from pathlib import Path
import zipfile

REPOSITORY=Path(__file__).resolve().parents[2]
ROOT=REPOSITORY/'01_词汇与短语'/'Oxford3000_学习包'


if __name__=='__main__':
    target=REPOSITORY/'_exports/Oxford3000_学习包.zip'
    target.parent.mkdir(parents=True,exist_ok=True)
    paths=[p for p in ROOT.rglob('*') if p.is_file() and not any(part in {'_cache','__pycache__'} for part in p.relative_to(ROOT).parts)]
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for path in paths:archive.write(path,path.relative_to(REPOSITORY).as_posix())
        source=REPOSITORY/'06_原始资料/Oxford词表/oxford-3000-by-cefr-level.pdf'
        archive.write(source,source.relative_to(REPOSITORY).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert archive.getinfo('01_词汇与短语/Oxford3000_学习包/audio/Oxford3000_完整连续真人音频.mp3').file_size==(ROOT/'audio/Oxford3000_完整连续真人音频.mp3').stat().st_size
        print('BUNDLE_COMPLETE',target,'files',len(archive.infolist()),'bytes',target.stat().st_size,flush=True)
