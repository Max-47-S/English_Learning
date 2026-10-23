"""Index original SWAC tags and retain attribution on every reusable clip."""
from collections import defaultdict
from pathlib import Path
import json
import re
import sys
import configparser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '_cache/python'))


def main():
    commons = json.loads((ROOT / 'data/human_audio_sources_v2.json').read_text(encoding='utf-8'))
    normalize_title = lambda title: title.replace('_', ' ').casefold()
    by_title = {normalize_title(r['title']): r for rows in commons.values() for r in rows}
    components_path = ROOT / 'data/human_audio_components.json'
    if components_path.exists():
        components = json.loads(components_path.read_text(encoding='utf-8'))
        by_title.update({normalize_title(r['title']):r for rows in components.values() for r in rows})
    result = defaultdict(list)
    for pack in ['eng-wcp-us', 'eng-wims-mary','eng-balm-emmanuel','eng-balm-judith','eng-balm-verbs']:
        folder = ROOT / '_cache/collections' / pack / 'flac'
        config = configparser.ConfigParser(interpolation=None, strict=False)
        text_index = (folder / 'index.tags.txt').read_text(encoding='utf-8-sig')
        config.read_string(text_index[text_index.index('[GLOBAL]'):])
        for filename in config.sections():
            if not filename.lower().endswith('.flac'):
                continue
            path = folder / filename
            get = lambda k: config.get(filename, k.upper(), fallback=config.get('GLOBAL', k.upper(), fallback='')).strip()
            text = get('swac_text') or get('title')
            if not text:
                continue
            row = {
                'text': text, 'cache_file': path.relative_to(ROOT).as_posix(),
                'collection': pack, 'artist': get('swac_speak_name'),
                'copyright': get('swac_coll_copyright'), 'tag_license': get('swac_coll_license'),
                'page_url': 'https://www.yojik.eu/audiocollections/audiocollections.html',
                'archive_url': f'https://www.yojik.eu/audiocollections/archives/{pack}_flac.tar.xz',
                'kind': 'human_recording',
            }
            if pack == 'eng-balm-judith':
                row.update(license='CC BY 3.0 US',license_url='https://creativecommons.org/licenses/by/3.0/us/',
                           credit=get('swac_coll_authors'))
            elif pack in {'eng-balm-emmanuel','eng-balm-verbs'}:
                row.update(license='CC BY 2.0 FR',license_url='https://creativecommons.org/licenses/by/2.0/fr/',
                           credit=get('swac_coll_authors'))
            elif pack == 'eng-wims-mary':
                row.update(license='CC BY 3.0 US', license_url='https://creativecommons.org/licenses/by/3.0/us/',
                           credit='Mary Maury; Bernadette Perrin-Riou; Association WimsEdu')
            else:
                original_title = 'File:' + path.stem + '.ogg'
                meta = by_title.get(normalize_title(original_title))
                if meta:
                    row.update({k: meta[k] for k in ['license','license_url','page_url','artist','credit','title']})
                else:
                    # The archive README offers BY 2.0 FR, but its audio tags say BY-SA
                    # without a version. Exclude these ambiguous files from automatic selection.
                    row.update(license='unresolved: archive README BY 2.0 FR / embedded tag BY-SA',
                               license_url='', excluded_license=True)
            key = text.lower().replace('’', "'")
            result[key].append(row)
    target = ROOT / '_cache/collection_index.json'
    target.write_text(json.dumps(dict(result), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    entries = json.loads((ROOT / 'data/pdf_entries.json').read_text(encoding='utf-8'))
    missing = sorted({e['lookup'] for e in entries if not any(not r.get('excluded_license') for r in result.get(e['lookup'], []))})
    print('INDEXED', len(result), 'LOOKUPS_MISSING_EXACT', len(missing), flush=True)
    print('MISSING',json.dumps(missing,ensure_ascii=False),flush=True)
    special = ['close','live','lead','record','present','object','subject','conduct','content','use','house','desert','tear','wind','used','separate','graduate','produce','IT','cd','dvd','c','d','v','ought','to','per cent','percent']
    for word in special:
        found={k:[{f:r[f] for f in ['text','collection','cache_file','license']} for r in rows] for k,rows in result.items() if re.fullmatch(re.escape(word.lower())+r'(?:\b.*)?', k)}
        print('VARIANTS',word,json.dumps(found,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
