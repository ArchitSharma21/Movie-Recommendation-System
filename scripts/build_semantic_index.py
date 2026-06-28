from __future__ import annotations

import argparse
import csv
import hashlib
import math
from pathlib import Path
import re

import numpy as np


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact dense text vectors for runtime semantic retrieval.")
    parser.add_argument("--catalog-path", type=Path, default=Path("data/processed/movie_catalog.csv"))
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/semantic_index.npz"))
    parser.add_argument("--dimensions", type=int, default=192)
    args = parser.parse_args()

    rows = load_rows(args.catalog_path)
    titles = np.array([row["clean_title"] or row["title"] for row in rows], dtype=np.str_)
    embeddings = np.vstack([embed(row, args.dimensions) for row in rows]).astype(np.float32)

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_path, titles=titles, embeddings=embeddings)
    print(f"Wrote {args.output_path} with {len(titles)} vectors x {args.dimensions} dimensions")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def embed(row: dict[str, str], dimensions: int) -> np.ndarray:
    text = " ".join(
        [
            row.get("clean_title") or row.get("title") or "",
            row.get("genres") or "",
            row.get("tags") or "",
            row.get("text") or "",
        ]
    )
    tokens = tokenize(text)
    vector = np.zeros(dimensions, dtype=np.float32)
    for token in tokens:
        weight = 1.0 + math.log1p(len(token))
        for salt in range(2):
            digest = hashlib.blake2b(f"{token}:{salt}".encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % dimensions
            sign = 1.0 if (value >> 8) & 1 else -1.0
            vector[index] += sign * weight

    norm = np.linalg.norm(vector)
    if norm:
        vector /= norm
    return vector


def tokenize(value: str) -> list[str]:
    return [
        token
        for token in TOKEN_RE.findall(value.lower())
        if token not in STOPWORDS and (len(token) > 1 or token.isdigit())
    ]


if __name__ == "__main__":
    main()
