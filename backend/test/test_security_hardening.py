"""Checks for the 2026-11 security remediation.

Each test pins one behaviour that a regression would silently undo.
Runs without a database, Redis or network.
"""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import pydantic

from backend import security
from backend.middleware_rate_limit import ORDER_ENDPOINTS, _FixedWindow, parse_limit
from backend.schemas.auth import SetupRequest
from backend.utils import client_ip as client_ip_mod
from backend.utils.plugin_loader import _installed_brokers, validate_broker_name


def _conn(peer, headers=None):
    """Minimal stand-in for a Starlette HTTPConnection."""
    return SimpleNamespace(
        client=SimpleNamespace(host=peer) if peer else None,
        headers={k.lower(): v for k, v in (headers or {}).items()},
    )


class ClientIpTrustTests(TestCase):
    """X-Forwarded-For must only be believed from a trusted peer.

    nginx uses $proxy_add_x_forwarded_for, which *appends* to a
    client-supplied XFF, so the leftmost entry is attacker-controlled.
    """

    def setUp(self):
        client_ip_mod.reset_cache()

    def tearDown(self):
        client_ip_mod.reset_cache()

    def _with_trusted(self, value):
        return patch.object(
            client_ip_mod,
            "get_settings",
            return_value=SimpleNamespace(
                trusted_proxy_ip_list=[v for v in value.split(",") if v]
            ),
        )

    def test_untrusted_peer_cannot_spoof_xff(self):
        with self._with_trusted("127.0.0.1"):
            got = client_ip_mod.client_ip(
                _conn("203.0.113.9", {"X-Forwarded-For": "10.1.2.3"})
            )
        self.assertEqual(got, "203.0.113.9", "claimed XFF must be ignored")

    def test_trusted_peer_xff_uses_rightmost_entry(self):
        # "1.2.3.4" is what the caller injected; "198.51.100.7" is what our
        # own nginx appended. The appended one must win.
        with self._with_trusted("127.0.0.1"):
            got = client_ip_mod.client_ip(
                _conn("127.0.0.1", {"X-Forwarded-For": "1.2.3.4, 198.51.100.7"})
            )
        self.assertEqual(got, "198.51.100.7")

    def test_no_trusted_proxies_ignores_headers_entirely(self):
        with self._with_trusted(""):
            got = client_ip_mod.client_ip(
                _conn("203.0.113.9", {"X-Forwarded-For": "10.1.2.3"})
            )
        self.assertEqual(got, "203.0.113.9")

    def test_garbage_header_falls_back_to_peer(self):
        with self._with_trusted("127.0.0.1"):
            got = client_ip_mod.client_ip(
                _conn("127.0.0.1", {"X-Forwarded-For": "not-an-ip, also-bad"})
            )
        self.assertEqual(got, "127.0.0.1")


class RateLimitTests(TestCase):
    def test_parse_limit_handles_configured_formats(self):
        self.assertEqual(parse_limit("50 per second", (1, 1)), (50, 1))
        self.assertEqual(parse_limit("25 per hour", (1, 1)), (25, 3600))
        # Unparseable spec must fall back, not raise.
        self.assertEqual(parse_limit("nonsense", (7, 60)), (7, 60))

    def test_fixed_window_blocks_past_the_limit(self):
        w = _FixedWindow()
        allowed = [w.allow("k", 3, 60) for _ in range(5)]
        self.assertEqual(allowed, [True, True, True, False, False])

    def test_fixed_window_is_per_key(self):
        w = _FixedWindow()
        self.assertTrue(w.allow("a", 1, 60))
        self.assertTrue(w.allow("b", 1, 60))
        self.assertFalse(w.allow("a", 1, 60))

    def test_order_endpoints_cover_every_trade_path(self):
        from backend.middleware_api_log import TRADE_ENDPOINTS

        # The tighter ORDER_RATE_LIMIT must apply to everything the trade log
        # considers an order action, or an order path could end up on the
        # looser general limit.
        self.assertEqual(set(TRADE_ENDPOINTS), set(ORDER_ENDPOINTS))


class ApiKeyLookupTests(TestCase):
    def test_lookup_is_stable_and_key_specific(self):
        a = security.generate_api_key()
        b = security.generate_api_key()
        self.assertEqual(security.api_key_lookup(a), security.api_key_lookup(a))
        self.assertNotEqual(security.api_key_lookup(a), security.api_key_lookup(b))
        self.assertEqual(len(security.api_key_lookup(a)), 64)

    def test_argon2_still_decides_validity(self):
        key = security.generate_api_key()
        stored = security.hash_api_key(key)
        self.assertTrue(security.verify_api_key(key, stored))
        self.assertFalse(security.verify_api_key(security.generate_api_key(), stored))

    def test_corrupt_hash_is_rejected_not_raised(self):
        # Previously only VerifyMismatchError was caught, so a malformed
        # stored hash surfaced as a 500 instead of an auth failure.
        self.assertFalse(security.verify_api_key("whatever", "not-a-hash"))
        self.assertFalse(security.verify_password("whatever", "$argon2id$broken"))


class FernetTests(TestCase):
    def test_roundtrip(self):
        self.assertEqual(security.decrypt_value(security.encrypt_value("x-y-z")), "x-y-z")

    def test_legacy_key_is_unchanged(self):
        """The pepper-derived key must keep its original KDF inputs.

        Every broker token already in the database was encrypted with it; a
        change to the salt or iteration count would make all of it
        undecryptable.
        """
        self.assertEqual(security._LEGACY_SALT, b"openbull_static_salt")
        self.assertEqual(security._LEGACY_ITERATIONS, 100_000)

    def test_ciphertext_written_under_legacy_key_still_decrypts(self):
        from cryptography.fernet import Fernet

        legacy = Fernet(
            security._derive_fernet_key(
                security.settings.encryption_pepper,
                security._LEGACY_SALT,
                security._LEGACY_ITERATIONS,
            )
        )
        token = legacy.encrypt(b"pre-existing-broker-token").decode()
        self.assertEqual(security.decrypt_value(token), "pre-existing-broker-token")


