"""Optional on-image copy localization (Spanish) via Claude."""

import logging
import os

import anthropic
import httpx
from campaign_schema import CampaignBrief

logger = logging.getLogger(__name__)


async def overlay_message_for_brief(brief: CampaignBrief) -> tuple[str, bool]:
    """
    Return (text_for_overlay, did_translate).

    When ``overlay_locale`` is ``es``, translate the campaign message to Spanish;
    otherwise return the original message.
    """
    if not brief.overlay_locale:
        return brief.campaign_message, False
    loc = brief.overlay_locale.strip().lower()
    if loc in ("en", "english", "default"):
        return brief.campaign_message, False
    if loc not in ("es", "es-es", "es-mx", "spanish", "spa"):
        logger.info("Unknown overlay_locale %s, using English", brief.overlay_locale)
        return brief.campaign_message, False

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if not anthropic_key and not openrouter_key:
        raise RuntimeError(
            "Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY to enable Spanish overlay text"
        )

    user = f"""Translate the following advertising line into natural, short Spanish for on-image
social ad copy. Keep a similar length and tone. Output ONLY the translated line, no quotes
or explanation.

{brief.campaign_message}"""

    if anthropic_key:
        client = anthropic.AsyncAnthropic(api_key=anthropic_key)
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        msg = await client.messages.create(
            model=model,
            max_tokens=200,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in msg.content if block.type == "text")
    else:
        model = os.getenv("ANTHROPIC_MODEL", "anthropic/claude-sonnet-4.6")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {openrouter_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": user}],
                    "max_tokens": 200,
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]

    out = (text or "").strip()
    if not out:
        logger.warning("Empty translation, falling back to English")
        return brief.campaign_message, False
    return out, True
