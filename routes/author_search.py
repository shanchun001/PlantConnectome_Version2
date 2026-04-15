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
        # Find paper titles by this author
        pipeline = [
            {"$match": {"authors": my_search}},
            {"$project": {"title": 1, "_id": 0}},
        ]
        title_docs = list(authors_collection.aggregate(pipeline))
        title_list = [doc["title"] for doc in title_docs if doc.get("title")]
        num_hits = len(title_list)

        if not num_hits:
            return render_template('author.html', genes=[], cytoscape_js_code="",
                                   author=query, connectome_count=0,
                                   warning='No publications found.', summary='', search_term=query)

        # Find relationships by title (indexed)
        result = list(all_dic_collection.find({"title": {"$in": title_list}}))

        elements = []
        for doc in result:
            elements.append((
                doc.get("entity1", ""), doc.get("entity1type", ""),
                doc.get("entity2", ""), doc.get("entity2type", ""),
                doc.get("edge", ""), doc.get("pubmedID", ""),
                doc.get("p_source", ""), doc.get("species", ""), doc.get("basis", ""),
                doc.get("source_extracted_definition", ""), doc.get("source_generated_definition", ""),
                doc.get("target_extracted_definition", ""), doc.get("target_generated_definition", ""),
                doc.get("entity1category", ""), doc.get("entity2category", ""), doc.get("relationship_label", ""),
                doc.get("source_identifier", ""), doc.get("target_identifier", ""),
                doc.get("extracted_associated_process_or_pathway", ""), doc.get("generated_associated_process_or_pathway", ""),
                doc.get("relevant_citations", "")
            ))
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
