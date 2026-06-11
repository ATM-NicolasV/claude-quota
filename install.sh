#!/usr/bin/env bash
# Install the autostart entry so the indicator launches at login.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="${HOME}/.config/autostart"
DESKTOP_PATH="${AUTOSTART_DIR}/claude-usage-indicator.desktop"

mkdir -p "${AUTOSTART_DIR}"

# Generate the autostart entry with the absolute path resolved at install time.
# The Desktop Entry spec defines no home-directory field code (only %f %F %u %U
# %i %c %k), so a placeholder like %h is silently dropped by the launcher and the
# resulting relative path fails to start. Writing the absolute path avoids that.
cat > "${DESKTOP_PATH}" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Indicator
Comment=Live Claude Code quota in the top bar
Exec=python3 ${APP_DIR}/main.py
Icon=utilities-system-monitor-symbolic
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
EOF
chmod 644 "${DESKTOP_PATH}"

echo "Installed autostart entry to ${DESKTOP_PATH}"
echo "Start now with: python3 ${APP_DIR}/main.py"
