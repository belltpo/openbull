import json
import importlib
import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_broker_plugins: dict = {}


def load_all_plugins() -> dict:
    global _broker_plugins
    broker_dir = Path(__file__).parent.parent / "broker"
    for plugin_path in broker_dir.glob("*/plugin.json"):
        broker_name = plugin_path.parent.name
        try:
            with open(plugin_path, encoding="utf-8") as f:
                data = json.load(f)
            _broker_plugins[broker_name] = data
            logger.info("Loaded broker plugin: %s", broker_name)
        except Exception as e:
            logger.error("Failed to load plugin %s: %s", broker_name, e)
    return _broker_plugins


def get_plugin_info(broker_name: str) -> dict | None:
    return _broker_plugins.get(broker_name)


def get_all_plugins() -> dict:
    return _broker_plugins


_NAME_RE = re.compile(r"^[a-z0-9_]{1,32}$")
_ALLOWED_MODULE_TYPES = frozenset(
    {"auth_api", "order_api", "funds", "data", "margin_api", "mapping"}
)


@lru_cache(maxsize=1)
def _installed_brokers() -> frozenset[str]:
    """Broker package names shipped on disk. Independent of load order, so
    this works even if called before :func:`load_all_plugins`."""
    broker_dir = Path(__file__).parent.parent / "broker"
    return frozenset(
        p.parent.name for p in broker_dir.glob("*/plugin.json")
    )


def validate_broker_name(broker_name: str) -> str:
    """Reject anything that is not a plain, known broker identifier.

    Broker names reach ``importlib.import_module`` interpolated into
    ``backend.broker.{name}.api.{type}`` from database rows and request
    payloads. The fixed prefix and suffix make traversal hard rather than
    impossible, so constrain the name to a plain identifier and to a broker
    package that actually exists.

    The allow-list is the set of ``backend/broker/*/plugin.json`` directories
    on disk, *not* the ``VALID_BROKERS`` setting: that setting defaults to
    "upstox,zerodha" while five brokers ship (angel, dhan, fyers, upstox,
    zerodha), so gating on it would break the others. It is a UI-facing list,
    not a security boundary.

    ``ImportError`` is raised rather than ``ValueError`` deliberately: every
    existing call site already wraps its ``importlib.import_module`` in
    ``except ImportError`` and degrades to "broker module not found", so a
    rejected name follows exactly the same path it would have taken when the
    module genuinely did not exist — no new 500s.
    """
    name = (broker_name or "").strip().lower()
    if not _NAME_RE.match(name):
        raise ImportError(f"Invalid broker name: {broker_name!r}")
    if name not in _installed_brokers():
        raise ImportError(f"Unknown broker: {name}")
    return name


def get_broker_module(broker_name: str, module_type: str):
    """Dynamically import a broker sub-module.
    module_type: 'auth_api', 'order_api', 'funds', 'data'
    """
    safe_broker = validate_broker_name(broker_name)
    if module_type not in _ALLOWED_MODULE_TYPES:
        raise ImportError(f"Invalid broker module type: {module_type!r}")
    module_path = f"backend.broker.{safe_broker}.api.{module_type}"
    return importlib.import_module(module_path)
