"""Tests for pooled WebSocket broker subscriptions."""

from unittest import TestCase

from backend.websocket_proxy import server


class WebSocketSubscriptionPoolTests(TestCase):
    def setUp(self):
        self.original = server._subscription_index
        server._subscription_index = {}

    def tearDown(self):
        server._subscription_index = self.original

    def test_duplicate_client_symbols_share_one_upstream_subscription(self):
        server._subscription_index[("NIFTY28JUL26FUT", "NFO", 1)] = {"client-a", "client-b"}
        self.assertEqual(
            server._desired_upstream_subscriptions(),
            {("NIFTY28JUL26FUT", "NFO"): 1},
        )

    def test_highest_requested_mode_wins_for_shared_symbol(self):
        server._subscription_index[("CRUDEOIL18MAY26FUT", "MCX", 1)] = {"client-a"}
        server._subscription_index[("CRUDEOIL18MAY26FUT", "MCX", 3)] = {"client-b"}
        self.assertEqual(
            server._desired_upstream_subscriptions(),
            {("CRUDEOIL18MAY26FUT", "MCX"): 3},
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
