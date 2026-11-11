# AEGIS Linux endpoint agent

A lightweight Linux collector for the AEGIS endpoint enrollment and signed telemetry API.

## Scope
- Enrolls with a one-time invitation and a locally generated Ed25519 keypair.
- Stores the private key in a mode-0600 file under a mode-0700 state directory.
- Sends a heartbeat and bounded process metadata from `/proc`.
- Signs the complete versioned event envelope and sends it over HTTPS.
- Never collects process command-line arguments, passwords, browser data or private files.
- Does not execute remote commands, modify system configuration, or perform persistence outside the documented systemd service/timer installation.

## Install
Use a dedicated unprivileged service account. The systemd unit uses `StateDirectory=aegis-agent` so systemd owns and protects `/var/lib/aegis-agent`.

```sh
sudo useradd --system --home-dir /var/lib/aegis-agent --shell /usr/sbin/nologin aegis-agent
sudo python3 -m venv /opt/aegis-agent
sudo /opt/aegis-agent/bin/pip install -r requirements.txt
sudo install -m 0644 aegis-agent.service aegis-agent.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

Create an enrollment invitation in the AEGIS tenant console, then run enrollment interactively as the service account. The token is read with a hidden prompt and is not stored.

```sh
sudo -u aegis-agent /opt/aegis-agent/bin/python aegis_agent.py --state-dir /var/lib/aegis-agent enroll --server https://aegis.example.com
```

Enable periodic collection after successful enrollment:

```sh
sudo systemctl enable --now aegis-agent.timer
```

## Local development
```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The API endpoint must be HTTPS with a valid certificate. Configure gateway rate limits for enrollment and event ingestion. Agent updates should be distributed as signed packages through the organization's software-management system.
