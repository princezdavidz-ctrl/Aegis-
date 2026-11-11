# AEGIS Windows endpoint agent

A lightweight Windows collector using native Toolhelp32 process enumeration and Windows DPAPI.

## Scope and protections
- Enrolls with a one-time invitation and locally generated Ed25519 identity.
- Protects the private key with machine-scope DPAPI; the installer applies a restrictive ACL to the state directory.
- Uses native Windows process APIs to collect PID and executable name only. It does not inspect command lines, process memory, browser data or credentials.
- Sends a bounded heartbeat and process inventory over HTTPS with signed canonical event envelopes.
- Does not execute remote commands, install drivers, inject into processes, or change endpoint security settings.

## Install
Run PowerShell as Administrator from this directory. The installer creates the program and state directories, restricts state access to Local Service, SYSTEM and Administrators, and registers a periodic scheduled task.

    Set-ExecutionPolicy -Scope Process Bypass
    .\install.ps1

Create an invitation in the AEGIS tenant console, then enroll interactively. The token is read through a hidden prompt and is not persisted.

    & "$env:ProgramFiles\AEGIS\venv\Scripts\python.exe" "$env:ProgramFiles\AEGIS\aegis_agent.py" --state-dir "$env:ProgramData\AEGIS" enroll --server https://aegis.example.com

The scheduled task runs as Local Service every five minutes. The state directory ACL permits only Local Service, SYSTEM and local Administrators to read the DPAPI-protected identity.

## Local development

    py -m pip install -r requirements.txt
    py -m unittest discover -s tests -v

The API endpoint must use HTTPS with a valid certificate. Configure gateway rate limits and distribute agent updates through a signed software deployment channel.
