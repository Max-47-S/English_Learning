"""Read phrase-table columns separately to prevent OCR crossing column boundaries."""
from pathlib import Path
import json
import sys

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS / '_cache/python'))
import objc
import Vision
from Foundation import NSURL

ROOT = TOOLS.parents[1] / '05_听力与歌曲/雅思王听力语料库'
CACHE = TOOLS / '_cache/chapter11_ocr'


def main():
    pages = json.loads((ROOT / 'data/chapter11_ocr_pages.json').read_text())['pages']
    output = []
    for page in pages:
        n = page['pdf_page']
        if not any(a <= n <= b for a, b in [(7, 12), (17, 22), (27, 31), (59, 70)]):
            continue
        target = CACHE / f'columns-{n:03d}.json'
        if target.exists():
            output.append(json.loads(target.read_text()))
            continue
        upper = .923
        heading = next((r for r in page['observations'] if '训练' in r['text'] and
                        ('吞音' in r['text'] or '连读' in r['text'])), None)
        if heading:
            upper = heading['y'] - .012
        results = {'pdf_page': n, 'upper': upper, 'columns': {}}
        png = CACHE / page['image']
        for label, left, width, chinese in [
            ('left_word', .115, .259, False), ('left_meaning', .374, .132, True),
            ('right_word', .491, .259, False), ('right_meaning', .751, .193, True),
        ]:
            roi = (left, .063, width, upper - .063)
            with objc.autorelease_pool():
                request = Vision.VNRecognizeTextRequest.alloc().init()
                request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
                request.setRecognitionLanguages_(['zh-Hans', 'en-US'] if chinese else ['en-US'])
                request.setUsesLanguageCorrection_(chinese)
                request.setAutomaticallyDetectsLanguage_(chinese)
                request.setRegionOfInterest_(((roi[0], roi[1]), (roi[2], roi[3])))
                handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
                    NSURL.fileURLWithPath_(str(png)), {})
                ok, error = handler.performRequests_error_([request], None)
                if not ok:
                    raise RuntimeError(str(error))
                rows = []
                for observation in request.results():
                    candidate = observation.topCandidates_(1)[0]
                    b = observation.boundingBox()
                    rows.append({'text': str(candidate.string()), 'confidence': float(candidate.confidence()),
                                 'x': roi[0] + b.origin.x * roi[2],
                                 'y': roi[1] + b.origin.y * roi[3],
                                 'w': b.size.width * roi[2], 'h': b.size.height * roi[3]})
                results['columns'][label] = rows
        target.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
        output.append(results)
        print('PHRASE_COLUMNS', n, {k: len(v) for k, v in results['columns'].items()}, flush=True)
    (ROOT / 'data/chapter11_ocr_columns.json').write_text(json.dumps(
        {'pages': output}, ensure_ascii=False, indent=2) + '\n')
    print('PHRASE_COLUMNS_COMPLETE', len(output), flush=True)


if __name__ == '__main__':
    main()
