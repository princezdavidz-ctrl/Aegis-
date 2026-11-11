"""macOS endpoint agent tests; run on macos-latest."""
import base64
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aegis_agent import (
    AgentError, _load_private_key, _store_private_key, build_signed_event,
    canonical_event_bytes, collect_processes, require_https,
)


class MacOSAgentTests(unittest.TestCase):
    def test_requires_https(self):
        self.assertEqual(require_https("https://aegis.example/path/"), "https://aegis.example/path")
        for value in ("http://aegis.example", "https://user:pass@aegis.example", "https://aegis.example?q=1"):
            with self.assertRaises(AgentError):
                require_https(value)

    def test_signature_is_ed25519_over_canonical_envelope(self):
        key = Ed25519PrivateKey.generate()
        signed = build_signed_event(key, device_id=str(uuid4()), sequence=1,
            event_type="heartbeat", payload={"status":"healthy"},
            observed_at=datetime(2026, 11, 11, tzinfo=timezone.utc))
        key.public_key().verify(base64.b64decode(signed["signature_b64"]), canonical_event_bytes(signed["event"]))

    def test_native_process_inventory_is_bounded_and_minimal(self):
        rows = collect_processes()
        self.assertLessEqual(len(rows), 200)
        for row in rows:
            self.assertEqual(set(row), {"pid", "name"})
            self.assertGreaterEqual(row["pid"], 0)
            self.assertNotIn(" ", row["name"])

    def test_private_key_round_trips_through_login_keychain(self):
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes_raw()
        account = "ci-" + str(uuid4())
        try:
            _store_private_key(account, raw)
            restored = _load_private_key(account)
            self.assertEqual(restored.private_bytes_raw(), raw)
        finally:
            import keyring
            try:
                keyring.get_keyring().delete_password("com.aegis.endpoint.identity", account)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
