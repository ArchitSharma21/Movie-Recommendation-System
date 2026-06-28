from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import math
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a lightweight item-item collaborative filtering baseline.")
    parser.add_argument("--ratings-path", type=Path, default=Path("data/raw/ml-latest-small/ratings.csv"))
    parser.add_argument("--catalog-path", type=Path, default=Path("data/processed/movie_catalog.csv"))
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/item_neighbors.csv"))
    parser.add_argument("--metrics-path", type=Path, default=Path("data/processed/item_cf_metrics.csv"))
    parser.add_argument("--like-threshold", type=float, default=4.0)
    parser.add_argument("--min-item-likes", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=25)
    parser.add_argument("--max-users", type=int, default=0, help="Optional cap for quick experiments.")
    args = parser.parse_args()

    movie_titles = load_titles(args.catalog_path)
    user_likes, item_likes = load_likes(args.ratings_path, args.like_threshold, args.max_users)
    eligible_items = {movie_id for movie_id, count in item_likes.items() if count >= args.min_item_likes}
    co_counts = count_co_likes(user_likes, eligible_items)
    neighbors = build_neighbors(co_counts, item_likes, args.top_k)

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    write_neighbors(args.output_path, neighbors, movie_titles)
    write_metrics(args.metrics_path, user_likes, item_likes, eligible_items, neighbors)

    print(f"Wrote {args.output_path}")
    print(f"Wrote {args.metrics_path}")


def load_titles(path: Path) -> dict[str, str]:
    titles: dict[str, str] = {}
    if not path.exists():
        return titles
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            movie_id = row.get("movie_id") or row.get("movieId")
            title = row.get("clean_title") or row.get("title")
            if movie_id and title:
                titles[movie_id] = title
    return titles


def load_likes(
    path: Path,
    like_threshold: float,
    max_users: int,
) -> tuple[dict[str, list[str]], Counter[str]]:
    user_likes: dict[str, list[str]] = defaultdict(list)
    item_likes: Counter[str] = Counter()
    seen_users: set[str] = set()

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            user_id = row["userId"]
            if max_users and user_id not in seen_users and len(seen_users) >= max_users:
                continue
            seen_users.add(user_id)

            if float(row["rating"]) < like_threshold:
                continue
            movie_id = row["movieId"]
            user_likes[user_id].append(movie_id)
            item_likes[movie_id] += 1

    return dict(user_likes), item_likes


def count_co_likes(user_likes: dict[str, list[str]], eligible_items: set[str]) -> Counter[tuple[str, str]]:
    co_counts: Counter[tuple[str, str]] = Counter()
    for liked_items in user_likes.values():
        filtered = sorted({movie_id for movie_id in liked_items if movie_id in eligible_items})
        for left_index, left in enumerate(filtered):
            for right in filtered[left_index + 1 :]:
                co_counts[(left, right)] += 1
    return co_counts


def build_neighbors(
    co_counts: Counter[tuple[str, str]],
    item_likes: Counter[str],
    top_k: int,
) -> dict[str, list[tuple[str, float, int]]]:
    candidates: dict[str, list[tuple[str, float, int]]] = defaultdict(list)
    for (left, right), count in co_counts.items():
        score = count / math.sqrt(item_likes[left] * item_likes[right])
        candidates[left].append((right, score, count))
        candidates[right].append((left, score, count))

    return {
        movie_id: sorted(values, key=lambda item: item[1], reverse=True)[:top_k]
        for movie_id, values in candidates.items()
    }


def write_neighbors(
    path: Path,
    neighbors: dict[str, list[tuple[str, float, int]]],
    movie_titles: dict[str, str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["movie_id", "title", "neighbor_movie_id", "neighbor_title", "score", "co_likes"],
        )
        writer.writeheader()
        for movie_id, values in sorted(neighbors.items(), key=lambda item: item[0]):
            for neighbor_id, score, co_likes in values:
                writer.writerow(
                    {
                        "movie_id": movie_id,
                        "title": movie_titles.get(movie_id, ""),
                        "neighbor_movie_id": neighbor_id,
                        "neighbor_title": movie_titles.get(neighbor_id, ""),
                        "score": round(score, 6),
                        "co_likes": co_likes,
                    }
                )


def write_metrics(
    path: Path,
    user_likes: dict[str, list[str]],
    item_likes: Counter[str],
    eligible_items: set[str],
    neighbors: dict[str, list[tuple[str, float, int]]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["users", "liked_interactions", "liked_items", "eligible_items", "items_with_neighbors"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "users": len(user_likes),
                "liked_interactions": sum(len(items) for items in user_likes.values()),
                "liked_items": len(item_likes),
                "eligible_items": len(eligible_items),
                "items_with_neighbors": len(neighbors),
            }
        )


if __name__ == "__main__":
    main()
