"""
Apply alias resolution to the PlantConnectome MongoDB all_dic collection.

For every entity (entity1 and entity2) that matches:
  - an exact alias (e.g. "NPR1")
  - an alias + suffix pattern ("NPR1 protein", "NPR1 gene", etc.)
  - an embedded AGI code (AT1G01380)

...rewrite the entity to the canonical "(ALIAS1, ALIAS2, AGI)" form and set
the entity type to "gene identifier". Also extract the AGI code into a
dedicated source_AGI / target_AGI field.

Usage:
    python apply_alias_dict.py
"""
import json
import os
import re
import time
from pymongo import MongoClient, UpdateMany

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["PlantConnectome"]
col = db["all_dic"]

ALIAS_JSON = "utils/alias_to_stringDict.json"

SUFFIXES = ["", " protein", " protein(s)", " proteins", " gene", " gene(s)", " genes"]
AGI_RE = re.compile(r"AT[1-5CM]G\d{5}", re.IGNORECASE)

print(f"Loading {ALIAS_JSON}...")
with open(ALIAS_JSON) as f:
    alias_dict = json.load(f)
print(f"  {len(alias_dict)} aliases loaded")

t_start = time.time()


def canonical_string(canonical):
    """Given 'ETC1, AT1G01380', return '(ETC1, AT1G01380)'."""
    return f"({canonical})"


def extract_agi(canonical):
    """Extract first AGI from canonical string, or return ''."""
    m = AGI_RE.search(canonical)
    return m.group(0).upper() if m else ""


# ── Step 1: Exact + suffix matches via targeted update_many ──────────────
# For each (alias, suffix) pair, only the alias prefix is replaced with the
# canonical "(...)" form; the suffix is preserved.
#   "NPR1"              -> "(ATNPR1, NIM1, NPR1, SAI1, AT1G64280)"
#   "NPR1 protein"      -> "(ATNPR1, NIM1, NPR1, SAI1, AT1G64280) protein"
#   "NPR1 gene(s)"      -> "(ATNPR1, NIM1, NPR1, SAI1, AT1G64280) gene(s)"

print("\nStep 1: Applying exact + suffix alias matches...")
alias_items = sorted(alias_dict.items())
total_aliases = len(alias_items)

stats = {"entity1_updated": 0, "entity2_updated": 0, "aliases_processed": 0}

for i, (alias_lower, canonical) in enumerate(alias_items, 1):
    canon_str = canonical_string(canonical)
    agi = extract_agi(canonical)

    for suf in SUFFIXES:
        old_lower = alias_lower + suf       # e.g. "npr1 protein"
        new_display = canon_str + suf       # "(...) protein"
        new_lower = new_display.lower()

        # Skip if the target already equals the display (avoid redundant writes)
        # Update entity1
        set_e1 = {
            "entity1": new_display,
            "entity1_lower": new_lower,
            "entity1type": "gene identifier",
            "entity1category": "Gene Identifier",
        }
        if agi:
            set_e1["source_AGI"] = agi
        r1 = col.update_many(
            {"entity1_lower": old_lower, "entity1": {"$ne": new_display}},
            {"$set": set_e1}
        )
        stats["entity1_updated"] += r1.modified_count

        # Update entity2
        set_e2 = {
            "entity2": new_display,
            "entity2_lower": new_lower,
            "entity2type": "gene identifier",
            "entity2category": "Gene Identifier",
        }
        if agi:
            set_e2["target_AGI"] = agi
        r2 = col.update_many(
            {"entity2_lower": old_lower, "entity2": {"$ne": new_display}},
            {"$set": set_e2}
        )
        stats["entity2_updated"] += r2.modified_count

    stats["aliases_processed"] = i
    if i % 1000 == 0 or i == total_aliases:
        elapsed = time.time() - t_start
        rate = i / elapsed
        eta = (total_aliases - i) / rate if rate > 0 else 0
        print(
            f"  {i:>6}/{total_aliases}  "
            f"e1={stats['entity1_updated']:>9,}  "
            f"e2={stats['entity2_updated']:>9,}  "
            f"({elapsed:.0f}s, eta {eta:.0f}s)"
        )

print(f"\nStep 1 done: {stats['entity1_updated']:,} entity1 + "
      f"{stats['entity2_updated']:,} entity2 documents updated "
      f"({time.time()-t_start:.0f}s)")

# ── Step 2: Rebuild entity_lookup to reflect renames ─────────────────────
print("\nStep 2: Rebuilding entity_lookup with new canonical names...")
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
print(f"  entity1 side done ({time.time()-t2:.0f}s)")

t3 = time.time()
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
print(f"  entity2 side done ({time.time()-t3:.0f}s)")

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

from pymongo import TEXT
db["entity_lookup"].create_index([("_id", TEXT)], name="text_lower")
db["entity_lookup"].create_index("count")
db.drop_collection("entity_lookup_e1")
db.drop_collection("entity_lookup_e2")
print(f"  entity_lookup rebuilt: {db['entity_lookup'].count_documents({}):,} entities")

print(f"\nAll done in {time.time()-t_start:.0f}s")
