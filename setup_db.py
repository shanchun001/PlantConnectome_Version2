"""
Setup script to initialize the PlantConnectome MongoDB database with sample data.
Run this once to create the database, collections, and indexes.

Usage:
    python setup_db.py
"""
from pymongo import MongoClient, TEXT
import os

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(mongo_uri)
db = client["PlantConnectome"]

print("Setting up PlantConnectome database...")

# Create collections
all_dic = db["all_dic"]
authors = db["authors"]
scientific_chunks = db["scientific_chunks"]

# Create indexes on all_dic
print("Creating indexes on all_dic...")
all_dic.create_index([("entity1", TEXT), ("entity2", TEXT)], name="textindex")
all_dic.create_index("pubmedID")
all_dic.create_index("entity1")
all_dic.create_index("entity2")

# Create indexes on authors
print("Creating indexes on authors...")
authors.create_index("authors")
authors.create_index("pubmedID")

# Create index on scientific_chunks
print("Creating indexes on scientific_chunks...")
scientific_chunks.create_index("custom_id")


# Insert sample data for testing
print("Inserting sample data...")

sample_records = [
    {
        "entity1": "Arabidopsis thaliana",
        "entity1type": "ORGANISM",
        "entity2": "salicylic acid",
        "entity2type": "HORMONE",
        "edge": "produces",
        "pubmedID": "sample_001",
        "p_source": "abstract",
        "species": "Arabidopsis thaliana",
        "basis": "experimental study",
        "source_extracted_definition": "A model flowering plant widely used in plant biology research",
        "source_generated_definition": "Arabidopsis thaliana is a small cruciferous plant used as a model organism",
        "target_extracted_definition": "A plant hormone involved in defense signaling",
        "target_generated_definition": "Salicylic acid mediates systemic acquired resistance in plants"
    },
    {
        "entity1": "NPR1",
        "entity1type": "GENE",
        "entity2": "systemic acquired resistance",
        "entity2type": "BIOLOGICAL PROCESS",
        "edge": "regulates",
        "pubmedID": "sample_002",
        "p_source": "abstract",
        "species": "Arabidopsis thaliana",
        "basis": "genetic analysis",
        "source_extracted_definition": "A key regulator of plant immune responses",
        "source_generated_definition": "NPR1 is a transcriptional co-activator essential for SA-mediated defense",
        "target_extracted_definition": "A broad-spectrum plant defense mechanism",
        "target_generated_definition": "SAR provides long-lasting protection against pathogens"
    },
    {
        "entity1": "drought stress",
        "entity1type": "TREATMENT",
        "entity2": "ABA",
        "entity2type": "HORMONE",
        "edge": "induces accumulation of",
        "pubmedID": "sample_003",
        "p_source": "results",
        "species": "Oryza sativa",
        "basis": "physiological study",
        "source_extracted_definition": "Water deficit condition affecting plant growth",
        "source_generated_definition": "Drought stress triggers multiple hormonal and molecular responses",
        "target_extracted_definition": "Abscisic acid, a plant hormone involved in stress responses",
        "target_generated_definition": "ABA promotes stomatal closure and stress tolerance"
    },
]

# Insert sample data
if all_dic.count_documents({}) == 0:
    all_dic.insert_many(sample_records)
    print(f"Inserted {len(sample_records)} sample records into all_dic")
else:
    print(f"all_dic already has {all_dic.count_documents({})} records, skipping sample data insertion")

# Insert sample authors
sample_authors = [
    {"authors": ["MUTWIL M", "PERSSON S"], "pubmedID": "sample_001"},
    {"authors": ["DONG X", "CAO H"], "pubmedID": "sample_002"},
    {"authors": ["SHINOZAKI K", "YAMAGUCHI-SHINOZAKI K"], "pubmedID": "sample_003"},
]

if authors.count_documents({}) == 0:
    authors.insert_many(sample_authors)
    print(f"Inserted {len(sample_authors)} sample author records")
else:
    print(f"authors already has {authors.count_documents({})} records, skipping")

# Update stats.txt
paper_count = len(set(doc["pubmedID"] for doc in all_dic.find({}, {"pubmedID": 1})))
relationship_count = all_dic.count_documents({})
with open('stats.txt', 'w') as f:
    f.write(f"{paper_count}\t{relationship_count}")
print(f"Updated stats.txt: {paper_count} papers, {relationship_count} relationships")

print("\nSetup complete! Run 'python app.py' to start the server.")
