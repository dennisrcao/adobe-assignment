# Adobe Creative Automation Pipeline: System Architecture

*Aligned with the current `apps/api/` + `apps/web/` monorepo (Nx + pnpm workspaces) and `packages/campaign-schema/`.*

## 1. Repository layout & how to run it

| Location | Role |
|----------|------|
| **Repo root** | `package.json`, `nx.json`, `pnpm-workspace.yaml`; **`pnpm install`** wires Node deps. **`pyproject.toml`** here holds **Ruff** only (lint/format for `apps/**` and `packages/**`). |
| **`apps/api/`** | FastAPI app; **`uv`** creates **`apps/api/.env`**; run API with **`cd apps/api && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload`**. `src/paths.get_repo_root()` points at the monorepo root (for `output/`, `config/`, `input_assets/`, `cache/`). |
| **`apps/web/`** | Vite + React package **`@adobe-pipeline/web`**, port **3000**; dev server proxies `/generate`, `/output-files`, `/health` to the API. |
| **`packages/campaign-schema/`** | Editable Python package: Pydantic **`CampaignBrief` / `Product`**, **`BrandConfig`**, **`load_brand_config(brand_path)`**, **`check_prohibited_words`**. Consumed by `apps/api` via `uv`’s local path dep (no import cycle). |

**Fresh machine (condensed):** `pnpm install` (root) → `cd apps/api && cp .env.example .env` → edit keys → `uv sync --all-groups` → return to root → **`pnpm dev`** (starts both API and web via Nx; uses `NX_DAEMON=false` in the script). Alternatively **`pnpm run dev:web`** and **`pnpm run dev:api`** in two terminals. Full steps: **[README.md](README.md)**.

**Optional — shared logs across terminals:** [`.claude/commands/ADOBE-Start.md`](.claude/commands/ADOBE-Start.md) documents a **tmux** session `adobe-assignment` (windows `web` / `api`); not required for a single local session.

## 2. High-Level End-to-End Flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React / Vite)                          │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ apps/web/src/pages/Campaign/CampaignPage.tsx                      │      │
│  │  • Campaign brief: name, 2+ products (id + name), region, audience│      │
│  │  • Campaign message, optional on-image language (e.g. Spanish)   │      │
│  │  • Submit → fetch() POST /generate/campaign (JSON body)         │      │
│  │  • Progress: N / total from `creative` events (0/N during heroes)│      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                  ↓                                          │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ apps/web/src/lib/campaignApi.ts — parseSseResponse()            │      │
│  │  • Reads fetch Response body stream; splits SSE `data: {...}`   │      │
│  │  • Not browser EventSource (custom POST + stream parse)         │      │
│  │  • Updates grid on `creative`; shows legal/hero/check rows      │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────────────────┘
                                  ↓
                    POST /generate/campaign  (Vite dev proxy → :8000)
                    text/event-stream
                                  ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI / Python)                          │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ apps/api/src/routes/campaign.py — POST /generate/campaign         │      │
