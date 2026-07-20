"""Generate source-backed OpenBull documentation inventories.

This script deliberately reads configuration definitions and metadata, never the
values in a developer's .env file. Generated output is deterministic for a given
source commit so that ``--check`` is suitable for a release or CI gate.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "documentation" / "inventories"
EXTERNAL_API_OUT = ROOT / "documentation" / "06-api-websocket" / "external-api"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def normalized_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.splitlines()) + "\n"


def schema_name(schema: Any) -> str:
    if not schema:
        return "—"
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in schema:
        return " / ".join(schema_name(item) for item in schema["anyOf"])
    if schema.get("type") == "array":
        return f"array[{schema_name(schema.get('items', {}))}]"
    return schema.get("title") or schema.get("type") or "inline schema"


def request_shape(operation: dict[str, Any], method: str, endpoint: Any | None) -> str:
    body = operation.get("requestBody", {}).get("content", {})
    if body:
        media = next(iter(body.values()))
        return schema_name(media.get("schema", {}))
    params = operation.get("parameters", [])
    if params:
        return ", ".join(f"{p.get('in')}:{p.get('name')}" for p in params)
    source = inspect.getsource(endpoint) if endpoint is not None else ""
    if method in {"POST", "PUT", "PATCH"} and any(
        token in source for token in ("request.json(", "_read_body(", "_request_json(")
    ):
        model = re.search(r"([A-Za-z_]\w*)\.model_validate\(", source)
        return model.group(1) if model else "Untyped JSON body (handler-validated)"
    return "No request body"


def response_shape(operation: dict[str, Any], endpoint: Any | None) -> str:
    responses = operation.get("responses", {})
    preferred = responses.get("200") or responses.get("201") or next(iter(responses.values()), {})
    content = preferred.get("content", {})
    if content:
        media = next(iter(content.values()))
        schema = media.get("schema", {})
        if schema:
            return schema_name(schema)

    # FastAPI cannot infer a useful schema for many handlers because they
    # return dictionaries/JSONResponse dynamically. Preserve that fact, but
    # still give readers a source-derived contract hint instead of a blank.
    source = inspect.getsource(endpoint) if endpoint is not None else ""
    if "RedirectResponse" in source:
        return "HTTP redirect"
    keys = re.findall(r"[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\s*:", source)
    priority = [
        "status", "message", "data", "count", "items", "mode", "detail",
        "placed", "consistent", "discrepancy", "details",
    ]
    observed = [key for key in priority if key in keys]
    if observed:
        return "Untyped JSON object; observed keys: " + ", ".join(observed)
    description = preferred.get("description")
    if description and description.lower() not in {"successful response", "success response"}:
        return f"Untyped handler response: {description}"
    return "Untyped handler response; inspect linked handler/OpenAPI"


PUBLIC_PATHS = {
    "/health",
    "/auth/check-setup",
    "/auth/setup",
    "/auth/login",
    "/upstox/callback",
    "/zerodha/callback",
    "/fyers/callback",
    "/dhan/callback",
}

ADMIN_OPERATIONS = {
    ("POST", "/api/v1/analyzertoggle"): "OpenBull API key + active broker context + administrator",
    ("GET", "/auth/error-logs"): "Admin session cookie",
    ("POST", "/web/trading-mode"): "Admin session cookie",
    ("POST", "/web/sandbox/config"): "Admin session cookie",
    ("POST", "/web/sandbox/squareoff-now"): "Admin session cookie",
    ("POST", "/web/sandbox/settle-now"): "Admin session cookie",
    ("POST", "/web/sandbox/wipe-all"): "Admin session cookie",
    ("POST", "/web/sandbox/reload-squareoff"): "Admin session cookie",
    ("POST", "/web/fr/config"): "Admin session cookie",
    ("POST", "/web/fr/target-templates"): "Admin session cookie",
    ("PUT", "/web/fr/target-templates/{template_id}"): "Admin session cookie",
    ("DELETE", "/web/fr/target-templates/{template_id}"): "Admin session cookie",
    ("POST", "/web/fr/targets"): "Admin session cookie",
    ("PUT", "/web/fr/targets/{target_id}"): "Admin session cookie",
    ("DELETE", "/web/fr/targets/{target_id}"): "Admin session cookie",
    ("POST", "/web/fr/symbol-maps"): "Admin session cookie",
    ("PUT", "/web/fr/symbol-maps/{map_id}"): "Admin session cookie",
    ("DELETE", "/web/fr/symbol-maps/{map_id}"): "Admin session cookie",
}


def auth_for(method: str, path: str) -> str:
    if (method, path) in ADMIN_OPERATIONS:
        return ADMIN_OPERATIONS[(method, path)]
    if path in PUBLIC_PATHS:
        return "Public"
    if method == "GET" and path in {
        "/api/v1/futures-risk/trades",
        "/api/v1/futures-risk/trades/{trade_id}",
    }:
        return "OpenBull API key (owner identity; broker context not required)"
    if path.startswith("/api/v1/"):
        return "OpenBull API key + active broker context"
    if "/webhook/" in path:
        return "Strategy webhook token"
    if path.startswith("/ws/strategy/"):
        return "Session cookie during WebSocket handshake"
    return "Session cookie"


def generate_api(app: Any) -> tuple[str, str]:
    spec = app.openapi()
    handlers: dict[tuple[str, str], Any] = {}
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        for route_method in getattr(route, "methods", set()) or set():
            handlers[(route_method.upper(), getattr(route, "path", ""))] = endpoint

    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for path, item in sorted(spec["paths"].items()):
        for method, operation in item.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                continue
            normalized_method = method.upper()
            endpoint = handlers.get((normalized_method, path))
            try:
                source_file = Path(inspect.getsourcefile(endpoint) or "").resolve().relative_to(ROOT)
                source_line = inspect.getsourcelines(endpoint)[1]
                source_ref = f"`{str(source_file).replace(os.sep, '/')}:{source_line}`"
            except (OSError, TypeError, ValueError):
                source_ref = "Generated/internal"
            rows.append(
                (
                    normalized_method,
                    path,
                    operation.get("summary") or operation.get("operationId", "—"),
                    auth_for(normalized_method, path),
                    request_shape(operation, normalized_method, endpoint),
                    response_shape(operation, endpoint),
                    source_ref,
                )
            )
    lines = [
        "# Generated API Endpoint Inventory",
        "",
        "> Generated from the FastAPI OpenAPI document. Authentication labels are classified from the current route families and must be read with the detailed security guide.",
        "",
        f"Operations: **{len(rows)}** across **{len(spec['paths'])}** paths.",
        "",
        "| Method | Path | Operation | Authentication | Request | Success response | Handler |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        escaped = [str(cell).replace("|", "\\|").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    lines.extend(["", "Machine-readable contract: [openapi.json](openapi.json).", ""])
    return "\n".join(lines), json_dump(spec)


def frontend_access(path: str) -> str:
    if path in {"/", "/login", "/setup", "*"}:
        return "Public"
    if path in {
        "/broker/select", "/broker/angel/totp", "/broker/dhan/token",
        "/broker/config", "/apikey", "/logs", "/sandbox", "/sandbox/mypnl",
    }:
        return "Authenticated session"
    return "Authenticated session + active broker"


def generate_frontend_routes() -> str:
    source = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    routes: list[tuple[str, int]] = []
    for match in re.finditer(r'path="([^"]+)"', source):
        path = match.group(1)
        line = source.count("\n", 0, match.start()) + 1
        routes.append((path, line))
    lines = [
        "# Generated Frontend Route Inventory",
        "",
        f"Routes declared in `frontend/src/App.tsx`: **{len(routes)}**.",
        "",
        "| Route | Route guard | Declaration | Notes |",
        "|---|---|---|---|",
    ]
    for path, line in routes:
        notes = "Catch-all not-found page" if path == "*" else ""
        if path == "/tools/futures-risk/admin":
            notes = "Route requires broker; page and mutation APIs enforce admin behavior separately"
        if path == "/tools/futures-risk/card-demo":
            notes = "Source-defined UI demonstration route"
        lines.append(
            f"| `{path}` | {frontend_access(path)} | `frontend/src/App.tsx:{line}` | {notes} |"
        )
    lines.append("")
    return "\n".join(lines)


def generate_database(metadata: Any) -> str:
    tables = list(metadata.sorted_tables)
    lines = [
        "# Generated Database Schema Inventory",
        "",
        f"SQLAlchemy metadata tables: **{len(tables)}**.",
        "",
        "> This is the ORM metadata view. Read it together with the Alembic and startup-migration guide for existing installations.",
        "",
    ]
    for table in tables:
        lines.extend([
            f"## `{table.name}`",
            "",
            "| Column | Type | Nullable | Key/default | Foreign key |",
            "|---|---|---:|---|---|",
        ])
        for col in table.columns:
            markers: list[str] = []
            if col.primary_key:
                markers.append("PK")
            if col.unique:
                markers.append("unique")
            if col.index:
                markers.append("index")
            if col.default is not None:
                default_arg = col.default.arg
                if callable(default_arg):
                    default_arg = getattr(default_arg, "__name__", default_arg.__class__.__name__)
                markers.append(f"default `{default_arg}`")
            if col.server_default is not None:
                markers.append("server default")
            fks = ", ".join(sorted(str(fk.target_fullname) for fk in col.foreign_keys)) or "—"
            lines.append(
                f"| `{col.name}` | `{col.type}` | {'yes' if col.nullable else 'no'} | "
                f"{', '.join(markers) or '—'} | `{fks}` |"
            )
        constraints = [c.name for c in table.constraints if getattr(c, "name", None)]
        indexes = [i.name for i in table.indexes if i.name]
        if constraints or indexes:
            lines.extend([
                "",
                f"Named constraints: {', '.join(f'`{x}`' for x in sorted(constraints)) or '—'}  ",
                f"Indexes: {', '.join(f'`{x}`' for x in sorted(indexes)) or '—'}",
            ])
        lines.append("")
    return "\n".join(lines)


def display_default(field: Any, secret: bool) -> str:
    if secret:
        return "Required; generate a unique secret"
    default = field.default
    text = repr(default)
    if "PydanticUndefined" in text:
        return "Required"
    return f"`{default}`"


def generate_environment(settings_cls: Any) -> str:
    secret_names = {"app_secret_key", "encryption_pepper", "database_url"}
    lines = [
        "# Generated Environment Variable Inventory",
        "",
        "> Generated from `backend.config.Settings`. Values from `.env` are never read or emitted.",
        "",
        "| Variable | Type | Sensitive | Default/requirement | Purpose source |",
        "|---|---|---:|---|---|",
    ]
    for name, field in settings_cls.model_fields.items():
        env_name = name.upper()
        secret = name in secret_names or any(part in name for part in ("secret", "password", "pepper"))
        annotation = str(field.annotation).replace("<class '", "").replace("'>", "")
        lines.append(
            f"| `{env_name}` | `{annotation}` | {'yes' if secret else 'no'} | "
            f"{display_default(field, secret)} | `backend/config.py` |"
        )
    lines.extend([
        "",
        "Deployment scripts also derive production values such as HTTPS frontend/CORS URLs, secure cookies, WebSocket public URL, database credentials, and service paths. See the deployment configuration guide before editing a live `.env`.",
        "",
    ])
    return "\n".join(lines)


def generate_external_api_guides() -> dict[Path, str]:
    """Mirror detailed endpoint guides while redacting key-shaped examples."""
    payloads: dict[Path, str] = {}
    source_root = ROOT / "docs" / "api"
    secret_literal = re.compile(r"(?i)(\"apikey\"\s*:\s*\")[0-9a-f]{32,}(\")")
    banner = (
        "> Generated from the matching in-repository API guide and redacted by "
        "`documentation/tools/generate_reference.py`. Verify its route/schema against "
        "the generated OpenAPI contract for this commit.\n\n"
    )
    for source in sorted(source_root.rglob("*.md")):
        content = source.read_text(encoding="utf-8")
        content = secret_literal.sub(r'\1${OPENBULL_API_KEY}\2', content)
        destination = EXTERNAL_API_OUT / source.relative_to(source_root)

        def rewrite_link(match: re.Match[str]) -> str:
            target = match.group(2)
            if target.startswith(("#", "http://", "https://", "mailto:")):
                return match.group(0)
            path_part, separator, fragment = target.partition("#")
            resolved = (source.parent / path_part).resolve()
            try:
                resolved.relative_to(source_root)
                return match.group(0)  # Identical mirrored layout preserves this link.
            except ValueError:
                if not resolved.exists():
                    return match.group(0)
                relative = os.path.relpath(resolved, destination.parent).replace("\\", "/")
                suffix = f"#{fragment}" if separator else ""
                return f"{match.group(1)}{relative}{suffix}{match.group(3)}"

        content = re.sub(r"(\]\()([^\s)]+)(\))", rewrite_link, content)
        payloads[destination] = banner + content
    return payloads


def generated_payloads() -> dict[Path, str]:
    from backend.config import Settings
    from backend.database import Base
    from backend.main import app

    api_md, openapi_json = generate_api(app)
    metadata = {
        "source_commit_time": git("show", "-s", "--format=%cI", "HEAD"),
        "git_commit": git("rev-parse", "HEAD"),
        "git_describe": git("describe", "--always", "--dirty"),
        "generator": "documentation/tools/generate_reference.py",
    }
    payloads = {
        OUT / "api-endpoints.md": api_md,
        OUT / "openapi.json": openapi_json,
        OUT / "frontend-routes.md": generate_frontend_routes(),
        OUT / "database-schema.md": generate_database(Base.metadata),
        OUT / "environment-variables.md": generate_environment(Settings),
        OUT / "generation-metadata.json": json_dump(metadata),
    }
    payloads.update(generate_external_api_guides())
    return payloads


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if generated files differ")
    args = parser.parse_args()
    payloads = generated_payloads()
    OUT.mkdir(parents=True, exist_ok=True)
    changed: list[Path] = []
    for path, content in payloads.items():
        content = normalized_text(content)
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            changed.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
    if args.check and changed:
        print("Generated documentation is stale:")
        for path in changed:
            print(f" - {path.relative_to(ROOT)}")
        return 1
    verb = "Validated" if args.check else "Generated"
    print(f"{verb} {len(payloads)} reference files for {git('rev-parse', '--short', 'HEAD')}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
