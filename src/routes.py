"""
Routes for Forkcast — natural language restaurant search via TF-IDF.
"""
import os
import pickle
import numpy as np
from flask import send_from_directory, request, jsonify
from sklearn.metrics.pairwise import cosine_similarity

# ── Index loading ─────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
INDEX_PATH = os.path.join(DATA_DIR, 'forkcast_index.pkl')

_index = None

def get_index():
    global _index
    if _index is None:
        if not os.path.exists(INDEX_PATH):
            raise FileNotFoundError(
                f"Index not found at {INDEX_PATH}. "
                "Run: python src/preprocess.py"
            )
        print("Loading Forkcast index...")
        with open(INDEX_PATH, 'rb') as f:
            _index = pickle.load(f)
        print(f"Index loaded: {len(_index['restaurants'])} restaurants.")
    return _index


# ── Query expansion ───────────────────────────────────────────────────────────

SYNONYMS = {
    'spicy':       ['hot', 'fiery', 'spiced', 'chili', 'pepper', 'jalapeño'],
    'cheap':       ['inexpensive', 'affordable', 'budget', 'value', '$'],
    'healthy':     ['fresh', 'organic', 'salad', 'vegetarian', 'vegan', 'nutritious', 'light', 'greens'],
    'burger':      ['burgers', 'cheeseburger', 'hamburger'],
    'pizza':       ['pizzas', 'pie', 'flatbread', 'italian'],
    'sushi':       ['japanese', 'roll', 'maki', 'sashimi', 'nigiri'],
    'vegetarian':  ['vegan', 'plant-based', 'meatless', 'veggie'],
    'vegan':       ['plant-based', 'vegetarian', 'meatless', 'dairy-free'],
    'noodles':     ['pasta', 'ramen', 'pho', 'udon', 'lo mein', 'spaghetti'],
    'breakfast':   ['brunch', 'morning', 'eggs', 'pancakes', 'waffles', 'omelette'],
    'dessert':     ['sweet', 'cake', 'ice cream', 'cookie', 'pastry', 'chocolate'],
    'seafood':     ['fish', 'shrimp', 'lobster', 'crab', 'salmon', 'tuna'],
    'mexican':     ['tacos', 'burritos', 'enchiladas', 'quesadilla', 'salsa'],
    'chinese':     ['fried rice', 'dumplings', 'dim sum', 'noodles', 'stir fry'],
    'indian':      ['curry', 'masala', 'biryani', 'naan', 'tikka'],
    'thai':        ['pad thai', 'curry', 'basil', 'lemongrass', 'coconut'],
    'bbq':         ['barbecue', 'grilled', 'smoked', 'ribs', 'brisket'],
    'sandwich':    ['sub', 'hoagie', 'wrap', 'panini', 'hero'],
    'salad':       ['greens', 'bowl', 'healthy', 'fresh', 'lettuce'],
    'wings':       ['chicken wings', 'buffalo', 'hot wings'],
}


def expand_query(query: str) -> str:
    tokens = query.lower().split()
    expanded = list(tokens)
    for token in tokens:
        if token in SYNONYMS:
            expanded.extend(SYNONYMS[token])
    return ' '.join(expanded)

# ── Menu item matching ────────────────────────────────────────────────────────

def find_matching_items(items: list, query: str, max_items: int = 3) -> list:
    """Return up to max_items menu items most relevant to the query."""
    if not items:
        return []
    query_words = set(query.lower().split())
    scored = []
    for item in items:
        text = f"{item['name']} {item['description']}".lower()
        score = sum(1 for w in query_words if w in text)
        scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:max_items]]

# ── Core search ───────────────────────────────────────────────────────────────

def search_restaurants(query: str, price_filter: str = '', limit: int = 10) -> list:
    if not query.strip():
        return []

    idx = get_index()
    expanded = expand_query(query)
    query_vec = idx['vectorizer'].transform([expanded])
    scores = cosine_similarity(query_vec, idx['tfidf_matrix']).flatten()

    top_indices = scores.argsort()[::-1]

    results = []
    for i in top_indices:
        if len(results) >= limit:
            break
        if scores[i] < 0.01:
            break

        row = idx['restaurants'][i]
        rid = str(int(float(str(row['id'])))) if str(row['id']).replace('.','',1).isdigit() else str(row['id'])

        if price_filter and str(row.get('price_range', '')).strip() != price_filter:
            continue

        all_items = idx['menu_data'].get(rid, [])
        matched = find_matching_items(all_items, query)

        results.append({
            'name':          row.get('name', ''),
            'category':      row.get('category', ''),
            'price_range':   row.get('price_range', ''),
            'score':         round(float(row.get('score') or 0), 1),
            'ratings':       str(row.get('ratings', '')),
            'address':       row.get('full_address', ''),
            'similarity':    round(float(scores[i]), 4),
            'matched_items': matched,
        })

    return results


# ── Route registration ────────────────────────────────────────────────────────

def register_routes(app):
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    @app.route("/api/config")
    def config():
        return jsonify({'use_llm': False})

    @app.route('/api/search')
    def search():
        query = request.args.get('q', '').strip()
        price = request.args.get('price', '').strip()
        limit = min(int(request.args.get('limit', 10)), 25)
        try:
            results = search_restaurants(query, price_filter=price, limit=limit)
            return jsonify(results)
        except FileNotFoundError as e:
            return jsonify({'error': str(e)}), 503

