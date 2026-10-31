"""Check tracked learning links, deep links, media, and shared data after moves."""
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hashlib
import json
import re
import subprocess
import unicodedata

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=None)
def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def anchors(path):
    text = path.read_text(encoding="utf-8")
    found = set(re.findall(r'\bid=["\']([^"\']+)', text))
    used = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.M):
        heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading).lower()
        slug = "".join(c for c in heading if unicodedata.category(c)[0] in "LNM" or c in " _-")
        slug = re.sub(r"\s", "-", slug)
        count = used.get(slug, 0)
        used[slug] = count + 1
        found.add(slug + (f"-{count}" if count else ""))
    return found


def main():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")[:-1]
    published = {ROOT / p for p in tracked}
    errors, links = [], 0
    for name in tracked:
        file = ROOT / name
        if not file.is_file():
            errors.append(f"Missing tracked file: {name}")
            continue
        if file.suffix not in {".md", ".html"}:
            continue
        text = file.read_text(encoding="utf-8")
        text = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", text, flags=re.I)
        text = re.sub(r"^```[^\n]*\n[\s\S]*?^```[^\n]*$", "", text, flags=re.M)
        text = re.sub(r"`[^`\n]+`", "", text)
        hrefs = re.findall(r"\]\(([^)\n]+)\)", text)
        hrefs += re.findall(r'(?:href|src)=["\']([^"\']+)', text)
        for href in hrefs:
            parts = urlsplit(href)
            if parts.scheme or parts.netloc:
                continue
            target = (file.parent / unquote(parts.path)).resolve() if parts.path else file
            links += 1
            if not target.exists() or (target.is_file() and target not in published):
                errors.append(f"{name}: missing published target {href}")
                continue
            fragment = unquote(parts.fragment)
            if not fragment or target.suffix not in {".md", ".html"}:
                continue
            route = re.fullmatch(r"(word|phrase)-(\d+)", fragment)
            if target.suffix == ".html" and route:
                rows = load(target.parent / "data/vocabulary.json")
                valid = int(route[2]) in {r["id"] for r in rows}
            else:
                valid = fragment in anchors(target)
            if not valid:
                errors.append(f"{name}: missing anchor {href}")
    for pack, count, pdf in [
        ("Oxford3000_学习包", 3306, "oxford-3000-by-cefr-level.pdf"),
        ("OxfordPhraseList_学习包", 750, "oxford-phrase-list.pdf"),
    ]:
        folder = ROOT / "01_词汇与短语" / pack
        rows = load(folder / "data/vocabulary.json")
        timeline = load(folder / "data/audio_timeline.json")
        assert len(rows) == len(timeline["entries"]) == count
        assert [r["id"] for r in rows] == [r["id"] for r in timeline["entries"]]
        assert (folder / timeline["file"]).is_file()
        html = (folder / "连续听读.html").read_text(encoding="utf-8")
        payload = re.search(r'<script\b(?=[^>]*\bid="vocabulary")[^>]*>([\s\S]*?)</script>', html)[1]
        assert json.loads(payload) == rows, pack
        metadata = load(folder / "data/pdf_metadata.json")
        digest = hashlib.sha256((ROOT / "06_原始资料/Oxford词表" / pdf).read_bytes()).hexdigest()
        expected = metadata.get("source_sha256") or metadata.get("sha256")
        if expected:
            assert digest == expected, pack
    dialogue = ROOT / "03_日常对话/日常对话母体_120句/data/母句.json"
    for source in load(dialogue)["sourceFiles"].values():
        assert (dialogue.parent / source).resolve() in published, source
    if errors:
        raise AssertionError("\n".join(errors[:30]) + f"\nTotal: {len(errors)}")
    print(f"REPOSITORY_OK: {len(tracked)} files, {links} local links; Oxford data, media and dialogue sources verified")


if __name__ == "__main__":
    main()
