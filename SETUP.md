# PlantConnectome Setup Guide

## Prerequisites

- Python 3.10+
- MongoDB 6.0+ (running locally or accessible via URI)
- pip

## 1. Install Dependencies

```bash
cd PlantConnectome
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Environment Variables

Create a `.env` file in the project root (optional — defaults are provided):

```
MONGO_URI=mongodb://localhost:27017/
OPENAI_API_KEY=sk-...  # Required for AI summary generation and edge validation
```

## 3. Prepare Data Files

You need two data files in the project root:

| File | Description |
|------|-------------|
| `gut_microbiome_2_2k_most_recent_papers_semi-fixed.xlsx` | Knowledge graph relationships extracted from papers. Columns: `pmid`, `section`, `source`, `source_type`, `source_category`, `target`, `target_type`, `target_category`, `relationship`, `relationship_label`, `species`, `basis`, `source_extracted_definition`, `source_generated_definition`, `target_extracted_definition`, `target_generated_definition` |
| `papers.with_citations.jsonl` | Full text of papers (one JSON object per line). Keys: `PMID`, `Title`, `Abstract`, `Intro`, `Methods`, `Results`, `Discuss`, `Concl`, `AuthorList`, `CitationCount` |

## 4. Load Data into MongoDB

Run the scripts in this order:

### Step 1: Load KG relationships from Excel

```bash
python load_data.py
```

This populates:
- **`all_dic`** collection — all KG relationships (entities, types, categories, edges, PMIDs, sections, definitions)
- **`stats.txt`** — paper and relationship counts for the homepage
- **`catalogue.pkl`** — alphabetical entity catalogue for browsing
- **`utils/Microbiome_entities.csv`** — entity type-to-category mappings (updated from data)

### Step 2: Load paper text and authors from JSONL

```bash
python load_papers.py
```

This populates:
- **`scientific_chunks`** collection — paper text split by section (keys: `pmid` + `section`). Used for "Source Text" modal and edge validation.
- **`authors`** collection — author lists per paper (keys: `authors` array + `pubmedID`). Used for author search.

## 5. Start the Server

```bash
python app.py
```

The server runs at **http://127.0.0.1:8080**.

For production:
```bash
gunicorn -c gunicorn.conf.py app:app
```

## MongoDB Collections

| Collection | Documents | Description |
|---|---|---|
| `all_dic` | ~586K | KG relationships with entity types, categories, definitions |
| `scientific_chunks` | ~598K | Paper text by section (TITLE, ABSTRACT, INTRO, METHODS, RESULTS, DISCUSSION, CONCLUSION) |
| `authors` | ~137K | Author lists per PMID |
| `gene_alias` | varies | Gene name aliases for search expansion |

## Entity Categories (22)

These are assigned during KG extraction and stored in `source_category` / `target_category`:

| Prompt Category | Visualization Category |
|---|---|
| Gene / Protein | GENE/PROTEIN |
| Genomic / Transcriptomic / Proteomic / Epigenomic Feature / Gene Mutant | GENE/PROTEIN |
| Microbial Species | MICROORGANISM |
| Virus | MICROORGANISM |
| Taxonomic / Evolutionary / Phylogenetic Group | TAXONOMY |
| Complex / Structure / Compartment / Cell / Organ / Organism | CELL/COMPARTMENT |
| Clinical Phenotype / Clinical Trait / Host Condition | PHENOTYPE |
| Non-Clinical Phenotype | PHENOTYPE |
| Disease | DISEASE/CONDITION |
| Treatment / Exposure / Perturbation | TREATMENT |
| Metabolite | CHEMICAL |
| Chemical / Cofactor / Ligand | CHEMICAL |
| Biological Process / Function | BIOLOGICAL PROCESS |
| Regulatory / Signaling Mechanism / Metabolic Pathway | BIOLOGICAL PROCESS |
| Computational / Model / Algorithm / Data / Metric | METHOD |
| Method / Assay / Experimental Setup / Parameter / Sample | METHOD |
| Ecological / Soil / Aquatic / Climate Context | ENVIRONMENT |
| Epidemiological / Population | HOST/ORGANISM |
| Equipment / Device / Material / Instrument | METHOD |
| Social / Economic / Policy / Management | OTHER |
| Knowledge / Concept / Hypothesis / Theoretical Construct | OTHER |
| Property / Measurement / Characterization | OTHER |

## Relationship Labels (21)

Stored in `relationship_label` and used for edge coloring/categorization:

- Activation / Induction / Causation / Result
- Repression / Inhibition / Negative Regulation
- Regulation / Control
- Expression / Detection / Identification
- Association / Interaction / Binding
- Localization / Containment / Composition
- Requirement / Activity / Function / Participation
- Encodes / Contains
- Lacks / Dissimilar
- Synthesis / Formation
- Modification / Changes / Alters
- Treatment / Exposure / Perturbation / Administration
- Comparison / Evaluation / Benchmarking
- Definition / Classification / Naming
- Property / Characterization
- Hypothesis / Assumption / Proposal
- Temporal / Sequential Relationship
- Is / Similarity / Equivalence / Analogy
- Limitation / Innovation / Improvement / Advancement
- No Effect / Null Relationship
- Others: (custom label)

## Updating Data

To reload with new data:

1. Replace `gut_microbiome_2_2k_most_recent_papers_semi-fixed.xlsx` and/or `papers.with_citations.jsonl`
2. Re-run `python load_data.py` (drops and recreates `all_dic`)
3. Re-run `python load_papers.py` (drops and recreates `scientific_chunks` and `authors`)
4. Restart the server
