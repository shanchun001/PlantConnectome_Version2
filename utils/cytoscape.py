'''
This module contains helper functions needed to generate the CytoscapeJS graph.
'''
import networkx as nx
import json
import pandas as pd

def graphConverter(graph, ref):
    updatedElements = []
    for k, v in graph.adjacency():
        source = str(k[0]).replace("'", "").replace('"', '')
        if v:
            for i, j in v.items():
                target = str(i).replace("'", "").replace('"', '')
                for p, q in j.items():
                    type = str(q['relation']).replace("'", "").replace('"', '')
                    sourcetype = str(q['sourcetype']).replace("'", "").replace('"', '')
                    targettype = str(q['targettype']).replace("'", "").replace('"', '')
                    p_source = str(q['p_source']).replace("'", "").replace('"', '')
                    pmid = str(q['pmid']).replace("'", "").replace('"', '')
                    species = str(q['species']).replace("'", "").replace('"', '')
                    basis = str(q['basis']).replace("'", "").replace('"', '')
                    source_extracted_definition = str(q['source_extracted_definition']).replace("'", "").replace('"', '')
                    source_generated_definition = str(q['source_generated_definition']).replace("'", "").replace('"', '')
                    target_extracted_definition = str(q['target_extracted_definition']).replace("'", "").replace('"', '')
                    target_generated_definition = str(q['target_generated_definition']).replace("'", "").replace('"', '')
                    sourcecategory = str(q.get('sourcecategory', '')).replace("'", "").replace('"', '')
                    targetcategory = str(q.get('targetcategory', '')).replace("'", "").replace('"', '')
                    relationship_label = str(q.get('relationship_label', '')).replace("'", "").replace('"', '')
                    if ((source, k[1]), target) in ref:
                        updatedElements.append({
                            "source": source, "sourcetype": sourcetype,
                            "target": target, "targettype": targettype,
                            "interaction": type, "p_source": p_source,
                            "pmid": pmid, "species": species, "basis": basis,
                            "source_extracted_definition": source_extracted_definition,
                            "source_generated_definition": source_generated_definition,
                            "target_extracted_definition": target_extracted_definition,
                            "target_generated_definition": target_generated_definition,
                            "sourcecategory": sourcecategory,
                            "targetcategory": targetcategory,
                            "relationship_label": relationship_label
                        })
    return updatedElements

def edgeConverter(elements):
    updatedElements = []
    for i in elements:
        updatedElements.append({
            "source": str(i[0]).replace("'", "").replace('"', '').replace('\n', ''),
            "sourcetype": str(i[1]).replace("'", "").replace('"', '').replace('\n', ''),
            "target": str(i[2]).replace("'", "").replace('"', '').replace('\n', ''),
            "targettype": str(i[3]).replace("'", "").replace('"', '').replace('\n', ''),
            "interaction": str(i[4]).replace("'", "").replace('"', '').replace('\n', ''),
            "pmid": str(i[5]).replace("'", "").replace('"', '').replace('\n', ''),
            "p_source": str(i[6]).replace("'", "").replace('"', '').replace('\n', ''),
            "species": str(i[7]).replace("'", "").replace('"', '').replace('\n', ''),
            "basis": str(i[8]).replace("'", "").replace('"', '').replace('\n', ''),
            "source_extracted_definition": str(i[9]).replace("'", "").replace('"', '').replace('\n', ''),
            "source_generated_definition": str(i[10]).replace("'", "").replace('"', '').replace('\n', ''),
            "target_extracted_definition": str(i[11]).replace("'", "").replace('"', '').replace('\n', ''),
            "target_generated_definition": str(i[12]).replace("'", "").replace('"', '').replace('\n', ''),
            "sourcecategory": str(i[13]).replace("'", "").replace('"', '').replace('\n', '') if len(i) > 13 else '',
            "targetcategory": str(i[14]).replace("'", "").replace('"', '').replace('\n', '') if len(i) > 14 else '',
            "relationship_label": str(i[15]).replace("'", "").replace('"', '').replace('\n', '') if len(i) > 15 else ''
        })
    return updatedElements

