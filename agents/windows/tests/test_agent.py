"""Windows-native endpoint agent unit tests; run on windows-latest."""
import base64
import os
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aegis_agent import (
    AgentError, build_signed_event, canonical_event_bytes, collect_processes,
    protect_private_key, require_https, unprotect_private_key,
)


class WindowsAgentTests(unittest.TestCase):
    def test_requires_https(self):
        self.assertEqual(require_https("https://aegis.example/path/"), "https://aegis.example/path")
        for value in ("http://aegis.example", "https://user:pass@aegis.example", "https://aegis.example?q=1"):
            with self.assertRaises(AgentError):
                require_https(value)

    def test_signature_is_ed25519_over_canonical_envelope(self):
        key = Ed25519PrivateKey.generate()
        signed = build_signed_event(key, device_id=str(uuid4()), sequence=7,
            event_type="heartbeat", payload={"status":"healthy"},
            observed_at=datetime(2026, 11, 11, tzinfo=timezone.utc))
        key.public_key().verify(base64.b64decode(signed["signature_b64"]), canonical_event_bytes(signed["event"]))

    @unittest.skipUnless(os.name == "nt", "DPAPI requires Windows")
    def test_machine_dpapi_round_trip(self):
        raw = os.urandom(32)
        self.assertEqual(unprotect_private_key(protect_private_key(raw)), raw)

    @unittest.skipUnless(os.name == "nt", "Toolhelp32 requires Windows")
    def test_native_process_inventory_is_bounded_and_minimal(self):
        rows = collect_processes()
        self.assertLessEqual(len(rows), 200)
        for row in rows:
            self.assertEqual(set(row), {"pid", "name"})
            self.assertGreaterEqual(row["pid"], 0)


if __name__ == "__main__":
    unittest.main()
