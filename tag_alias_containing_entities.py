"""
Bulk-tag every entity whose name contains a known gene alias as a
whole word, setting its category to "Gene Identifier".

This complements apply_alias_dict.py:
  - apply_alias_dict.py only rewrites entities whose whole name is an
    alias (optionally with a protein/gene suffix).
  - This script leaves the name + type untouched but updates the
    category for entities like "NPR1 mutant", "CESA1-1 plants",
    "overexpression of NPR1", "NPR1/NPR3/NPR4", etc.

Usage:
    python tag_alias_containing_entities.py
"""
import json
import os
import re
import time
from pymongo import MongoClient, UpdateOne

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
ALIAS_JSON = "utils/alias_to_stringDict.json"
BATCH_SIZE = 10000

client = MongoClient(MONGO_URI)
db = client["PlantConnectome"]
col = db["all_dic"]

print(f"Loading {ALIAS_JSON}...")
with open(ALIAS_JSON) as f:
    alias_dict = json.load(f)
aliases = set(alias_dict.keys())
print(f"  {len(aliases):,} aliases loaded")

# Split on any run of non-alphanumeric chars. Keeps tokens like "npr1",
# "at1g64280", "cesa1". Strips punctuation (parens, commas, dashes, slashes).
SPLIT_RE = re.compile(r"[^a-z0-9]+")


def tokens(s):
    if not s:
        return ()
    return (t for t in SPLIT_RE.split(s) if t)


def has_alias(lower_name):
    # Short-circuit: first matching alias token is enough
    for t in tokens(lower_name):
        if t in aliases:
            return True
    return False


t_start = time.time()
print("\nScanning all_dic...")

total = col.estimated_document_count()
ops1 = []
ops2 = []
flagged_e1 = 0
flagged_e2 = 0
processed = 0

cursor = col.find(
    {},
    {
        "_id": 1,
        "entity1_lower": 1,
        "entity2_lower": 1,
        "entity1category": 1,
        "entity2category": 1,
    },
    no_cursor_timeout=True,
)

try:
    for doc in cursor:
        e1l = doc.get("entity1_lower", "") or ""
        e2l = doc.get("entity2_lower", "") or ""
        cat1 = (doc.get("entity1category", "") or "").strip()
        cat2 = (doc.get("entity2category", "") or "").strip()

        if cat1 != "Gene Identifier" and has_alias(e1l):
            ops1.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"entity1category": "Gene Identifier"}}))
            flagged_e1 += 1
        if cat2 != "Gene Identifier" and has_alias(e2l):
            ops2.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"entity2category": "Gene Identifier"}}))
            flagged_e2 += 1

        if len(ops1) >= BATCH_SIZE:
            col.bulk_write(ops1, ordered=False)
            ops1 = []
        if len(ops2) >= BATCH_SIZE:
            col.bulk_write(ops2, ordered=False)
            ops2 = []

        processed += 1
        if processed % 500000 == 0:
            elapsed = time.time() - t_start
            rate = processed / elapsed if elapsed else 0
            eta = (total - processed) / rate if rate else 0
            print(
                f"  processed {processed:>10,}/{total:,}  "
                f"e1-flagged={flagged_e1:>9,}  e2-flagged={flagged_e2:>9,}  "
                f"({elapsed:.0f}s, eta {eta:.0f}s)"
            )

    # Flush
    if ops1:
        col.bulk_write(ops1, ordered=False)
    if ops2:
        col.bulk_write(ops2, ordered=False)
finally:
    cursor.close()

print(
    f"\nScan done in {time.time()-t_start:.0f}s: "
    f"{flagged_e1:,} entity1 + {flagged_e2:,} entity2 categories updated"
)

# ── Rebuild entity_lookup so preview reflects the new category ──────────
from pymongo import TEXT

print("\nRebuilding entity_lookup...")
t2 = time.time()

col.aggregate([
    {"$group": {
        "_id": "$entity1_lower",
        "name": {"$first": "$entity1"},
        "type": {"$first": "$entity1type"},
        "category": {"$first": "$entity1category"},
        "count": {"$sum": 1}
    }},
    {"$out": "entity_lookup_e1"}
], allowDiskUse=True)

col.aggregate([
    {"$group": {
        "_id": "$entity2_lower",
        "name": {"$first": "$entity2"},
        "type": {"$first": "$entity2type"},
        "category": {"$first": "$entity2category"},
        "count": {"$sum": 1}
    }},
    {"$out": "entity_lookup_e2"}
], allowDiskUse=True)

db.drop_collection("entity_lookup")
db["entity_lookup_e1"].aggregate([
    {"$unionWith": {"coll": "entity_lookup_e2"}},
    {"$group": {
        "_id": "$_id",
        "name": {"$first": "$name"},
        "type": {"$first": "$type"},
        "category": {"$first": "$category"},
        "count": {"$sum": "$count"}
    }},
    {"$out": "entity_lookup"}
], allowDiskUse=True)

db["entity_lookup"].create_index([("_id", TEXT)], name="text_lower")
db["entity_lookup"].create_index("count")
db.drop_collection("entity_lookup_e1")
db.drop_collection("entity_lookup_e2")
print(f"  entity_lookup rebuilt: {db['entity_lookup'].count_documents({}):,} entities ({time.time()-t2:.0f}s)")

print(f"\nAll done in {time.time()-t_start:.0f}s")
