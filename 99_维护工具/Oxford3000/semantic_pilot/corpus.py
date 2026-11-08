"""Prepare a local review concordance from the pinned sample PDFs."""

import hashlib
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OXFORD = ROOT / "01_词汇与短语" / "Oxford3000_学习包"
PRIVATE = ROOT / "_exports" / "Oxford3000_雅思语义试点"
TOKEN = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
BOUNDARY = re.compile(r"""[.!?]+[)"'’”]* (?=[A-Z"'‘“])""")
ABBREVIATION = re.compile(r"\b(?:Mr|Mrs|Dr|Ms|Prof|St|[A-Z])\.$")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True)
class Sentence:
    ref: str
    source: str
    lines: tuple
    text: str

    @property
    def tokens(self):
        return list(TOKEN.finditer(self.text))

    @property
    def complete(self):
        return bool(re.search(r"""(?<!\.)[.!?]["'’”)]*$""", self.text))


def split_sentences(text):
    start = 0
    for boundary in BOUNDARY.finditer(text):
        end = boundary.end() - 1
        if ABBREVIATION.search(text[start:end]):
            continue
        yield text[start:end]
        start = boundary.end()
    if start < len(text):
        yield text[start:]


def blocks_on_page(page, start, end, speaker):
    lines = []
    for line_number in range(start, end + 1):
        line = page[line_number - 1].strip()
        if not line:
            if lines:
                yield lines
                lines = []
            continue
        line = re.sub(speaker, "", line) if speaker else line
        lines.append((line_number, re.sub(r"\s+", " ", line)))
    if lines:
        yield lines


def load_corpus(directory, pdftotext):
    manifest = read_json(HERE / "sources.json")
    pages_by_file = {}
    for filename, pdf in manifest["pdfs"].items():
        path = directory / filename
        if sha256(path) != pdf["sha256"]:
            raise ValueError(f"{filename}: PDF differs from the reviewed version")
        layout = subprocess.check_output(
            [pdftotext, "-layout", "-enc", "UTF-8", "-eol", "unix", str(path), "-"],
            encoding="utf-8",
        )
        pages_by_file[filename] = [page.split("\n") for page in layout.split("\f")]

    sentences = {}
    seen_passages = set()
    for source in manifest["sources"]:
        blocks = []
        pages = pages_by_file[source["file"]]
        for region in source["regions"]:
            page, first, last = region[:3]
            for index, lines in enumerate(
                blocks_on_page(pages[page - 1], first, last, source.get("speaker"))
            ):
                text = ""
                for _, line in lines:
                    # Join wrapped lines, retaining printed hyphens and punctuation.
                    text += ("" if not text or text.endswith("-") else " ") + line
                location = (page, lines[0][0], lines[-1][0])
                if len(region) == 4 and region[3] == "continue" and index == 0:
                    previous_lines, previous_text = blocks[-1]
                    blocks[-1] = (previous_lines + (location,), previous_text + " " + text)
                else:
                    blocks.append(((location,), text))
        passage = tuple(text.casefold() for _, text in blocks)
        if not blocks or passage in seen_passages:
            raise ValueError(f'{source["id"]}: empty or duplicate passage')
        seen_passages.add(passage)
        for paragraph, (lines, text) in enumerate(blocks, 1):
            for number, sentence in enumerate(split_sentences(text), 1):
                ref = f'{source["id"]}.{paragraph:02}.{number:02}'
                sentences[ref] = Sentence(ref, source["id"], lines, sentence)
    return manifest, sentences


def candidates(words, sentences):
    by_form = defaultdict(list)
    for word, forms in words.items():
        for form in set([word, *forms]):
            by_form[form].append(word)
    for sentence in sentences.values():
        for index, match in enumerate(sentence.tokens):
            form = match.group().casefold().replace("’", "'").removesuffix("'s")
            for word in by_form[form]:
                yield (word, sentence.ref, index), match
