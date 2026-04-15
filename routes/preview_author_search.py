from flask import Blueprint, render_template
from utils.mongo import db
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

author_search = Blueprint('author_search', __name__)

@author_search.route('/preview_author_search/<query>', methods=['GET'])
def preview_author_search(query):
    start_time = time.time()
    authors_collection = db["authors"]

    pipeline = [
        {"$match": {"authors": {"$regex": query, "$options": "i"}}},
        # Only keep authors whose papers exist in all_dic (join on title)
        {"$lookup": {
            "from": "all_dic",
            "localField": "title",
            "foreignField": "title",
            "pipeline": [{"$limit": 1}],
            "as": "kg_match"
        }},
        {"$match": {"kg_match.0": {"$exists": True}}},
        {"$project": {"authors": 1, "pubmedID": 1, "title": 1}},
        {"$set": {
            "authors": {
                "$filter": {
                    "input": "$authors",
                    "as": "author",
                    "cond": {
                        "$regexMatch": {
                            "input": "$$author",
                            "regex": query,
                            "options": "i"
                        }
                    }
                }
            }
        }},
        {"$match": {"authors.0": {"$exists": True}}},
        {"$unwind": "$authors"},
        {"$group": {
            "_id": "$authors",
            "publication_count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]

    authors_list = []
    try:
        authors_cursor = authors_collection.aggregate(pipeline)
        for doc in authors_cursor:
            full_name = doc["_id"]
            count = doc.get("publication_count", 0)
            authors_list.append({
                "full_name": full_name,
                "publication_count": count
            })
    except Exception as e:
        logging.error(f"Error during aggregation of authors: {e}")
        authors_list = []

    if not authors_list:
        return render_template('not_found.html', search_term=query)
    return render_template(
        'preview_authorsearch.html',
        authors=authors_list,
        search_term=query
    )
