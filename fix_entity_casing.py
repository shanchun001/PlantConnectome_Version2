"""
Fix entity casing inconsistencies - targeted approach.
Only processes the ~14K entities that have multiple casing variants.
Uses indexed entity1_lower/entity2_lower for fast targeted updates.

Usage:
    python fix_entity_casing.py
"""
import os, time
from pymongo import MongoClient, UpdateMany

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client["PlantConnectome"]
col = db["all_dic"]

def fix_casing(field, lower_field):
    print(f"\nFinding {field} variants (entities with multiple casings)...")
    t = time.time()
    # Only aggregate entities that have multiple distinct casings
    variants = list(col.aggregate([
        {"$group": {
            "_id": f"${lower_field}",
            "casings": {"$addToSet": f"${field}"},
            "counts": {"$push": f"${field}"}
        }},
        {"$match": {"$expr": {"$gt": [{"$size": "$casings"}, 1]}}},
        {"$project": {
            "_id": 1,
            "casings": 1,
            "total": {"$size": "$counts"}
        }}
    ], allowDiskUse=True))
    print(f"  Found {len(variants)} entities with casing variants ({time.time()-t:.0f}s)")

    # For each variant group, find most common casing and update non-representative ones
    updated = 0
    for i, v in enumerate(variants):
        lower_val = v["_id"]
        casings = v["casings"]

        # Count each casing by querying directly (using index)
        counts = {}
        for casing in casings:
            c = col.count_documents({lower_field: lower_val, field: casing})
            counts[casing] = c

        # Most common casing wins
        representative = max(counts, key=counts.get)

        # Update all docs with non-representative casings
        non_rep = [c for c in casings if c != representative]
        for bad_casing in non_rep:
            result = col.update_many(
                {lower_field: lower_val, field: bad_casing},
                {"$set": {field: representative}}
            )
            updated += result.modified_count

        if (i + 1) % 1000 == 0:
            print(f"  processed {i+1}/{len(variants)}, updated {updated} docs so far...")

    print(f"  Total: {updated} documents updated")
    return updated

t_start = time.time()

u1 = fix_casing("entity1", "entity1_lower")
u2 = fix_casing("entity2", "entity2_lower")

print(f"\nDone in {time.time()-t_start:.0f}s — {u1+u2} total documents updated")

# Verify fix
print("\nVerification - 'cesa genes' variants after fix:")
docs = list(col.aggregate([
    {"$match": {"entity1_lower": "cesa genes"}},
    {"$group": {"_id": "$entity1", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]))
for d in docs:
    print(f"  '{d['_id']}' ({d['count']}x)")

print("\nVerification - 'salt stress' variants after fix:")
docs = list(col.aggregate([
    {"$match": {"entity1_lower": "salt stress"}},
    {"$group": {"_id": "$entity1", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]))
for d in docs:
    print(f"  '{d['_id']}' ({d['count']}x)")
