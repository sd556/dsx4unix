import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_launcher(tmp_path: Path) -> Path:
    checkout = tmp_path / "portable checkout"
    checkout.mkdir()
    launcher = checkout / "start_dsx"
    shutil.copy2(REPO_ROOT / "start_dsx", launcher)
    launcher.chmod(0o755)
    return launcher


def test_setup_delegates_to_repo_bootstrap(tmp_path):
    launcher = _copy_launcher(tmp_path)
    marker = tmp_path / "setup-called"
    bootstrap = launcher.parent / "scripts/bootstrap-stack.sh"
    bootstrap.parent.mkdir()
    bootstrap.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" > "$SETUP_MARKER"\n'
    )
    bootstrap.chmod(0o755)
    env = os.environ.copy()
    env["SETUP_MARKER"] = str(marker)

    result = subprocess.run(
        [str(launcher), "setup", "--example"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert marker.read_text().strip() == "--example"


def test_start_without_installed_stack_reports_exact_setup_command(tmp_path):
    launcher = _copy_launcher(tmp_path)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(fake_home)

    result = subprocess.run(
        [str(launcher), "start"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0
    assert f"{launcher} setup" in result.stderr


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(0o755)


def _installed_launcher_fixture(tmp_path: Path, stack_active: bool):
    checkout = tmp_path / "installed checkout with spaces"
    home = tmp_path / "home with spaces"
    bin_dir = tmp_path / "fake bin"
    call_log = tmp_path / "systemctl-calls.log"
    helper_log = tmp_path / "profile-helper.log"
    service_state = tmp_path / "services-started"

    checkout.mkdir()
    home.mkdir()
    launcher = checkout / "start_dsx"
    shutil.copy2(REPO_ROOT / "start_dsx", launcher)
    launcher.chmod(0o755)

    _write_executable(
        checkout / "vendor/hefesto-dualsense4unix/.venv/bin/hefesto-dualsense4unix",
        "#!/bin/sh\nexit 0\n",
    )
    runtime = checkout / ".runtime/racingdsx"
    runtime.mkdir(parents=True)
    (runtime / "RacingDSX.dll").write_bytes(b"fixture")
    (runtime / "RacingDSX.json").write_text("{}")

    helper = checkout / "scripts/apply-trigger-profile.py"
    _write_executable(
        helper,
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['PROFILE_HELPER_LOG']).write_text(' '.join(sys.argv[1:]))\n"
        "raise SystemExit(int(os.environ.get('PROFILE_HELPER_EXIT', '0')))\n",
    )
    preset = checkout / "config/trigger-presets/high.json"
    preset.parent.mkdir(parents=True)
    preset.write_text("{}")

    unit_dir = home / ".config/systemd/user"
    unit_dir.mkdir(parents=True)
    for unit in ("hefesto-dualsense4unix.service", "racingdsx.service"):
        (unit_dir / unit).write_text(f"WorkingDirectory={checkout}\n")

    _write_executable(
        bin_dir / "systemctl",
        "#!/bin/sh\n"
        "printf 'systemctl %s\\n' \"$*\" >> \"$CALL_LOG\"\n"
        "case \" $* \" in\n"
        "  *' --quiet is-active '*)\n"
        "    [ \"${STACK_ACTIVE:-0}\" = 1 ] && exit 0\n"
        "    [ -e \"$SYSTEMCTL_STATE\" ] && exit 0\n"
        "    exit 3\n"
        "    ;;\n"
        "  *' start '*) touch \"$SYSTEMCTL_STATE\" ;;\n"
        "esac\n"
        "exit 0\n",
    )
    _write_executable(
        bin_dir / "ss",
        "#!/bin/sh\n"
        "printf 'UNCONN 0 0 0.0.0.0:5300 0.0.0.0:*\\n'\n"
        "printf 'UNCONN 0 0 127.0.0.1:6969 0.0.0.0:*\\n'\n",
    )
    _write_executable(bin_dir / "sleep", "#!/bin/sh\nexit 0\n")

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CALL_LOG": str(call_log),
            "PROFILE_HELPER_LOG": str(helper_log),
            "SYSTEMCTL_STATE": str(service_state),
            "STACK_ACTIVE": "1" if stack_active else "0",
        }
    )
    return launcher, env, call_log, helper_log


def test_high_active_stack_applies_profile_and_restarts_only_racingdsx(tmp_path):
    launcher, env, call_log, helper_log = _installed_launcher_fixture(tmp_path, stack_active=True)
    result = subprocess.run([str(launcher), "high"], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "high" in helper_log.read_text()
    calls = call_log.read_text()
    assert "restart racingdsx.service" in calls
    assert "restart hefesto-dualsense4unix.service" not in calls
    assert "stop hefesto-dualsense4unix.service" not in calls


def test_normal_active_stack_uses_same_racing_only_refresh(tmp_path):
    launcher, env, call_log, helper_log = _installed_launcher_fixture(tmp_path, stack_active=True)
    result = subprocess.run([str(launcher), "normal"], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "normal" in helper_log.read_text()
    calls = call_log.read_text()
    assert "restart racingdsx.service" in calls
    assert "restart hefesto-dualsense4unix.service" not in calls


def test_profile_selection_starts_stack_when_not_fully_active(tmp_path):
    launcher, env, call_log, _ = _installed_launcher_fixture(tmp_path, stack_active=False)
    result = subprocess.run([str(launcher), "high"], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    calls = call_log.read_text()
    assert "start hefesto-dualsense4unix.service" in calls
    assert "start racingdsx.service" in calls


def test_profile_helper_failure_does_not_touch_services(tmp_path):
    launcher, env, call_log, _ = _installed_launcher_fixture(tmp_path, stack_active=True)
    env["PROFILE_HELPER_EXIT"] = "1"
    result = subprocess.run([str(launcher), "high"], env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert not call_log.exists() or "restart" not in call_log.read_text()
