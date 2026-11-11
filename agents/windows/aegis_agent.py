"""Least-privilege Windows endpoint collector for the AEGIS endpoint API."""
from __future__ import annotations

import argparse
import base64
import ctypes
import getpass
import json
import os
import platform
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

AGENT_VERSION = "0.1.0"
MAX_PROCESSES = 200
CRYPTPROTECT_LOCAL_MACHINE = 0x4
CRYPTPROTECT_UI_FORBIDDEN = 0x1
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
DEFAULT_STATE_DIR = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "AEGIS"


class AgentError(RuntimeError):
    """Safe user-facing error without secret material."""


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


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


def _blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect_private_key(raw: bytes) -> bytes:
    """Protect key with machine-scope DPAPI; state directory ACL limits readers."""
    if os.name != "nt":
        raise AgentError("Windows DPAPI is available only on Windows")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    source, keepalive = _blob(raw)
    destination = DATA_BLOB()
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    if not crypt32.CryptProtectData(ctypes.byref(source), "AEGIS endpoint identity",
        None, None, None, CRYPTPROTECT_LOCAL_MACHINE | CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(destination)):
        raise AgentError("Windows DPAPI could not protect the endpoint key")
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(destination.pbData)
        del keepalive


def unprotect_private_key(protected: bytes) -> bytes:
    if os.name != "nt":
        raise AgentError("Windows DPAPI is available only on Windows")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    source, keepalive = _blob(protected)
    destination = DATA_BLOB()
    description = wintypes.LPWSTR()
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt32.CryptUnprotectData(ctypes.byref(source), ctypes.byref(description),
        None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(destination)):
        raise AgentError("Windows DPAPI could not unlock the endpoint key")
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(destination.pbData)
        if description:
            kernel32.LocalFree(description)
        del keepalive


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".aegis-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
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


def _load_key(path: Path) -> Ed25519PrivateKey:
    try:
        raw = unprotect_private_key(path.read_bytes())
        if len(raw) != 32:
            raise AgentError("protected endpoint key is invalid")
        return Ed25519PrivateKey.from_private_bytes(raw)
    except OSError:
        raise AgentError("protected endpoint key is unavailable") from None


def _request_json(url: str, payload: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    request = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": f"AEGIS-Windows-Agent/{AGENT_VERSION}",
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
    """Use Toolhelp32 process APIs; never read command lines or process memory."""
    if os.name != "nt":
        return []
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if handle == INVALID_HANDLE_VALUE:
        raise AgentError("Windows process inventory is unavailable")
    result: list[dict[str, Any]] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(handle, ctypes.byref(entry))
        while ok and len(result) < MAX_PROCESSES:
            result.append({"pid": int(entry.th32ProcessID), "name": entry.szExeFile[:128]})
            ok = kernel32.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(handle)
    return result


def enroll(server_url: str, token: str, state_dir: Path) -> str:
    server = require_https(server_url)
    if not token or len(token) > 256:
        raise AgentError("enrollment token is invalid")
    state_dir.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw, serialization.NoEncryption())
    _atomic_write(state_dir / "device.key.dpapi", protect_private_key(raw))
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    payload = {
        "enrollment_token": token, "platform": "windows",
        "public_key_b64": base64.b64encode(public).decode("ascii"),
        "hostname": platform.node()[:255] or "windows-host", "agent_version": AGENT_VERSION,
    }
    result = _request_json(server + "/api/v1/endpoints/enroll", payload)
    device_id = result.get("device_id")
    if not isinstance(device_id, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", device_id
    ):
        raise AgentError("server returned an invalid device identity")
    _write_json(state_dir / "config.json", {
        "server_url": server, "device_id": device_id, "last_sequence": 0,
        "os_version": platform.version(), "architecture": platform.machine()[:32],
    })
    return device_id


def run_once(state_dir: Path) -> int:
    config_path = state_dir / "config.json"
    config = _read_json(config_path)
    server = require_https(str(config.get("server_url", "")))
    device_id = str(config.get("device_id", ""))
    if not device_id:
        raise AgentError("agent is not enrolled")
    key = _load_key(state_dir / "device.key.dpapi")
    sequence = int(config.get("last_sequence", 0))
    events = [
        ("heartbeat", {"agent_version": AGENT_VERSION, "hostname": platform.node()[:255],
            "os_version": platform.version(), "architecture": platform.machine()[:32]}),
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
    parser = argparse.ArgumentParser(description="AEGIS Windows endpoint collector")
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
