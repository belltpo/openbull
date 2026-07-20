"""Capture source-backed frontend route screenshots through Chrome CDP.

This script starts the dedicated documentation backend, Vite, and a temporary
Chrome profile. It creates a documentation-only account at runtime and never
prints its generated password. Captures include final URL/title and a body-text
hash so redirects and blank pages can be detected during review.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websocket


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "documentation" / "assets" / "screenshots"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
BASE = "http://127.0.0.1:5173"
USERNAME = "docs_admin"

ROUTES = [
    ("home", "/"),
    ("login", "/login"),
    ("broker-select", "/broker/select"),
    ("broker-angel-totp", "/broker/angel/totp"),
    ("broker-dhan-token", "/broker/dhan/token"),
    ("quick-order", "/quick-order"),
    ("playground", "/playground"),
    ("dashboard", "/dashboard"),
    ("broker-config", "/broker/config"),
    ("api-key", "/apikey"),
    ("search", "/search"),
    ("order-book", "/orderbook"),
    ("trade-book", "/tradebook"),
    ("positions", "/positions"),
    ("holdings", "/holdings"),
    ("websocket-test", "/websocket/test"),
    ("logs", "/logs"),
    ("sandbox", "/sandbox"),
    ("sandbox-pnl", "/sandbox/mypnl"),
    ("tools", "/tools"),
    ("option-chain", "/tools/optionchain"),
    ("oi-tracker", "/tools/oitracker"),
    ("max-pain", "/tools/maxpain"),
    ("option-greeks", "/tools/greeks"),
    ("iv-smile", "/tools/ivsmile"),
    ("volatility-surface", "/tools/volsurface"),
    ("straddle", "/tools/straddle"),
    ("gex", "/tools/gex"),
    ("straddle-strangle-chain", "/tools/straddles-strangle-chain"),
    ("strategy-builder", "/tools/strategybuilder"),
    ("strategy-portfolio", "/tools/strategyportfolio"),
    ("futures-risk", "/tools/futures-risk"),
    ("futures-risk-admin", "/tools/futures-risk/admin"),
    ("futures-risk-card-demo", "/tools/futures-risk/card-demo"),
    ("strategy-list", "/strategy"),
    ("strategy-wizard", "/strategy/new"),
    ("strategy-detail", "/strategy/1"),
    ("strategy-edit", "/strategy/1/edit"),
    ("not-found", "/documentation-route-not-found"),
]

CLICK_TEXT = """(label) => {
  const control = [...document.querySelectorAll('button,[role=tab]')]
    .find(node => (node.innerText || '').trim().includes(label));
  if (!control) return 0;
  control.click();
  return 1;
}"""

ACTIONS: dict[str, list[tuple[str, str, str]]] = {
    "order-book": [
        (
            "01-modify-order.png",
            "Open order modification dialog",
            "(()=>{const x=[...document.querySelectorAll('button')].find(n=>(n.innerText||'').trim()==='Modify');if(!x)return 0;x.click();return 1})()",
        ),
        (
            "02-cancel-order-confirmation.png",
            "Open single-order cancellation confirmation",
            "(()=>{const x=[...document.querySelectorAll('button')].find(n=>(n.innerText||'').trim()==='Cancel');if(!x)return 0;x.click();return 1})()",
        ),
        (
            "03-cancel-all-confirmation.png",
            "Open cancel-all confirmation",
            "(()=>{const x=[...document.querySelectorAll('button')].find(n=>(n.innerText||'').trim().startsWith('Cancel All'));if(!x)return 0;x.click();return 1})()",
        ),
    ],
    "positions": [
        (
            "01-close-position-confirmation.png",
            "Open single-position close confirmation",
            "(()=>{const x=[...document.querySelectorAll('button')].find(n=>(n.innerText||'').trim()==='Close');if(!x)return 0;x.click();return 1})()",
        ),
        (
            "02-close-all-confirmation.png",
            "Open close-all confirmation",
            "(()=>{const x=[...document.querySelectorAll('button')].find(n=>(n.innerText||'').trim().startsWith('Close All'));if(!x)return 0;x.click();return 1})()",
        ),
    ],
    "broker-config": [
        (
            "01-open-broker-selector.png",
            "Open broker selector",
            "(()=>{const x=document.querySelector('[role=combobox]');if(!x)return 0;x.click();return 1})()",
        )
    ],
    "playground": [
        (
            "01-websocket-mode.png",
            "Switch to WebSocket mode",
            f"({CLICK_TEXT})('WebSocket')",
        )
    ],
    "sandbox": [
        (
            "01-reset-confirmation.png",
            "Open sandbox reset confirmation",
            f"({CLICK_TEXT})('Reset my sandbox')",
        )
    ],
    "futures-risk": [
        (
            "01-phase-history.png",
            "Open phase history",
            f"({CLICK_TEXT})('Phase history')",
        ),
        (
            "02-quick-order.png",
            "Open Quick Order",
            f"({CLICK_TEXT})('Quick Order')",
        ),
    ],
    "futures-risk-card-demo": [
        (
            "01-expand-all.png",
            "Expand every instrument timeline",
            "(()=>{const xs=[...document.querySelectorAll('button')].filter(x=>(x.innerText||'').trim()==='Expand all');xs.forEach(x=>x.click());return xs.length})()",
        )
    ],
    "strategy-wizard": [
        (
            "01-signal-driven.png",
            "Select signal-driven strategy",
            f"({CLICK_TEXT})('Signal-driven')",
        )
    ],
    "strategy-portfolio": [
        (
            "01-expanded-strategy.png",
            "Expand a saved strategy",
            "(()=>{const x=document.querySelector('button[aria-label=\"Expand\"]');if(!x)return 0;x.click();return 1})()",
        ),
        (
            "02-close-strategy.png",
            "Open close-strategy dialog",
            f"({CLICK_TEXT})('Close strategy')",
        ),
        (
            "03-delete-strategy-confirmation.png",
            "Open delete-strategy confirmation",
            "(()=>{const x=[...document.querySelectorAll('button')].find(n=>(n.innerText||'').trim()==='Delete');if(!x)return 0;x.click();return 1})()",
        ),
    ],
    "strategy-detail": [
        (
            "01-setup-tab.png",
            "Open strategy setup tab",
            f"({CLICK_TEXT})('Setup')",
        ),
        (
            "02-webhook-tab.png",
            "Open strategy webhook tab",
            f"({CLICK_TEXT})('Webhook')",
        ),
    ],
}


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_port(port: int, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(port):
            return
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for local port {port}")


def chrome_path() -> Path:
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError("Chrome or Edge was not found")


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(
            ws_url, timeout=20, origin="http://127.0.0.1:9222"
        )
        self.next_id = 0

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self.next_id += 1
        call_id = self.next_id
        self.ws.send(json.dumps({"id": call_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") != call_id:
                continue
            if "error" in message:
                raise RuntimeError(f"CDP {method}: {message['error']}")
            return message.get("result", {})

    def evaluate(self, expression: str, await_promise: bool = True) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
            },
        )
        remote = result.get("result", {})
        if remote.get("subtype") == "error":
            raise RuntimeError(remote.get("description", "JavaScript evaluation failed"))
        return remote.get("value")

    def navigate(self, url: str, settle: float = 2.0) -> None:
        self.call("Page.navigate", {"url": url})
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                state = self.evaluate("document.readyState", await_promise=False)
                if state == "complete":
                    break
            except Exception:
                pass
            time.sleep(0.2)
        time.sleep(settle)

    def capture(self, path: Path) -> dict[str, Any]:
        deepest_scroll = self.evaluate(
            "Math.max(document.documentElement.scrollHeight, document.body?.scrollHeight||0, "
            "...[...document.querySelectorAll('*')].map(x=>x.scrollHeight||0))",
            False,
        )
        target_height = max(900, min(12000, int(deepest_scroll or 900)))
        self.call(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 1440,
                "height": target_height,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )
        time.sleep(0.35)
        metrics = self.call("Page.getLayoutMetrics")
        size = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
        width = max(1440, int(size.get("width", 1440)))
        height = max(target_height, min(12000, int(size.get("height", target_height))))
        shot = self.call(
            "Page.captureScreenshot",
            {
                "format": "png",
                "fromSurface": True,
                "captureBeyondViewport": True,
                "clip": {"x": 0, "y": 0, "width": width, "height": height, "scale": 1},
            },
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(shot["data"]))
        body = self.evaluate("document.body ? document.body.innerText : ''", False) or ""
        self.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
        )
        return {
            "final_url": self.evaluate("location.href", False),
            "title": self.evaluate("document.title", False),
            "width": width,
            "height": height,
            "body_text_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "body_text_preview": body[:240].replace("\n", " | "),
        }


def browser_ws_url() -> str:
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=1) as response:
                targets = json.load(response)
            pages = [target for target in targets if target.get("type") == "page"]
            if pages:
                return pages[0]["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("Chrome DevTools target did not start")


def write_catalogue(record: dict[str, Any]) -> None:
    lines = [
        "# Verified Screenshot Catalogue",
        "",
        f"> Captured from commit `{record['git_commit'][:12]}` at "
        f"`{record['captured_at']}` with a 1440 x 900 CSS-pixel viewport.",
        "",
        "The captures use a dedicated local documentation database in Sandbox mode, an "
        "unsupported documentation-only broker guard, and labelled order/position/holding/trade/strategy fixtures. "
        "They verify source-rendered layouts, route guards, populated sandbox states, and safe UI interactions without contacting a broker. "
        "Time-dependent broker values and successful live-order outcomes require a "
        "separate sanitized runtime evidence pass.",
        "",
    ]
    for capture in record["captures"]:
        action = capture.get("action")
        heading = action or "Verified route state"
        lines.extend(
            [
                f"## `{capture['route']}` — {heading}",
                "",
                f"Final URL: `{capture['final_url']}`  ",
                f"Rendered size: `{capture['width']} x {capture['height']}`  ",
                f"File: [`{capture['file']}`]({capture['file']})",
                "",
                f"![{capture['route']} — {heading}]({capture['file']})",
                "",
            ]
        )
    content = "\n".join(line.rstrip() for line in lines).rstrip() + "\n"
    (OUT / "README.md").write_text(content, encoding="utf-8", newline="\n")


def start_processes(temp_dir: Path) -> tuple[list[subprocess.Popen[Any]], CDP]:
    if port_open(8000) or port_open(5173) or port_open(9222):
        raise RuntimeError("Ports 8000, 5173, and 9222 must be free")
    devnull = open(os.devnull, "wb")
    processes: list[subprocess.Popen[Any]] = []
    subprocess.run(
        [str(PYTHON), "documentation/tools/docs_runtime.py", "recreate"],
        cwd=ROOT,
        check=True,
        stdout=devnull,
        stderr=devnull,
    )
    processes.append(
        subprocess.Popen(
            [str(PYTHON), "documentation/tools/docs_runtime.py", "serve"],
            cwd=ROOT,
            stdout=devnull,
            stderr=devnull,
        )
    )
    wait_port(8000, 120)
    processes.append(
        subprocess.Popen(
            ["cmd.exe", "/c", "npm run dev -- --host 127.0.0.1"],
            cwd=ROOT / "frontend",
            stdout=devnull,
            stderr=devnull,
        )
    )
    wait_port(5173, 120)
    processes.append(
        subprocess.Popen(
            [
                str(chrome_path()),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--remote-allow-origins=*",
                "--remote-debugging-port=9222",
                f"--user-data-dir={temp_dir / 'chrome'}",
                "--window-size=1440,900",
                "about:blank",
            ],
            stdout=devnull,
            stderr=devnull,
        )
    )
    cdp = CDP(browser_ws_url())
    cdp.call("Page.enable")
    cdp.call("Runtime.enable")
    cdp.call(
        "Emulation.setDeviceMetricsOverride",
        {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
    )
    return processes, cdp


def terminate_process(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> int:
    password = secrets.token_urlsafe(24)
    manifest: list[dict[str, Any]] = []
    temp_dir = Path(tempfile.mkdtemp(prefix="openbull-docs-"))
    processes: list[subprocess.Popen[Any]] = []
    try:
        processes, cdp = start_processes(temp_dir)

        cdp.navigate(f"{BASE}/")
        item = cdp.capture(OUT / "home" / "00-complete-page.png")
        manifest.append({"route": "/", "file": "home/00-complete-page.png", **item})

        cdp.navigate(f"{BASE}/setup")
        item = cdp.capture(OUT / "setup" / "00-complete-page.png")
        manifest.append({"route": "/setup", "file": "setup/00-complete-page.png", **item})

        setup_payload = json.dumps(
            {"username": USERNAME, "email": "docs@example.com", "password": password}
        )
        setup_result = cdp.evaluate(
            "fetch('/auth/setup',{method:'POST',headers:{'Content-Type':'application/json'},"
            f"body:{json.dumps(setup_payload)}}}).then(async r=>({{status:r.status,body:await r.text()}}))"
        )
        if setup_result["status"] not in (200, 403):
            raise RuntimeError(f"Documentation setup failed: HTTP {setup_result['status']}")

        cdp.navigate(f"{BASE}/login")
        item = cdp.capture(OUT / "login" / "00-complete-page.png")
        manifest.append({"route": "/login", "file": "login/00-complete-page.png", **item})

        login_payload = json.dumps({"username": USERNAME, "password": password})
        login_result = cdp.evaluate(
            "fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},"
            f"body:{json.dumps(login_payload)}}}).then(async r=>({{status:r.status,body:await r.text()}}))"
        )
        if login_result["status"] != 200:
            raise RuntimeError(f"Documentation login failed: HTTP {login_result['status']}")

        subprocess.run(
            [
                str(PYTHON),
                "documentation/tools/docs_runtime.py",
                "seed-broker",
                "--username",
                USERNAME,
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        for slug, route in ROUTES:
            if route in ("/", "/login"):
                continue
            cdp.navigate(f"{BASE}{route}")
            item = cdp.capture(OUT / slug / "00-complete-page.png")
            manifest.append({"route": route, "file": f"{slug}/00-complete-page.png", **item})
            for filename, action, expression in ACTIONS.get(slug, []):
                cdp.navigate(f"{BASE}{route}")
                affected = cdp.evaluate(expression, False)
                if not affected:
                    raise RuntimeError(f"Could not perform documented action: {action}")
                time.sleep(1)
                action_item = cdp.capture(OUT / slug / filename)
                manifest.append(
                    {
                        "route": route,
                        "action": action,
                        "file": f"{slug}/{filename}",
                        **action_item,
                    }
                )

        record = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "viewport": {"width": 1440, "height": 900, "device_scale_factor": 1},
            "database": "dedicated local documentation database",
            "broker": "sandbox-only documentation fixture; no provider contacted",
            "fixtures": [
                "one stopped Documentation NIFTY Spread lifecycle strategy",
                "one active Documentation Bull Call Spread portfolio strategy",
                "one open sandbox order",
                "one executed sandbox trade",
                "one open sandbox position",
                "one sandbox holding and fund row",
            ],
            "captures": manifest,
        }
        (OUT / "manifest.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        write_catalogue(record)
        print(f"Captured {len(manifest)} route screenshots.")
        return 0
    finally:
        for process in reversed(processes):
            terminate_process(process)
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
