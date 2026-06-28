# Dataset Strategy

The legacy project uses an older IMDb-style metadata CSV. V2 keeps that as a fallback, but the main dataset path is now:

```text
data/processed/movie_catalog.csv
```

The app automatically prefers that processed catalog when it exists. Otherwise, it falls back to:

```text
data/legacy/main_data.csv
```

Legacy CSVs from the original project live under:

```text
data/legacy/
```

## TMDb Key

Use this exact name locally and on Hugging Face:

```text
TMDB_API_KEY
```

Local `.env` example:

```bash
TMDB_API_KEY=your_tmdb_api_key_here
MOVIE_CATALOG_PATH=data/processed/movie_catalog.csv
```

On Hugging Face Spaces, add a repository secret named `TMDB_API_KEY`.

This project uses the official TMDb API. It does not scrape TMDb pages.

## MovieLens Variants

Use `small` for fast development:

```bash
python scripts/prepare_movielens.py --variant small
```

Recommended first deployment pipeline:

```bash
make pipeline-demo
```

This combines MovieLens small ratings with a broad recent TMDb catalog.

Use `32m` for the serious/offline project dataset:

```bash
python scripts/prepare_movielens.py --variant 32m
```

The `32m` raw dataset is too large to treat casually inside the repo. Generate it offline, keep `data/raw/` untracked, and commit or upload only compact processed artifacts that the Hugging Face Space needs.

## Filtering Examples

Build a compact catalog with only movies that have at least 20 ratings:

```bash
python scripts/prepare_movielens.py --variant 32m --min-ratings 20
```

Build a tiny demo catalog:

```bash
python scripts/prepare_movielens.py --variant small --limit 2000
```

The generated files are:

```text
data/processed/movie_catalog.csv
data/processed/catalog_metrics.csv
```

## Recent Movie Coverage With TMDb

MovieLens gives us ratings. TMDb gives us current movie discovery. To add post-2019 catalog coverage:

```bash
python scripts/build_tmdb_catalog.py --min-year 2019 --pages 50
```

This writes:

```text
data/processed/tmdb_recent_catalog.csv
```

This is not meant to be exhaustive. It pulls popular recent movies, which is better for a responsive demo than ingesting every low-vote or obscure title.

Country/origin metadata is enriched from TMDb details for a representative subset of the broad recent catalog. The front-page origin note should be read as a transparency estimate, not a census of every title.

For broader 2018-2026 coverage, run a per-year sweep:

```bash
make tmdb-broad-recent
```

That writes:

```text
data/processed/tmdb_broad_recent_catalog.csv
```

Use the broad catalog when recall matters more than artifact size and curation quality.

To keep both MovieLens and TMDb rows, write MovieLens to a separate file and merge:

```bash
python scripts/prepare_movielens.py \
  --variant 32m \
  --min-ratings 20 \
  --catalog-output-path data/processed/movielens_32m_catalog.csv

python scripts/build_tmdb_catalog.py \
  --min-year 2019 \
  --pages 50

python scripts/merge_catalogs.py \
  --inputs data/processed/movielens_32m_catalog.csv data/processed/tmdb_recent_catalog.csv \
  --output-path data/processed/movie_catalog.csv
```

## Collaborative Filtering Baseline

After preparing MovieLens, build item-item collaborative neighbors:

```bash
python scripts/train_item_cf.py \
  --ratings-path data/raw/ml-latest-small/ratings.csv \
  --catalog-path data/processed/movie_catalog.csv
```

For a larger `32m` run, start with conservative filters:

```bash
python scripts/train_item_cf.py \
  --ratings-path data/raw/ml-32m/ratings.csv \
  --catalog-path data/processed/movie_catalog.csv \
  --min-item-likes 20 \
  --max-users 100000
```

The generated files are:

```text
data/processed/item_neighbors.csv
data/processed/item_cf_metrics.csv
data/processed/item_cf_eval.csv
data/processed/semantic_index.npz
```

When `item_neighbors.csv` exists, the FastAPI app automatically blends collaborative recommendations with the content baseline.

Evaluate the baseline:

```bash
python scripts/evaluate_item_cf.py \
  --ratings-path data/raw/ml-latest-small/ratings.csv \
  --neighbors-path data/processed/item_neighbors.csv \
  --k 10
```

Build the semantic retrieval artifact:

```bash
python scripts/build_semantic_index.py \
  --catalog-path data/processed/movie_catalog.csv \
  --output-path data/processed/semantic_index.npz
```

This is a compact offline vector artifact. The live Hugging Face Space loads it directly and does not download an embedding model during startup.

## Why TMDb Is Still Needed

MovieLens is ideal for ratings and collaborative filtering, but it is not a poster/cast/overview database. TMDb gives the app current presentation metadata and lets the UI stay polished.

The long-term target is:

```text
MovieLens ratings -> collaborative filtering
MovieLens/TMDb metadata -> content features
TMDb API -> posters, cast, current movie details
```
