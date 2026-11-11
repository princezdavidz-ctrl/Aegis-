# AEGIS macOS endpoint agent

A lightweight macOS collector using the macOS Keychain for local signing-key storage and the native BSD process inventory utility.

## Scope and protections
- Enrolls with a one-time invitation and a locally generated Ed25519 identity.
- Stores the private key only in the macOS Keychain; it refuses fallback to file-based key storage.
- Collects PID and executable name only, using ps with no command-line arguments.
- Sends a bounded heartbeat and process inventory as signed events over HTTPS.
- Runs as the logged-in user through a LaunchAgent; no root privileges are required.
- Does not inspect process memory, browser data, credentials or private files and accepts no remote commands.

## Install
Run the installer from this directory in the target user's interactive macOS session:

    chmod +x install.sh
    ./install.sh

Create an invitation in the AEGIS tenant console, then enroll interactively. The token is read through a hidden prompt and is not persisted.

    "$HOME/.local/lib/aegis-agent/venv/bin/python" "$HOME/.local/lib/aegis-agent/aegis_agent.py" --state-dir "$HOME/Library/Application Support/AEGIS" enroll --server https://aegis.example.com

The LaunchAgent runs at login and every five minutes. The private key remains in the user's Keychain and is not written to the state directory.

## Local development

    python3 -m pip install -r requirements.txt
    python3 -m unittest discover -s tests -v

The API endpoint must use HTTPS with a valid certificate. Configure gateway rate limits and distribute agent updates through a signed software deployment channel.
