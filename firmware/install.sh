#!/bin/bash
# PRATICO 3 - start the field program at every power-on, for a git checkout.
# Same as  pratico-service install  for a pipx/pip install. Run as the normal user, not with sudo:
#     bash install.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
exec /usr/bin/python3 "$DIR/pratico3_service.py" install "$@"
