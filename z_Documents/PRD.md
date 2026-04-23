# Adobe FDE Take-Home — PRD Summary

Condensed from **FDE Take Home Lite.pdf** and **Gmail - Forward Deployed AI Engineer, Adobe - Assessment.pdf** (FAQ + process). Use this as the single checklist while building.

---

## What you’re building

A **local proof-of-concept**: a **creative automation pipeline** that takes a **structured campaign brief** + **optional assets**, uses **GenAI for images** when assets are missing, and writes **social-style creatives** (multiple **aspect ratios**) with the **campaign message on the image**. **English** is required; **localization** is optional polish.

**Time:** plan for **2–3 hours** of build; you’ll present in a **~30 minute** live session.

---

## When it’s done: what it does (definition)

**Definition:** A small **local program** (CLI or simple desktop/web UI) that reads a **campaign brief** and optional **brand/product images**, then **produces finished social-style images**—one set per **product** and per **required aspect ratio**—each showing the **campaign message** as readable on-image text. If an expected asset is **absent**, the tool **calls a GenAI image API** to synthesize a suitable visual, then still composites text and exports to disk. Nothing in the brief requires Adobe products, cloud deploy, or a database.

**In one sentence:** *“Turn structured brief + folder of assets into organized, multi-ratio ad creatives with on-image copy, using GenAI only when files aren’t there.”*

---

## Concrete example (illustrative)

**You run** (exact flags TBD when implemented):

```bash
uv run python -m campaign_pipeline run --brief examples/brief.yaml --assets ./input_assets --out ./output
```

**Input — `examples/brief.yaml` (shape is illustrative):**

```yaml
campaign_name: "Spring refresh 2026"
products:
  - id: toothpaste-mint
    name: "Glacier Mint Toothpaste"
  - id: mouthwash-ice
    name: "Arctic Mouthwash"
target_region: "US — Pacific Northwest"
target_audience: "Health-conscious millennials, urban"
campaign_message: "Fresher mornings start here."
```

**Input — `input_assets/` (optional):**

- `toothpaste-mint/hero.png` — product shot (pipeline **reuses** this for that product’s creatives).
- `mouthwash-ice/` — **empty** or missing hero → pipeline **generates** a hero via GenAI for that product.

**Output — `output/` (layout is your choice; example):**

```text
output/
  toothpaste-mint/
    1x1.png      # 1:1 feed
    9x16.png     # 9:16 story
    16x9.png     # 16:9 link / video thumb
  mouthwash-ice/
    1x1.png
    9x16.png
    16x9.png
```

Each PNG is a **final creative**: visual (uploaded or generated) **plus** the line **“Fresher mornings start here.”** rendered on the image (English). A **2–3 minute video** would show this run end-to-end and point to the README for API keys and commands.

---

## Input specification (defined)

These are the **logical** inputs your pipeline accepts. File names and schema keys can match your implementation; the **semantics** below are what the assignment cares about.

### 1. Campaign brief (structured file)

A single document (e.g. `brief.yaml`, `brief.json`) that **must** encode:

| Field | Required | Definition |
|--------|----------|------------|
| **Products** | Yes (≥ **2** distinct products) | List of things being advertised. Each entry should be **identifiable** (e.g. `id` + human-readable `name`) so outputs can be grouped per product. |
| **Target region / market** | Yes | Geographic or commercial market the campaign targets (string). Used to steer messaging/visuals if your generator uses it. |
| **Target audience** | Yes | Who the ads speak to (string). Same as above—prompt/context for generation or copy tone. |
| **Campaign message** | Yes | The **exact short copy** that must appear **on** every final image (English for the minimum bar). |

Optional fields (not required by PDF, but useful): `campaign_name`, `tone`, `cta`, `channels`, dates, etc.

**Example — JSON** (`examples/brief.json`):

