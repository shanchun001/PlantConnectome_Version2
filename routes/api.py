from flask import Blueprint, jsonify
from Bio import Entrez
import sys
import pickle

sys.path.append('utils')
from utils.api import generate_term_api_route, REPLACEMENTS, generate_cytoscape_elements, generate_summary_text
from utils.search import Gene, make_abbreviations, make_functional_annotations
from utils.cytoscape import process_network

api = Blueprint('api', __name__)
from utils.mongo import db

normal_search = generate_term_api_route('normal')
substring_search = generate_term_api_route('substring')

@api.route('/api/author/<query>', methods=['GET'])
def api_author(query):
    try:
        my_search = query.upper()
        replacements = {"a": "ae", "o": "oe", "u": "ue", "ss": "ss", "e": "e", "o": "o", "i": "i", "c": "c"}
        my_search = ''.join(replacements.get(c, c) for c in my_search)
    except:
        my_search = 'DEFAULT'.upper()

    authors_collection = db["authors"]
    all_dic_collection = db["all_dic"]

    forSending = []
    elements = []
    elementsAb = {}
    elementsFa = {}
    num_hits = 0

    if my_search != '':
        hits = authors_collection.find({"authors": my_search})
        pm_list = []
        if hits is not None:
            for i in hits:
                num_hits += 1
                pm_list.append(i['pubmedID'])

        Entrez.email = "your_email@example.com"
        search_query = my_search + "[Author]"
        handle = Entrez.esearch(db="pubmed", term=search_query)
        record = Entrez.read(handle)
        count = record["Count"]

        if hits is not None:
            result = all_dic_collection.find({"pubmedID": {"$in": pm_list}})
            for i in result:
                forSending.append(Gene(i["entity1"], i["entity2"], i["edge"], i["pubmedID"]))
                elements.append((i["entity1"], i["entity2"], i["edge"]))

    if len(forSending):
        elements = list(set(elements))
        elementsAb = make_abbreviations([], elements)
        elementsFa = make_functional_annotations([], elements)
        cytoscape_elements = generate_cytoscape_elements(process_network(elements))
        text_sum = generate_summary_text(forSending)

    return jsonify({
        'paper_counts': {
            'PlantConnectome': num_hits,
            'NCBI': int(count)
        },
        'abbreviations': elementsAb,
        'functional_annotations': elementsFa,
        'cytoscape_elements': cytoscape_elements[0] + cytoscape_elements[1],
        'text_summary': text_sum
    })

@api.route('/api/title/<query>', methods=['GET'])
def title_search(query):
    try:
        my_search = query
    except:
        my_search = '26503768'
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
            forSending.append(Gene(i["entity1"], i["entity2"], i["edge"], i["pubmedID"]))
            elements.append((i["entity1"], i["entity2"], i["edge"]))
            hits.append(i["pubmedID"])

        elements = list(set(elements))
        elementsAb = make_abbreviations([], elements)
        elementsFa = make_functional_annotations([], elements)
        cytoscape_elements = generate_cytoscape_elements(process_network(elements))
        text_sum = generate_summary_text(forSending)

        return jsonify({
            'abbreviations': elementsAb,
            'functional_annotations': elementsFa,
            'cytoscape_elements': cytoscape_elements[0] + cytoscape_elements[1],
            'text_summary': text_sum
        })
