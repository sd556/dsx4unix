# High Adaptive-Trigger Profile Design

**Date:** 2026-07-17
**Status:** Approved

## Objective

Add reversible launcher commands that provide maximum adaptive-trigger feedback on both DualSense triggers:

- `start_dsx high` applies an aggressive Forza profile to R2 throttle and L2 brake feedback.
- `start_dsx normal` restores the exact R2 and L2 settings that existed immediately before `high` was first selected.

The implementation must preserve unrelated RacingDSX configuration and must not restart Hefesto when the managed stack is already running.

## Selected approach

Use a source-controlled partial `high` preset plus a small configuration helper. The helper edits only `Profiles.Forza.throttleSettings` and `Profiles.Forza.brakeSettings` in `.runtime/racingdsx/RacingDSX.json`.

On the first transition from normal to high, it snapshots only the trigger keys that the high preset overrides. The snapshot is stored in `.runtime/racingdsx/trigger-profile-state.json`. Repeated `high` calls reapply the high preset but never replace the saved normal snapshot. `normal` restores the saved keys and removes the state file only after the configuration has been written successfully.

This is preferred over complete duplicate profiles because it avoids configuration drift, and over a C# runtime multiplier because it keeps tuning explicit without changing telemetry parsing behavior.

## High preset

The initial high preset targets the existing Forza profile and affects both triggers.

### R2 — throttle

| Setting | High value | Effect |
|---|---:|---|
| `GripLossValue` | `0.20` | Enter grip-loss feedback much earlier than normal `0.60`. |
| `EffectIntensity` | `3` | Increase vibration, stiffness, and resistance output. |
| `TurnAccelerationScale` | `1.00` | Make lateral acceleration during a drift contribute four times as strongly as normal `0.25`. |
| `ForwardAccelerationScale` | `1.50` | Increase longitudinal acceleration contribution. |
| `AccelerationLimit` | `5` | Reach peak stiffness/resistance sooner than normal `10`. |
| `VibrationModeStart` | `1` | Permit vibration with almost any nonzero throttle input. |
| `MinVibration` | `1` | Avoid suppressing low-frequency grip-loss feedback. |
| `MaxVibration` | `75` | Allow up to `225` after intensity, below the byte maximum `255`. |
| `VibrationSmoothing` | `1` | React immediately to telemetry changes. |
| `MinStiffness` | `25` | Strong initial vibration stiffness. |
| `MaxStiffness` | `35` | Allow up to `105` after intensity. |
| `MinResistance` | `2` | Heavy baseline resistance from initial pull. |
| `MaxResistance` | `3` | Produce effective resistance `6–8` after intensity and protocol clamping. |
| `ResistanceSmoothing` | `1` | React immediately to acceleration changes. |

### L2 — brake

| Setting | High value | Effect |
|---|---:|---|
| `GripLossValue` | `0.01` | Enter lock-up/grip-loss feedback earlier than normal `0.05`, while retaining RacingDSX's existing brake-input safety gate. |
| `EffectIntensity` | `3` | Increase vibration, stiffness, and resistance output. |
| `VibrationStart` | `0` | Start custom brake vibration at the beginning of trigger travel. |
| `MinVibration` | `1` | Avoid suppressing low-frequency lock-up feedback. |
| `MaxVibration` | `75` | Allow up to `225` after intensity, below the byte maximum `255`. |
| `VibrationSmoothing` | `1` | React immediately to telemetry changes. |
| `MinStiffness` | `25` | Strong vibration stiffness throughout braking. |
| `MaxStiffness` | `35` | Allow up to `105` after intensity. |
| `MinResistance` | `2` | Heavy baseline resistance from initial pull. |
| `MaxResistance` | `3` | Produce effective resistance `6–8` after intensity and protocol clamping. |
| `ResistanceSmoothing` | `1` | React immediately to brake changes. |

`TriggerMode` remains unchanged. A user who disabled adaptive feedback will not have it silently enabled by profile selection.

## Command behavior

### `start_dsx high`

