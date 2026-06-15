"""
Order dispatch + broker-context + event logging shared by the Futures-Risk
service (request context) and the auto-exit engine (background thread).

All DB access here is synchronous (``backend.sandbox._db.session_scope``) so the
engine thread and the sync service helpers can share it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from backend.models.auth import BrokerAuth
from backend.models.broker_config import BrokerConfig
from backend.models.futures_risk import FrTradeEvent
from backend.sandbox._db import session_scope
from backend.security import decrypt_value

logger = logging.getLogger(__name__)


def load_broker_context_sync(user_id: int) -> dict[str, Any] | None:
    """Resolve a user's active broker auth/config for server-side calls.

    Mirrors ``dependencies.get_broker_context`` but sync + no request. Returns
    ``{"auth_token", "broker", "config"}`` or ``None`` when no active session.
    """
    try:
        with session_scope() as db:
            ba = (
                db.execute(
                    select(BrokerAuth).where(
                        BrokerAuth.user_id == user_id,
                        BrokerAuth.is_revoked == False,  # noqa: E712
                    )
                )
                .scalars()
                .first()
            )
            if ba is None:
                return None
            broker = ba.broker_name
            auth_token = decrypt_value(ba.access_token)

            bc = (
                db.execute(
                    select(BrokerConfig).where(
                        BrokerConfig.user_id == user_id,
                        BrokerConfig.broker_name == broker,
                    )
                )
                .scalar_one_or_none()
            )
            config: dict[str, Any] = {}
            if bc is not None:
                config = {
                    "api_key": decrypt_value(bc.api_key),
                    "api_secret": decrypt_value(bc.api_secret),
                    "redirect_url": bc.redirect_url,
                    "client_id": (bc.extra_config or {}).get("client_id"),
                }
            return {"auth_token": auth_token, "broker": broker, "config": config}
    except Exception:
        logger.exception("load_broker_context_sync failed for user %s", user_id)
        return None


def dispatch_order(
    mode: str,
    user_id: int,
    order_data: dict[str, Any],
    *,
    auth_token: str | None = None,
    broker: str | None = None,
    config: dict | None = None,
) -> tuple[bool, dict[str, Any], int]:
    """Place an order honouring the trade's mode.

    * ``sandbox`` → simulated engine (no broker auth needed).
    * ``live``    → broker order API via the user's auth (loaded if not passed).
    """
    if mode == "sandbox":
        from backend.services.sandbox_service import place_order as sbx_place

        return sbx_place(user_id, order_data)

    if not (auth_token and broker):
        ctx = load_broker_context_sync(user_id)
        if ctx is None:
            return False, {"status": "error", "message": "No active broker session"}, 403
        auth_token, broker, config = ctx["auth_token"], ctx["broker"], ctx["config"]

    from backend.services.order_service import place_order

    # user_id omitted so the live broker path is forced regardless of the
    # global trading-mode flag — the trade carries its own mode.
    return place_order(order_data, auth_token=auth_token, broker=broker, config=config)


def log_event(
    db,
    *,
    trade_id: int | None,
    user_id: int,
    kind: str,
    message: str,
    severity: str = "info",
    payload: dict | None = None,
) -> None:
    """Append one audit/auto-exit-log row. Caller owns the transaction."""
    db.add(
        FrTradeEvent(
            trade_id=trade_id,
            user_id=user_id,
            kind=kind,
            severity=severity,
            message=message,
            payload=payload,
        )
    )


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)