│  │  • FastAPI validates body → Pydantic CampaignBrief (campaign_schema) │   │
│  │  • StreamingResponse(_stream_campaign) → SSE queue               │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                  ↓                                          │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ _run_campaign() (same file)                                     │      │
│  │                                                                   │      │
│  │  0️⃣  CONFIG + OVERLAY + LEGAL (before heroes)                    │      │
│  │     ├─ load_brand_config(repo/config/brand.yaml) ← YAML or defaults │   │
│  │     ├─ overlay_message_for_brief() — optional Spanish overlay   │      │
│  │     │     (Claude; needs ANTHROPIC or OPENROUTER if locale=es)   │      │
│  │     ├─ check_prohibited_words(overlay_text, list) — regex / list  │      │
│  │     └─ SSE: overview, legal_check                               │      │
│  │                                                                   │      │
│  │  1️⃣  HERO RESOLUTION (per product, parallel)                     │      │
│  │     asyncio.gather(_resolve_hero for each product)              │      │
│  │     Per product:                                                │      │
│  │     ├─ find_hero_path() → input_assets/<id>/hero.{png,jpg,...}  │      │
│  │     │  └─ If exists: local Path, SSE product_start (local)      │      │
│  │     └─ If missing:                                              │      │
│  │        ├─ product_hero_prompt() — Claude → Luma prompt          │      │
│  │        ├─ hero_cache get/save — hash(product_id + prompt)       │      │
│  │        ├─ generate_product_hero() — Luma Photon → URL         │      │
│  │        └─ downloaded Path under cache/                          │      │
│  │     (Always ends with a local Path; compositor never takes URL) │      │
│  │                                                                   │      │
│  │  2️⃣  COMPOSITING (per product × 3 ratios, sequential loop)         │      │
│  │     run_in_threadpool(render_creative, …) — blocking Pillow     │      │
│  │     For each (product, ratio) in order:                        │      │
│  │       ├─ compositor: cover crop + bottom-bar overlay text,      │      │
│  │       │  save output/<id>/{1x1,9x16,16x9}.png                 │      │
│  │       ├─ SSE: creative (image_url, …)                        │      │
│  │       ├─ run_in_threadpool(check_brand_image) — contrast, etc. │      │
│  │       └─ SSE: check_result (legal + brand fields)             │      │
│  │                                                                   │      │
│  │  3️⃣  REPORTING                                                  │      │
│  │     └─ report.json + report.md (includes checks, overlay_text)  │      │
│  │     └─ SSE: complete (legal_ok, all_checks_pass, …)            │      │
│  │                                                                   │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
                                  ↓
         ┌──────────────────────────────────────────────────────────┐
         │              EXTERNAL APIs                                 │
         │  ┌────────────────────────────────────────────────────┐  │
         │  │ Anthropic Claude (primary if ANTHROPIC_API_KEY)   │  │
         │  │  • Hero image prompt (prompt_gen)                  │  │
         │  │  • Optional: Spanish overlay (localization)        │  │
         │  └────────────────────────────────────────────────────┘  │
         │  ┌────────────────────────────────────────────────────┐  │
         │  │ OpenRouter (if no Anthropic key)                    │  │
         │  │  • OpenAI-compatible chat for same prompts         │  │
         │  └────────────────────────────────────────────────────┘  │
         │  ┌────────────────────────────────────────────────────┐  │
         │  │ Luma Photon (LUMA_API_KEY)                         │  │
         │  │  • Hero 1:1 image when no local file + cache miss   │  │
         │  └────────────────────────────────────────────────────┘  │
         └──────────────────────────────────────────────────────────┘
                                  ↓
         ┌──────────────────────────────────────────────────────────┐
         │              FILE STORAGE (local repo)                    │
         │  input_assets/<product_id>/hero.*  — optional per product │
         │  cache/<hash>.png                 — Luma hero cache        │
         │  output/<product_id>/*.png, report.json, report.md       │
         │  config/brand.yaml                — prohibited words, etc.│
         └──────────────────────────────────────────────────────────┘
```

---

## 3. Hero Cache Strategy

### Cache key

- [`apps/api/src/services/hero_cache.py`](apps/api/src/services/hero_cache.py) keys cache files by a hash of **product_id + image prompt** (see implementation for exact formula).

### Lifecycle

1. If local `input_assets/<id>/hero.*` exists → use it (no Luma, no cache entry for “hero gen”).
2. Else compute prompt via Claude; if `cache/<hash>.png` exists → cache hit, skip Luma.
3. Else Luma → download → write `cache/<hash>.png` → use for all three ratios.

---

## 4. Service Layer (actual modules)

| Module | Role |
|--------|------|
| [`packages/campaign-schema/campaign_schema/brief.py`](packages/campaign-schema/campaign_schema/brief.py) | Pydantic `CampaignBrief`, `Product` |
| [`packages/campaign-schema/campaign_schema/brand.py`](packages/campaign-schema/campaign_schema/brand.py) | `BrandConfig`, `load_brand_config(path)`, `check_prohibited_words` |
| [`apps/api/src/routes/campaign.py`](apps/api/src/routes/campaign.py) | SSE campaign orchestration |
| [`apps/api/src/services/asset_resolver.py`](apps/api/src/services/asset_resolver.py) | `find_hero_path(product_id)` |
| [`apps/api/src/services/prompt_gen.py`](apps/api/src/services/prompt_gen.py) | Claude / OpenRouter → Luma-friendly hero prompt |
| [`apps/api/src/services/hero_cache.py`](apps/api/src/services/hero_cache.py) | Get/save cached hero PNGs |
| [`apps/api/src/services/image_gen/luma.py`](apps/api/src/services/image_gen/luma.py) | Luma Photon → URL, polling |
| [`apps/api/src/services/compositor.py`](apps/api/src/services/compositor.py) | Sync Pillow: crop, **overlay_text** on image, save PNG |
| [`apps/api/src/services/checks.py`](apps/api/src/services/checks.py) | `check_brand_image` — bottom-strip contrast, optional logo / primary color (Pillow) |
| [`apps/api/src/services/localization.py`](apps/api/src/services/localization.py) | Optional Spanish overlay string via Claude |
| [`apps/api/src/services/brief_parser.py`](apps/api/src/services/brief_parser.py) | Helpers: YAML/JSON string → `CampaignBrief` (not used by the live POST route; FastAPI validates JSON directly) |

Routers: [`health.py`](apps/api/src/routes/health.py), [`auth.py`](apps/api/src/routes/auth.py) (stubs/health as wired in [`main.py`](apps/api/src/main.py)). Static: `GET /output-files/...` mounts repo `output/`.

---

## 5. Request / Response Flow (summary)

```
Client POST JSON  →  CampaignBrief validation
  →  brand.yaml + overlay + legal
  →  SSE: overview, legal_check
  →  parallel hero resolution  →  product_start (per product)
  →  for each product × ratio: threadpool render → creative → check_brand → check_result
  →  write report files
  →  SSE: complete
```

---

## 6. SSE Event Contract (current)

| `type` | When |
|--------|------|
| `overview` | Start: `run_id`, `product_count`, `total_creatives` |
| `legal_check` | After prohibited-word scan: `ok`, `hit_terms` |
| `product_start` | Per product: `product_id`, `source` = `local` \| `genai` |
| `creative` | Each finished PNG: `product_id`, `ratio`, `file_path`, `image_url` |
| `check_result` | After each file: `legal_ok`, `legal_hit_terms`, `brand_ok`, `brand_issues` |
| `complete` | `elapsed_ms`, `genai_calls`, `cache_hits`, `localization_applied`, `legal_ok`, `all_checks_pass`, `report_path`, `report_md_path` |
| `error` | Exception message string |

---

## 7. Report Artifacts

### `output/report.json` (shape)

- `run_id`, `timestamp`, `elapsed_ms`
- `brief` — `CampaignBrief.model_dump()`
- `overlay_text` — string actually rendered (English or translated)
- `summary` — `total_creatives_generated`, `genai_hero_generations`, `cache_hits`
- `checks` — `legal_ok`, `legal_hit_terms`, `localization_applied`, `all_brand_ok`, `all_checks_pass`, `per_creative` (list with legal + brand per file)

### `output/report.md`

- Human-readable lines including legal, brand rollup, localization.

---

## 8. Compositor (Pillow)

[`apps/api/src/services/compositor.py`](apps/api/src/services/compositor.py)

- `render_creative(...)` is **synchronous**; the route uses **`run_in_threadpool`** to avoid blocking the event loop.
- `hero_source` is a local **`Path`** (cached or `input_assets`).
- Pixel sizes:

| key | size (W×H) |
|-----|------------|
| `1x1` | 1080×1080 |
| `9x16` | 1080×1920 |
| `16x9` | 1920×1080 |

---

## 9. Compliance & config

- **[`config/brand.yaml`](config/brand.yaml)** — `prohibited_words`, `min_contrast_ratio`, optional `logo_path` / `primary_color`.
- **Legal** — list + regex (whole-word / phrase), not an LLM judgment.
- **Brand** — heuristic contrast in bottom image strip; optional file existence / color coverage.

---

## 10. API keys & env

- **Anthropic** `ANTHROPIC_API_KEY` — preferred for Claude (hero prompt + optional Spanish overlay).
- **OpenRouter** `OPENROUTER_API_KEY` — alternative if Anthropic is unset.
- **Luma** `LUMA_API_KEY` — when a hero must be generated.
- **`LUMA_MODEL`**, **`ANTHROPIC_MODEL`**, **`LOG_LEVEL`**, **`CORS_ORIGINS`** — see `apps/api/.env.example` and README.

---

## 11. Error handling

- Global FastAPI handlers in [`apps/api/src/main.py`](apps/api/src/main.py) return JSON for typical HTTP errors.
- The campaign stream catches failures in `_run_campaign`, logs, and emits **`{ "type": "error", "message": "..." }`** over SSE; the client shows the message.

---

## 12. Concurrency

- **Hero resolution:** `asyncio.gather` across products (parallel Luma/Claude per product). Rate limits may require tuning in production.
- **Compositing + `check_brand_image`:** `run_in_threadpool` (Pillow and image reads are sync).

---

## 13. Tests

- [`apps/api/tests/test_checks.py`](apps/api/tests/test_checks.py) — prohibited words, contrast helper, `load_brand_config` smoke.
- [`apps/api/tests/test_asgi.py`](apps/api/tests/test_asgi.py) — `httpx` + `ASGITransport` smoke for `/health`.
- Run: `cd apps/api && uv sync --all-groups && uv run pytest` (see [`apps/api/pyproject.toml`](apps/api/pyproject.toml) `pytest` config).

---

## 14. Runtime notes (anyio / threadpool)

- [`apps/api/src/main.py`](apps/api/src/main.py) preloads **`anyio._backends._asyncio`** at import so Starlette’s **`run_in_threadpool`** (Pillow + `check_brand_image`) uses a consistent asyncio backend. The API should always be run as **`cd apps/api && uv run …`** from the venv that **`uv sync`** created.

---

## 15. Intentionally out of scope / future

- In-browser per-product file upload (today: disk paths `input_assets/<id>/` only).
- Cloud deployment, auth/database for this pipeline (placeholders may exist under `auth`).
- Stamping a brand logo **onto** the PNG (optional checks are file / color heuristics only).
- Broader localization beyond the Spanish overlay path.

These items are product/ops choices, not required by the take-home’s local POC.
