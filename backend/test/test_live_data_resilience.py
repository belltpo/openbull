"""Regression tests for the production live-data failure modes."""

import asyncio
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.broker.dhan.streaming.dhan_adapter import DhanAdapter
from backend.services import option_chain_service, quotes_service, symbol_service
from backend.utils import redis_client


class QuoteGatewayTests(unittest.TestCase):
    def setUp(self):
        with quotes_service._COOLDOWN_LOCK:
            quotes_service._COOLDOWNS.clear()
        with quotes_service._QUOTE_LOCK:
            quotes_service._QUOTE_CACHE.clear()
            quotes_service._QUOTE_INFLIGHT.clear()

    def test_single_quote_uses_multi_quote_endpoint_only(self):
        module = SimpleNamespace(
            get_multi_quotes=Mock(return_value=[{
                "symbol": "NIFTY", "exchange": "NSE_INDEX",
                "data": {"ltp": 24500.5, "volume": 42},
            }]),
            get_quotes=Mock(side_effect=AssertionError("single endpoint must not be called")),
        )
        with patch.object(quotes_service.importlib, "import_module", return_value=module):
            ok, response, status = quotes_service.get_quotes_with_auth(
                "NIFTY", "NSE_INDEX", "token", "dhan", {"client_id": "1"},
            )
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(response["data"]["ltp"], 24500.5)
        module.get_multi_quotes.assert_called_once()
        module.get_quotes.assert_not_called()

    def test_simultaneous_identical_batches_share_one_upstream_call(self):
        entered = threading.Event()
        release = threading.Event()
        calls = 0

        def get_multi(symbols, _token, _config):
            nonlocal calls
            calls += 1
            entered.set()
            release.wait(2)
            return [{"symbol": "NIFTY", "exchange": "NSE_INDEX", "data": {"ltp": 10}}]

        module = SimpleNamespace(get_multi_quotes=get_multi)
        results = []
        with patch.object(quotes_service.importlib, "import_module", return_value=module):
            first = threading.Thread(target=lambda: results.append(quotes_service.get_multi_quotes_with_auth(
                [{"symbol": "NIFTY", "exchange": "NSE_INDEX"}], "token", "dhan", {"client_id": "1"},
            )))
            second = threading.Thread(target=lambda: results.append(quotes_service.get_multi_quotes_with_auth(
                [{"symbol": "NIFTY", "exchange": "NSE_INDEX"}], "token", "dhan", {"client_id": "1"},
            )))
            first.start()
            self.assertTrue(entered.wait(1))
            second.start()
            time.sleep(0.05)
            release.set()
            first.join(2)
            second.join(2)
        self.assertEqual(calls, 1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result[0] for result in results))

    def test_dhan_805_returns_structured_relogin_action(self):
        module = SimpleNamespace(get_multi_quotes=Mock(side_effect=Exception("Dhan error 805")))
        with patch.object(quotes_service.importlib, "import_module", return_value=module):
            ok, response, status = quotes_service.get_multi_quotes_with_auth(
                [{"symbol": "NIFTY", "exchange": "NSE_INDEX"}], "other-token", "dhan", {"client_id": "2"},
            )
        self.assertFalse(ok)
        self.assertEqual(status, 429)
        self.assertEqual(response["code"], "BROKER_RATE_LIMIT")
        self.assertTrue(response["requires_broker_reauth"])
        self.assertEqual(response["action_url"], "/broker/config")


class DhanReconnectTests(unittest.TestCase):
    def _adapter(self) -> DhanAdapter:
        adapter = DhanAdapter("token", {"client_id": "1"})
        adapter._running = True
        adapter._connected = True
        adapter._set_cache_connection = Mock()
        return adapter

    def test_closed_subscribe_socket_forces_reconnect_and_keeps_demand(self):
        adapter = self._adapter()
        adapter._subs[("2", "123")] = (1, "NIFTY", "NSE_INDEX")
        ws = Mock()
        ws.sock = SimpleNamespace(connected=False)
        adapter._ws = ws

        with self.assertRaises(ConnectionError):
            adapter._send_subscribe([{"ExchangeSegment": "2", "SecurityId": "123"}], "TICKER")
        self.assertFalse(adapter._connected)
        ws.close.assert_called_once()
        self.assertIn(("2", "123"), adapter._subs)


class RedisLoopOwnershipTests(unittest.TestCase):
    def test_each_event_loop_gets_its_own_async_client(self):
        made = []

        def factory(*_args, **_kwargs):
            client = object()
            made.append(client)
            return client

        async def resolve():
            return redis_client.get_redis()

        with patch.object(redis_client.redis, "from_url", side_effect=factory):
            first = asyncio.run(resolve())
            second = asyncio.run(resolve())
        self.assertIsNot(first, second)
        self.assertEqual(len(made), 2)


