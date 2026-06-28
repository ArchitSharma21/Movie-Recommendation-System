from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate item-item CF with leave-one-out liked-item ranking.")
    parser.add_argument("--ratings-path", type=Path, default=Path("data/raw/ml-latest-small/ratings.csv"))
    parser.add_argument("--neighbors-path", type=Path, default=Path("data/processed/item_neighbors.csv"))
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/item_cf_eval.csv"))
    parser.add_argument("--like-threshold", type=float, default=4.0)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--max-users", type=int, default=0)
    args = parser.parse_args()

    user_likes = load_user_likes(args.ratings_path, args.like_threshold, args.max_users)
    neighbors = load_neighbors(args.neighbors_path)
    metrics = evaluate(user_likes, neighbors, args.k)
    write_metrics(args.output_path, metrics)
    print(f"Wrote {args.output_path}")


def load_user_likes(
    path: Path,
    like_threshold: float,
    max_users: int,
) -> dict[str, list[tuple[int, str]]]:
    user_likes: dict[str, list[tuple[int, str]]] = defaultdict(list)
    seen_users: set[str] = set()

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            user_id = row["userId"]
            if max_users and user_id not in seen_users and len(seen_users) >= max_users:
                continue
            seen_users.add(user_id)

            if float(row["rating"]) < like_threshold:
                continue
            user_likes[user_id].append((int(row["timestamp"]), row["movieId"]))

    return {user_id: sorted(items) for user_id, items in user_likes.items() if len(items) >= 2}


def load_neighbors(path: Path) -> dict[str, list[tuple[str, float]]]:
    neighbors: dict[str, list[tuple[str, float]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            neighbors[row["movie_id"]].append((row["neighbor_movie_id"], float(row["score"])))
    return dict(neighbors)


def evaluate(
    user_likes: dict[str, list[tuple[int, str]]],
    neighbors: dict[str, list[tuple[str, float]]],
    k: int,
) -> dict[str, float | int]:
    evaluated_users = 0
    hits = 0
    reciprocal_rank_sum = 0.0
    recommended_items: Counter[str] = Counter()
    item_universe = {movie_id for items in user_likes.values() for _, movie_id in items}

    for liked_items in user_likes.values():
        holdout = liked_items[-1][1]
        history = [movie_id for _, movie_id in liked_items[:-1]]
        ranked = rank_from_history(history, neighbors, k)
        if not ranked:
            continue

        evaluated_users += 1
        recommended_items.update(ranked)
        if holdout in ranked:
            hits += 1
            reciprocal_rank_sum += 1.0 / (ranked.index(holdout) + 1)

    recall = hits / evaluated_users if evaluated_users else 0.0
    precision = hits / (evaluated_users * k) if evaluated_users else 0.0
    mrr = reciprocal_rank_sum / evaluated_users if evaluated_users else 0.0
    coverage = len(recommended_items) / len(item_universe) if item_universe else 0.0

    return {
        "k": k,
        "evaluated_users": evaluated_users,
        "hits": hits,
        "recall_at_k": round(recall, 6),
        "precision_at_k": round(precision, 6),
        "mrr_at_k": round(mrr, 6),
        "coverage": round(coverage, 6),
        "unique_recommended_items": len(recommended_items),
        "item_universe": len(item_universe),
    }


def rank_from_history(
    history: list[str],
    neighbors: dict[str, list[tuple[str, float]]],
    k: int,
) -> list[str]:
    history_set = set(history)
    scores: Counter[str] = Counter()
    for movie_id in history:
        for neighbor_id, score in neighbors.get(movie_id, []):
            if neighbor_id in history_set:
                continue
            scores[neighbor_id] += score
    return [movie_id for movie_id, _ in scores.most_common(k)]


def write_metrics(path: Path, metrics: dict[str, float | int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics))
        writer.writeheader()
        writer.writerow(metrics)


if __name__ == "__main__":
    main()
