from flask import Blueprint, render_template
import sys
import logging
import time
from pymongo import DESCENDING

sys.path.append('utils')

from utils.mongo import db
from utils.text import make_text
from utils.search import Gene
from utils.cytoscape import process_network, generate_cytoscape_js

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[logging.FileHandler("author_search.log"), logging.StreamHandler()]
)

author_search_results = Blueprint('author_search_results', __name__)

def standardize_author_name(query):
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "ß": "ss", "é": "e", "ó": "o",
        "í": "i", "ç": "c"
    }
    query = ''.join(replacements.get(c.lower(), c) for c in query).upper()
    parts = query.strip().split()
    if not parts:
        return ''
    suffixes = {'JR', 'SR', 'II', 'III', 'IV'}
    last_part = parts[-1]
    if last_part in suffixes and len(parts) >= 3:
        last_name = ' '.join(parts[:-2])
        initials = parts[-2]
    elif len(last_part) <= 3 and last_part.isalpha():
        last_name = ' '.join(parts[:-1])
        initials = last_part.replace('.', '')
    else:
        first_names = parts[:-1]
        last_name = parts[-1]
        initials = ''.join(name[0] for name in first_names).replace('.', '')
    return f"{last_name} {initials}".strip()

@author_search_results.route('/author/<query>', methods=['GET'])
def author(query):
    start_time = time.time()
    try:
        my_search = standardize_author_name(query)
    except Exception as e:
        my_search = 'DEFAULT'

    if not my_search:
        return render_template('not_found.html', search_term=query)

    authors_collection = db["authors"]
    all_dic_collection = db["all_dic"]

    try:
        pipeline = [
            {"$match": {"authors": my_search}},
            {"$project": {"pubmedID": 1, "_id": 0}},
        ]
        pubmed_ids = list(authors_collection.aggregate(pipeline))
        pm_list = [doc["pubmedID"] for doc in pubmed_ids]
        num_hits = len(pm_list)

        if not num_hits:
            return render_template('author.html', genes=[], cytoscape_js_code="",
                                   author=query, connectome_count=0,
                                   warning='No publications found.', summary='', search_term=query)

        projection = {
            "entity1": 1, "entity1type": 1, "entity2": 1, "entity2type": 1,
            "edge": 1, "pubmedID": 1, "p_source": 1, "species": 1, "basis": 1,
            "source_extracted_definition": 1, "source_generated_definition": 1,
            "target_extracted_definition": 1, "target_generated_definition": 1,
            "_id": 0
        }
        result_cursor = all_dic_collection.find({"pubmedID": {"$in": pm_list}}, projection)
        result = list(result_cursor)

        elements = [
            (
                doc["entity1"], doc["entity1type"], doc["entity2"],
                doc["entity2type"], doc["edge"], doc["pubmedID"],
                doc["p_source"], doc["species"], doc["basis"],
                doc["source_extracted_definition"], doc["source_generated_definition"],
                doc["target_extracted_definition"], doc["target_generated_definition"]
            )
            for doc in result
        ]
        forSending = [Gene(*element) for element in elements]

        updatedElements = process_network(elements)
        cytoscape_js_code = generate_cytoscape_js(updatedElements, {}, {})
        summaryText = make_text(forSending)

        return render_template(
            'author.html',
            genes=forSending,
            cytoscape_js_code=cytoscape_js_code,
            author=query,
            connectome_count=num_hits,
            warning='',
            summary=summaryText,
            search_term=query
        )
    except Exception as e:
        logging.error(f"Unexpected error during author search: {e}")
        return render_template('error.html', message='An unexpected error occurred. Please try again later.', search_term=query)