def nodeDegreeFilter(graph):
    nodesToKeep = []
    totalDegree = 0
    degrees = sorted(graph.degree, key=lambda x: x[1], reverse=True)
    for node, degree in degrees:
        if totalDegree <= 500 or not nodesToKeep:
            nodesToKeep.append(node)
            totalDegree += degree
        if totalDegree > 500:
            break
    edges_to_keep = {edge for node in nodesToKeep for edge in list(graph.in_edges(node)) + list(graph.out_edges(node))}
    ref = {edge: 1 for edge in edges_to_keep}
    return graph, ref

def process_network(elements):
    elements = list({tuple(e) for e in elements})
    if len(elements) <= 100000:
        return edgeConverter(elements)
    G = nx.MultiDiGraph()
    for e in elements:
        G.add_edge(
            e[0], e[2],
            sourcetype=e[1], targettype=e[3],
            relation=e[4], pmid=e[5], p_source=e[6],
            species=e[7], basis=e[8],
            source_extracted_definition=e[9], source_generated_definition=e[10],
            target_extracted_definition=e[11], target_generated_definition=e[12],
            sourcecategory=e[13] if len(e) > 13 else '',
            targetcategory=e[14] if len(e) > 14 else '',
            relationship_label=e[15] if len(e) > 15 else '',
        )
    G, ref = nodeDegreeFilter(G)
    return graphConverter(G, ref)

ENTITY_CATEGORIES = pd.read_csv('utils/Connectome_entities.csv')
ENTITY_CATEGORIES_DICT = {
    row.iloc[0]: row.iloc[2] for _, row in ENTITY_CATEGORIES.iterrows()
}

with open('utils/Connectome_relationships.json', 'r') as file:
    RELATIONSHIP_CATEGORIES = json.load(file)


def normalize_relationship_label(label):
    """Strip brackets and normalize a relationship_label like '[Regulation / Control]' to 'REGULATION/CONTROL'."""
    if not label:
        return ''
    label = label.strip()
    if label.startswith('[') and label.endswith(']'):
        label = label[1:-1]
    # Normalize: remove spaces around slashes, uppercase
    return '/'.join(part.strip() for part in label.upper().split('/'))


