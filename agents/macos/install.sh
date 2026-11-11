#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/lib/aegis-agent"
STATE_DIR="$HOME/Library/Application Support/AEGIS"
LOG_DIR="$HOME/Library/Logs/AEGIS"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
LABEL="com.aegis.endpoint"
PLIST="$LAUNCH_AGENTS/$LABEL.plist"

mkdir -p "$INSTALL_DIR" "$STATE_DIR" "$LOG_DIR" "$LAUNCH_AGENTS"
chmod 700 "$STATE_DIR"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --disable-pip-version-check -r "$ROOT/requirements.txt"
install -m 0755 "$ROOT/aegis_agent.py" "$INSTALL_DIR/aegis_agent.py"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$INSTALL_DIR/venv/bin/python</string>
    <string>$INSTALL_DIR/aegis_agent.py</string>
    <string>--state-dir</string>
    <string>$STATE_DIR</string>
    <string>run-once</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>300</integer>
  <key>StandardOutPath</key><string>$LOG_DIR/agent.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/agent-error.log</string>
</dict>
</plist>
EOF
chmod 600 "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
echo "AEGIS macOS agent installed. Enroll this user with a one-time invitation."
