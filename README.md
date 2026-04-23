# Adobe FDE Take-Home — Creative Automation Pipeline

A local creative automation pipeline that reads a campaign brief (JSON or YAML) and optional product images, generates social ad creatives at three aspect ratios per product, and streams live results to a React UI.

---

## Interview / submission checklist (FDE take-home)

Process items are **your** responsibility (not verified by code):

- **Public GitHub repository** with this pipeline and a **comprehensive README** (this file).
- **2–3 minute recorded demo** showing the app running locally and how to install, set API keys, and generate output. Per Adobe’s process, send the video to your **Talent Partner at least one day before** the interview so reviewers can follow along.
- **Live session** (~30 minutes) — be ready to walk through design tradeoffs and how to run the project cold from the README.

---

## How It Works

```
Campaign brief (form or JSON/YAML)
    ↓
POST /generate/campaign  (FastAPI)
    ↓
Per product (parallel):
  ├── input_assets/<product_id>/hero.png exists?
  │     YES → use it                   (local path)
  │     NO  → Claude generates prompt → Luma Photon → hero image URL
  ↓
Compositing × 3 ratios  (Pillow)
  ├── 1:1   → 1080 × 1080 px
  ├── 9:16  → 1080 × 1920 px
  └── 16:9  → 1920 × 1080 px
  Each image: cover-crop + campaign message overlay (bottom bar)
    ↓
SSE events stream to React UI (images appear live as they render)
    ↓
Legal (prohibited terms) + brand checks (contrast, optional logo path) per `config/brand.yaml`
    ↓
output/<product_id>/{1x1,9x16,16x9}.png  +  output/report.json (includes check summary)
```

---

## Prerequisites

