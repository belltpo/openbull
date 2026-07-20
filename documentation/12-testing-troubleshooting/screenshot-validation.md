# Screenshot and Manual Validation

## Capture environment

Use a dedicated local documentation database, documentation-only admin, sandbox trading mode, masked provider values, and the commit recorded in each manifest. Do not use a live personal broker account for documentation images.

## Capture procedure

1. Build/start PostgreSQL, Redis, FastAPI, and Vite from the documented commit.
2. Seed only source-defined demo/sandbox records needed for the workflow.
3. Set viewport to 1440×900 and record theme/mode.
4. Capture `00-complete-page.png` for the full route.
5. Capture numbered action images in workflow order.
6. Redact secrets and personal identifiers without hiding the UI control being explained.
7. Compare all labels, options, defaults, errors, and results to source and runtime.
8. Complete the route `manifest.md`.

## Screenshot acceptance

- Entire page header/navigation and principal content visible.
- No browser password manager, personal profile, real API key/token, or unrelated window.
- No stale error banner unless the screenshot documents that error.
- Live values include capture time and are not described as stable constants.
- Source-defined demo data is labelled demo data.
