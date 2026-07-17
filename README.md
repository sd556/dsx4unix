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

`start` waits for each UDP listener and then performs a stability check. If setup artifacts are absent, the launcher prints the exact setup command instead of trying stale external services.

## Forza Horizon 4 telemetry

Configure FH4 telemetry output for UDP port `5300`. The managed pipeline is:

1. RacingDSX listens for FH4 packets on UDP `5300`.
2. It maps throttle, brake, acceleration, and tire slip to DSX protocol v1 messages.
3. Hefesto listens on UDP `6969` and translates those messages to DualSense HID reports.

The bundled Hefesto revision preserves ordinary raw stiffness values `9–255`, scales named resistance levels `0–8`, and preserves custom/hybrid force bytes exactly. This retains the dynamic force range emitted by RacingDSX.

The installed RacingDSX runtime config is initialized from `config/RacingDSX.json`. Bootstrap preserves an existing runtime config on subsequent runs.

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
