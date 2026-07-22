"""Regression coverage for duplicate-exit and broker reconciliation safety."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from backend.futures_risk import reconciliation, service
from backend.services.positions_service import _broker_error_message


def _trade(**overrides):
    values = {
        "id": 24,
        "user_id": 1,
        "mode": "live",
        "status": "active",
        "side": "BUY",
        "option_symbol": "NIFTY21JUL2624000CE",
        "option_exchange": "NFO",
        "product": "MIS",
        "remaining_qty": 65,
        "entry_option_price": 190.75,
        "exit_attempt_id": "attempt-1",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class BrokerPositionParsingTests(TestCase):
    def test_external_partial_close_reduces_but_never_increases_recorded_qty(self):
        reduced = reconciliation.decide_position_reconciliation(195, "BUY", 65)
        oversized = reconciliation.decide_position_reconciliation(65, "BUY", 195)
        self.assertEqual((reduced.action, reduced.broker_quantity), ("adjusted", 65))
        self.assertEqual(oversized.action, "blocked")

    def test_opposite_broker_direction_is_blocked(self):
        decision = reconciliation.decide_position_reconciliation(65, "BUY", -65)
        self.assertEqual(decision.action, "blocked")
        self.assertIn("direction", decision.message or "")

    def test_dhan_exact_position_is_signed_and_strictly_matched(self):
        rows = [{
            "tradingSymbol": "NIFTY21JUL2624000CE",
            "exchangeSegment": "NSE_FNO",
            "productType": "INTRADAY",
            "netQty": "65",
            "realizedProfit": "12.5",
            "unrealizedProfit": "3.5",
        }]
        with patch(
            "backend.broker.upstox.mapping.order_data.get_brsymbol_from_cache",
            return_value="NIFTY21JUL2624000CE",
        ):
            snapshot = reconciliation.dhan_position_from_rows(
                rows,
                symbol="NIFTY21JUL2624000CE",
                exchange="NFO",
                product="MIS",
            )
        self.assertTrue(snapshot.ok)
        self.assertEqual(snapshot.quantity, 65)
        self.assertEqual(snapshot.broker_pnl, 16.0)

    def test_valid_empty_dhan_positions_is_confirmed_zero(self):
        with patch(
            "backend.broker.upstox.mapping.order_data.get_brsymbol_from_cache",
            return_value="NIFTY21JUL2624000CE",
        ):
            snapshot = reconciliation.dhan_position_from_rows(
                [], symbol="NIFTY21JUL2624000CE", exchange="NFO", product="MIS"
            )
        self.assertTrue(snapshot.ok)
        self.assertEqual(snapshot.quantity, 0)

    def test_auth_error_envelope_is_never_treated_as_empty_positions(self):
        message = _broker_error_message({
            "status": "error",
            "errorType": "InvalidToken",
            "errorMessage": "Client ID or token invalid",
        })
        self.assertEqual(message, "Client ID or token invalid")

    def test_dhan_auth_error_snapshot_fails_closed(self):
        ctx = {"broker": "dhan", "auth_token": "expired-token", "config": {}}
        reconciliation.invalidate_position_cache("dhan", "expired-token")
        with patch(
            "backend.broker.dhan.api.order_api.get_positions",
            return_value={
                "status": "error",
                "errorType": "InvalidToken",
                "errorMessage": "Client ID or token invalid",
            },
        ):
            snapshot = reconciliation.get_position_snapshot(_trade(), ctx, force=True)
        self.assertTrue(snapshot.supported)
        self.assertFalse(snapshot.ok)
        self.assertIsNone(snapshot.quantity)
        self.assertIn("token invalid", snapshot.message or "")


class ExitCoordinatorTests(TestCase):
    def test_confirmed_external_close_never_dispatches_another_order(self):
        trade = _trade()
        zero = reconciliation.PositionSnapshot(True, True, quantity=0)
        with (
            patch.object(service, "_claim_exit_attempt", return_value=(trade, "attempt-1")),
            patch.object(service, "get_position_snapshot", return_value=zero),
            patch.object(service, "_apply_position_snapshot", return_value=("closed", 0, None)),
            patch.object(service, "dispatch_order") as dispatch,
        ):
            result = service.execute_trade_exit(
                24,
                user_id=1,
                requested_qty=65,
                reason="manual",
                ctx={"broker": "dhan", "auth_token": "token", "config": {}},
            )
        self.assertTrue(result.ok)
        self.assertTrue(result.reconciled)
        self.assertEqual(result.remaining_qty, 0)
        dispatch.assert_not_called()

    def test_one_rejection_opens_circuit_breaker_without_retry(self):
        trade = _trade()
        unsupported = reconciliation.PositionSnapshot(False, True)
        db = SimpleNamespace(get=Mock(return_value=trade))

        @contextmanager
        def fake_session_scope():
            yield db

        with (
            patch.object(service, "_claim_exit_attempt", return_value=(trade, "attempt-1")),
            patch.object(service, "get_position_snapshot", return_value=unsupported),
            patch.object(service, "session_scope", side_effect=fake_session_scope),
            patch.object(
                service,
                "dispatch_order",
                return_value=(False, {"message": "Broker order was rejected"}, 409),
            ) as dispatch,
            patch.object(service, "_set_exit_blocked") as block,
        ):
            result = service.execute_trade_exit(
                24,
                user_id=None,
                requested_qty=65,
                reason="sl",
                ctx={"broker": "test", "auth_token": "token", "config": {}},
                futures_price=24171.0,
            )
        self.assertFalse(result.ok)
        self.assertTrue(result.blocked)
        dispatch.assert_called_once()
        block.assert_called_once()


if __name__ == "__main__":
    import unittest

    unittest.main()
