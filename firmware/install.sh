#!/bin/bash
# PRATICO 3 - install the field program as a systemd *user* service that starts at power-on
# (no login needed). Run as the normal user (e.g. fww), not with sudo:
#     bash install.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.config/systemd/user" "$HOME/PRATICO_3/calibration" "$HOME/PRATICO_3/results" \
         "$HOME/PRATICO_3/logs"
sed "s#@FWDIR@#$DIR#g" "$DIR/pratico3.service" > "$HOME/.config/systemd/user/pratico3.service"
systemctl --user daemon-reload
systemctl --user enable pratico3.service
echo "pratico3.service installed and enabled (firmware in $DIR)"

if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]; then
    echo
    echo "!! Linger is off: user services start only after a login. Enable start at boot with:"
    echo "     sudo loginctl enable-linger $USER"
fi
if systemctl is-enabled --quiet fww.service 2>/dev/null; then
    echo
    echo "!! The PRATICO 2 service fww.service is enabled and would compete for the hardware:"
    echo "     sudo systemctl disable --now fww.service"
fi
if [ ! -f "$HOME/PRATICO_3/calibration/pratico3_cal.json" ]; then
    echo
    echo "No calibration yet: the field program shows absorbance only until you run"
    echo "     python3 $DIR/pratico3_cal.py"
fi
echo
echo "Start now:  systemctl --user start pratico3      Logs:  journalctl --user-unit=pratico3 -f"
