"""Tests for compliance checks (no external APIs)."""

from pathlib import Path

from campaign_schema import (
    BrandConfig,
    check_prohibited_words,
    load_brand_config,
)
from PIL import Image
from src.paths import get_repo_root
from src.services.checks import check_brand_image, estimate_bottom_strip_contrast


def test_prohibited_hits() -> None:
    ok, hits = check_prohibited_words(
        "Our miracle cure is guaranteed", ("miracle", "cure", "guarantee")
    )
    assert not ok
    assert "miracle" in hits
    assert "cure" in hits


def test_prohibited_whole_word() -> None:
    ok, _ = check_prohibited_words("Recurring", ("cure",))
    assert ok  # "cure" as substring of Recurring for whole-word — actually "curing" - "cure" in "Recurring"? "Recurring" doesn't contain "cure" as whole word. "secure" - no. Good
    ok2, _ = check_prohibited_words("A secure fit", ("cure",))
    assert ok2  # secure doesn't match cure


def test_contrast_synthetic(tmp_path: Path) -> None:
    # Bottom 20% must mix light and dark (uniform bars can measure as low contrast)
    p = tmp_path / "bw.png"
    im = Image.new("RGB", (200, 200), (255, 255, 255))
    px = im.load()
    for y in range(160, 200):
        for x in range(200):
            px[x, y] = (255, 255, 255) if (x + y) % 2 == 0 else (0, 0, 0)
    im.save(p, format="PNG")
    ratio = estimate_bottom_strip_contrast(p)
    assert ratio > 4.0


def test_check_brand_passes_strong_contrast(tmp_path: Path) -> None:
    p = tmp_path / "contrast.png"
    im = Image.new("RGB", (200, 200), (128, 128, 128))
    px = im.load()
    for y in range(160, 200):
        for x in range(200):
            px[x, y] = (255, 255, 255) if x % 2 == 0 else (0, 0, 0)
    im.save(p, format="PNG")
    cfg = BrandConfig(logo_path=None, primary_color=None, min_contrast_ratio=1.2)
    repo = Path("/tmp")
    ok, issues = check_brand_image(p, cfg, repo_root=repo)
    assert ok, issues  # no logo, no color — only contrast, should be ok


def test_load_brand_config_no_crash() -> None:
    cfg = load_brand_config(get_repo_root() / "config" / "brand.yaml")
    assert cfg.min_contrast_ratio >= 1.0
    assert len(cfg.prohibited_words) > 0