```json
{
  "campaign_name": "Spring refresh 2026",
  "products": [
    { "id": "sku-1001", "name": "Glacier Mint Toothpaste" },
    { "id": "sku-2002", "name": "Arctic Mouthwash" }
  ],
  "target_region": "US-Pacific Northwest",
  "target_audience": "Urban millennials who care about oral health",
  "campaign_message": "Fresher mornings start here."
}
```

**Example — YAML** (equivalent semantics to the JSON above):

```yaml
campaign_name: "Spring refresh 2026"
products:
  - id: sku-1001
    name: "Glacier Mint Toothpaste"
  - id: sku-2002
    name: "Arctic Mouthwash"
target_region: "US-Pacific Northwest"
target_audience: "Urban millennials who care about oral health"
campaign_message: "Fresher mornings start here."
```

### 2. Input assets (folder or mock storage)

**Definition:** A directory (or abstraction) of **existing images** the pipeline may **reuse** instead of calling GenAI.

| Concept | Definition |
|---------|------------|
| **Asset root** | Base path you pass in (e.g. `./input_assets`). |
| **Per-product assets** | Files associated with a product **id** from the brief (e.g. `input_assets/sku-1001/hero.png`). Your README should document the **convention** you chose. |
| **Missing file** | If no usable image exists for that product, the pipeline **must** **generate** an image via a **GenAI image model** before compositing text. |

Supported formats: typically **PNG/JPEG**; define what you accept in the README.

---

## Output specification (defined)

**Definition:** A **directory tree** of **raster image files** (e.g. PNG), each representing a **finished social creative** for one **(product × aspect ratio)** pair, with the **campaign message** visibly rendered on the image.

### Required dimensions (semantics)

| Output aspect | Typical use | Pixel size (example only) |
|---------------|-------------|---------------------------|
| **1:1** | Square feed | e.g. 1080×1080 |
| **9:16** | Story / vertical | e.g. 1080×1920 |
| **16:9** | Horizontal / link / video thumb | e.g. 1920×1080 |

Exact pixels are **your choice**; ratios **1:1, 9:16, 16:9** are what the FAQ recommends. You need **at least three** distinct ratios.

### Required cardinality

For **each** product in the brief × **each** required ratio → **exactly one** final image (unless you document otherwise).  
**Minimum file count** for the examples above: **2 products × 3 ratios = 6** files.

### Variants model

A **variant** is one instance of a creative output. The brief's literal objective is *"generate variations for campaign assets."*

The variants model: **product × ratio × (optional locale)**

- **Minimum:** product × ratio (e.g., 2 products × 3 ratios = 6 variants)
- **With localization:** product × ratio × locale (e.g., 2 products × 3 ratios × 2 locales = 12 variants)

This framing clarifies scope for the assignment and for scaling — the pipeline is designed to support multiple dimensions of variation without architectural change.

### Organization

**Definition:** Paths must make it **obvious** which product and which ratio each file belongs to. Example patterns:

- `output/<product_id>/1x1.png`, `9x16.png`, `16x9.png`
- `output/<product_id>_1x1.png`, …
- `output/<product_slug>/feed.png`, `story.png`, `landscape.png` (if README maps names → ratios)

### Content of each file

Each output image **must**:

1. Contain a **hero/visual** area (from **uploaded asset** scaled/cropped **or** **GenAI-generated** image).
2. Display the brief’s **campaign message** as **legible on-image text** (English).

### Example expected outputs (same brief as above)

Given `products`: `sku-1001`, `sku-2002` and ratios **1:1, 9:16, 16:9**:

```text
output/
  sku-1001/
    1x1.png     ← visual + "Fresher mornings start here." at 1:1
    9x16.png    ← same message, 9:16 canvas
    16x9.png    ← same message, 16:9 canvas
  sku-2002/
    1x1.png
    9x16.png
    16x9.png
```

**Expected behavior differences:**

