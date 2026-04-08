'''
This module contains the routes for searching.
'''
from flask import Blueprint
import sys

sys.path.append('utils')

from utils.search import generate_search_route, generate_search_route2, generate_multi_search_route

term_searches = Blueprint('term_searches', __name__)
term_results = Blueprint('term_results', __name__)

normal = generate_search_route('normal')
substring = generate_search_route('substring')

normal_results = generate_search_route2('normal')
substring_results = generate_search_route2('substring')

normal_results_multi = generate_multi_search_route('normal')
substring_results_multi = generate_multi_search_route('substring')
