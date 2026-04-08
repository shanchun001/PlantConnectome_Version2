"""
Load plant science data from CSV into the PlantConnectome MongoDB database.

Usage:
    python load_data.py

Reads: oup_wly_elv_spr_sci_sciadv_all_kg.csv
Populates: all_dic collection + stats.txt + catalogue.pkl
"""
import pandas as pd
import pickle
import os
from collections import defaultdict
from pymongo import MongoClient, TEXT

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oup_wly_elv_spr_sci_sciadv_all_kg.csv")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

client = MongoClient(MONGO_URI)
db = client["PlantConnectome"]

# ── 1. Read CSV in chunks (11M+ rows) ────────────────────────────────────
print(f"Reading {DATA_PATH} ...")
CHUNK_SIZE = 100000

# First pass: count rows and unique custom_ids for stats
print("Counting rows ...")
total_rows = 0
custom_ids = set()
for chunk in pd.read_csv(DATA_PATH, chunksize=CHUNK_SIZE, usecols=["custom_id"]):
    total_rows += len(chunk)
    custom_ids.update(chunk["custom_id"].dropna().unique())
    if total_rows % 1000000 == 0:
        print(f"  counted {total_rows} rows ...")

# Extract unique paper identifiers from custom_id (strip section suffix)
paper_ids = set()
for cid in custom_ids:
    # custom_id format: "Volume56_Issue414_Title_b36497_section"
    # The paper identifier is everything before the last underscore (section)
    parts = str(cid).rsplit("_", 1)
    if len(parts) > 1:
        paper_ids.add(parts[0])
    else:
        paper_ids.add(str(cid))

print(f"  {total_rows} rows, {len(paper_ids)} unique papers")

# ── 2. Drop and recreate all_dic ─────────────────────────────────────────
print("Dropping existing all_dic collection ...")
db.drop_collection("all_dic")

# ── 3. Load data in chunks ───────────────────────────────────────────────
print(f"Inserting records into all_dic in chunks of {CHUNK_SIZE} ...")
inserted = 0
all_entities = set()
type_counts = defaultdict(int)

for chunk in pd.read_csv(DATA_PATH, chunksize=CHUNK_SIZE):
    docs = []
    for _, row in chunk.iterrows():
        doc = {
            "entity1":       str(row.get("source", "")).strip() if pd.notna(row.get("source")) else "",
            "entity1type":   str(row.get("source_type", "")).strip() if pd.notna(row.get("source_type")) else "",
            "entity1category": str(row.get("source_category", "")).strip() if pd.notna(row.get("source_category")) else "",
            "entity2":       str(row.get("target", "")).strip() if pd.notna(row.get("target")) else "",
            "entity2type":   str(row.get("target_type", "")).strip() if pd.notna(row.get("target_type")) else "",
            "entity2category": str(row.get("target_category", "")).strip() if pd.notna(row.get("target_category")) else "",
            "edge":          str(row.get("relationship", "")).strip() if pd.notna(row.get("relationship")) else "",
            "relationship_label": str(row.get("relationship_category", "")).strip() if pd.notna(row.get("relationship_category")) else "",
            "pubmedID":      str(row.get("custom_id", "")).strip() if pd.notna(row.get("custom_id")) else "",
            "custom_id":     str(row.get("custom_id", "")).strip() if pd.notna(row.get("custom_id")) else "",
            "p_source":      str(row.get("section", "")).strip() if pd.notna(row.get("section")) else "",
            "journal":       str(row.get("journal", "")).strip() if pd.notna(row.get("journal")) else "",
            "year":          str(row.get("year", "")).strip() if pd.notna(row.get("year")) else "",
            "title":         str(row.get("title", "")).strip() if pd.notna(row.get("title")) else "",
            "species":       str(row.get("species", "")).strip() if pd.notna(row.get("species")) else "",
            "basis":         str(row.get("basis", "")).strip() if pd.notna(row.get("basis")) else "",
            "source_extracted_definition": str(row.get("source_extracted_definition", "")).strip() if pd.notna(row.get("source_extracted_definition")) else "",
            "source_generated_definition": str(row.get("source_generated_definition", "")).strip() if pd.notna(row.get("source_generated_definition")) else "",
            "target_extracted_definition": str(row.get("target_extracted_definition", "")).strip() if pd.notna(row.get("target_extracted_definition")) else "",
            "target_generated_definition": str(row.get("target_generated_definition", "")).strip() if pd.notna(row.get("target_generated_definition")) else "",
            "source_identifier": str(row.get("source_identifier", "")).strip() if pd.notna(row.get("source_identifier")) else "",
            "target_identifier": str(row.get("target_identifier", "")).strip() if pd.notna(row.get("target_identifier")) else "",
        }
        docs.append(doc)

        # Track entities and types for catalogue/categories
        if doc["entity1"]:
            all_entities.add(doc["entity1"])
        if doc["entity2"]:
            all_entities.add(doc["entity2"])
        if doc["entity1type"]:
            type_counts[doc["entity1type"].upper()] += 1
        if doc["entity2type"]:
            type_counts[doc["entity2type"].upper()] += 1

    if docs:
        db["all_dic"].insert_many(docs)
    inserted += len(docs)
    print(f"  inserted {inserted}/{total_rows}")

# ── 4. Create indexes ───────────────────────────────────────────────────
print("Creating indexes on all_dic ...")
db["all_dic"].create_index([("entity1", TEXT), ("entity2", TEXT)], name="textindex", default_language="english")
db["all_dic"].create_index("pubmedID")
db["all_dic"].create_index("custom_id")
db["all_dic"].create_index("entity1")
db["all_dic"].create_index("entity2")

# ── 5. Update stats.txt ─────────────────────────────────────────────────
paper_count = len(paper_ids)
relationship_count = inserted
with open("stats.txt", "w") as f:
    f.write(f"{paper_count}\t{relationship_count}")
print(f"stats.txt updated: {paper_count} papers, {relationship_count} relationships")

# ── 6. Build catalogue.pkl ───────────────────────────────────────────────
print("Building catalogue.pkl ...")
grouped = defaultdict(list)
for entity in sorted(all_entities):
    first_char = entity[0].upper() if entity else "?"
    if first_char.isdigit():
        first_char = first_char
    elif not first_char.isalpha():
        first_char = "#"
    grouped[first_char].append(entity)

header = sorted(grouped.keys())
catalogue = [header, dict(grouped)]

with open("catalogue.pkl", "wb") as f:
    pickle.dump(catalogue, f)
print(f"catalogue.pkl created: {len(all_entities)} unique entities in {len(header)} groups")

# ── 7. Update entity categories CSV from actual data ────────────────────
print("Updating Connectome_entities.csv from actual data ...")

existing_categories = {}
try:
    edf = pd.read_csv("utils/Connectome_entities.csv")
    for _, row in edf.iterrows():
        existing_categories[row["TYPE"]] = row["CATEGORY"]
except:
    pass

rows = []
for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
    category = existing_categories.get(etype, "OTHER")
    rows.append({"TYPE": etype, "COUNT": count, "CATEGORY": category})

new_edf = pd.DataFrame(rows)
new_edf.to_csv("utils/Connectome_entities.csv", index=False)
print(f"  {len(rows)} entity types written")

print("\nDone! Run 'python app.py' to start the server.")
