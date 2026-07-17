"""
Option chain service - builds a strikes-around-ATM chain with live CE/PE quotes.
"""

import logging
from typing import Any

from sqlalchemy import text

from backend.services.market_data_service import _run_query
from backend.services.option_symbol_service import (
    _apply_offset,
    _fetch_available_strikes,
    _find_atm,
    _find_near_month_futures,
    _format_strike,
    _option_exchange_for,
    _parse_underlying,
    _quote_exchange_for,
)
from backend.services.quotes_service import get_multi_quotes_with_auth, get_quotes_with_auth

logger = logging.getLogger(__name__)

_QUOTE_ERROR_FIELDS = (
    "code",
    "broker",
    "broker_message",
    "requires_broker_reauth",
    "action_url",
    "retry_after_seconds",
)


def _quote_failure(prefix: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Preserve broker guidance so API clients can show the correct action."""
    result: dict[str, Any] = {
        "status": "error",
        "message": f"{prefix}: {payload.get('message', 'unknown quote error')}",
    }
    for field in _QUOTE_ERROR_FIELDS:
        if field in payload:
            result[field] = payload[field]
    return result


def _strike_labels(strikes: list[float], atm: float, count: int | None) -> list[dict]:
    """Return strikes around ATM with CE/PE labels (ITMn / ATM / OTMn)."""
    if atm not in strikes:
        return [{"strike": s, "ce_label": "", "pe_label": ""} for s in strikes]

    atm_idx = strikes.index(atm)
    if count is None:
        selected = strikes
    else:
        start = max(0, atm_idx - count)
        end = min(len(strikes), atm_idx + count + 1)
        selected = strikes[start:end]

    out = []
    for strike in selected:
        if strike == atm:
            ce_label = pe_label = "ATM"
        elif strike < atm:
            n = atm_idx - strikes.index(strike)
            ce_label, pe_label = f"ITM{n}", f"OTM{n}"
        else:
            n = strikes.index(strike) - atm_idx
            ce_label, pe_label = f"OTM{n}", f"ITM{n}"
        out.append({"strike": strike, "ce_label": ce_label, "pe_label": pe_label})
    return out


def _lookup_chain_symbols(
    base_symbol: str, expiry_ddmmmyy: str, options_exchange: str, strikes: list[float]
) -> dict[float, dict]:
    """Bulk-load CE/PE symbol details for all strikes in one DB round-trip."""
    expiry_db = f"{expiry_ddmmmyy[:2]}-{expiry_ddmmmyy[2:5]}-{expiry_ddmmmyy[5:]}".upper()

    rows = _run_query(
        "SELECT symbol, strike, instrumenttype, lotsize, tick_size FROM symtoken "
        "WHERE symbol LIKE :prefix AND expiry = :expiry AND exchange = :exch "
        "AND instrumenttype IN ('CE','PE') AND strike = ANY(:strikes)",
        {
            "prefix": f"{base_symbol}{expiry_ddmmmyy}%",
            "expiry": expiry_db,
            "exch": options_exchange.upper(),
            "strikes": strikes,
        },
    )
    by_strike: dict[float, dict] = {}
    for symbol, strike, itype, lotsize, tick_size in rows:
        slot = by_strike.setdefault(strike, {})
        slot[itype] = {"symbol": symbol, "lotsize": lotsize, "tick_size": tick_size}
    return by_strike


def get_option_chain(
    underlying: str,
    exchange: str,
    expiry_date: str | None,
    strike_count: int,
    auth_token: str,
    broker: str,
    config: dict | None = None,
) -> tuple[bool, dict[str, Any], int]:
    """Build option chain (strike_count strikes either side of ATM) with live quotes."""
    try:
        base_symbol, embedded_expiry = _parse_underlying(underlying)
        final_expiry = (expiry_date or embedded_expiry or "").upper()
        if not final_expiry:
            return False, {"status": "error", "message": "Expiry date required"}, 400

        quote_exchange = _quote_exchange_for(base_symbol, exchange)
        options_exchange = _option_exchange_for(quote_exchange)

        # Resolve the instrument that provides the ATM-pricing LTP. Indices
        # and equities quote on the spot exchange. Commodities/currencies have
        # no spot, so we auto-pick the near-month FUT unless the caller passed
        # an explicit FUT contract via ``underlying="BASE{DDMMMYY}FUT"``.
        if quote_exchange in ("NSE_INDEX", "BSE_INDEX", "NSE", "BSE"):
            pricing_symbol, pricing_exchange = base_symbol, quote_exchange
        elif embedded_expiry:
            pricing_symbol, pricing_exchange = underlying.upper(), quote_exchange
        else:
            fut = _find_near_month_futures(base_symbol, quote_exchange)
            if not fut:
                return False, {
                    "status": "error",
                    "message": f"No FUT contract found for {base_symbol} on {quote_exchange} to use as underlying",
                }, 404
            pricing_symbol, pricing_exchange = fut["symbol"], fut["exchange"]

        ok, qdata, status_code = get_quotes_with_auth(
            symbol=pricing_symbol, exchange=pricing_exchange,
            auth_token=auth_token, broker=broker, config=config,
        )
        if not ok:
            return False, _quote_failure("Failed to fetch underlying LTP", qdata), status_code

        underlying_data = qdata.get("data", {})
        underlying_ltp = underlying_data.get("ltp")
        underlying_prev_close = underlying_data.get("prev_close", underlying_data.get("close", 0))
        if underlying_ltp is None:
            return False, {"status": "error", "message": "Underlying LTP unavailable"}, 500

        strikes = _fetch_available_strikes(base_symbol, final_expiry, "CE", options_exchange)
        if not strikes:
            return False, {
                "status": "error",
                "message": f"No strikes found for {base_symbol} {final_expiry} on {options_exchange}",
            }, 404

        atm = _find_atm(float(underlying_ltp), strikes)
        labelled = _strike_labels(strikes, atm, strike_count)
        target_strikes = [item["strike"] for item in labelled]
        symbol_index = _lookup_chain_symbols(base_symbol, final_expiry, options_exchange, target_strikes)

        # Build the multi-quote request for everything that exists
        symbols_to_fetch: list[dict] = []
        for item in labelled:
            slot = symbol_index.get(item["strike"], {})
            for itype in ("CE", "PE"):
                if itype in slot:
                    symbols_to_fetch.append({"symbol": slot[itype]["symbol"], "exchange": options_exchange})

        if not symbols_to_fetch:
            return False, {"status": "error", "message": "No valid option symbols found"}, 404

        ok_q, mqdata, quote_status = get_multi_quotes_with_auth(
            symbols_list=symbols_to_fetch,
            auth_token=auth_token, broker=broker, config=config,
        )
        if not ok_q:
            # Never turn an upstream failure (especially Dhan 805/rate limit)
            # into a successful option chain containing misleading zeroes.
            return False, _quote_failure("Failed to fetch option quotes", mqdata), quote_status

        quotes_map: dict[str, dict] = {}
        usable_quotes = 0
        for q in mqdata.get("results", []):
            symbol = q.get("symbol")
            if symbol:
                quotes_map[symbol] = q
                if not q.get("error") and any(
                    key in q for key in ("ltp", "open", "high", "low", "volume", "oi", "bid", "ask")
                ):
                    usable_quotes += 1

        if not quotes_map or usable_quotes == 0:
            return False, {
                "status": "error",
                "code": "QUOTE_UNAVAILABLE",
                "broker": str(broker or "").lower(),
                "message": "No live option quotes are available yet. The page will retry automatically.",
                "action_url": "/broker/config",
            }, 503

        chain = []
        for item in labelled:
            slot = symbol_index.get(item["strike"], {})
            row = {"strike": item["strike"]}

            for itype, label_key in (("CE", "ce_label"), ("PE", "pe_label")):
                meta = slot.get(itype)
                if not meta:
                    row[itype.lower()] = None
                    continue
                q = quotes_map.get(meta["symbol"], {})
                row[itype.lower()] = {
                    "symbol": meta["symbol"],
                    "label": item[label_key],
                    "ltp": q.get("ltp", 0),
                    "open": q.get("open", 0),
                    "high": q.get("high", 0),
                    "low": q.get("low", 0),
                    "prev_close": q.get("prev_close", 0),
                    "volume": q.get("volume", 0),
                    "oi": q.get("oi", 0),
                    "bid": q.get("bid", 0),
                    "ask": q.get("ask", 0),
                    "bid_qty": q.get("bid_qty", 0),
                    "ask_qty": q.get("ask_qty", 0),
                    "lotsize": meta["lotsize"],
                    "tick_size": meta["tick_size"],
                }

            chain.append(row)

        return True, {
            "status": "success",
            "underlying": base_symbol,
            "underlying_ltp": float(underlying_ltp),
            "underlying_prev_close": float(underlying_prev_close or 0),
            "quote_symbol": pricing_symbol,
            "quote_exchange": pricing_exchange,
            "expiry_date": final_expiry,
            "atm_strike": atm,
            "chain": chain,
        }, 200

    except Exception as e:
        logger.exception("Error in get_option_chain: %s", e)
        return False, {"status": "error", "message": str(e)}, 500
