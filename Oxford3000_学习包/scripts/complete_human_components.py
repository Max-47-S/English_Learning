"""Fetch a small set of human-spoken letter/word components for abbreviations."""
from __future__ import annotations
import argparse
import asyncio
from collections import defaultdict
import json
from pathlib import Path
import sys

from fetch_human_audio import Fetcher, ROOT, CACHE, UA, save
sys.path.insert(0, str(CACHE / "python"))
import aiohttp


async def main(proxy):
    fetcher = Fetcher(proxy, "human_audio_components.json")
    manifest = ROOT / "data/human_audio_components.json"
    if manifest.exists():
        fetcher.sources.update(json.loads(manifest.read_text(encoding="utf-8")))
    mapping = defaultdict(list)
    for label, variants in {"letter_c":["C","c"], "letter_d":["D","d"], "letter_v":["V","v"], "letter_i":["I","i"], "letter_t":["T","t"], "per":["per"], "ought":["ought"], "percent":["percent"]}.items():
        for variant in variants:
            for prefix in ["En-us-", "En-uk-", "En-"]:
                mapping["File:"+prefix+variant+".ogg"].append(label)
    async with aiohttp.ClientSession(headers={"User-Agent":UA}, connector=aiohttp.TCPConnector(limit=10)) as session:
        await fetcher.titles(session, mapping, "human_components")
        save(manifest, dict(fetcher.sources))
        await fetcher.downloads(session)
        save(manifest, dict(fetcher.sources))
    print("COMPONENTS_FOUND", list(fetcher.sources), flush=True)


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--proxy")
    args=p.parse_args()
    asyncio.run(main(args.proxy))
