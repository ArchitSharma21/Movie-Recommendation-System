from __future__ import annotations

import argparse
import csv
from datetime import date
import os
from pathlib import Path
import time

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

import requests


TMDB_BASE_URL = "https://api.themoviedb.org/3"
USER_AGENT = "Movie-Recommendation-System/2.0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a recent movie catalog from TMDb discover results.")
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/tmdb_recent_catalog.csv"))
    parser.add_argument("--min-year", type=int, default=2019)
    parser.add_argument("--max-year", type=int, default=date.today().year)
    parser.add_argument("--pages", type=int, default=25)
    parser.add_argument("--per-year", action="store_true", help="Run discover separately for each year.")
    parser.add_argument("--language", default="en-US")
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--max-retries", type=int, default=4)
    args = parser.parse_args()

    load_local_env()

    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        raise SystemExit("TMDB_API_KEY is required in .env or environment variables.")

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    genres = load_genres(api_key, args.language, args.max_retries)
    movies = discover_movies(
        api_key=api_key,
        genre_lookup=genres,
        min_year=args.min_year,
        max_year=args.max_year,
        pages=args.pages,
        language=args.language,
        sleep_seconds=args.sleep,
        max_retries=args.max_retries,
        per_year=args.per_year,
    )
    write_catalog(args.output_path, movies)
    print(f"Wrote {args.output_path} with {len(movies)} movies")


def load_genres(api_key: str, language: str, max_retries: int) -> dict[int, str]:
    response = tmdb_get(
        "/genre/movie/list",
        params={"api_key": api_key, "language": language},
        max_retries=max_retries,
    )
    return {item["id"]: item["name"] for item in response.json().get("genres", [])}


def discover_movies(
    api_key: str,
    genre_lookup: dict[int, str],
    min_year: int,
    max_year: int,
    pages: int,
    language: str,
    sleep_seconds: float,
    max_retries: int,
    per_year: bool,
) -> list[dict[str, str | int | float]]:
    movies: dict[int, dict[str, str | int | float]] = {}
    ranges = [(min_year, max_year)]
    if per_year:
        ranges = [(year, year) for year in range(min_year, max_year + 1)]

    for start_year, end_year in ranges:
        start_date = f"{start_year}-01-01"
        end_date = min(f"{end_year}-12-31", date.today().isoformat())
        for page in range(1, pages + 1):
            response = tmdb_get(
                "/discover/movie",
                params={
                    "api_key": api_key,
                    "language": language,
                    "sort_by": "popularity.desc",
                    "include_adult": "false",
                    "include_video": "false",
                    "primary_release_date.gte": start_date,
                    "primary_release_date.lte": end_date,
                    "vote_count.gte": 25,
                    "page": page,
                },
                max_retries=max_retries,
            )
            for item in response.json().get("results", []):
                tmdb_id = item["id"]
                release_date = item.get("release_date") or ""
                year = release_date[:4] if release_date else ""
                origin_countries = item.get("origin_country") or []
                genre_names = [
                    genre_lookup[genre_id]
                    for genre_id in item.get("genre_ids", [])
                    if genre_id in genre_lookup
                ]
                title = item.get("title") or item.get("original_title") or ""
                if not title:
                    continue
                text = " ".join([title, item.get("overview") or "", " ".join(genre_names)])
                movies[tmdb_id] = {
                    "movie_id": f"tmdb-{tmdb_id}",
                    "title": f"{title} ({year})" if year else title,
                    "clean_title": title,
                    "year": year,
                    "genres": " ".join(genre_names),
                    "tags": "",
                    "rating_count": item.get("vote_count") or 0,
                    "rating_mean": item.get("vote_average") or 0.0,
                    "imdb_id": "",
                    "tmdb_id": tmdb_id,
                    "original_language": item.get("original_language") or "",
                    "origin_countries": "|".join(origin_countries),
                    "text": " ".join(text.split()),
                }
            time.sleep(sleep_seconds)

    return list(movies.values())


def tmdb_get(path: str, params: dict[str, str | int], max_retries: int) -> requests.Response:
    wait_seconds = 1.0
    for attempt in range(max_retries + 1):
        response = requests.get(
            f"{TMDB_BASE_URL}{path}",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else wait_seconds
            print(f"TMDb rate limited request. Waiting {wait_seconds:.1f}s before retry.")
            time.sleep(wait_seconds)
            wait_seconds = min(wait_seconds * 2, 60)
            continue
        try:
            response.raise_for_status()
            return response
        except requests.HTTPError:
            if attempt >= max_retries or response.status_code < 500:
                raise
            print(f"TMDb request failed with {response.status_code}. Retrying in {wait_seconds:.1f}s.")
            time.sleep(wait_seconds)
            wait_seconds = min(wait_seconds * 2, 60)

    raise RuntimeError("TMDb request failed after retries.")


def write_catalog(path: Path, movies: list[dict[str, str | int | float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "movie_id",
                "title",
                "clean_title",
                "year",
                "genres",
                "tags",
                "rating_count",
                "rating_mean",
                "imdb_id",
                "tmdb_id",
                "original_language",
                "origin_countries",
                "text",
            ],
        )
        writer.writeheader()
        writer.writerows(movies)


def load_local_env(path: Path = Path(".env")) -> None:
    if load_dotenv:
        load_dotenv(path)
        return
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()
