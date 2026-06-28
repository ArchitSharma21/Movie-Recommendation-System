---
title: Movie Recommendation System
emoji: 🎬
colorFrom: red
colorTo: indigo
sdk: docker
pinned: false
---

# Movie Recommendation System

A modernized movie recommendation project built for a production-style AI portfolio: backend APIs, content-based retrieval, TMDb metadata enrichment, explainable recommendation signals, and Hugging Face Spaces deployment.

This repository is being upgraded from an older Flask demo into a lean v2 architecture that can grow into a full hybrid recommender system.

This product uses the TMDb API but is not endorsed or certified by TMDb.

## Current V2 Capabilities

- FastAPI application served with Uvicorn.
- Hugging Face Spaces-compatible Docker deployment.
- Server-side TMDb integration using `TMDB_API_KEY` from environment secrets.
- Local content-based recommendation baseline using the existing movie catalog.
- Lightweight TF-IDF content retrieval with stopword filtering.
- Compact semantic-vector retrieval from precomputed catalog embeddings.
- Recommendation API with explanations and scoring signals.
- Existing UI flow preserved: search a movie, view details, cast, and recommendations.
- TMDb review fetch with lightweight sentiment labels.
- Self-recommendations filtered from recommendation results.
- Legacy bachelor-era datasets are preserved under `data/legacy/`.

## Planned AI/ML Roadmap

- MovieLens ingestion pipeline for ratings and movie metadata.
- Collaborative filtering baseline.
- Semantic content embeddings and FAISS retrieval.
- Hybrid ranking that combines collaborative, content, popularity, and recency signals.
- Evaluation with Precision@K, Recall@K, NDCG@K, and coverage.
- Explanation layer: shared genres, cast/crew overlap, semantic similarity, and user-history signals.

## Architecture

```text
MovieLens / TMDb
      |
Feature Pipeline
      |
User Features + Item Features
      |
Candidate Generation
  - Collaborative Filtering
  - Content Similarity
  - Embedding Retrieval
      |
Hybrid Ranking
      |
Explanation Layer
      |
FastAPI + UI
```

## Local Development

Create a `.env` file or export the key in your shell. Use this exact key name locally and in Hugging Face Space secrets:

```bash
export TMDB_API_KEY="your_tmdb_api_key_here"
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Or with `uv`:

```bash
uv pip install -r requirements.txt
```

Run the app:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

Then open `http://localhost:7860`.

You can also use the project Makefile:

```bash
make dev
make run
```

## Updating The Dataset

The legacy catalog is kept as a fallback. To build a newer processed catalog from MovieLens:

```bash
python scripts/prepare_movielens.py --variant small
```

For the stronger offline dataset:

```bash
python scripts/prepare_movielens.py --variant 32m --min-ratings 20
```

The app automatically prefers `data/processed/movie_catalog.csv` when it exists. See [docs/DATASETS.md](docs/DATASETS.md) for details.

To add newer TMDb coverage, use:

```bash
python scripts/build_tmdb_catalog.py --min-year 2019 --pages 50
```

Then merge the MovieLens and TMDb catalogs as described in [docs/DATASETS.md](docs/DATASETS.md).

For broader 2018-2026 TMDb coverage:

```bash
make tmdb-broad-recent
```

This is intentionally separate from the default demo pipeline because it makes many more API requests and pulls in more low-signal titles.

Build the first collaborative-filtering artifact:

```bash
python scripts/train_item_cf.py
```

When `data/processed/item_neighbors.csv` exists, the app automatically blends item-item collaborative recommendations into the API and UI results.
The item-CF evaluator writes `data/processed/item_cf_eval.csv` with Recall@K, Precision@K, MRR@K, and coverage.
The semantic index writes `data/processed/semantic_index.npz`, which is loaded at runtime without downloading a model.

For the full repeatable workflow:

```bash
make pipeline-small
```

For a stronger Hugging Face demo with MovieLens ratings plus broad recent TMDb coverage:

```bash
make pipeline-demo
```

For the larger offline workflow:

```bash
make pipeline-32m
```

See [docs/AUTOMATION.md](docs/AUTOMATION.md) for the auto-update and Hugging Face hosting strategy.
See [docs/ROADMAP.md](docs/ROADMAP.md) for the five-phase modernization status.
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the Hugging Face deployment checklist.

Validate runtime artifacts:

```bash
make validate
```

## Hugging Face Spaces

This project is designed for the free CPU Space tier:

- Heavy model training should happen offline or in a controlled build step.
- Runtime should use compact precomputed artifacts.
- TMDb credentials should be stored as a Space secret named `TMDB_API_KEY`.
- The app listens on port `7860`.
- Run `make validate` before deployment.

## API

Health check:

```text
GET /api/health
```

Suggestions:

```text
GET /api/suggestions
```

Content recommendation baseline:

```text
GET /api/recommendations?title=avatar&limit=12
```

Catalog stats:

```text
GET /api/catalog
```
