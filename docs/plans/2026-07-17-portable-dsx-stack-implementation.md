# Portable DSX Stack Implementation Plan

> Execute in order with tests first for each behavior change. Preserve existing unrelated/generated working-tree files.

**Goal:** A normal clone of dsx4unix can bootstrap and run the tested RacingDSX + Hefesto stack from this repository.

**Architecture:** Hefesto is pinned as a Git submodule under `vendor/`. An idempotent shell bootstrap initializes it, builds repo-local runtimes, renders absolute-path user-systemd units, and installs the canonical launcher link. `start_dsx` remains the only runtime control surface.

**Tooling:** Bash, Git submodules, uv/Python venv, .NET 8, systemd user units, pytest.

## Task 1: Add the tested Hefesto submodule

**Files:** `.gitmodules`, `vendor/hefesto-dualsense4unix`

1. Add `git@github.com:sd556/hefesto-dualsense4unix.git` at `vendor/hefesto-dualsense4unix` without modifying the sibling checkout.
2. Pin it to `4abcf9a1c74d1006be9b1288aa6298d66d2123cd`.
3. Verify `git submodule status` and the checked-out commit.

## Task 2: Add failing bootstrap regression tests

**Files:** `tests/test_stack_bootstrap.py`, `tests/test_start_dsx.py`

1. Add a shell test harness with temporary repository/HOME directories and stub binaries.
2. Test unit rendering uses the actual checkout path rather than `~/code/dsx4unix`.
3. Test ordinary uninitialized submodule flow invokes `git submodule update --init --recursive`.
4. Test bootstrap reloads but never enables/starts services.
5. Test rerunning bootstrap is idempotent.
6. Test `start_dsx setup` delegates to the bootstrap script.
7. Test missing installed artifacts produce the exact setup command.
8. Run focused tests and confirm RED failures due to missing implementation.

## Task 3: Implement service templates and bootstrap

**Files:** `systemd/hefesto-dualsense4unix.service.in`, `systemd/racingdsx.service.in`, `scripts/bootstrap-stack.sh`, `.gitignore`

1. Add templates with repository-root placeholders.
2. Resolve repository root and user paths safely, including spaces.
3. Initialize the submodule.
4. Validate Git, systemctl, ss, Python/uv, and .NET 8 prerequisites.
5. Create/install Hefesto’s `.venv` from its own pyproject.
6. Publish RacingDSX to a repository-local ignored runtime directory.
7. Render and atomically install both user units.
8. Atomically refresh `~/.local/bin/start_dsx`.
9. Reload systemd only.
10. Expand ignores for generated runtime artifacts without deleting existing files.
11. Run focused tests until GREEN.

## Task 4: Integrate launcher setup and diagnostics

**File:** `start_dsx`, `tests/test_start_dsx.py`

1. Add `setup` to usage and dispatch.
2. Add a prerequisite check before service operations.
3. Preserve existing ordered startup and stability checks.
4. Use the repository-resolved bootstrap path.
5. Run launcher tests and shell syntax checks.

## Task 5: Update documentation

**Files:** `README.md`

1. Replace the external Hefesto install instructions with one-repository bootstrap commands.
2. Document normal clone and recursive clone variants.
3. Document that bootstrap does not enable autostart.
4. Document `setup/start/stop/restart/status/logs/enable/disable` commands.
5. Document supported distro prerequisites and exact commands.

## Task 6: Clean-clone bootstrap verification

1. Create a fresh temporary clone of the local dsx4unix Git repository with no initialized submodules.
2. Run bootstrap in a temporary HOME with controlled service stubs where host service mutation is undesirable.
3. Verify submodule initialization, venv, .NET publish, rendered units, symlink, and idempotent second run.
4. Verify no enable/start calls occurred.

## Task 7: Full static and automated verification

1. Run `bash -n start_dsx scripts/bootstrap-stack.sh`.
2. Run all dsx4unix pytest tests.
3. Run complete Hefesto pytest suite and Ruff against bundled source.
4. Run RacingDSX parity tests.
5. Run .NET Release build/publish and require zero errors.
6. Inspect final diff and ensure generated/unrelated files are not staged.

## Task 8: Live runtime verification

1. Stop RacingDSX while clearing both triggers with valid `Off` instructions.
2. Run the real bootstrap against this checkout.
3. Restart with `start_dsx restart`.
4. Verify active services and stable UDP listeners on 6969/5300.
5. Verify DualSense discovery in device/service diagnostics.

## Task 9: Commit and push

1. Stage only the approved portable-stack files and submodule pointer.
2. Run `git diff --cached --check` and inspect staged status/diff.
3. Commit with a focused message.
4. Push `main` to `origin`.
5. Verify local HEAD equals `origin/main` and report tests/runtime evidence.
