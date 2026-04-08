from flask import Blueprint, request, render_template, url_for, redirect
import pickle
import sys

sys.path.append('utils')

similarity_search = Blueprint('similarity_search', __name__)

@similarity_search.route('/similarity_form/', methods=['POST'])
def similarity_form():
    try:
        query = request.form["similarity_id"]
        type = request.form["similarity_type"]
    except:
        query = ""
        type = ""
    return redirect(url_for("similarity_search.similarity", query=query, type=type))

@similarity_search.route('/similarity/<type>/<query>', methods=['GET'])
def similarity(query, type):
    forSending = []
    if query != "" and type != "":
        return render_template('/similarity.html', results=forSending, search_term=query,
                               number_nodes=len(forSending), number_papers=0, type=type)
    else:
        return render_template('not_found.html', search_term=query)