def generate_cytoscape_js(elements, ab, fa):

    def escape_js_string(value):
        if not value:
            return ''
        return str(value).replace("'", "").replace('"', '').replace('\n', '').replace('\\', '').replace('`', '').replace('${', '')

    # Canonical node category names (must match network.js nodeStyles keys)
    _CANONICAL_NODE_CATS = [
        'GENE / PROTEIN',
        'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE',
        'PHENOTYPE / TRAIT / DISEASE',
        'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGAN / ORGANISM',
        'TAXONOMIC / EVOLUTIONARY / PHYLOGENETIC GROUP',
        'CHEMICAL / METABOLITE / COFACTOR / LIGAND',
        'TREATMENT / PERTURBATION / STRESS / MUTANT',
        'METHOD / ASSAY / EXPERIMENTAL SETUP / PARAMETER / SAMPLE',
        'BIOLOGICAL PROCESS / PATHWAY / FUNCTION',
        'REGULATORY / SIGNALING MECHANISM',
        'COMPUTATIONAL / MODEL / ALGORITHM / DATA / METRIC',
        'ENVIRONMENTAL / ECOLOGICAL / SOIL / CLIMATE CONTEXT',
        'CLINICAL / EPIDEMIOLOGICAL / POPULATION',
        'EQUIPMENT / DEVICE / MATERIAL / INSTRUMENT',
        'SOCIAL / ECONOMIC / POLICY / MANAGEMENT',
        'KNOWLEDGE / CONCEPT / HYPOTHESIS / THEORETICAL CONSTRUCT',
        'PROPERTY / MEASUREMENT / CHARACTERIZATION',
    ]

    def get_node_category(node_category, node_type):
        """Normalize DB category to closest canonical name for network.js styling."""
        if not node_category:
            return 'OTHER'
        raw = node_category.strip().upper()
        # Split on | or ; to handle multi-category values
        parts = [p.strip() for p in raw.replace('|', ';').split(';') if p.strip()]
        raw = parts[0] if parts else raw
        # Exact match
        if raw in _CANONICAL_NODE_CATS:
            return raw
        # Prefix match: find the canonical key that best matches
        for canon in _CANONICAL_NODE_CATS:
            if raw.startswith(canon[:20]) or canon.startswith(raw[:20]):
                return canon
        # Keyword match: check if key distinguishing words appear
        raw_words = set(raw.split())
        best_score, best_canon = 0, 'OTHER'
        for canon in _CANONICAL_NODE_CATS:
            canon_words = set(canon.split())
            overlap = len(raw_words & canon_words)
            if overlap > best_score:
                best_score = overlap
                best_canon = canon
        return best_canon if best_score >= 2 else 'OTHER'

    def get_edge_category(relationship_label, interaction):
        """Return the relationship_label as-is (it is the category from the prompt)."""
        if relationship_label:
            label = relationship_label.strip()
            # Normalise capitalisation to Title Case
            return label
        return interaction or 'NA'

    # ── Nodes: merge by entity name (same name = same node) ──────────────
    node_data = {}  # name -> {category: count, type: most_common_type}
    node_type_counts = {}  # name -> {type: count}
    for edge in elements:
        for name, ntype, ncat in [
            (edge["source"], edge["sourcetype"], edge.get("sourcecategory", "")),
            (edge["target"], edge["targettype"], edge.get("targetcategory", ""))
        ]:
            cat = get_node_category(ncat, ntype)
            if name not in node_data:
                node_data[name] = {cat: 1}
                node_type_counts[name] = {ntype: 1}
            else:
                node_data[name][cat] = node_data[name].get(cat, 0) + 1
                node_type_counts[name][ntype] = node_type_counts[name].get(ntype, 0) + 1

    nodes_js = []
    for name, cat_counts in node_data.items():
        # Pick category with highest count (exclude OTHER if others exist)
        non_other = {c: v for c, v in cat_counts.items() if c != 'OTHER'}
        best_cat = max(non_other, key=non_other.get) if non_other else 'OTHER'
        best_type = max(node_type_counts[name], key=node_type_counts[name].get)
        safe_name = escape_js_string(name)
        nodes_js.append(
            f"{{ data: {{ id: '{safe_name}', originalId: '{safe_name}', type: '{escape_js_string(best_type)}', category: '{escape_js_string(best_cat)}' }} }}"
        )

    # ── Edges: merge by (source, target, edge_category) ─────────────────
    edge_map = {}  # (src, tgt, cat) -> {pmids, interaction, first_edge_data}
    for edge in elements:
        src = edge["source"]
        tgt = edge["target"]
        rel_label = edge.get("relationship_label", "")
        interaction = edge.get("interaction", "")
        cat = get_edge_category(rel_label, interaction)
        key = (src, tgt, cat)
        pmid = edge.get("pmid", "")
        if key not in edge_map:
            edge_map[key] = {
                "pmids": {pmid} if pmid else set(),
                "category": cat,
                "interaction": interaction,  # actual relationship verb, not the category
                "edge": edge
            }
        else:
            if pmid:
                edge_map[key]["pmids"].add(pmid)

    edges_js = []
    for i, ((src, tgt, cat), data) in enumerate(edge_map.items()):
        e = data["edge"]
        pmids_str = ", ".join(sorted(data["pmids"]))
        edges_js.append(f"""{{
            data: {{
                id: 'edge{i}',
                source: '{escape_js_string(src)}',
                sourcetype: '{escape_js_string(e["sourcetype"])}',
                target: '{escape_js_string(tgt)}',
                targettype: '{escape_js_string(e["targettype"])}',
                category: '{escape_js_string(cat)}',
                interaction: '{escape_js_string(data["interaction"])}',
                p_source: '{escape_js_string(e["p_source"])}',
                pmid: '{escape_js_string(pmids_str)}',
                species: '{escape_js_string(e["species"])}',
                basis: '{escape_js_string(e["basis"])}',
                source_extracted_definition: '{escape_js_string(e["source_extracted_definition"])}',
                source_generated_definition: '{escape_js_string(e["source_generated_definition"])}',
                target_extracted_definition: '{escape_js_string(e["target_extracted_definition"])}',
                target_generated_definition: '{escape_js_string(e["target_generated_definition"])}'
            }}
        }}""")

    with open('network.js', 'r') as template_file:
        template = template_file.read()

    return template.replace(
        '_INSERT_NODES_HERE_', ', '.join(nodes_js)
    ).replace(
        '_INSERT_EDGES_HERE_', ', '.join(edges_js)
    ).replace('REPLACE_AB', json.dumps(ab)).replace('REPLACE_FA', json.dumps(fa))


