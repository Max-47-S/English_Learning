"""Export a portable, offline HTML player with losslessly indexed original MP3s."""
from pathlib import Path
import base64
import hashlib
import json
import shutil
import zipfile


def export_pc(dataset, template, destination, source_root, repo):
    destination = Path(destination)
    audio = destination / 'audio'
    audio.mkdir(parents=True, exist_ok=True)
    tracks = []
    for track in dataset['tracks']:
        if track['chapter'] not in (3, 4, 5, 11):
            continue
        index = track['mp3Index']
        target = audio / (track['id'] + '.mp3')
        valid = target.exists() and target.stat().st_size == index['bytes']
        if valid:
            valid = hashlib.sha256(target.read_bytes()).hexdigest() == index['sha256']
        if not valid:
            with (source_root / track['file']).open('rb') as original, target.open('wb') as output:
                output.write(base64.b64decode(index['prefixBase64']))
                original.seek(index['sourceOffset'])
                remaining = index['bodyBytes']
                while remaining:
                    block = original.read(min(4 * 1024 * 1024, remaining))
                    if not block:
                        raise ValueError('Original MP3 ended unexpectedly')
                    output.write(block)
                    remaining -= len(block)
            assert hashlib.sha256(target.read_bytes()).hexdigest() == index['sha256']
        tracks.append({**track, 'file': 'audio/' + target.name})
    data = {**dataset, 'collections': [c for c in dataset['collections'] if c['id'] == 'ielts'],
            'chapters': [c for c in dataset['chapters'] if c['collection'] == 'ielts'],
            'entries': [e for e in dataset['entries'] if e['collection'] == 'ielts'], 'tracks': tracks,
            'defaultCollection': 'ielts', 'defaultMode': 'original', 'defaultView': 'pc',
            'localAudioIndexed': True, 'pdfHref': 'source/chapter11.pdf'}
    assert len(data['entries']) == 5569 and len(tracks) == 59
    page = template.replace('__STUDY_DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c'))
    page = page.replace('<body>', '<body class="pc-view pc-pack">').replace('<title>英语听读 · Oxford 与雅思</title>', '<title>王陆听力 · 四章真人听读</title>')
    page = page.replace('英语听读<small>单词、短语、听力，都在这里。</small>', '王陆听力<small>四章原版真人录音 · 同步词卡</small>')
    (destination / 'PC听读.html').write_text(page)
    (destination / 'source').mkdir(exist_ok=True)
    shutil.copyfile(source_root / 'Chapter11_综合测试/文本/Chapter11_综合测试_剑21版.pdf', destination / 'source/chapter11.pdf')
    (destination / '使用说明.md').write_text('''# 王陆四章 PC 听读

双击 `PC听读.html`，用 Chrome、Edge 或 Safari 打开。保持 `audio` 文件夹与 HTML 在一起，复制整个文件夹即可换电脑使用，无需安装程序或联网。

- Chapter 3、4、5、11 共 5,569 条词卡、59 段原版真人录音，横向／纵向录音分别同步。
- 选“原版录音”后点击连续播放，卡片和目录会跟着原声变化。1× 保持原来的声音、停顿和节奏。
- 上方速度可选 0.5×～2×。倍速同时缩放发音和原有间隔，不额外插入停顿。
- 点击目录可定位到本词。上一词、下一词、重听均播放本词后暂停；点击连续播放或音频进度条恢复连续。
- “系统朗读”为设备合成语音，另有词间停顿设置，与原版真人录音分开。
- 空格播放／暂停，←／→ 切词，R 重听；在输入框或按钮内时使用控件自己的键盘操作。

音频保留原始 MPEG 声音帧，仅补充准确的浏览器播放索引；未重新录音、配音或改变原有节奏。
''')
    archive = destination.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as bundle:
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(destination.parent))
    print('PC PACK', destination, 'ZIP', archive, flush=True)
