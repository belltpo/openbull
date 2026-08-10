"""End-to-end unit coverage for Futures-Risk target/RL state transitions."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from backend.futures_risk import engine, service


class _ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _TradeDb:
    def __init__(self, trade, targets):
        self.trade = trade
        self.targets = targets

    def get(self, model, key):
        return self.trade if key == self.trade.id else None

    def execute(self, statement):
        return _ScalarRows(self.targets)

    def add(self, obj):
        return None


def _trade(**overrides):
    values = {
        "id": 91,
        "user_id": 1,
        "mode": "sandbox",
        "status": "active",
        "created_at": datetime.now(tz=timezone.utc),
        "futures_symbol": "NIFTY28JUL26FUT",
        "futures_exchange": "NFO",
        "option_symbol": "NIFTY21JUL2624000PE",
        "option_exchange": "NFO",
        "direction": -1,
        "entry_futures_price": 24241.70,
        "sl_price": 24246.70,
        "sl_basis": "initial",
        "remaining_qty": 130,
        "exit_state": "idle",
        "exit_attempt_reason": None,
        "exit_attempted_at": None,
        "exit_failure_count": 0,
        "exit_block_reason": None,
        "last_exit_order_id": None,
        "meta": {"trailing_mode": "entry_after_t1"},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _target(seq=1, price=24236.70, qty=65, status="pending"):
    return SimpleNamespace(
        seq=seq,
        trigger_price=price,
        exit_qty=qty,
        status=status,
        hit_futures_price=None,
        hit_at=None,
    )


class TriggerLifecycleTests(TestCase):
    def test_bearish_t1_marks_hit_trails_rl_to_entry_then_rl_closes_remainder(self):
        trade = _trade()
        target = _target()
        target2 = _target(seq=2, price=24231.70, qty=65)
        db = _TradeDb(trade, [target, target2])

        @contextmanager
        def fake_session_scope():
            yield db

        exit_reasons = []

        def execute_exit(*args, **kwargs):
            exit_reasons.append(kwargs["reason"])
            if kwargs.get("target_seq") == 1:
                target.status = "hit"
                target.hit_futures_price = kwargs["futures_price"]
                target.hit_at = datetime.now(tz=timezone.utc)
                exited = int(kwargs["requested_qty"])
                trade.remaining_qty -= exited
                return service.ExitExecutionResult(
                    True,
                    "T1 exited",
                    exited_qty=exited,
                    remaining_qty=trade.remaining_qty,
                )
            trade.remaining_qty = 0
            trade.status = "stopped"
            return service.ExitExecutionResult(True, "RL exited", exited_qty=65, remaining_qty=0)

        with (
            patch.object(engine, "session_scope", fake_session_scope),
            patch.object(engine, "ensure_symbols_streaming"),
            patch.object(engine, "load_broker_context_sync", return_value=None),
            patch.object(engine, "_futures_price", side_effect=[24236.70, 24241.70]),
            patch.object(engine.fr_service, "prepare_automatic_exit", return_value=True),
            patch.object(engine.fr_service, "execute_trade_exit", side_effect=execute_exit),
            patch.object(engine.fr_service, "_bool_cfg", return_value=True),
        ):
            engine._process_trade(trade.id, {})
            self.assertEqual(target.status, "hit")
            self.assertEqual(trade.sl_price, trade.entry_futures_price)
            self.assertEqual(trade.sl_basis, "entry")
            self.assertEqual(trade.remaining_qty, 65)

            engine._process_trade(trade.id, {})

        self.assertEqual(exit_reasons, ["t1", "sl"])
        self.assertEqual(trade.status, "stopped")
        self.assertEqual(trade.remaining_qty, 0)

    def test_crossed_target_remains_latched_when_price_moves_away_during_retry(self):
        trade = _trade(
            exit_state="retry_wait",
            exit_attempt_reason="t1",
            exit_attempted_at=datetime.now(tz=timezone.utc) - timedelta(seconds=30),
            exit_failure_count=1,
        )
        db = _TradeDb(
            trade,
            [_target(), _target(seq=2, price=24231.70, qty=65)],
        )

        @contextmanager
        def fake_session_scope():
            yield db

        with (
            patch.object(engine, "session_scope", fake_session_scope),
            patch.object(engine, "ensure_symbols_streaming"),
            patch.object(engine, "load_broker_context_sync", return_value=None),
            # Bearish T1 is 24236.70. This price has rebounded above it but is
            # still below the 24246.70 risk limit.
            patch.object(engine, "_futures_price", return_value=24238.00),
            patch.object(engine.fr_service, "prepare_automatic_exit", return_value=True),
            patch.object(
                engine.fr_service,
                "execute_trade_exit",
                return_value=service.ExitExecutionResult(
                    True,
                    "reconciled",
                    remaining_qty=65,
                    reconciled=True,
                ),
            ) as execute_exit,
            patch.object(engine.fr_service, "_bool_cfg", return_value=True),
        ):
            engine._process_trade(trade.id, {})

        self.assertEqual(execute_exit.call_args.kwargs["reason"], "t1")
        self.assertEqual(execute_exit.call_args.kwargs["target_seq"], 1)

    def test_rl_supersedes_target_retry_wait_in_sandbox(self):
        trade = _trade(
            exit_state="retry_wait",
            exit_attempt_reason="t1",
            exit_attempted_at=datetime.now(tz=timezone.utc),
            exit_failure_count=3,
            exit_block_reason="T1 order was rejected",
        )
        db = _TradeDb(trade, [_target()])

        @contextmanager
        def fake_session_scope():
            yield db

        with patch.object(service, "session_scope", fake_session_scope):
            ready = service.prepare_automatic_exit(trade.id, reason="sl", ctx=None)

        self.assertTrue(ready)
        self.assertEqual(trade.exit_state, "idle")
        self.assertEqual(trade.exit_failure_count, 0)
        self.assertIsNone(trade.exit_block_reason)

    def test_exhausted_target_stays_latched_but_later_rl_can_supersede_it(self):
        trade = _trade(
            exit_state="retry_wait",
            exit_attempt_reason="t1",
            exit_attempted_at=datetime.now(tz=timezone.utc) - timedelta(seconds=30),
            exit_failure_count=3,
            exit_block_reason="T1 order was rejected",
        )
        db = _TradeDb(trade, [_target(), _target(seq=2, price=24231.70)])

        @contextmanager
        def fake_session_scope():
            yield db

        with (
            patch.object(service, "session_scope", fake_session_scope),
            patch.object(service, "get_config_value", side_effect=lambda key, default=None: "3" if key == "exit_retry_max_attempts" else "10"),
        ):
            self.assertFalse(service.prepare_automatic_exit(trade.id, reason="t1", ctx=None))
            self.assertEqual(trade.exit_state, "retry_exhausted")
            self.assertTrue(service.prepare_automatic_exit(trade.id, reason="sl", ctx=None))

        self.assertEqual(trade.exit_state, "idle")
        self.assertEqual(trade.exit_failure_count, 0)


class FreshFuturesPriceTests(TestCase):
    def test_stale_cache_uses_broker_fallback_and_refreshes_shared_cache(self):
        cache = Mock()
        cache.get_all.return_value = {
            "last_update": 1.0,
            "ltp": {"value": 24000.0},
        }
        ctx = {"auth_token": "token", "broker": "dhan", "config": {}}
        with (
            patch.object(engine, "get_market_data_cache", return_value=cache),
            patch.object(engine.fr_service, "get_config_value", return_value="5"),
            patch.object(
                engine,
                "get_quotes_with_auth",
                return_value=(True, {"data": {"ltp": 24236.70}}, 200),
            ) as quote,
            patch.object(engine, "process_market_data") as remember,
        ):
            value = engine._futures_price("NIFTY28JUL26FUT", "NFO", ctx)

        self.assertEqual(value, 24236.70)
        quote.assert_called_once()
        remember.assert_called_once()

    def test_fresh_cache_does_not_call_broker(self):
        cache = Mock()
        cache.get_all.return_value = {
            "last_update": datetime.now(tz=timezone.utc).timestamp(),
            "ltp": {"value": 24236.70},
        }
        with (
            patch.object(engine, "get_market_data_cache", return_value=cache),
            patch.object(engine.fr_service, "get_config_value", return_value="5"),
            patch.object(engine, "get_quotes_with_auth") as quote,
        ):
            value = engine._futures_price("NIFTY28JUL26FUT", "NFO", None)

        self.assertEqual(value, 24236.70)
        quote.assert_not_called()


if __name__ == "__main__":
    import unittest

    unittest.main()
