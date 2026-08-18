#!/bin/bash
# One-line Setup & Restore Script for GitHub Codespaces
set -e

echo "=== Setting up Telegram-GDrive Sync in Codespaces ==="

# 1. Install rclone
if ! command -v rclone &> /dev/null; then
    echo "Installing rclone..."
    sudo apt-get update -qq && sudo apt-get install -y -qq rclone
fi

# 2. Install uv if missing
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Create rclone config directory
mkdir -p ~/.config/rclone

# 4. Restore rclone configuration if provided in RCLONE_CONF_BASE64 secret/env
if [ -n "$RCLONE_CONF_BASE64" ]; then
    echo "$RCLONE_CONF_BASE64" | base64 -d > ~/.config/rclone/rclone.conf || echo "$RCLONE_CONF_BASE64" | base64 --decode > ~/.config/rclone/rclone.conf
    echo "rclone.conf restored successfully!"
fi

# 5. Restore Telegram session file if provided in TG_SESSION_BASE64 secret/env
mkdir -p .state
if [ -n "$TG_SESSION_BASE64" ]; then
    echo "$TG_SESSION_BASE64" | base64 -d > .state/tg_session.session 2>/dev/null || true
fi

# 6. Install python dependencies
uv sync || pip install telethon rich psutil pypdf pdfplumber

echo "=== Setup complete! ==="
