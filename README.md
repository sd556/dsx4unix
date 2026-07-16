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

## RacingDSX on Linux (Native .NET)

**Goal**: Run RacingDSX (the original C# app) natively on Linux via .NET 8 runtime → UDP 6969 → Hefesto → DualSense.

### Architecture

```
┌──────────────────────┐     UDP telemetry      ┌──────────────────┐     UDP 6969 (DSX JSON)     ┌──────────────────┐     HID (direct)     ┌────────────┐
│  Forza Horizon 4     │ ──────────────────────→│  RacingDSX       │ ────────────────────────────→│  Hefesto         │ ────────────────────→│ DualSense   │
│  (Proton / Native)   │  UDP 5300              │  (.NET 8 Linux)  │  (DSX protocol compatible)   │  (DualSense4Unix)  │  hidraw / pydualsense │ (PS5)      │
└──────────────────────┘                        └──────────────────┘                                └──────────────────┘                        └────────────┘
```

### Prerequisites

1. **.NET 8 Runtime** installed (`dotnet --version >= 8.0`)
2. **Hefesto** running on UDP 6969 (see above)
3. **RacingDSX-Headless** source in `RacingDSX-Headless/`

### Quick Start

```bash
cd ~/code/dsx4unix/RacingDSX-Headless

# Build
dotnet publish -c Release -r linux-x64 -o bin/Release/net8.0/linux-x64

# Run
dotnet bin/Release/net8.0/linux-x64/RacingDSX.dll
```

### Configuration

Edit `bin/Release/net8.0/linux-x64/RacingDSX.json`:

```json
{
  "DisableAppCheck": true,
  "VerboseLevel": 1,
  "DSXPort": 6969,
  "DefaultProfile": "Forza",
  "Profiles": {
    "Forza": {
      "GameType": 1,
      "IsEnabled": true,
      "Name": "Forza",
      "gameUDPPort": 5300,
      "throttleSettings": {
        "TriggerMode": 2,
        "GripLossValue": 0.6,
        "EffectIntensity": 2,
        "TurnAccelerationScale": 0.25,
        "ForwardAccelerationScale": 1,
        "AccelerationLimit": 10,
        "VibrationModeStart": 5,
        "MinVibration": 5,
        "MaxVibration": 55,
        "VibrationSmoothing": 1,
        "MinStiffness": 15,
        "MaxStiffness": 20,
        "MinResistance": 0,
        "MaxResistance": 7,
        "ResistanceSmoothing": 0.4
      },
      "brakeSettings": {
        "TriggerMode": 2,
        "EffectIntensity": 1,
        "GripLossValue": 0.05,
        "VibrationStart": 0,
        "VibrationModeStart": 30,
        "MinVibration": 15,
        "MaxVibration": 20,
        "VibrationSmoothing": 1,
        "MinStiffness": 15,
        "MaxStiffness": 20,
        "MinResistance": 0,
        "MaxResistance": 7,
        "ResistanceSmoothing": 0.4
      }
    }
  }
}
```

### Tuning Guide: L2 (Brake) & R2 (Throttle) for FH4

**R2 (Throttle) — Grip Loss / Drift Kickback:**

| Parameter | Default | Description | Tuning Tips |
|-----------|---------|-------------|-------------|
| `TriggerMode` | 2 | 0=Resistance, 1=Vibration, 2=Hybrid | Keep at 2 for hybrid vibration+resistance |
| `GripLossValue` | 0.6 | Tire slip threshold to trigger vibration | Lower (0.3-0.4) for earlier drift detection |
| `EffectIntensity` | 2 | Multiplier for vibration frequency & resistance | **Increase to 3-5 for stronger kickback** |
| `MaxVibration` | 55 | Max vibration frequency | Increase to 80-100 for more intense rumble |
| `MinStiffness` | 15 | Stiffness at max acceleration | Lower to 5 for softer throttle feel |
| `MaxStiffness` | 20 | Stiffness at zero acceleration | Higher = stiffer idle feel |
| `MaxResistance` | 7 | Max resistance level (0-8) | Keep at 7 for strong resistance |
| `ResistanceSmoothing` | 0.4 | EWMA smoothing factor | Lower (0.2) for snappier response |
| `VibrationModeStart` | 5 | Min throttle input for vibration | Lower to trigger vibration at light throttle |

**L2 (Brake) — Brake Pressure Feel:**

| Parameter | Default | Description | Tuning Tips |
|-----------|---------|-------------|-------------|
| `TriggerMode` | 2 | 0=Resistance, 1=Vibration, 2=Hybrid | Keep at 2 for hybrid mode |
| `EffectIntensity` | 1 | Multiplier for brake effects | Increase to 2-3 for stronger brake feel |
| `GripLossValue` | 0.05 | Tire slip threshold for brake vibration | Lower for earlier ABS-like feedback |
| `MinStiffness` | 15 | Stiffness at max brake pressure | Lower to 5 for progressive brake feel |
| `MaxStiffness` | 20 | Stiffness at zero brake pressure | Higher = stiffer idle feel |
| `MaxResistance` | 7 | Max resistance level (0-8) | Keep at 7 for strong brake resistance |
| `ResistanceSmoothing` | 0.4 | EWMA smoothing factor | Lower (0.2) for snappier brake response |

### Hefesto Patch Required

Hefesto needs the following patches to support RacingDSX's `VibrateResistance` mode:

**File**: `src/hefesto_dualsense4unix/core/trigger_effects.py`

1. **Clamp force values 0-255 → 0-8** (RacingDSX sends 0-255, Hefesto expects 0-8):
```python
def _force(value: int, *, name: str) -> int:
    clamped = max(0, min(8, value))
    if clamped == 8:
        return 255
    return clamped * 32
```

2. **Add custom mode presets** to `PRESET_FACTORIES`:
```python
"CustomTriggerValue": custom,
"VibrateResistance": custom,
"VibrateResistanceA": custom,
"VibrateResistanceB": custom,
"VibrateResistanceAB": custom,
"VibratePulse": custom,
"VibratePulseA": custom,
"VibratePulseB": custom,
"VibratePulseAB": custom,
```

### Protocol Mismatch Fix

RacingDSX `Program.cs` must be patched to match Hefesto's expected DSX protocol:

1. **Add `version` field** to `Packet` class:
```csharp
[JsonPropertyName("version")]
public int Version { get; set; } = 1;
```

2. **Serialize `type` as string** (Hefesto expects `"TriggerUpdate"` not `1`):
```csharp
public class InstructionTypeStringConverter : JsonConverter<InstructionType>
{
    public override void Write(Utf8JsonWriter writer, InstructionType value, JsonSerializerOptions options)
    {
        writer.WriteStringValue(value.ToString());
    }
}
```

3. **Serialize `parameters` correctly** — skip `controllerIndex`, serialize enums as strings:
```csharp
// Skip controllerIndex (first element) — Hefesto expects [side, mode, ...]
int startIdx = value.Length > 0 && value[0] is int ? 1 : 0;
```

### Known Issues

- **R2 drift kickback is subtle** — RacingDSX calculates vibration frequency from acceleration data. During steady drift (constant speed), acceleration is low → frequency = 0. Increase `EffectIntensity` to 3-5 for stronger kickback.
- **Wine alternative** — RacingDSX can also run under Wine/Proton but requires ICU DLLs and Xvfb. Native .NET is simpler.

## License

MIT
