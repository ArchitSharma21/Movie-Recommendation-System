from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re


TOKEN_RE = re.compile(r"[a-z0-9]+")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge MovieLens and TMDb catalog CSVs into one app catalog.")
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/movie_catalog.csv"))
    parser.add_argument("--metrics-output-path", type=Path, default=Path("data/processed/catalog_metrics.csv"))
    args = parser.parse_args()

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = merge_catalogs(args.inputs)
    write_catalog(args.output_path, rows)
    write_metrics(args.metrics_output_path, rows, args.inputs)
    print(f"Wrote {args.output_path} with {len(rows)} movies")
    print(f"Wrote {args.metrics_output_path}")


def merge_catalogs(paths: list[Path]) -> list[dict[str, str]]:
    rows_by_key: dict[str, dict[str, str]] = {}
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                normalized = key_for(row)
                if not normalized:
                    continue
                existing = rows_by_key.get(normalized)
                if existing is None:
                    rows_by_key[normalized] = normalize_row(row)
                    continue
                rows_by_key[normalized] = merge_row(existing, normalize_row(row))
    return list(rows_by_key.values())


def key_for(row: dict[str, str]) -> str:
    tmdb_id = row.get("tmdb_id") or row.get("tmdbId") or ""
    if tmdb_id:
        return f"tmdb:{tmdb_id}"
    title = row.get("clean_title") or row.get("title") or row.get("movie_title") or ""
    year = row.get("year") or ""
    return f"title:{normalize_text(title)}:{year}"


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    title = row.get("title") or row.get("clean_title") or row.get("movie_title") or ""
    clean_title = row.get("clean_title") or title
    return {
        "movie_id": row.get("movie_id") or row.get("movieId") or "",
        "title": title,
        "clean_title": clean_title,
        "year": row.get("year") or "",
        "genres": row.get("genres") or "",
        "tags": row.get("tags") or "",
        "rating_count": row.get("rating_count") or "0",
        "rating_mean": row.get("rating_mean") or "0.0",
        "imdb_id": row.get("imdb_id") or row.get("imdbId") or "",
        "tmdb_id": row.get("tmdb_id") or row.get("tmdbId") or "",
        "original_language": row.get("original_language") or row.get("language") or "",
        "origin_countries": row.get("origin_countries") or row.get("country") or "",
        "text": row.get("text") or " ".join([clean_title, row.get("genres") or "", row.get("tags") or ""]),
    }


def merge_row(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    merged = left.copy()
    for field, value in right.items():
        if not value:
            continue
        if field in {"tags", "text"} and merged.get(field):
            merged[field] = " ".join([merged[field], value])
        elif not merged.get(field) or field in {"rating_count", "rating_mean"}:
            merged[field] = value
    return merged


def write_catalog(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
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
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_metrics(path: Path, rows: list[dict[str, str]], inputs: list[Path]) -> None:
    years = [int(row["year"]) for row in rows if row.get("year", "").isdigit()]
    rated_movies = sum(1 for row in rows if int(float(row.get("rating_count") or 0)) > 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["variant", "movies", "rated_movies", "min_year", "max_year", "sources"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "variant": "merged",
                "movies": len(rows),
                "rated_movies": rated_movies,
                "min_year": min(years) if years else "",
                "max_year": max(years) if years else "",
                "sources": "|".join(str(path) for path in inputs),
            }
        )


def normalize_text(value: str) -> str:
    return " ".join(TOKEN_RE.findall(value.lower()))


if __name__ == "__main__":
    main()