class SymbolDiscoveryTests(unittest.TestCase):
    def test_index_underlyings_are_not_hidden_by_company_name_grouping(self):
        with patch("backend.services.market_data_service._run_query", return_value=[
            ("BANKNIFTY", "Nifty Bank"), ("NIFTY", "Nifty 50"),
        ]):
            rows = symbol_service.get_option_underlyings("NFO")
        self.assertEqual([row["symbol"] for row in rows], ["BANKNIFTY", "NIFTY"])


class OptionChainQuoteFailureTests(unittest.TestCase):
    def _common_patches(self):
        return (
            patch.object(option_chain_service, "_fetch_available_strikes", return_value=[24000.0]),
            patch.object(option_chain_service, "_lookup_chain_symbols", return_value={
                24000.0: {
                    "CE": {"symbol": "NIFTY28JUL2624000CE", "lotsize": 65, "tick_size": 0.05},
                    "PE": {"symbol": "NIFTY28JUL2624000PE", "lotsize": 65, "tick_size": 0.05},
                },
            }),
        )

    def test_underlying_rate_limit_keeps_structured_relogin_fields(self):
        rate_issue = {
            "status": "error", "code": "BROKER_RATE_LIMIT", "broker": "dhan",
            "message": "Dhan data rate limit reached.", "requires_broker_reauth": True,
            "action_url": "/broker/config", "retry_after_seconds": 90,
        }
        with patch.object(option_chain_service, "get_quotes_with_auth", return_value=(False, rate_issue, 429)):
            ok, response, status = option_chain_service.get_option_chain(
                "NIFTY", "NFO", "28JUL26", 5, "token", "dhan", {"client_id": "1"},
            )
        self.assertFalse(ok)
        self.assertEqual(status, 429)
        self.assertEqual(response["code"], "BROKER_RATE_LIMIT")
        self.assertTrue(response["requires_broker_reauth"])
        self.assertEqual(response["action_url"], "/broker/config")

    def test_option_batch_rate_limit_is_not_returned_as_zero_chain(self):
        rate_issue = {
            "status": "error", "code": "BROKER_RATE_LIMIT", "broker": "dhan",
            "message": "Dhan data rate limit reached.", "requires_broker_reauth": True,
            "action_url": "/broker/config", "retry_after_seconds": 90,
        }
        strike_patch, symbol_patch = self._common_patches()
        with (
            patch.object(option_chain_service, "get_quotes_with_auth", return_value=(
                True, {"status": "success", "data": {"ltp": 24010.0, "prev_close": 23900.0}}, 200,
            )),
            strike_patch,
            symbol_patch,
            patch.object(option_chain_service, "get_multi_quotes_with_auth", return_value=(False, rate_issue, 429)),
        ):
            ok, response, status = option_chain_service.get_option_chain(
                "NIFTY", "NFO", "28JUL26", 5, "token", "dhan", {"client_id": "1"},
            )
        self.assertFalse(ok)
        self.assertEqual(status, 429)
        self.assertEqual(response["code"], "BROKER_RATE_LIMIT")
        self.assertNotIn("chain", response)

    def test_empty_option_batch_is_retryable_error_not_zero_chain(self):
        strike_patch, symbol_patch = self._common_patches()
        with (
            patch.object(option_chain_service, "get_quotes_with_auth", return_value=(
                True, {"status": "success", "data": {"ltp": 24010.0, "prev_close": 23900.0}}, 200,
            )),
            strike_patch,
            symbol_patch,
            patch.object(option_chain_service, "get_multi_quotes_with_auth", return_value=(
                True, {"status": "success", "results": []}, 200,
            )),
        ):
            ok, response, status = option_chain_service.get_option_chain(
                "NIFTY", "NFO", "28JUL26", 5, "token", "dhan", {"client_id": "1"},
            )
        self.assertFalse(ok)
        self.assertEqual(status, 503)
        self.assertEqual(response["code"], "QUOTE_UNAVAILABLE")
        self.assertNotIn("chain", response)

    def test_all_error_option_rows_are_not_rendered_as_zero_chain(self):
        strike_patch, symbol_patch = self._common_patches()
        with (
            patch.object(option_chain_service, "get_quotes_with_auth", return_value=(
                True, {"status": "success", "data": {"ltp": 24010.0, "prev_close": 23900.0}}, 200,
            )),
            strike_patch,
            symbol_patch,
            patch.object(option_chain_service, "get_multi_quotes_with_auth", return_value=(
                True, {"status": "success", "results": [
                    {"symbol": "NIFTY28JUL2624000CE", "exchange": "NFO", "error": "No quote data"},
                    {"symbol": "NIFTY28JUL2624000PE", "exchange": "NFO", "error": "No quote data"},
                ]}, 200,
            )),
        ):
            ok, response, status = option_chain_service.get_option_chain(
                "NIFTY", "NFO", "28JUL26", 5, "token", "dhan", {"client_id": "1"},
            )
        self.assertFalse(ok)
        self.assertEqual(status, 503)
        self.assertEqual(response["code"], "QUOTE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
