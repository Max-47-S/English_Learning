"""Build the private Oxford 3000 IELTS semantic pilot and its audio index."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from corpus import HERE, OXFORD, PRIVATE, candidates, load_corpus, read_json, sha256


WORDNET_SHA256 = "6c492d0c7b4a40e7674d088191d3aa11f373bb1da60762e098b8ee2dda96ef22"
POS = {"1": "n.", "2": "v.", "3": "adj.", "4": "adv.", "5": "adj."}
EXCLUDED = {
    "!proper-name": "专名",
    "!same-phrase": "同一个固定短语里的第二个词形",
    "!different-lexeme": "属于另一个独立词目",
    "?context": "语境不足，待核实",
}
AUDIO_FILE = Path("audio") / "30词真人音频.mp3"


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_senses(lexicon, archive):
    if sha256(archive) != WORDNET_SHA256:
        raise ValueError("WordNet archive differs from the reviewed release")
    with tarfile.open(archive, "r:bz2") as tar:
        license_text = tar.extractfile("WordNet-3.0/LICENSE").read()
        if license_text != (HERE / "WORDNET-LICENSE.txt").read_bytes():
            raise ValueError("WordNet license copy differs from the archive")
        index = {line.split()[0].decode() for line in tar.extractfile("WordNet-3.0/dict/index.sense")}
    senses = {}
    for word, entry in lexicon.items():
        seen = set()
        for sense, (key, gloss) in entry["senses"].items():
            lemma, code = key.split("%", 1)
            if key not in index or key in seen or word not in lemma.split("_"):
                raise ValueError(f"{word}.{sense}: invalid WordNet sense key {key}")
            seen.add(key)
            senses[word, sense] = {
                "id": f"{word}.{sense}",
                "wordnetKey": key,
                "pos": POS[code[0]],
                "construction": lemma.replace("_", " ") if lemma != word else "",
                "zh": gloss,
            }
    return senses, license_text


def read_reviews():
    reviews = {}
    for line in (HERE / "reviews.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        word, ref, token, sense, spans = line.split()
        key = (word, ref, int(token))
        if key in reviews:
            raise ValueError(f"Duplicate review: {key}")
        reviews[key] = (sense, [] if spans == "-" else spans.split(","))
    return reviews


def occurrence_spans(word, sentence, token, match, spans):
    tokens = sentence.tokens
    result = {}
    for span in spans:
        left, right = (token + int(offset) for offset in span.split(":"))
        if not (0 <= left <= token < right <= len(tokens) and right - left >= 2):
            raise ValueError(f"{word}/{sentence.ref}/{token}: invalid collocation span {span}")
        start, end = tokens[left].start(), tokens[right - 1].end()
        surface = sentence.text[start:end]
        key = (sentence.text[start:match.start()] + word + sentence.text[match.end():end])
        key = key.casefold().replace("’", "'")
        if key in result:
            raise ValueError(f"{word}/{sentence.ref}/{token}: duplicate collocation {key}")
        result[key] = {"text": surface, "start": start, "end": end}
    return result


def make_sense(sense, ids, evidence, sentences):
    collocations = defaultdict(list)
    for ident in ids:
        for key, span in evidence[ident]["collocations"].items():
            collocations[key].append((ident, span))
    ranked = sorted(collocations, key=lambda key: (-len(collocations[key]), key))
    rows = []
    for key in ranked:
        hits = collocations[key]
        forms = Counter(span["text"] for _, span in hits)
        rows.append({
            "key": key,
            "text": forms.most_common(1)[0][0],
            "count": len(hits),
            "forms": list(forms),
            "evidence": [ident for ident, _ in hits],
        })
    example = None
    if ranked:
        # Pick a complete occurrence of the highest-ranked collocation.
        hits = [(ident, span, sentences[evidence[ident]["sentence"]])
                for ident, span in collocations[ranked[0]]]
        complete = [(ident, span, sentence) for ident, span, sentence in hits if sentence.complete]
        if complete:
            ident, span, sentence = min(complete, key=lambda hit: (len(hit[2].text), hit[0]))
            example = {"text": sentence.text, "evidence": ident, "start": span["start"], "end": span["end"]}
    return {**sense, "count": len(ids), "evidence": ids, "collocations": rows, "example": example}


def analyse(lexicon, senses, sentences):
    forms = {word: entry["forms"] for word, entry in lexicon.items()}
    hits = dict(candidates(forms, sentences))
    reviews = read_reviews()
    if hits.keys() != reviews.keys():
        raise ValueError(f"Review coverage changed. Missing: {sorted(hits.keys() - reviews.keys())}; "
                         f"unmatched: {sorted(reviews.keys() - hits.keys())}")
    evidence = {}
    by_sense = defaultdict(list)
    by_word = defaultdict(list)
    accepted = set()
    for (word, ref, token), (sense, spans) in reviews.items():
        ident = f"{word}/{ref}/{token}"
        match = hits[word, ref, token]
        sentence = sentences[ref]
        row = {
            "word": word, "source": sentence.source, "sentence": ref, "lines": sentence.lines,
            "token": token, "form": match.group(), "start": match.start(), "end": match.end(),
        }
        evidence[ident] = row
        by_word[word].append(ident)
        if sense in EXCLUDED:
            if spans:
                raise ValueError(f"{ident}: uncounted match cannot have collocations")
            row.update(status=sense, reason=EXCLUDED[sense])
            continue
        sense_data = senses[word, sense]
        if (ref, token) in accepted:
            raise ValueError(f"{ident}: multiple accepted lemmas for the same token")
        accepted.add((ref, token))
        collocations = occurrence_spans(word, sentence, token, match, spans)
        construction = sense_data["construction"]
        if construction and not any(f" {construction} " in f" {key} " for key in collocations):
            raise ValueError(f"{ident}: the tagged construction {construction!r} needs source evidence")
        row.update(status="verified", sense=sense_data["id"], collocations=collocations)
        by_sense[word, sense].append(ident)

    cards = []
    for word in lexicon:
        groups = defaultdict(list)
        for name in lexicon[word]["senses"]:
            if ids := by_sense[word, name]:
                sense = make_sense(senses[word, name], ids, evidence, sentences)
                groups[sense["pos"]].append(sense)
        pos_groups = []
        for pos, rows in groups.items():
            rows.sort(key=lambda row: (-row["count"], row["id"]))
            pos_groups.append({"pos": pos, "count": sum(row["count"] for row in rows), "senses": rows})
        pos_groups.sort(key=lambda group: (-group["senses"][0]["count"], -group["count"], group["pos"]))
        excluded = [ident for ident in by_word[word] if evidence[ident]["status"] != "verified"]
        cards.append({
            "id": len(cards) + 1, "word": word, "groups": pos_groups, "uncounted": excluded,
            "count": sum(group["count"] for group in pos_groups),
            "forms": sorted({evidence[ident]["form"].lower() for ident in by_word[word]
                             if evidence[ident]["status"] == "verified"}),
        })
    return cards, evidence


def audio_plan(cards):
    vocab = read_json(OXFORD / "data" / "vocabulary.json")
    timeline = read_json(OXFORD / "data" / "audio_timeline.json")
    cues = {row["id"]: row for row in timeline["entries"]}
    rows = defaultdict(list)
    for entry in vocab:
        rows[entry["word"].casefold()].append(entry)
    rate = timeline["sample_rate"]
    cursor = 0
    segments = []
    for card in cards:
        originals = rows[card["word"]]
        if not originals:
            raise ValueError(f'{card["word"]} is missing from the Oxford list')
        wanted = {group["pos"] for group in card["groups"]}
        available = set()
        recorded = {}
        for entry in originals:
            cue = cues[entry["id"]]
            if cue["word"] != entry["word"] or cue["kind"] != "human_recording":
                raise ValueError(f'Invalid original audio entry {entry["id"]}')
            parts = set(re.findall(r"\b[a-z]+\.", entry["pos"]))
            available.update(parts)
            if wanted.intersection(parts):
                recorded.setdefault(tuple(cue["source_ids"]), cue)
        if not recorded:
            raise ValueError(f'{card["word"]} has no original audio for the observed parts of speech')
        start = cursor
        for cue in recorded.values():
            left, speech, right = (round(cue[field] * rate) for field in ("start", "spoken_end", "end"))
            if not left < speech < right:
                raise ValueError(f'Invalid cue boundaries: {cue["id"]}')
            segments.append((left, right))
            spoken_end = cursor + speech - left
            cursor += right - left
        card["originals"] = [{key: entry[key] for key in ("id", "pos", "level", "pdf_page")}
                             for entry in originals]
        card["unseenPos"] = sorted(available.intersection(POS.values()) - wanted)
        card["audio"] = {"start": start / rate, "end": cursor / rate, "spokenEnd": spoken_end / rate,
                         "sourceEntryIds": [cue["id"] for cue in recorded.values()]}
    return OXFORD / timeline["file"], segments


def encode_audio(ffmpeg, original, segments, output):
    count = len(segments)
    split = f"[0:a]asplit={count}" + "".join(f"[c{i}]" for i in range(count))
    trims = [f"[c{i}]atrim=start_sample={start}:end_sample={end},asetpts=PTS-STARTPTS[t{i}]"
             for i, (start, end) in enumerate(segments)]
    join = "".join(f"[t{i}]" for i in range(count)) + f"concat=n={count}:v=0:a=1[out]"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(original),
         "-filter_complex", ";".join([split, *trims, join]), "-map", "[out]",
         "-c:a", "libmp3lame", "-b:a", "64k", str(output)],
        check=True,
    )


def page_html(data):
    shared = OXFORD.parents[1] / "99_维护工具" / "通用"
    text = (HERE / "player.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    replacements = {
        "PLAYER_CSS": (HERE / "player.css").read_text(encoding="utf-8"),
        "PLAYER_JS": (HERE / "player.js").read_text(encoding="utf-8"),
        "TRANSLATION_CSS": (shared / "hover-translations.css").read_text(encoding="utf-8"),
        "TRANSLATION_JS": (shared / "hover-translations.js").read_text(encoding="utf-8"),
        "PLAYBACK_JS": (HERE.parent / "playback.js").read_text(encoding="utf-8"),
        "ORIGINAL": quote(os.path.relpath(OXFORD / "连续听读.html", PRIVATE), safe="/."),
        "AUDIO_CREDIT": quote(os.path.relpath(OXFORD / "来源与许可.md", PRIVATE), safe="/."),
        "AUDIO": quote(AUDIO_FILE.as_posix(), safe="/"),
        "DATA": payload,
    }
    return re.sub(r"__([A-Z_]+)__", lambda marker: replacements[marker[1]], text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdftotext", default="pdftotext")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--wordnet", type=Path, default=PRIVATE / "_cache" / "WordNet-3.0.tar.bz2")
    parser.add_argument("--review", action="store_true", help="Export local contexts for reviewing new annotations")
    args = parser.parse_args()
    lexicon = read_json(HERE / "lexicon.json")
    manifest, sentences = load_corpus(PRIVATE / "来源", args.pdftotext)
    if args.review:
        rows = [f"{word}\t{ref}\t{token}\t{match.group()}\t{sentences[ref].text}"
                for (word, ref, token), match in candidates({w: e["forms"] for w, e in lexicon.items()}, sentences)]
        (PRIVATE / "待核对词形.tsv").write_text("\n".join(sorted(rows)) + "\n", encoding="utf-8")
        print(f"Review contexts: {len(rows)}")
        return

    indexed_text = "\n".join(f"{s.ref}\t{s.lines}\t{s.text}" for s in sentences.values())
    if hashlib.sha256(indexed_text.encode()).hexdigest() != manifest["concordance_sha256"]:
        raise ValueError("Extracted sentence/line positions changed; review the concordance before counting")
    senses, wordnet_license = load_senses(lexicon, args.wordnet)
    cards, evidence = analyse(lexicon, senses, sentences)
    original, segments = audio_plan(cards)
    shown_senses = [s for card in cards for group in card["groups"] for s in group["senses"]]
    data = {
        "schema": 1, "manifest": manifest, "cards": cards, "evidence": evidence,
        "dictionary": {
            "name": "Princeton WordNet 3.0", "terms": "https://wordnet.princeton.edu/license-and-commercial-use",
            "sha256": WORDNET_SHA256,
        },
        "stats": {
            "cards": len(cards), "multiPosCards": sum(len(card["groups"]) > 1 for card in cards),
            "sentences": len(sentences), "tokens": sum(len(s.tokens) for s in sentences.values()),
            "senses": len(shown_senses), "examples": sum(bool(s["example"]) for s in shown_senses),
            "collocations": sum(len(s["collocations"]) for s in shown_senses),
            "repeatedCollocations": sum(c["count"] > 1 for s in shown_senses for c in s["collocations"]),
            "candidateHits": len(evidence), "verified": sum(card["count"] for card in cards),
            "pending": sum(row["status"].startswith("?") for row in evidence.values()),
            "excluded": sum(row["status"].startswith("!") for row in evidence.values()),
            "recordings": len(segments), "durationSeconds": cards[-1]["audio"]["end"],
        },
    }
    if len(cards) != 30 or any(not card["groups"] for card in cards):
        raise ValueError("The pilot must have 30 Oxford headwords with verified senses")
    with TemporaryDirectory(dir=PRIVATE) as tmp:
        staging = Path(tmp)
        encode_audio(args.ffmpeg, original, segments, staging / AUDIO_FILE)
        (staging / "雅思语义试点.html").write_text(page_html(data), encoding="utf-8")
        (staging / "WORDNET-LICENSE.txt").write_bytes(wordnet_license)
        write_json(staging / "统计与出处.json", data)
        (PRIVATE / AUDIO_FILE.parent).mkdir(exist_ok=True)
        for relative in (AUDIO_FILE, "WORDNET-LICENSE.txt", "统计与出处.json", "雅思语义试点.html"):
            (staging / relative).replace(PRIVATE / relative)
    print(json.dumps(data["stats"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
