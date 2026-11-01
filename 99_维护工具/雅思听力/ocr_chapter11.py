"""Recognize the supplied Chapter 11 PDF locally with macOS Vision."""
from pathlib import Path
import json
import os
import subprocess
import sys

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS / '_cache/python'))
import objc
import Vision
from Foundation import NSURL
from pypdf import PdfReader

ROOT = TOOLS.parents[1] / '05_听力与歌曲/雅思王听力语料库'
PDF = ROOT / 'Chapter11_综合测试/文本/Chapter11_综合测试_剑21版.pdf'
CACHE = TOOLS / '_cache/chapter11_ocr'
RENDER = Path('/Users/wangxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm')


def recognize(page):
    target = CACHE / f'page-{page:03d}.json'
    if target.exists():
        return json.loads(target.read_text())
    prefix = CACHE / f'page-{page:03d}'
    png = prefix.with_suffix('.png')
    if not png.exists():
        subprocess.run([str(RENDER), '-f', str(page), '-l', str(page), '-scale-to',
                        '2600', '-png', '-singlefile', str(PDF), str(prefix)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with objc.autorelease_pool():
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(['zh-Hans', 'en-US'])
        request.setUsesLanguageCorrection_(True)
        request.setAutomaticallyDetectsLanguage_(True)
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
            NSURL.fileURLWithPath_(str(png)), {})
        ok, error = handler.performRequests_error_([request], None)
        if not ok:
            raise RuntimeError(str(error))
        rows = []
        for observation in request.results():
            candidate = observation.topCandidates_(1)[0]
            box = observation.boundingBox()
            rows.append({'text': str(candidate.string()), 'confidence': float(candidate.confidence()),
                         'x': box.origin.x, 'y': box.origin.y,
                         'w': box.size.width, 'h': box.size.height})
    result = {'pdf_page': page, 'image': png.name, 'observations': rows}
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    total = len(PdfReader(PDF).pages)
    pages = []
    for page in range(1, total + 1):
        result = recognize(page)
        pages.append(result)
        top = [r['text'] for r in result['observations'] if r['y'] > .75 and r['x'] < .7]
        print(f'{page}/{total} ' + ' | '.join(top[:5]), flush=True)
        (ROOT / 'data/chapter11_ocr_pages.json').write_text(json.dumps(
            {'engine': 'macOS Vision accurate, zh-Hans + en-US', 'render_pixels': 2600,
             'pdf_pages': total, 'completed_pages': len(pages), 'pages': pages},
            ensure_ascii=False, indent=2) + '\n')
    print('OCR_COMPLETE', len(pages), flush=True)


if __name__ == '__main__':
    main()
