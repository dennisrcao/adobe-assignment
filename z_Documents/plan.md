# Implementation Plan — Creative Automation Pipeline

## Overview

Build a locally-runnable web app that automates social ad creative generation from a campaign brief. Users submit a form (campaign name, products, region, audience, on-image message); the pipeline resolves one hero image per product (local file if present, else GenAI), composites it into three standard social ratios (1:1, 9:16, 16:9), burns the campaign message onto each output, runs brand + legal checks, and streams results live to the UI via Server-Sent Events.

**Approach:** Reuse the FastAPI + SSE + React + Luma plumbing already validated in the `storyboard-agent` project. Drop everything not required for this POC — Supabase auth, DSPy, deployment configs, database. Keep the patterns that work (async polling of Luma generations, SSE event queue, Vite dev proxy, Pillow image ops) and build the creative-automation logic on top.

**Shape of the solution:** Nx + pnpm monorepo with one Python app (`apps/api`, managed by `uv`), one React app (`apps/web`), and a shared Pydantic schema package (`packages/campaign-schema`). Both apps start with `pnpm dev` from the repo root.

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Clean async, built-in SSE, storyboard-agent precedent |
| LLM | Claude via OpenRouter (default) or Anthropic SDK | OpenRouter removes signup friction for reviewers; Anthropic SDK path preserved for direct use |
| Image generation | Luma Photon (`lumaai` SDK, `photon-flash-1`) | Already working code in storyboard-agent; Flash variant is ~6 s end-to-end |
| Image compositing | Pillow (PIL) | Local, instant, free — no headless browser, no second API call |
| Frontend | React + Vite + TypeScript, SCSS modules | Familiar; fast HMR; no framework runtime cost |
| Shared schemas | Pydantic v2 package (`packages/campaign-schema`) | Single source of truth for brief + brand config across Python callers |
| Monorepo | Nx + pnpm workspaces | One `pnpm dev` starts API and web; Nx caches lint/test targets |
| Python deps | `uv` | Deterministic locks, fast installs, venv per app |
| Config | `.env` (loaded by pydantic-settings / dotenv), `config/brand.yaml` | Keys and brand rules live outside code |

---

## Repository Structure

```
adobe-assignment/
├── package.json, nx.json, pnpm-workspace.yaml, tsconfig.base.json
├── pyproject.toml                         # Ruff config (repo-wide Python lint)
│
├── apps/
│   ├── api/
│   │   ├── pyproject.toml                 # API-scoped deps via uv
│   │   ├── project.json                   # Nx target: `nx serve api`
│   │   ├── .env.example
│   │   └── src/
│   │       ├── main.py                    # FastAPI app, CORS, routers, lifespan
│   │       ├── paths.py                   # get_repo_root()
│   │       ├── errors.py                  # APIError hierarchy + handlers
│   │       ├── dependencies.py
│   │       ├── routes/
│   │       │   ├── campaign.py            # POST /generate/campaign → SSE
│   │       │   └── health.py
│   │       └── services/
│   │           ├── brief_parser.py
│   │           ├── asset_resolver.py      # Check input_assets/<product_id>/hero.*
│   │           ├── prompt_gen.py          # Claude → Luma-optimized image prompt
│   │           ├── image_gen/luma.py      # Luma async polling + download
│   │           ├── hero_cache.py          # Hash(prompt + product_id) → cached PNG
│   │           ├── compositor.py          # Pillow: resize, cover-crop, overlay
│   │           ├── localization.py        # Claude → translate message (optional)
│   │           └── checks.py              # Brand contrast heuristic + legal word scan
│   │
│   └── web/
│       ├── package.json                   # @adobe-pipeline/web
│       ├── project.json                   # Nx target: `nx serve web`
│       ├── vite.config.ts                 # Dev proxy: /generate, /output-files, /health
│       └── src/
│           ├── main.tsx, App.tsx
│           ├── pages/Campaign/            # CampaignPage + form defaults + SSE consumer
│           ├── lib/campaignApi.ts
│           └── styles/ (_globals, _variables)
│
├── packages/
│   └── campaign-schema/                   # Pydantic: CampaignBrief, Product, BrandConfig
│
├── input_assets/<product_id>/hero.png     # Optional per-product local hero
├── output/<product_id>/{1x1,9x16,16x9}.png + report.json + report.md (gitignored)
├── cache/                                 # Luma hero cache (gitignored)
├── config/brand.yaml                      # Prohibited words, contrast floor, logo path
├── CLAUDE.md, README.md, ___Architecture.md
└── z_Documents/                           # This plan, PRD, source PDFs
```

---

## Pipeline Flow

### 1. Brief submission
Form POSTs JSON to `POST /generate/campaign`; API validates against `CampaignBrief` from `packages/campaign-schema`. Browser opens an `EventSource` on the same response (SSE).

### 2. Hero resolution (parallel per product via `asyncio.gather`)
```
For each product:
  IF input_assets/<product_id>/hero.{png,jpg,jpeg,webp} exists
    → use local image                                 (SSE: product_start, source="local")
  ELSE
    → hero_cache lookup on hash(prompt_context + product_id)
    → on miss: Claude synthesizes a Luma-optimized prompt from (product, region, audience, message)
              → Luma Photon Flash generation, async-poll until complete
              → download + persist to cache/<hash>.png
    → emit product_start with source="genai" and cached flag
```

