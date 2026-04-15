import unicodedata
import re
import time
import uuid
import json
from collections import defaultdict

from flask import request, render_template, redirect, url_for

from mongo import db
from my_cache import cache

entity_lookup = db["entity_lookup"]

# Comprehensive type -> category mapping (from GitHub PlantConnectome categoryMap)
_CATEGORY_MAP = {
    'biological process': [
        'metabolic pathway', 'function', 'pathway', 'signaling pathway',
        'metabolic process', 'cell process', 'biochemical process', 'cellular process',
        'molecular function', 'signalling pathway', 'genetic process', 'biological pathway', 'process'
    ],
    'cell/organ/organism': [
        'organism', 'organ', 'subcellular compartment', 'tissue', 'cell type',
        'organelle', 'virus', 'organelles', 'cell structure', 'plant', 'organism part'
    ],
    'chemical': [
        'metabolite', 'molecule', 'compound', 'chemical', 'hormone', 'phytohormone',
        'polysaccharide', 'material', 'polymer', 'chemical structure', 'biopolymer',
        'chemical compound', 'plant hormone', 'chemical group'
    ],
    'gene/protein': [
        'gene', 'protein', 'mutant', 'protein complex', 'enzyme', 'protein domain',
        'genetic element', 'gene family', 'protein family', 'protein structure', 'peptide',
        'protein motif', 'enzyme activity', 'protein region', 'gene feature', 'gene region',
        'gene structure', 'protein feature', 'transcription factor', 'gene cluster', 'gene group',
        'promoter', 'subunit', 'transcript', 'gene element', 'allele', 'protein sequence',
        'protein modification', 'post-translational modification', 'genetic locus',
        'protein subunit', 'genes', 'qtl', 'protein function', 'amino acid residue',
        'histone modification', 'protein fragment', 'receptor', 'genetic event', 'protein kinase',
        'protein class', 'protein group', 'gene product', 'antibody', 'proteins',
        'protein interaction', 'gene module', 'gene identifier'
    ],
    'genomic/transcriptomic feature': [
        'genomic region', 'genome', 'amino acid', 'genomic feature', 'dna sequence', 'rna',
        'sequence', 'mutation', 'chromosome', 'gene expression', 'genetic material', 'genotype',
        'genomic element', 'genetic marker', 'epigenetic mark', 'genetic variation',
        'regulatory element', 'epigenetic modification', 'dna element', 'mirna', 'genomic location',
        'subfamily', 'dna', 'activity', 'genetic feature', 'sequence motif', 'genetic variant',
        'motif', 'mrna', 'residue', 'region', 'genomic sequence', 'cis-element', 'clade',
        'accession', 'plasmid', 'genomic data', 'cultivar', 'genomic event', 'genomic resource',
        'ecotype', 'marker', 'lncrna', 'genetic construct', 'sequence feature', 'genus',
        'genetic concept'
    ],
    'method': [
        'method', 'technique', 'tool', 'database', 'software', 'dataset', 'concept', 'study',
        'description', 'model', 'modification', 'location', 'author', 'measurement', 'experiment',
        'researcher', 'mechanism', 'system', 'feature', 'parameter', 'algorithm', 'event',
        'reaction', 'resource', 'interaction', 'device', 'metric', 'technology', 'network',
        'construct', 'vector', 'category', 'data', 'research', 'geographical location',
        'document', 'analysis', 'person', 'project', 'research field', 'researchers',
        'gene network', 'relationship'
    ],
    'phenotype': ['phenotype'],
    'treatment': [
        'treatment', 'environment', 'condition', 'time', 'environmental factor', 'disease',
        'developmental stage', 'time point', 'stress', 'geographic location', 'abiotic stress',
        'time period'
    ]
}
TYPE_TO_CATEGORY = {t: cat for cat, types in _CATEGORY_MAP.items() for t in types}

def lookup_entity_names(search_term, mode="substring"):
    """
    Use entity_lookup collection for fast entity name discovery.
    Returns a list of lowercase entity names matching the search term.
    mode: 'substring' (prefix-anchored regex on _id, uses B-tree index), 'exact'
    """
    term_lower = search_term.lower()
    limit = 500
    if mode == "substring":
        # Contains regex on entity_lookup._id (lowercase entity names)
        # No sort (sorting defeats index use)
        results = entity_lookup.find(
            {"_id": {"$regex": re.escape(term_lower)}},
            {"_id": 1}
        ).limit(limit)
    elif mode == "exact":
        results = entity_lookup.find(
            {"_id": term_lower},
            {"_id": 1}
        ).limit(1)
    return [doc["_id"] for doc in results]
from cytoscape import generate_cytoscape_js, process_network, PROMPT_TO_VIS_CATEGORY, ENTITY_CATEGORIES_DICT
from text import make_text

cache = {}

