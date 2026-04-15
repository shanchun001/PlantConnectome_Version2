from flask import Blueprint, request, render_template
import sys

sys.path.append('utils')
from utils.search import Gene
from utils.cytoscape import process_network, generate_cytoscape_js
from utils.text import make_text
from utils.mongo import db

title_searches = Blueprint('title_searches', __name__)

@title_searches.route('/title/<query>', methods=['GET'])
def title_search(query):
    try:
        my_search = query
    except:
        my_search = '38050352'
    pmids = []
    for i in my_search.split(';'):
        pmids += i.split()

    all_dic_collection = db["all_dic"]
    forSending = []
    elements = []
    elementsAb = {}
    elementsFa = {}

    if pmids:
        hits = []
        # Search by pubmedID (custom_id) OR by pubmed_id (numeric PMID from paper_metadata)
        result = list(all_dic_collection.find({"$or": [
            {"pubmedID": {"$in": pmids}},
            {"pubmed_id": {"$in": pmids}}
        ]}))

        for i in result:
            forSending.append(Gene(
                i["entity1"], i.get("entity1type", ""), i["entity2"], i.get("entity2type", ""),
                i.get("edge"), i.get("pubmedID"), i.get("p_source"), i.get("species"), i.get("basis"),
                i.get("source_extracted_definition"), i.get("source_generated_definition"),
                i.get("target_extracted_definition"), i.get("target_generated_definition"),
                i.get("entity1category", ""), i.get("entity2category", ""), i.get("relationship_label", ""),
                i.get("source_identifier", ""), i.get("target_identifier", ""),
                i.get("extracted_associated_process_or_pathway", ""), i.get("generated_associated_process_or_pathway", ""),
                i.get("relevant_citations", "")
            ))
            elements.append((
                i["entity1"], i.get("entity1type", ""), i["entity2"], i.get("entity2type", ""),
                i.get("edge"), i.get("pubmedID"), i.get("p_source"), i.get("species"), i.get("basis"),
                i.get("source_extracted_definition"), i.get("source_generated_definition"),
                i.get("target_extracted_definition"), i.get("target_generated_definition"),
                i.get("entity1category", ""), i.get("entity2category", ""), i.get("relationship_label", ""),
                i.get("source_identifier", ""), i.get("target_identifier", ""),
                i.get("extracted_associated_process_or_pathway", ""), i.get("generated_associated_process_or_pathway", ""),
                i.get("relevant_citations", "")
            ))
            hits.append(i.get("pubmedID", ""))

        if forSending:
            updatedElements = process_network(elements)
            cytoscape_js_code = generate_cytoscape_js(updatedElements, elementsAb, elementsFa)
            summaryText = make_text(forSending)

            return render_template('gene.html', genes=forSending, cytoscape_js_code=cytoscape_js_code,
                                   number_papers=len(list(set(hits))), search_term=query, summary=summaryText, is_node=False)

    return render_template('not_found.html', search_term=query)
