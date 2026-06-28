from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path
import time

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

import requests


TMDB_BASE_URL = "https://api.themoviedb.org/3"
USER_AGENT = "Movie-Recommendation-System/2.0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich a TMDb catalog with country/language fields from movie details.")
    parser.add_argument("--input-path", type=Path, default=Path("data/processed/tmdb_broad_recent_catalog.csv"))
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/tmdb_broad_recent_catalog.csv"))
    parser.add_argument("--limit-per-year", type=int, default=100)
    parser.add_argument("--sleep", type=float, default=0.03)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--max-retries", type=int, default=4)
    args = parser.parse_args()

    load_local_env()
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        raise SystemExit("TMDB_API_KEY is required in .env or environment variables.")

    rows = load_rows(args.input_path)
    selected = select_rows(rows, args.limit_per_year)
    print(f"Enriching {len(selected)} of {len(rows)} rows")

    try:
        for index, row in enumerate(selected, start=1):
            tmdb_id = row.get("tmdb_id")
            if not tmdb_id:
                continue
            if row.get("origin_countries"):
                continue
            details = tmdb_get(f"/movie/{tmdb_id}", {"api_key": api_key}, args.max_retries)
            origin_countries = details.get("origin_country") or [
                item.get("iso_3166_1")
                for item in details.get("production_countries", [])
                if item.get("iso_3166_1")
            ]
            row["origin_countries"] = "|".join(country for country in origin_countries if country)
            row["original_language"] = details.get("original_language") or row.get("original_language", "")
            if index % args.checkpoint_every == 0:
                write_rows(args.output_path, rows)
                print(f"Enriched {index}/{len(selected)}")
            time.sleep(args.sleep)
    finally:
        write_rows(args.output_path, rows)
    print(f"Wrote {args.output_path}")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def select_rows(rows: list[dict[str, str]], limit_per_year: int) -> list[dict[str, str]]:
    if limit_per_year <= 0:
        return rows
    selected: list[dict[str, str]] = []
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        year = row.get("year") or "unknown"
        if row.get("origin_countries"):
            continue
        if counts[year] >= limit_per_year:
            continue
        selected.append(row)
        counts[year] += 1
    return selected


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def tmdb_get(path: str, params: dict[str, str], max_retries: int) -> dict:
    wait_seconds = 1.0
    for attempt in range(max_retries + 1):
        response = requests.get(
            f"{TMDB_BASE_URL}{path}",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else wait_seconds
            print(f"TMDb rate limited request. Waiting {wait_seconds:.1f}s before retry.")
            time.sleep(wait_seconds)
            wait_seconds = min(wait_seconds * 2, 60)
            continue
        try:
            response.raise_for_status()
            return response.json()
        except requests.HTTPError:
            if attempt >= max_retries or response.status_code < 500:
                raise
            print(f"TMDb request failed with {response.status_code}. Retrying in {wait_seconds:.1f}s.")
            time.sleep(wait_seconds)
            wait_seconds = min(wait_seconds * 2, 60)
    raise RuntimeError("TMDb request failed after retries.")


def load_local_env(path: Path = Path(".env")) -> None:
    if load_dotenv:
        load_dotenv(path)
        return
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()
