"""
Load section text and paper metadata into PlantConnectome MongoDB.

Populates:
  - scientific_chunks: paper text by section (title + section keys)
  - authors: author lists + pubmed_id per title

Usage:
    python load_section_text.py
"""
import csv
import os
import sys
import time
import re
from pymongo import MongoClient

# Increase CSV field size limit for large section texts
csv.field_size_limit(sys.maxsize)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
SECTION_TEXT_PATH = "/mnt/data/section_text_mapping.csv"
PAPER_META_PATH = "/mnt/data/paper_metadata.csv"

client = MongoClient(MONGO_URI)
db = client["PlantConnectome"]

BATCH = 10000

# ── 1. Load section text into scientific_chunks ──────────────────────────
print("Step 1: Loading section text into scientific_chunks...")
print(f"  Reading {SECTION_TEXT_PATH}...")
t = time.time()

db.drop_collection("scientific_chunks")

total = 0
errors = 0

# Read the entire file and handle malformed rows by requiring exactly 3 fields per record
# Use csv.reader with error handling for embedded newlines/tables
chunk_docs = []
current_title = ""
current_section = ""
current_text = ""

with open(SECTION_TEXT_PATH, "r", encoding="utf-8", errors="replace") as f:
    header = f.readline()  # skip header
    for line in f:
        # Try to parse as a proper CSV row (title, section, section_text)
        # A valid row starts with a quote: "title","section","text..."
        line = line.rstrip('\n').rstrip('\r')
        if not line:
            continue

        # Check if this is a new record (starts with a quoted field that looks like a title)
        # New records start with "Title text","section","
        parts = None
        try:
            parts = list(csv.reader([line]))[0]
        except:
            pass

        if parts and len(parts) >= 3 and parts[1].strip().lower() in (
            'abstract', 'introduction', 'methods', 'results', 'discussion',
            'conclusion', 'results_and_discussion', 'title',
            'materials_and_methods', 'supplementary_data', 'acknowledgements',
            'references', 'appendix', 'background', 'figures_and_tables',
        ):
            # Save previous record
            if current_title and current_text.strip():
                text_clean = re.sub(r'\s*\$[^$]+\$\s*#reference_key_\d+#\s*', ' ', current_text).strip()
                chunk_docs.append({"title": current_title, "section": current_section, "text": text_clean})
                total += 1
                if len(chunk_docs) >= BATCH:
                    db["scientific_chunks"].insert_many(chunk_docs)
                    chunk_docs = []
                    if total % 100000 == 0:
                        print(f"    inserted {total} chunks...")

            current_title = parts[0].strip()
            current_section = parts[1].strip().upper()
            current_text = parts[2] if len(parts) > 2 else ""
        else:
            # Continuation of previous record's text (embedded newline or table)
            if current_title:
                current_text += " " + line

    # Save last record
    if current_title and current_text.strip():
        text_clean = re.sub(r'\s*\$[^$]+\$\s*#reference_key_\d+#\s*', ' ', current_text).strip()
        chunk_docs.append({"title": current_title, "section": current_section, "text": text_clean})
        total += 1

if chunk_docs:
    db["scientific_chunks"].insert_many(chunk_docs)

print(f"  Inserted {total} chunks ({time.time()-t:.0f}s)")

print("  Creating indexes...")
db["scientific_chunks"].create_index("title")
db["scientific_chunks"].create_index([("title", 1), ("section", 1)])
print("  Indexes created")

# ── 2. Load paper metadata into authors collection ───────────────────────
print(f"\nStep 2: Loading paper metadata into authors...")
print(f"  Reading {PAPER_META_PATH}...")
t = time.time()

db.drop_collection("authors")

author_docs = []
total_papers = 0

def standardize_author_name(name):
    """Convert 'Nicholas H Battey' -> 'BATTEY NH' format."""
    parts = name.strip().split()
    if not parts:
        return ""
    surname = parts[-1].upper()
    initials = "".join(p[0].upper() for p in parts[:-1] if p)
    return f"{surname} {initials}".strip()

with open(PAPER_META_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        title = row.get("title", "").strip()
        doi = row.get("doi", "").strip()
        authors_raw = row.get("authors", "").strip()
        pubmed_id = row.get("pubmed_id", "").strip()

        if not title:
            continue

        # Parse authors (semicolon-separated)
        if authors_raw:
            author_list = [a.strip() for a in authors_raw.split(";") if a.strip()]
            standardized = [standardize_author_name(a) for a in author_list if a]
            standardized = [a for a in standardized if a]
        else:
            standardized = []

        author_docs.append({
            "title": title,
            "authors": standardized,
            "authors_original": author_list if authors_raw else [],
            "pubmedID": pubmed_id,
            "doi": doi,
        })
        total_papers += 1

        if len(author_docs) >= BATCH:
            db["authors"].insert_many(author_docs)
            author_docs = []

if author_docs:
    db["authors"].insert_many(author_docs)

print(f"  Inserted {total_papers} papers ({time.time()-t:.0f}s)")

print("  Creating indexes...")
db["authors"].create_index("title")
db["authors"].create_index("authors")
db["authors"].create_index("pubmedID")
print("  Indexes created")

# ── 3. Build title-to-pubmedID lookup in all_dic ────────────────────────
# Update all_dic docs with pubmed_id from paper_metadata where title matches
print("\nStep 3: Linking pubmed_id from paper_metadata to all_dic...")
t = time.time()
# Load all authors into memory (only 61K rows, ~10MB)
author_list = list(db["authors"].find({"pubmedID": {"$ne": ""}}, {"title": 1, "pubmedID": 1}))
print(f"  {len(author_list)} papers with pubmed_id")
updated = 0
for i, doc in enumerate(author_list):
    result = db["all_dic"].update_many(
        {"title": doc["title"]},
        {"$set": {"pubmed_id": doc["pubmedID"]}}
    )
    updated += result.modified_count
    if (i + 1) % 10000 == 0:
        print(f"    processed {i+1}/{len(author_list)}, updated {updated} docs...")

print(f"  Linked pubmed_id to {updated} all_dic documents ({time.time()-t:.0f}s)")

# ── 4. Summary ───────────────────────────────────────────────────────────
print(f"\nDone!")
print(f"  scientific_chunks: {db['scientific_chunks'].count_documents({})} documents")
print(f"  authors: {db['authors'].count_documents({})} documents")

# Test
doc = db["scientific_chunks"].find_one({"title": "Characterization of antifreeze activity in Antarctic plants"})
if doc:
    print(f"\n  Test: '{doc['title']}' / {doc['section']}: {doc['text'][:80]}...")
