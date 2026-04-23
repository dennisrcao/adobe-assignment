import asyncio
import contextlib
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from campaign_schema import (
    BrandConfig,
    CampaignBrief,
    Product,
    check_prohibited_words,
    load_brand_config,
)
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from ..paths import get_repo_root
from ..services.asset_resolver import find_hero_path
from ..services.checks import check_brand_image
from ..services.compositor import RATIO_ORDER, render_creative
from ..services.hero_cache import get_cached, save_to_cache
from ..services.image_gen.luma import generate_product_hero
from ..services.localization import overlay_message_for_brief
from ..services.prompt_gen import product_hero_prompt

logger = logging.getLogger(__name__)

router = APIRouter()


async def _emit(queue: asyncio.Queue[str | None], payload: dict[str, Any]) -> None:
    await queue.put(f"data: {json.dumps(payload)}\n\n")


async def _resolve_hero(
    p: Product,
    brief: CampaignBrief,
    queue: asyncio.Queue[str | None],
) -> tuple[str, Any, int, int]:
    """Resolve hero for one product. Returns (product_id, hero, genai_count, cache_count)."""
    local = find_hero_path(p.id)
    if local is not None:
        await _emit(
            queue, {"type": "product_start", "product_id": p.id, "source": "local"}
        )
        return p.id, local, 0, 0

    await _emit(queue, {"type": "product_start", "product_id": p.id, "source": "genai"})
    prompt = await product_hero_prompt(brief=brief, product=p)
    cached = get_cached(p.id, prompt)
    if cached:
        return p.id, cached, 0, 1

    url = await generate_product_hero(image_prompt=prompt, aspect_ratio="1:1")
    path = await save_to_cache(p.id, prompt, url)
    return p.id, path, 1, 0


async def _run_campaign(
    brief: CampaignBrief,
    public_base: str,
    queue: asyncio.Queue[str | None],
) -> None:
    repo = get_repo_root()
    output_root = repo / "output"
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    started = time.perf_counter()
    n = len(brief.products)
    total_creatives = n * len(RATIO_ORDER)

    try:
        brand: BrandConfig = load_brand_config(
            get_repo_root() / "config" / "brand.yaml"
        )
        overlay_text, localization_applied = await overlay_message_for_brief(brief)
        legal_ok, legal_hits = check_prohibited_words(
            overlay_text, brand.prohibited_words
        )

        await _emit(
            queue,
            {
                "type": "overview",
                "run_id": run_id,
                "product_count": n,
                "total_creatives": total_creatives,
            },
        )
        await _emit(
            queue,
            {
                "type": "legal_check",
                "ok": legal_ok,
                "hit_terms": legal_hits,
            },
        )

        # Resolve all heroes in parallel — Luma calls for different products run concurrently
        results = await asyncio.gather(
            *[_resolve_hero(p, brief, queue) for p in brief.products]
        )
        hero_by_id: dict[str, Any] = {}
        genai_heroes = 0
        cache_hits = 0
        for product_id, hero, genai, hits in results:
            hero_by_id[product_id] = hero
            genai_heroes += genai
            cache_hits += hits

        per_check: list[dict[str, Any]] = []
        all_brand_ok = True

        for p in brief.products:
            src = hero_by_id[p.id]
            for ratio in RATIO_ORDER:
                out_path = output_root / p.id / f"{ratio}.png"
                await run_in_threadpool(
                    render_creative,
                    hero_source=src,
                    message=overlay_text,
                    ratio_key=ratio,
                    out_path=out_path,
                )
                rel = f"{p.id}/{ratio}.png"
                image_url = f"{public_base}/output-files/{rel}"
                await _emit(
                    queue,
                    {
                        "type": "creative",
                        "product_id": p.id,
                        "ratio": ratio,
                        "file_path": str(out_path.relative_to(repo)),
                        "image_url": image_url,
                    },
                )
                b_ok, b_notes = await run_in_threadpool(
                    check_brand_image, out_path, brand, repo_root=repo
                )
                if not b_ok:
                    all_brand_ok = False
                row: dict[str, Any] = {
                    "product_id": p.id,
                    "ratio": ratio,
                    "legal_ok": legal_ok,
                    "legal_hit_terms": legal_hits,
                    "brand_ok": b_ok,
                    "brand_issues": b_notes,
                }
                per_check.append(row)
                await _emit(
                    queue,
                    {
                        "type": "check_result",
                        "product_id": p.id,
                        "ratio": ratio,
                        "legal_ok": legal_ok,
                        "legal_hit_terms": legal_hits,
                        "brand_ok": b_ok,
                        "brand_issues": b_notes,
                    },
                )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        all_checks_pass = legal_ok and all_brand_ok
        report: dict[str, Any] = {
            "run_id": run_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_ms": elapsed_ms,
            "brief": brief.model_dump(),
            "overlay_text": overlay_text,
            "summary": {
                "total_creatives_generated": total_creatives,
                "genai_hero_generations": genai_heroes,
                "cache_hits": cache_hits,
            },
            "checks": {
                "legal_ok": legal_ok,
                "legal_hit_terms": legal_hits,
                "localization_applied": localization_applied,
                "all_brand_ok": all_brand_ok,
                "all_checks_pass": all_checks_pass,
                "per_creative": per_check,
            },
        }
        report_path = output_root / "report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report_md = output_root / "report.md"
        report_md.write_text(
            f"# Campaign run\n\n- **Run ID:** {run_id}\n- **Elapsed:** {elapsed_ms} ms\n"
            f"- **Creatives:** {total_creatives}\n- **GenAI hero generations:** {genai_heroes}\n"
            f"- **Legal copy OK:** {legal_ok} ({legal_hits!r})\n"
            f"- **Brand checks (all creatives):** {all_brand_ok}\n"
            f"- **All checks pass:** {all_checks_pass}\n"
            f"- **Localization applied:** {localization_applied}\n",
            encoding="utf-8",
        )

        await _emit(
            queue,
            {
                "type": "complete",
                "elapsed_ms": elapsed_ms,
                "genai_calls": genai_heroes,
                "cache_hits": cache_hits,
                "estimated_cost_usd": None,
                "output_dir": str(output_root),
                "localization_applied": localization_applied,
                "legal_ok": legal_ok,
                "all_checks_pass": all_checks_pass,
                "report_path": str(report_path.relative_to(repo)),
                "report_md_path": str(report_md.relative_to(repo)),
            },
        )
    except Exception as exc:
        logger.error("Campaign generation failed: %s", exc, exc_info=True)
        await _emit(queue, {"type": "error", "message": str(exc)})
    finally:
        await queue.put(None)


async def _stream_campaign(
    brief: CampaignBrief, public_base: str
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    task = asyncio.create_task(_run_campaign(brief, public_base, queue))
    try:
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk
    finally:
        if not task.done():
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@router.post("/campaign")
async def generate_campaign(
    brief: CampaignBrief,
    request: Request,
) -> StreamingResponse:
    public_base = str(request.base_url).rstrip("/")
    return StreamingResponse(
        _stream_campaign(brief, public_base),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
