# Claude Code: Adobe FDE Take-Home Project

## Overview

**Adobe Forward Deployed AI Engineer take-home assignment:** Build a creative automation pipeline that takes a campaign brief (JSON/YAML) + optional product images, generates social ad creatives at 3 aspect ratios per product using GenAI, and outputs organized PNG files with campaign message text overlay.

**Deliverables:** Public GitHub repo + 2-3 min demo video + comprehensive README.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend** | Python + FastAPI | REST API with SSE for streaming progress |
| **Frontend** | React + Vite + TypeScript | Web UI: form input, image upload, live results grid |
| **LLM** | Anthropic SDK (Claude) | Generate image prompts from campaign context |
| **Image Gen** | Luma Photon (lumaai SDK) | Generate hero images for missing assets |
| **Image Ops** | Pillow (PIL) | Resize/crop to aspect ratios, text overlay |
| **Data** | Pydantic + YAML/JSON | Campaign brief schema, type validation |
| **Package Mgmt** | uv (Python) + pnpm (JS) | Fast, deterministic dependency management |
| **Env** | .env + python-dotenv | API keys: LUMA_API_KEY, ANTHROPIC_API_KEY |

---

## Architecture

```
User form (React)
    ↓
POST /generate/campaign (FastAPI)
    ↓
[Hero resolution] ← Asset resolver checks input_assets/
                 ← If missing, Claude → Luma → hero image
    ↓
[Async parallel per product] ← asyncio.gather
    ├─ Localization (Claude translate if non-English region)
    ├─ Compositing × 3 ratios (Pillow: resize, crop, overlay text)
    ├─ Brand checks (contrast, logo overlay, prohibited words)
    └─ Cache management (hash → cached PNG on reruns)
    ↓
SSE events stream back to React
    ├─ overview (total products, creatives)
    ├─ product_start (source: local or genai)
    ├─ creative (one per product × ratio)
    ├─ check_result (brand OK, legal OK)
    └─ complete (metrics: time, cost, cache hits)
    ↓
output/ folder
    ├─ <product_id>/
    │   ├─ 1x1.png
    │   ├─ 9x16.png
    │   ├─ 16x9.png
    ├─ report.json (metrics artifact)
    └─ report.md (human-readable summary)
```

---

## Repository Structure

```
adobe-assignment/
├── package.json, nx.json, pnpm-workspace.yaml   # Nx + pnpm at repo root; `pnpm dev` runs both apps
├── pyproject.toml                    # Ruff (lint/format for Python under apps/ + packages/)
│
├── apps/
│   ├── api/                          # Python FastAPI backend (uv-managed)
│   │   ├── src/
│   │   │   ├── main.py               # App entry, CORS, routers
│   │   │   ├── paths.py              # get_repo_root() → repo root
│   │   │   ├── routes/
│   │   │   │   ├── campaign.py      # POST /generate/campaign → SSE
│   │   │   │   └── health.py         # GET /health
│   │   │   └── services/
│   │   │       ├── brief_parser.py  # YAML/JSON → CampaignBrief
│   │   │       ├── asset_resolver.py # Check input_assets/<product_id>/
│   │   │       ├── prompt_gen.py     # Claude → image prompt
│   │   │       ├── image_gen/        # Luma Photon → image URL
│   │   │       ├── compositor.py     # Pillow: resize, crop, overlay
│   │   │       ├── localization.py  # Claude → translate to Spanish
│   │   │       └── checks.py        # Brand/legal image checks
│   │   ├── project.json              # Nx targets (serve, test, ruff, …)
│   │   ├── pyproject.toml
│   │   └── .env.example
│   └── web/                          # React + Vite frontend (pnpm, no auth DB)
│       ├── src/
│       │   ├── pages/Campaign/      # Campaign form + SSE + results grid
│       │   └── lib/campaignApi.ts   # POST /generate/campaign, SSE stream
│       ├── package.json              # @adobe-pipeline/web
│       └── vite.config.ts
│
├── packages/
│   └── campaign-schema/              # Pydantic CampaignBrief / Product; BrandConfig + load_brand_config
│
├── input_assets/                     # User drops product images here
│   └── <product_id>/hero.png         # e.g., insulated-trail-bottle/hero.png
│
├── output/                           # Generated creatives (gitignored)
│   └── <product_id>/{1x1,9x16,16x9}.png + report.json/.md
│
├── config/
│   └── brand.yaml                    # Brand / compliance (loaded by checks.py)
│
├── CLAUDE.md                         # This file
├── README.md
└── z_Documents/                      # Planning docs + one folder per source PDF (PDF + page PNGs)
    ├── plan.md                       # Implementation plan
    ├── PRD.md                        # Product requirements
    ├── plan_architecture.md          # Architecture diagrams
    ├── FDE Take Home Lite/           # FDE Take Home Lite.pdf + FDE Take Home Lite-1.png, …
    └── Gmail - …/                    # Gmail/FAQ PDF + matching -N.png renders
```

