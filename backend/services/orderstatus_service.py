"""
Order status service - fetches status of a specific order by orderid.
"""

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _coerce_positive_float(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if num > 0 else None


def _coerce_nonnegative_int(value: Any) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError):
        return 0
    return num if num >= 0 else 0


def _extract_fill_price(order: dict[str, Any]) -> float | None:
    for key in (
        "average_price",
        "fill_price",
        "avg_price",
        "averagePrice",
        "avgPrice",
        "averageTradedPrice",
        "traded_price",
        "tradedPrice",
    ):
        price = _coerce_positive_float(order.get(key))
        if price is not None:
            return price
    return None


def _weighted_trade_fill(
    trades: list[dict[str, Any]],
    orderid: str,
    *,
    assume_same_order: bool = False,
) -> tuple[float | None, int]:
    total_qty = 0
    total_value = 0.0
    first_price: float | None = None
    wanted = str(orderid)

    for trade in trades:
        trade_orderid = str(trade.get("orderid") or trade.get("orderId") or "") if isinstance(trade, dict) else ""
        if not assume_same_order and trade_orderid != wanted:
            continue
        if assume_same_order and trade_orderid and trade_orderid != wanted:
            continue
        price = _coerce_positive_float(
            trade.get("average_price")
            or trade.get("fill_price")
            or trade.get("traded_price")
            or trade.get("tradedPrice")
        )
        if price is None:
            continue
        first_price = first_price or price
        qty = _coerce_nonnegative_int(
            trade.get("quantity")
            or trade.get("traded_quantity")
            or trade.get("tradedQuantity")
            or trade.get("filled_quantity")
            or trade.get("filledQty")
        )
        if qty <= 0:
            continue
        total_qty += qty
        total_value += price * qty

    if total_qty > 0:
        return round(total_value / total_qty, 4), total_qty
    return first_price, 0


def _is_broker_error(response: Any) -> bool:
    return isinstance(response, dict) and (
        response.get("status") in ("error", "failed")
        or response.get("errorType")
    )


def _transformed_trades(
    mapping_module: Any,
    raw_trades: Any,
) -> list[dict[str, Any]]:
    if _is_broker_error(raw_trades):
        return []
    mapped = mapping_module.map_trade_data(trade_data=raw_trades)
    transformed = mapping_module.transform_tradebook_data(mapped)
    return transformed if isinstance(transformed, list) else []


def _tradebook_fill_for_order(
    api_module: Any,
    mapping_module: Any,
    auth_token: str,
    orderid: str,
) -> tuple[float | None, int]:
    """Best-effort executed fill lookup for brokers exposing tradebook rows."""
    if hasattr(api_module, "get_trades_by_order_id"):
        try:
            raw_trades = api_module.get_trades_by_order_id(auth_token, orderid)
            price, qty = _weighted_trade_fill(
                _transformed_trades(mapping_module, raw_trades),
                orderid,
                assume_same_order=True,
            )
            if price is not None:
                return price, qty
        except Exception:
            logger.debug("Per-order trade lookup failed for %s", orderid, exc_info=True)

    if hasattr(api_module, "get_trade_book"):
        try:
            raw_trades = api_module.get_trade_book(auth_token)
            return _weighted_trade_fill(
                _transformed_trades(mapping_module, raw_trades),
                orderid,
            )
        except Exception:
            logger.debug("Tradebook fill lookup failed for %s", orderid, exc_info=True)

    return None, 0


def _attach_tradebook_fill(
    order: dict[str, Any],
    api_module: Any,
    mapping_module: Any,
    auth_token: str,
    orderid: str,
) -> None:
    if _extract_fill_price(order) is not None:
        return
    raw_status = order.get("order_status") or order.get("status")
    status = str(raw_status or "").strip().lower()
    filled_qty = _coerce_nonnegative_int(
        order.get("filled_quantity")
        or order.get("filledQty")
        or order.get("traded_quantity")
        or order.get("tradedQuantity")
    )
    filled_statuses = {"complete", "completed", "traded", "filled", "success", "part_traded"}
    if filled_qty <= 0 and status not in filled_statuses:
        return
    fill_price, fill_qty = _tradebook_fill_for_order(api_module, mapping_module, auth_token, orderid)
    if fill_price is None:
        return
    order["average_price"] = fill_price
    order["fill_price"] = fill_price
    if fill_qty > 0 and not _coerce_nonnegative_int(order.get("filled_quantity")):
        order["filled_quantity"] = fill_qty


def get_orderstatus_with_auth(
    orderid: str, auth_token: str, broker: str, config: dict | None = None
) -> tuple[bool, dict[str, Any], int]:
    """Get status of a specific order using provided auth token."""
    try:
        api_module = importlib.import_module(f"backend.broker.{broker}.api.order_api")
        mapping_module = importlib.import_module(f"backend.broker.{broker}.mapping.order_data")
    except ImportError as error:
        logger.error("Error importing broker modules: %s", error)
        return False, {"status": "error", "message": "Broker-specific module not found"}, 404

    try:
        order_data = api_module.get_order_book(auth_token)

        if isinstance(order_data, dict) and order_data.get("status") == "error":
            return False, {"status": "error", "message": order_data.get("message", "Error fetching orders")}, 500

        mapped_data = mapping_module.map_order_data(order_data=order_data)
        transformed = mapping_module.transform_order_data(mapped_data)

        for order in transformed:
            if str(order.get("orderid")) == str(orderid):
                _attach_tradebook_fill(order, api_module, mapping_module, auth_token, str(orderid))
                return True, {"status": "success", "data": order}, 200

        return False, {"status": "error", "message": f"Order {orderid} not found"}, 404

    except Exception as e:
        logger.error("Error fetching order status: %s", e)
        return False, {"status": "error", "message": str(e)}, 500
