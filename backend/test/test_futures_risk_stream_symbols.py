"""Tests for the quick-order live-stream contract list."""

from unittest import TestCase

from backend.api.futures_risk import _stream_symbols


class FuturesRiskStreamSymbolsTests(TestCase):
    def test_preserves_futures_option_order_and_removes_duplicates(self):
        self.assertEqual(
            _stream_symbols([
                {"symbol": "NIFTY28JUL26FUT", "exchange": "NFO"},
                {"symbol": "NIFTY28JUL2624500CE", "exchange": "NFO"},
                {"symbol": "NIFTY28JUL2624500PE", "exchange": "NFO"},
                {"symbol": "NIFTY28JUL2624500CE", "exchange": "NFO"},
            ]),
            [
                {"symbol": "NIFTY28JUL26FUT", "exchange": "NFO"},
                {"symbol": "NIFTY28JUL2624500CE", "exchange": "NFO"},
                {"symbol": "NIFTY28JUL2624500PE", "exchange": "NFO"},
            ],
        )