### 3. Localization (optional)
If `overlay_locale == "es"`, Claude translates the campaign message to Spanish; otherwise the English message is used verbatim. Hero prompts always use the original English context.

### 4. Compositing — three ratios per product (sequential per product, parallel across products)
For each (product, ratio) in products × {1:1→1080²; 9:16→1080×1920; 16:9→1920×1080}:
1. Load hero (local or cached)
2. Cover-crop to target canvas
3. Draw semi-transparent bottom strip, overlay campaign message (Arial on macOS, DejaVu Sans on Linux, Pillow default as final fallback) sized to image width
4. Save to `output/<product_id>/<ratio>.png`
5. Emit SSE `creative { product_id, ratio, file_path, image_url }` so the UI slot fills live

### 5. Brand + legal checks
Run **after** compositing, on the final PNGs:
- **Contrast:** heuristic WCAG-AA-style signal on the bottom 20% strip (overlay region) vs. the text color. Emits per-creative `check_result`.
- **Prohibited words:** scan overlay copy (localized if applicable) against `config/brand.yaml → prohibited_terms`. Emits a single `legal_check`.
- **Logo presence:** if `brand.logo_path` is set, confirm the file exists on disk (path check only — not image-recognition).

Flags are surfaced but do **not** block file output ("signal, don't stop the world").

### 6. Report artifact
After all creatives finish, write:
- `output/report.json` — run id, elapsed ms, per-product source + prompt + cache hit, per-creative check results
- `output/report.md` — the same info as a human-readable summary

### 7. Completion
Emit SSE `complete` with elapsed time, genai call count, cache hits, localization flag, report paths. Grid shows all 6 creatives; user can open the report.

---

## Key Design Decisions

1. **Hero-first, ratio-second.** Generate or load one hero per product, composite to all three ratios locally with Pillow. N GenAI calls for N products, not N × 3. Cuts cost and wall time.

2. **Claude for image prompts, not raw product names.** Luma gets a prompt informed by campaign context (audience, region, message tone), which produces markedly better images and is auditable in the report.

3. **Pillow for text overlay.** Instant, free, pixel-level control. A second "text rendering" API call would add latency and cost for no quality gain; headless-browser rendering is fragile.

4. **SSE streaming.** 10–30 s per Luma generation is too long for a polling/loading-spinner UX. Streaming is a live progress UI — each creative slots into the grid as it finishes.

5. **Async parallel heroes.** All product hero resolutions run via `asyncio.gather`. For 2 products × 20 s each, wall time ≈ 20 s, not 40 s.

6. **Hero cache keyed on prompt context.** Reruns with the same brief reuse cached Luma output — demonstrable "cost-aware engineering" moment in the demo. Local `input_assets/` heroes are not cached (no point; already on disk).

7. **OpenRouter as the default Claude provider.** Reviewers can test with a single API key; `ANTHROPIC_API_KEY` takes precedence if set for direct Anthropic access.

8. **Brand rules as YAML config, not code.** `config/brand.yaml` is editable by a brand team without touching Python.

9. **Checks signal, don't block.** Contrast and prohibited-word flags surface in SSE and `report.json`; the pipeline still writes output. Interview-friendly: shows compliance thinking without producing an unusable demo if a flag trips.

10. **Nx monorepo + `pnpm dev`.** One command starts both servers; a new machine setup is `pnpm install` → `uv sync` → `pnpm dev`. No bespoke "run scripts."

---

## Patterns Reused From `storyboard-agent`

| Source | Pattern | Destination |
|---|---|---|
| `apps/api/src/services/image_gen/luma.py` | Luma async polling + download with timeout protection | `apps/api/src/services/image_gen/luma.py` — reshaped as `generate_hero()` |
| `apps/api/src/main.py` | CORS, lifespan, exception handlers, router mounting | `apps/api/src/main.py` |
| `apps/api/src/routes/*.py` | APIRouter per feature, SSE event queue pattern, `asyncio.gather` | `apps/api/src/routes/campaign.py` |
| `apps/api/src/errors.py` | `APIError` hierarchy + FastAPI handlers | `apps/api/src/errors.py` |
| `apps/web/src/lib/*` | Vite dev proxy config + SSE consumer via `EventSource` | `apps/web/vite.config.ts` + `apps/web/src/lib/campaignApi.ts` |
| `.env.example` | Documented keys pattern | `apps/api/.env.example` |
| Ruff config (E, W, F, I, N, B, A, C4, UP, SIM, RUF; line length 88) | Repo-wide Python lint | root `pyproject.toml` |

**Explicitly not reused:** DSPy, Supabase auth / database / row-level security, deployment (Vercel/Fly), storyboard-specific Pydantic models, agents framework.

---

## SSE Event Types