| Situation | Expected output |
|-----------|------------------|
| `sku-1001` has `hero.png` | Background looks like **that photo** (cropped/scaled); message overlaid. |
| `sku-2002` has **no** hero | Background is **GenAI-generated** (on-brand-ish scene/product still life per your prompt); message overlaid. |
| Same `campaign_message` for all | **Identical string** on all six files (unless you add localization as a bonus). |

---

## Must deliver

| Item | Detail |
|------|--------|
| **Demo video** | **2–3 minutes** — show it working + enough for interviewers to run locally |
| **Video timing** | Send to **Talent Partner ≥1 day before** the interview |
| **Repo** | **Public GitHub** — code + **README** |
| **After finish** | Email thread: **links** + **interview availability**; **confirm receipt** if asked |

---

## Required behavior (minimum)

1. **Brief input** — JSON, YAML, or similar; must include:
   - **≥2 different products**
   - **Target region/market**
   - **Target audience**
   - **Campaign message**

2. **Assets** — From a **local folder** or **mock storage**; **reuse** when available.

3. **GenAI** — If something needed is **missing**, **generate** with a **GenAI image API** (any provider — **not** required to use Adobe Firefly).

4. **Aspect ratios** — **≥3** (FAQ suggests **1:1**, **9:16**, **16:9** as standard social sizes).

5. **On-image text** — **Campaign message** visible on the final creative (**English** minimum).

6. **Run locally** — CLI or simple local app; **your** language/framework.

7. **Outputs** — Save to a **folder**, organized **by product** and **aspect ratio** (no mandated naming — **your judgment**).

8. **README** must cover:
   - How to run  
   - Example input + output  
   - Key design decisions  
   - Assumptions + limitations  

---

## Data sources (architecture framing from the brief)

| Layer | Description |
|-------|-------------|
| **User inputs** | Campaign briefs and assets uploaded manually |
| **Storage** | To save generated or transient assets — brief cites Azure, AWS, or Dropbox as examples; local folder satisfies the POC |
| **GenAI** | Best-fit APIs for generating hero images, *resized and localized variations* (note: GenAI scope includes more than just image generation) |

---

## Nice to have (bonus)

- **Brand compliance checks** (e.g., presence of logo, use of brand colors)
- **Simple legal content checks** (e.g., flagging prohibited words)
- **Logging or reporting of results**

---

## FAQ highlights (constraints)

- **No** required Adobe stack (Firefly, AEM, Workfront, DAM, etc.) — goal is **GenAI integration**, generic approach.
- **No** provided API keys — use your own / free tiers as needed.
- **No** required folder naming convention.
- **No** sample brand pack — **make your own** test content if needed.
- **No** required GDPR/CCPA/cloud vs on-prem stance — use judgment.
- **Success story:** emphasize **time saved**, **volume of campaigns/variants**, and **efficiency**.

---

## Design decisions to defend (interview prep)

Be ready to defend these choices:

1. **Image API choice:** Luma Photon (fast, already integrated in storyboard-agent pattern). Alternative considered: OpenAI Images, Stability. Why Luma: known behavior, existing polling pattern, cost-effective.

2. **Text render approach:** Pillow (PIL) for text overlay, not HTML-to-image or GenAI-based text. Why: instant (no API call), reliable (no headless browser), controllable (pixel-level positioning), cost-free (no second API call).

3. **Cache key design:** Hash(prompt + product_id) only, not ratio. Why: hero is generated once per product, reused for all 3 ratios. Ratio is irrelevant to generation.

4. **Hero-first, ratio-second:** Generate/load hero once, composite to 3 ratios locally. N GenAI calls for N products, not N×M. Why: 3× cheaper API cost, 3× faster wall time.

5. **React + FastAPI (not CLI-only):** Adapted from storyboard-agent. Why: already know this stack, no learning curve, clear separation of concerns, compelling demo with SSE streaming.

6. **No deployment to Railway/Vercel:** Brief says "run locally." No requirement to host. Why: reduces setup complexity, risk surface, secret management burden for a take-home.

