from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import re

from app.recommender.content import ContentRecommender, Recommendation
from app.recommender.item_cf import ItemCFRecommender
from app.recommender.semantic import SemanticRecommender


@dataclass(frozen=True)
class HybridWeights:
    content: float = 0.45
    semantic: float = 0.20
    collaborative: float = 0.20
    popularity: float = 0.10
    rating: float = 0.10
    recency: float = 0.05


class HybridRanker:
    def __init__(
        self,
        content: ContentRecommender,
        item_cf: ItemCFRecommender,
        semantic: SemanticRecommender,
        weights: HybridWeights | None = None,
    ) -> None:
        self.content = content
        self.item_cf = item_cf
        self.semantic = semantic
        self.weights = weights or HybridWeights()

    def recommend(self, title: str, limit: int = 12) -> list[Recommendation]:
        candidates: dict[str, Recommendation] = {}
        source_keys = self._source_keys(title)
        content_recommendations = self.content.recommend(title, limit=limit * 4)
        collaborative_recommendations = self.item_cf.recommend(title, limit=limit * 4)
        semantic_recommendations = self.semantic.recommend(title, limit=limit * 4)

        for recommendation in content_recommendations:
            key = self._key(recommendation.title)
            if key in source_keys:
                continue
            candidates[key] = self._with_metadata(recommendation)

        for recommendation in collaborative_recommendations:
            self._merge(candidates, recommendation, source_keys)

        for recommendation in semantic_recommendations:
            self._merge(candidates, recommendation, source_keys)

        ranked = [self._rank_candidate(recommendation) for recommendation in candidates.values()]
        return [
            recommendation
            for recommendation in sorted(ranked, key=lambda item: item.score, reverse=True)
            if self._key(recommendation.title) not in source_keys
        ][:limit]

    def _merge(
        self,
        candidates: dict[str, Recommendation],
        recommendation: Recommendation,
        source_keys: set[str],
    ) -> None:
        key = self._key(recommendation.title)
        if key in source_keys:
            return
        existing = candidates.get(key)
        if existing is None:
            candidates[key] = self._with_metadata(recommendation)
            return

        candidates[key] = Recommendation(
            title=existing.title,
            score=max(existing.score, recommendation.score),
            explanation=f"{existing.explanation} Also supported by another retrieval signal.",
            signals={**existing.signals, **recommendation.signals},
        )

    def _with_metadata(self, recommendation: Recommendation) -> Recommendation:
        return Recommendation(
            title=recommendation.title,
            score=recommendation.score,
            explanation=recommendation.explanation,
            signals={**self.content.movie_signals(recommendation.title), **recommendation.signals},
        )

    def _rank_candidate(self, recommendation: Recommendation) -> Recommendation:
        content_score = self._as_float(recommendation.signals.get("content_similarity"))
        semantic_score = self._as_float(recommendation.signals.get("semantic_similarity"))
        collaborative_score = self._as_float(recommendation.signals.get("collaborative_similarity"))
        popularity_score = self._popularity_score(recommendation.signals.get("rating_count"))
        rating_score = self._rating_score(recommendation.signals.get("rating_mean"))
        recency_score = self._recency_score(recommendation.signals.get("year"))

        final_score = (
            self.weights.content * content_score
            + self.weights.semantic * semantic_score
            + self.weights.collaborative * collaborative_score
            + self.weights.popularity * popularity_score
            + self.weights.rating * rating_score
            + self.weights.recency * recency_score
        )
        final_score = round(final_score, 4)

        active_retrievers = [
            name
            for name, score in (
                ("content", content_score),
                ("semantic", semantic_score),
                ("collaborative", collaborative_score),
            )
            if score
        ]
        ranker = "hybrid" if len(active_retrievers) > 1 else active_retrievers[0] if active_retrievers else "metadata"
        signals = {
            **recommendation.signals,
            "content_component": round(content_score, 4),
            "semantic_component": round(semantic_score, 4),
            "collaborative_component": round(collaborative_score, 4),
            "popularity_component": round(popularity_score, 4),
            "rating_component": round(rating_score, 4),
            "recency_component": round(recency_score, 4),
            "ranker": ranker,
        }

        return Recommendation(
            title=recommendation.title,
            score=final_score,
            explanation=self._explain(recommendation, signals),
            signals=signals,
        )

    @staticmethod
    def _explain(recommendation: Recommendation, signals: dict[str, float | int | str]) -> str:
        reasons = []
        if signals.get("content_component"):
            reasons.append("content similarity")
        if signals.get("semantic_component"):
            reasons.append("semantic profile")
        if signals.get("collaborative_component"):
            reasons.append("user co-like patterns")
        if signals.get("recency_component", 0) >= 0.7:
            reasons.append("recent release")
        if signals.get("rating_component", 0) >= 0.75:
            reasons.append("strong audience rating")
        if not reasons:
            return recommendation.explanation
        return f"Ranked by {', '.join(reasons[:3])}."

    @staticmethod
    def _popularity_score(value: float | int | str | None) -> float:
        rating_count = max(HybridRanker._as_float(value), 0.0)
        return min(math.log1p(rating_count) / math.log1p(5000), 1.0)

    @staticmethod
    def _rating_score(value: float | int | str | None) -> float:
        rating = HybridRanker._as_float(value)
        if rating <= 0:
            return 0.0
        if rating > 5:
            return min(rating / 10, 1.0)
        return min(rating / 5, 1.0)

    @staticmethod
    def _recency_score(value: float | int | str | None) -> float:
        try:
            year = int(str(value))
        except (TypeError, ValueError):
            return 0.0

        current_year = date.today().year
        age = max(current_year - year, 0)
        if age <= 1:
            return 1.0
        if age >= 15:
            return 0.0
        return round((15 - age) / 14, 4)

    @staticmethod
    def _as_float(value: float | int | str | None) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _key(value: str) -> str:
        value = re.sub(r"\(\d{4}\)\s*$", "", value)
        return " ".join(re.findall(r"[a-z0-9]+", value.lower()))

    def _source_keys(self, title: str) -> set[str]:
        keys = {self._key(title)}
        source = self.content.find(title)
        if source:
            keys.add(self._key(source.title))
            keys.add(self._key(source.display_title))
        return {key for key in keys if key}