# Human-readable display names for raw category strings from the database
CATEGORY_DISPLAY_NAMES = {
    'gene / protein': 'Gene / Protein',
    'genomic / transcriptomic / proteomic / epigenomic feature': 'Genomic / Transcriptomic / Proteomic / Epigenomic Feature',
    'genomic / transcriptomic / proteomic / epigenomic feature / gene mutant': 'Genomic / Transcriptomic / Proteomic / Epigenomic Feature / Gene Mutant',
    'genomic / transcriptomic / epigenomic feature': 'Genomic / Transcriptomic / Epigenomic Feature',
    'complex / structure / compartment / cell / organ / organism': 'Complex / Structure / Compartment / Cell / Organ / Organism',
    'complex / structure / compartment / cell / organism': 'Complex / Structure / Compartment / Cell / Organism',
    'taxonomic / evolutionary / phylogenetic group': 'Taxonomic / Evolutionary / Phylogenetic Group',
    'chemical / metabolite / cofactor / ligand': 'Chemical / Metabolite / Cofactor / Ligand',
    'treatment / perturbation / stress / mutant': 'Treatment / Perturbation / Stress / Mutant',
    'method / assay / experimental setup / parameter / sample': 'Method / Assay / Experimental Setup / Parameter / Sample',
    'biological process / pathway / function / regulatory / signaling mechanism': 'Biological Process / Pathway / Function / Regulatory / Signaling Mechanism',
    'biological process / pathway / function': 'Biological Process / Pathway / Function',
    'biological process / function': 'Biological Process / Function',
    'regulatory / signaling mechanism / metabolic pathway': 'Regulatory / Signaling Mechanism / Metabolic Pathway',
    'regulatory / signaling mechanism': 'Regulatory / Signaling Mechanism',
    'environmental / ecological / soil / climate context': 'Environmental / Ecological / Soil / Climate Context',
    'phenotype / trait / disease': 'Phenotype / Trait / Disease',
    'computational / model / algorithm / data / metric': 'Computational / Model / Algorithm / Data / Metric',
    'equipment / device / material / instrument': 'Equipment / Device / Material / Instrument',
    'clinical / epidemiological / population': 'Clinical / Epidemiological / Population',
    'social / economic / policy / management': 'Social / Economic / Policy / Management',
    'knowledge / concept / hypothesis / theoretical construct': 'Knowledge / Concept / Hypothesis / Theoretical Construct',
    'property / measurement / characterization': 'Property / Measurement / Characterization',
    'property / characterization': 'Property / Characterization',
}

def get_display_category(raw_category):
    """Map raw DB category string to clean human-readable display name."""
    if not raw_category:
        return 'Other'
    return CATEGORY_DISPLAY_NAMES.get(raw_category.strip().lower(), raw_category.strip())

def normalize_text(text):
    return unicodedata.normalize("NFKC", text.strip().upper())


def contains_special_characters(text):
    return bool(re.search(r'[^a-zA-Z0-9_ ]', text))

def clean_word(word):
    return re.sub(r'[^a-zA-Z0-9_]', '', word)


def make_abbreviations(abbreviations, elements):
    ab = {}
    return ab

def make_functional_annotations(gopredict, elements):
    fa = {}
    return fa


class Gene:
    def __init__(
        self, id, idtype, description, descriptiontype,
        inter_type=None, publication=None, p_source=None,
        species=None, basis=None,
        source_extracted_definition=None, source_generated_definition=None,
        target_extracted_definition=None, target_generated_definition=None,
        idcategory=None, targetcategory=None, relationship_label=None,
        source_identifier=None, target_identifier=None,
        extracted_associated_process=None, generated_associated_process=None,
        relevant_citations=None
    ):
        self.id = id
        self.idtype = idtype
        self.target = description
        self.targettype = descriptiontype
        self.inter_type = inter_type
        self.publication = publication
        self.p_source = p_source
        self.species = species
        self.basis = basis
        self.source_extracted_definition = source_extracted_definition
        self.source_generated_definition = source_generated_definition
        self.target_extracted_definition = target_extracted_definition
        self.target_generated_definition = target_generated_definition
        self.idcategory = get_display_category(idcategory) if idcategory else ''
        self.targetcategory = get_display_category(targetcategory) if targetcategory else ''
        self.relationship_label = relationship_label or inter_type or ''
        self.source_identifier = source_identifier or ''
        self.target_identifier = target_identifier or ''
        self.extracted_associated_process = extracted_associated_process or ''
        self.generated_associated_process = generated_associated_process or ''
        self.relevant_citations = relevant_citations or ''

    def __repr__(self):
        return str(self.__dict__)

    def __str__(self):
        return str(self.__dict__)

    def getElements(self):
        return (self.id, self.idtype, self.target, self.targettype, self.inter_type)


