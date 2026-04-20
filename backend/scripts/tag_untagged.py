"""Standalone tagger — classifies records that still have fewer than 2 tags.

Runs against MongoDB directly (bypasses the FastAPI event loop) so the live
API stays responsive while we catch up on tagging 1,000+ records.

Usage:
    python -m scripts.tag_untagged            # default concurrency 4
    python -m scripts.tag_untagged 6          # with custom concurrency
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import List

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

from businesses.categorizer import tag_records_batch  # noqa: E402


async def main(concurrency: int = 4) -> None:
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "eilatush")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    docs: List[dict] = []
    async for d in db.businesses.find(
        {
            "$or": [
                {"tags": {"$exists": False}},
                {"tags": {"$size": 0}},
            ]
        },
        {"_id": 0, "id": 1, "name": 1, "subtitle": 1, "description": 1,
         "category_hint": 1, "type": 1, "tags": 1},
    ):
        docs.append(d)

    print(f"to tag: {len(docs)}", flush=True)
    if not docs:
        return

    batch_size = 40
    for start in range(0, len(docs), batch_size):
        batch = docs[start : start + batch_size]
        try:
            tag_lists = await tag_records_batch(batch, concurrency=concurrency)
        except Exception as e:
            print(f"batch {start} failed: {e}", flush=True)
            continue
        for r, tags in zip(batch, tag_lists):
            if not tags:
                continue
            merged = list(dict.fromkeys(tags + (r.get("tags") or [])))[:3]
            try:
                await db.businesses.update_one(
                    {"id": r["id"]}, {"$set": {"tags": merged}}
                )
            except Exception as e:
                print(f"update failed for {r.get('id')}: {e}", flush=True)
        done = start + len(batch)
        print(f"progress: {done}/{len(docs)}", flush=True)

    print("tagging done", flush=True)


if __name__ == "__main__":
    conc = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    asyncio.run(main(conc))
