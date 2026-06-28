# Project Roadmap

## Phase 1: Stabilize The Legacy Demo

Status: complete.

- Preserve the original UI workflow.
- Move secrets out of frontend JavaScript.
- Replace the old Flask runtime path with FastAPI.
- Keep old datasets under `data/legacy/`.

## Phase 2: Modern Data Pipeline

Status: complete for the demo, expandable for the 32M run.

- MovieLens ingestion.
- TMDb recent catalog builder.
- Catalog merge pipeline.
- Country/language transparency metadata.
- Runtime artifacts under `data/processed/`.

## Phase 3: Recommender Engine

Status: functional v1 complete.

- TF-IDF content retrieval.
- Item-item collaborative filtering.
- Compact semantic-vector retrieval.
- Hybrid ranker with explainable components.
- Offline evaluation for item-CF.

## Phase 4: API And UI Integration

Status: complete.

- FastAPI health/catalog/recommendation APIs.
- Existing UI search/detail/cast/review/recommendation traversal preserved.
- Live TMDb details, posters, cast, bios, and reviews.
- Front-page dataset transparency note.
- Self-recommendations are filtered from API and UI results.

## Phase 5: Professional Polish

Status: complete for the current Hugging Face demo.

- Runtime validation command.
- Final README and architecture documentation.
- Deployment verification on Hugging Face Spaces.
- Hugging Face deployment checklist.
- Clean Docker build context.
- Optional next upgrade: SentenceTransformer + FAISS artifact builder if storage and build time remain comfortable.
