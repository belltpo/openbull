"""Regression coverage for independent multi-symbol Futures-Risk updates."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from backend.api.futures_risk import _calculate_session_mtm
from backend.futures_risk import engine


class FuturesRiskMultiSymbolTests(TestCase):
    def test_mtm_uses_each_option_contract_and_side_independently(self):
        trades = [
            {
                "underlying": "NIFTY",
                "status": "active",
                "option_symbol": "NIFTY28JUL2624500CE",
                "option_exchange": "NFO",
                "side": "BUY",
                "entry_option_price": 100.0,
                "pnl_qty": 65,
                "remaining_qty": 65,
                "realized_pnl": 25.0,
            },
            {
                "underlying": "BANKNIFTY",
                "status": "active",
                "option_symbol": "BANKNIFTY28JUL2655900PE",
                "option_exchange": "NFO",
                "side": "SELL",
                "entry_option_price": 200.0,
                "pnl_qty": 15,
                "remaining_qty": 15,
                "realized_pnl": 10.0,
            },
        ]
        result = _calculate_session_mtm(
            trades,
            {
                ("NIFTY28JUL2624500CE", "NFO"): 104.0,
                ("BANKNIFTY28JUL2655900PE", "NFO"): 190.0,
            },
        )

        self.assertEqual(result["active_count"], 2)
        self.assertEqual(result["booked"], 35.0)
        self.assertEqual(result["open"], 410.0)  # (4*65) + ((200-190)*15)
        self.assertEqual(result["total"], 445.0)

    def test_missing_quote_is_not_treated_as_zero_premium(self):
        result = _calculate_session_mtm(
            [{
                "status": "active",
                "option_symbol": "NIFTY28JUL2624500CE",
                "option_exchange": "NFO",
                "side": "BUY",
                "entry_option_price": 100.0,
                "pnl_qty": 65,
                "remaining_qty": 65,
                "realized_pnl": 12.0,
            }],
            {("NIFTY28JUL2624500CE", "NFO"): 0.0},
        )

        self.assertEqual(result["open"], 0.0)
        self.assertEqual(result["total"], 12.0)

    def test_trade_streaming_keeps_futures_and_option_legs(self):
        trade = SimpleNamespace(
            user_id=1,
            futures_symbol="BANKNIFTY28JUL26FUT",
            futures_exchange="NFO",
            option_symbol="BANKNIFTY28JUL2655900CE",
            option_exchange="NFO",
        )
        calls: list[tuple[str, str]] = []

        with patch.object(engine, "ensure_streaming", side_effect=lambda symbol, exchange: calls.append((symbol, exchange))):
            engine.ensure_symbols_streaming([
                {"symbol": trade.futures_symbol, "exchange": trade.futures_exchange},
                {"symbol": trade.option_symbol, "exchange": trade.option_exchange},
                {"symbol": trade.option_symbol, "exchange": trade.option_exchange},
            ])

        self.assertEqual(calls, [
            ("BANKNIFTY28JUL26FUT", "NFO"),
            ("BANKNIFTY28JUL2655900CE", "NFO"),
        ])


if __name__ == "__main__":
    import unittest

    unittest.main()
