PYTHON ?= python3
PIP ?= pip

.PHONY: help dev run catalog-small catalog-32m tmdb-recent tmdb-broad-recent enrich-tmdb-broad merge-catalogs merge-small-recent merge-small-broad-recent build-semantic item-cf-small item-cf-32m eval-item-cf-small eval-item-cf-32m pipeline-small pipeline-demo pipeline-32m compile validate

help:
	@echo "Movie Recommendation System v2"
	@echo ""
	@echo "Common commands:"
	@echo "  make dev             Install Python dependencies"
	@echo "  make run             Start the FastAPI app on port 7860"
	@echo "  make pipeline-small  Build a small local MovieLens pipeline"
	@echo "  make pipeline-demo   Build MovieLens small + recent TMDb catalog for HF demo"
	@echo "  make pipeline-32m    Build the larger offline MovieLens + TMDb pipeline"
	@echo "  make compile         Syntax-check app and scripts"
	@echo "  make validate        Validate runtime artifacts and app readiness"

dev:
	$(PIP) install -r requirements.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload

catalog-small:
	$(PYTHON) scripts/prepare_movielens.py --variant small --catalog-output-path data/processed/movielens_small_catalog.csv

catalog-32m:
	$(PYTHON) scripts/prepare_movielens.py --variant 32m --min-ratings 20 --catalog-output-path data/processed/movielens_32m_catalog.csv

tmdb-recent:
	$(PYTHON) scripts/build_tmdb_catalog.py --min-year 2019 --pages 50

tmdb-broad-recent:
	$(PYTHON) scripts/build_tmdb_catalog.py --min-year 2018 --max-year 2026 --pages 50 --per-year --output-path data/processed/tmdb_broad_recent_catalog.csv

enrich-tmdb-broad:
	$(PYTHON) scripts/enrich_tmdb_metadata.py --input-path data/processed/tmdb_broad_recent_catalog.csv --output-path data/processed/tmdb_broad_recent_catalog.csv --limit-per-year 100

merge-catalogs:
	$(PYTHON) scripts/merge_catalogs.py --inputs data/processed/movielens_32m_catalog.csv data/processed/tmdb_recent_catalog.csv --output-path data/processed/movie_catalog.csv

merge-small-recent:
	$(PYTHON) scripts/merge_catalogs.py --inputs data/processed/movielens_small_catalog.csv data/processed/tmdb_recent_catalog.csv --output-path data/processed/movie_catalog.csv

merge-small-broad-recent:
	$(PYTHON) scripts/merge_catalogs.py --inputs data/processed/movielens_small_catalog.csv data/processed/tmdb_broad_recent_catalog.csv --output-path data/processed/movie_catalog.csv

item-cf-small:
	$(PYTHON) scripts/train_item_cf.py --ratings-path data/raw/ml-latest-small/ratings.csv --catalog-path data/processed/movie_catalog.csv --min-item-likes 5

item-cf-32m:
	$(PYTHON) scripts/train_item_cf.py --ratings-path data/raw/ml-32m/ratings.csv --catalog-path data/processed/movie_catalog.csv --min-item-likes 20 --max-users 100000

build-semantic:
	$(PYTHON) scripts/build_semantic_index.py --catalog-path data/processed/movie_catalog.csv --output-path data/processed/semantic_index.npz

eval-item-cf-small:
	$(PYTHON) scripts/evaluate_item_cf.py --ratings-path data/raw/ml-latest-small/ratings.csv --neighbors-path data/processed/item_neighbors.csv --k 10

eval-item-cf-32m:
	$(PYTHON) scripts/evaluate_item_cf.py --ratings-path data/raw/ml-32m/ratings.csv --neighbors-path data/processed/item_neighbors.csv --k 10 --max-users 100000

pipeline-small: catalog-small
	$(PYTHON) scripts/merge_catalogs.py --inputs data/processed/movielens_small_catalog.csv --output-path data/processed/movie_catalog.csv
	$(PYTHON) scripts/train_item_cf.py --ratings-path data/raw/ml-latest-small/ratings.csv --catalog-path data/processed/movie_catalog.csv --min-item-likes 5
	$(PYTHON) scripts/build_semantic_index.py --catalog-path data/processed/movie_catalog.csv --output-path data/processed/semantic_index.npz
	$(PYTHON) scripts/evaluate_item_cf.py --ratings-path data/raw/ml-latest-small/ratings.csv --neighbors-path data/processed/item_neighbors.csv --k 10

pipeline-demo: catalog-small tmdb-broad-recent enrich-tmdb-broad merge-small-broad-recent item-cf-small build-semantic eval-item-cf-small

pipeline-32m: catalog-32m tmdb-recent merge-catalogs item-cf-32m build-semantic eval-item-cf-32m

compile:
	$(PYTHON) -m py_compile app/__init__.py app/config.py app/main.py app/schemas.py app/recommender/__init__.py app/recommender/content.py app/recommender/hybrid.py app/recommender/item_cf.py app/recommender/semantic.py app/services/__init__.py app/services/sentiment.py app/services/tmdb.py scripts/prepare_movielens.py scripts/train_item_cf.py scripts/evaluate_item_cf.py scripts/build_tmdb_catalog.py scripts/enrich_tmdb_metadata.py scripts/build_semantic_index.py scripts/merge_catalogs.py scripts/validate_runtime.py

validate:
	$(PYTHON) scripts/validate_runtime.py