1. Run the existing setup validation.
2. Parse and validate the runtime RacingDSX JSON and high-preset JSON before writing anything.
3. Verify the `Forza`, `throttleSettings`, and `brakeSettings` objects and every preset key exist with compatible JSON value types.
4. If no high-profile state exists, atomically save the currently selected trigger values as the normal snapshot.
5. Atomically apply the high values to the runtime configuration.
6. If both managed services are already active, restart only `racingdsx.service` and verify UDP `5300` plus the existing stability window. Hefesto and its controller handle remain untouched.
7. If the stack is not fully active, use the existing `start_all` path.
8. Print the selected profile and the runtime configuration path.

Repeated calls are idempotent and do not overwrite the normal snapshot.

### `start_dsx normal`

1. Run the existing setup validation.
2. If no high-profile state exists, report that normal is already selected and leave the configuration unchanged.
3. Parse and validate both runtime configuration and saved state before writing anything.
4. Atomically restore only the saved R2/L2 keys; preserve all unrelated settings, including edits made while high was active.
5. Remove the state file only after successful restoration.
6. Use the same RacingDSX-only restart behavior when the stack is active, or the existing `start_all` path otherwise.
7. Print the selected profile and runtime configuration path.

Repeated calls are idempotent.

## Configuration safety

- Runtime config: `.runtime/racingdsx/RacingDSX.json`.
- Preset source: `config/trigger-presets/high.json`.
- Reversible state: `.runtime/racingdsx/trigger-profile-state.json`.
- JSON writes use a temporary file in the destination directory, flush and `fsync`, then `os.replace`.
- Invalid/missing config objects, malformed JSON, incompatible value types, or invalid saved state cause a nonzero exit before service changes.
- The helper never edits `config/RacingDSX.json`, complete profiles, DSX ports, executable names, or the DiRT profile.
- Runtime state remains untracked and is excluded from Git.

## Components

- `config/trigger-presets/high.json`: source-controlled partial R2/L2 high values.
- `scripts/apply-trigger-profile.py`: validates, snapshots, atomically applies, and restores trigger values.
- `start_dsx`: exposes `high` and `normal`, invokes the helper, and safely refreshes RacingDSX.
- `tests/test_trigger_profiles.py`: helper regression coverage.
- `tests/test_start_dsx.py`: launcher dispatch and service-lifecycle regression coverage.
- `README.md`: concise command documentation and high-profile safety notes.

No changes are required in `Parser.cs` or Hefesto.

## Testing

Follow RED-GREEN-REFACTOR. Regression tests cover:

- `high` updates every approved R2 and L2 key.
- The first `high` call snapshots exact normal values.
- Repeated `high` calls preserve that original snapshot.
- `normal` restores exact trigger values and leaves unrelated config edits intact.
- Repeated `normal` calls are harmless.
- Missing objects/keys, type mismatches, malformed JSON, and malformed state fail without changing config or invoking systemd.
- Atomic replacement does not leave a partially written destination.
- Paths containing spaces work.
- Existing launcher commands and no-argument `start` behavior remain unchanged.
- An active stack restarts RacingDSX only; a stopped/partial stack follows existing startup behavior.
- Shell syntax, focused Python tests, the complete relevant test suite, and `git diff --check` pass.

## Live verification

After automated verification and with explicit awareness that trigger forces will be strong:

1. Confirm the controller remains connected over Bluetooth.
2. Record hashes of the live trigger settings and saved normal snapshot.
3. Run `start_dsx high`; confirm only RacingDSX changes PID and both UDP listeners remain healthy.
4. Inspect the live JSON and confirm both R2 and L2 high values are active.
5. Run `start_dsx normal`; confirm both trigger sections exactly match the saved pre-high values.
6. Confirm Hefesto retained its PID/controller handle and no Bluetooth, CRC, HIDP, or disconnect errors occurred.

Live gameplay feel remains a hardware acceptance test; automated tests verify configuration and lifecycle behavior.

## Non-goals

- Changing telemetry formulas in `Parser.cs`.
- Changing Hefesto HID translation or Bluetooth pacing.
- Tuning DiRT profiles.
- Automatically enabling disabled trigger modes.
- Persistently replacing the user's normal settings with repository defaults.
