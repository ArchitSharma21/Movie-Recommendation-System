from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

import requests

from app.config import Settings
from app.services.sentiment import label_sentiment


@dataclass(frozen=True)
class TmdbMovie:
    tmdb_id: int
    title: str
    original_title: str
    poster: str
    overview: str
    genres: str
    rating: float | str
    vote_count: str
    release_date_raw: str
    release_date_display: str
    runtime: str
    status: str
    imdb_id: str | None
    year: int | str


class TMDbService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.tmdb_api_key)

    def search_movie(self, title: str) -> TmdbMovie | None:
        results = self._get("/search/movie", {"query": title}).get("results", [])
        if not results:
            return None

        normalized = self._normalize(title)
        chosen = max(
            results,
            key=lambda item: max(
                SequenceMatcher(None, normalized, self._normalize(item.get("title", ""))).ratio(),
                SequenceMatcher(None, normalized, self._normalize(item.get("original_title", ""))).ratio(),
            ),
        )
        return self.movie_details(chosen["id"])

    def movie_details(self, tmdb_id: int) -> TmdbMovie | None:
        data = self._get(f"/movie/{tmdb_id}", {})
        if not data:
            return None

        poster_path = data.get("poster_path")
        release_date = data.get("release_date") or ""
        return TmdbMovie(
            tmdb_id=data["id"],
            title=data.get("title") or data.get("original_title") or "Unknown",
            original_title=data.get("original_title") or data.get("title") or "Unknown",
            poster=self._image_url(poster_path),
            overview=data.get("overview") or "Overview is not available.",
            genres=", ".join(genre["name"] for genre in data.get("genres", [])),
            rating=data.get("vote_average") or "N/A",
            vote_count=f"{data.get('vote_count') or 0:,}",
            release_date_raw=release_date,
            release_date_display=self._format_date(release_date),
            runtime=self._format_runtime(data.get("runtime")),
            status=data.get("status") or "Unknown",
            imdb_id=data.get("imdb_id"),
            year=self._year(release_date),
        )

    def cast(self, tmdb_id: int, limit: int = 10) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        credits = self._get(f"/movie/{tmdb_id}/credits", {})
        cast_cards: dict[str, list[str]] = {}
        cast_details: dict[str, list[str]] = {}

        for person in credits.get("cast", [])[:limit]:
            person_id = str(person.get("id"))
            name = person.get("name") or "Unknown"
            profile = self._image_url(person.get("profile_path"))
            character = person.get("character") or "Unknown"
            cast_cards[name] = [person_id, character, profile]

            detail = self._get(f"/person/{person_id}", {})
            cast_details[name] = [
                person_id,
                profile,
                self._format_date(detail.get("birthday") or ""),
                detail.get("place_of_birth") or "Not Available",
                detail.get("biography") or "Not Available",
            ]

        return cast_cards, cast_details

    def tmdb_recommendations(self, tmdb_id: int, limit: int = 12) -> list[TmdbMovie]:
        data = self._get(f"/movie/{tmdb_id}/recommendations", {})
        movies: list[TmdbMovie] = []
        for item in data.get("results", [])[:limit]:
            details = self.movie_details(item["id"])
            if details:
                movies.append(details)
        return movies

    def reviews(self, tmdb_id: int, limit: int = 8) -> dict[str, str]:
        data = self._get(f"/movie/{tmdb_id}/reviews", {"language": "en-US", "page": 1})
        reviews: dict[str, str] = {}
        for item in data.get("results", [])[:limit]:
            content = item.get("content") or ""
            if not content:
                continue
            trimmed = " ".join(content.split())
            if len(trimmed) > 700:
                trimmed = f"{trimmed[:697]}..."
            reviews[trimmed] = label_sentiment(trimmed)
        return reviews

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {}
        query = {"api_key": self.settings.tmdb_api_key, **params}
        try:
            response = requests.get(
                f"{self.settings.tmdb_base_url}{path}",
                params=query,
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return {}

    def _image_url(self, path: str | None) -> str:
        if path:
            return f"{self.settings.tmdb_image_base_url}{path}"
        return "/static/default.jpg"

    @staticmethod
    def _format_runtime(minutes: int | None) -> str:
        if not minutes:
            return "N/A"
        hours, remainder = divmod(int(minutes), 60)
        if hours and remainder:
            return f"{hours} hour(s) {remainder} min(s)"
        if hours:
            return f"{hours} hour(s)"
        return f"{remainder} min(s)"

    @staticmethod
    def _format_date(value: str) -> str:
        if not value:
            return "Unknown"
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%b %d %Y")
        except ValueError:
            return value

    @staticmethod
    def _year(value: str) -> int | str:
        if not value:
            return "N/A"
        try:
            return datetime.strptime(value, "%Y-%m-%d").year
        except ValueError:
            return "N/A"

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.lower().split())
