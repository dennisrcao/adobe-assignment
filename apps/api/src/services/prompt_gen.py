"""Claude → short Luma-friendly image prompt for a product hero."""

import logging
import os

import anthropic
import httpx
from campaign_schema import CampaignBrief, Product

logger = logging.getLogger(__name__)


async def product_hero_prompt(*, brief: CampaignBrief, product: Product) -> str:
    """Generate Luma-friendly image prompt via Claude (Anthropic or OpenRouter)."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    if not anthropic_key and not openrouter_key:
        raise RuntimeError(
            "Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY to enable GenAI hero images"
        )

    user = f"""Campaign context:
- Product: {product.name} (id: {product.id})
- Region: {brief.target_region}
- Audience: {brief.target_audience}
- Campaign message (do not render as text in the image): {brief.campaign_message}

Write ONE concise image generation prompt (2-4 short sentences) for a photorealistic hero product visual
for social advertising. Describe setting, lighting, and mood only. No quoted ad copy, no on-image text."""

    if anthropic_key:
        # Direct Anthropic API
        client = anthropic.AsyncAnthropic(api_key=anthropic_key)
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        msg = await client.messages.create(
            model=model,
            max_tokens=300,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in msg.content if block.type == "text")
    else:
        # OpenRouter: OpenAI-compatible /chat/completions endpoint
        model = os.getenv("ANTHROPIC_MODEL", "anthropic/claude-sonnet-4.6")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {openrouter_key}"},
                json={
                    "model": model,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]

    out = text.strip()
    if not out:
        raise RuntimeError("Claude returned an empty image prompt")
    logger.debug("Hero prompt for %s: %s", product.id, out[:200])
    return out
