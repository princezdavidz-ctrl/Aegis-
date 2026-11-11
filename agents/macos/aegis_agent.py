"""Least-privilege macOS endpoint collector for the AEGIS endpoint API."""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import keyring
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

AGENT_VERSION = "0.1.0"
MAX_PROCESSES = 200
KEYCHAIN_SERVICE = "com.aegis.endpoint.identity"
DEFAULT_STATE_DIR = Path.home() / "Library" / "Application Support" / "AEGIS"


class AgentError(RuntimeError):
    """Safe user-facing error without secret material."""


def require_https(server_url: str) -> str:
    parsed = urllib.parse.urlparse(server_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise AgentError("server URL must be HTTPS and contain no embedded credentials")
    if parsed.query or parsed.fragment:
        raise AgentError("server URL must not include a query string or fragment")
    return server_url.rstrip("/")


def canonical_event_bytes(event: dict[str, Any]) -> bytes:
    return json.dumps(event, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("utf-8")


def build_signed_event(private_key: Ed25519PrivateKey, *, device_id: str,
    sequence: int, event_type: str, payload: dict[str, Any],
    observed_at: datetime | None = None, event_id: str | None = None) -> dict[str, Any]:
    observed = observed_at or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise AgentError("event timestamp must be timezone-aware")
    timestamp = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    event = {
        "schema_version": 1, "device_id": device_id, "event_id": event_id or str(uuid4()),
        "sequence": sequence, "observed_at": timestamp, "event_type": event_type,
        "payload": payload,
    }
    signature = private_key.sign(canonical_event_bytes(event))
    return {"event": event, "signature_b64": base64.b64encode(signature).decode("ascii")}


def _keychain():
    backend = keyring.get_keyring()
    if not backend.__class__.__module__.startswith("keyring.backends.macOS"):
        raise AgentError("secure macOS Keychain backend is unavailable; refusing file-based key storage")
    return backend


def _store_private_key(device_id: str, raw: bytes) -> None:
    try:
        _keychain().set_password(KEYCHAIN_SERVICE, device_id, base64.b64encode(raw).decode("ascii"))
    except AgentError:
        raise
    except Exception:
        raise AgentError("macOS Keychain could not store the endpoint identity") from None


def _load_private_key(device_id: str) -> Ed25519PrivateKey:
    try:
        encoded = _keychain().get_password(KEYCHAIN_SERVICE, device_id)
        if not encoded:
            raise AgentError("endpoint identity is missing from macOS Keychain")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) != 32:
            raise AgentError("stored endpoint identity is invalid")
        return Ed25519PrivateKey.from_private_bytes(raw)
    except AgentError:
        raise
    except Exception:
        raise AgentError("macOS Keychain could not unlock the endpoint identity") from None


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".aegis-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_write(path, (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise AgentError("agent state is unavailable or invalid") from None
    if not isinstance(value, dict):
        raise AgentError("agent state is invalid")
    return value


def _request_json(url: str, payload: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    request = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": f"AEGIS-macOS-Agent/{AGENT_VERSION}",
    }, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read(65536).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 403, 404, 409, 422):
            raise AgentError(f"server rejected endpoint request (HTTP {exc.code})") from None
        raise AgentError(f"endpoint server unavailable (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise AgentError("endpoint server unavailable or returned an invalid response") from None
    if not isinstance(result, dict):
        raise AgentError("endpoint server returned an invalid response")
    return result


def collect_processes() -> list[dict[str, Any]]:
    """Use the native BSD ps utility with no command-line or argument collection."""
    try:
        completed = subprocess.run(
            ["/bin/ps", "-axo", "pid=,comm="],
            check=False, capture_output=True, text=True, timeout=8,
            encoding="utf-8", errors="replace", shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise AgentError("macOS process inventory is unavailable") from None
    if completed.returncode != 0:
        raise AgentError("macOS process inventory is unavailable")
    processes: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        match = re.match(r"^\s*(\d+)\s+(.+?)\s*$", line)
        if not match:
            continue
        pid = int(match.group(1))
        executable = match.group(2).strip()
        name = Path(executable).name[:128]
        if name:
            processes.append({"pid": pid, "name": name})
        if len(processes) >= MAX_PROCESSES:
            break
    return processes


def enroll(server_url: str, token: str, state_dir: Path) -> str:
    server = require_https(server_url)
    if not token or len(token) > 256:
        raise AgentError("enrollment token is invalid")
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    payload = {
        "enrollment_token": token, "platform": "macos",
        "public_key_b64": base64.b64encode(public).decode("ascii"),
        "hostname": platform.node()[:255] or "macos-host", "agent_version": AGENT_VERSION,
    }
    result = _request_json(server + "/api/v1/endpoints/enroll", payload)
    device_id = result.get("device_id")
    if not isinstance(device_id, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", device_id
    ):
        raise AgentError("server returned an invalid device identity")
    _store_private_key(device_id, raw)
    _write_json(state_dir / "config.json", {
        "server_url": server, "device_id": device_id, "last_sequence": 0,
        "os_version": platform.mac_ver()[0], "architecture": platform.machine()[:32],
    })
    return device_id


def run_once(state_dir: Path) -> int:
    config_path = state_dir / "config.json"
    config = _read_json(config_path)
    server = require_https(str(config.get("server_url", "")))
    device_id = str(config.get("device_id", ""))
    if not device_id:
        raise AgentError("agent is not enrolled")
    key = _load_private_key(device_id)
    sequence = int(config.get("last_sequence", 0))
    events = [
        ("heartbeat", {"agent_version": AGENT_VERSION, "hostname": platform.node()[:255],
            "os_version": platform.mac_ver()[0], "architecture": platform.machine()[:32]}),
        ("process", {"processes": collect_processes()}),
    ]
    for event_type, payload in events:
        sequence += 1
        config["last_sequence"] = sequence
        _write_json(config_path, config)
        _request_json(server + "/api/v1/endpoints/events",
            build_signed_event(key, device_id=device_id, sequence=sequence,
                event_type=event_type, payload=payload))
    return sequence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AEGIS macOS endpoint collector")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    enroll_parser = commands.add_parser("enroll", help="enroll with a one-time invitation")
    enroll_parser.add_argument("--server", required=True)
    commands.add_parser("run-once", help="collect and submit one telemetry batch")
    args = parser.parse_args(argv)
    try:
        if args.command == "enroll":
            token = getpass.getpass("One-time AEGIS enrollment token: ").strip()
            print(f"AEGIS endpoint enrolled: {enroll(args.server, token, args.state_dir)}")
        else:
            print(f"AEGIS telemetry submitted; last sequence: {run_once(args.state_dir)}")
        return 0
    except AgentError as exc:
        print(f"AEGIS agent: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
