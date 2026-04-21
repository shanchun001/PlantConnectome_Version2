"""
Token-level alias rewrite for entity names that contain a known gene
alias as a word. Complements apply_alias_dict.py, which only handles
the bare alias + "protein"/"gene" suffixes.

Example rewrites:
  "NPR1 protein levels"
      -> "(ATNPR1, NIM1, NPR1, SAI1, AT1G64280) protein levels"
  "NPR1 (Nonexpressor pathogenesis-related genes 1)"
      -> "(ATNPR1, NIM1, NPR1, SAI1, AT1G64280) (Nonexpressor pathogenesis-related genes 1)"
  "NON EXPRESSOR OF PR GENES1 (NPR1)"
      -> "NON EXPRESSOR OF PR GENES1 (ATNPR1, NIM1, NPR1, SAI1, AT1G64280)"
  "overexpression of cesa1"
      -> "overexpression of (ATCESA1, CESA1, RSW1, AT4G32410, ANY1)"

Rules:
  * Tokenize on any non-word character except "-" (preserves hyphens).
  * A token qualifies if its bare lowercase form is in the alias dict.
  * If exactly 1 token qualifies, replace it in place with "(CANONICAL)".
  * If >1 token qualifies, we leave the name unchanged but still set the
    category to "Gene Identifier" (already done by the tagging pass).
  * Skip docs whose entity already starts with "(" — those were already
    canonicalized by apply_alias_dict.py.
  * Collapse accidental "((" / "))" from a match living inside parens.

Usage:
    python rewrite_alias_tokens.py
"""
import json
import os
import re
import time
from pymongo import MongoClient, UpdateOne

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
ALIAS_JSON = "utils/alias_to_stringDict.json"
BATCH_SIZE = 5000

client = MongoClient(MONGO_URI)
db = client["PlantConnectome"]
col = db["all_dic"]

print(f"Loading {ALIAS_JSON}...")
with open(ALIAS_JSON) as f:
    alias_dict = json.load(f)
print(f"  {len(alias_dict):,} aliases loaded")

# Token definition: runs of word chars OR single non-word chars preserved
# so we can reassemble the string. We treat "-" as a word-joining char so
# "npr1-1" is one token (and won't match "npr1" alone).
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]+|[^A-Za-z0-9_-]+")


def rewrite(name):
    """
    Return (new_display, new_lower) if at least one token matches an
    alias and exactly one qualifies. Returns (None, None) otherwise.
    """
    if not name:
        return None, None
    if name.strip().startswith("("):
        return None, None  # already canonicalized

    parts = TOKEN_RE.findall(name)
    match_indices = []
    for i, p in enumerate(parts):
        pl = p.lower()
        if pl and pl in alias_dict:
            match_indices.append(i)

    if len(match_indices) != 1:
        return None, None

    idx = match_indices[0]
    canon = alias_dict[parts[idx].lower()]
    parts[idx] = f"({canon})"
    new_display = "".join(parts)

    # Collapse accidental double parens like "((CANON))" -> "(CANON)"
    new_display = new_display.replace("((", "(").replace("))", ")")
    return new_display, new_display.lower()


t_start = time.time()
print("\nScanning all_dic for token-level rewrites...")

# Only docs that have an alias token to consider — same tagging query but
# broader (entity1/entity2 candidates where category was set to Gene
# Identifier by the tagger). We can't trust that marker entirely since it
# was set by the lenient pre-exclusion pass, so re-scan everything whose
# entity_lower doesn't already start with '('.
cursor = col.find(
    {
        "$or": [
            {"entity1_lower": {"$not": {"$regex": r"^\("}}},
            {"entity2_lower": {"$not": {"$regex": r"^\("}}},
        ]
    },
    {
        "_id": 1,
        "entity1": 1, "entity1_lower": 1,
        "entity2": 1, "entity2_lower": 1,
    },
    no_cursor_timeout=True,
)

ops1 = []
ops2 = []
rewritten_e1 = 0
rewritten_e2 = 0
processed = 0

try:
    for doc in cursor:
        # entity1
        e1 = doc.get("entity1") or ""
        if not e1.strip().startswith("("):
            new_disp, new_lower = rewrite(e1)
            if new_disp and new_disp != e1:
                ops1.append(UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "entity1": new_disp,
                        "entity1_lower": new_lower,
                        "entity1category": "Gene Identifier",
                    }}
                ))
                rewritten_e1 += 1

        # entity2
        e2 = doc.get("entity2") or ""
        if not e2.strip().startswith("("):
            new_disp, new_lower = rewrite(e2)
            if new_disp and new_disp != e2:
                ops2.append(UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "entity2": new_disp,
                        "entity2_lower": new_lower,
                        "entity2category": "Gene Identifier",
                    }}
                ))
                rewritten_e2 += 1

        if len(ops1) >= BATCH_SIZE:
            col.bulk_write(ops1, ordered=False)
            ops1 = []
        if len(ops2) >= BATCH_SIZE:
            col.bulk_write(ops2, ordered=False)
            ops2 = []

        processed += 1
        if processed % 500000 == 0:
            elapsed = time.time() - t_start
            print(
                f"  processed {processed:>10,}  "
                f"e1-rewrites={rewritten_e1:>9,}  e2-rewrites={rewritten_e2:>9,}  "
                f"({elapsed:.0f}s)"
            )

    if ops1:
        col.bulk_write(ops1, ordered=False)
    if ops2:
        col.bulk_write(ops2, ordered=False)
finally:
    cursor.close()

print(
    f"\nDone: {rewritten_e1:,} entity1 + {rewritten_e2:,} entity2 "
    f"documents rewritten in {time.time()-t_start:.0f}s"
)

# Rebuild entity_lookup
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
