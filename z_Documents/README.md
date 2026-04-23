# z_Documents

Planning text (`PRD.md`, `plan.md`, `plan_architecture.md`) lives at the top level. Each **assignment PDF** is in its **own subfolder** together with that document’s per-page **PNG** renders, so a sorted file listing groups the source with `*-1.png`, `*-2.png`, etc.

- `FDE Take Home Lite/` — `FDE Take Home Lite.pdf` + `FDE Take Home Lite-1.png` …
- `Gmail - Forward Deployed AI Engineer, Adobe - Assessment/` — the `.pdf` + matching `-N.png` files

Renders are **checked in** so you can read them in the repo without re-running the conversion. To **regenerate** (requires Poppler’s `pdftoppm`):

```bash
REPO=$(git rev-parse --show-toplevel)
FDE="$REPO/z_Documents/FDE Take Home Lite"
GMAIL="$REPO/z_Documents/Gmail - Forward Deployed AI Engineer, Adobe - Assessment"
pdftoppm -png "$FDE/FDE Take Home Lite.pdf" "$FDE/FDE Take Home Lite"
pdftoppm -png \
  "$GMAIL/Gmail - Forward Deployed AI Engineer, Adobe - Assessment.pdf" \
  "$GMAIL/Gmail - Forward Deployed AI Engineer, Adobe - Assessment"
```
