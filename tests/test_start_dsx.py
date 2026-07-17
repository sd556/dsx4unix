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
