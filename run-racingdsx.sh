#!/bin/bash
# Launch RacingDSX under Wine + Xvfb in the background
# Pipeline: FH4 → UDP 5300 → RacingDSX → UDP 6969 → Hefesto → DualSense

WINEPREFIX="/var/home/deck/code/dsx4unix/.wine-racingdsx"
WINE="/home/deck/.local/share/Steam/steamapps/common/Proton Hotfix/files/bin/wine"
RACINGDSX_DIR="/var/home/deck/code/dsx4unix/RacingDSX"
export LD_LIBRARY_PATH="/usr/lib64"

cd "$RACINGDSX_DIR"

xvfb-run -s "-screen 0 1024x768x24" \
  WINEDEBUG=-all \
  "$WINE" RacingDSX.exe &

echo "RacingDSX started (PID: $!)"
echo "  Listening on UDP 5300 (game input)"
echo "  Forwarding to UDP 6969 (Hefesto)"
