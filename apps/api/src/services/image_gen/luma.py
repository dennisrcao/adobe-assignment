import asyncio
import logging
import os

from lumaai import AsyncLumaAI

logger = logging.getLogger(__name__)


def _style_pack_urls() -> list[str]:
    raw = os.environ.get("LUMA_STYLE_REF_URLS", "")
    return [u.strip() for u in raw.split(",") if u.strip()]


def _style_ref_weight() -> float:
    try:
        return float(os.environ.get("LUMA_STYLE_REF_WEIGHT", "0.8"))
    except ValueError:
        return 0.8


PRODUCT_HERO_PREFIX = (
    "Professional advertising product photography, clean commercial lighting, "
    "high-end social ad creative, crisp focus. No text, no logos, no watermarks, "
    "no words or letters in the image. Single hero product visual. "
)

DEFAULT_MODEL = os.getenv("LUMA_MODEL", "photon-flash-1")
POLL_INTERVAL_S = 2.0
MAX_POLL_SECONDS = 180


async def _run_photon(
    *,
    prompt: str,
    aspect_ratio: str,
    model: str | None,
    image_refs: list[dict] | None = None,
) -> str:
    api_key = os.environ.get("LUMA_API_KEY")
    if not api_key:
        raise RuntimeError("LUMA_API_KEY is not set")

    kwargs: dict = {
        "model": model or DEFAULT_MODEL,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
    }

    pack = _style_pack_urls()
    if pack:
        if len(pack) > 1:
            logger.debug(
                "Luma allows only 1 style_ref; using first of %d URL(s), ignoring the rest",
                len(pack),
            )
        kwargs["style_ref"] = [{"url": pack[0], "weight": _style_ref_weight()}]

    if image_refs:
        kwargs["image_ref"] = image_refs

    async with AsyncLumaAI(auth_token=api_key) as client:
        generation = await client.generations.image.create(**kwargs)
        logger.info(
            "Luma generation %s queued (model=%s)", generation.id, kwargs["model"]
        )

        elapsed = 0.0
        while generation.state not in ("completed", "failed"):
            if elapsed >= MAX_POLL_SECONDS:
                raise TimeoutError(
                    f"Luma generation {generation.id} exceeded {MAX_POLL_SECONDS}s"
                )
            await asyncio.sleep(POLL_INTERVAL_S)
            elapsed += POLL_INTERVAL_S
            generation = await client.generations.get(id=generation.id)

        if generation.state == "failed":
            reason = getattr(generation, "failure_reason", None) or "unknown"
            raise RuntimeError(f"Luma generation {generation.id} failed: {reason}")

        if not generation.assets or not generation.assets.image:
            raise RuntimeError(
                f"Luma generation {generation.id} returned no image asset"
            )

        logger.info(
            "Luma generation %s completed in ~%.1fs",
            generation.id,
            elapsed,
        )
        return generation.assets.image


async def generate_product_hero(
    *,
    image_prompt: str,
    aspect_ratio: str = "1:1",
    model: str | None = None,
) -> str:
    """Generate a product hero image URL via Luma Photon (campaign ads, not storyboard sketch)."""
    full = PRODUCT_HERO_PREFIX + image_prompt
    return await _run_photon(
        prompt=full, aspect_ratio=aspect_ratio, model=model, image_refs=None
    )
