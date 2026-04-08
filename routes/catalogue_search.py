from flask import Blueprint, request, render_template
import pickle
import sys
import re
from utils.mongo import db
import time

sys.path.append('utils')

catalogue_search = Blueprint('catalogue_search', __name__)

@catalogue_search.route('/catalogue', methods=['GET'])
def catalogue():
    try:
        cata = pickle.load(open('catalogue.pkl', 'rb'))
        return render_template("/catalogue.html", entities=cata[1], header=sorted(cata[0]))
    except FileNotFoundError:
        return render_template('error.html', message='Catalogue data not yet available.')
