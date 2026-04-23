"""Repository-root paths (uvicorn cwd: apps/api; repo root is four levels up from src)."""

from pathlib import Path


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent
