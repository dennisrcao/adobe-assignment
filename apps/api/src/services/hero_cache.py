"""Hero image cache: hash(product_id + claude_prompt) → cached PNG."""

import hashlib
import logging
from pathlib import Path

import httpx

from ..paths import get_repo_root

logger = logging.getLogger(__name__)


def _cache_dir() -> Path:
    d = get_repo_root() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(product_id: str, prompt: str) -> str:
    """Generate cache key from product_id and prompt (20-char SHA256 prefix)."""
    return hashlib.sha256(f"{product_id}:{prompt}".encode()).hexdigest()[:20]


def get_cached(product_id: str, prompt: str) -> Path | None:
    """Return cached hero Path if exists, else None."""
    path = _cache_dir() / f"{cache_key(product_id, prompt)}.png"
    return path if path.is_file() else None


async def save_to_cache(product_id: str, prompt: str, image_url: str) -> Path:
    """Download Luma CDN image and save to cache. Returns the cached Path."""
    key = cache_key(product_id, prompt)
    path = _cache_dir() / f"{key}.png"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(image_url)
        r.raise_for_status()
        path.write_bytes(r.content)
    logger.debug("Cached hero for %s → %s", product_id, path.name)
    return path
