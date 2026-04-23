"""Pillow: resize/crop to ratio canvases, overlay campaign message."""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# width x height
RATIO_SIZES: dict[str, tuple[int, int]] = {
    "1x1": (1080, 1080),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
}

RATIO_ORDER = ("1x1", "9x16", "16x9")


def _load_image(path: Path) -> Image.Image:
    with Image.open(path) as im:
        return im.convert("RGBA")


def _cover_resize(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    iw, ih = im.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return im.crop((left, top, left + tw, top + th))


def _default_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", size=size
        )
    except OSError:
        try:
            return ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=size
            )
        except OSError:
            return ImageFont.load_default(size=size)


def _wrap_text(
    text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw
) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for w in words[1:]:
        trial = f"{current} {w}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return lines


def _overlay_message(im: Image.Image, message: str) -> Image.Image:
    w, h = im.size
    draw = ImageDraw.Draw(im, "RGBA")
    # responsive font size
    size = max(18, min(48, w // 28))
    font = _default_font(size)
    max_text_w = int(w * 0.9)
    lines = _wrap_text(message, font, max_text_w, draw)
    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines] or [
        size
    ]
    total_h = sum(line_heights) + (len(lines) - 1) * 6
    pad = 20
    bar_h = total_h + pad * 2
    y0 = h - bar_h
    # semi-transparent bar
    overlay = Image.new("RGBA", (w, bar_h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rectangle((0, 0, w, bar_h), fill=(0, 0, 0, 200))
    im.paste(overlay, (0, y0), overlay)

    y = y0 + pad
    for i, line in enumerate(lines):
        lw = draw.textlength(line, font=font)
        x = (w - lw) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_heights[i] + 6
    return im


def render_creative(
    *,
    hero_source: Path,
    message: str,
    ratio_key: str,
    out_path: Path,
) -> None:
    if ratio_key not in RATIO_SIZES:
        raise ValueError(f"Unknown ratio: {ratio_key}")
    size = RATIO_SIZES[ratio_key]

    im = _load_image(hero_source)
    im = _cover_resize(im, size)
    im = _overlay_message(im, message)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out_path, format="PNG", optimize=True)
    logger.info("Wrote %s", out_path)
