"""
preprocess.py — Run once to build the TF-IDF index from the Uber Eats dataset.

Usage:
    python src/preprocess.py

Outputs:
    data/forkcast_index.pkl  — vectorizer + TF-IDF matrix + restaurant/menu data
"""

import os
import pickle
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
RESTAURANT_CSV = os.path.join(DATA_DIR, 'restaurants.csv')
MENUS_FULL_CSV = os.path.join(DATA_DIR, 'restaurant-menus.csv')
MENUS_SAMPLE_CSV = os.path.join(DATA_DIR, 'restaurant-menus-sample.csv')
OUTPUT_PATH = os.path.join(DATA_DIR, 'forkcast_index.pkl')

SAMPLE_SIZE = 5000
MAX_MENU_ITEMS_PER_RESTAURANT = 50  # stored; only 3 shown in UI


def build_index(use_sample_menus=False):
    print("Loading restaurants...")
    restaurants = pd.read_csv(RESTAURANT_CSV)
    restaurants['id'] = pd.to_numeric(restaurants['id'], errors='coerce').astype('Int64').astype(str)
    restaurants['name'] = restaurants['name'].fillna('')
    restaurants['category'] = restaurants['category'].fillna('')
    restaurants['price_range'] = restaurants['price_range'].fillna('')
    restaurants['full_address'] = restaurants['full_address'].fillna('')
    restaurants['score'] = pd.to_numeric(restaurants['score'], errors='coerce').fillna(0.0)
    restaurants['ratings'] = restaurants['ratings'].fillna('').astype(str)

    if len(restaurants) > SAMPLE_SIZE:
        restaurants = restaurants.sample(SAMPLE_SIZE, random_state=42).reset_index(drop=True)
        print(f"Sampled {SAMPLE_SIZE} restaurants from full dataset.")

    restaurant_ids = set(restaurants['id'])

    # Choose menus file
    menus_file = MENUS_SAMPLE_CSV if use_sample_menus else MENUS_FULL_CSV
    if not os.path.exists(menus_file):
        menus_file = MENUS_SAMPLE_CSV
        print(f"Full menus file not found, falling back to sample: {menus_file}")

    print(f"Loading menus from {os.path.basename(menus_file)}...")
    chunks = []
    for chunk in pd.read_csv(menus_file, chunksize=100_000, low_memory=False):
        chunk['restaurant_id'] = pd.to_numeric(chunk['restaurant_id'], errors='coerce').astype('Int64').astype(str)
        filtered = chunk[chunk['restaurant_id'].isin(restaurant_ids)]
        if not filtered.empty:
            chunks.append(filtered)

    if chunks:
        menus = pd.concat(chunks, ignore_index=True)
        menus['name'] = menus['name'].fillna('')
        menus['description'] = menus['description'].fillna('')
        menus['price'] = menus['price'].fillna('').astype(str)
        print(f"Loaded {len(menus):,} menu items for {menus['restaurant_id'].nunique()} restaurants.")
    else:
        menus = pd.DataFrame(columns=['restaurant_id', 'category', 'name', 'description', 'price'])
        print("Warning: no matching menu items found.")

    # Group menus by restaurant for fast lookup
    menus_by_restaurant = {
        rid: group for rid, group in menus.groupby('restaurant_id')
    }

    print("Building composite documents...")
    docs = []
    menu_data = {}

    for _, row in restaurants.iterrows():
        rid = row['id']
        rest_menus = menus_by_restaurant.get(rid, pd.DataFrame())

        parts = [row['name'], row['category'], row['price_range']]

        items_for_display = []
        for i, (_, item) in enumerate(rest_menus.iterrows()):
            parts.append(item['name'])
            if item['description'].strip():
                parts.append(item['description'])
            if i < MAX_MENU_ITEMS_PER_RESTAURANT:
                items_for_display.append({
                    'name': item['name'],
                    'description': item['description'],
                    'price': item['price'],
                })

        docs.append(' '.join(p for p in parts if p))
        menu_data[rid] = items_for_display

    print("Fitting TF-IDF vectorizer...")
    vectorizer = TfidfVectorizer(
        stop_words='english',
        ngram_range=(1, 2),
        max_features=60_000,
        min_df=1,
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform(docs)
    print(f"TF-IDF matrix shape: {tfidf_matrix.shape}")

    index = {
        'restaurants': restaurants.to_dict('records'),
        'menu_data': menu_data,
        'vectorizer': vectorizer,
        'tfidf_matrix': tfidf_matrix,
    }

    with open(OUTPUT_PATH, 'wb') as f:
        pickle.dump(index, f, protocol=4)

    print(f"Index saved to {OUTPUT_PATH}")
    return index


if __name__ == '__main__':
    import sys
    use_sample = '--sample' in sys.argv
    build_index(use_sample_menus=use_sample)
