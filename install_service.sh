#!/bin/bash
set -e

SERVICE_NAME="telegram-gdrive-sync.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$SYSTEMD_USER_DIR"

SERVICE_FILE="$SYSTEMD_USER_DIR/$SERVICE_NAME"

cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Telegram to Google Drive Auto-Sync Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStartPre=/bin/sleep 60
ExecStart=$(which uv) run python main.py
Restart=on-failure
RestartSec=30s
StandardOutput=append:$PROJECT_DIR/logs/daemon.log
StandardError=append:$PROJECT_DIR/logs/daemon.log

[Install]
WantedBy=default.target
EOF

echo "Systemd service file created at $SERVICE_FILE"

# Reload systemd user daemon
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"

echo ""
echo "=== Systemd Autostart Service Installed Successfully ==="
echo "The daemon will start automatically whenever you log in."
echo ""
echo "Commands to manage the background service:"
echo "  Start now:   systemctl --user start $SERVICE_NAME"
echo "  Stop now:    systemctl --user stop $SERVICE_NAME"
echo "  Check status: systemctl --user status $SERVICE_NAME"
echo "  View logs:   journalctl --user -u $SERVICE_NAME -f"
echo ""
