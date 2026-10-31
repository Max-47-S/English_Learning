"""Extract the supplied PDF in its own reading order and fetch reusable sources."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
REPOSITORY=Path(__file__).resolve().parents[2]
ROOT=REPOSITORY/'01_词汇与短语'/'Oxford3000_学习包'
PROJECT = REPOSITORY
CACHE = ROOT / "_cache"
DATA = ROOT / "data"
PDF = PROJECT / "06_原始资料/Oxford词表/oxford-3000-by-cefr-level.pdf"

SOURCES = {
    "averaged_perceptron_tagger_eng.zip": "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/taggers/averaged_perceptron_tagger_eng.zip",
    "wordnet.zip": "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/wordnet.zip",
    "ecdict.csv": "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv",
    "ECDICT_LICENSE.txt": "https://raw.githubusercontent.com/skywind3000/ECDICT/master/LICENSE",
    "cmn-eng.zip": "https://www.manythings.org/anki/cmn-eng.zip",
    "eng-wims-mary_flac.tar.xz": "https://www.yojik.eu/audiocollections/archives/eng-wims-mary_flac.tar.xz",
    "eng-wcp-us_flac.tar.xz": "https://www.yojik.eu/audiocollections/archives/eng-wcp-us_flac.tar.xz",
    "eng-wims-mary_README.txt": "https://www.yojik.eu/audiocollections/detailled/eng-wims-mary/readme.txt",
    "eng-wcp-us_README.txt": "https://www.yojik.eu/audiocollections/detailled/eng-wcp-us/readme.txt",
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract():
    from pypdf import PdfReader
    import pdfplumber
    reader = PdfReader(PDF)
    entries = []
    levels = Counter()
    level = None
    unmatched = []
    page_texts = []
    pos_re = re.compile(r"^(.*?)\s+(indefinite article|definite article|modal v\.|auxiliary v\.|exclam\.|det\.|pron\.|prep\.|adv\.|adj\.|conj\.|n\.|v\.|number)(.*)$")
    with pdfplumber.open(PDF) as coordinate_pdf:
      for page_no, page in enumerate(coordinate_pdf.pages, 1):
        columns = []
        for x0, x1 in [(35, 169), (169, 300), (300, 431), (431, 561)]:
            crop = page.crop((x0, 115 if page_no == 1 else 35, x1, 800))
            columns.append(crop.extract_text(x_tolerance=1.3, y_tolerance=3) or "")
        text = "\n".join(columns).replace("\xa0", " ")
        page_texts.append({"page": page_no, "text": text})
        pending = ""
        for raw in text.splitlines():
            line = re.sub(r"\s+", " ", raw).strip()
            if not line or "Oxford" in line or "University Press" in line or re.fullmatch(r"\d+ / \d+", line):
                continue
            if re.fullmatch(r"[AB][12]", line):
                level = line
                continue
            if not level:
                continue
            if line in {"to", "of"} and not pending and entries and entries[-1]["word"] in {"ought", "used", "have", "next", "according", "out"}:
                entries[-1]["word"] += " " + line
                entries[-1]["lookup"] += " " + line
                entries[-1]["pdf_text"] += " " + line
                continue
            if re.match(r"^(adj\.|adv\.|n\.|v\.|prep\.|pron\.|det\.|conj\.|exclam\.|number|auxiliary)", line) and entries and not pending:
                entries[-1]["pos"] += " " + line
                entries[-1]["pdf_text"] += " " + line
                continue
            current = (pending + " " + line).strip()
            match = pos_re.match(current)
            if not match:
                pending = current
                continue
            head, pos, rest = match.groups()
            pending = ""
            qualifier = ""
            q = re.search(r"\s*\((.*)\)\s*$", head)
            if q:
                qualifier = q.group(1)
                head = head[:q.start()].strip()
            homograph = ""
            h = re.search(r"([1-9])$", head)
            if h:
                homograph = h.group(1)
                head = head[:h.start()]
            levels[level] += 1
            entries.append({
                "id": len(entries) + 1,
                "level": level,
                "level_index": levels[level],
                "word": head,
                "lookup": head.lower().replace("’", "'"),
                "qualifier": qualifier,
                "homograph": homograph,
                "pos": (pos + rest).strip(),
                "pdf_page": page_no,
                "pdf_text": current,
            })
        if pending:
            unmatched.append({"page": page_no, "text": pending})
    if unmatched:
        raise RuntimeError(f"Unparsed PDF text: {unmatched}")
    metadata = {
        "source_pdf": PDF.name,
        "sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
        "pages": len(reader.pages),
        "entries": len(entries),
        "unique_lookups": len({e["lookup"] for e in entries}),
        "level_counts": dict(levels),
        "reading_order": "PDF visual coordinates: each page, four columns left-to-right and each column top-to-bottom; retain repeated words at different CEFR levels and parts of speech.",
    }
    write_json(DATA / "pdf_entries.json", entries)
    write_json(DATA / "pdf_metadata.json", metadata)
    write_json(CACHE / "pdf_extracted_pages.json", page_texts)
    print(json.dumps(metadata, ensure_ascii=False), flush=True)
    for lev in levels:
        group = [e for e in entries if e["level"] == lev]
        print(lev, "FIRST", [e["word"] for e in group[:8]], "LAST", [e["word"] for e in group[-8:]], flush=True)


def download(names, proxy):
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy}) if proxy else urllib.request.ProxyHandler()
    opener = urllib.request.build_opener(handler)
    CACHE.mkdir(parents=True, exist_ok=True)
    for name in names or SOURCES:
        url = SOURCES[name]
        destination = CACHE / name
        if destination.exists() and destination.stat().st_size:
            print("CACHED", name, destination.stat().st_size, flush=True)
            continue
        partial = destination.with_name(destination.name + ".part")
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "EnglishLearningPersonal/1.0 (+https://github.com/Max-47-S/English_Learning)"})
                with opener.open(request, timeout=60) as response, partial.open("wb") as output:
                    total = 0
                    last_report = time.monotonic()
                    while chunk := response.read(1024 * 256):
                        output.write(chunk)
                        total += len(chunk)
                        if time.monotonic() - last_report > 15:
                            print("DOWNLOADING", name, round(total/1024/1024, 1), "MiB", flush=True)
                            last_report = time.monotonic()
                partial.replace(destination)
                print("DOWNLOADED", name, total, flush=True)
                break
            except Exception as exc:
                print("DOWNLOAD_RETRY", name, attempt+1, str(exc), flush=True)
                if attempt == 2:
                    raise
                time.sleep(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["extract", "download"])
    parser.add_argument("names", nargs="*")
    parser.add_argument("--proxy")
    args = parser.parse_args()
    if args.action == "extract":
        extract()
    else:
        download(args.names, args.proxy)
