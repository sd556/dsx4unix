import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO_ROOT / "scripts" / "bootstrap-stack.sh"


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(0o755)


def _fixture_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "checkout with spaces"
    home = tmp_path / "home with spaces"
    bin_dir = tmp_path / "bin"
    (repo / "systemd").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / ".runtime" / "racingdsx").mkdir(parents=True)
    home.mkdir()

    for template in (
        "hefesto-dualsense4unix.service.in",
        "racingdsx.service.in",
    ):
        shutil.copy2(REPO_ROOT / "systemd" / template, repo / "systemd" / template)
    shutil.copy2(REPO_ROOT / "start_dsx", repo / "start_dsx")
    (repo / "start_dsx").chmod(0o755)
    _write_executable(repo / ".runtime" / "racingdsx" / "RacingDSX", "#!/bin/sh\n")

    _write_executable(
        bin_dir / "git",
        "#!/bin/sh\n"
        'printf "git %s\\n" "$*" >> "$CALL_LOG"\n'
        'mkdir -p "$DSX_REPO_ROOT/vendor/hefesto-dualsense4unix"\n',
    )
    _write_executable(
        bin_dir / "systemctl",
        "#!/bin/sh\n"
        'printf "systemctl %s\\n" "$*" >> "$CALL_LOG"\n',
    )
    return repo, home, bin_dir


def _run_bootstrap(repo: Path, home: Path, bin_dir: Path, call_log: Path):
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CALL_LOG": str(call_log),
            "DSX_REPO_ROOT": str(repo),
            "DSX_BOOTSTRAP_SKIP_INSTALL": "1",
            "DSX_BOOTSTRAP_SKIP_BUILD": "1",
            "DSX_DOTNET_BIN": "/bin/true",
        }
    )
    return subprocess.run(
        [str(BOOTSTRAP)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_bootstrap_initializes_submodule_renders_units_without_starting_services(tmp_path):
    repo, home, bin_dir = _fixture_repo(tmp_path)
    call_log = tmp_path / "calls.log"

    result = _run_bootstrap(repo, home, bin_dir, call_log)

    assert result.returncode == 0, result.stderr
    calls = call_log.read_text()
    assert "submodule update --init --recursive" in calls
    assert "systemctl --user daemon-reload" in calls
    assert " enable " not in f" {calls} "
    assert " start " not in f" {calls} "

    hefesto_unit = (home / ".config/systemd/user/hefesto-dualsense4unix.service").read_text()
    racing_unit = (home / ".config/systemd/user/racingdsx.service").read_text()
    assert str(repo / "vendor/hefesto-dualsense4unix") in hefesto_unit
    assert str(repo / ".runtime/racingdsx") in racing_unit
    assert 'ExecStart="/bin/true"' in racing_unit
    assert f'WorkingDirectory={repo / "vendor/hefesto-dualsense4unix"}' in hefesto_unit
    assert f'WorkingDirectory={repo / ".runtime/racingdsx"}' in racing_unit
    assert "WorkingDirectory=\"" not in hefesto_unit + racing_unit
    assert (home / ".local/bin/start_dsx").resolve() == repo / "start_dsx"


def test_bootstrap_is_idempotent(tmp_path):
    repo, home, bin_dir = _fixture_repo(tmp_path)
    call_log = tmp_path / "calls.log"

    first = _run_bootstrap(repo, home, bin_dir, call_log)
    units_before = {
        path.name: path.read_text()
        for path in (home / ".config/systemd/user").iterdir()
    }
    second = _run_bootstrap(repo, home, bin_dir, call_log)
    units_after = {
        path.name: path.read_text()
        for path in (home / ".config/systemd/user").iterdir()
    }

    assert first.returncode == second.returncode == 0
    assert units_after == units_before
    assert (home / ".local/bin/start_dsx").resolve() == repo / "start_dsx"


def test_bootstrap_rejects_paths_systemd_cannot_render_safely(tmp_path):
    checkout = tmp_path / "portable%checkout"
    checkout.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "DSX_REPO_ROOT": str(checkout),
            "DSX_BOOTSTRAP_SKIP_INSTALL": "1",
            "DSX_BOOTSTRAP_SKIP_BUILD": "1",
            "DSX_DOTNET_BIN": "/bin/true",
        }
    )

    result = subprocess.run(
        [str(BOOTSTRAP)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Unsupported checkout path" in result.stderr
