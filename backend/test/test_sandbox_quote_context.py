"""Regression tests for sandbox broker quote context."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from backend.sandbox import quote_helper


class _Result:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _Session:
    def __init__(self, rows):
        self._rows = iter(rows)

    def execute(self, _statement):
        return _Result(next(self._rows))


class SandboxQuoteContextTests(TestCase):
    def test_dhan_client_id_is_preserved_for_sandbox_quote_fallback(self):
        """A sandbox MARKET order must send Dhan's required client-id header."""
        config = SimpleNamespace(
            broker_name="dhan",
            api_key="encrypted-app-id",
            api_secret="encrypted-app-secret",
            redirect_url="http://127.0.0.1:8000/dhan/callback",
            extra_config={"client_id": "1109010608"},
        )
        auth = SimpleNamespace(broker_name="dhan", access_token="encrypted-token")
        session = _Session([config, auth, config])

        @contextmanager
        def fake_session_scope():
            yield session

        with (
            patch.object(quote_helper, "session_scope", fake_session_scope),
            patch.object(quote_helper, "decrypt_value", side_effect=lambda value: f"plain:{value}"),
        ):
            broker, token, broker_config = quote_helper._resolve_broker_for_user(7)

        self.assertEqual(broker, "dhan")
        self.assertEqual(token, "plain:encrypted-token")
        self.assertEqual(broker_config["client_id"], "1109010608")
        self.assertEqual(broker_config["api_key"], "plain:encrypted-app-id")


if __name__ == "__main__":
    import unittest

    unittest.main()
