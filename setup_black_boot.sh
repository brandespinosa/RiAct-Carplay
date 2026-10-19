#!/bin/bash
# Keeps the screen black from power-on until CarPlay opens:
# hides the rainbow splash, boot logo and boot text, skips the desktop,
# and runs the CarPlay app full screen in the "cage" kiosk instead.
# Run once on the Pi:  bash setup_black_boot.sh
set -euo pipefail

APP_URL="${APP_URL:-https://github.com/brandespinosa/react-carplay/releases/latest/download/Carplay-arm64.AppImage}"
USER_NAME="${SUDO_USER:-$USER}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
HERE="$(cd "$(dirname "$0")" && pwd)"
BOOT=/boot/firmware
[ -f "$BOOT/cmdline.txt" ] || BOOT=/boot

echo "Installing cage (kiosk) and fuse (needed by the AppImage)"
sudo apt-get update
sudo apt-get install -y cage xwayland fuse libfuse2

echo "Downloading the black-screen CarPlay app"
sudo -u "$USER_NAME" mkdir -p "$HOME_DIR/carplay"
sudo -u "$USER_NAME" curl -fL "$APP_URL" -o "$HOME_DIR/carplay/Carplay.AppImage"
chmod +x "$HOME_DIR/carplay/Carplay.AppImage"

echo "Hiding the rainbow splash, boot logo and boot text"
sudo cp -n "$BOOT/config.txt" "$BOOT/config.txt.bak"
sudo cp -n "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.bak"
grep -q '^disable_splash=1' "$BOOT/config.txt" || echo 'disable_splash=1' | sudo tee -a "$BOOT/config.txt" >/dev/null
# cmdline.txt must stay one line: send boot text to tty3, drop the splash, hide logo and cursor
sudo sed -i -e 's/console=tty1/console=tty3/' -e 's/ splash//' "$BOOT/cmdline.txt"
for opt in quiet loglevel=3 logo.nologo vt.global_cursor_default=0; do
  grep -qw "$opt" "$BOOT/cmdline.txt" || sudo sed -i "1 s/\$/ $opt/" "$BOOT/cmdline.txt"
done

echo "Booting to a black console instead of the desktop"
sudo raspi-config nonint do_boot_behaviour B1
sudo systemctl disable getty@tty1.service

echo "Installing the CarPlay kiosk service"
sed -e "s#/home/pi/#$HOME_DIR/#" -e "s/^User=pi/User=$USER_NAME/" "$HERE/carplay-kiosk.service" \
  | sudo tee /etc/systemd/system/carplay-kiosk.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable carplay-kiosk.service

echo "Done. Reboot to use it:  sudo reboot"
