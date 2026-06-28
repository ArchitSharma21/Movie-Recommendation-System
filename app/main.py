from __future__ import annotations

from datetime import date, datetime

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.recommender import ContentRecommender, HybridRanker, ItemCFRecommender, SemanticRecommender
from app.schemas import RecommendationResponse
from app.services.tmdb import TMDbService, TmdbMovie


app = FastAPI(
    title=settings.app_name,
    description="A hybrid-ready movie recommendation system optimized for Hugging Face Spaces.",
    version="2.0.0",
)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

templates = Jinja2Templates(directory=settings.templates_dir)
recommender = ContentRecommender(settings.catalog_path)
item_cf = ItemCFRecommender(settings.catalog_path, settings.item_neighbors_path)
semantic = SemanticRecommender(settings.semantic_index_path)
hybrid_ranker = HybridRanker(recommender, item_cf, semantic)
tmdb = TMDbService(settings)


@app.get("/", response_class=HTMLResponse)
@app.get("/home", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "suggestions": recommender.suggestions(),
            "catalog_stats": recommender.stats(),
            "asset_version": settings.asset_version,
        },
    )


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "catalog_loaded": bool(recommender.movies),
        "catalog_path": str(settings.catalog_path),
        "tmdb_enabled": tmdb.enabled,
        "item_cf_enabled": item_cf.enabled,
        "semantic_enabled": semantic.enabled,
    }


@app.get("/api/catalog")
def catalog() -> dict[str, int | str]:
    return recommender.stats()


@app.get("/api/suggestions")
def suggestions() -> dict[str, list[str]]:
    return {"suggestions": recommender.suggestions()}


@app.get("/api/recommendations", response_model=RecommendationResponse)
def api_recommendations(
    title: str = Query(..., min_length=1),
    limit: int = Query(12, ge=1, le=24),
) -> RecommendationResponse:
    recommendations = hybrid_ranker.recommend(title, limit=limit)
    return RecommendationResponse(
        query=title,
        recommendations=[
            {
                "title": recommendation.title,
                "score": recommendation.score,
                "explanation": recommendation.explanation,
                "signals": recommendation.signals,
            }
            for recommendation in recommendations
        ],
    )


@app.post("/recommend", response_class=HTMLResponse)
async def recommend(request: Request) -> HTMLResponse:
    form = await request.form()
    title = str(form.get("title") or form.get("movie") or "").strip()
    if not title:
        return HTMLResponse(_not_found_fragment(), status_code=400)

    page_context = _build_recommendation_context(request, title)
    if page_context is None:
        return HTMLResponse(_not_found_fragment(), status_code=404)

    return templates.TemplateResponse(request, "recommend.html", page_context)


def _build_recommendation_context(request: Request, title: str) -> dict | None:
    tmdb_movie = tmdb.search_movie(title)
    catalog_movie = recommender.find(title)
    if tmdb_movie is None and catalog_movie is None:
        return None

    display_title = tmdb_movie.title if tmdb_movie else catalog_movie.display_title
    movie_cards = _movie_cards(title, tmdb_movie)
    casts, cast_details = tmdb.cast(tmdb_movie.tmdb_id) if tmdb_movie else ({}, {})
    reviews = tmdb.reviews(tmdb_movie.tmdb_id) if tmdb_movie else {}

    rel_date = tmdb_movie.release_date_raw if tmdb_movie else ""
    movie_rel_date = datetime.strptime(rel_date, "%Y-%m-%d") if rel_date else ""
    curr_date = datetime.strptime(str(date.today()), "%Y-%m-%d") if rel_date else ""

    return {
        "title": display_title,
        "poster": tmdb_movie.poster if tmdb_movie else "/static/default.jpg",
        "overview": tmdb_movie.overview if tmdb_movie else "Overview is not available.",
        "vote_average": tmdb_movie.rating if tmdb_movie else "N/A",
        "vote_count": tmdb_movie.vote_count if tmdb_movie else "0",
        "release_date": tmdb_movie.release_date_display if tmdb_movie else "Unknown",
        "movie_rel_date": movie_rel_date,
        "curr_date": curr_date,
        "runtime": tmdb_movie.runtime if tmdb_movie else "N/A",
        "status": tmdb_movie.status if tmdb_movie else "Unknown",
        "genres": tmdb_movie.genres if tmdb_movie else ", ".join(catalog_movie.genres),
        "movie_cards": movie_cards,
        "reviews": reviews,
        "casts": casts,
        "cast_details": cast_details,
    }


def _movie_cards(title: str, source_movie: TmdbMovie | None) -> dict[str, list[str | int | float]]:
    content_recommendations = hybrid_ranker.recommend(title, limit=12)
    cards: dict[str, list[str | int | float]] = {}

    for index, recommendation in enumerate(content_recommendations):
        enriched = tmdb.search_movie(recommendation.title)
        poster = enriched.poster if enriched else "/static/default.jpg"
        if poster == "/static/default.jpg":
            poster = f"{poster}?movie={index}"
        original_title = enriched.original_title if enriched else recommendation.title
        year = enriched.year if enriched else "N/A"
        rating = enriched.rating if enriched else round(recommendation.score * 10, 1)
        cards[poster] = [recommendation.title, original_title, rating, year]

    if cards or source_movie is None:
        return cards

    for movie in tmdb.tmdb_recommendations(source_movie.tmdb_id):
        cards[movie.poster] = [movie.title, movie.original_title, movie.rating, movie.year]

    return cards


def _not_found_fragment() -> str:
    return """
    <center>
      <h3>
        Sorry! The movie you requested is not in our database.
        Please check the spelling or try another title.
      </h3>
    </center>
    """
