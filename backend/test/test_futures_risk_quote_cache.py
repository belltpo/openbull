"""Regression tests for Futures-Risk quote-preview broker throttling."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import patch

from backend.api import futures_risk as api


class FuturesRiskQuoteCacheTests(TestCase):
    def setUp(self):
        with api._quote_cache_lock:
            api._recent_quotes.clear()

    def test_simultaneous_preview_cache_miss_makes_one_broker_request(self):
        """Concurrent quick panels must share the first Dhan quote request."""
        calls = 0
        calls_lock = threading.Lock()
        instruments = [
            {"symbol": "BANKNIFTY28JUL26FUT", "exchange": "NFO"},
            {"symbol": "BANKNIFTY28JUL2655900CE", "exchange": "NFO"},
        ]

        def broker_quotes(*, symbols_list, auth_token, broker, config):
            nonlocal calls
            with calls_lock:
                calls += 1
            # Keep the first request in flight until every caller has reached
            # the cache-miss path.
            time.sleep(0.05)
            return True, {
                "results": [
                    {"symbol": item["symbol"], "exchange": item["exchange"], "data": {"last_price": 100.0}}
                    for item in symbols_list
                ]
            }, 200

        with (
            patch.object(api, "_fresh_cached_quote", return_value=None),
            patch("backend.services.quotes_service.get_multi_quotes_with_auth", side_effect=broker_quotes),
        ):
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(
                    lambda _: api._quote_payloads(instruments, "token", "dhan", {"client_id": "123"}),
                    range(4),
                ))

        self.assertEqual(calls, 1)
        self.assertTrue(all(payload[("BANKNIFTY28JUL26FUT", "NFO")]["ltp"] == 100.0 for payload in results))


if __name__ == "__main__":
    import unittest

    unittest.main()
