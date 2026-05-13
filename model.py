import pandas as pd
import ast
import pickle
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# Create model folder if it doesn't exist
if not os.path.exists("model"):
    os.makedirs("model")

# ── LOAD DATA ────────────────────────────────────────────────
movies  = pd.read_csv("data/tmdb_5000_movies.csv")
credits = pd.read_csv("data/tmdb_5000_credits.csv")

# Merge on title — keeps movie_id for OMDB API lookups
movies = movies.merge(credits, on="title")
movies = movies[["movie_id", "title", "overview", "genres", "keywords", "cast", "crew"]]
movies.dropna(inplace=True)


# ── HELPER FUNCTIONS ─────────────────────────────────────────
def convert(text):
    return [i["name"] for i in ast.literal_eval(text)]

def convert_cast(text):
    return [i["name"] for i in ast.literal_eval(text)[:3]]

def fetch_director(text):
    for i in ast.literal_eval(text):
        if i["job"] == "Director":
            return [i["name"]]
    return []

def collapse(lst):
    return [i.replace(" ", "") for i in lst]


# ── CLEAN DATA ───────────────────────────────────────────────
movies["genres"]   = movies["genres"].apply(convert).apply(collapse)
movies["keywords"] = movies["keywords"].apply(convert).apply(collapse)
movies["cast"]     = movies["cast"].apply(convert_cast).apply(collapse)
movies["crew"]     = movies["crew"].apply(fetch_director).apply(collapse)
movies["overview"] = movies["overview"].apply(lambda x: x.split() if isinstance(x, str) else [])

movies["tags"] = (
    movies["overview"] +
    movies["genres"]   +
    movies["keywords"] +
    movies["cast"]     +
    movies["crew"]
)

# Keep movie_id so app.py can call OMDB by title fetched from id
movies = movies[["movie_id", "title", "tags"]]
movies["tags"] = movies["tags"].apply(lambda x: " ".join(x).lower())


# ── BUILD MODEL ──────────────────────────────────────────────
tfidf      = TfidfVectorizer(max_features=5000, stop_words="english")
vectors    = tfidf.fit_transform(movies["tags"])
similarity = linear_kernel(vectors, vectors)


# ── SAVE ─────────────────────────────────────────────────────
pickle.dump(movies,     open("model/movies.pkl",     "wb"))
pickle.dump(similarity, open("model/similarity.pkl", "wb"))

print("Model built and saved successfully!")