#!/bin/bash
# One-line Setup & Restore Script for GitHub Codespaces
set -e

# 1. Install rclone if missing
if ! command -v rclone &> /dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y -qq rclone
fi

# 2. Install uv if missing
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Create rclone config directory
mkdir -p ~/.config/rclone

# 4. Restore rclone configuration if provided in RCLONE_CONF_BASE64 secret/env
if [ -n "$RCLONE_CONF_BASE64" ]; then
    echo "$RCLONE_CONF_BASE64" | base64 -d > ~/.config/rclone/rclone.conf 2>/dev/null || echo "$RCLONE_CONF_BASE64" | base64 --decode > ~/.config/rclone/rclone.conf 2>/dev/null || true
fi

# 5. Ensure .state directory exists and clear corrupted session placeholders
mkdir -p .state
if [ -f .state/tg_session.session ]; then
    if ! file .state/tg_session.session | grep -q "SQLite"; then
        rm -f .state/tg_session.session
    fi
fi

if [ -n "$TG_SESSION_BASE64" ]; then
    echo "$TG_SESSION_BASE64" | base64 -d > .state/tg_session.session 2>/dev/null || true
    if ! file .state/tg_session.session | grep -q "SQLite"; then
        rm -f .state/tg_session.session
    fi
fi

# 6. Install python dependencies editable & uv sync
$HOME/.local/bin/uv sync || true
$HOME/.local/bin/uv pip install -e . || pip install -e . || true