# Map long DB category strings to short display labels
# Uses exact strings from the data extraction prompt
_CAT_SHORT = {
    # Official categories from the GPT extraction prompt
    'GENE / PROTEIN':                                                            'Gene/Protein',
    'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE':                 'Genomic/Transcriptomic Feature',
    'PHENOTYPE / TRAIT / DISEASE':                                               'Phenotype/Disease',
    'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGAN / ORGANISM':               'Cell/Organ/Organism',
    'TAXONOMIC / EVOLUTIONARY / PHYLOGENETIC GROUP':                             'Taxonomic/Organism',
    'CHEMICAL / METABOLITE / COFACTOR / LIGAND':                                 'Chemical/Metabolite',
    'TREATMENT / PERTURBATION / STRESS / MUTANT':                                'Treatment/Stress',
    'METHOD / ASSAY / EXPERIMENTAL SETUP / PARAMETER / SAMPLE':                  'Method/Assay',
    'BIOLOGICAL PROCESS / PATHWAY / FUNCTION':                                   'Biological Process',
    'REGULATORY / SIGNALING MECHANISM':                                          'Biological Process',
    'COMPUTATIONAL / MODEL / ALGORITHM / DATA / METRIC':                         'Computational/Model',
    'ENVIRONMENTAL / ECOLOGICAL / SOIL / CLIMATE CONTEXT':                       'Environmental Context',
    'CLINICAL / EPIDEMIOLOGICAL / POPULATION':                                   'Clinical/Population',
    'EQUIPMENT / DEVICE / MATERIAL / INSTRUMENT':                                'Equipment/Material',
    'SOCIAL / ECONOMIC / POLICY / MANAGEMENT':                                   'Other',
    'KNOWLEDGE / CONCEPT / HYPOTHESIS / THEORETICAL CONSTRUCT':                  'Other',
    'PROPERTY / MEASUREMENT / CHARACTERIZATION':                                 'Other',
    # Variant forms encountered in the actual data
    'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE / GENE MUTANT':   'Genomic/Transcriptomic Feature',
    'GENOMIC / TRANSCRIPTOMIC / EPIGENOMIC FEATURE':                             'Genomic/Transcriptomic Feature',
    'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGANISM':                       'Cell/Organ/Organism',
    'BIOLOGICAL PROCESS / PATHWAY / FUNCTION / REGULATORY / SIGNALING MECHANISM': 'Biological Process',
    'BIOLOGICAL PROCESS / FUNCTION':                                             'Biological Process',
    'REGULATORY / SIGNALING MECHANISM / METABOLIC PATHWAY':                      'Biological Process',
    'PROPERTY / CHARACTERIZATION':                                               'Other',
    'TREATMENT / EXPOSURE / PERTURBATION':                                       'Treatment/Stress',
    # Short forms already in data
    'GENE/PROTEIN': 'Gene/Protein', 'PHENOTYPE': 'Phenotype/Disease',
    'CELL/ORGAN/ORGANISM': 'Cell/Organ/Organism', 'CHEMICAL': 'Chemical/Metabolite',
    'TREATMENT': 'Treatment/Stress', 'BIOLOGICAL PROCESS': 'Biological Process',
    'GENOMIC/TRANSCRIPTOMIC FEATURE': 'Genomic/Transcriptomic Feature',
    'METHOD': 'Method/Assay',
    'NA': 'Other', 'OTHER': 'Other', 'OTHERS': 'Other',
}

def _short_cat(raw_cat, raw_type=''):
    """Resolve a raw DB category (and optional type) to a short display label."""
    if raw_cat:
        hit = _CAT_SHORT.get(raw_cat.upper()) or _CAT_SHORT.get(raw_cat.upper().strip())
        if hit:
            return hit
    if raw_type:
        hit = ENTITY_CATEGORIES_DICT.get(raw_type.upper(), '')
        if hit:
            return _CAT_SHORT.get(hit, hit)
    return 'Other'


