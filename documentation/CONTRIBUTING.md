# Maintaining the Documentation

Documentation changes are part of the feature definition. A change is incomplete when it alters a user-visible field, route, API contract, database table, permission, scheduled task, integration, environment variable, or operational procedure without updating this directory.

## Update workflow

1. Identify the affected technical and user-manual sections.
2. Run `documentation/tools/generate_reference.py`.
3. Update prose, workflow steps, validation rules, permissions, expected results, and troubleshooting guidance.
4. Capture replacement screenshots from the same commit being released.
5. Redact all secrets and account identifiers.
6. Update cross-links and the traceability matrix.
7. Run backend tests, frontend lint/build, and documentation validation.
8. Record the release in `13-change-log/CHANGELOG.md`.
9. Have a second developer or tester complete `validation/review-checklist.md`.

## Writing rules

- Describe current behavior, not intended future behavior.
- State explicitly when a requested role or capability is not implemented.
- Use exact UI labels and exact HTTP paths.
- Do not hardcode credentials, broker account values, live symbols, current prices, dates, or environment-specific hostnames as universal values.
- Mark examples as examples.
- Link a page workflow to the API, model, integration, and troubleshooting sections it depends on.
- For destructive actions, describe confirmation, authorization, scope, and recovery implications.

## Screenshot rules

- Capture the complete page at 1440×900 unless a workflow needs a focused image.
- Number action screenshots in workflow order: `01-`, `02-`, and so on.
- Store assets under `documentation/assets/screenshots/<route-slug>/`.
- Use a documentation-only database/account and sandbox mode.
- Mask API keys, broker tokens, client IDs, names, email addresses, order IDs, and account balances when they identify a real person or account.
- Record route, final URL, viewport, commit, capture time, content hash, and fixture boundary in `assets/screenshots/manifest.json`.

## Validation commands

```powershell
cd D:\openbull
.\.venv\Scripts\python.exe .\documentation\tools\generate_reference.py --check
.\.venv\Scripts\python.exe .\documentation\tools\validate_documentation.py
.\.venv\Scripts\python.exe -m unittest discover -s backend\test -p "test_*.py" -v
cd frontend
npm run lint
npm run build
```
