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

    # Simple approach: find matching docs, count in Python (fast on 61K collection)
    authors_list = []
    try:
        query_upper = query.strip().upper()
        logging.info(f"Author search: query='{query}', upper='{query_upper}'")
        docs = list(authors_collection.find(
            {"authors": {"$regex": query_upper}},
            {"authors": 1}
        ))
        logging.info(f"Author search: found {len(docs)} docs")
        # Count matching author names
        from collections import Counter
        name_counts = Counter()
        for doc in docs:
            for author in doc.get("authors", []):
                if query_upper in author.upper():
                    name_counts[author] += 1

        for name, count in name_counts.most_common():
            authors_list.append({
                "full_name": name,
                "publication_count": count
            })
    except Exception as e:
        logging.error(f"Error during author search: {e}")
        authors_list = []

    elapsed_time = time.time() - start_time
    logging.info(f"Author search for '{query}': {len(authors_list)} authors found in {elapsed_time:.2f}s")

    if authors_list:
        return render_template(
            'preview_authorsearch.html',
            authors=authors_list,
            search_term=query
        )
    else:
        return render_template('not_found.html', search_term=query)
