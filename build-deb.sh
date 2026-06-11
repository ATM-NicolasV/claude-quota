#!/usr/bin/env bash
# Build a .deb for claude-usage-indicator using only dpkg-deb (no extra build tooling).
# Usage: ./build-deb.sh [version]   (default version: 1.0.0)
set -euo pipefail

VERSION="${1:-1.0.0}"
PKG="claude-usage-indicator"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_ROOT="$(mktemp -d)"
DEB_PATH="${APP_DIR}/${PKG}_${VERSION}_all.deb"

trap 'rm -rf "${BUILD_ROOT}"' EXIT

# mktemp creates the dir as 0700; the package root must be world-readable (0755).
chmod 755 "${BUILD_ROOT}"

# --- file tree -------------------------------------------------------------
install -d "${BUILD_ROOT}/DEBIAN"
install -d "${BUILD_ROOT}/usr/lib/${PKG}"
install -d "${BUILD_ROOT}/usr/bin"
install -d "${BUILD_ROOT}/etc/xdg/autostart"
install -d "${BUILD_ROOT}/usr/share/doc/${PKG}"

# Application modules
for module in usage_client formatting indicator main; do
    install -m 644 "${APP_DIR}/${module}.py" "${BUILD_ROOT}/usr/lib/${PKG}/"
done
install -m 644 "${APP_DIR}/README.md" "${BUILD_ROOT}/usr/share/doc/${PKG}/"

# Launcher: running main.py directly puts its dir on sys.path[0], so the
# sibling modules import cleanly without any package install.
cat > "${BUILD_ROOT}/usr/bin/${PKG}" <<EOF
#!/bin/sh
exec python3 /usr/lib/${PKG}/main.py "\$@"
EOF
chmod 755 "${BUILD_ROOT}/usr/bin/${PKG}"

# Autostart entry (system-wide; each user reads their own ~/.claude at runtime).
cat > "${BUILD_ROOT}/etc/xdg/autostart/${PKG}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Indicator
Comment=Live Claude Code quota in the top bar
Exec=${PKG}
Icon=utilities-system-monitor-symbolic
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
EOF
chmod 644 "${BUILD_ROOT}/etc/xdg/autostart/${PKG}.desktop"

# --- control ---------------------------------------------------------------
INSTALLED_SIZE="$(du -ks "${BUILD_ROOT}/usr" "${BUILD_ROOT}/etc" | awk '{s+=$1} END {print s}')"
cat > "${BUILD_ROOT}/DEBIAN/control" <<EOF
Package: ${PKG}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1
Installed-Size: ${INSTALLED_SIZE}
Maintainer: Nicolas Vidal <nicolas.vidal@atm-consulting.fr>
Description: Live Claude Code quota indicator for the GNOME top bar
 Shows Claude Code subscription usage (5-hour window and 7-day weekly) as a
 tray indicator, refreshed periodically. Reads the local OAuth token from
 ~/.claude/.credentials.json. The usage endpoint is undocumented and may
 change without notice; the app degrades gracefully on auth/network errors.
EOF

# --- build -----------------------------------------------------------------
dpkg-deb --build --root-owner-group "${BUILD_ROOT}" "${DEB_PATH}"
echo "Built ${DEB_PATH}"
