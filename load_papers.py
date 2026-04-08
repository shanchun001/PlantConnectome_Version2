"""
Load paper text and authors from papers.with_citations.jsonl into MongoDB.

Populates:
  - scientific_chunks: paper text split by section (pmid + section keys)
  - authors: author lists per PMID

Usage:
    python load_papers.py
"""
import json
import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
JSONL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "papers.with_citations.jsonl")

client = MongoClient(MONGO_URI)
db = client["PlantConnectome"]

SECTION_MAP = {
    "Title": "TITLE",
    "Abstract": "ABSTRACT",
    "Intro": "INTRO",
    "Methods": "METHODS",
    "Results": "RESULTS",
    "Discuss": "DISCUSSION",
    "Concl": "CONCLUSION",
}


def standardize_author_name(name):
    """Convert 'B S Drasar' -> 'DRASAR BS' format."""
    parts = name.strip().split()
    if not parts:
        return ""
    surname = parts[-1].upper()
    initials = "".join(p[0].upper() for p in parts[:-1] if p)
    return f"{surname} {initials}".strip()


print(f"Reading {JSONL_PATH} ...")

chunk_docs = []
author_docs = []
errors = 0

with open(JSONL_PATH, "r") as f:
    for line in f:
        try:
            paper = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue

        pmid = str(paper.get("PMID", "")).strip()
        if not pmid:
            continue

        # Scientific chunks
        for json_key, section_label in SECTION_MAP.items():
            text = paper.get(json_key)
            if text and str(text).strip():
                chunk_docs.append({
                    "pmid": pmid,
                    "section": section_label,
                    "text": str(text).strip(),
                })

        # Authors
        author_list = paper.get("AuthorList", [])
        if author_list:
            standardized = [standardize_author_name(a) for a in author_list if a]
            standardized = [a for a in standardized if a]
            if standardized:
                author_docs.append({"authors": standardized, "pubmedID": pmid})

print(f"  {len(chunk_docs)} chunk documents, {len(author_docs)} author documents ({errors} parse errors)")

# ── Load scientific_chunks ────────────────────────────────────────────────
print("Dropping existing scientific_chunks collection ...")
db.drop_collection("scientific_chunks")

BATCH = 50000
print(f"Inserting {len(chunk_docs)} records into scientific_chunks ...")
for i in range(0, len(chunk_docs), BATCH):
    db["scientific_chunks"].insert_many(chunk_docs[i:i + BATCH])
    print(f"  inserted {min(i + BATCH, len(chunk_docs))}/{len(chunk_docs)}")

print("Creating indexes on scientific_chunks ...")
db["scientific_chunks"].create_index([("pmid", 1), ("section", 1)])
db["scientific_chunks"].create_index("pmid")

# ── Load authors ──────────────────────────────────────────────────────────
print("Dropping existing authors collection ...")
db.drop_collection("authors")

print(f"Inserting {len(author_docs)} records into authors ...")
for i in range(0, len(author_docs), BATCH):
    db["authors"].insert_many(author_docs[i:i + BATCH])
    print(f"  inserted {min(i + BATCH, len(author_docs))}/{len(author_docs)}")

print("Creating indexes on authors ...")
db["authors"].create_index("authors")
db["authors"].create_index("pubmedID")

# ── Summary ───────────────────────────────────────────────────────────────
print(f"\nDone!")
print(f"  scientific_chunks: {db['scientific_chunks'].count_documents({})} documents")
print(f"  authors: {db['authors'].count_documents({})} documents")
print("\nRun 'python app.py' to start the server.")
