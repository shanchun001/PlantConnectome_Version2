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

You need the data file in the project root:

| File | Description |
|------|-------------|
| `oup_wly_elv_spr_sci_sciadv_all_kg.csv` | Knowledge graph relationships extracted from plant science papers. Columns: `custom_id`, `journal`, `year`, `month`, `title`, `section`, `filename`, `source`, `source_identifier`, `source_type`, `source_category`, `source_extracted_definition`, `source_generated_definition`, `relationship`, `relationship_category`, `target`, `target_identifier`, `target_type`, `target_category`, `target_extracted_definition`, `target_generated_definition`, `species`, `basis` |

## 4. Load Data into MongoDB

```bash
python load_data.py
```

This populates:
- **`all_dic`** collection — all KG relationships (entities, types, categories, edges, definitions)
- **`stats.txt`** — paper and relationship counts for the homepage
- **`catalogue.pkl`** — alphabetical entity catalogue for browsing
- **`utils/Connectome_entities.csv`** — entity type-to-category mappings (updated from data)

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
| `all_dic` | ~11.1M | KG relationships with entity types, categories, definitions |
| `scientific_chunks` | varies | Paper text by section (optional, for source text modals) |
| `authors` | varies | Author lists per paper (optional, for author search) |

## Entity Categories

| Category | Examples |
|---|---|
| GENE/PROTEIN | Genes, proteins, enzymes, transcription factors, protein complexes, mutants |
| PHENOTYPE | Observable characteristics, stress responses, growth traits |
| CELL/ORGAN/ORGANISM | Organisms, organs, tissues, cell types, subcellular compartments |
| CHEMICAL | Metabolites, hormones, compounds, molecules |
| TREATMENT | Environmental conditions, experimental treatments, stress factors |
| BIOLOGICAL PROCESS | Pathways, signaling, metabolic processes |
| GENOMIC/TRANSCRIPTOMIC FEATURE | DNA sequences, mutations, chromosomes, gene expression |
| METHOD | Techniques, databases, software, tools, datasets |
| GENE IDENTIFIER | Gene identifiers (e.g., AT4G02770) |

## Updating Data

To reload with new data:

1. Replace `oup_wly_elv_spr_sci_sciadv_all_kg.csv`
2. Re-run `python load_data.py` (drops and recreates `all_dic`)
3. Restart the server
