from flask import jsonify
from search import find_terms
from mongo import db
from cytoscape import process_network

import time
import re
import json
import os
import pandas as pd

genes = db["all_dic"]

REPLACEMENTS = {"a": "ae", "o": "oe", "u": "ue", "ss": "ss", "e": "e", "o": "o", "i": "i", "c": "c"}


def generate_cytoscape_elements(elements):
    df = pd.read_csv('utils/Connectome_entities.csv')

    nodes = [
        "{ data: { id: '%s' } }" % node
        for node in set(
            edge["source"] + "', type: '" + edge["sourcetype"] + "', category: '" +
            (
                str(df.loc[df.iloc[:, 0] == edge["sourcetype"].upper(), df.columns[2]].values[0])
                if not df.loc[df.iloc[:, 0] == edge["sourcetype"].upper(), df.columns[2]].empty
                else "NA"
            )
            for edge in elements
        ) | set(
            edge["target"] + "', type: '" + edge["targettype"] + "', category: '" +
            (
                str(df.loc[df.iloc[:, 0] == edge["targettype"].upper(), df.columns[2]].values[0])
                if not df.loc[df.iloc[:, 0] == edge["targettype"].upper(), df.columns[2]].empty
                else "NA"
            )
            for edge in elements
        )
    ]

    with open('utils/Connectome_relationships.json', 'r') as file:
        data = json.load(file)

    def get_key(dictionary, value):
        for key, val in dictionary.items():
            if value in val:
                return key
        return None

    edges = [
        "{ data: { id: 'edge%s', source: '%s', sourcetype: '%s', target: '%s', targettype: '%s', category:'%s', interaction: '%s', p_source: '%s', pmid: '%s', species: '%s', basis:'%s', source_extracted_definition:'%s', source_generated_definition:'%s', target_extracted_definition:'%s', target_generated_definition:'%s' } }" % (
            i,
            edge['source'], edge['sourcetype'],
            edge['target'], edge['targettype'],
            get_key(data, edge['interaction'].upper()),
            edge['interaction'],
            edge['pmid'], edge['p_source'],
            edge['species'], edge['basis'],
            edge['source_extracted_definition'], edge['source_generated_definition'],
            edge['target_extracted_definition'], edge['target_generated_definition'],
        )
        for i, edge in enumerate(elements)
    ]

    nodes = ', '.join(nodes).replace('\n', '')
    edges = ', '.join(edges).replace('\n', '')
    return nodes, edges


class Gene:
    def __init__(self, id, idtype, description, descriptiontype, inter_type, publication, p_source, species, basis,
                 source_extracted_definition, source_generated_definition, target_extracted_definition, target_generated_definition):
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

    def __repr__(self):
        return str(self.__dict__)

    def __str__(self):
        return str(self.__dict__)

    def getElements(self):
        return (self.id, self.idtype, self.target, self.targettype, self.inter_type)


def generate_summary_text(elements):
    if not len(elements):
        return ''
    topicDic, nodeDegree, nodeSentenceDegree = {}, {}, {}
    for i in elements:
        key = i.id + "[" + i.idtype + "]"
        if key not in topicDic:
            topicDic[key] = {}
            nodeDegree[key] = 0
            nodeSentenceDegree[key] = {}
        if i.inter_type not in topicDic[key]:
            topicDic[key][i.inter_type] = [[i.target + "[" + i.targettype + "]", i.publication]]
            nodeSentenceDegree[key][i.inter_type] = 1
            nodeDegree[key] += 1
        else:
            topicDic[key][i.inter_type] += [[i.target + "[" + i.targettype + "]", i.publication]]
            nodeDegree[key] += 1
            nodeSentenceDegree[key][i.inter_type] += 1

    sorted_nodes = sorted(nodeDegree, key=lambda x: nodeDegree[x], reverse=True)
    finished_sentences = []
    for i in sorted_nodes:
        sorted_sentences = sorted(nodeSentenceDegree[i], key=lambda x: nodeSentenceDegree[i][x], reverse=True)
        for j in sorted_sentences:
            text, temp, tempRefs = i + ' ' + j + ' ', {}, []
            for k in topicDic[i][j]:
                if k[0] not in temp:
                    temp[k[0]] = [k[1]]
                else:
                    temp[k[0]] += [k[1]]
            for target in temp:
                tempRefs += [target + ' (' + ', '.join(list(set(temp[target]))) + ')']
            finished_sentences.append(text + ', '.join(tempRefs))
    return '. '.join(finished_sentences) + '.'


def generate_term_api_route(query_type):
    def api_route(query):
        if len(query):
            forSending, elements, summary = [], [], ''
            all_dic_collection = db["all_dic"]
            for term in query.split(';'):
                results = find_terms([term], all_dic_collection, query_type)
                elements.extend(results[0])
                forSending.extend(results[1])
            elements = list(set(elements))
            papers = [i.publication for i in forSending]
            summary = generate_summary_text(forSending)
            cytoscape_elements = generate_cytoscape_elements(process_network(elements))
        return jsonify({
            'cytoscape_entities': cytoscape_elements[0],
            'cytoscape_relationships_basis_definitions': cytoscape_elements[1],
            'text_summary': summary,
            'publications': papers
        })
    return api_route
