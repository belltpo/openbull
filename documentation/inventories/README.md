# Generated Inventories

The files in this directory are generated from the current application source and metadata:

- `api-endpoints.md` and `openapi.json`
- `frontend-routes.md`
- `database-schema.md`
- `environment-variables.md`
- `generation-metadata.json`

Regenerate them with:

```powershell
.\.venv\Scripts\python.exe .\documentation\tools\generate_reference.py
```

Do not manually edit generated files. Add interpretation, workflows, permission detail, and operational guidance in the numbered documentation sections.
