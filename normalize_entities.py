"""
Normalize entity casing in the PlantConnectome MongoDB database.

Uses MongoDB aggregation (not Python memory) to find representative casings.
Adds lowercase fields for fast indexed search.

Usage:
    python normalize_entities.py
"""
import os
from pymongo import MongoClient, UpdateMany

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["PlantConnectome"]
col = db["all_dic"]

BATCH = 10000

# ── Step 1: Add lowercase fields using MongoDB update pipeline ───────────
# This uses $set with aggregation expressions — no Python memory needed
print("Step 1: Adding entity1_lower and entity2_lower fields...")
print("  This updates documents directly in MongoDB using $toLower...")

# Use aggregation pipeline update (MongoDB 4.2+)
result = col.update_many(
    {"entity1_lower": {"$exists": False}},
    [{"$set": {
        "entity1_lower": {"$toLower": "$entity1"},
        "entity2_lower": {"$toLower": "$entity2"},
    }}]
)
print(f"  Updated {result.modified_count} documents with lowercase fields")

# ── Step 2: Create indexes on lowercase fields ──────────────────────────
print("\nStep 2: Creating indexes on lowercase fields...")
col.create_index("entity1_lower", name="entity1_lower_1")
print("  Created entity1_lower_1")
col.create_index("entity2_lower", name="entity2_lower_1")
print("  Created entity2_lower_1")

# ── Step 3: Find representative casing using aggregation ─────────────────
print("\nStep 3: Finding representative casing for entities...")
print("  Using MongoDB aggregation (entity1 side)...")

# For entity1: group by lowercase, find most common casing
pipeline_e1 = [
    {"$group": {
        "_id": {"lower": {"$toLower": "$entity1"}, "original": "$entity1"},
        "count": {"$sum": 1}
    }},
    {"$sort": {"count": -1}},
    {"$group": {
        "_id": "$_id.lower",
        "representative": {"$first": "$_id.original"},
        "total": {"$sum": "$count"}
    }},
    {"$out": "entity1_rep_temp"}
]
col.aggregate(pipeline_e1, allowDiskUse=True)
e1_rep_count = db["entity1_rep_temp"].count_documents({})
print(f"  Found {e1_rep_count} unique entity1 values")

print("  Using MongoDB aggregation (entity2 side)...")
pipeline_e2 = [
    {"$group": {
        "_id": {"lower": {"$toLower": "$entity2"}, "original": "$entity2"},
        "count": {"$sum": 1}
    }},
    {"$sort": {"count": -1}},
    {"$group": {
        "_id": "$_id.lower",
        "representative": {"$first": "$_id.original"},
        "total": {"$sum": "$count"}
    }},
    {"$out": "entity2_rep_temp"}
]
col.aggregate(pipeline_e2, allowDiskUse=True)
e2_rep_count = db["entity2_rep_temp"].count_documents({})
print(f"  Found {e2_rep_count} unique entity2 values")

# ── Step 4: Update entity names to representative casing ─────────────────
print("\nStep 4: Updating entity1 to representative casing...")
updated = 0
for doc in db["entity1_rep_temp"].find({}, {"_id": 1, "representative": 1}):
    lower_val = doc["_id"]
    rep = doc["representative"]
    # Update all docs where entity1_lower matches but entity1 doesn't match representative
    result = col.update_many(
        {"entity1_lower": lower_val, "entity1": {"$ne": rep}},
        {"$set": {"entity1": rep}}
    )
    updated += result.modified_count
    if updated % 100000 == 0 and updated > 0:
        print(f"  entity1: {updated} documents updated...")
print(f"  entity1: {updated} total documents updated")

print("Updating entity2 to representative casing...")
updated = 0
for doc in db["entity2_rep_temp"].find({}, {"_id": 1, "representative": 1}):
    lower_val = doc["_id"]
    rep = doc["representative"]
    result = col.update_many(
        {"entity2_lower": lower_val, "entity2": {"$ne": rep}},
        {"$set": {"entity2": rep}}
    )
    updated += result.modified_count
    if updated % 100000 == 0 and updated > 0:
        print(f"  entity2: {updated} documents updated...")
print(f"  entity2: {updated} total documents updated")

# ── Step 5: Cleanup temp collections ─────────────────────────────────────
print("\nStep 5: Cleaning up...")
db.drop_collection("entity1_rep_temp")
db.drop_collection("entity2_rep_temp")

# ── Step 6: Verify ───────────────────────────────────────────────────────
print("\nVerification:")
sample_queries = ["cesa", "arabidopsis thaliana", "salicylic acid", "npr1", "drought"]
for q in sample_queries:
    doc = col.find_one({"entity1_lower": q})
    if doc:
        print(f'  "{q}" -> entity1: "{doc["entity1"]}"')
    else:
        doc = col.find_one({"entity2_lower": q})
        if doc:
            print(f'  "{q}" -> entity2: "{doc["entity2"]}"')
        else:
            print(f'  "{q}" -> not found')

print("\nDone!")
