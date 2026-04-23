# ADOBE-Start

Start the adobe-assignment dev servers (Vite + FastAPI) in a persistent **tmux** session so any Claude Code instance can read their output.

**Path rule:** No machine-specific home paths. Run every block from **this repository’s git root** (the folder that contains `apps/`, `package.json`, and `.git`). Get it once with:

```bash
cd path/to/your/clone
export REPO="$(git rev-parse --show-toplevel)"
```

Use `$REPO` in all `cd` / `send-keys` below. If the shell is **already** at the git root, `REPO` can be `$(git rev-parse --show-toplevel)` inline.

## Constants
- **Session name:** `adobe-assignment`
- **Window `web`** — Vite, **port `3000`** (`apps/web/vite.config.ts`)
- **Window `api`** — FastAPI, **port `8000`**
- **Repo root** — `REPO` = `$(git rev-parse --show-toplevel)` from inside the clone

## Pre-flight Check 1: Is the tmux session already running?
```bash
tmux has-session -t adobe-assignment 2>/dev/null && echo "SESSION_EXISTS" || echo "NO_SESSION"
```

If `SESSION_EXISTS`:
- Capture recent output from both windows:
```bash
tmux capture-pane -t adobe-assignment:web -p -S -20
tmux capture-pane -t adobe-assignment:api -p -S -20
```
- If the frontend shows `ready in` or `Local:` and the backend shows `Application startup complete` or `Uvicorn running`, report both servers are **already running** and stop. Do not create duplicates.
- If the session exists but appears crashed, kill it and proceed:
```bash
tmux kill-session -t adobe-assignment
```

## Pre-flight Check 2: Are the ports already in use?
```bash
lsof -ti:3000 2>/dev/null && echo "PORT_3000_IN_USE" || echo "PORT_3000_FREE"
lsof -ti:8000 2>/dev/null && echo "PORT_8000_IN_USE" || echo "PORT_8000_FREE"
```

If a port is in use, report the PID and process:
```bash
lsof -i:3000 | head -5
lsof -i:8000 | head -5
```

Ask the user whether to kill the occupying process before proceeding. If confirmed:
```bash
lsof -ti:3000 | xargs kill -9 2>/dev/null
lsof -ti:8000 | xargs kill -9 2>/dev/null
```

## Create Session and Start Servers

**Monorepo rule:** JavaScript dependencies are installed at the **repository root** (`pnpm install`). If the user has never run that (or they see `ERR_CONNECTION_REFUSED` on :3000), the Vite binary is not available. The commands below run from `$REPO` and use a workspace **filter** so the web app always resolves `vite` correctly.

**Before Step 1:** `cd` to the repository root, then:
```bash
export REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"
```

### Step 0: Ensure Node dependencies (idempotent, fast when already installed)
```bash
pnpm install
```
(Or only when missing: `test -d "$REPO/node_modules" || pnpm -C "$REPO" install`.)

### Step 1: Create the tmux session with the `web` window
```bash
tmux new-session -d -s adobe-assignment -n web -x 220 -y 50
```

### Step 2: Create the `api` window
```bash
tmux new-window -t adobe-assignment -n api
```

### Step 3: Start the frontend (from repo root — do **not** rely on `cd apps/web` alone before `pnpm install`)
```bash
tmux send-keys -t adobe-assignment:web "cd \"$REPO\" && pnpm run dev:web" Enter
```

### Step 4: Start the backend
```bash
tmux send-keys -t adobe-assignment:api "cd \"$REPO/apps/api\" && uv sync && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload" Enter
```

**Alternative (single shell, no tmux):** from `$REPO`, run `pnpm run dev` to start both API and web through Nx (uses `NX_DAEMON=false` in the script; run `nx reset` if the Nx daemon ever hangs).

### Step 5: Wait and verify
```bash
sleep 4 && tmux capture-pane -t adobe-assignment:web -p -S -20 && echo "---API---" && tmux capture-pane -t adobe-assignment:api -p -S -20
```

Look for:
- **Frontend:** `ready in` or `Local:   http://localhost:3000/`
- **Backend:** `Application startup complete` or `Uvicorn running on http://0.0.0.0:8000` (or `127.0.0.1:8000`)

If either shows an error (e.g. `EADDRINUSE`, missing `uv`/`pnpm`), report it and suggest fixes.

## Instructions
1. `cd` to the git root; `export REPO="$(git rev-parse --show-toplevel)"`.
2. Run Pre-flight Check 1. If the session is healthy, stop and report.
3. Run Pre-flight Check 2. Report port conflicts; ask before killing.
4. Run **Step 0** (`pnpm install` at least once) before first start or when `node_modules` is missing.
5. Run Steps 1–5 in order.
6. Report:
   - Servers in tmux session **`adobe-assignment`**
   - **Campaign UI:** `http://localhost:3000/campaign`
   - **API:** `http://localhost:8000` | **Docs:** `/docs` | **Health:** `/health`
   - **Logs:** `tmux attach -t adobe-assignment` (windows: `Ctrl-b` then `n` / `p`)
   - **Stop:** `/ADOBE-Stop`

## Notes
- GenAI path needs `apps/api/.env` with `ANTHROPIC_API_KEY` and `LUMA_API_KEY` if any product lacks a local hero. Local-hero-only runs do not.
- Vite **proxies** `/generate`, `/output-files`, `/health` to the API in dev.
