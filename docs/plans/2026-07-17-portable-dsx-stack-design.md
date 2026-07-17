# Portable DSX Stack Design

**Date:** 2026-07-17
**Status:** Approved

## Objective

Make `dsx4unix` the single entry repository for the tested FH4 telemetry stack:

`FH4 UDP :5300 -> RacingDSX-Headless -> Hefesto UDP :6969 -> DualSense HID`

A user on another Linux machine must be able to clone `dsx4unix`, run one bootstrap command, and then control the complete stack through `start_dsx`.

## Source layout

- Keep RacingDSX-Headless in its existing directory.
- Add the tested Hefesto fork as the Git submodule `vendor/hefesto-dualsense4unix`.
- Pin the submodule to commit `4abcf9a1c74d1006be9b1288aa6298d66d2123cd`, which contains DSX hybrid/custom mode support and preserves RacingDSX force dynamics.
- Use the fork remote so the pinned commit is publicly retrievable by another checkout.

A normal `git clone` leaves submodule content uninitialized. The bootstrap command therefore runs `git submodule update --init --recursive` itself. `git clone --recurse-submodules` remains supported but is not required.

## Bootstrap

Add executable `scripts/bootstrap-stack.sh` and expose it as `start_dsx setup`.

The bootstrap is idempotent and performs these steps:

1. Resolve the repository root from the script location; never assume `~/code/dsx4unix`.
2. Initialize/update the Hefesto submodule to the commit recorded by the parent repository.
3. Check required commands and fail with exact install guidance when a prerequisite cannot be installed safely without elevated package-manager access.
4. Create a repository-local Hefesto virtual environment and install Hefesto from the bundled submodule using `uv` when available, with `python -m venv` plus pip as a fallback.
5. Publish RacingDSX-Headless for the detected Linux architecture using .NET 8.
6. Generate user-systemd units with absolute paths to this checkout.
7. Install/update the canonical `~/.local/bin/start_dsx` symlink.
8. Reload the user systemd manager.

Bootstrap must not enable or start either service implicitly. Hefesto must never be enabled for automatic login startup unless the user explicitly runs `start_dsx enable`.

## Runtime and services

- `hefesto-dualsense4unix.service` runs the executable from `vendor/hefesto-dualsense4unix/.venv` and uses the submodule as its working directory.
- `racingdsx.service` runs the published native RacingDSX executable from this checkout.
- RacingDSX requires and starts after Hefesto.
- `start_dsx start` starts Hefesto first, waits for UDP `6969`, then starts RacingDSX and waits for UDP `5300`.
- A post-start stability window rejects listeners from processes that immediately crash.
- If units, virtualenv, submodule, or published executable are missing, `start_dsx` prints the exact setup command.

## Portability and generated files

Do not commit machine-specific virtualenvs, runtime logs, Wine prefixes, downloaded archives/installers, Python caches, .NET `obj` intermediates, or publish output. Commit source, templates, tests, documentation, and the submodule pointer.

Existing unrelated/generated working-tree files are preserved locally and excluded from the portable commit rather than deleted.

## Testing

Add regression coverage for:

- An ordinary clone with an uninitialized submodule invoking bootstrap.
- Path generation from an arbitrary checkout location and HOME.
- Idempotent reinstallation of units and launcher link.
- No implicit service enable/start during bootstrap.
- Launcher setup diagnostics when prerequisites/artifacts are absent.
- Shell syntax and static checks.

Retain and run:

- Complete bundled Hefesto tests and Ruff checks.
- RacingDSX parity tests.
- dsx4unix Python tests.
- .NET Release publish/build.

## Live verification

After clean-environment bootstrap verification:

1. Clear diagnostic effects with a valid `Off` command.
2. Restart the managed stack.
3. Confirm both services are active.
4. Confirm UDP listeners on `6969` and `5300` remain stable.
5. Confirm the connected DualSense is visible to the Hefesto process/logs.

## Commit scope

The final dsx4unix commit includes only:

- `.gitmodules` and the pinned Hefesto submodule pointer.
- Bootstrap implementation and service templates.
- Launcher changes.
- Tests and documentation.
- Intentional portable source/config updates.

Generated and unrelated working-tree changes remain unstaged. Push the completed commit to `origin/main` after all verification passes.
