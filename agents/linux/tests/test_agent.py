"""Unit tests for the Linux endpoint collector."""
import base64
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aegis_agent import (
    AgentError, _atomic_write, build_signed_event, canonical_event_bytes,
    collect_processes, require_https,
)


class LinuxAgentTests(unittest.TestCase):
    def test_requires_https_and_rejects_embedded_credentials(self):
        self.assertEqual(require_https("https://aegis.example/path/"), "https://aegis.example/path")
        for value in ("http://aegis.example", "https://user:pass@aegis.example", "https://aegis.example?q=1"):
            with self.assertRaises(AgentError):
                require_https(value)

    def test_event_signature_matches_canonical_envelope(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private = Ed25519PrivateKey.generate()
        event = build_signed_event(private, device_id=str(uuid4()), sequence=1,
            event_type="heartbeat", payload={"status":"healthy"},
            observed_at=datetime(2026, 11, 11, tzinfo=timezone.utc))
        signature = base64.b64decode(event["signature_b64"], validate=True)
        public = private.public_key()
        public.verify(signature, canonical_event_bytes(event["event"]))
        self.assertEqual(event["event"]["observed_at"], "2026-11-11T00:00:00Z")

    def test_collect_processes_is_bounded_and_omits_command_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / "123"
            proc.mkdir()
            (proc / "comm").write_text("safe-process\n")
            (proc / "status").write_text("Name:\tsafe-process\nUid:\t1000\t1000\t1000\t1000\n")
            rows = collect_processes(root)
            self.assertEqual(rows, [{"pid":123,"name":"safe-process","uid":1000}])
            self.assertNotIn("cmdline", rows[0])

    def test_atomic_write_sets_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "state" / "private.key"
            _atomic_write(target, b"secret", 0o600)
            self.assertEqual(target.read_bytes(), b"secret")
            self.assertEqual(os.stat(target).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(target.parent).st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
