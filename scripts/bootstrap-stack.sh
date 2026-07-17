#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${DSX_REPO_ROOT:-$(cd -- "$SCRIPT_DIR/.." && pwd)}"
HEFESTO_ROOT="$REPO_ROOT/vendor/hefesto-dualsense4unix"
RACING_PROJECT="$REPO_ROOT/RacingDSX-Headless/RacingDSX.csproj"
RACING_RUNTIME="$REPO_ROOT/.runtime/racingdsx"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
USER_BIN_DIR="$HOME/.local/bin"
INSTALL_UDEV=0

usage() {
    cat <<EOF
Usage: $REPO_ROOT/start_dsx setup [--install-udev]

Bootstraps the bundled Hefesto + RacingDSX stack without enabling or starting it.
  --install-udev  Install Hefesto's system udev rules (requires sudo).
EOF
}

for arg in "$@"; do
    case "$arg" in
        --install-udev) INSTALL_UDEV=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown setup argument: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

need_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        case "$1" in
            git) echo "Ubuntu: sudo apt update && sudo apt install -y git" >&2
                 echo "Fedora: sudo dnf install -y git" >&2 ;;
            systemctl) echo "Ubuntu: sudo apt update && sudo apt install -y systemd" >&2
                       echo "Fedora: sudo dnf install -y systemd" >&2 ;;
            ss) echo "Ubuntu: sudo apt update && sudo apt install -y iproute2" >&2
                echo "Fedora: sudo dnf install -y iproute" >&2 ;;
            python3) echo "Ubuntu: sudo apt update && sudo apt install -y python3 python3-venv" >&2
                     echo "Fedora: sudo dnf install -y python3 python3-devel" >&2 ;;
        esac
        return 1
    fi
}

atomic_render() {
    local template="$1" destination="$2" content temporary
    content="$(<"$template")"
    content="${content//@REPO_ROOT@/$REPO_ROOT}"
    content="${content//@DOTNET_BIN@/$DOTNET_BIN}"
    mkdir -p -- "$(dirname -- "$destination")"
    temporary="$(mktemp "${destination}.tmp.XXXXXX")"
    printf '%s\n' "$content" >"$temporary"
    chmod 0644 "$temporary"
    mv -f -- "$temporary" "$destination"
}

find_dotnet() {
    if [[ -n "${DSX_DOTNET_BIN:-}" ]]; then
        [[ -x "$DSX_DOTNET_BIN" ]] || {
            echo "DSX_DOTNET_BIN is not executable: $DSX_DOTNET_BIN" >&2
            return 1
        }
        printf '%s\n' "$DSX_DOTNET_BIN"
    elif command -v dotnet >/dev/null 2>&1; then
        command -v dotnet
    elif [[ -x "$HOME/.dotnet/dotnet" ]]; then
        printf '%s\n' "$HOME/.dotnet/dotnet"
    else
        echo "Missing .NET 8 SDK. Install it, or place dotnet at ~/.dotnet/dotnet." >&2
        return 1
    fi
}

runtime_identifier() {
    case "$(uname -m)" in
        x86_64|amd64) printf '%s\n' linux-x64 ;;
        aarch64|arm64) printf '%s\n' linux-arm64 ;;
        *) echo "Unsupported CPU architecture: $(uname -m)" >&2; return 1 ;;
    esac
}

case "$REPO_ROOT" in
    *'%'*|*'"'*|*'\'*|*$'\n'*)
        echo "Unsupported checkout path for systemd unit rendering: $REPO_ROOT" >&2
        echo "Move the repository to a path without %, double quotes, backslashes, or newlines." >&2
        exit 1
        ;;
esac

need_command git
need_command systemctl
need_command ss
if ! command -v uv >/dev/null 2>&1; then
    need_command python3
fi
DOTNET_BIN="$(find_dotnet)"

echo "[1/6] Initializing bundled Hefesto submodule..."
git -C "$REPO_ROOT" submodule update --init --recursive

if [[ "${DSX_BOOTSTRAP_SKIP_INSTALL:-0}" != 1 ]]; then
    echo "[2/6] Creating Hefesto virtual environment..."
    if command -v uv >/dev/null 2>&1; then
        uv venv --python python3 --allow-existing "$HEFESTO_ROOT/.venv"
        uv pip install --python "$HEFESTO_ROOT/.venv/bin/python" -e "$HEFESTO_ROOT"
    else
        need_command python3
        python3 -m venv "$HEFESTO_ROOT/.venv"
        "$HEFESTO_ROOT/.venv/bin/python" -m pip install --upgrade pip
        "$HEFESTO_ROOT/.venv/bin/python" -m pip install -e "$HEFESTO_ROOT"
    fi
else
    echo "[2/6] Skipping Hefesto install (test override)."
fi

if [[ "${DSX_BOOTSTRAP_SKIP_BUILD:-0}" != 1 ]]; then
    echo "[3/6] Publishing RacingDSX..."
    DOTNET_MAJOR="$($DOTNET_BIN --version | cut -d. -f1)"
    if [[ ! "$DOTNET_MAJOR" =~ ^[0-9]+$ ]] || (( DOTNET_MAJOR < 8 )); then
        echo "RacingDSX requires .NET SDK 8 or newer; found $($DOTNET_BIN --version)." >&2
        exit 1
    fi
    RID="$(runtime_identifier)"
    mkdir -p -- "$RACING_RUNTIME"
    "$DOTNET_BIN" publish "$RACING_PROJECT" -c Release -r "$RID" --self-contained false -o "$RACING_RUNTIME"
    if [[ ! -e "$RACING_RUNTIME/RacingDSX.json" ]]; then
        cp -- "$REPO_ROOT/config/RacingDSX.json" "$RACING_RUNTIME/RacingDSX.json"
    fi
else
    echo "[3/6] Skipping RacingDSX publish (test override)."
fi

echo "[4/6] Installing checkout-relative user services..."
atomic_render "$REPO_ROOT/systemd/hefesto-dualsense4unix.service.in" \
    "$USER_UNIT_DIR/hefesto-dualsense4unix.service"
atomic_render "$REPO_ROOT/systemd/racingdsx.service.in" \
    "$USER_UNIT_DIR/racingdsx.service"

echo "[5/6] Installing launcher..."
mkdir -p -- "$USER_BIN_DIR"
ln -sfn -- "$REPO_ROOT/start_dsx" "$USER_BIN_DIR/start_dsx"
systemctl --user daemon-reload

if (( INSTALL_UDEV )); then
    echo "Installing DualSense udev rules..."
    "$HEFESTO_ROOT/scripts/install_udev.sh"
fi

echo "[6/6] Bootstrap complete. Services were not enabled or started."
echo "Start the stack with: $USER_BIN_DIR/start_dsx start"
