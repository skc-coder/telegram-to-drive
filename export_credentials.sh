#!/bin/bash
# Generate one-line import command for GitHub Codespaces

RCLONE_B64=$(base64 -w 0 ~/.config/rclone/rclone.conf)
TG_B64=$(base64 -w 0 .state/tg_session.session)

echo ""
echo "=========================================================================="
echo "      COPY AND PASTE THIS EXACT ONE-LINE COMMAND INTO YOUR CODESPACE:     "
echo "=========================================================================="
echo ""
echo "export RCLONE_CONF_BASE64=\"$RCLONE_B64\" && export TG_SESSION_BASE64=\"$TG_B64\" && ./setup_codespace.sh"
echo ""
echo "=========================================================================="
