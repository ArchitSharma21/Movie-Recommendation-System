import os
import numpy as np
import pandas as pd
from flask import Flask, render_template, request
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json
import bs4 as bs
import urllib.request
import pickle
import requests
from datetime import date, datetime


TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
LEGACY_CATALOG_PATH = os.path.join("data", "legacy", "main_data.csv")
# load the nlp model and tfidf vectorizer from disk
filename = 'nlp_model.pkl'
clf = pickle.load(open(filename, 'rb'))
vectorizer = pickle.load(open('tranform.pkl','rb'))
    
# converting list of string to list (eg. "["abc","def"]" to ["abc","def"])
def convert_to_list(my_list):
    my_list = my_list.split('","')
    my_list[0] = my_list[0].replace('["','')
    my_list[-1] = my_list[-1].replace('"]','')
    return my_list

# convert list of numbers to list (eg. "[1,2,3]" to [1,2,3])
def convert_to_list_num(my_list):
    my_list = my_list.split(',')
    my_list[0] = my_list[0].replace("[","")
    my_list[-1] = my_list[-1].replace("]","")
    return my_list

def get_suggestions():
    data = pd.read_csv(LEGACY_CATALOG_PATH)
    return list(data['movie_title'].str.capitalize())

app = Flask(__name__)

@app.route("/")
@app.route("/home")
def home():
    suggestions = get_suggestions()
    return render_template('home.html',suggestions=suggestions)


def get_tmdb_reviews_from_imdb(imdb_id, max_reviews=10):
    """
    Given an imdb_id like 'tt1234567', return a dict {review_text: sentiment}
    using TMDb's API. Returns {} on failure or if no reviews found.
    """
    if not TMDB_API_KEY:
        # Key not available — caller will handle fallback
        print("TMDb API key not set; skipping TMDb fetch.")
        return {}

    try:
        find_url = f"https://api.themoviedb.org/3/find/{imdb_id}"
        params = {"api_key": TMDB_API_KEY, "external_source": "imdb_id"}
        r = requests.get(find_url, params=params, timeout=8)
        r.raise_for_status()
        found = r.json()

        results = found.get("movie_results") or []
        if not results:
            return {}

        tmdb_id = results[0]["id"]

        reviews_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/reviews"
        params = {"api_key": TMDB_API_KEY, "language": "en-US", "page": 1}
        r2 = requests.get(reviews_url, params=params, timeout=8)
        r2.raise_for_status()
        reviews_data = r2.json()

        out = {}
        count = 0
        for item in reviews_data.get("results", []):
            if count >= max_reviews:
                break
            content = item.get("content")
            if not content:
                continue
            # run your classifier to keep UX consistent
            movie_review_list = np.array([content])
            movie_vector = vectorizer.transform(movie_review_list)
            pred = clf.predict(movie_vector)
            sentiment = "Positive" if pred else "Negative"
            out[content] = sentiment
            count += 1

        return out

    except Exception as e:
        print(f"TMDb fetch failed: {e}")
        return {}


@app.route("/recommend",methods=["POST"])
@app.route("/recommend", methods=["POST"])
def recommend():
    # getting data from AJAX request
    title = request.form['title']
    cast_ids = request.form['cast_ids']
    cast_names = request.form['cast_names']
    cast_chars = request.form['cast_chars']
    cast_bdays = request.form['cast_bdays']
    cast_bios = request.form['cast_bios']
    cast_places = request.form['cast_places']
    cast_profiles = request.form['cast_profiles']
    imdb_id = request.form['imdb_id']
    poster = request.form['poster']
    genres = request.form['genres']
    overview = request.form['overview']
    vote_average = request.form['rating']
    vote_count = request.form['vote_count']
    rel_date = request.form['rel_date']
    release_date = request.form['release_date']
    runtime = request.form['runtime']
    status = request.form['status']
    rec_movies = request.form['rec_movies']
    rec_posters = request.form['rec_posters']
    rec_movies_org = request.form['rec_movies_org']
    rec_year = request.form['rec_year']
    rec_vote = request.form['rec_vote']

    # suggestions
    suggestions = get_suggestions()

    # convert strings to lists
    rec_movies_org = convert_to_list(rec_movies_org)
    rec_movies = convert_to_list(rec_movies)
    rec_posters = convert_to_list(rec_posters)
    cast_names = convert_to_list(cast_names)
    cast_chars = convert_to_list(cast_chars)
    cast_profiles = convert_to_list(cast_profiles)
    cast_bdays = convert_to_list(cast_bdays)
    cast_bios = convert_to_list(cast_bios)
    cast_places = convert_to_list(cast_places)

    cast_ids = convert_to_list_num(cast_ids)
    rec_vote = convert_to_list_num(rec_vote)
    rec_year = convert_to_list_num(rec_year)

    # tidy bios/chars
    for i in range(len(cast_bios)):
        cast_bios[i] = cast_bios[i].replace(r'\n', '\n').replace(r'\"', '\"')
    for i in range(len(cast_chars)):
        cast_chars[i] = cast_chars[i].replace(r'\n', '\n').replace(r'\"', '\"')

    # dictionaries for template
    movie_cards = {
        rec_posters[i]: [rec_movies[i], rec_movies_org[i], rec_vote[i], rec_year[i]]
        for i in range(len(rec_posters))
    }
    casts = {
        cast_names[i]: [cast_ids[i], cast_chars[i], cast_profiles[i]]
        for i in range(len(cast_profiles))
    }
    cast_details = {
        cast_names[i]: [cast_ids[i], cast_profiles[i], cast_bdays[i], cast_places[i], cast_bios[i]]
        for i in range(len(cast_places))
    }

   
    movie_reviews = {}  # default: no reviews
    try:
        url = f"https://www.imdb.com/title/{imdb_id}/reviews?ref_=tt_ov_rt"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        soup = bs.BeautifulSoup(r.text, "lxml")
        soup_result = soup.find_all("div", {"class": "text show-more__control"})

        reviews_list = []
        reviews_status = []
        for reviews in soup_result:
            if reviews.string:
                reviews_list.append(reviews.string)
                movie_review_list = np.array([reviews.string])
                movie_vector = vectorizer.transform(movie_review_list)
                pred = clf.predict(movie_vector)
                reviews_status.append('Positive' if pred else 'Negative')

        if reviews_list:
            movie_reviews = {
                reviews_list[i]: reviews_status[i] for i in range(len(reviews_list))
            }
    except Exception as e:
        print(f"IMDb reviews fetch failed: {e}")
        movie_reviews = {}

    if not movie_reviews:
        movie_reviews = get_tmdb_reviews_from_imdb(imdb_id)

    # dates
    movie_rel_date = ""
    curr_date = ""
    if rel_date:
        today = str(date.today())
        curr_date = datetime.strptime(today, '%Y-%m-%d')
        movie_rel_date = datetime.strptime(rel_date, '%Y-%m-%d')

    return render_template(
        'recommend.html',
        title=title,
        poster=poster,
        overview=overview,
        vote_average=vote_average,
        vote_count=vote_count,
        release_date=release_date,
        movie_rel_date=movie_rel_date,
        curr_date=curr_date,
        runtime=runtime,
        status=status,
        genres=genres,
        movie_cards=movie_cards,
        reviews=movie_reviews,  # may be empty
        casts=casts,
        cast_details=cast_details
    )

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=7860)