---

## Evaluation notes

- **Code quality and design** matter; you’ll **defend** the solution and discuss improvements.
- **You** should be the author; AI as a helper is understood, but **your** capability should show through.
- Be ready to discuss the 6 design decisions above (see section above).

---

## Business context (why this scenario exists)

**Business Goals (from the brief — use this language in README/demo):**

1. **Accelerate campaign velocity** — Rapidly ideate, produce, approve, and launch more campaigns per month.
2. **Ensure brand consistency** — Maintain global brand guidelines and voice across all markets and languages.
3. **Maximize relevance & personalization** — Adapt messaging, offers, and creative to local cultures, trends, and consumer preferences.
4. **Optimize marketing ROI** — Improve performance (CTR, conversions) versus cost and time efficiencies.
5. **Gain actionable insights** — Track effectiveness at scale and learn what content/creative/localization drives the best outcomes.

**Pain points** called out in the brief: manual localization at scale, inconsistent quality, slow approvals, weak analytics across silos, creative teams stuck in repetitive work. **You don’t need to solve all of this** — the POC is **variant generation + organization + GenAI fallback**.

---

## Testing this repo (`adobe-assignment`)

**Today:** This repo may only hold this PRD and PDFs—there is **no automated test suite** until application code exists.

**Once the POC exists, plan to verify:**

| Check | Why |
|--------|-----|
| **README path** | Interviewers will follow it cold |
| **Example brief + assets** | Proves inputs are real, not hand-waved |
| **≥2 products, ≥3 ratios** | Hard requirement |
| **Message visible on every output** | Hard requirement |
| **Missing-asset run** | Proves GenAI fallback |
| **API key in env** | No keys supplied by Adobe; use your own |

**Optional later:** unit tests for parsing, path layout, and overlay logic with **mocked** image API calls (CI-friendly, no GPU).

---

## Learnings & context (from specs + surrounding repos)

- **Deliverables are explicit:** public GitHub (code + README), **2–3 min demo video** to Talent Partner **≥1 day** before interview, then email **links + availability**; you may need to **confirm receipt** on the thread.
- **Full-stack is fine if you own it:** The brief says "CLI or simple local app." React + FastAPI is legitimate if you already know the stack (e.g., from storyboard-agent). Avoid new frameworks.
- **GenAI flex:** Any **third-party image API** is fine; **Adobe Firefly / AEM / DAM** are **not** required. Multi-language copy on image is **optional**.
- **Output structure:** No mandated naming—**your judgment**, but must be **clearly organized by product and aspect ratio**.
- **Variants model:** Product × ratio is the minimum. Locale adds a third dimension if localization is enabled.
- **How success is framed (FAQ):** time saved, number of campaigns/variants generated, overall **efficiency**—use that language in README/demo when describing impact.
- **Evaluation:** Expect to **defend** design tradeoffs; they want **your** implementation (AI tools ok, but capability should read as yours). See "Design decisions to defend" section above.
- **Source materials:** Original PDFs live under **`z_Documents/<document-name>/`** next to their page PNGs (e.g. `z_Documents/FDE Take Home Lite/FDE Take Home Lite.pdf`).
- **`storyboard-agent` (pattern reuse):** That project is **full stack** (React/Vite + FastAPI + Supabase + Luma + LLM). For this POC, copy the **FastAPI + SSE + React patterns**, strip the **Supabase auth, NX, database, and deployment** overhead. Reuse = pragmatism, not laziness.
- **`storyboard-research`:** Archive of 67+ cloned repos for research. ComfyUI is great for local GPU pipelines but adds ops burden. For this assignment, a single HTTP image API (Luma, DALL-E, etc.) is sufficient.

---

*Source PDFs: `z_Documents/FDE Take Home Lite/`, `z_Documents/Gmail - … Assessment/` (see that folder for exact names).*
