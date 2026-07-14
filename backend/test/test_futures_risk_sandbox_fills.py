"""Regression coverage for Futures-Risk sandbox fill-price accounting."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from backend.futures_risk import service
from backend.services import sandbox_service


class FuturesRiskSandboxFillTests(TestCase):
    def test_actual_sandbox_fill_replaces_missing_preview_quote(self):
        """A Dhan preview miss must not persist a zero entry P&L basis."""
        plan = {"entry_opt": 0.0}

        service._apply_sandbox_fill_price(plan, {"average_price": 27.5})

        self.assertEqual(plan["entry_opt"], 27.5)
        self.assertEqual(service._leg_exit_pnl("BUY", plan["entry_opt"], 32.6, 65), 331.5)

    def test_sandbox_fill_extraction_ignores_zero_price(self):
        self.assertEqual(service._extract_order_fill_price({"average_price": "39.75"}), 39.75)
        self.assertIsNone(service._extract_order_fill_price({"average_price": 0}))

    def test_market_order_response_contains_actual_sandbox_fill(self):
        """Futures-Risk must receive the fill that the simulator recorded."""
        created = SimpleNamespace(orderid="sandbox-order-1")
        filled = SimpleNamespace(status="complete", average_price=27.5)
        info = SimpleNamespace(instrument_type="OPTIDX")

        with (
            patch.object(sandbox_service, "validate_order", return_value=(True, None, info)),
            patch.object(sandbox_service.fund_manager, "compute_required_margin", return_value=0.0),
            patch.object(sandbox_service.fund_manager, "block_margin", return_value=(True, None)),
            patch.object(sandbox_service.position_manager, "get_position_snapshot", return_value=None),
            patch.object(sandbox_service.order_manager, "create_order", return_value=created),
            patch.object(sandbox_service.order_manager, "get_order", return_value=filled),
            patch.object(sandbox_service, "get_ltp_with_fallback", return_value=27.5),
            patch.object(sandbox_service, "_try_fill_order") as try_fill,
        ):
            ok, response, status = sandbox_service.place_order(1, {
                "symbol": "NIFTY14JUL2624050PE",
                "exchange": "NFO",
                "action": "BUY",
                "quantity": "65",
                "pricetype": "MARKET",
                "product": "MIS",
                "price": "0",
                "trigger_price": "0",
            })

        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(response["average_price"], 27.5)
        try_fill.assert_called_once_with(created, 27.5)


if __name__ == "__main__":
    import unittest

    unittest.main()
