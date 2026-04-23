"""Brand and legal compliance checks for campaign copy and rendered creatives."""

from __future__ import annotations

import logging
from pathlib import Path

from campaign_schema import BrandConfig, parse_hex_color
from PIL import Image

logger = logging.getLogger(__name__)


def estimate_bottom_strip_contrast(path: Path) -> float:
    """
    Heuristic: contrast between ~lightest and ~darkest sRGB in the bottom 20% of the image.
    """
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        y0 = int(h * 0.8)
        crop = im.crop((0, y0, w, h))
    cw, ch = crop.size
    px = crop.load()
    lums: list[float] = []
    for y in range(ch):
        for x in range(cw):
            r, g, b = px[x, y]
            lums.append(_relative_luminance_255(r, g, b))
    if not lums:
        return 1.0
    lums.sort()
    n = len(lums)
    lo = lums[n // 20]  # ~5th percentile
    hi = lums[19 * n // 20]  # ~95th percentile
    l_min, l_max = (lo, hi) if lo <= hi else (hi, lo)
    if l_max < 0.0001 and l_min < 0.0001:
        return 1.0
    return (l_max + 0.05) / (l_min + 0.05)


def _relative_luminance_255(r: int, g: int, b: int) -> float:
    def channel(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r_, g_, b_ = channel(float(r)), channel(float(g)), channel(float(b))
    return 0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_


def _color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def primary_color_coverage(
    path: Path, *, rgb: tuple[int, int, int], max_dist: float = 50.0
) -> float:
    """Fraction of pixels within max_dist (Euclidean in RGB) of the brand color."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        if w * h == 0:
            return 0.0
        step = max(1, (w * h) // 50_000)
        close = 0
        n = 0
        px = im.load()
        for y in range(0, h, step):
            for x in range(0, w, step):
                r, g, b = px[x, y]
                n += 1
                if _color_distance((r, g, b), rgb) <= max_dist:
                    close += 1
    return close / n if n else 0.0


def check_brand_image(
    path: Path, config: BrandConfig, *, repo_root: Path
) -> tuple[bool, list[str]]:
    """
    Run best-effort brand checks on a rendered PNG.

    Returns (ok, human-readable issues).
    """
    issues: list[str] = []
    if not path.is_file():
        return False, [f"Missing output file: {path}"]

    try:
        ratio = estimate_bottom_strip_contrast(path)
    except OSError as exc:
        logger.warning("Contrast read failed for %s: %s", path, exc, exc_info=True)
        return False, [f"Could not read image: {path}"]

    if ratio < config.min_contrast_ratio:
        issues.append(
            f"Bottom-strip contrast {ratio:.2f} below minimum {config.min_contrast_ratio:.2f}"
        )

    if config.logo_path:
        logo = repo_root / config.logo_path
        if not logo.is_file():
            issues.append(f"Brand logo not found at {config.logo_path}")

    if config.primary_color and config.min_primary_color_coverage > 0:
        prgb = parse_hex_color(config.primary_color)
        if prgb is not None:
            cov = primary_color_coverage(path, rgb=prgb)
            if cov < config.min_primary_color_coverage:
                issues.append(
                    f"Primary color {config.primary_color} coverage {cov:.4f} below "
                    f"threshold {config.min_primary_color_coverage:.4f}"
                )

    return (len(issues) == 0, issues)