---

## How to Run Locally

### Prerequisites
- **Python 3.11+** with `uv` package manager
- **Node 18+** with `pnpm` package manager
- **API keys:**
  - `LUMA_API_KEY` from [lumalabs.ai](https://lumalabs.ai)
  - `ANTHROPIC_API_KEY` from [console.anthropic.com](https://console.anthropic.com)

### Setup

```bash
# 1. Clone the repo, then from your machine:
cd /path/to/adobe-assignment   # your clone: contains apps/, packages/, and .git

# 2. Monorepo install (Node + Nx)
pnpm install   # at repo root; wires workspaces and Nx

# 3. Backend Python env (for api only)
cd apps/api
cp .env.example .env
# Edit .env: keys only if a product has no `input_assets/<id>/hero.*` (GenAI path) or for overlay_locale
uv sync
cd ../..

# 4. Start both (from repo root) — or use two terminals: `nx serve api` / `nx serve web`
pnpm dev
# Vite: http://localhost:3000 (see apps/web/vite.config.ts) — dev proxy to API for `/generate`, `/output-files`, `/health`

# 5. Campaign pipeline (default)
# Open http://localhost:3000/campaign, submit the form, watch SSE fill the grid. PNGs go to /output/ and are served at /output-files/...
```

### One dev stack, multiple Cursor / Claude Code windows

It is **not** required that every chat session start its own Vite and API. Prefer **one** long-lived stack (e.g. project slash command **`/ADOBE-Start`** in `.claude/commands/`, which runs `pnpm install` at the **repo root** when needed, then **`pnpm run dev:web`** from the root so Vite resolves in the pnpm workspace, plus **Uvicorn** in a second tmux window — session `adobe-assignment`, windows `web` and `api` on ports **3000** and **8000**).

- **Other** Claude Code (or Cursor) windows can **assume** that instance is already running and focus on **scoped** work (e.g. a single route or component). They should **not** spawn duplicate servers on the same ports.
- **Shared visibility:** Any window can read the same backend (or Vite) output by running **`tmux capture-pane -t adobe-assignment:api -p -S -80`** (or `-t adobe-assignment:web` for the frontend). That is a shared log view on the host, not a per-chat resource.
- **Quick health check:** `curl -s http://127.0.0.1:8000/health` confirms the API that every chat is talking to. Stop with **`/ADOBE-Stop`** (see `.claude/commands/`) when you are done.

---

## Key Design Decisions (defend in interview)

1. **Hero-first, ratio-second:** Generate/load hero once per product, composite to 3 ratios locally. N GenAI calls, not N×M.

2. **Claude for prompts:** Ask Claude to generate Luma-optimized image prompts from brief context (product, region, audience), not just pass product name.

3. **Pillow for text overlay:** Speed (instant), reliability (no headless browser), control (pixel-level), cost (free vs. second API call).

4. **Caching with seeding:** Hash(prompt + product_id) → cache; if cache miss, call Luma with deterministic seed for reproducible reruns.

5. **SSE streaming:** Live progress UI — images appear one by one as they generate (10-30s each).

6. **Luma + Anthropic:** Both have robust APIs, known behavior, Anthropic SDK direct (no DSPy overhead).

---

## Coding Standards

Extracted from storyboard-agent and z_research/farren-base-feat2 patterns.

### Python Backend

**Linting & Formatting (Ruff)**
- Line length: 88
- Target Python: 3.12
- Quote style: double quotes
- Indent: spaces (4)
- Rules: E, W, F, I, N, B, A, C4, UP, SIM, RUF
- Ignored: E501, UP006, UP007, UP045, UP046, UP047
- Config: Ruff in repo root `pyproject.toml` (`[tool.ruff]`); `apps/api/pyproject.toml` for the API package

**Type Hints**
- Use Python 3.10+ union syntax: `str | None` (not `Optional[str]`)
- Type hints on all function signatures
- Pydantic models for request/response validation

**Error Handling**
- Custom error hierarchy: `APIError` base with status codes
- Subclasses: `NotFoundError(404)`, `BadRequestError(400)`, `UnauthorizedError(401)`, `ForbiddenError(403)`, `InternalServerError(500)`
- FastAPI `@app.exception_handler()` decorators convert to JSON
- Use `raise ... from error` for exception chaining

**Pydantic Models**
- Minimal config (only `ConfigDict` when needed for ORM compatibility)
- No `Field()` unless validation required
- Separate schemas: Create, Read, Update for REST operations
- Use `model_dump()` and `model_dump(exclude_none=True)`

**Service Layer**
- One service module per external dependency (e.g., `luma.py`)
- **Async vs sync:** use `async def` only when the body awaits real non-blocking I/O; use ordinary `def` for blocking or CPU-bound sync work and expose it via a sync route or `run_in_threadpool`—never block the event loop inside `async def`. See `.cursor/rules/005-fastapi-python.mdc`.
- Keyword-only arguments (`*,`) for API clarity
- Read env vars at function call time (not import)
- Comprehensive docstrings with Args, Returns, Raises
- Raise specific exception types (not generic `Exception`)
- Polling loops with timeout protection

**Logging**
- Module-level logger: `logger = logging.getLogger(__name__)`
- Parametric logging: `logger.info("msg %s", var)` — never f-strings in logs
- Use `exc_info=True` in error logs for stack traces
- Log at critical function entry/exit points
- Never log sensitive information

**FastAPI Routes**
- One `APIRouter` per feature; include in main.py with prefix
- Dependency injection via `Depends(dependency_func)`; prefer `Annotated[..., Depends(...)]` for route parameters where practical
- Trailing underscore `_param` when parameter used only for dependency
- `response_model=` for explicit response schemas
- `status_code=` for non-200 success codes

**FastAPI (layout, dependencies, blocking I/O)**

- **Structure:** This repo uses `routes/` + `services/`; larger features may move to domain subpackages (router + schemas + service together). Full checklist: `.cursor/rules/005-fastapi-python.mdc`.
- **Dependencies:** Designed to be safe when invoked multiple times per request; put shared validation (e.g. load entity or 404) in dependencies.
- **Pydantic v2:** `model_dump` / `model_validate`; avoid v1 `.dict()` patterns.

**Async Patterns**
- Use `asyncio.gather(*tasks, return_exceptions=True)` for concurrent execution
- `asyncio.create_task()` for background tasks
- Proper cleanup in `finally` blocks with `task.cancel()`
- Nested async functions for modular logic
- `async with` for resource management

### TypeScript/React Frontend

**Component Props & Types**
- Inline `type` literals for component props (preferred)
- `interface` for larger/complex shapes
- Destructure props in function signature
- Use `React.ReactNode` for children type hints

**CSS Modules & SCSS Nesting**
- CSS Modules (.module.scss) colocated with component
- Nesting depth: 2–4 levels; nesting mirrors JSX structure
- Root block = component wrapper (e.g., `.page`, `.card`, `.adminRoot`)
- Nested selectors reflect JSX hierarchy
- Pseudo-selectors (&:hover, &.active, &:disabled) nested inline
- Shared variables in `_variables.scss` (imported with `@use '../variables' as *;`)
- Both Sass variables AND CSS Custom Properties used
- Semantic color naming: `$bg`, `$bg-raised`, `$bg-hover`, `$text`, `$text-muted`, `$accent`

**className Merging**
- Template literals: ``className={`${styles.btn} ${active ? styles.active : ''}`}``
- Array.filter().join(): `[styles.a, condition ? styles.b : ''].filter(Boolean).join(' ')`

**JSX Patterns**
- Ternary operator for 2–3 branches
- Guard clauses for early returns
- `.map()` with stable keys (not array indices)
- Colocated type/config files (e.g., `campaignFormDefaults.ts` with `CampaignPage.tsx`)

**State Management**
- **Local state** with `useState` for the campaign form and results (no global auth in this app)
- If you add **Zustand** later, use a single store per concern, atomic selector hooks, and an `actions` namespace (see tkdodo’s guides)
- Discriminated unions for complex state: use `kind` discriminant + variant-specific fields
- `useEffect` for side effects with proper cleanup

**TypeScript Config**
- `target: ES2022`
- `jsx: react-jsx` (automatic transform)
- `strict: true`
- `noUnusedLocals: true`, `noUnusedParameters: true`, `noFallthroughCasesInSwitch: true`
- Path alias `@/` for `src/`

### Shared Conventions

- **Pydantic models:** Single source of truth for schema.
- **No circular imports:** Services → models, routes → services.
- **Comments:** Only for WHY, not WHAT. Code self-documents.
- **No hardcoded values:** Config in `.env` or `config/brand.yaml`.

### Cursor Rules

Stored in `.cursor/rules/`:
- **001-adobe-pipeline.mdc** — Monorepo layout, `uv`, pointers to CLAUDE.md
- **005-fastapi-python.mdc** — FastAPI async/sync, Pydantic v2, dependencies, structure vs this repo
- **010-frontend-scss.mdc** — SCSS modules, nesting mirrors JSX, tokens (`apps/web/src/`)
- **020-zustand.mdc** — Optional Zustand if you add `apps/web/src/stores/`

---

## Common Tasks

### Add a new brand compliance check
1. Edit `apps/api/src/services/checks.py` — add function `check_<name>(image_path, brand_pack) -> bool, List[str]`
2. Call it in `apps/api/src/routes/campaign.py` inside the check loop
3. Add SSE event for the result
4. Test with a mocked image

### Change the Luma model
Edit `.env`: `LUMA_MODEL=photon-1` (quality) or `photon-flash-1` (speed)

### Add a new language for localization
Edit `apps/api/src/services/localization.py`: map `target_region` to language code, update prompt. Keep to one extra locale (Spanish) for POC.

### Run tests
```bash
cd apps/api
uv run pytest
```

---

## Debug Mode

Set env var:
```bash
export LOG_LEVEL=DEBUG  # FastAPI logs all requests/responses
```

Or edit `.env`:
```
LOG_LEVEL=DEBUG
LUMA_MODEL=photon-flash-1  # Use fast mode for quick iteration
```

---

## Interview Defense Checklist

Be ready to defend:
- ✅ Why Luma (fast, working code in storyboard-agent)
- ✅ Why Pillow (instant, free, controllable)
- ✅ Why React + FastAPI (already know it from storyboard-agent)
- ✅ Why no deployment (not asked for, local is the contract)
- ✅ Why hero-first (N calls, not N×M)
- ✅ Why SSE (live progress, better UX than polling)
- ✅ Why Spanish-only localization (avoid font rabbit holes in POC)

---

## Related Docs

- **[PRD.md](z_Documents/PRD.md)** — What to build (requirements, deliverables, evaluation notes)
- **[plan.md](z_Documents/plan.md)** — How to build it (architecture, pipeline flow, design decisions, timeline)
- **[plan_architecture.md](z_Documents/plan_architecture.md)** — Architecture diagrams and cache strategy
- **[README.md](README.md)** — How to run it, examples, demo notes

---

*Last updated: 2026-04-23*
