"""Find licensed English human recordings, retaining per-file attribution."""
from __future__ import annotations
import argparse
import asyncio
from collections import defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import time
import urllib.parse

REPOSITORY=Path(__file__).resolve().parents[2]
ROOT=REPOSITORY/'01_词汇与短语'/'Oxford3000_学习包'
CACHE = ROOT / "_cache"
sys.path.insert(0, str(CACHE / "python"))
import aiohttp

sys.stdout.reconfigure(encoding="utf-8")
UA = "EnglishLearningPersonal/1.0 (+https://github.com/Max-47-S/English_Learning)"
ALIASES = {
    "aeroplane": "airplane", "analyse": "analyze", "behaviour": "behavior",
    "centre": "center", "colour": "color", "coloured": "colored",
    "defence": "defense", "dialogue": "dialog", "favour": "favor",
    "favourite": "favorite", "grey": "gray", "honour": "honor",
    "humour": "humor", "jewellery": "jewelry", "kilometre": "kilometer",
    "labour": "labor", "licence": "license", "metre": "meter",
    "neighbour": "neighbor", "neighbourhood": "neighborhood",
    "offence": "offense", "organise": "organize", "organisation": "organization",
    "practise": "practice", "programme": "program", "theatre": "theater",
    "traveller": "traveler", "tyre": "tire", "Mr": "mister", "Mrs": "missus",
    "OK": "okay", "o’clock": "o'clock",
}
HETERONYMS = {
    "close", "live", "lead", "record", "present", "object", "subject", "conduct",
    "content", "minute", "excuse", "refuse", "desert", "tear", "wind", "row",
    "use", "house", "increase", "decrease", "import", "export", "permit",
    "produce", "project", "progress", "protest", "transfer", "transport",
    "insult", "suspect", "survey", "conflict", "contrast", "convert", "perfect",
    "separate", "estimate", "graduate", "associate", "deliberate", "appropriate",
}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plain(value):
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