def find_preview_fast(my_search, genes, search_type):
    """
    Fast preview computation using MongoDB aggregation.
    Returns only the preview_dict entries (entity list) without fetching full relationship data.
    ~10-50x faster than find_terms for the preview page.
    """
    if not my_search:
        return []

    term = my_search[0]
    term_lower = term.lower()

    # For all search types, use entity_lookup first for fast entity discovery,
    # then query all_dic using exact $in on indexed _lower fields
    if search_type == "normal":
        # Text search on entity_lookup is fast (~0.3s)
        matched_names = [d["_id"] for d in entity_lookup.find(
            {"$text": {"$search": term}},
            {"_id": 1}
        ).limit(300)]
        if not matched_names:
            return []
    elif search_type == "substring":
        matched_names = lookup_entity_names(term, mode="substring")
        if not matched_names:
            return []
    elif search_type == "exact":
        matched_names = [term_lower]
    else:
        matched_names = [d["_id"] for d in entity_lookup.find(
            {"$text": {"$search": term}}, {"_id": 1}
        ).limit(300)]
        if not matched_names:
            return []

    matched_set = set(matched_names)

    # Count unique neighbor nodes per matched entity.
    # Use $unionWith to combine both sides before deduplicating,
    # so a neighbor that appears as both entity1 and entity2 is counted once.

    # First: project both sides into a uniform (entity, neighbor) shape, then union + dedupe
    pipeline = [
        # Side 1: entity1 matched, neighbor is entity2
        {"$match": {"entity1_lower": {"$in": matched_names}}},
        {"$project": {
            "entity": "$entity1",
            "neighbor": "$entity2",
            "type": "$entity1type",
            "category": "$entity1category",
        }},
        # Union with Side 2: entity2 matched, neighbor is entity1
        {"$unionWith": {
            "coll": "all_dic",
            "pipeline": [
                {"$match": {"entity2_lower": {"$in": matched_names}}},
                {"$project": {
                    "entity": "$entity2",
                    "neighbor": "$entity1",
                    "type": "$entity2type",
                    "category": "$entity2category",
                }},
            ]
        }},
        # Deduplicate: group by (entity, neighbor) so each neighbor counts once
        {"$group": {
            "_id": {"entity": "$entity", "neighbor": "$neighbor"},
            "type": {"$first": "$type"},
            "category": {"$first": "$category"},
        }},
        # Count unique neighbors per entity + collect ALL distinct categories
        {"$group": {
            "_id": "$_id.entity",
            "type": {"$first": "$type"},
            "categories": {"$addToSet": "$category"},
            "node_count": {"$sum": 1}
        }},
        {"$sort": {"node_count": -1}},
        {"$limit": 500}
    ]

    results_combined = list(genes.aggregate(pipeline, allowDiskUse=True))

    def resolve_vis_category(ecat, etype):
        """Return raw DB category as-is (uppercased). No short-form conversion."""
        if ecat:
            return ecat.strip().upper()
        return 'OTHER'

    # Build result tuples — already deduplicated by the pipeline
    results = []
    for r in results_combined:
        entity = r["_id"]
        etype = r.get("type", "") or ""
        raw_cats = r.get("categories", [])
        node_count = r["node_count"]
        # Join all distinct non-empty categories
        cats = sorted(set(get_display_category(c.strip()) for c in raw_cats if c and c.strip()))
        vis_cat = ", ".join(cats) if cats else "Other"
        # +1 to include the entity itself (gene.html counts all nodes including self)
        results.append((entity, etype, node_count + 1, node_count + 1, vis_cat))

    return sorted(results, key=lambda x: x[2], reverse=True)


