# dsx4unix — Racing Telemetry → DualSense Adaptive Triggers on Linux

Port of [RacingDSX](https://github.com/cosmii02/RacingDSX) to Linux (Bazzite / Fedora / Ubuntu). Reads racing game telemetry via UDP, maps it to adaptive trigger effects, and sends DSX-compatible JSON over UDP to a Linux DualSense daemon.

## Architecture

```
┌──────────────────────┐     UDP telemetry      ┌──────────────────┐     UDP 6969 (DSX JSON)     ┌──────────────────┐     HID (direct)     ┌────────────┐
│  Racing Game         │ ──────────────────────→│  dsx4unix        │ ────────────────────────────→│  Hefesto         │ ────────────────────→│ DualSense   │
│  (Proton / Native)   │  (Forza / DiRT binary) │  (Python)        │  (DSX protocol compatible)   │  (DualSense4Unix)  │  hidraw / pydualsense │ (PS5)      │
└──────────────────────┘                        └──────────────────┘                                └──────────────────┘                        └────────────┘
```

**dsx4unix** replaces the C# RacingDSX Windows app. It:

1. **Receives** raw UDP telemetry packets from racing games (Forza Motorsport 7/8/Horizon, DiRT Rally)
2. **Parses** binary telemetry into structured data (throttle, brake, tire slip, RPM, acceleration)
3. **Maps** telemetry to adaptive trigger effects (resistance + vibration on L2/R2)
4. **Sends** DSX-compatible JSON instructions over UDP to `127.0.0.1:6969`
5. **Hefesto** receives the DSX protocol and drives the DualSense controller directly

**The DualSense controller is driven by Hefesto** — dsx4unix only speaks the DSX protocol. This means zero HID driver code and full compatibility with RacingDSX profiles.

## Supported Games

| Game | Telemetry Format | Packet Size | Status |
|------|-----------------|-------------|--------|
| Forza Motorsport 7 | Forza binary (sled + dash) | 311 bytes | ✅ |
| Forza Motorsport 8 | Forza binary (dash) | 331 bytes | ✅ |
| Forza Horizon 4 | Forza binary (dash, offset) | 324 bytes | ✅ |
| DiRT Rally 1 | DiRT binary | 264 bytes | ✅ |

## Prerequisites

### 1. DualSense Controller Connected
Connect your PS5 DualSense via USB or Bluetooth.

### 2. Hefesto (DualSense4Unix)
Hefesto is the Linux DSX replacement that receives UDP on port 6969 and drives the DualSense:

```bash
# Install from source
git clone https://github.com/AndreBFarias/hefesto-dualsense4unix.git
cd hefesto-dualsense4unix
./scripts/dev_bootstrap.sh --with-tray
./scripts/install_udev.sh  # needs sudo
systemctl --user enable --now hefesto-dualsense4unix.service
```

Or use the [Flatpak](https://github.com/AndreBFarias/hefesto-dualsense4unix) / [.deb](https://github.com/AndreBFarias/hefesto-dualsense4unix/releases) packages.

### 3. Python 3.10+
```bash
# Bazzite / Fedora
sudo dnf install python3-pip python3-devel

# Ubuntu / Pop!_OS
sudo apt install python3-pip python3-dev
```

## Installation

```bash
cd ~/code/dsx4unix
pip install -e .
```

## Usage

```bash
# Run with default Forza profile
dsx4unix --profile forza

# Run with DiRT Rally profile
dsx4unix --profile dirt

# Custom config file
dsx4unix --config /path/to/config.yaml

# Verbose logging
dsx4unix --verbose

# Show available profiles
dsx4unix --list-profiles
```

## Configuration

Default config at `config/default.yaml`. Per-profile configs in `config/profiles/`.

### Profile Structure

```yaml
game: forza                          # forza | dirt | null
name: "Forza Motorsport"
telemetry_port: 30778               # UDP port to receive game telemetry
dsx_host: "127.0.0.1"               # Hefesto UDP address
dsx_port: 6969                      # Hefesto UDP port

throttle:
  trigger_mode: vibration           # off | resistance | vibration
  grip_loss_value: 0.6              # tire slip threshold for vibration
  effect_intensity: 1.0             # 0.0–1.0 multiplier
  turn_acceleration_scale: 0.25     # weight for lateral acceleration
  forward_acceleration_scale: 1.0   # weight for forward acceleration
  acceleration_limit: 10            # max acceleration for resistance mapping
  vibration_mode_start: 5           # min throttle input for vibration
  min_vibration: 5                  # min vibration frequency
  max_vibration: 55                 # max vibration frequency
  vibration_smoothing: 1.0          # EWMA alpha for vibration
  min_stiffness: 255                # max stiffness at zero accel
  max_stiffness: 175                # min stiffness at max accel
  min_resistance: 0                 # min resistance at zero accel
  max_resistance: 3                 # max resistance at max accel
  resistance_smoothing: 0.9         # EWMA alpha for resistance

brake:
  trigger_mode: vibration
  grip_loss_value: 0.05
  effect_intensity: 1.0
  vibration_start: 0
  vibration_mode_start: 30
  min_vibration: 15
  max_vibration: 20
  vibration_smoothing: 1.0
  min_stiffness: 150
  max_stiffness: 5
  min_resistance: 0
  max_resistance: 7
  resistance_smoothing: 0.4

lightbar:
  rpm_redline_ratio: 0.9            # ratio of RPM range where redline activates
```

## How It Works

### Telemetry Parsing
Reads raw binary UDP packets from the game. Forza uses a fixed-offset binary format (float32 for most fields, uint8 for controls). DiRT Rally uses a similar but different offset layout.

### Trigger Mapping
- **Resistance mode**: Maps brake/throttle input to continuous trigger resistance
- **Vibration mode**: Adds pulsing vibration when tires lose grip (slip exceeds threshold)
- Uses EWMA (Exponentially Weighted Moving Average) smoothing to prevent jitter

### Lightbar
- **In-race**: RPM-based color (green → yellow → red as RPM approaches redline)
- **Menu/Pre-race**: Car class color (Forza) or default purple

### DSX Protocol Output
Sends JSON to Hefesto on port 6969:
```json
{"version": 1, "instructions": [{"type": "TriggerUpdate", "parameters": ["right", "Resistance", 0, 128]}]}
```

## Comparison: RacingDSX (Windows) vs dsx4unix (Linux)

| Aspect | RacingDSX | dsx4unix |
|--------|-----------|----------|
| Language | C# .NET 8 (WinForms) | Python 3.10+ |
| OS | Windows only | Linux (Bazzite, Fedora, Ubuntu) |
| Controller driver | DSX (Windows service) | Hefesto (Linux daemon) |
| Telemetry | Same UDP binary format | Same UDP binary format |
| DSX protocol | Same JSON over UDP | Same JSON over UDP |
| Config | INI file | YAML file |
| UI | WinForms GUI | CLI + logging |

## Project Structure

```
dsx4unix/
├── config/
│   ├── default.yaml              # Default config
│   └── profiles/
│       ├── forza.yaml            # Forza Motorsport profile
│       └── dirt.yaml             # DiRT Rally profile
├── src/dsx4unix/
│   ├── __init__.py
│   ├── __main__.py               # Entry point
│   ├── config/
│   │   ├── loader.py             # YAML config loading
│   │   └── models.py             # Pydantic models
│   ├── parsers/
│   │   ├── base.py               # Base parser class
│   │   ├── forza.py              # Forza telemetry parser
│   │   └── dirt.py               # DiRT Rally parser
│   ├── telemetry.py              # Data packet model
│   ├── mapper.py                 # Telemetry → trigger mapping
│   └── dsx.py                    # DSX protocol sender
└── pyproject.toml
```

## License

MIT
