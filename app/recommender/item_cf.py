from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re

from app.recommender.content import Recommendation


TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Neighbor:
    title: str
    score: float
    co_likes: int


class ItemCFRecommender:
    """Loads precomputed item-item collaborative filtering neighbors."""

    def __init__(self, catalog_path: Path, neighbors_path: Path) -> None:
        self.catalog_path = catalog_path
        self.neighbors_path = neighbors_path
        self._title_to_id: dict[str, str] | None = None
        self._id_to_title: dict[str, str] | None = None
        self._neighbors: dict[str, list[Neighbor]] | None = None

    @property
    def enabled(self) -> bool:
        return self.neighbors_path.exists()

    def recommend(self, title: str, limit: int = 12) -> list[Recommendation]:
        if not self.enabled:
            return []

        movie_id = self._find_movie_id(title)
        if movie_id is None:
            return []

        recommendations: list[Recommendation] = []
        for neighbor in self.neighbors.get(movie_id, [])[:limit]:
            recommendations.append(
                Recommendation(
                    title=neighbor.title,
                    score=round(neighbor.score, 4),
                    explanation="Users who liked the selected movie also liked this.",
                    signals={
                        "collaborative_similarity": round(neighbor.score, 4),
                        "co_likes": neighbor.co_likes,
                    },
                )
            )
        return recommendations

    @property
    def title_to_id(self) -> dict[str, str]:
        if self._title_to_id is None:
            self._load_catalog()
        return self._title_to_id or {}

    @property
    def id_to_title(self) -> dict[str, str]:
        if self._id_to_title is None:
            self._load_catalog()
        return self._id_to_title or {}

    @property
    def neighbors(self) -> dict[str, list[Neighbor]]:
        if self._neighbors is None:
            self._neighbors = self._load_neighbors()
        return self._neighbors

    def _load_catalog(self) -> None:
        title_to_id: dict[str, str] = {}
        id_to_title: dict[str, str] = {}
        if not self.catalog_path.exists():
            self._title_to_id = {}
            self._id_to_title = {}
            return

        with self.catalog_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                movie_id = row.get("movie_id") or row.get("movieId") or ""
                title = row.get("clean_title") or row.get("title") or row.get("movie_title") or ""
                if not movie_id or not title:
                    continue
                title_to_id[self._normalize(title)] = movie_id
                id_to_title[movie_id] = title

        self._title_to_id = title_to_id
        self._id_to_title = id_to_title

    def _load_neighbors(self) -> dict[str, list[Neighbor]]:
        neighbors: dict[str, list[Neighbor]] = defaultdict(list)
        if not self.neighbors_path.exists():
            return {}

        with self.neighbors_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                movie_id = row["movie_id"]
                neighbor_id = row["neighbor_movie_id"]
                title = row.get("neighbor_title") or self.id_to_title.get(neighbor_id, "")
                if not title:
                    continue
                neighbors[movie_id].append(
                    Neighbor(
                        title=title,
                        score=float(row.get("score") or 0.0),
                        co_likes=int(float(row.get("co_likes") or 0)),
                    )
                )
        return dict(neighbors)

    def _find_movie_id(self, title: str) -> str | None:
        normalized = self._normalize(title)
        if normalized in self.title_to_id:
            return self.title_to_id[normalized]

        best_title = max(
            self.title_to_id,
            key=lambda candidate: SequenceMatcher(None, normalized, candidate).ratio(),
            default="",
        )
        if best_title and SequenceMatcher(None, normalized, best_title).ratio() >= 0.72:
            return self.title_to_id[best_title]
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(TOKEN_RE.findall(value.lower()))