- **Python 3.12+** with [`uv`](https://github.com/astral-sh/uv) (install: `curl -LsSf https://astral.sh/uv/install.sh | sh` or see uv docs)
- **Node 18+** with [`pnpm`](https://pnpm.io) (e.g. `corepack enable` then `corepack prepare pnpm@10.27.0 --activate`, or use the version in root `package.json` under `packageManager`)
- **API keys** (only required when a product has no local hero image, or when `overlay_locale: es`):
  - `OPENROUTER_API_KEY` — [openrouter.ai](https://openrouter.ai) — default Claude provider (OpenAI-compatible endpoint)
  - `LUMA_API_KEY` — [lumalabs.ai](https://lumalabs.ai)
  - *Optional:* `ANTHROPIC_API_KEY` from [console.anthropic.com](https://console.anthropic.com) — if set, the code uses the Anthropic SDK directly and ignores `OPENROUTER_API_KEY`.

---

## Setup

These steps assume a **fresh clone** on a new machine. All commands that touch Node use the **repository root** (the directory that contains `package.json` and `apps/`). All Python install and API commands use **`apps/api/`** as the working directory so `uv` picks up `pyproject.toml` and creates `.venv` there.

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd adobe-assignment

# 2. Install Node deps and wire the pnpm workspace (required before Vite or Nx can run)
pnpm install

# 3. Python virtualenv and dependencies for the API
cd apps/api
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY and LUMA_API_KEY (needed when a product has no local hero; see table below)
uv sync --all-groups
cd ../..

# 4. Start the stack from the repo root — serves Vite on :3000 and the API on :8000
pnpm dev
# Open http://localhost:3000  (redirects to /campaign)
```

**Environment file:** the API loads **`apps/api/.env`** (same folder as `apps/api/pyproject.toml`). Uvicorn is always run with **`cd apps/api && uv run …`** (via Nx in `pnpm dev`, or by hand), so the app uses that venv, not a system-wide Python. To point at a single secrets file you already have:

```bash
ln -sf /path/to/your/.env apps/api/.env
```

**Running API and web separately (optional, two terminals):** from the repo root, `pnpm run dev:web` and `pnpm run dev:api`, or in `apps/api` run `uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload` and in another terminal (from `apps/web`) `pnpm dev`.

Open `http://localhost:3000` (redirects to `/campaign`), fill the form, and click **Generate**.

---

## Input

### Campaign Brief (form or file)

The web form submits a JSON body matching this schema. Equivalent YAML is shown for readability; the API expects JSON (see the second block for `curl`).

**YAML (illustrative — not loaded from disk by the app):**

```yaml
campaign_name: "PNW Trail Season 2026"
products:
  - id: insulated-trail-bottle
    name: "Insulated trail bottle (navy)"
  - id: technical-hiking-pack
    name: "Technical hiking pack (olive)"
target_region: "US — Pacific Northwest"
target_audience: "Weekend hikers and backcountry day-trippers"
campaign_message: "Drink clean. Pack smart. Go farther."
# overlay_locale: null   # optional; use "es" for Spanish overlay text
```

**JSON (same payload — paste into `curl` or API clients):**

```json
{
  "campaign_name": "PNW Trail Season 2026",
  "products": [
    { "id": "insulated-trail-bottle", "name": "Insulated trail bottle (navy)" },
    { "id": "technical-hiking-pack", "name": "Technical hiking pack (olive)" }
  ],
  "target_region": "US — Pacific Northwest",
  "target_audience": "Weekend hikers and backcountry day-trippers",
  "campaign_message": "Drink clean. Pack smart. Go farther.",
  "overlay_locale": null
}
```

Minimum 2 products required. `id` must match the folder name under `input_assets/` if you're supplying a local hero image.

Optional field **`overlay_locale`:** set to `"es"` to translate the campaign message to **Spanish** for on-image text (uses Claude via `OPENROUTER_API_KEY`, or `ANTHROPIC_API_KEY` if set). Omit or `null` for English as written.

### Brand and compliance (`config/brand.yaml`)

Edit [`config/brand.yaml`](config/brand.yaml) to tune **prohibited words** (simple legal-style flagging on the **overlay** copy), minimum **bottom-strip contrast** (heuristic WCAG-style signal on each output PNG), and optionally a **logo file path** under the repo (checks that the file exists — it does not stamp the logo on the image in this POC). Results appear in SSE as `legal_check` and `check_result` events and in `output/report.json` under `checks`.

### Local Hero Images (optional)

**The web UI does not upload files.** You add images on disk under the repo (or bind a volume in Docker), using the same **product `id`** as the folder name. The form’s “Product id” field is that folder name.

Drop product images here to skip GenAI generation:

```
input_assets/
└── <product_id>/
    └── hero.png   (or .jpg, .jpeg, .webp)
```

**Per product, one optional hero** — the assignment’s minimum is **at least two products** in the brief; on disk that means **separate `input_assets/<id>/` folders** (e.g. two products ⇒ two folders, each may contain its own `hero.*`). There is not a single shared asset for all products. If a product’s folder is absent or has no `hero` file, the pipeline calls Claude + Luma to generate a hero for **that** product only.

---

## Output

```
output/
├── insulated-trail-bottle/
│   ├── 1x1.png      (1080 × 1080)
│   ├── 9x16.png     (1080 × 1920)
│   └── 16x9.png     (1920 × 1080)
├── technical-hiking-pack/
│   ├── 1x1.png
│   ├── 9x16.png
│   └── 16x9.png
├── report.json      (run metrics + checks.legal_ok, checks.per_creative, …)
└── report.md        (human-readable summary)
```

Images are also served live at `http://localhost:8000/output-files/<product_id>/<ratio>.png` during the run.

---

## Example Output

Each generated creative is a resized/cropped hero image with the campaign message overlaid as a semi-transparent bottom bar:

| 1:1 (1080×1080) | 9:16 (1080×1920) | 16:9 (1920×1080) |
|---|---|---|
| Square — Instagram feed | Vertical — Stories / Reels | Horizontal — display / YouTube |

---

## Key Design Decisions

**Hero-first, ratio-second** — Generate or load one hero image per product, then composite to all three ratios locally with Pillow. N GenAI calls, not N×M.

**Claude for prompt generation** — Rather than passing a product name to Luma directly, Claude synthesizes campaign context (product, region, audience, message) into a Luma-optimized prompt. Better images, and the prompt is auditable.

**Pillow for text overlay** — Instant, free, pixel-level control, no headless browser. A second API call for text rendering would add latency and cost for no quality gain.

**SSE streaming** — Images appear one by one as they finish compositing. Polling or a single JSON response would make the 10–30 s wait per GenAI product opaque.

**Luma Photon** — Proven, working API with fast generation (Photon Flash) and a clean Python SDK.

**Local-only, no database** — This is a proof-of-concept. No auth, no persistence layer beyond the output folder and report files.

**Compliance hooks** — Prohibited-word flagging and a heuristic bottom-strip contrast check run on every run; optional logo path check is configured in `config/brand.yaml`. Flagging does not block file output (interview-friendly “signal, don’t stop the world”).

---

## Assumptions and Limitations

- **Default on-image language is English** — Set `overlay_locale` to `"es"` (API/JSON) or choose Spanish in the web form to translate overlay copy with Claude. Hero image prompts still use the original context from the English brief.
- **GenAI hero cache** — Luma-generated heroes are cached under `cache/` (keyed by product id + prompt). Local `input_assets/` heroes are not cached. Delete `cache/` to force fresh Luma downloads for the same prompt.
- **Font fallback** — Uses Arial on macOS, DejaVu Sans on Linux, or Pillow's built-in default. No custom brand font.
- **Brand checks are heuristic** — Contrast is estimated from the bottom 20% of each PNG; optional primary-color coverage is a loose sample. Logo check verifies file presence, not in-image placement.
- **Parallel hero resolution** — Each product’s hero is resolved in parallel (`asyncio.gather`). Many Luma calls at once may hit rate limits; if that happens, reduce concurrency in code or add staggering.
- **Local images override GenAI** — If `input_assets/<id>/hero.*` exists, it is always used, regardless of brief content. Delete it to force GenAI generation.

---

## Project Structure

```
adobe-assignment/
├── package.json, nx.json, pnpm-workspace.yaml
├── pyproject.toml          # Ruff (Python) at repo root
├── apps/
│   ├── api/                # Python FastAPI backend (uv)
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── routes/campaign.py  # POST /generate/campaign → SSE
│   │   │   └── services/         # compositor, checks, luma, …
│   │   └── tests/
│   └── web/                # React + Vite + TypeScript (pnpm) — @adobe-pipeline/web
│       └── src/pages/Campaign/
├── packages/campaign-schema/  # Pydantic brief + brand config (shared)
├── config/                 # brand.yaml (compliance / brand checks)
├── input_assets/
└── output/                 # gitignored
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | When no local hero, or `overlay_locale: es` | Default Claude provider (OpenRouter's OpenAI-compatible endpoint) |
| `ANTHROPIC_API_KEY` | No (optional override) | If set, uses the Anthropic SDK directly and ignores `OPENROUTER_API_KEY` |
| `ANTHROPIC_MODEL` | No (default: `anthropic/claude-sonnet-4.6`) | Model id. Keep the `anthropic/...` form for OpenRouter; use a bare id (e.g. `claude-sonnet-4-6`) if you switch to `ANTHROPIC_API_KEY` |
| `LUMA_API_KEY` | When no local hero | Luma Photon API key for image generation |
| `LUMA_MODEL` | No (default: `photon-flash-1`) | `photon-1` for quality, `photon-flash-1` for speed |
| `LOG_LEVEL` | No (default: `INFO`) | Set to `DEBUG` for verbose request logging |
