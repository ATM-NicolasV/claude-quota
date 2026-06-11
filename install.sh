#!/usr/bin/env bash
# Install the autostart entry so the indicator launches at login.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="${HOME}/.config/autostart"

mkdir -p "${AUTOSTART_DIR}"
install -m 644 "${APP_DIR}/claude-usage-indicator.desktop" \
    "${AUTOSTART_DIR}/claude-usage-indicator.desktop"

echo "Installed autostart entry to ${AUTOSTART_DIR}/claude-usage-indicator.desktop"
echo "Start now with: python3 ${APP_DIR}/main.py"
