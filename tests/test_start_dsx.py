import json
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


def _installed_launcher_fixture(
    tmp_path: Path,
    *,
    hefesto_active: bool = True,
    racing_active: bool = True,
    restart_stable: bool = True,
    post_start_failure: str = "",
):
    checkout = tmp_path / "installed checkout with spaces"
    home = tmp_path / "home with spaces"
    bin_dir = tmp_path / "fake bin"
    call_log = tmp_path / "systemctl-calls.log"
    helper_log = tmp_path / "profile-helper.log"
    service_state = tmp_path / "service state"

    checkout.mkdir(parents=True)
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
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['PROFILE_HELPER_LOG']).write_text(json.dumps(sys.argv[1:]))\n"
        "raise SystemExit(int(os.environ.get('PROFILE_HELPER_EXIT', '0')))\n",
    )
    preset = checkout / "config/trigger-presets/high.json"
    preset.parent.mkdir(parents=True)
    preset.write_text("{}")

    unit_dir = home / ".config/systemd/user"
    unit_dir.mkdir(parents=True)
    for unit in ("hefesto-dualsense4unix.service", "racingdsx.service"):
        (unit_dir / unit).write_text(f"WorkingDirectory={checkout}\n")

    service_state.mkdir()
    if hefesto_active:
        (service_state / "hefesto-dualsense4unix.service").touch()
    if racing_active:
        (service_state / "racingdsx.service").touch()

    _write_executable(
        bin_dir / "systemctl",
        "#!/bin/sh\n"
        "printf 'systemctl %s\\n' \"$*\" >> \"$CALL_LOG\"\n"
        "command=\n"
        "service=\n"
        "for arg in \"$@\"; do\n"
        "  case \"$arg\" in\n"
        "    is-active|start|restart|stop) command=$arg ;;\n"
        "    *.service) service=$arg ;;\n"
        "  esac\n"
        "done\n"
        "case \"$command\" in\n"
        "  is-active)\n"
        "    if [ \"$service\" = racingdsx.service ] && [ -e \"$SYSTEMCTL_STATE/restarted-racingdsx\" ] && [ \"$RESTART_STABLE\" != 1 ]; then\n"
        "      exit 3\n"
        "    fi\n"
        "    if [ -n \"$POST_START_FAILURE\" ] && [ \"$service\" = \"$POST_START_FAILURE\" ] && [ -e \"$SYSTEMCTL_STATE/started-racingdsx.service\" ]; then\n"
        "      exit 3\n"
        "    fi\n"
        "    [ -e \"$SYSTEMCTL_STATE/$service\" ] && exit 0\n"
        "    exit 3\n"
        "    ;;\n"
        "  start)\n"
        "    touch \"$SYSTEMCTL_STATE/$service\" \"$SYSTEMCTL_STATE/started-$service\"\n"
        "    ;;\n"
        "  restart)\n"
        "    touch \"$SYSTEMCTL_STATE/$service\" \"$SYSTEMCTL_STATE/restarted-racingdsx\"\n"
        "    ;;\n"
        "  stop)\n"
        "    for arg in \"$@\"; do\n"
        "      case \"$arg\" in *.service) rm -f \"$SYSTEMCTL_STATE/$arg\" ;; esac\n"
        "    done\n"
        "    ;;\n"
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
            "RESTART_STABLE": "1" if restart_stable else "0",
            "POST_START_FAILURE": post_start_failure,
        }
    )
    return launcher, env, call_log, helper_log


def test_high_active_stack_applies_profile_and_restarts_only_racingdsx(tmp_path):
    launcher, env, call_log, helper_log = _installed_launcher_fixture(tmp_path)
    result = subprocess.run([str(launcher), "high"], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    checkout = launcher.parent
    assert json.loads(helper_log.read_text()) == [
        "high",
        "--config",
        str(checkout / ".runtime/racingdsx/RacingDSX.json"),
        "--preset",
        str(checkout / "config/trigger-presets/high.json"),
        "--state",
        str(checkout / ".runtime/racingdsx/trigger-profile-state.json"),
    ]
    calls = call_log.read_text()
    assert "restart racingdsx.service" in calls
    assert "restart hefesto-dualsense4unix.service" not in calls
    assert "stop hefesto-dualsense4unix.service" not in calls


def test_normal_active_stack_uses_same_racing_only_refresh(tmp_path):
    launcher, env, call_log, helper_log = _installed_launcher_fixture(tmp_path)
    result = subprocess.run([str(launcher), "normal"], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    checkout = launcher.parent
    assert json.loads(helper_log.read_text()) == [
        "normal",
        "--config",
        str(checkout / ".runtime/racingdsx/RacingDSX.json"),
        "--preset",
        str(checkout / "config/trigger-presets/high.json"),
        "--state",
        str(checkout / ".runtime/racingdsx/trigger-profile-state.json"),
    ]
    calls = call_log.read_text()
    assert "restart racingdsx.service" in calls
    assert "restart hefesto-dualsense4unix.service" not in calls


def test_profile_selection_starts_stack_when_only_hefesto_is_active(tmp_path):
    launcher, env, call_log, _ = _installed_launcher_fixture(
        tmp_path, hefesto_active=True, racing_active=False
    )
    result = subprocess.run([str(launcher), "high"], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    calls = call_log.read_text()
    assert "start hefesto-dualsense4unix.service" in calls
    assert "start racingdsx.service" in calls


def test_profile_selection_starts_stack_when_only_racingdsx_is_active(tmp_path):
    launcher, env, call_log, _ = _installed_launcher_fixture(
        tmp_path, hefesto_active=False, racing_active=True
    )
    result = subprocess.run([str(launcher), "normal"], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    calls = call_log.read_text()
    assert "start hefesto-dualsense4unix.service" in calls
    assert "start racingdsx.service" in calls


def test_active_stack_restart_stability_failure_is_reported_without_stopping_hefesto(tmp_path):
    launcher, env, call_log, _ = _installed_launcher_fixture(tmp_path, restart_stable=False)
    result = subprocess.run([str(launcher), "high"], env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert "profile switch failed stability check" in result.stderr
    calls = call_log.read_text()
    assert "restart racingdsx.service" in calls
    assert "stop hefesto-dualsense4unix.service" not in calls


def test_partial_stack_start_stability_failure_cleans_up_both_services(tmp_path):
    launcher, env, call_log, _ = _installed_launcher_fixture(
        tmp_path,
        hefesto_active=True,
        racing_active=False,
        post_start_failure="racingdsx.service",
    )
    result = subprocess.run([str(launcher), "high"], env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert "failed stability check" in result.stderr
    assert "stop racingdsx.service hefesto-dualsense4unix.service" in call_log.read_text()


def test_profile_helper_failure_does_not_touch_services(tmp_path):
    launcher, env, call_log, _ = _installed_launcher_fixture(tmp_path)
    env["PROFILE_HELPER_EXIT"] = "1"
    result = subprocess.run([str(launcher), "high"], env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert not call_log.exists()


def test_high_and_normal_reject_trailing_arguments_before_helper_or_systemctl(tmp_path):
    for command in ("high", "normal"):
        launcher, env, call_log, helper_log = _installed_launcher_fixture(tmp_path / command)
        result = subprocess.run(
            [str(launcher), command, "unexpected"], env=env, text=True, capture_output=True
        )
        assert result.returncode == 2
        assert f"{command} does not accept additional arguments" in result.stderr
        assert not helper_log.exists()
        assert not call_log.exists()
