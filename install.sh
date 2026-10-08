#!/usr/bin/env bash
# install.sh — set up the tint4 tray indicator + autostart + config scaffold.
#
# 1. Installs the indicator runtime deps (GTK3 + AppIndicator).
# 2. Writes ~/.config/autostart/tint4-indicator.desktop (runs at login).
# 3. Scaffolds ~/.config/tint4/config.json (left untouched if it already exists).
#
# It detects the right Pythons for the two jobs, because this box has three:
#   - the indicator needs gi/Gtk/AppIndicator  (usually the apt/system Python)
#   - the daemon needs usb/portio/PIL          (usually the 3.14 source build)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/tint4"
CONFIG_FILE="$CONFIG_DIR/config.json"
AUTOSTART_DIR="$HOME/.config/autostart"

say()  { printf '\033[1;34m[tint4]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[tint4]\033[0m %s\n' "$*"; }

# --- 1. indicator runtime deps -------------------------------------------
say "Installing indicator dependencies (GTK3 + AppIndicator)…"
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y python3-gi gir1.2-ayatanaappindicator3-0.1 \
        || sudo apt-get install -y python3-gi gir1.2-appindicator3-0.1
else
    warn "apt-get not found — install python3-gi + gir1.2-ayatanaappindicator3-0.1 manually"
fi

# --- 2. detect the two pythons -------------------------------------------
detect_indicator_python() {
    for p in python3 /usr/bin/python3 python3.12 python3.13; do
        if command -v "$p" >/dev/null 2>&1 \
           && "$p" -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" >/dev/null 2>&1; then
            command -v "$p"; return 0
        fi
    done
    return 1
}
detect_daemon_python() {
    for p in python3 /usr/local/bin/python3 python3.14 python3.13 /usr/bin/python3; do
        if command -v "$p" >/dev/null 2>&1 \
           && "$p" -c "import usb, portio, PIL" >/dev/null 2>&1; then
            command -v "$p"; return 0
        fi
    done
    return 1
}

IPY="$(detect_indicator_python || true)"
DPY="$(detect_daemon_python || true)"
if [ -z "$IPY" ]; then
    warn "no Python with gi/Gtk found — the indicator will not start until python3-gi is installed"
    IPY=python3
fi

# --- 3. autostart entry --------------------------------------------------
say "Enabling autostart…"
mkdir -p "$AUTOSTART_DIR"
chmod +x "$HERE/tint4-indicator.py"
cat > "$AUTOSTART_DIR/tint4-indicator.desktop" <<EOF
[Desktop Entry]
Name=tint4 eInk
Comment=eInk cover-display carousel + panel indicator
Exec=$IPY $HERE/tint4-indicator.py --autostart
Icon=preferences-desktop-display
Terminal=false
Type=Application
X-GNOME-Autostart-enabled=true
EOF

# --- 3b. app-finder launcher --------------------------------------------
say "Installing app-finder launcher…"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
sed -e "s|@INDICATOR_PY@|$IPY|g" -e "s|@HERE@|$HERE|g" \
    "$HERE/tint4-restart.desktop" > "$APPS_DIR/tint4-restart.desktop"
chmod +x "$APPS_DIR/tint4-restart.desktop"
update-desktop-database "$APPS_DIR" 2>/dev/null || true

# --- 4. config scaffold --------------------------------------------------
say "Writing config scaffold…"
mkdir -p "$CONFIG_DIR"
if [ -f "$CONFIG_FILE" ]; then
    say "config already exists at $CONFIG_FILE (left untouched)"
else
    if [ -n "$DPY" ]; then
        DAEMON_CMD="[\"pkexec\", \"$DPY\", \"$HERE/HelperDaemon.py\"]"
        say "daemon Python detected: $DPY"
    else
        DAEMON_CMD='["pkexec", "tinta4plusu-helper"]'
        warn "no Python with usb/portio/PIL found — defaulting daemon_cmd to tinta4plusu-helper (may be a stale binary)"
    fi
    IMG_DIR="${TINT4_IMAGE_DIR:-$HOME/Pictures/eink}"
    mkdir -p "$IMG_DIR" 2>/dev/null || true
    cat > "$CONFIG_FILE" <<EOF
{
  "image_dir": "$IMG_DIR",
  "interval": 60,
  "mode": 5,
  "brightness": 4,
  "daemon_cmd": $DAEMON_CMD
}
EOF
fi

say "Done."
say "Start now:  $IPY $HERE/tint4-indicator.py --autostart"
say "Prefs:       $CONFIG_FILE"