class Fetcher:
    def __init__(self, proxy, manifest_name="human_audio_sources.json"):
        self.proxy = proxy
        self.sem = asyncio.Semaphore(4)
        self.sources = defaultdict(list)
        self.manifest_name = manifest_name
        self.metadata_cache = CACHE / "commons_metadata"
        self.metadata_cache.mkdir(parents=True, exist_ok=True)

    async def json(self, session, host, query):
        url = host + "?" + urllib.parse.urlencode(query)
        cache = self.metadata_cache / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        async with self.sem:
            for attempt in range(4):
                try:
                    async with session.get(url, proxy=self.proxy, timeout=aiohttp.ClientTimeout(total=50)) as response:
                        if response.status in {429, 500, 502, 503, 504}:
                            await asyncio.sleep(2 ** (attempt + 1))
                            continue
                        response.raise_for_status()
                        data = await response.json(content_type=None)
                        if "error" in data:
                            raise RuntimeError(data["error"])
                        save(cache, data)
                        return data
                except Exception as exc:
                    if attempt == 3:
                        print("METADATA_ERROR", str(exc)[:180], flush=True)
                        return {}
                    await asyncio.sleep(attempt + 1)
        return {}

    async def titles(self, session, mapping, label):
        titles = list(mapping)
        title_lookup = defaultdict(list)
        for mapped_title, mapped_words in mapping.items():
            for mapped_word in mapped_words:
                if mapped_word not in title_lookup[mapped_title.casefold()]:
                    title_lookup[mapped_title.casefold()].append(mapped_word)
        batches = [titles[i:i+50] for i in range(0, len(titles), 50)]
        completed = 0
        async def batch(batch_titles):
            nonlocal completed
            data = await self.json(session, "https://commons.wikimedia.org/w/api.php", {
                "action": "query", "format": "json", "titles": "|".join(batch_titles),
                "prop": "imageinfo", "iiprop": "url|extmetadata",
            })
            for page in data.get("query", {}).get("pages", {}).values():
                infos = page.get("imageinfo")
                if not infos:
                    continue
                info = infos[0]
                meta = info.get("extmetadata", {})
                get = lambda key: plain(meta.get(key, {}).get("value", ""))
                license_name = get("LicenseShortName")
                if not any(x in license_name.lower() for x in ["cc by", "cc0", "public domain"]):
                    continue
                description = get("ImageDescription")
                if re.search(r"text.to.speech|speech synthesis|espeak|synthetic voice|AI.generated", description, re.I):
                    continue
                title = page["title"]
                for word in title_lookup.get(title.casefold(), []):
                    item = {
                        "title": title,
                        "url": info["url"].split("?")[0],
                        "page_url": info.get("descriptionurl", "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))),
                        "artist": get("Artist"), "artist_html": meta.get("Artist", {}).get("value", ""),
                        "license": license_name, "license_url": get("LicenseUrl"),
                        "description": description, "credit": get("Credit"),
                        "kind": "human_recording",
                    }
                    if item["url"] not in {r["url"] for r in self.sources[word]}:
                        self.sources[word].append(item)
            completed += 1
            if completed % 10 == 0 or completed == len(batches):
                print("METADATA", label, f"{completed}/{len(batches)}", "covered_words", len(self.sources), flush=True)
        await asyncio.gather(*(batch(b) for b in batches))

    async def discover_wiktionary(self, session, words):
        batches = [words[i:i+30] for i in range(0, len(words), 30)]
        mapping = defaultdict(list)
        for n, group in enumerate(batches, 1):
            data = await self.json(session, "https://en.wiktionary.org/w/api.php", {
                "action": "query", "format": "json", "titles": "|".join(group),
                "prop": "images", "imlimit": "max", "redirects": "1",
            })
            for page in data.get("query", {}).get("pages", {}).values():
                word = page["title"].replace("’", "'").lower()
                for image in page.get("images", []):
                    title = image["title"]
                    filename = title.removeprefix("File:")
                    if not re.search(r"\.(ogg|oga|wav|mp3)$", filename, re.I):
                        continue
                    if not re.match(r"(?:En[-_]|LL-Q1860\s*\(eng\))", filename, re.I):
                        continue
                    if word not in mapping[title]:
                        mapping[title].append(word)
            if n % 5 == 0 or n == len(batches):
                print("WIKTIONARY_DISCOVERY", f"{n}/{len(batches)}", "files", len(mapping), flush=True)
        await self.titles(session, mapping, "wiktionary")

    async def downloads(self, session):
        folder = CACHE / "human_audio"
        folder.mkdir(parents=True, exist_ok=True)
        distinct = {}
        for rows in self.sources.values():
            for row in rows:
                suffix = Path(urllib.parse.urlparse(row["url"]).path).suffix
                row["cache_file"] = str((folder / (hashlib.sha256(row["url"].encode()).hexdigest()[:20] + suffix)).relative_to(ROOT))
                distinct.setdefault(row["url"], row)
        sem = asyncio.Semaphore(2)
        throttle = asyncio.Lock()
        next_request = 0.0
        completed = 0
        failures = []
        async def one(row):
            nonlocal completed, next_request
            destination = ROOT / row["cache_file"]
            if not destination.exists() or destination.stat().st_size < 100:
                async with sem:
                    error = 'Retry limit reached'
                    success = False
                    for attempt in range(7):
                        try:
                            async with throttle:
                                await asyncio.sleep(max(0, next_request - time.monotonic()))
                                next_request = time.monotonic() + 0.6
                            async with session.get(row["url"], proxy=self.proxy, timeout=aiohttp.ClientTimeout(total=60)) as response:
                                if response.status in {429, 500, 502, 503, 504}:
                                    delay = max(float(response.headers.get('Retry-After','0')), min(60, 2 ** (attempt + 2)))
                                    next_request = max(next_request, time.monotonic() + delay)
                                    error = f'HTTP {response.status}; retry-after {delay}s'
                                    continue
                                response.raise_for_status()
                                data = await response.read()
                                if len(data) < 100:
                                    raise ValueError("Empty recording")
                                destination.write_bytes(data)
                                success = True
                                break
                        except Exception as exc:
                            error = str(exc)
                            await asyncio.sleep(min(30, attempt + 2))
                    if not success:
                        failures.append({"url": row["url"], "error": error})
                        print('AUDIO_FAILURE', row.get('spoken_word',row.get('title')),error,flush=True)
                        save(CACHE / "audio_download_failures.json", failures)
            completed += 1
            if completed % 25 == 0 or completed == len(distinct):
                print("AUDIO_DOWNLOAD", f"{completed}/{len(distinct)}", "failures", len(failures), flush=True)
        await asyncio.gather(*(one(row) for row in distinct.values()))
        save(CACHE / "audio_download_failures.json", failures)

    async def run(self, metadata_only=False, download_only=False):
        entries = json.loads((ROOT / "data/pdf_entries.json").read_text(encoding="utf-8"))
        spellings = {e["lookup"]: e["word"].replace("’", "'") for e in entries}
        spellings.pop("a, an", None)
        spellings.update({"a": "a", "an": "an"})
        manifest = ROOT / "data" / self.manifest_name
        if not manifest.exists() and self.manifest_name != "human_audio_sources.json":
            previous = ROOT / "data/human_audio_sources.json"
            if previous.exists():
                self.sources.update(json.loads(previous.read_text(encoding="utf-8")))
        if manifest.exists():
            self.sources.update(json.loads(manifest.read_text(encoding="utf-8")))
        connector = aiohttp.TCPConnector(limit=18)
        async with aiohttp.ClientSession(headers={"User-Agent": UA}, connector=connector) as session:
            if download_only:
                await self.downloads(session)
                save(manifest, dict(self.sources))
                return
            for prefix in ["En-us-", "En-uk-", "En-"]:
                mapping = defaultdict(list)
                for word, display in spellings.items():
                    if word in self.sources:
                        continue
                    mapping["File:" + prefix + display + ".ogg"].append(word)
                await self.titles(session, mapping, prefix)
                save(manifest, dict(self.sources))
            mapping = defaultdict(list)
            for word, display in spellings.items():
                if word in self.sources:
                    continue
                for variant in {display.lower(), ALIASES.get(display, ALIASES.get(word, display.lower()))}:
                    for prefix in ["En-us-", "En-uk-"]:
                        mapping["File:" + prefix + variant + ".ogg"].append(word)
            await self.titles(session, mapping, "spelling_variants")
            missing = [w for w in spellings if w not in self.sources]
            discover = sorted(set(missing) | (HETERONYMS & spellings.keys()))
            await self.discover_wiktionary(session, discover)
            save(manifest, dict(self.sources))
            print("HUMAN_METADATA_COMPLETE", len(self.sources), "/", len(spellings), flush=True)
            print("MISSING_HUMAN", [w for w in spellings if w not in self.sources], flush=True)
            if not metadata_only:
                await self.downloads(session)
                save(manifest, dict(self.sources))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy")
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--manifest-name", default="human_audio_sources.json")
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(Fetcher(args.proxy, args.manifest_name).run(args.metadata_only, args.download_only))
