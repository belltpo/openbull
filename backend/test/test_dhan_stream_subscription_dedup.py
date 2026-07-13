"""Regression tests for Dhan streaming subscription request de-duplication."""

from unittest import TestCase
from unittest.mock import patch

from backend.broker.dhan.streaming.dhan_adapter import DhanAdapter
from backend.websocket_proxy.base_adapter import MODE_DEPTH, MODE_LTP


class DhanStreamSubscriptionDedupTests(TestCase):
    def setUp(self):
        self.adapter = DhanAdapter("access-token", {"client_id": "1109010608"})
        self.adapter._connected = True
        # Keep the test deterministic; it verifies the pending batch without
        # creating a timer or opening a broker connection.
        self.adapter._start_batch_timer = lambda: None

    @patch("backend.broker.upstox.mapping.order_data.get_token_from_cache", return_value="12345")
    def test_repeated_symbol_at_same_mode_queues_one_dhan_request(self, _token):
        symbol = [{"symbol": "NIFTY28JUL26FUT", "exchange": "NFO"}]

        self.adapter.subscribe(symbol, MODE_LTP)
        self.adapter.subscribe(symbol, MODE_LTP)

        self.assertEqual(len(self.adapter._sub_queue), 1)
        self.assertEqual(self.adapter._sub_queue[0]["dhan_mode"], "TICKER")

    @patch("backend.broker.upstox.mapping.order_data.get_token_from_cache", return_value="12345")
    def test_pending_ticker_is_replaced_when_upgraded_to_full(self, _token):
        symbol = [{"symbol": "NIFTY28JUL26FUT", "exchange": "NFO"}]

        self.adapter.subscribe(symbol, MODE_LTP)
        self.adapter.subscribe(symbol, MODE_DEPTH)

        self.assertEqual(len(self.adapter._sub_queue), 1)
        self.assertEqual(self.adapter._sub_queue[0]["dhan_mode"], "FULL")
