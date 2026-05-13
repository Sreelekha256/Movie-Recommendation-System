from flask import Flask, render_template, request, redirect, url_for, session
import pickle
import random
import requests
import urllib.parse
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "cinevault_secret_2024"

# ── LOAD MODEL ───────────────────────────────────────────────
movies     = pickle.load(open("model/movies.pkl",     "rb"))
similarity = pickle.load(open("model/similarity.pkl", "rb"))

# ── OMDB API KEY ─────────────────────────────────────────────
OMDB_API_KEY = "b3994a5b"


# ── DATABASE INIT ────────────────────────────────────────────
def init_db():
    conn   = sqlite3.connect("database/users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


# ── FETCH MOVIE DATA ─────────────────────────────────────────
def fetch_movie_data(movie_id):
    try:
        title   = movies[movies["movie_id"] == movie_id]["title"].values[0]
        encoded = urllib.parse.quote(title)
        url     = f"http://www.omdbapi.com/?t={encoded}&apikey={OMDB_API_KEY}"
        data    = requests.get(url, timeout=5).json()

        if data.get("Response") == "True":
            poster = data.get("Poster", "")
            if not poster or poster == "N/A":
                poster = "https://placehold.co/300x450/141414/E50914?text=No+Poster"

            rating  = data.get("imdbRating", "N/A")
            year    = data.get("Year",    "")[:4]
            plot    = data.get("Plot",    "No description available.")
            runtime = data.get("Runtime", "").replace(" min", "").strip()
            genre   = data.get("Genre",   "")
            genres  = [g.strip() for g in genre.split(",")] if genre else []

            # YouTube search URL for trailer — opens directly in browser
            yt_query    = urllib.parse.quote(f"{title} official trailer")
            trailer_url = f"https://www.youtube.com/results?search_query={yt_query}"

            return {
                "title":       title,
                "poster":      poster,
                "rating":      rating,
                "year":        year,
                "plot":        plot,
                "runtime":     runtime,
                "genres":      genres,
                "trailer_url": trailer_url,
            }

    except Exception:
        pass

    # Fallback
    try:
        title = movies[movies["movie_id"] == movie_id]["title"].values[0]
    except Exception:
        title = "Unknown"

    yt_query = urllib.parse.quote(f"{title} official trailer")
    return {
        "title":       title,
        "poster":      "https://placehold.co/300x450/141414/E50914?text=No+Poster",
        "rating":      "N/A",
        "year":        "",
        "plot":        "",
        "runtime":     "",
        "genres":      [],
        "trailer_url": f"https://www.youtube.com/results?search_query={yt_query}",
    }


# ── RECOMMEND FUNCTION ───────────────────────────────────────
def get_recommendations(movie):
    if movie not in movies["title"].values:
        return []

    idx        = movies[movies["title"] == movie].index[0]
    distances  = similarity[idx]
    movie_list = sorted(enumerate(distances), reverse=True, key=lambda x: x[1])[1:7]

    results = []
    for i, _ in movie_list:
        row      = movies.iloc[i]
        movie_id = int(row["movie_id"])
        data     = fetch_movie_data(movie_id)
        results.append(data)

    return results


# ── LOGIN ────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn   = sqlite3.connect("database/users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user"] = username
            return redirect(url_for("home"))
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)


# ── REGISTER ─────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            hashed = generate_password_hash(password)
            conn   = sqlite3.connect("database/users.db")
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hashed)
                )
                conn.commit()
                conn.close()
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                conn.close()
                error = "Username already taken. Try another."

    return render_template("register.html", error=error)


# ── LOGOUT ───────────────────────────────────────────────────
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# ── HOME ─────────────────────────────────────────────────────
@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))

    all_movies = movies["title"].values.tolist()

    # Hero movie
    hero_title = random.choice(all_movies)
    hero_row   = movies[movies["title"] == hero_title].iloc[0]
    hero       = fetch_movie_data(int(hero_row["movie_id"]))

    # Row 1 — Featured (12 movies)
    featured = []
    for t in random.sample(all_movies, 12):
        row = movies[movies["title"] == t].iloc[0]
        featured.append(fetch_movie_data(int(row["movie_id"])))

    # Row 2 — More to Watch (10 movies)
    more = []
    for t in random.sample(all_movies, 10):
        row = movies[movies["title"] == t].iloc[0]
        more.append(fetch_movie_data(int(row["movie_id"])))

    return render_template(
        "home.html",
        all_movies = all_movies,
        hero       = hero,
        featured   = featured,
        more       = more,
        username   = session["user"],
    )


# ── TRENDING ─────────────────────────────────────────────────
@app.route("/trending")
def trending():
    if "user" not in session:
        return redirect(url_for("login"))

    all_movies = movies["title"].values.tolist()

    trending_list = []
    for t in random.sample(all_movies, 16):
        row = movies[movies["title"] == t].iloc[0]
        trending_list.append(fetch_movie_data(int(row["movie_id"])))

    hero = trending_list[0]

    return render_template(
        "trending.html",
        trending   = trending_list,
        all_movies = all_movies,
        username   = session["user"],
        hero       = hero,
    )


# ── RECOMMEND ────────────────────────────────────────────────
@app.route("/recommend", methods=["POST"])
def recommend_movies():
    if "user" not in session:
        return redirect(url_for("login"))

    movie      = request.form.get("movie", "").strip()
    all_movies = movies["title"].values.tolist()
    results    = get_recommendations(movie)

    hero = {}
    if movie in movies["title"].values:
        hero_row = movies[movies["title"] == movie].iloc[0]
        hero     = fetch_movie_data(int(hero_row["movie_id"]))

    return render_template(
        "recommendations.html",
        results        = results,
        selected_movie = movie,
        all_movies     = all_movies,
        username       = session["user"],
        hero           = hero,
    )


# ── RUN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)