# Mapping from prompt entity categories to visualization categories
# Each category maps to itself (exact names from GPT extraction prompt)
PROMPT_TO_VIS_CATEGORY = {
    # Map long prompt category names → short vis category names (matching CAT_ALIAS in templates)
    'GENE / PROTEIN': 'GENE/PROTEIN',
    'PHENOTYPE / TRAIT / DISEASE': 'PHENOTYPE',
    'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGAN / ORGANISM': 'CELL/ORGAN/ORGANISM',
    'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGANISM': 'CELL/ORGAN/ORGANISM',
    'TAXONOMIC / EVOLUTIONARY / PHYLOGENETIC GROUP': 'CELL/ORGAN/ORGANISM',
    'CHEMICAL / METABOLITE / COFACTOR / LIGAND': 'CHEMICAL',
    'TREATMENT / PERTURBATION / STRESS / MUTANT': 'TREATMENT',
    'METHOD / ASSAY / EXPERIMENTAL SETUP / PARAMETER / SAMPLE': 'METHOD',
    'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE': 'GENOMIC/TRANSCRIPTOMIC FEATURE',
    'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE / GENE MUTANT': 'GENOMIC/TRANSCRIPTOMIC FEATURE',
    'GENOMIC / TRANSCRIPTOMIC / EPIGENOMIC FEATURE': 'GENOMIC/TRANSCRIPTOMIC FEATURE',
    'BIOLOGICAL PROCESS / PATHWAY / FUNCTION': 'BIOLOGICAL PROCESS',
    'BIOLOGICAL PROCESS / FUNCTION': 'BIOLOGICAL PROCESS',
    'BIOLOGICAL PROCESS / PATHWAY / FUNCTION / REGULATORY / SIGNALING MECHANISM': 'BIOLOGICAL PROCESS',
    'REGULATORY / SIGNALING MECHANISM': 'BIOLOGICAL PROCESS',
    'REGULATORY / SIGNALING MECHANISM / METABOLIC PATHWAY': 'BIOLOGICAL PROCESS',
    'COMPUTATIONAL / MODEL / ALGORITHM / DATA / METRIC': 'METHOD',
    'ENVIRONMENTAL / ECOLOGICAL / SOIL / CLIMATE CONTEXT': 'TREATMENT',
    'CLINICAL / EPIDEMIOLOGICAL / POPULATION': 'CELL/ORGAN/ORGANISM',
    'EQUIPMENT / DEVICE / MATERIAL / INSTRUMENT': 'METHOD',
    'SOCIAL / ECONOMIC / POLICY / MANAGEMENT': 'OTHER',
    'KNOWLEDGE / CONCEPT / HYPOTHESIS / THEORETICAL CONSTRUCT': 'OTHER',
    'PROPERTY / MEASUREMENT / CHARACTERIZATION': 'OTHER',
    'PROPERTY / CHARACTERIZATION': 'OTHER',
    # Short form keys (in case they appear in data)
    'GENE/PROTEIN': 'GENE/PROTEIN',
    'PHENOTYPE': 'PHENOTYPE',
    'CELL/ORGAN/ORGANISM': 'CELL/ORGAN/ORGANISM',
    'CHEMICAL': 'CHEMICAL',
    'TREATMENT': 'TREATMENT',
    'METHOD': 'METHOD',
    'BIOLOGICAL PROCESS': 'BIOLOGICAL PROCESS',
    'GENOMIC/TRANSCRIPTOMIC FEATURE': 'GENOMIC/TRANSCRIPTOMIC FEATURE',
    'GENE IDENTIFIER': 'GENE IDENTIFIER',
    'PROCESS': 'BIOLOGICAL PROCESS',
    'NA': 'OTHER',
}
