# ADOBE-Stop

Stop the **full-stack** adobe-assignment dev servers (tmux session `adobe-assignment`) and free **ports 3000 and 8000**.

**Note:** If you started the stack with `pnpm run dev` (Nx) in a regular terminal **instead of** tmux, there is no `adobe-assignment` session — **Step 2** (port-based kill) still stops those processes. If the browser still shows "connection refused" after a **start**, run **`pnpm install`** at the **repo root** first, then start again (see `ADOBE-Start` Step 0).

## Constants
- **Session:** `adobe-assignment`
- **Ports:** `3000` (Vite), `8000` (API)

## Step 1: Kill the tmux session
```bash
tmux kill-session -t adobe-assignment 2>/dev/null && echo "SESSION_KILLED" || echo "NO_SESSION"
```

## Step 2: Port-based fallback
```bash
lsof -ti:3000 | xargs kill -9 2>/dev/null && echo "PORT_3000_CLEANED" || echo "PORT_3000_ALREADY_FREE"
lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "PORT_8000_CLEANED" || echo "PORT_8000_ALREADY_FREE"
```

## Step 3: Verify
```bash
tmux has-session -t adobe-assignment 2>/dev/null && echo "WARNING: session still exists" || echo "Session gone"
lsof -ti:3000 2>/dev/null && echo "WARNING: 3000 still in use" || echo "3000 free"
lsof -ti:8000 2>/dev/null && echo "WARNING: 8000 still in use" || echo "8000 free"
```

## Instructions
- Run Steps 1–3. Report `SESSION_KILLED` or `NO_SESSION` and whether ports are free. Idempotent (safe to run more than once).
