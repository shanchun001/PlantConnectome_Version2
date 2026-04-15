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

    # Simple approach: find matching authors, group by standardized name
    # No $lookup needed — we'll verify against all_dic when user clicks through
    pipeline = [
        {"$match": {"authors": {"$regex": query, "$options": "i"}}},
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
        {"$sort": {"publication_count": -1}}
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

    elapsed_time = time.time() - start_time
    logging.info(f"Author search for '{query}': {len(authors_list)} authors found in {elapsed_time:.2f}s")

    if authors_list:
        return render_template(
            'preview_authorsearch.html',
            authors_list=authors_list,
            search_term=query
        )
    else:
        return render_template('not_found.html', search_term=query)
