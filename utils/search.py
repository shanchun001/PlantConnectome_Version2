import unicodedata
import re
import time
import uuid
from collections import defaultdict

from flask import request, render_template, redirect, url_for

from mongo import db
from my_cache import cache

entity_lookup = db["entity_lookup"]

def lookup_entity_names(search_term, mode="substring"):
    """
    Use entity_lookup collection for fast entity name discovery.
    Returns a list of lowercase entity names matching the search term.
    mode: 'substring' (prefix-anchored regex on _id, uses B-tree index), 'exact'
    """
    term_lower = search_term.lower()
    limit = 500
    if mode == "substring":
        # Prefix-anchored regex uses B-tree index on _id → fast
        # No sort (sorting defeats index use on 11M docs)
        results = entity_lookup.find(
            {"_id": {"$regex": "^" + re.escape(term_lower)}},
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
        idcategory=None, targetcategory=None, relationship_label=None
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
        self.idcategory = PROMPT_TO_VIS_CATEGORY.get((idcategory or '').upper(), '') if idcategory else ''
        self.targetcategory = PROMPT_TO_VIS_CATEGORY.get((targetcategory or '').upper(), '') if targetcategory else ''
        self.relationship_label = relationship_label or inter_type or ''

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
    'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE':                 'Genomic Feature',
    'PHENOTYPE / TRAIT / DISEASE':                                               'Phenotype',
    'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGAN / ORGANISM':               'Cell/Organism',
    'TAXONOMIC / EVOLUTIONARY / PHYLOGENETIC GROUP':                             'Taxonomy',
    'CHEMICAL / METABOLITE / COFACTOR / LIGAND':                                 'Chemical',
    'TREATMENT / PERTURBATION / STRESS / MUTANT':                                'Treatment',
    'METHOD / ASSAY / EXPERIMENTAL SETUP / PARAMETER / SAMPLE':                  'Method',
    'BIOLOGICAL PROCESS / PATHWAY / FUNCTION':                                   'Biological Process',
    'REGULATORY / SIGNALING MECHANISM':                                          'Regulatory/Signaling',
    'COMPUTATIONAL / MODEL / ALGORITHM / DATA / METRIC':                         'Computational',
    'ENVIRONMENTAL / ECOLOGICAL / SOIL / CLIMATE CONTEXT':                       'Environment',
    'CLINICAL / EPIDEMIOLOGICAL / POPULATION':                                   'Clinical',
    'EQUIPMENT / DEVICE / MATERIAL / INSTRUMENT':                                'Equipment',
    'SOCIAL / ECONOMIC / POLICY / MANAGEMENT':                                   'Social/Policy',
    'KNOWLEDGE / CONCEPT / HYPOTHESIS / THEORETICAL CONSTRUCT':                  'Concept',
    'PROPERTY / MEASUREMENT / CHARACTERIZATION':                                 'Property',
    # Variant forms encountered in the actual data
    'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE / GENE MUTANT':   'Genomic Feature',
    'GENOMIC / TRANSCRIPTOMIC / EPIGENOMIC FEATURE':                             'Genomic Feature',
    'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGANISM':                       'Cell/Organism',
    'BIOLOGICAL PROCESS / PATHWAY / FUNCTION / REGULATORY / SIGNALING MECHANISM': 'Biological Process',
    'BIOLOGICAL PROCESS / FUNCTION':                                             'Biological Process',
    'REGULATORY / SIGNALING MECHANISM / METABOLIC PATHWAY':                      'Regulatory/Signaling',
    'PROPERTY / CHARACTERIZATION':                                               'Property',
    'TREATMENT / EXPOSURE / PERTURBATION':                                       'Treatment',
    # Short forms already in data
    'GENE/PROTEIN': 'Gene/Protein', 'PHENOTYPE': 'Phenotype',
    'CELL/ORGAN/ORGANISM': 'Cell/Organism', 'CHEMICAL': 'Chemical',
    'TREATMENT': 'Treatment', 'BIOLOGICAL PROCESS': 'Biological Process',
    'GENOMIC/TRANSCRIPTOMIC FEATURE': 'Genomic Feature',
    'METHOD': 'Method',
    'NA': 'Mixed', 'OTHER': 'Other', 'OTHERS': 'Other',
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

    # Use $in on indexed _lower fields — very fast
    match_q = {"$or": [
        {"entity1_lower": {"$in": matched_names}},
        {"entity2_lower": {"$in": matched_names}}
    ]}

    # Aggregate entity1 side
    pipeline_e1 = [
        {"$match": match_q},
        {"$group": {
            "_id": {"entity": "$entity1", "type": "$entity1type", "category": "$entity1category"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 200}
    ]

    pipeline_e2 = [
        {"$match": match_q},
        {"$group": {
            "_id": {"entity": "$entity2", "type": "$entity2type", "category": "$entity2category"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 200}
    ]

    # Run both aggregations
    results_e1 = list(genes.aggregate(pipeline_e1, allowDiskUse=True))
    results_e2 = list(genes.aggregate(pipeline_e2, allowDiskUse=True))

    # Merge by entity name.
    # Track: most common entity_type (for the URL), display category, total count
    seen = {}  # entity -> [best_etype, best_count, total_count, vis_cat]
    for r in results_e1 + results_e2:
        entity = r["_id"]["entity"]
        etype = r["_id"].get("type", "") or ""
        ecat = r["_id"].get("category", "") or ""
        count = r["count"]
        vis_cat = _short_cat(ecat, etype)
        if entity not in seen:
            seen[entity] = [etype, count, count, vis_cat]
        else:
            entry = seen[entity]
            entry[2] += count  # sum total count
            if count > entry[1]:  # keep most common type for the URL
                entry[0] = etype
                entry[1] = count
                entry[3] = vis_cat  # update category to match dominant type

    # Return as tuples: (entity, entity_type, count, count, vis_cat)
    # - entity_type (index 1): most common type — used in the URL for gene.html route
    # - vis_cat (index 4): display category label — shown in the table column
    results = [
        (entity, entry[0], entry[2], entry[2], entry[3])
        for entity, entry in seen.items()
    ]
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
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", "")
            ))
            elements.append((
                e1, e1t, e2, e2t,
                doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                doc.get("species"), doc.get("basis"),
                doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", "")
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
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", "")
            ))
            elements.append((
                e1, e1t, e2, e2t,
                doc.get("edge"), doc.get("pubmedID"), doc.get("p_source"),
                doc.get("species"), doc.get("basis"),
                doc.get("source_extracted_definition"), doc.get("source_generated_definition"),
                doc.get("target_extracted_definition"), doc.get("target_generated_definition"),
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", "")
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
                doc["target_extracted_definition"], doc["target_generated_definition"]
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
                doc["target_extracted_definition"], doc["target_generated_definition"]
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
                doc["target_extracted_definition"], doc["target_generated_definition"]
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
        start_time = time.time()
        categories = [value for key, value in request.args.items() if key.startswith('category_')]
        if not query:
            query = 'DEFAULT'
        if len(query) > 0:
            my_search = query.upper().split(';')
            trimmed_search = [keyword.strip() for keyword in my_search if keyword.strip()]
            collection = db["all_dic"]

            # Fast path: use aggregation to build entity preview list only
            # Full relationship data is deferred until user selects entities
            preview = find_preview_fast(trimmed_search, collection, search_type)

            if preview:
                unique_id = str(uuid.uuid4())
                # Store minimal deferred info — full data computed on demand
                cache[unique_id] = {
                    "deferred": True,
                    "trimmed_search": trimmed_search,
                    "search_type": search_type,
                    "preview": preview,
                }
                patterns_title = query.upper()
                return render_template(
                    'preview_search.html',
                    genes=[],
                    selected_categories=categories,
                    cytoscape_js_code="",
                    search_term=patterns_title,
                    warning="",
                    summary="",
                    node_ab=[],
                    node_fa={},
                    is_node=True,
                    search_type=search_type,
                    preview_results=preview,
                    unique_id=unique_id,
                    entity_categories=PROMPT_TO_VIS_CATEGORY,
                    entity_categories_csv={}  # Not needed for preview — saves 13MB per request
                )
            else:
                return render_template('not_found.html', search_term=query)
        return render_template('not_found.html', search_term=query)
    return search_route


def generate_search_route2(search_type):
    def search_route(query, entity_type):
        categories = [value for key, value in request.args.items() if key.startswith('category_')]
        uid = request.args.get('uid')
        if not uid:
            return "Error: No unique_id provided in ?uid=."
        if uid not in cache:
            return "Error: This search data is not available or may have expired."
        stored_data = cache[uid]
        # Compute full data on demand if deferred
        if stored_data.get("deferred"):
            collection = db["all_dic"]
            elements, forSending, elementsAb, node_fa, preview = find_terms(
                stored_data["trimmed_search"], collection, stored_data["search_type"]
            )
            summaryText = make_text(forSending)
            stored_data.update({
                "elements": elements, "forSending": forSending,
                "elementsAb": elementsAb, "node_fa": node_fa,
                "summaryText": summaryText, "deferred": False
            })
        else:
            elements = stored_data["elements"]
            forSending = stored_data["forSending"]
            elementsAb = stored_data["elementsAb"]
            node_fa = stored_data["node_fa"]
            preview = stored_data["preview"]
            summaryText = stored_data["summaryText"]

        # Filter by entity name; entity_type from URL may be a category string,
        # so match by name only (or also by type if it's a raw type like 'gene')
        filtered_forSending = [
            g for g in forSending
            if (g.id == query or g.target == query)
        ]
        filtered_elements = [
            e for e in elements
            if (e[0] == query or e[2] == query)
        ]
        updatedElements = process_network(filtered_elements)
        cytoscape_js_code = generate_cytoscape_js(updatedElements, elementsAb, node_fa)
        patterns_title = f"{query.upper()} [{entity_type.upper()}]" if entity_type else query.upper()

        if filtered_forSending:
            return render_template(
                'gene.html',
                genes=filtered_forSending,
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
            data = request.get_json(silent=True) or {}
            selected_list = data.get("selected_entities", [])
            search_term = data.get("search_term", "")
            uid = request.args.get("uid")
            if not uid:
                return render_template('error.html', message="No uid provided in ?uid=..."), 400
            if uid not in cache:
                return render_template('error.html', message="Session ended or not in cache."), 400
            cache[uid]["multi_selected_entities"] = selected_list
            if not search_term:
                search_term = "placeholder"
            return redirect(url_for(
                request.endpoint,
                multi_query=f"{search_term}_multi",
                uid=uid
            ))

        uid = request.args.get("uid")
        if not uid:
            return render_template('error.html', message="Session ended. Please re-run the search.")
        if uid not in cache:
            return render_template('error.html', message="Session ended or not in cache.")

        stored_data = cache[uid]
        # Compute full data on demand if deferred
        if stored_data.get("deferred"):
            collection = db["all_dic"]
            elements, forSending, elementsAb, node_fa, preview = find_terms(
                stored_data["trimmed_search"], collection, stored_data["search_type"]
            )
            summaryText = make_text(forSending)
            stored_data.update({
                "elements": elements, "forSending": forSending,
                "elementsAb": elementsAb, "node_fa": node_fa,
                "summaryText": summaryText, "deferred": False
            })
        else:
            elements = stored_data.get("elements", [])
            forSending = stored_data.get("forSending", [])
            elementsAb = stored_data.get("elementsAb", {})
            node_fa = stored_data.get("node_fa", [])
            preview = stored_data.get("preview", [])
            summaryText = stored_data.get("summaryText", "")

        raw_pairs = stored_data.get("multi_selected_entities", [])
        pairs = []
        for item in raw_pairs:
            if '|' in item:
                entityName, entityType = item.split('|', 1)
                pairs.append(f"{entityName} [{entityType}]")
            else:
                pairs.append(item)

        if not pairs:
            return render_template('not_found.html', search_term=multi_query)

        combined_elements = set()
        combined_forSending = []
        combined_preview = []
        display_labels = []

        for pair in pairs:
            match = bracket_pattern.match(pair)
            if match:
                entityName = match.group(1).strip()
                entityType = match.group(2).strip()
                display_label = f"{entityName} [{entityType}]"
            else:
                entityName = pair
                entityType = "UNKNOWN"
                display_label = f"{entityName} [UNKNOWN]"
            display_labels.append(display_label)

            partial_forSending = [
                g for g in forSending
                if ((g.id.upper() == entityName.upper() and g.idtype.upper() == entityType.upper())
                    or (g.target.upper() == entityName.upper() and g.targettype.upper() == entityType.upper()))
            ]
            partial_elements = [
                e for e in elements
                if ((e[0].upper() == entityName.upper() and e[1].upper() == entityType.upper())
                    or (e[2].upper() == entityName.upper() and e[3].upper() == entityType.upper()))
            ]
            combined_forSending.extend(partial_forSending)
            combined_elements.update(partial_elements)

        if not combined_forSending:
            return render_template('not_found.html', search_term=multi_query)

        updatedElements = process_network(list(combined_elements))
        cytoscape_js_code = generate_cytoscape_js(updatedElements, {}, node_fa)
        finalSummaryText = make_text(combined_forSending)
        all_pairs_label = ", ".join(label.upper() for label in display_labels)
        number_papers = len({g.publication for g in combined_forSending})

        return render_template(
            'gene.html',
            genes=combined_forSending,
            cytoscape_js_code=cytoscape_js_code,
            search_term=all_pairs_label,
            number_papers=number_papers,
            warning="",
            summary=finalSummaryText,
            node_ab=[],
            node_fa=node_fa,
            is_node=True,
            search_type=search_type,
            preview_results=combined_preview
        )
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
