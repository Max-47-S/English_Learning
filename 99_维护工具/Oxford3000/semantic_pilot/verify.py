"""Recheck the generated pilot against local source PDFs and original audio."""

import argparse
import math
import subprocess
from array import array
from collections import Counter

from build import AUDIO_FILE, write_json
from corpus import HERE, OXFORD, PRIVATE, candidates, load_corpus, read_json, sha256


def verify_text(data, pdftotext):
    manifest, sentences = load_corpus(PRIVATE / "来源", pdftotext)
    assert manifest == data["manifest"]
    evidence = data["evidence"]
    lexicon = read_json(HERE / "lexicon.json")
    matches = dict(candidates({word: entry["forms"] for word, entry in lexicon.items()}, sentences))
    assert len(matches) == len(evidence)
    for row in evidence.values():
        sentence = sentences[row["sentence"]]
        match = matches[row["word"], row["sentence"], row["token"]]
        assert sentence.source == row["source"]
        assert sentence.lines == tuple(map(tuple, row["lines"]))
        assert (match.start(), match.end(), match.group()) == (row["start"], row["end"], row["form"])
        for span in row.get("collocations", {}).values():
            assert span["start"] <= match.start() < match.end() <= span["end"]
            assert sentence.text[span["start"]:span["end"]] == span["text"]

    verified = Counter()
    total_examples = 0
    for card in data["cards"]:
        assert card["count"] == sum(group["count"] for group in card["groups"])
        for group in card["groups"]:
            counts = [sense["count"] for sense in group["senses"]]
            assert counts == sorted(counts, reverse=True) and group["count"] == sum(counts)
            for sense in group["senses"]:
                assert sense["count"] == len(sense["evidence"])
                assert all(evidence[i]["sense"] == sense["id"] for i in sense["evidence"])
                verified.update(sense["evidence"])
                collocations = sense["collocations"]
                assert collocations == sorted(collocations, key=lambda item: (-item["count"], item["key"]))
                actual = Counter(key for i in sense["evidence"] for key in evidence[i]["collocations"])
                assert actual == {item["key"]: item["count"] for item in collocations}
                for item in collocations:
                    assert item["evidence"] == [
                        i for i in sense["evidence"] if item["key"] in evidence[i]["collocations"]
                    ]
                example = sense["example"]
                top = collocations[0]
                row = evidence[example["evidence"]]
                sentence = sentences[row["sentence"]]
                span = row["collocations"][top["key"]]
                assert example["evidence"] in top["evidence"] and sentence.complete
                assert example["text"] == sentence.text
                assert example["text"][example["start"]:example["end"]] == span["text"]
                total_examples += 1
    assert verified == {key: 1 for key, row in evidence.items() if row["status"] == "verified"}
    cards = {card["word"]: card for card in data["cards"]}
    assert len(data["cards"]) == len(cards) == 30
    assert [g["count"] for g in cards["work"]["groups"]] == [10, 2]
    assert [s["count"] for s in cards["level"]["groups"][0]["senses"]] == [4, 3]
    life = next(s for s in cards["life"]["groups"][0]["senses"] if s["id"] == "life.living")
    assert life["collocations"][0]["forms"] == ["everyday life", "everyday lives"]
    assert life["collocations"][0]["count"] == 2
    assert evidence["time/L07.10.02/19"]["status"] == "!same-phrase"
    assert evidence["use/L07.04.01/8"]["status"] == "!different-lexeme"
    assert evidence["work/R03.01.02/12"]["status"] == "!proper-name"
    return {"occurrences": len(matches), "verified": len(verified), "completeExamples": total_examples}


def verify_audio(data, ffmpeg):
    timeline = read_json(OXFORD / "data" / "audio_timeline.json")
    sample_rate = timeline["sample_rate"]
    original = OXFORD / timeline["file"]
    cues = {cue["id"]: cue for cue in timeline["entries"]}
    prefix = [ffmpeg, "-nostdin", "-v", "error", "-i"]
    suffix = ["-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-"]
    pilot = subprocess.check_output([*prefix, str(PRIVATE / AUDIO_FILE), *suffix])
    positions = []
    cursor = 0
    for card in data["cards"]:
        assert round(card["audio"]["start"] * sample_rate) == cursor
        for source_id in card["audio"]["sourceEntryIds"]:
            cue = cues[source_id]
            assert cue["word"].lower() == card["word"]
            first, spoken, last = [round(cue[field] * sample_rate) for field in ("start", "spoken_end", "end")]
            positions.append((first, spoken - first, cursor))
            cursor += last - first
        assert round(card["audio"]["end"] * sample_rate) == cursor
    assert abs(len(pilot) // 2 - cursor) <= sample_rate // 100
    assert len(positions) == data["stats"]["recordings"]
    correlations = []
    with subprocess.Popen([*prefix, str(original), *suffix], stdout=subprocess.PIPE) as process:
        offset = 0
        for first, length, target in sorted(positions):
            skipped = (first - offset) * 2
            assert skipped >= 0
            while skipped:
                chunk = process.stdout.read(min(skipped, 1024 * 1024))
                assert chunk, "Original MP3 ended before the cue"
                skipped -= len(chunk)
            original_clip = array("h", process.stdout.read(length * 2))
            pilot_clip = array("h", pilot[target * 2:(target + length) * 2])
            assert len(original_clip) == len(pilot_clip) == length
            numerator = sum(a * b for a, b in zip(original_clip, pilot_clip))
            norm = math.sqrt(sum(a * a for a in original_clip) * sum(b * b for b in pilot_clip))
            correlations.append(numerator / norm)
            offset = first + length
        while process.stdout.read(1024 * 1024):
            pass
        assert process.wait() == 0
    assert min(correlations) >= .98, correlations
    return {"verifiedClips": len(correlations), "minSignalCorrelation": round(min(correlations), 6),
            "decodedSeconds": len(pilot) / 2 / sample_rate, "originalAudioSha256": sha256(original)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdftotext", default="pdftotext")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    data = read_json(PRIVATE / "统计与出处.json")
    report = {"text": verify_text(data, args.pdftotext), "audio": verify_audio(data, args.ffmpeg)}
    write_json(PRIVATE / "数据与音轨校验.json", report)
    print(report)


if __name__ == "__main__":
    main()
