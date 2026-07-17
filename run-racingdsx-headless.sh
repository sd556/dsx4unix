#!/bin/bash
# Run RacingDSX headless on Linux (native .NET 8)
# Receives FH4 telemetry on UDP 5300, sends trigger instructions to Hefesto on UDP 6969

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/RacingDSX-Headless/bin/Release/net8.0/linux-x64"
CONFIG_FILE="$BUILD_DIR/RacingDSX.json"
DOTNET="$HOME/.dotnet/dotnet"

# Ensure config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config not found at $CONFIG_FILE"
    echo "Copying from RacingDSX/RacingDSX.json..."
    cp "$SCRIPT_DIR/RacingDSX/RacingDSX.json" "$CONFIG_FILE"
fi

# Ensure DisableAppCheck is true
python3 -c "
import json
with open('$CONFIG_FILE') as f:
    d = json.load(f)
d['DisableAppCheck'] = True
with open('$CONFIG_FILE', 'w') as f:
    json.dump(d, f, indent=2)
"

echo "Starting RacingDSX headless..."
echo "  Telemetry port: 5300 (FH4)"
echo "  DSX port: 6969 (Hefesto)"
echo ""

cd "$BUILD_DIR"
exec "$DOTNET" RacingDSX.dll
