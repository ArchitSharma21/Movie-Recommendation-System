# Automation And Hosting Strategy

The live Hugging Face Space should serve compact prebuilt artifacts. It should not download MovieLens 32M or rebuild collaborative models on every startup.

## Recommended Flow

Run heavy updates locally or in a scheduled external job:

```bash
make pipeline-32m
```

For the first Hugging Face demo, use the lighter pipeline:

```bash
make pipeline-demo
```

The current demo pipeline writes a compact merged catalog with MovieLens ratings and broad recent TMDb coverage. It is intentionally broad-but-filtered, not an exhaustive dump of every TMDb title.

The UI still fetches rich movie details live from TMDb when a user opens a movie: poster, cast, cast biographies, review snippets, and recommendation-card metadata. The stored catalog is intentionally compact and optimized for retrieval/ranking.

Then commit or upload only the compact artifacts needed at runtime:

```text
data/processed/movie_catalog.csv
data/processed/item_neighbors.csv
data/processed/semantic_index.npz
data/processed/catalog_metrics.csv
data/processed/item_cf_metrics.csv
```

Keep raw downloads out of git:

```text
data/raw/
```

## Hugging Face Spaces

Hugging Face Spaces free CPU is a good runtime target for this app because inference is light:

- load compact CSV artifacts;
- serve FastAPI/Jinja pages;
- call TMDb for live details/posters/cast;
- avoid training during startup.

The free Space disk is not the right place to rely on scheduled persistent data generation. Treat the Space as a serving environment, not a data warehouse.

## Auto-Updates

Auto-update is possible, but should happen outside the Space:

1. Scheduled machine or CI job runs the dataset pipeline.
2. Job writes processed artifacts.
3. Job pushes updated artifacts to the Space repository or a storage backend.
4. Space restarts/rebuilds and serves the new artifacts.

This keeps cold starts predictable and avoids losing generated files when a Space restarts.

## TMDb Usage

The project uses the official TMDb API. It does not scrape TMDb web pages.

The TMDb catalog builder:

- uses `TMDB_API_KEY`;
- sends a user agent;
- sleeps between requests;
- retries transient failures;
- backs off when TMDb returns `429 Too Many Requests`.

The app should include TMDb attribution:

```text
This product uses the TMDb API but is not endorsed or certified by TMDb.
```
