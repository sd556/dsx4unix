# dsx4unix — Racing Telemetry to DualSense Adaptive Triggers on Linux

A Linux-native FH4/Forza telemetry stack for PS5 DualSense adaptive triggers.

```text
Forza Horizon 4 --UDP :5300--> RacingDSX-Headless --DSX JSON :6969--> Hefesto --hidraw--> DualSense
```

This repository includes:

- The native .NET 8 `RacingDSX-Headless` bridge.
- The tested Hefesto fork as a pinned Git submodule.
- User-systemd service templates.
- One idempotent bootstrap and runtime launcher.
- The original Python `dsx4unix` mapper for development and comparison.

## Supported games

| Game | Telemetry format | Packet size |
|---|---|---:|
| Forza Motorsport 7 | Forza sled + dash | 311 bytes |
| Forza Motorsport 8 | Forza dash | 331 bytes |
| Forza Horizon 4 | Forza dash, offset | 324 bytes |
| DiRT Rally 1 | DiRT binary | 264 bytes |

## Project status / TODO

- [x] Run RacingDSX natively on Linux with .NET 8.
- [x] Translate RacingDSX protocol v1 messages through the bundled Hefesto fork.
- [x] Preserve RacingDSX's custom trigger force range in Hefesto.
- [x] Provide idempotent setup, user-systemd services, and a single runtime launcher.
- [x] Validate FH4 telemetry and adaptive triggers with a physical DualSense over USB.
- [x] Stabilize Bluetooth HID output with transport-aware pacing and verify sustained FH4 operation on physical hardware.
- [ ] Complete physical-hardware regression passes for FM7, FM8, and DiRT Rally 1.

## Prerequisites

Run the stack on the Linux host that owns the DualSense HID device and user-systemd session. Required tools are:

