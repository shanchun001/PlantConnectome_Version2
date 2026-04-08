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
gene_alias = db["gene_alias"]

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

# Create index on gene_alias
print("Creating indexes on gene_alias...")
gene_alias.create_index("gene")
gene_alias.create_index("aliases")

# Insert sample data for testing
print("Inserting sample data...")

sample_records = [
    {
        "entity1": "Lactobacillus rhamnosus",
        "entity1type": "MICROORGANISM",
        "entity2": "inflammatory bowel disease",
        "entity2type": "DISEASE",
        "edge": "ASSOCIATED WITH",
        "pubmedID": "33456789",
        "p_source": "sample_001",
        "species": "Homo sapiens",
        "basis": "clinical study",
        "source_extracted_definition": "A probiotic bacterium commonly found in the human gut",
        "source_generated_definition": "Lactobacillus rhamnosus is a gram-positive bacterium used as a probiotic",
        "target_extracted_definition": "A chronic inflammatory condition of the gastrointestinal tract",
        "target_generated_definition": "IBD is a group of inflammatory conditions affecting the colon and small intestine"
    },
    {
        "entity1": "Escherichia coli",
        "entity1type": "MICROORGANISM",
        "entity2": "butyrate",
        "entity2type": "METABOLITE",
        "edge": "PRODUCES",
        "pubmedID": "33456790",
        "p_source": "sample_002",
        "species": "Escherichia coli K-12",
        "basis": "in vitro experiment",
        "source_extracted_definition": "A gram-negative bacterium commonly found in the lower intestine",
        "source_generated_definition": "E. coli is a versatile microorganism with both commensal and pathogenic strains",
        "target_extracted_definition": "A short-chain fatty acid produced by gut bacteria",
        "target_generated_definition": "Butyrate is a key energy source for colonocytes"
    },
    {
        "entity1": "Bifidobacterium longum",
        "entity1type": "MICROORGANISM",
        "entity2": "immune response",
        "entity2type": "BIOLOGICAL PROCESS",
        "edge": "MODULATES",
        "pubmedID": "33456791",
        "p_source": "sample_003",
        "species": "Homo sapiens",
        "basis": "clinical trial",
        "source_extracted_definition": "A beneficial bacterium in the human gut microbiome",
        "source_generated_definition": "B. longum is one of the most common probiotic species",
        "target_extracted_definition": "The body's defense mechanism against pathogens",
        "target_generated_definition": "The immune response involves both innate and adaptive immunity"
    },
    {
        "entity1": "Akkermansia muciniphila",
        "entity1type": "MICROORGANISM",
        "entity2": "obesity",
        "entity2type": "DISEASE",
        "edge": "NEGATIVELY CORRELATED WITH",
        "pubmedID": "33456792",
        "p_source": "sample_004",
        "species": "Homo sapiens",
        "basis": "meta-analysis",
        "source_extracted_definition": "A mucin-degrading bacterium in the gut",
        "source_generated_definition": "A. muciniphila is associated with improved metabolic health",
        "target_extracted_definition": "A condition characterized by excessive body fat",
        "target_generated_definition": "Obesity is a complex metabolic disorder"
    },
    {
        "entity1": "Faecalibacterium prausnitzii",
        "entity1type": "MICROORGANISM",
        "entity2": "butyrate",
        "entity2type": "METABOLITE",
        "edge": "PRODUCES",
        "pubmedID": "33456793",
        "p_source": "sample_005",
        "species": "Homo sapiens",
        "basis": "in vitro study",
        "source_extracted_definition": "One of the most abundant bacteria in the healthy human gut",
        "source_generated_definition": "F. prausnitzii is a major butyrate producer and anti-inflammatory commensal",
        "target_extracted_definition": "A short-chain fatty acid with anti-inflammatory properties",
        "target_generated_definition": "Butyrate supports gut barrier integrity"
    },
    {
        "entity1": "Clostridioides difficile",
        "entity1type": "MICROORGANISM",
        "entity2": "antibiotic treatment",
        "entity2type": "TREATMENT",
        "edge": "INDUCED BY",
        "pubmedID": "33456794",
        "p_source": "sample_006",
        "species": "Homo sapiens",
        "basis": "clinical observation",
        "source_extracted_definition": "An opportunistic pathogen causing colitis",
        "source_generated_definition": "C. difficile infection often occurs after antibiotic-induced dysbiosis",
        "target_extracted_definition": "Use of antibiotics to treat bacterial infections",
        "target_generated_definition": "Antibiotic treatment can disrupt the normal gut microbiota"
    },
    {
        "entity1": "gut microbiome",
        "entity1type": "COMMUNITY",
        "entity2": "depression",
        "entity2type": "DISEASE",
        "edge": "ASSOCIATED WITH",
        "pubmedID": "33456795",
        "p_source": "sample_007",
        "species": "Homo sapiens",
        "basis": "cohort study",
        "source_extracted_definition": "The collective genome of microorganisms in the gut",
        "source_generated_definition": "The gut microbiome plays a key role in the gut-brain axis",
        "target_extracted_definition": "A mood disorder characterized by persistent sadness",
        "target_generated_definition": "Depression has been linked to gut-brain axis dysregulation"
    },
    {
        "entity1": "Lactobacillus rhamnosus",
        "entity1type": "MICROORGANISM",
        "entity2": "gut barrier",
        "entity2type": "ORGAN",
        "edge": "ENHANCES",
        "pubmedID": "33456796",
        "p_source": "sample_008",
        "species": "Mus musculus",
        "basis": "animal study",
        "source_extracted_definition": "A probiotic bacterium",
        "source_generated_definition": "L. rhamnosus strengthens intestinal barrier function",
        "target_extracted_definition": "The intestinal epithelial barrier",
        "target_generated_definition": "The gut barrier prevents translocation of harmful substances"
    },
    {
        "entity1": "Prevotella copri",
        "entity1type": "MICROORGANISM",
        "entity2": "rheumatoid arthritis",
        "entity2type": "DISEASE",
        "edge": "ASSOCIATED WITH",
        "pubmedID": "33456797",
        "p_source": "sample_009",
        "species": "Homo sapiens",
        "basis": "case-control study",
        "source_extracted_definition": "A gut bacterium enriched in certain disease states",
        "source_generated_definition": "P. copri has been linked to autoimmune conditions",
        "target_extracted_definition": "An autoimmune disease affecting joints",
        "target_generated_definition": "RA is characterized by chronic joint inflammation"
    },
    {
        "entity1": "Helicobacter pylori",
        "entity1type": "MICROORGANISM",
        "entity2": "gastric cancer",
        "entity2type": "DISEASE",
        "edge": "CAUSES",
        "pubmedID": "33456798",
        "p_source": "sample_010",
        "species": "Homo sapiens",
        "basis": "epidemiological study",
        "source_extracted_definition": "A gram-negative bacterium colonizing the stomach",
        "source_generated_definition": "H. pylori is a class I carcinogen according to WHO",
        "target_extracted_definition": "Malignant neoplasm of the stomach",
        "target_generated_definition": "Gastric cancer is strongly associated with H. pylori infection"
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
    {"authors": ["KNIGHT R", "TURNBAUGH PJ"], "pubmedID": "33456789"},
    {"authors": ["KNIGHT R", "GILBERT JA"], "pubmedID": "33456790"},
    {"authors": ["SEGAL E", "ELINAV E"], "pubmedID": "33456791"},
    {"authors": ["CANI PD", "DE VOS WM"], "pubmedID": "33456792"},
    {"authors": ["SOKOL H", "SEKSIK P"], "pubmedID": "33456793"},
    {"authors": ["KELLY CP", "LAMONT JT"], "pubmedID": "33456794"},
    {"authors": ["CRYAN JF", "DINAN TG"], "pubmedID": "33456795"},
    {"authors": ["KNIGHT R"], "pubmedID": "33456796"},
    {"authors": ["SCHER JU", "ABRAMSON SB"], "pubmedID": "33456797"},
    {"authors": ["MARSHALL BJ", "WARREN JR"], "pubmedID": "33456798"},
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
