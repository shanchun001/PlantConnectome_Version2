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
    nodes = set()
    edges = []

    def escape_js_string(value):
        if not value:
            return ''
        return str(value).replace("'", "").replace('"', '').replace('\n', '').replace('\\', '').replace('`', '').replace('${', '')

    def format_node(name, node_type, node_category=''):
        # Use stored category from KG if available, otherwise fall back to CSV
        if node_category:
            category = PROMPT_TO_VIS_CATEGORY.get(node_category.upper(), 'OTHER')
        else:
            category = ENTITY_CATEGORIES_DICT.get(node_type.upper(), 'OTHER')
        return f"{escape_js_string(name)}|{escape_js_string(node_type)}|{category}"

    def get_relationship_category(interaction, relationship_label=''):
        # Use stored relationship_label if available
        if relationship_label:
            normalized = normalize_relationship_label(relationship_label)
            # Check if it matches any key in RELATIONSHIP_CATEGORIES
            for category in RELATIONSHIP_CATEGORIES:
                if normalized == category or normalized.startswith(category.split('/')[0]):
                    return category
            # If it starts with "Others:", map to OTHERS
            if normalized.startswith('OTHERS'):
                return 'OTHERS'
            return normalized
        # Fall back to verb synonym lookup
        interaction_upper = interaction.upper()
        for category, relationships in RELATIONSHIP_CATEGORIES.items():
            if interaction_upper in relationships:
                return category
        return "NA"

    for i, edge in enumerate(elements):
        source_cat = edge.get("sourcecategory", "")
        target_cat = edge.get("targetcategory", "")
        rel_label = edge.get("relationship_label", "")

        nodes.add(format_node(edge["source"], edge["sourcetype"], source_cat))
        nodes.add(format_node(edge["target"], edge["targettype"], target_cat))
        edges.append(f"""{{
            data: {{
                id: 'edge{i}',
                source: '{escape_js_string(edge["source"])}',
                sourcetype: '{escape_js_string(edge["sourcetype"])}',
                target: '{escape_js_string(edge["target"])}',
                targettype: '{escape_js_string(edge["targettype"])}',
                category: '{escape_js_string(get_relationship_category(edge["interaction"], rel_label))}',
                interaction: '{escape_js_string(edge["interaction"])}',
                p_source: '{escape_js_string(edge["p_source"])}',
                pmid: '{escape_js_string(edge["pmid"])}',
                species: '{escape_js_string(edge["species"])}',
                basis: '{escape_js_string(edge["basis"])}',
                source_extracted_definition: '{escape_js_string(edge["source_extracted_definition"])}',
                source_generated_definition: '{escape_js_string(edge["source_generated_definition"])}',
                target_extracted_definition: '{escape_js_string(edge["target_extracted_definition"])}',
                target_generated_definition: '{escape_js_string(edge["target_generated_definition"])}'
            }}
        }}""")

    with open('network.js', 'r') as template_file:
        template = template_file.read()

    return template.replace(
        '_INSERT_NODES_HERE_',
        ', '.join([
            f"{{ data: {{ id: '{node.split('|')[0]}', type: '{node.split('|')[1]}', category: '{node.split('|')[2]}' }} }}"
            for node in nodes
        ])
    ).replace(
        '_INSERT_EDGES_HERE_',
        ', '.join(edges)
    ).replace('REPLACE_AB', json.dumps(ab)).replace('REPLACE_FA', json.dumps(fa))


# Mapping from prompt entity categories to visualization categories
PROMPT_TO_VIS_CATEGORY = {
    'GENE / PROTEIN': 'GENE/PROTEIN',
    'GENE/PROTEIN': 'GENE/PROTEIN',
    'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE / GENE MUTANT': 'GENE/PROTEIN',
    'GENE IDENTIFIER': 'GENE IDENTIFIER',
    'TAXONOMIC / EVOLUTIONARY / PHYLOGENETIC GROUP': 'CELL/ORGAN/ORGANISM',
    'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGAN / ORGANISM': 'CELL/ORGAN/ORGANISM',
    'CELL/ORGAN/ORGANISM': 'CELL/ORGAN/ORGANISM',
    'PHENOTYPE': 'PHENOTYPE',
    'TREATMENT': 'TREATMENT',
    'TREATMENT / EXPOSURE / PERTURBATION': 'TREATMENT',
    'ENVIRONMENTAL / ECOLOGICAL / SOIL / CLIMATE CONTEXT': 'TREATMENT',
    'METABOLITE': 'CHEMICAL',
    'CHEMICAL': 'CHEMICAL',
    'CHEMICAL / COFACTOR / LIGAND': 'CHEMICAL',
    'BIOLOGICAL PROCESS': 'BIOLOGICAL PROCESS',
    'BIOLOGICAL PROCESS / FUNCTION': 'BIOLOGICAL PROCESS',
    'REGULATORY / SIGNALING MECHANISM / METABOLIC PATHWAY': 'BIOLOGICAL PROCESS',
    'PROCESS': 'BIOLOGICAL PROCESS',
    'COMPUTATIONAL / MODEL / ALGORITHM / DATA / METRIC': 'METHOD',
    'METHOD': 'METHOD',
    'METHOD / ASSAY / EXPERIMENTAL SETUP / PARAMETER / SAMPLE': 'METHOD',
    'EQUIPMENT / DEVICE / MATERIAL / INSTRUMENT': 'METHOD',
    'GENOMIC/TRANSCRIPTOMIC FEATURE': 'GENOMIC/TRANSCRIPTOMIC FEATURE',
    'SOCIAL / ECONOMIC / POLICY / MANAGEMENT': 'OTHER',
    'KNOWLEDGE / CONCEPT / HYPOTHESIS / THEORETICAL CONSTRUCT': 'OTHER',
    'PROPERTY / MEASUREMENT / CHARACTERIZATION': 'OTHER',
}
