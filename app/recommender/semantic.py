from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re

import numpy as np

from app.recommender.content import Recommendation


TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class SemanticNeighbor:
    title: str
    score: float


class SemanticRecommender:
    """Loads compact precomputed dense text vectors for semantic-style retrieval."""

    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self._titles: list[str] | None = None
        self._embeddings: np.ndarray | None = None
        self._title_to_index: dict[str, int] | None = None

    @property
    def enabled(self) -> bool:
        return self.index_path.exists()

    def recommend(self, title: str, limit: int = 12) -> list[Recommendation]:
        if not self.enabled:
            return []

        index = self._find_index(title)
        if index is None:
            return []

        query_vector = self.embeddings[index]
        scores = self.embeddings @ query_vector
        order = np.argsort(scores)[::-1]
        recommendations: list[Recommendation] = []

        for candidate_index in order:
            if int(candidate_index) == index:
                continue
            score = float(scores[candidate_index])
            if score <= 0:
                continue
            recommendations.append(
                Recommendation(
                    title=self.titles[int(candidate_index)],
                    score=round(score, 4),
                    explanation="Semantically close movie profile.",
                    signals={"semantic_similarity": round(score, 4)},
                )
            )
            if len(recommendations) >= limit:
                break

        return recommendations

    @property
    def titles(self) -> list[str]:
        if self._titles is None:
            self._load_index()
        return self._titles or []

    @property
    def embeddings(self) -> np.ndarray:
        if self._embeddings is None:
            self._load_index()
        return self._embeddings if self._embeddings is not None else np.zeros((0, 0), dtype=np.float32)

    @property
    def title_to_index(self) -> dict[str, int]:
        if self._title_to_index is None:
            self._load_index()
        return self._title_to_index or {}

    def _load_index(self) -> None:
        data = np.load(self.index_path, allow_pickle=False)
        titles = [str(title) for title in data["titles"]]
        embeddings = data["embeddings"].astype(np.float32)
        self._titles = titles
        self._embeddings = embeddings
        self._title_to_index = {self._normalize(title): index for index, title in enumerate(titles)}

    def _find_index(self, title: str) -> int | None:
        normalized = self._normalize(title)
        if normalized in self.title_to_index:
            return self.title_to_index[normalized]

        best_title = max(
            self.title_to_index,
            key=lambda candidate: SequenceMatcher(None, normalized, candidate).ratio(),
            default="",
        )
        if best_title and SequenceMatcher(None, normalized, best_title).ratio() >= 0.72:
            return self.title_to_index[best_title]
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(TOKEN_RE.findall(value.lower()))
