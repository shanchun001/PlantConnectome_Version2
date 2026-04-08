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
        my_search = '24051094'
    pmids = []
    for i in my_search.split(';'):
        pmids += i.split()

    all_dic_collection = db["all_dic"]
    forSending = []
    elements = []
    elementsAb = {}
    elementsFa = {}

    if pmids != []:
        hits = []
        result = all_dic_collection.find({"pubmedID": {"$in": pmids}})
        for i in result:
            forSending.append(Gene(
                i["entity1"], i["entity1type"], i["entity2"], i["entity2type"],
                i["edge"], i["pubmedID"], i["p_source"], i["species"], i["basis"],
                i["source_extracted_definition"], i["source_generated_definition"],
                i["target_extracted_definition"], i["target_generated_definition"]
            ))
            elements.append((
                i["entity1"], i["entity1type"], i["entity2"], i["entity2type"],
                i["edge"], i["pubmedID"], i["p_source"], i["species"], i["basis"],
                i["source_extracted_definition"], i["source_generated_definition"],
                i["target_extracted_definition"], i["target_generated_definition"]
            ))
            hits.append(i["pubmedID"])

        updatedElements = process_network(elements)
        cytoscape_js_code = generate_cytoscape_js(updatedElements, elementsAb, elementsFa)
        summaryText = make_text(forSending)

        return render_template('gene.html', genes=forSending, cytoscape_js_code=cytoscape_js_code,
                               number_papers=len(list(set(hits))), search_term=query, summary=summaryText, is_node=False)
    else:
        return render_template('not_found.html', search_term=query)