def find_terms(my_search, genes, search_type):
    if not my_search:
        return [], [], {}, [], []

    function_start_time = time.time()
    loop_start_time = function_start_time

    forSending = []
    elements = []
    entity_counts = defaultdict(int)
    entity_connections = defaultdict(set)
    entity_cats = {}  # (entity, entity_type) -> prompt category from DB
    preview_dict = {}

    if search_type == "normal":
        search_term = my_search[0]
        # Use text index on all_dic directly — fast (~1-2s) and handles word boundaries
        # Limit to 10000 results to prevent loading 250K+ docs for common terms
        query = {"$text": {"$search": search_term}}
        result_list = list(genes.find(query).limit(10000))

        for doc in result_list:
            e1, e1t = doc["entity1"], doc.get("entity1type")
            e2, e2t = doc["entity2"], doc.get("entity2type")
            entity_counts[(e1, e1t)] += 1
            entity_counts[(e2, e2t)] += 1
            entity_connections[(e1, e1t)].add((e2, e2t))
            entity_connections[(e2, e2t)].add((e1, e1t))
            if doc.get("entity1category"):
                entity_cats[(e1, e1t)] = doc["entity1category"]
            if doc.get("entity2category"):
                entity_cats[(e2, e2t)] = doc["entity2category"]

            forSending.append(Gene(
                e1, e1t, e2, e2t,
                doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                doc.get("species"), doc.get("basis"),
                doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))
            elements.append((
                e1, e1t, e2, e2t,
                doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                doc.get("species"), doc.get("basis"),
                doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))

            for word in my_search:
                word_norm = normalize_text(word)
                e1_norm, e2_norm = normalize_text(e1), normalize_text(e2)
                if word_norm in e1_norm:
                    unique_node_count = len(entity_connections[(e1, e1t)]) + 1
                    if ((e1, e1t) not in preview_dict or
                        entity_counts[(e1, e1t)] > preview_dict[(e1, e1t)][2]):
                        e1_cat = entity_cats.get((e1, e1t), '')
                        e1_vis = PROMPT_TO_VIS_CATEGORY.get(e1_cat.upper(), ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')) if e1_cat else ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')
                        preview_dict[(e1, e1t)] = (e1, e1t, entity_counts[(e1, e1t)], unique_node_count, e1_vis)
                if word_norm in e2_norm:
                    unique_node_count = len(entity_connections[(e2, e2t)]) + 1
                    if ((e2, e2t) not in preview_dict or
                        entity_counts[(e2, e2t)] > preview_dict[(e2, e2t)][2]):
                        e2_cat = entity_cats.get((e2, e2t), '')
                        e2_vis = PROMPT_TO_VIS_CATEGORY.get(e2_cat.upper(), ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')) if e2_cat else ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')
                        preview_dict[(e2, e2t)] = (e2, e2t, entity_counts[(e2, e2t)], unique_node_count, e2_vis)

    elif search_type == "exact":
        search_term = my_search[0]
        if len(search_term.split()) > 1 or contains_special_characters(search_term):
            # Exact match on _lower field (B-tree index, very fast)
            term_lower = search_term.lower()
            query = {"$or": [
                {"entity1_lower": term_lower},
                {"entity2_lower": term_lower}
            ]}
            result_list = list(genes.find(query))
        else:
            text_search_str = f'"{search_term}"'
            query = {"$text": {"$search": text_search_str}}
            result_list = list(genes.find(query))

        for doc in result_list:
            e1, e1t = doc["entity1"], doc.get("entity1type")
            e2, e2t = doc["entity2"], doc.get("entity2type")
            e1_norm, e2_norm = normalize_text(e1), normalize_text(e2)
            entity_counts[(e1, e1t)] += 1
            entity_counts[(e2, e2t)] += 1
            entity_connections[(e1, e1t)].add((e2, e2t))
            entity_connections[(e2, e2t)].add((e1, e1t))
            if doc.get("entity1category"):
                entity_cats[(e1, e1t)] = doc["entity1category"]
            if doc.get("entity2category"):
                entity_cats[(e2, e2t)] = doc["entity2category"]

            forSending.append(Gene(
                e1, e1t, e2, e2t,
                doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                doc.get("species"), doc.get("basis"),
                doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))
            elements.append((
                e1, e1t, e2, e2t,
                doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                doc.get("species"), doc.get("basis"),
                doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))

            for word in my_search:
                word_norm = normalize_text(word)
                if e1_norm == word_norm:
                    unique_node_count = len(entity_connections[(e1, e1t)]) + 1
                    if ((e1, e1t) not in preview_dict or
                        entity_counts[(e1, e1t)] > preview_dict[(e1, e1t)][2]):
                        e1_cat = entity_cats.get((e1, e1t), '')
                        e1_vis = PROMPT_TO_VIS_CATEGORY.get(e1_cat.upper(), ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')) if e1_cat else ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')
                        preview_dict[(e1, e1t)] = (e1, e1t, entity_counts[(e1, e1t)], unique_node_count, e1_vis)
                if e2_norm == word_norm:
                    unique_node_count = len(entity_connections[(e2, e2t)]) + 1
                    if ((e2, e2t) not in preview_dict or
                        entity_counts[(e2, e2t)] > preview_dict[(e2, e2t)][2]):
                        e2_cat = entity_cats.get((e2, e2t), '')
                        e2_vis = PROMPT_TO_VIS_CATEGORY.get(e2_cat.upper(), ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')) if e2_cat else ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')
                        preview_dict[(e2, e2t)] = (e2, e2t, entity_counts[(e2, e2t)], unique_node_count, e2_vis)

    elif search_type == 'substring':
        # Use entity_lookup for fast substring discovery
        all_matched = set()
        for word in my_search:
            matched = lookup_entity_names(word, mode="substring")
            # Exclude exact matches (substring means contains but not equals)
            word_lower = word.lower()
            matched = [m for m in matched if m != word_lower]
            all_matched.update(matched)
        matched_list = list(all_matched)
        if matched_list:
            query = {"$or": [
                {"entity1_lower": {"$in": matched_list}},
                {"entity2_lower": {"$in": matched_list}}
            ]}
        else:
            query = {"_id": None}  # no results
        results = genes.find(query)
        loop_start_time = time.time()

        for doc in results:
            e1, e1t = doc["entity1"], doc["entity1type"]
            e2, e2t = doc["entity2"], doc["entity2type"]
            entity_counts[(e1, e1t)] += 1
            entity_counts[(e2, e2t)] += 1
            entity_connections[(e1, e1t)].add((e2, e2t))
            entity_connections[(e2, e2t)].add((e1, e1t))
            if doc.get("entity1category"):
                entity_cats[(e1, e1t)] = doc["entity1category"]
            if doc.get("entity2category"):
                entity_cats[(e2, e2t)] = doc["entity2category"]

            forSending.append(Gene(
                e1, e1t, e2, e2t,
                doc["edge"], doc["pubmedID"], doc["p_source"], doc["species"],
                doc["basis"], doc["source_extracted_definition"], doc["source_generated_definition"],
                doc["target_extracted_definition"], doc["target_generated_definition"],
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))
            elements.append((
                e1, e1t, e2, e2t,
                doc["edge"], doc["pubmedID"], doc["p_source"], doc["species"],
                doc["basis"], doc["source_extracted_definition"], doc["source_generated_definition"],
                doc["target_extracted_definition"], doc["target_generated_definition"]
            ))

            for word in my_search:
                pattern = re.compile(rf"{re.escape(word)}", re.IGNORECASE)
                if pattern.search(e1):
                    unique_node_count = len(entity_connections[(e1, e1t)]) + 1
                    if ((e1, e1t) not in preview_dict or
                        entity_counts[(e1, e1t)] > preview_dict[(e1, e1t)][2]):
                        e1_cat = entity_cats.get((e1, e1t), '')
                        e1_vis = PROMPT_TO_VIS_CATEGORY.get(e1_cat.upper(), ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')) if e1_cat else ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')
                        preview_dict[(e1, e1t)] = (e1, e1t, entity_counts[(e1, e1t)], unique_node_count, e1_vis)
                if pattern.search(e2):
                    unique_node_count = len(entity_connections[(e2, e2t)]) + 1
                    if ((e2, e2t) not in preview_dict or
                        entity_counts[(e2, e2t)] > preview_dict[(e2, e2t)][2]):
                        e2_cat = entity_cats.get((e2, e2t), '')
                        e2_vis = PROMPT_TO_VIS_CATEGORY.get(e2_cat.upper(), ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')) if e2_cat else ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')
                        preview_dict[(e2, e2t)] = (e2, e2t, entity_counts[(e2, e2t)], unique_node_count, e2_vis)

    elif search_type == 'non-alphanumeric':
        escaped_patterns = [re.escape(word) for word in my_search]
        combined_regex = "|".join([f'^{pat}[^a-zA-Z0-9 ]' for pat in escaped_patterns])
        compiled_regex = re.compile(combined_regex, re.IGNORECASE)
        query = {"$or": [
            {"entity1": {"$regex": compiled_regex}},
            {"entity2": {"$regex": compiled_regex}}
        ]}
        results = genes.find(query)
        loop_start_time = time.time()

        for doc in results:
            e1, e1t = doc["entity1"], doc["entity1type"]
            e2, e2t = doc["entity2"], doc["entity2type"]
            entity_counts[(e1, e1t)] += 1
            entity_counts[(e2, e2t)] += 1
            entity_connections[(e1, e1t)].add((e2, e2t))
            entity_connections[(e2, e2t)].add((e1, e1t))
            if doc.get("entity1category"):
                entity_cats[(e1, e1t)] = doc["entity1category"]
            if doc.get("entity2category"):
                entity_cats[(e2, e2t)] = doc["entity2category"]

            forSending.append(Gene(
                e1, e1t, e2, e2t,
                doc["edge"], doc["pubmedID"], doc["p_source"], doc["species"],
                doc["basis"], doc["source_extracted_definition"], doc["source_generated_definition"],
                doc["target_extracted_definition"], doc["target_generated_definition"],
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))
            elements.append((
                e1, e1t, e2, e2t,
                doc["edge"], doc["pubmedID"], doc["p_source"], doc["species"],
                doc["basis"], doc["source_extracted_definition"], doc["source_generated_definition"],
                doc["target_extracted_definition"], doc["target_generated_definition"]
            ))

            for word in my_search:
                pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
                if pattern.search(e1):
                    unique_node_count = len(entity_connections[(e1, e1t)]) + 1
                    if ((e1, e1t) not in preview_dict or
                        entity_counts[(e1, e1t)] > preview_dict[(e1, e1t)][2]):
                        e1_cat = entity_cats.get((e1, e1t), '')
                        e1_vis = PROMPT_TO_VIS_CATEGORY.get(e1_cat.upper(), ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')) if e1_cat else ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')
                        preview_dict[(e1, e1t)] = (e1, e1t, entity_counts[(e1, e1t)], unique_node_count, e1_vis)
                if pattern.search(e2):
                    unique_node_count = len(entity_connections[(e2, e2t)]) + 1
                    if ((e2, e2t) not in preview_dict or
                        entity_counts[(e2, e2t)] > preview_dict[(e2, e2t)][2]):
                        e2_cat = entity_cats.get((e2, e2t), '')
                        e2_vis = PROMPT_TO_VIS_CATEGORY.get(e2_cat.upper(), ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')) if e2_cat else ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')
                        preview_dict[(e2, e2t)] = (e2, e2t, entity_counts[(e2, e2t)], unique_node_count, e2_vis)

    elif search_type == 'paired_entity':
        patterns = [word for key in my_search for word in key.split('$')]
        escaped_patterns = [re.escape(word.lower()) for word in patterns]
        if len(escaped_patterns) == 2:
            p1, p2 = escaped_patterns
            condition1 = [{"$and": [
                {"entity1_lower": {"$regex": rf"\b{p1}\b"}},
                {"entity2_lower": {"$regex": rf"\b{p2}\b"}}
            ]}]
            condition2 = [{"$and": [
                {"entity1_lower": {"$regex": rf"\b{p2}\b"}},
                {"entity2_lower": {"$regex": rf"\b{p1}\b"}}
            ]}]
            query = {"$or": condition1 + condition2}
            results = genes.find(query)
            loop_start_time = time.time()
        else:
            results = []
            loop_start_time = time.time()

        for doc in results:
            e1, e1t = doc["entity1"], doc["entity1type"]
            e2, e2t = doc["entity2"], doc["entity2type"]
            entity_counts[(e1, e1t)] += 1
            entity_counts[(e2, e2t)] += 1
            entity_connections[(e1, e1t)].add((e2, e2t))
            entity_connections[(e2, e2t)].add((e1, e1t))
            if doc.get("entity1category"):
                entity_cats[(e1, e1t)] = doc["entity1category"]
            if doc.get("entity2category"):
                entity_cats[(e2, e2t)] = doc["entity2category"]

            forSending.append(Gene(
                e1, e1t, e2, e2t,
                doc["edge"], doc["pubmedID"], doc["p_source"], doc["species"],
                doc["basis"], doc["source_extracted_definition"], doc["source_generated_definition"],
                doc["target_extracted_definition"], doc["target_generated_definition"],
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))
            elements.append((
                e1, e1t, e2, e2t,
                doc["edge"], doc["pubmedID"], doc["p_source"], doc["species"],
                doc["basis"], doc["source_extracted_definition"], doc["source_generated_definition"],
                doc["target_extracted_definition"], doc["target_generated_definition"]
            ))

            for word in escaped_patterns:
                pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
                if pattern.search(e1):
                    unique_node_count = len(entity_connections[(e1, e1t)]) + 1
                    if ((e1, e1t) not in preview_dict or
                        entity_counts[(e1, e1t)] > preview_dict[(e1, e1t)][2]):
                        e1_cat = entity_cats.get((e1, e1t), '')
                        e1_vis = PROMPT_TO_VIS_CATEGORY.get(e1_cat.upper(), ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')) if e1_cat else ENTITY_CATEGORIES_DICT.get((e1t or '').upper(), 'OTHER')
                        preview_dict[(e1, e1t)] = (e1, e1t, entity_counts[(e1, e1t)], unique_node_count, e1_vis)
                if pattern.search(e2):
                    unique_node_count = len(entity_connections[(e2, e2t)]) + 1
                    if ((e2, e2t) not in preview_dict or
                        entity_counts[(e2, e2t)] > preview_dict[(e2, e2t)][2]):
                        e2_cat = entity_cats.get((e2, e2t), '')
                        e2_vis = PROMPT_TO_VIS_CATEGORY.get(e2_cat.upper(), ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')) if e2_cat else ENTITY_CATEGORIES_DICT.get((e2t or '').upper(), 'OTHER')
                        preview_dict[(e2, e2t)] = (e2, e2t, entity_counts[(e2, e2t)], unique_node_count, e2_vis)
    else:
        raise Exception(f"Invalid search_type: {search_type}")

    preview = sorted(preview_dict.values(), key=lambda x: (x[2], x[3]), reverse=True)

    end_time = time.time()
    function_elapsed_time = end_time - function_start_time
    loop_elapsed_time = end_time - loop_start_time
    print(f"Function Elapsed time: {function_elapsed_time:.4f} seconds")
    print(f"Loop Elapsed time: {loop_elapsed_time:.4f} seconds")

    return list(set(elements)), forSending, {}, [], preview


def generate_search_route(search_type):
    def search_route(query):
        if not query:
            query = 'DEFAULT'
        categories = [value for key, value in request.args.items() if key.startswith('category_')]
        my_search = query.upper().split(';')
        trimmed_search = [kw.strip() for kw in my_search if kw.strip()]
        collection = db["all_dic"]

        # Fast preview list via aggregation
        preview = find_preview_fast(trimmed_search, collection, search_type)
        if not preview:
            return render_template('not_found.html', search_term=query)

        # Store search params — full data loaded per-entity when user clicks
        unique_id = str(uuid.uuid4())
        cache[unique_id] = {
            "trimmed_search": trimmed_search,
            "search_type": search_type,
            "preview": preview,
            "deferred": True,
        }

        return render_template(
            'preview_search.html',
            genes=[],
            selected_categories=categories,
            cytoscape_js_code="",
            search_term=query.upper(),
            warning="",
            summary="",
            node_ab=[],
            node_fa={},
            is_node=True,
            search_type=search_type,
            preview_results=preview,
            unique_id=unique_id,
            entity_categories=PROMPT_TO_VIS_CATEGORY,
            entity_categories_csv={}
        )
    return search_route


def generate_search_route2(search_type):
    def search_route(query, entity_type):
        categories = [value for key, value in request.args.items() if key.startswith('category_')]
        uid = request.args.get('uid')
        collection = db["all_dic"]

        # Query by exact entity name on indexed _lower fields — no text search stemming
        query_lower = query.lower()
        exact_query = {"$or": [
            {"entity1_lower": query_lower},
            {"entity2_lower": query_lower}
        ]}
        forSending = []
        elements = []
        for doc in collection.find(exact_query):
            e1, e1t = doc["entity1"], doc.get("entity1type", "")
            e2, e2t = doc["entity2"], doc.get("entity2type", "")
            forSending.append(Gene(
                e1, e1t, e2, e2t,
                doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                doc.get("species"), doc.get("basis"),
                doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))
            elements.append((
                e1, e1t, e2, e2t,
                doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                doc.get("species"), doc.get("basis"),
                doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""),
                doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))
        elements = list(set(elements))
        elementsAb = {}
        node_fa = {}
        summaryText = make_text(forSending)
        preview = cache[uid]["preview"] if uid and uid in cache else []

        updatedElements = process_network(elements)
        cytoscape_js_code = generate_cytoscape_js(updatedElements, elementsAb, node_fa)
        # Collect ALL distinct categories and find original-cased entity name
        entity_categories = set()
        original_name = query  # fallback
        for g in forSending:
            if g.id.upper() == query.upper():
                original_name = g.id  # use DB casing
                if g.idcategory:
                    entity_categories.add(g.idcategory)
            if g.target.upper() == query.upper():
                original_name = g.target  # use DB casing
                if g.targetcategory:
                    entity_categories.add(g.targetcategory)
        cats_str = ", ".join(sorted(c for c in entity_categories if c and c != 'Other')) or ""
        patterns_title = f"{original_name} [{cats_str}]" if cats_str else original_name

        if forSending:
            return render_template(
                'gene.html',
                genes=forSending,
                selected_categories=categories,
                cytoscape_js_code=cytoscape_js_code,
                search_term=patterns_title,
                warning="",
                summary=summaryText,
                node_ab=[],
                node_fa=node_fa,
                is_node=True,
                search_type=search_type,
                preview_results=preview
            )
        else:
            return render_template('not_found.html', search_term=query)
    return search_route


def generate_multi_search_route(search_type):
    bracket_pattern = re.compile(r"^(.*)\[(.*)\]$")

    def search_route(multi_query):
        if request.method == 'POST':
            # Accept both JSON body and form data (hidden form submission)
            data = request.get_json(silent=True)
            if not data:
                raw_json = request.form.get("selected_entities_json", "{}")
                data = json.loads(raw_json) if raw_json else {}
            raw_pairs = data.get("selected_entities", [])
            if not raw_pairs:
                return render_template('not_found.html', search_term=multi_query)

            # Extract entity names from selected pairs (format: "entity_name|entity_type|display_category")
            selected_entity_names = set()
            display_labels = []
            for item in raw_pairs:
                parts = item.split('|')
                entityName = parts[0] if len(parts) > 0 else item
                entityType = parts[1] if len(parts) > 1 else ""
                displayCat = parts[2] if len(parts) > 2 else entityType
                selected_entity_names.add(entityName.upper())
                display_labels.append(f"{entityName} [{displayCat}]" if displayCat else entityName)

            # Query MongoDB directly for the selected entities
            collection = db["all_dic"]
            name_list_lower = [n.lower() for n in selected_entity_names]
            query = {"$or": [
                {"entity1_lower": {"$in": name_list_lower}},
                {"entity2_lower": {"$in": name_list_lower}}
            ]}
            result_list = list(collection.find(query).limit(10000))

            forSending = []
            elements = []
            for doc in result_list:
                e1, e1t = doc["entity1"], doc.get("entity1type", "")
                e2, e2t = doc["entity2"], doc.get("entity2type", "")
                if e1.upper() in selected_entity_names or e2.upper() in selected_entity_names:
                    forSending.append(Gene(
                        e1, e1t, e2, e2t,
                        doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                        doc.get("species"), doc.get("basis"),
                        doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                        doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                        doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                        doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                        doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                        doc.get("relevant_citations", "")
                    ))
                    elements.append((
                        e1, e1t, e2, e2t,
                        doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                        doc.get("species"), doc.get("basis"),
                        doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                        doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                        doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                        doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                        doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                        doc.get("relevant_citations", "")
                    ))

            if not forSending:
                return render_template('not_found.html', search_term=multi_query)

            updatedElements = process_network(list(set(elements)))
            cytoscape_js_code = generate_cytoscape_js(updatedElements, {}, {})
            finalSummaryText = make_text(forSending)
            all_pairs_label = ", ".join(display_labels)
            number_papers = len({g.publication for g in forSending})

            return render_template(
                'gene.html',
                genes=forSending,
                cytoscape_js_code=cytoscape_js_code,
                search_term=all_pairs_label,
                number_papers=number_papers,
                warning="",
                summary=finalSummaryText,
                node_ab=[],
                node_fa={},
                is_node=True,
                search_type=search_type,
                preview_results=[]
            )

        # GET fallback — redirect back to search
        search_term = multi_query.replace("_multi", "")
        return redirect(url_for('normal', query=search_term) if search_type == 'normal'
                        else url_for('substring', query=search_term))
    return search_route


def generate_search_route3(search_type):
    def search_route(query):
        categories = [value for key, value in request.args.items() if key.startswith('category_')]
        try:
            my_search = query.strip()
        except Exception as e:
            my_search = 'DEFAULT'

        forSending, preview = [], []
        cytoscape_js_code = ""
        summaryText = ""
        node_ab = []
        node_fa = []

        if my_search:
            split_search = my_search.upper().split(';')
            trimmed_search = [keyword.strip() for keyword in split_search if keyword.strip()]
            all_dic_collection = db["all_dic"]
            elements, forSending, elementsAb, node_fa, preview = find_terms(
                trimmed_search, all_dic_collection, search_type
            )
            updatedElements = process_network(elements)
            cytoscape_js_code = generate_cytoscape_js(updatedElements, elementsAb, node_fa)
            summaryText = make_text(forSending)

        if forSending:
            display_search_term = my_search.upper()
            return render_template(
                'gene.html',
                genes=forSending,
                selected_categories=categories,
                cytoscape_js_code=cytoscape_js_code,
                search_term=display_search_term,
                warning="",
                summary=summaryText,
                node_ab=node_ab,
                node_fa=node_fa,
                is_node=True,
                search_type=search_type,
                preview_results=preview
            )
        else:
            return render_template('not_found.html', search_term=my_search)
    return search_route