- Git
- Python 3.10+ with venv support, or [uv](https://docs.astral.sh/uv/)
- .NET SDK 8 or newer
- `systemctl` and `ss`
- A DualSense connected over USB or Bluetooth

Ubuntu 24.04:

```bash
sudo apt update && sudo apt install -y git python3 python3-venv python3-dev libhidapi-dev libudev-dev libxi-dev dotnet-sdk-8.0 iproute2
```

Fedora:

```bash
sudo dnf install -y git python3 python3-devel hidapi-devel systemd dotnet-sdk-8.0 iproute
```

Confirm .NET before setup:

```bash
dotnet --version
```

The bootstrap also detects a user-local SDK at `~/.dotnet/dotnet`.

## Clone and bootstrap

A normal clone is supported; setup initializes Hefesto automatically:

```bash
git clone https://github.com/sd556/dsx4unix.git ~/code/dsx4unix
cd ~/code/dsx4unix
./start_dsx setup
```

Equivalent recursive clone:

```bash
git clone --recurse-submodules https://github.com/sd556/dsx4unix.git ~/code/dsx4unix
cd ~/code/dsx4unix
./start_dsx setup
```

To additionally install Hefesto's udev rules and load `uinput` (requires sudo):

```bash
cd ~/code/dsx4unix
./start_dsx setup --install-udev
```

Setup performs the following idempotently:

1. Initializes/updates `vendor/hefesto-dualsense4unix` to the pinned commit.
2. Creates `vendor/hefesto-dualsense4unix/.venv` and installs Hefesto.
3. Publishes RacingDSX into `.runtime/racingdsx` for the host architecture.
4. Installs checkout-relative user services in `~/.config/systemd/user/`.
5. Links `~/.local/bin/start_dsx` to this checkout.
6. reloads the user systemd manager.

**Setup does not start or enable either service.** Hefesto will not automatically run at login unless you explicitly enable it.

## Run the complete stack

```bash
~/.local/bin/start_dsx start
```

All commands:

```bash
~/.local/bin/start_dsx setup             # rebuild/reinstall; does not start
~/.local/bin/start_dsx start             # Hefesto :6969, then RacingDSX :5300
~/.local/bin/start_dsx stop              # RacingDSX, then Hefesto
~/.local/bin/start_dsx restart
~/.local/bin/start_dsx status
~/.local/bin/start_dsx logs
~/.local/bin/start_dsx logs --follow
~/.local/bin/start_dsx enable            # opt in to login autostart
~/.local/bin/start_dsx disable
```

Select or restore the Forza adaptive-trigger profile from the repository checkout:

```bash
./start_dsx high    # maximum R2 throttle + L2 brake feedback
./start_dsx normal  # restore the exact trigger settings saved before high
```

The intentionally forceful `high` profile affects both triggers: it lowers grip-loss thresholds, strengthens baseline resistance and vibration, and reduces smoothing so R2 and L2 react immediately. The first `high` snapshots exactly the selected Forza throttle and brake keys in `.runtime/racingdsx/trigger-profile-state.json`; repeated `high` selections reapply the preset without replacing that snapshot. `normal` restores those pre-high values exactly and removes the state file. Other Forza values, edits made while high is active, the DiRT profile, and all unrelated configuration remain unchanged.

Profile selection updates the live `.runtime/racingdsx/RacingDSX.json`, never the seed `config/RacingDSX.json`. If both managed services are already active, it restarts and checks only RacingDSX; Hefesto is never stopped or restarted, so its Bluetooth controller handle remains intact. If either service is inactive, the launcher uses the normal full-stack start and stability checks instead.

Invalid configuration, preset, or saved state exits nonzero before any service action; JSON destination replacement is atomic. A helper write/removal error also prevents service action, though an earlier successful state or config write is not rolled back. A later service start/restart or health-check failure returns nonzero without rolling back the selected profile; incomplete-stack startup failures use the normal full-stack cleanup.

`start` waits for each UDP listener and then performs a stability check. If setup artifacts are absent, the launcher prints the exact setup command instead of trying stale external services.

## Forza Horizon 4 telemetry

Configure FH4 telemetry output for UDP port `5300`. The managed pipeline is:

1. RacingDSX listens for FH4 packets on UDP `5300`.
2. It maps throttle, brake, acceleration, and tire slip to DSX protocol v1 messages.
3. Hefesto listens on UDP `6969` and translates those messages to DualSense HID reports.

The bundled Hefesto revision preserves ordinary raw stiffness values `9–255`, scales named resistance levels `0–8`, and preserves custom/hybrid force bytes exactly. This retains the dynamic force range emitted by RacingDSX.

The installed RacingDSX runtime config is initialized from `config/RacingDSX.json`. Bootstrap preserves an existing runtime config on subsequent runs.

### Adaptive-trigger tuning

The live R2/L2 response is calculated in `RacingDSX-Headless/GameParsers/Parser.cs`:

- `GetInRaceRightTriggerInstruction()` controls R2/throttle response.
- `GetInRaceLeftTriggerInstruction()` controls L2/brake response.
- `Map()` and `EWMA()` provide value mapping and response smoothing for both triggers.

The tunable values come from the active profile's `throttleSettings` and `brakeSettings`. For a running installed stack, edit `.runtime/racingdsx/RacingDSX.json`; `config/RacingDSX.json` is only the seed copied during first-time setup. The corresponding strongly typed defaults are in `RacingDSX-Headless/Config/ThrottleSettings.cs` and `RacingDSX-Headless/Config/BrakeSettings.cs`.

Restart RacingDSX after changing its live JSON config:

```bash
systemctl --user restart racingdsx.service
```

## Diagnostics

```bash
~/.local/bin/start_dsx status
~/.local/bin/start_dsx logs --follow
ss -lunp | grep -E ':(5300|6969)([[:space:]]|$)'
```

Expected listeners:

- UDP `6969`: Hefesto DSX server
- UDP `5300`: RacingDSX FH4 telemetry receiver

If the controller is not writable, install the bundled udev rules, then reconnect it:

```bash
cd ~/code/dsx4unix
./start_dsx setup --install-udev
```

## Development

Install and test the original Python mapper:

```bash
cd ~/code/dsx4unix
uv sync
uv run pytest -q
```

Run Hefesto's complete tests from the bundled source:

```bash
cd ~/code/dsx4unix/vendor/hefesto-dualsense4unix
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests
```

Build RacingDSX directly:

```bash
cd ~/code/dsx4unix
"${HOME}/.dotnet/dotnet" publish RacingDSX-Headless/RacingDSX.csproj -c Release -r linux-x64 --self-contained false
```

## Repository layout

```text
dsx4unix/
├── config/RacingDSX.json
├── RacingDSX-Headless/
├── scripts/bootstrap-stack.sh
├── systemd/*.service.in
├── vendor/hefesto-dualsense4unix/   # pinned Git submodule
├── start_dsx
├── src/dsx4unix/
└── tests/
```

## License

MIT
