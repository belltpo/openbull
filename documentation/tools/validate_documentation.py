"""Validate generated references, internal links, routes, and screenshots."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DOCS = ROOT / "documentation"
SCREENSHOTS = DOCS / "assets" / "screenshots"
LINK_RE = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
ROUTE_RE = re.compile(r"^\| `([^`]+)` \|", re.MULTILINE)


def validate_generated(errors: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, str(DOCS / "tools" / "generate_reference.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        errors.append((result.stdout + result.stderr).strip())


def validate_authorization_inventory(errors: list[str]) -> None:
    from documentation.tools.generate_reference import ADMIN_OPERATIONS

    inventory = (DOCS / "inventories" / "api-endpoints.md").read_text(encoding="utf-8")
    for (method, path), expected in ADMIN_OPERATIONS.items():
        marker = f"| {method} | {path} |"
        row = next((line for line in inventory.splitlines() if line.startswith(marker)), None)
        if row is None or f"| {expected} |" not in row:
            errors.append(f"Authorization inventory drift: {method} {path} must be {expected}")


def validate_endpoint_contract_inventory(errors: list[str]) -> None:
    inventory = (DOCS / "inventories" / "api-endpoints.md").read_text(encoding="utf-8")
    rows = [line for line in inventory.splitlines() if re.match(r"^\| (GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD) \|", line)]
    if not rows:
        errors.append("API endpoint inventory contains no operation rows")
        return
    for row in rows:
        columns = [cell.strip() for cell in row.strip("|").split("|")]
        if len(columns) != 7:
            errors.append(f"Malformed API inventory row: {row[:120]}")
            continue
        method, path, _operation, _auth, request, response, handler = columns
        if request in {"", "—"}:
            errors.append(f"Missing request contract summary: {method} {path}")
        if response in {"", "—"}:
            errors.append(f"Missing response contract summary: {method} {path}")
        if handler in {"", "—"}:
            errors.append(f"Missing handler reference: {method} {path}")


def validate_links(errors: list[str]) -> None:
    for page in DOCS.rglob("*.md"):
        text = page.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            if "<" in raw_target or ">" in raw_target:
                continue
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path_text = unquote(target.split("#", 1)[0])
            if not path_text:
                continue
            resolved = (page.parent / path_text).resolve()
            if not resolved.exists():
                errors.append(f"Broken link in {page.relative_to(ROOT)}: {target}")


def route_fixture(route: str) -> str:
    if route == "*":
        return "/documentation-route-not-found"
    return route.replace(":id", "1")


def validate_screenshots(errors: list[str]) -> None:
    manifest_path = SCREENSHOTS / "manifest.json"
    if not manifest_path.exists():
        errors.append("Screenshot manifest is missing")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    captures = manifest.get("captures", [])
    base_captures = {item["route"] for item in captures if "action" not in item}

    route_inventory = (DOCS / "inventories" / "frontend-routes.md").read_text(
        encoding="utf-8"
    )
    declared = ROUTE_RE.findall(route_inventory)
    missing_routes = sorted(
        route for route in declared if route_fixture(route) not in base_captures
    )
    if missing_routes:
        errors.append(f"Routes missing complete-page capture: {', '.join(missing_routes)}")

    manifest_files: set[str] = set()
    for item in captures:
        relative = item["file"].replace("\\", "/")
        manifest_files.add(relative)
        image = SCREENSHOTS / relative
        if not image.exists() or image.stat().st_size < 1000:
            errors.append(f"Missing/empty screenshot: {relative}")
        final_path = urlparse(item["final_url"]).path
        if final_path != item["route"]:
            errors.append(
                f"Screenshot redirect mismatch: {item['route']} -> {item['final_url']}"
            )
        if not item.get("body_text_preview", "").strip():
            errors.append(f"Blank rendered body: {relative}")
        preview = item.get("body_text_preview", "").lower()
        if item["route"] != "/documentation-route-not-found" and any(
            marker in preview
            for marker in ("failed to load", "unexpected error", "unknown instrument")
        ):
            errors.append(f"Runtime error state captured as evidence: {relative}")

    actual_files = {
        str(path.relative_to(SCREENSHOTS)).replace("\\", "/")
        for path in SCREENSHOTS.rglob("*.png")
    }
    for orphan in sorted(actual_files - manifest_files):
        errors.append(f"Screenshot not recorded in manifest: {orphan}")

    action_evidence = {
        (item["route"], item.get("action", "")) for item in captures if "action" in item
    }
    required_actions = {
        ("/broker/config", "Open broker selector"),
        ("/playground", "Switch to WebSocket mode"),
        ("/orderbook", "Open order modification dialog"),
        ("/orderbook", "Open single-order cancellation confirmation"),
        ("/orderbook", "Open cancel-all confirmation"),
        ("/positions", "Open single-position close confirmation"),
        ("/positions", "Open close-all confirmation"),
        ("/sandbox", "Open sandbox reset confirmation"),
        ("/tools/strategyportfolio", "Expand a saved strategy"),
        ("/tools/strategyportfolio", "Open close-strategy dialog"),
        ("/tools/strategyportfolio", "Open delete-strategy confirmation"),
        ("/tools/futures-risk", "Open phase history"),
        ("/tools/futures-risk", "Open Quick Order"),
        ("/tools/futures-risk/card-demo", "Expand every instrument timeline"),
        ("/strategy/new", "Select signal-driven strategy"),
        ("/strategy/1", "Open strategy setup tab"),
        ("/strategy/1", "Open strategy webhook tab"),
    }
    missing_actions = sorted(required_actions - action_evidence)
    if missing_actions:
        errors.append(
            "Important action evidence missing: "
            + ", ".join(f"{route} ({action})" for route, action in missing_actions)
        )
    if not (SCREENSHOTS / "annotations.md").exists():
        errors.append("Numbered screenshot annotation guide is missing")


def validate_manual_chapters(errors: list[str]) -> None:
    chapters = [
        "getting-started.md", "core-trading.md", "analytics.md",
        "strategy-builder.md", "strategy-automation.md", "futures-risk.md",
        "api-and-live-data.md",
    ]
    concepts = {
        "purpose/access": ("purpose", "access"),
        "screenshots": ("screenshot",),
        "controls/fields": ("control", "field"),
        "workflow": ("workflow",),
        "validation/errors": ("validation", "error"),
        "expected result": ("expected",),
        "APIs/dependencies": ("api", "dependenc"),
    }
    base = DOCS / "10-end-user-manual"
    for filename in chapters:
        text = (base / filename).read_text(encoding="utf-8").lower()
        for label, alternatives in concepts.items():
            if not any(term in text for term in alternatives):
                errors.append(f"Manual chapter {filename} lacks {label} coverage")


def validate_no_secret_literals(errors: list[str]) -> None:
    forbidden = re.compile(
        r"(?i)(?:api[_ -]?key|access[_ -]?token|password)\s*[:=]\s*['\"]?[0-9a-f]{32,}"
    )
    for page in DOCS.rglob("*.md"):
        if forbidden.search(page.read_text(encoding="utf-8")):
            errors.append(f"Possible credential literal in {page.relative_to(ROOT)}")


def validate_encoding(errors: list[str]) -> None:
    mojibake = ("â€", "â€“", "â€”", "Â", "Ã", "ðŸ")
    for page in DOCS.rglob("*.md"):
        text = page.read_text(encoding="utf-8")
        if any(marker in text for marker in mojibake):
            errors.append(f"Possible mojibake in {page.relative_to(ROOT)}")


def main() -> int:
    errors: list[str] = []
    validate_generated(errors)
    validate_authorization_inventory(errors)
    validate_endpoint_contract_inventory(errors)
    validate_links(errors)
    validate_screenshots(errors)
    validate_manual_chapters(errors)
    validate_no_secret_literals(errors)
    validate_encoding(errors)
    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print(
        "Documentation validation passed: generated references, authorization labels, "
        "links, routes, screenshots/actions, manual sections, encoding, and secret scan."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
