from dataclasses import dataclass
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - deployment installs python-dotenv
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parents[1]
if load_dotenv:
    load_dotenv(ROOT_DIR / ".env")


def _default_catalog_path() -> Path:
    configured = os.getenv("MOVIE_CATALOG_PATH")
    if configured:
        return Path(configured)

    processed_catalog = ROOT_DIR / "data" / "processed" / "movie_catalog.csv"
    if processed_catalog.exists():
        return processed_catalog

    return ROOT_DIR / "data" / "legacy" / "main_data.csv"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Movie Recommendation System"
    root_dir: Path = ROOT_DIR
    templates_dir: Path = ROOT_DIR / "templates"
    static_dir: Path = ROOT_DIR / "static"
    catalog_path: Path = _default_catalog_path()
    item_neighbors_path: Path = ROOT_DIR / "data" / "processed" / "item_neighbors.csv"
    semantic_index_path: Path = ROOT_DIR / "data" / "processed" / "semantic_index.npz"
    asset_version: str = os.getenv("ASSET_VERSION", "2026-06-28-arrow-preview")
    tmdb_api_key: str | None = os.getenv("TMDB_API_KEY")
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p/original"
    request_timeout_seconds: float = 8.0


settings = Settings()
