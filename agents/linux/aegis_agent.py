"""Least-privilege Linux endpoint collector for the AEGIS endpoint API."""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import platform as host_platform
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

AGENT_VERSION = "0.1.0"
MAX_PROCESSES = 200
DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "aegis-agent"


class AgentError(RuntimeError):
    """Safe, user-facing agent error without secret material."""


def require_https(server_url: str) -> str:
    parsed = urllib.parse.urlparse(server_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise AgentError("server URL must be an HTTPS origin or base path without embedded credentials")
    if parsed.query or parsed.fragment:
        raise AgentError("server URL must not include a query string or fragment")
    return server_url.rstrip("/")


def canonical_event_bytes(event: dict[str, Any]) -> bytes:
    """Match the backend's sorted compact JSON canonicalization."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("utf-8")


def build_signed_event(private_key: Ed25519PrivateKey, *, device_id: str,
    sequence: int, event_type: str, payload: dict[str, Any],
    observed_at: datetime | None = None, event_id: str | None = None) -> dict[str, Any]:
    observed = observed_at or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise AgentError("event timestamp must be timezone-aware")
    observed = observed.astimezone(timezone.utc)
    timestamp = observed.isoformat().replace("+00:00", "Z")
    event = {
        "schema_version": 1,
        "device_id": device_id,
        "event_id": event_id or str(uuid4()),
        "sequence": sequence,
        "observed_at": timestamp,
        "event_type": event_type,
        "payload": payload,
    }
    signature = private_key.sign(canonical_event_bytes(event))
    return {"event": event, "signature_b64": base64.b64encode(signature).decode("ascii")}


def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temp_name = tempfile.mkstemp(prefix=".aegis-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        os.chmod(path, mode)
    except Exception:
        try:
            os.unlink(temp_name)
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


def _private_key(path: Path) -> Ed25519PrivateKey:
    try:
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise AgentError("private key permissions are too broad; expected mode 0600")
        raw = path.read_bytes()
        if len(raw) != 32:
            raise AgentError("private key file is invalid")
        return Ed25519PrivateKey.from_private_bytes(raw)
    except OSError:
        raise AgentError("private key is unavailable") from None


def _request_json(url: str, payload: dict[str, Any], *, timeout: float = 15.0) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    request = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"AEGIS-Linux-Agent/{AGENT_VERSION}",
    }, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read(65536).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Never echo the response body: it may contain sensitive diagnostics.
        if exc.code in (400, 401, 403, 404, 409, 422):
            raise AgentError(f"server rejected endpoint request (HTTP {exc.code})") from None
        raise AgentError(f"endpoint server unavailable (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise AgentError("endpoint server unavailable or returned an invalid response") from None
    if not isinstance(result, dict):
        raise AgentError("endpoint server returned an invalid response")
    return result


def enroll(server_url: str, token: str, state_dir: Path) -> str:
    server = require_https(server_url)
    if not token or len(token) > 256:
        raise AgentError("enrollment token is invalid")
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)
    key = Ed25519PrivateKey.generate()
    raw_private = key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path = state_dir / "device.key"
    _atomic_write(key_path, raw_private, 0o600)
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    release = host_platform.freedesktop_os_release() if hasattr(host_platform, "freedesktop_os_release") else {}
    payload = {
        "enrollment_token": token,
        "platform": "linux",
        "public_key_b64": base64.b64encode(public_key).decode("ascii"),
        "hostname": host_platform.node()[:255] or "linux-host",
        "agent_version": AGENT_VERSION,
    }
    result = _request_json(server + "/api/v1/endpoints/enroll", payload)
    device_id = result.get("device_id")
    if not isinstance(device_id, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", device_id
    ):
        raise AgentError("server returned an invalid device identity")
    _write_json(state_dir / "config.json", {
        "server_url": server,
        "device_id": device_id,
        "last_sequence": 0,
        "os_name": release.get("PRETTY_NAME", "Linux"),
        "architecture": host_platform.machine()[:32],
    })
    return device_id


def collect_processes(proc_root: Path = Path("/proc")) -> list[dict[str, Any]]:
    """Collect bounded process metadata; deliberately omit command-line arguments."""
    processes: list[dict[str, Any]] = []
    try:
        entries = sorted((entry for entry in proc_root.iterdir() if entry.name.isdigit()),
            key=lambda entry: int(entry.name))
    except OSError:
        return processes
    for entry in entries:
        if len(processes) >= MAX_PROCESSES:
            break
        try:
            name = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
            if not name:
                continue
            uid = None
            for line in (entry / "status").read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("Uid:"):
                    uid = int(line.split()[1])
                    break
            processes.append({"pid": int(entry.name), "name": name[:128], "uid": uid})
        except (OSError, ValueError, IndexError):
            continue
    return processes


def run_once(state_dir: Path) -> int:
    config_path = state_dir / "config.json"
    key_path = state_dir / "device.key"
    config = _read_json(config_path)
    server = require_https(str(config.get("server_url", "")))
    device_id = str(config.get("device_id", ""))
    if not device_id:
        raise AgentError("agent is not enrolled")
    key = _private_key(key_path)
    sequence = int(config.get("last_sequence", 0))

    release = host_platform.freedesktop_os_release() if hasattr(host_platform, "freedesktop_os_release") else {}
    events = [
        ("heartbeat", {
            "agent_version": AGENT_VERSION,
            "hostname": host_platform.node()[:255],
            "os_name": release.get("PRETTY_NAME", "Linux"),
            "architecture": host_platform.machine()[:32],
        }),
        ("process", {"processes": collect_processes()}),
    ]
    for event_type, payload in events:
        sequence += 1
        # Persist sequence before transmission; failures may create harmless gaps,
        # but cannot cause a retry to reuse an already accepted sequence.
        config["last_sequence"] = sequence
        _write_json(config_path, config)
        signed = build_signed_event(key, device_id=device_id, sequence=sequence,
            event_type=event_type, payload=payload)
        _request_json(server + "/api/v1/endpoints/events", signed)
    return sequence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AEGIS Linux endpoint collector")
    parser.add_argument("--state-dir", type=Path, default=Path(os.environ.get(
        "AEGIS_AGENT_STATE_DIR", str(DEFAULT_STATE_DIR))))
    commands = parser.add_subparsers(dest="command", required=True)
    enroll_parser = commands.add_parser("enroll", help="enroll this host with a one-time invitation")
    enroll_parser.add_argument("--server", required=True, help="AEGIS HTTPS base URL")
    commands.add_parser("run-once", help="collect and submit one telemetry batch")
    args = parser.parse_args(argv)
    try:
        if args.command == "enroll":
            token = getpass.getpass("One-time AEGIS enrollment token: ").strip()
            device_id = enroll(args.server, token, args.state_dir)
            print(f"AEGIS endpoint enrolled: {device_id}")
        else:
            last_sequence = run_once(args.state_dir)
            print(f"AEGIS telemetry submitted; last sequence: {last_sequence}")
        return 0
    except AgentError as exc:
        print(f"AEGIS agent: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
