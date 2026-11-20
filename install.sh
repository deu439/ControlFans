#!/usr/bin/env bash
# Installs (or uninstalls with --uninstall) the Control Fans systemd service.
set -euo pipefail

LIB_DIR=/usr/local/lib/control_fans
CONF_DIR=/etc/control_fans
UNIT=/etc/systemd/system/control_fans.service
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (try: sudo $0 $*)" >&2
    exit 1
fi

if [[ "${1:-}" == "--uninstall" ]]; then
    systemctl disable --now control_fans.service 2>/dev/null || true
    rm -f "$UNIT"
    rm -rf "$LIB_DIR"
    systemctl daemon-reload
    echo "Uninstalled. Configuration in $CONF_DIR was kept."
    exit 0
fi

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

if [[ ! -d /sys/devices/platform/applesmc.768 ]]; then
    modprobe applesmc 2>/dev/null || true
fi
if [[ ! -d /sys/devices/platform/applesmc.768 ]]; then
    echo "Warning: /sys/devices/platform/applesmc.768 not found. This software needs an Apple machine with the applesmc kernel module." >&2
fi

echo "Installing program to $LIB_DIR"
install -d "$LIB_DIR"
install -m 755 "$SRC_DIR/control_fans.py" "$LIB_DIR/control_fans.py"
python3 -m venv "$LIB_DIR/venv"
"$LIB_DIR/venv/bin/pip" install --quiet --upgrade -r "$SRC_DIR/requirements.txt"

echo "Installing configuration to $CONF_DIR"
install -d "$CONF_DIR"
if [[ -e "$CONF_DIR/config.yml" ]]; then
    echo "  $CONF_DIR/config.yml exists, keeping it (new default saved as config.yml.new)"
    install -m 644 "$SRC_DIR/config.yml" "$CONF_DIR/config.yml.new"
else
    install -m 644 "$SRC_DIR/config.yml" "$CONF_DIR/config.yml"
fi

echo "Installing systemd unit"
install -m 644 "$SRC_DIR/control_fans.service" "$UNIT"
systemctl daemon-reload
systemctl enable control_fans.service

cat <<MSG

Installed. Review $CONF_DIR/config.yml (fan and sensor names differ between models),
then start the service with:
    systemctl start control_fans.service
and watch it with:
    journalctl -u control_fans.service -f
MSG
