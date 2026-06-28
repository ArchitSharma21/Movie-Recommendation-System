# Hugging Face Deployment

## Required Secret

Set this Space secret:

```text
TMDB_API_KEY
```

The app will run without the key, but posters, cast details, TMDb reviews, and live movie metadata will be degraded.

## Runtime Artifacts

The Space serves compact prebuilt artifacts:

```text
data/processed/movie_catalog.csv
data/processed/item_neighbors.csv
data/processed/semantic_index.npz
data/processed/catalog_metrics.csv
data/processed/item_cf_metrics.csv
data/processed/item_cf_eval.csv
```

Do not generate MovieLens/TMDb artifacts during Space startup.

## Pre-Deploy Checks

Run:

```bash
make compile
make validate
```

Expected health:

```text
catalog_loaded: true
tmdb_enabled: true
item_cf_enabled: true
semantic_enabled: true
```

## Hugging Face Settings

This repository uses Docker Spaces and listens on port `7860`.

The build context excludes local secrets, raw dataset downloads, caches, and old pickle models via `.dockerignore`.

## Manual Smoke Test

After deployment:

```text
GET /api/health
GET /api/catalog
GET /api/recommendations?title=Avatar&limit=5
```

Then test the UI flow:

1. Search for `Avatar`.
2. Open a recommended movie.
3. Confirm the app shows details, cast, reviews when available, and more recommendations.
