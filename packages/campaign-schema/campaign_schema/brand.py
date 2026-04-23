"""Brand configuration and legal copy checks (no FastAPI / app imports)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_PROHIBITED = ("guarantee", "cure", "miracle", "risk-free", "100% free")


@dataclass
class BrandConfig:
    """Loaded from a brand YAML file with fallbacks."""

    prohibited_words: tuple[str, ...] = _DEFAULT_PROHIBITED
    min_contrast_ratio: float = 3.0
    logo_path: str | None = None
    primary_color: str | None = None
    min_primary_color_coverage: float = 0.0001


def _parse_hex_color(value: str) -> tuple[int, int, int] | None:
    s = value.strip().lstrip("#")
    if len(s) != 6 or not re.fullmatch(r"[0-9a-fA-F]+", s):
        return None
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def parse_hex_color(value: str) -> tuple[int, int, int] | None:
    """Parse a 6-digit hex color; used by API image checks and brand loading."""
    return _parse_hex_color(value)


def load_brand_config(brand_path: Path) -> BrandConfig:
    """Load brand config from the given YAML path or return defaults."""
    if not brand_path.is_file():
        logger.info("No brand config at %s, using defaults", brand_path)
        return BrandConfig()
    data = yaml.safe_load(brand_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return BrandConfig()
    words = data.get("prohibited_words")
    prohibited: tuple[str, ...] = _DEFAULT_PROHIBITED
    if isinstance(words, list) and all(isinstance(x, str) for x in words):
        cleaned = tuple(w.strip().lower() for w in words if w and w.strip())
        prohibited = cleaned if len(cleaned) > 0 else _DEFAULT_PROHIBITED
    raw_logo = data.get("logo_path")
    logo: str | None
    if raw_logo in (None, "null", ""):
        logo = None
    elif isinstance(raw_logo, str) and raw_logo.strip():
        logo = raw_logo.strip()
    else:
        logo = None
    min_c = data.get("min_contrast_ratio", 3.0)
    try:
        min_contrast = float(min_c) if min_c is not None else 3.0
    except (TypeError, ValueError):
        min_contrast = 3.0
    pc = data.get("primary_color")
    primary = pc.strip() if isinstance(pc, str) and _parse_hex_color(pc) else None
    cov = data.get("min_primary_color_coverage", 0.0001)
    try:
        min_cov = float(cov) if cov is not None else 0.0001
    except (TypeError, ValueError):
        min_cov = 0.0001
    return BrandConfig(
        prohibited_words=prohibited,
        min_contrast_ratio=max(1.0, min_contrast),
        logo_path=logo,
        primary_color=primary,
        min_primary_color_coverage=max(0.0, min_cov),
    )


def check_prohibited_words(text: str, words: tuple[str, ...]) -> tuple[bool, list[str]]:
    """Return (ok, matched_terms). Whole words and phrases, case-insensitive."""
    if not text:
        return True, []
    t = text
    found: list[str] = []
    for w in words:
        w = w.strip()
        if not w:
            continue
        if " " in w:
            if re.search(re.escape(w), t, re.IGNORECASE):
                found.append(w)
        else:
            if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", t, re.IGNORECASE):
                found.append(w)
    return (len(found) == 0), found
