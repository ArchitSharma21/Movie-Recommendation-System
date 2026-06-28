from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from difflib import SequenceMatcher
import math
from pathlib import Path
import re


TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "about",
    "after",
    "all",
    "also",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "her",
    "his",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "one",
    "or",
    "she",
    "that",
    "the",
    "their",
    "they",
    "this",
    "to",
    "when",
    "with",
    "who",
}


@dataclass(frozen=True)
class CatalogMovie:
    title: str
    display_title: str
    director: str
    actors: tuple[str, ...]
    genres: tuple[str, ...]
    text: str
    year: str = ""
    rating_count: int = 0
    rating_mean: float = 0.0
    original_language: str = ""
    origin_countries: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    title: str
    score: float
    explanation: str
    signals: dict[str, float | int | str]


class ContentRecommender:
    """Small CPU-friendly content recommender used as the first v2 baseline."""

    def __init__(self, catalog_path: Path) -> None:
        self.catalog_path = catalog_path
        self._movies: list[CatalogMovie] | None = None
        self._vectors: list[dict[str, float]] | None = None

    def suggestions(self) -> list[str]:
        return [movie.display_title for movie in self.movies]

    def stats(self) -> dict[str, int | str]:
        years = [int(movie.year) for movie in self.movies if movie.year.isdigit()]
        languages: Counter[str] = Counter()
        countries: Counter[str] = Counter()
        for movie in self.movies:
            if movie.original_language:
                languages[movie.original_language] += 1
            for country in movie.origin_countries:
                if country:
                    countries[country] += 1
        return {
            "catalog_path": str(self.catalog_path),
            "movies": len(self.movies),
            "min_year": min(years) if years else "unknown",
            "max_year": max(years) if years else "unknown",
            "top_languages": self._format_distribution(languages),
            "top_origins": self._format_distribution(countries),
        }

    def find(self, title: str) -> CatalogMovie | None:
        normalized = self._normalize(title)
        if not normalized:
            return None

        for movie in self.movies:
            if self._normalize(movie.title) == normalized:
                return movie

        best = max(
            self.movies,
            key=lambda movie: SequenceMatcher(None, normalized, self._normalize(movie.title)).ratio(),
            default=None,
        )
        if best and SequenceMatcher(None, normalized, self._normalize(best.title)).ratio() >= 0.72:
            return best
        return None

    def movie_signals(self, title: str) -> dict[str, float | int | str]:
        movie = self.find(title)
        if movie is None:
            return {}
        return {
            "year": movie.year,
            "rating_count": movie.rating_count,
            "rating_mean": movie.rating_mean,
            "genres": ", ".join(movie.genres),
        }

    def recommend(self, title: str, limit: int = 12) -> list[Recommendation]:
        source = self.find(title)
        if source is None:
            return []

        source_index = self.movies.index(source)
        source_vector = self.vectors[source_index]
        scored: list[tuple[float, CatalogMovie]] = []
        for index, movie in enumerate(self.movies):
            if index == source_index:
                continue
            score = self._cosine(source_vector, self.vectors[index])
            if score > 0:
                scored.append((score, movie))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            Recommendation(
                title=movie.display_title,
                score=round(score, 4),
                explanation=self._explain(source, movie),
                signals={
                    "content_similarity": round(score, 4),
                    "shared_genres": ", ".join(sorted(set(source.genres) & set(movie.genres))) or "None",
                    "year": movie.year,
                    "rating_count": movie.rating_count,
                    "rating_mean": movie.rating_mean,
                },
            )
            for score, movie in scored[:limit]
        ]

    @property
    def movies(self) -> list[CatalogMovie]:
        if self._movies is None:
            self._movies = self._load_movies()
        return self._movies

    @property
    def vectors(self) -> list[dict[str, float]]:
        if self._vectors is None:
            token_counts = [Counter(self._tokens(movie.text)) for movie in self.movies]
            doc_frequency: Counter[str] = Counter()
            for counts in token_counts:
                doc_frequency.update(counts.keys())

            total_docs = len(token_counts)
            idf = {
                token: math.log((1 + total_docs) / (1 + frequency)) + 1
                for token, frequency in doc_frequency.items()
            }
            self._vectors = [
                {token: count * idf[token] for token, count in counts.items()}
                for counts in token_counts
            ]
        return self._vectors

    def _load_movies(self) -> list[CatalogMovie]:
        movies: list[CatalogMovie] = []
        with self.catalog_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                title = (row.get("movie_title") or row.get("clean_title") or row.get("title") or "").strip()
                if not title:
                    continue
                is_legacy_catalog = "movie_title" in row
                actors = tuple(
                    value.strip()
                    for value in (row.get("actor_1_name"), row.get("actor_2_name"), row.get("actor_3_name"))
                    if value and value.strip()
                )
                genres = tuple(self._split_genres(row.get("genres", "")))
                text = row.get("comb") or row.get("text") or " ".join(
                    [title, *actors, row.get("director_name") or "", *genres, row.get("tags") or ""]
                )
                movies.append(
                    CatalogMovie(
                        title=title,
                        display_title=title.title() if is_legacy_catalog else title,
                        director=(row.get("director_name") or "").strip(),
                        actors=actors,
                        genres=genres,
                        text=text,
                        year=row.get("year", ""),
                        rating_count=self._as_int(row.get("rating_count")),
                        rating_mean=self._as_float(row.get("rating_mean")),
                        original_language=(row.get("original_language") or "").strip(),
                        origin_countries=tuple(self._split_multi_value(row.get("origin_countries") or "")),
                    )
                )
        return movies

    def _explain(self, source: CatalogMovie, candidate: CatalogMovie) -> str:
        shared_genres = sorted(set(source.genres) & set(candidate.genres))
        shared_people = sorted(({source.director, *source.actors} & {candidate.director, *candidate.actors}) - {""})
        if shared_people and shared_genres:
            return f"Similar cast/crew and shared {', '.join(shared_genres[:2])} tone."
        if shared_people:
            return f"Shares {', '.join(shared_people[:2])} with the selected movie."
        if shared_genres:
            return f"Matches on {', '.join(shared_genres[:3])}."
        return "Close match from the content profile."

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        common = set(left) & set(right)
        numerator = sum(left[token] * right[token] for token in common)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(TOKEN_RE.findall(value.lower()))

    @staticmethod
    def _tokens(value: str) -> list[str]:
        return [
            token
            for token in TOKEN_RE.findall(value.lower())
            if token not in STOPWORDS and (len(token) > 1 or token.isdigit())
        ]

    @staticmethod
    def _split_genres(value: str) -> list[str]:
        value = value.replace("(no genres listed)", "")
        if "|" in value:
            return [item.strip() for item in value.split("|") if item.strip()]
        return [item.strip() for item in value.split() if item.strip()]

    @staticmethod
    def _split_multi_value(value: str) -> list[str]:
        if "|" in value:
            return [item.strip() for item in value.split("|") if item.strip()]
        return [value.strip()] if value.strip() else []

    @staticmethod
    def _format_distribution(counter: Counter[str], limit: int = 4) -> str:
        total = sum(counter.values())
        if not total:
            return "unknown"
        parts = []
        for value, count in counter.most_common(limit):
            parts.append(f"{value} {round((count / total) * 100)}%")
        return ", ".join(parts)

    @staticmethod
    def _as_int(value: str | None) -> int:
        try:
            return int(float(value or 0))
        except ValueError:
            return 0

    @staticmethod
    def _as_float(value: str | None) -> float:
        try:
            return float(value or 0.0)
        except ValueError:
            return 0.0