```ts
type SSEEvent =
  | { type: "overview"; total_products: number; total_creatives: number; localized_message?: string }
  | { type: "product_start"; product_id: string; product_name: string; source: "local" | "genai"; cache_hit?: boolean }
  | { type: "creative"; product_id: string; ratio: "1x1" | "9x16" | "16x9"; file_path: string; image_url: string }
  | { type: "check_result"; product_id: string; ratio: string; contrast_ok: boolean; flags: string[] }
  | { type: "legal_check"; overlay_text: string; flagged_terms: string[] }
  | { type: "complete";
      elapsed_ms: number;
      genai_calls: number;
      cache_hits: number;
      report_path: string;
      localization_applied: boolean;
    }
  | { type: "error"; product_id?: string; message: string };
```

---

## Features: required, nice-to-have, above-and-beyond

### Required (brief minimum)
- Campaign brief input (form or YAML/JSON), ≥ 2 products, region, audience, message
- Local asset reuse when `input_assets/<id>/hero.*` is present
- GenAI hero generation when it isn't
- Output at three aspect ratios (1:1, 9:16, 16:9)
- Campaign message visible on every output
- Runs locally, one command
- Output organized by product + ratio
- Comprehensive README

### Nice-to-have (brief bonus)
- Brand compliance checks (contrast heuristic; optional logo path)
- Legal content checks (prohibited-word scan)
- Structured run report (`report.json` + `report.md`)

### Above-and-beyond (demo leverage)
- React UI with live SSE progress — much stronger demo than a CLI
- Hero cache with prompt-based key — demonstrates cost-aware thinking
- Brand config as YAML — brand team can self-serve
- Optional Spanish localization of on-image text — hits the brief's multi-language "plus"
- Nx + pnpm monorepo + repo-wide Ruff — shows production hygiene without overengineering

---

## Limitations to Mention Proactively

- **Text rendering is basic.** Bottom-strip overlay with a system font works for the POC. Real campaigns use templated design systems or Adobe Express for pixel-perfect brand compliance.
- **Brand color consistency** isn't guaranteed by Luma alone. Production would layer brand-conditioned models or post-gen color correction.
- **Local folder stands in for a DAM.** Brief mentions Azure/AWS/Dropbox; swapping the asset resolver to an S3/GCS backend is a one-file change.
- **No approval workflow.** Pipeline drafts; production routes through stakeholder review.
- **Localization is message-only.** True localization includes culturally-adapted imagery, which the POC doesn't attempt.
- **Luma rate limits** are not handled beyond parallel `gather`. A production version would add staggering or a semaphore.

---

## Pre-Build Decisions

1. **Image API** — Luma Photon (`photon-flash-1`), proven in storyboard-agent. No fallback provider wired in for the POC; document the decision.
2. **Text render** — Pillow only. HTML-to-image and SVG-to-PNG rejected (headless-browser overhead; less pixel control).
3. **Caching** — Filesystem cache under `cache/` keyed on `hash(prompt_context + product_id)`. Ratio is not in the key; one hero serves all three ratios.
4. **Brand pack** — Single `config/brand.yaml` at repo root. Contrast floor + prohibited terms + optional logo path. Pipeline runs without it, but it ships with sensible defaults.
5. **Localization** — Spanish only for the POC. Font handling uses the platform's installed Arial / DejaVu Sans (Latin-script-safe). Avoid RTL/CJK to sidestep font-bundling and layout complexity.
6. **Default Claude provider** — OpenRouter. Single env var (`OPENROUTER_API_KEY`) is lower-friction for reviewers than requesting a direct Anthropic key. `ANTHROPIC_API_KEY` takes precedence when set.
7. **Monorepo** — Nx + pnpm for JS; `uv` per Python app. One root-level `pnpm dev` runs both.

---

## Timeline Estimate

| Phase | Time |
|---|---|
| Monorepo scaffold + Nx + pnpm + uv + `.env.example` | ~45 min |
| Shared schema package (`packages/campaign-schema`) | ~30 min |
| API services (asset resolver, prompt gen, Luma, compositor, checks, localization, cache) | ~2 hr |
| SSE route + report writer | ~45 min |
| React Campaign page + SSE consumer + results grid | ~1.5 hr |
| Brand YAML + defaults + two example products (one local hero, one GenAI) | ~20 min |
| Tests (brief parser, compositor math, asset resolver, checks) | ~30 min |
| README + architecture doc + demo video | ~1 hr |

**Total: ~6–7 hours.** Above the brief's nominal "2–3 hours" estimate, but the brief explicitly asks for a comprehensive README and demo, and rewards thoughtful design. The extra time buys the web UI, SSE progress, cache, and report — all of which make the 30-minute interview walkthrough much stronger.

---

## Success Criteria

The POC is done when:
1. A reviewer can clone the repo, run `pnpm install && pnpm dev`, open `http://localhost:3000/campaign`, submit the default brief, and watch six PNGs stream into the grid.
2. `output/` contains a well-organized directory per product with three ratios + `report.json` + `report.md`.
3. README covers setup, example brief, architecture diagram, design decisions, and limitations.
4. Every design decision has a defensible "why" tied to the brief (cost, speed, quality, UX, brand compliance, or reproducibility).
5. A 2–3 minute demo video shows form fill → generate → creatives stream → report — end to end.
