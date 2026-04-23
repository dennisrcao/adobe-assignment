"""Resolve product hero image under input_assets/<product_id>/hero.{png,jpg,webp}."""

from pathlib import Path

from ..paths import get_repo_root

_HERO_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def find_hero_path(product_id: str) -> Path | None:
    base = get_repo_root() / "input_assets" / product_id
    for ext in _HERO_EXTS:
        p = base / f"hero{ext}"
        if p.is_file():
            return p
    return None
