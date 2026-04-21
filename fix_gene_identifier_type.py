"""
Correct the entity1type / entity2type on docs that apply_alias_dict.py
wrongly set to "gene identifier". "Gene Identifier" belongs in the
CATEGORY axis, not the TYPE axis.

Infer the correct type from the canonical suffix:
    "(CANON)"            -> type "gene"    (bare alias, originally a gene symbol)
    "(CANON) gene"       -> type "gene"
    "(CANON) genes"      -> type "genes"
    "(CANON) gene(s)"    -> type "gene(s)"
    "(CANON) protein"    -> type "protein"
    "(CANON) proteins"   -> type "proteins"
    "(CANON) protein(s)" -> type "protein(s)"

Usage:
    python fix_gene_identifier_type.py
"""
import os
import re
import time
from pymongo import MongoClient, UpdateMany

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["PlantConnectome"]
col = db["all_dic"]

SUFFIX_TO_TYPE = [
    (" protein(s)", "protein(s)"),
    (" proteins", "proteins"),
    (" protein", "protein"),
    (" gene(s)", "gene(s)"),
    (" genes", "genes"),
    (" gene", "gene"),
]

t_start = time.time()

# Entity-1 side
print("entity1: restoring types on canonical gene-identifier docs...")
# Bare canonical -> "gene"
r = col.update_many(
    {
        "entity1type": "gene identifier",
        "entity1_lower": {"$regex": r"^\([^)]*\)$"},
    },
    {"$set": {"entity1type": "gene"}}
)
print(f"  bare '(CANON)'  -> type=gene: {r.modified_count:,}")

# Canonical + suffix
for suf, newtype in SUFFIX_TO_TYPE:
    r = col.update_many(
        {
            "entity1type": "gene identifier",
            "entity1_lower": {"$regex": r"^\([^)]*\)" + re.escape(suf) + r"$"},
        },
        {"$set": {"entity1type": newtype}}
    )
    print(f"  '(CANON){suf}' -> type={newtype}: {r.modified_count:,}")

# Anything still marked "gene identifier" that didn't match the patterns —
# fall back to empty type (rare).
r = col.update_many(
    {"entity1type": "gene identifier"},
    {"$set": {"entity1type": ""}}
)
print(f"  residual entity1type='gene identifier' cleared: {r.modified_count:,}")

# Entity-2 side
print("\nentity2: restoring types on canonical gene-identifier docs...")
r = col.update_many(
    {
        "entity2type": "gene identifier",
        "entity2_lower": {"$regex": r"^\([^)]*\)$"},
    },
    {"$set": {"entity2type": "gene"}}
)
print(f"  bare '(CANON)'  -> type=gene: {r.modified_count:,}")

for suf, newtype in SUFFIX_TO_TYPE:
    r = col.update_many(
        {
            "entity2type": "gene identifier",
            "entity2_lower": {"$regex": r"^\([^)]*\)" + re.escape(suf) + r"$"},
        },
        {"$set": {"entity2type": newtype}}
    )
    print(f"  '(CANON){suf}' -> type={newtype}: {r.modified_count:,}")

r = col.update_many(
    {"entity2type": "gene identifier"},
    {"$set": {"entity2type": ""}}
)
print(f"  residual entity2type='gene identifier' cleared: {r.modified_count:,}")

print(f"\nDone in {time.time()-t_start:.0f}s")