class CachedContextTests(TestCase):
    """The broker/API context cache must never hold plaintext secrets.

    Redis ships with no password and no TLS and persists an RDB snapshot to
    disk, so caching decrypted broker tokens put live brokerage credentials
    in cleartext outside the database.
    """

    def _row(self):
        return SimpleNamespace(
            access_token=security.encrypt_value("broker-access-token"),
            api_key=security.encrypt_value("broker-app-id"),
            api_secret=security.encrypt_value("broker-app-secret"),
            redirect_url="http://127.0.0.1:8000/dhan/callback",
            extra_config={"client_id": "1109010608"},
        )

    def test_payload_contains_no_plaintext(self):
        from backend.dependencies import _encrypted_ctx_payload

        row = self._row()
        payload = repr(_encrypted_ctx_payload("dhan", row, row))
        for secret in ("broker-access-token", "broker-app-id", "broker-app-secret"):
            self.assertNotIn(secret, payload)

    def test_roundtrip_restores_the_same_values(self):
        from backend.dependencies import _decrypt_ctx_payload, _encrypted_ctx_payload

        row = self._row()
        token, broker, config = _decrypt_ctx_payload(
            _encrypted_ctx_payload("dhan", row, row)
        )
        self.assertEqual(token, "broker-access-token")
        self.assertEqual(broker, "dhan")
        self.assertEqual(config["api_key"], "broker-app-id")
        self.assertEqual(config["api_secret"], "broker-app-secret")
        # client_id must survive — Dhan ticks do not work without it.
        self.assertEqual(config["client_id"], "1109010608")
        self.assertEqual(config["redirect_url"], row.redirect_url)

    def test_missing_broker_config_is_tolerated(self):
        from backend.dependencies import _decrypt_ctx_payload, _encrypted_ctx_payload

        row = self._row()
        token, broker, config = _decrypt_ctx_payload(
            _encrypted_ctx_payload("upstox", row, None)
        )
        self.assertEqual(token, "broker-access-token")
        self.assertEqual(config, {})

    def test_cache_keys_are_shared_between_http_and_ws_paths(self):
        from backend.dependencies import _key_api_ctx
        from backend.websocket_proxy import auth as ws_auth

        # These had drifted ("api_ctx:" vs "api_ctx:v2:"), so the two paths
        # silently kept separate entries.
        self.assertIs(ws_auth._key_api_ctx, _key_api_ctx)
        self.assertIn("v3", _key_api_ctx(1))


class PasswordPolicyTests(TestCase):
    def _make(self, password):
        return SetupRequest(username="admin", email="a@b.com", password=password)

    def test_accepts_a_reasonable_password(self):
        self.assertTrue(self._make("Str0ng-Passphrase").password)

    def test_rejects_short_password(self):
        with self.assertRaises(pydantic.ValidationError):
            self._make("Sh0rt!1")

    def test_rejects_single_character_class(self):
        with self.assertRaises(pydantic.ValidationError):
            self._make("abcdefghijklmnop")


class BrokerNameTests(TestCase):
    def test_every_installed_broker_is_accepted(self):
        installed = _installed_brokers()
        self.assertTrue(installed, "no broker plugins discovered")
        for name in installed:
            self.assertEqual(validate_broker_name(name), name)

    def test_traversal_and_unknown_names_are_rejected(self):
        for bad in ["..", "..os", "os", "backend", "upstox.api", "up/stox", "", "x" * 40]:
            with self.subTest(bad=bad), self.assertRaises(ImportError):
                validate_broker_name(bad)

    def test_rejection_is_importerror_so_callers_degrade_gracefully(self):
        # Call sites catch ImportError and return "broker module not found";
        # a ValueError would escape as a 500.
        with self.assertRaises(ImportError):
            validate_broker_name("definitely-not-a-broker")


class FormBodyRedactionTests(TestCase):
    def test_form_encoded_secrets_are_redacted(self):
        from backend.middleware_api_log import _summarise_body

        out = _summarise_body(
            b"apikey=supersecret&symbol=NIFTY&password=hunter2",
            "application/x-www-form-urlencoded",
        )
        self.assertNotIn("supersecret", out)
        self.assertNotIn("hunter2", out)
        self.assertIn("NIFTY", out)

    def test_json_redaction_still_works(self):
        from backend.middleware_api_log import _summarise_body

        out = _summarise_body(
            b'{"apikey":"supersecret","symbol":"NIFTY"}', "application/json"
        )
        self.assertNotIn("supersecret", out)
        self.assertIn("NIFTY", out)


class JwtTests(TestCase):
    def test_roundtrip_and_rejections(self):
        token = security.create_access_token({"sub": "1", "jti": "j"})
        payload = security.decode_access_token(token)
        self.assertEqual(payload["sub"], "1")
        self.assertIsNone(security.decode_access_token("garbage"))
        self.assertIsNone(security.decode_access_token(token[:-4] + "AAAA"))

    def test_alg_none_is_rejected(self):
        import base64
        import json

        def b64(raw):
            return base64.urlsafe_b64encode(raw).rstrip(b"=")

        header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        body = b64(json.dumps({"sub": "1"}).encode())
        self.assertIsNone(
            security.decode_access_token((header + b"." + body + b".").decode())
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
