"""Regression tests for WebSocket broker authentication context."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from backend.websocket_proxy import auth


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, results):
        self._results = iter(results)

    async def execute(self, _statement):
        return next(self._results)


class _SessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False


class WebSocketBrokerContextTests(IsolatedAsyncioTestCase):
    async def test_dhan_client_id_is_passed_to_websocket_adapter(self):
        """Dhan ticks require client_id, so it must survive WS auth lookup."""
        api_key = "openbull-api-key"
        config = SimpleNamespace(
            api_key="encrypted-app-id",
            api_secret="encrypted-app-secret",
            redirect_url="http://127.0.0.1:8000/dhan/callback",
            extra_config={"client_id": "1109010608"},
        )
        session = _Session([
            _Result([SimpleNamespace(user_id=7, api_key_hash="hash")]),
            _Result([SimpleNamespace(broker_name="dhan", access_token="encrypted-token")]),
            _Result([config]),
        ])

        with (
            patch.object(auth, "cache_get_json", new=AsyncMock(return_value=None)),
            patch.object(auth, "cache_set_json", new=AsyncMock()),
            patch.object(auth, "async_session", return_value=_SessionContext(session)),
            patch.object(auth, "verify_api_key", return_value=True),
            patch.object(auth, "decrypt_value", side_effect=lambda value: f"plain:{value}"),
        ):
            user_id, token, broker, broker_config = await auth.verify_api_key_standalone(api_key)

        self.assertEqual(user_id, 7)
        self.assertEqual(token, "plain:encrypted-token")
        self.assertEqual(broker, "dhan")
        self.assertEqual(broker_config["client_id"], "1109010608")
        self.assertEqual(broker_config["api_key"], "plain:encrypted-app-id")


if __name__ == "__main__":
    import unittest

    unittest.main()
