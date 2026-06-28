from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import re
from urllib.request import urlretrieve
from zipfile import ZipFile


DATASETS = {
    "small": {
        "url": "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip",
        "folder": "ml-latest-small",
    },
    "32m": {
        "url": "https://files.grouplens.org/datasets/movielens/ml-32m.zip",
        "folder": "ml-32m",
    },
}

YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


@dataclass(frozen=True)
class MovieLensPaths:
    raw_dir: Path
    processed_dir: Path
    variant: str

    @property
    def zip_path(self) -> Path:
        return self.raw_dir / f"{DATASETS[self.variant]['folder']}.zip"

    @property
    def extract_dir(self) -> Path:
        return self.raw_dir / DATASETS[self.variant]["folder"]

    @property
    def movies_path(self) -> Path:
        return self.extract_dir / "movies.csv"

    @property
    def ratings_path(self) -> Path:
        return self.extract_dir / "ratings.csv"

    @property
    def links_path(self) -> Path:
        return self.extract_dir / "links.csv"

    @property
    def tags_path(self) -> Path:
        return self.extract_dir / "tags.csv"

    @property
    def catalog_output_path(self) -> Path:
        return self.processed_dir / "movie_catalog.csv"

    @property
    def metrics_output_path(self) -> Path:
        return self.processed_dir / "catalog_metrics.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and process MovieLens datasets.")
    parser.add_argument("--variant", choices=DATASETS, default="small")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--catalog-output-path", type=Path, default=None)
    parser.add_argument("--min-ratings", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0, help="Optional catalog row limit for tiny HF demos.")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    paths = MovieLensPaths(args.raw_dir, args.processed_dir, args.variant)
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    paths.processed_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_download:
        download_dataset(paths)
    extract_dataset(paths)

    ratings = summarize_ratings(paths.ratings_path)
    tags = summarize_tags(paths.tags_path)
    links = load_links(paths.links_path)
    catalog_output_path = args.catalog_output_path or paths.catalog_output_path
    write_catalog(paths.movies_path, catalog_output_path, ratings, tags, links, args.min_ratings, args.limit)
    write_metrics(paths.metrics_output_path, paths.variant, catalog_output_path, ratings)

    print(f"Wrote {catalog_output_path}")
    print(f"Wrote {paths.metrics_output_path}")


def download_dataset(paths: MovieLensPaths) -> None:
    if paths.zip_path.exists():
        print(f"Using existing {paths.zip_path}")
        return

    url = DATASETS[paths.variant]["url"]
    print(f"Downloading {url}")
    urlretrieve(url, paths.zip_path)


def extract_dataset(paths: MovieLensPaths) -> None:
    if paths.movies_path.exists() and paths.ratings_path.exists():
        print(f"Using existing extracted dataset at {paths.extract_dir}")
        return

    print(f"Extracting {paths.zip_path}")
    with ZipFile(paths.zip_path) as archive:
        archive.extractall(paths.raw_dir)


def summarize_ratings(path: Path) -> dict[str, dict[str, float]]:
    summaries: dict[str, dict[str, float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            movie_id = row["movieId"]
            rating = float(row["rating"])
            summary = summaries.setdefault(movie_id, {"rating_count": 0, "rating_sum": 0.0})
            summary["rating_count"] += 1
            summary["rating_sum"] += rating

    for summary in summaries.values():
        summary["rating_mean"] = round(summary["rating_sum"] / summary["rating_count"], 4)
        del summary["rating_sum"]
    return summaries


def summarize_tags(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}

    tags: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            movie_id = row["movieId"]
            tag = clean_text(row.get("tag", ""))
            if not tag:
                continue
            normalized = tag.lower()
            tag_set = seen.setdefault(movie_id, set())
            if normalized in tag_set:
                continue
            tag_set.add(normalized)
            tags.setdefault(movie_id, []).append(tag)
    return {movie_id: values[:20] for movie_id, values in tags.items()}


def load_links(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    links: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            links[row["movieId"]] = {
                "imdbId": row.get("imdbId", ""),
                "tmdbId": row.get("tmdbId", ""),
            }
    return links


def write_catalog(
    movies_path: Path,
    output_path: Path,
    ratings: dict[str, dict[str, float]],
    tags: dict[str, list[str]],
    links: dict[str, dict[str, str]],
    min_ratings: int,
    limit: int,
) -> None:
    count = 0
    with movies_path.open(newline="", encoding="utf-8") as source, output_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(
            target,
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

        for row in csv.DictReader(source):
            movie_id = row["movieId"]
            rating_summary = ratings.get(movie_id, {"rating_count": 0, "rating_mean": 0.0})
            if rating_summary["rating_count"] < min_ratings:
                continue

            title, year = split_title(row["title"])
            genres = row["genres"].replace("|", " ")
            movie_tags = tags.get(movie_id, [])
            link = links.get(movie_id, {})
            text = " ".join([title, genres, " ".join(movie_tags)])
            writer.writerow(
                {
                    "movie_id": movie_id,
                    "title": row["title"],
                    "clean_title": title,
                    "year": year,
                    "genres": genres,
                    "tags": "|".join(movie_tags),
                    "rating_count": int(rating_summary["rating_count"]),
                    "rating_mean": rating_summary["rating_mean"],
                    "imdb_id": link.get("imdbId", ""),
                    "tmdb_id": link.get("tmdbId", ""),
                    "original_language": "",
                    "origin_countries": "",
                    "text": clean_text(text),
                }
            )
            count += 1
            if limit and count >= limit:
                break


def write_metrics(
    output_path: Path,
    variant: str,
    catalog_path: Path,
    ratings: dict[str, dict[str, float]],
) -> None:
    row_count = 0
    min_year = ""
    max_year = ""
    with catalog_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            row_count += 1
            year = row.get("year") or ""
            if year:
                min_year = min(min_year, year) if min_year else year
                max_year = max(max_year, year) if max_year else year

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["variant", "movies", "rated_movies", "min_year", "max_year"])
        writer.writeheader()
        writer.writerow(
            {
                "variant": variant,
                "movies": row_count,
                "rated_movies": len(ratings),
                "min_year": min_year,
                "max_year": max_year,
            }
        )


def split_title(value: str) -> tuple[str, str]:
    match = YEAR_RE.search(value)
    if not match:
        return value.strip(), ""
    return YEAR_RE.sub("", value).strip(), match.group(1)


def clean_text(value: str) -> str:
    return " ".join(value.replace("(no genres listed)", "").split())


if __name__ == "__main__":
    main()
