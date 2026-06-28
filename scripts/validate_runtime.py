from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re
import sys

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.main import api_recommendations, catalog, health


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate runtime artifacts and app-level recommendation readiness.")
    parser.add_argument("--catalog-path", type=Path, default=Path("data/processed/movie_catalog.csv"))
    parser.add_argument("--neighbors-path", type=Path, default=Path("data/processed/item_neighbors.csv"))
    parser.add_argument("--semantic-path", type=Path, default=Path("data/processed/semantic_index.npz"))
    parser.add_argument("--static-dir", type=Path, default=Path("static"))
    parser.add_argument("--query", default="Avatar")
    parser.add_argument("--min-movies", type=int, default=1000)
    args = parser.parse_args()

    failures: list[str] = []
    catalog_rows = count_csv_rows(args.catalog_path)
    neighbor_rows = count_csv_rows(args.neighbors_path)
    semantic_rows = count_semantic_rows(args.semantic_path)
    static_failures = validate_static_assets(args.static_dir)
    health_payload = health()
    catalog_payload = catalog()
    recommendations = api_recommendations(args.query, 5).recommendations

    if catalog_rows < args.min_movies:
        failures.append(f"catalog has only {catalog_rows} rows")
    if neighbor_rows == 0:
        failures.append("item neighbor artifact is empty")
    if semantic_rows != catalog_rows:
        failures.append(f"semantic index rows ({semantic_rows}) do not match catalog rows ({catalog_rows})")
    if not health_payload.get("tmdb_enabled"):
        failures.append("TMDb is not enabled; check TMDB_API_KEY")
    if not health_payload.get("item_cf_enabled"):
        failures.append("item-CF artifact is not enabled")
    if not health_payload.get("semantic_enabled"):
        failures.append("semantic artifact is not enabled")
    if not recommendations:
        failures.append(f"no recommendations returned for {args.query!r}")
    if any(normalize_title(item.title) == normalize_title(args.query) for item in recommendations):
        failures.append(f"self-recommendation returned for {args.query!r}")
    failures.extend(static_failures)

    print("Runtime validation")
    print(f"- catalog rows: {catalog_rows}")
    print(f"- item neighbor rows: {neighbor_rows}")
    print(f"- semantic rows: {semantic_rows}")
    print(f"- static assets: {args.static_dir}")
    print(f"- health: {health_payload}")
    print(f"- catalog: {catalog_payload}")
    print(f"- sample recommendations: {[item.title for item in recommendations]}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        sys.exit(1)

    print("\nValidation passed.")


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def count_semantic_rows(path: Path) -> int:
    if not path.exists():
        return 0
    data = np.load(path, allow_pickle=False)
    _ = data["titles"]
    return int(data["embeddings"].shape[0])


def validate_static_assets(static_dir: Path) -> list[str]:
    failures = []
    for filename in ["style.css", "recommend.js", "autocomplete.js", "image.jpg", "loader.gif", "default.jpg"]:
        path = static_dir / filename
        if not path.exists():
            failures.append(f"missing static asset: {path}")
        elif path.stat().st_size == 0:
            failures.append(f"empty static asset: {path}")
    return failures


def normalize_title(value: str) -> str:
    value = re.sub(r"\(\d{4}\)\s*$", "", value)
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


if __name__ == "__main__":
    main()
