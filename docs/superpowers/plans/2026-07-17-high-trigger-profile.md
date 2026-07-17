# High Adaptive-Trigger Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reversible `start_dsx high` and `start_dsx normal` commands that apply maximum feedback to both Forza triggers and restore the exact prior trigger settings.

**Architecture:** A source-controlled partial high preset contains only approved R2/L2 keys. A Python helper validates and atomically patches the live RacingDSX JSON while preserving a runtime snapshot of the original trigger values. The Bash launcher invokes the helper and refreshes RacingDSX without restarting Hefesto when the stack is already healthy.

**Tech Stack:** Bash, Python 3.11+ standard library, JSON, systemd user services, pytest.

## Global Constraints

- `start_dsx high` applies aggressive feedback to both R2 and L2.
- `start_dsx normal` restores the exact selected trigger values that existed before the first `high` transition.
- Do not overwrite the saved normal snapshot on repeated `high` calls.
- Preserve unrelated RacingDSX configuration, the DiRT profile, and edits made while high is active.
- Do not edit `config/RacingDSX.json` at runtime; the live file is `.runtime/racingdsx/RacingDSX.json`.
- Do not change `Parser.cs`, Hefesto HID translation, or Bluetooth pacing.
- When both services are active, restart only `racingdsx.service`; never restart Hefesto merely to switch a trigger profile.
- Preserve all pre-existing generated files, submodule changes, and untracked files.
- Follow RED-GREEN-REFACTOR and obtain fresh verification before claiming completion.

---

## File map

- Create `config/trigger-presets/high.json`: reviewed partial high values for Forza R2/L2.
- Create `scripts/apply-trigger-profile.py`: config/state validation, snapshot, atomic apply, exact restore.
- Create `tests/test_trigger_profiles.py`: black-box and failure-safety coverage for the helper.
- Modify `start_dsx`: add `high`/`normal` dispatch and RacingDSX-only refresh.
- Modify `tests/test_start_dsx.py`: launcher argument and service-lifecycle coverage.
- Modify `README.md`: user-facing command, strength, restore, and Bluetooth-lifecycle documentation.
- Retain `docs/plans/2026-07-17-high-trigger-profile-design.md`: approved design record.

---

### Task 1: Define the high preset through a failing contract test

**Files:**
- Create: `tests/test_trigger_profiles.py`
- Create: `config/trigger-presets/high.json`

**Interfaces:**
- Consumes: approved values in `docs/plans/2026-07-17-high-trigger-profile-design.md`.
- Produces: JSON object with exact top-level keys `throttleSettings` and `brakeSettings` for the helper in Task 2.

- [ ] **Step 1: Write the failing preset contract test**

Create `tests/test_trigger_profiles.py` with this initial content:

```python
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / "scripts" / "apply-trigger-profile.py"
PRESET = REPO_ROOT / "config" / "trigger-presets" / "high.json"

EXPECTED_HIGH = {
    "throttleSettings": {
        "GripLossValue": 0.20,
        "EffectIntensity": 3,
        "TurnAccelerationScale": 1.00,
        "ForwardAccelerationScale": 1.50,
        "AccelerationLimit": 5,
        "VibrationModeStart": 1,
        "MinVibration": 1,
        "MaxVibration": 75,
        "VibrationSmoothing": 1,
        "MinStiffness": 25,
        "MaxStiffness": 35,
        "MinResistance": 2,
        "MaxResistance": 3,
        "ResistanceSmoothing": 1,
    },
    "brakeSettings": {
        "GripLossValue": 0.01,
        "EffectIntensity": 3,
        "VibrationStart": 0,
        "MinVibration": 1,
        "MaxVibration": 75,
        "VibrationSmoothing": 1,
        "MinStiffness": 25,
        "MaxStiffness": 35,
        "MinResistance": 2,
        "MaxResistance": 3,
        "ResistanceSmoothing": 1,
    },
}


def test_high_preset_matches_approved_values():
    assert json.loads(PRESET.read_text()) == EXPECTED_HIGH
```

- [ ] **Step 2: Run the contract test and verify RED**

Run:

```bash
cd /home/deck/code/dsx4unix && python3 -m pytest tests/test_trigger_profiles.py::test_high_preset_matches_approved_values -q
```

Expected: FAIL because `config/trigger-presets/high.json` does not exist.

- [ ] **Step 3: Add the exact preset**

Create `config/trigger-presets/high.json`:

```json
{
  "throttleSettings": {
    "GripLossValue": 0.2,
    "EffectIntensity": 3,
    "TurnAccelerationScale": 1.0,
    "ForwardAccelerationScale": 1.5,
    "AccelerationLimit": 5,
    "VibrationModeStart": 1,
    "MinVibration": 1,
    "MaxVibration": 75,
    "VibrationSmoothing": 1,
    "MinStiffness": 25,
    "MaxStiffness": 35,
    "MinResistance": 2,
    "MaxResistance": 3,
    "ResistanceSmoothing": 1
  },
  "brakeSettings": {
    "GripLossValue": 0.01,
    "EffectIntensity": 3,
    "VibrationStart": 0,
    "MinVibration": 1,
    "MaxVibration": 75,
    "VibrationSmoothing": 1,
    "MinStiffness": 25,
    "MaxStiffness": 35,
    "MinResistance": 2,
    "MaxResistance": 3,
    "ResistanceSmoothing": 1
  }
}
```

- [ ] **Step 4: Run the contract test and verify GREEN**

Run the Step 2 command again. Expected: `1 passed`.

---

### Task 2: Implement exact snapshot, high apply, and normal restore

**Files:**
- Modify: `tests/test_trigger_profiles.py`
- Create: `scripts/apply-trigger-profile.py`

**Interfaces:**
- Consumes: `high|normal`, `--config PATH`, `--preset PATH`, and `--state PATH`.
- Produces: exit `0` and a concise status line on success; nonzero exit and `error: ...` on stderr on validation/write failure.
- State schema: `{"version": 1, "active": "high", "normal": {"throttleSettings": {...}, "brakeSettings": {...}}}`.

- [ ] **Step 1: Add failing behavior tests**

Append helper utilities and tests to `tests/test_trigger_profiles.py`:

```python
def _normal_config():
    return {
        "DisableAppCheck": True,
        "Profiles": {
            "Forza": {
                "Name": "Forza",
                "throttleSettings": {
                    **EXPECTED_HIGH["throttleSettings"],
                    "GripLossValue": 0.6,
                    "EffectIntensity": 2,
                    "TurnAccelerationScale": 0.25,
                    "ForwardAccelerationScale": 1,
                    "AccelerationLimit": 10,
                    "VibrationModeStart": 5,
                    "MinVibration": 5,
                    "MaxVibration": 55,
                    "MinStiffness": 15,
                    "MaxStiffness": 20,
                    "MinResistance": 0,
                    "MaxResistance": 7,
                    "ResistanceSmoothing": 0.4,
                },
                "brakeSettings": {
                    **EXPECTED_HIGH["brakeSettings"],
                    "GripLossValue": 0.05,
                    "EffectIntensity": 1,
                    "MinVibration": 15,
                    "MaxVibration": 20,
                    "MinStiffness": 15,
                    "MaxStiffness": 20,
                    "MinResistance": 0,
                    "MaxResistance": 7,
                    "ResistanceSmoothing": 0.4,
                    "customBrakeKey": 99,
                },
                "RPMRedlineRatio": 0.9,
            },
            "Dirt": {"sentinel": "unchanged"},
        },
        "DSXPort": 6969,
    }


def _run_helper(mode, config, state, preset=PRESET):
    return subprocess.run(
        [
            sys.executable,
            str(HELPER),
            mode,
            "--config",
            str(config),
            "--preset",
            str(preset),
            "--state",
            str(state),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_high_snapshots_and_applies_both_triggers(tmp_path):
    config_path = tmp_path / "runtime with spaces" / "RacingDSX.json"
    config_path.parent.mkdir()
    original = _normal_config()
    config_path.write_text(json.dumps(original))
    state_path = config_path.parent / "trigger-profile-state.json"

    result = _run_helper("high", config_path, state_path)

    assert result.returncode == 0, result.stderr
    actual = json.loads(config_path.read_text())
    assert {
        key: actual["Profiles"]["Forza"]["throttleSettings"][key]
        for key in EXPECTED_HIGH["throttleSettings"]
    } == EXPECTED_HIGH["throttleSettings"]
    assert {
        key: actual["Profiles"]["Forza"]["brakeSettings"][key]
        for key in EXPECTED_HIGH["brakeSettings"]
    } == EXPECTED_HIGH["brakeSettings"]
    assert actual["Profiles"]["Dirt"] == {"sentinel": "unchanged"}
    assert actual["Profiles"]["Forza"]["brakeSettings"]["customBrakeKey"] == 99
    state = json.loads(state_path.read_text())
    assert state["version"] == 1
    assert state["active"] == "high"
    for section, values in EXPECTED_HIGH.items():
        assert state["normal"][section] == {
            key: original["Profiles"]["Forza"][section][key]
            for key in values
        }


def test_repeated_high_preserves_original_snapshot(tmp_path):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    state_path = tmp_path / "state.json"
    assert _run_helper("high", config_path, state_path).returncode == 0
    saved = state_path.read_bytes()

    config = json.loads(config_path.read_text())
    config["Profiles"]["Forza"]["throttleSettings"]["GripLossValue"] = 0.33
    config_path.write_text(json.dumps(config))
    result = _run_helper("high", config_path, state_path)

    assert result.returncode == 0, result.stderr
    assert state_path.read_bytes() == saved
    assert json.loads(config_path.read_text())["Profiles"]["Forza"]["throttleSettings"]["GripLossValue"] == 0.2


def test_normal_restores_exact_values_and_preserves_unrelated_edits(tmp_path):
    config_path = tmp_path / "RacingDSX.json"
    original = _normal_config()
    config_path.write_text(json.dumps(original))
    state_path = tmp_path / "state.json"
    assert _run_helper("high", config_path, state_path).returncode == 0
    config = json.loads(config_path.read_text())
    config["Profiles"]["Forza"]["RPMRedlineRatio"] = 0.95
    config["Profiles"]["Forza"]["brakeSettings"]["customBrakeKey"] = 123
    config_path.write_text(json.dumps(config))

    result = _run_helper("normal", config_path, state_path)

    assert result.returncode == 0, result.stderr
    restored = json.loads(config_path.read_text())
    for section, keys in EXPECTED_HIGH.items():
        for key in keys:
            assert restored["Profiles"]["Forza"][section][key] == original["Profiles"]["Forza"][section][key]
    assert restored["Profiles"]["Forza"]["RPMRedlineRatio"] == 0.95
    assert restored["Profiles"]["Forza"]["brakeSettings"]["customBrakeKey"] == 123
    assert not state_path.exists()


def test_normal_without_state_is_idempotent(tmp_path):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    before = config_path.read_bytes()

    result = _run_helper("normal", config_path, tmp_path / "missing-state.json")

    assert result.returncode == 0
    assert "already selected" in result.stdout
    assert config_path.read_bytes() == before


@pytest.mark.parametrize(
    "mutate, expected_error",
    [
        (lambda config: config.pop("Profiles"), "Profiles"),
        (lambda config: config["Profiles"].pop("Forza"), "Forza"),
        (
            lambda config: config["Profiles"]["Forza"]["throttleSettings"].pop("GripLossValue"),
            "GripLossValue",
        ),
        (
            lambda config: config["Profiles"]["Forza"]["brakeSettings"].__setitem__("MaxVibration", "fast"),
            "MaxVibration",
        ),
    ],
)
def test_invalid_config_fails_without_writing(tmp_path, mutate, expected_error):
    config = _normal_config()
    mutate(config)
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(config))
    before = config_path.read_bytes()
    state_path = tmp_path / "state.json"

    result = _run_helper("high", config_path, state_path)

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert config_path.read_bytes() == before
    assert not state_path.exists()


def test_malformed_config_and_state_fail_without_writing(tmp_path):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text("{broken")
    before = config_path.read_bytes()
    state_path = tmp_path / "state.json"
    malformed_config = _run_helper("high", config_path, state_path)
    assert malformed_config.returncode != 0
    assert config_path.read_bytes() == before
    assert not state_path.exists()

    config_path.write_text(json.dumps(_normal_config()))
    assert _run_helper("high", config_path, state_path).returncode == 0
    high_before = config_path.read_bytes()
    state_path.write_text("{broken")
    malformed_state = _run_helper("normal", config_path, state_path)
    assert malformed_state.returncode != 0
    assert config_path.read_bytes() == high_before
```

- [ ] **Step 2: Run helper tests and verify RED**

Run:

```bash
cd /home/deck/code/dsx4unix && python3 -m pytest tests/test_trigger_profiles.py -q
```

Expected: preset contract passes and helper tests fail because `scripts/apply-trigger-profile.py` is missing.

- [ ] **Step 3: Implement the minimal helper**

Create executable `scripts/apply-trigger-profile.py`:

```python
#!/usr/bin/env python3
import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

SECTIONS = ("throttleSettings", "brakeSettings")


class ProfileError(Exception):
    pass


def load_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ProfileError(f"{label} does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProfileError(f"{label} must contain a JSON object: {path}")
    return value


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def compatible(current, replacement) -> bool:
    if is_number(current) and is_number(replacement):
        return True
    return type(current) is type(replacement)


def forza_sections(config: dict) -> dict:
    try:
        profiles = config["Profiles"]
        forza = profiles["Forza"]
    except (KeyError, TypeError) as exc:
        missing = exc.args[0] if exc.args else "Profiles.Forza"
        raise ProfileError(f"missing or invalid configuration object: {missing}") from exc
    if not isinstance(profiles, dict) or not isinstance(forza, dict):
        raise ProfileError("Profiles and Profiles.Forza must be JSON objects")
    result = {}
    for section in SECTIONS:
        value = forza.get(section)
        if not isinstance(value, dict):
            raise ProfileError(f"Profiles.Forza.{section} must be a JSON object")
        result[section] = value
    return result


def validate_overlay(config_sections: dict, overlay: dict, label: str) -> None:
    if set(overlay) != set(SECTIONS):
        raise ProfileError(f"{label} must contain exactly: {', '.join(SECTIONS)}")
    for section in SECTIONS:
        values = overlay[section]
        if not isinstance(values, dict) or not values:
            raise ProfileError(f"{label}.{section} must be a non-empty JSON object")
        current = config_sections[section]
        for key, replacement in values.items():
            if key not in current:
                raise ProfileError(f"missing configuration key: Profiles.Forza.{section}.{key}")
            if not compatible(current[key], replacement):
                raise ProfileError(
                    f"incompatible value type for Profiles.Forza.{section}.{key}"
                )


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise ProfileError(f"cannot atomically write {path}: {exc}") from exc


def parse_state(path: Path, config_sections: dict) -> dict:
    state = load_object(path, "trigger profile state")
    if state.get("version") != 1 or state.get("active") != "high":
        raise ProfileError("trigger profile state has an unsupported schema")
    normal = state.get("normal")
    if not isinstance(normal, dict):
        raise ProfileError("trigger profile state is missing normal settings")
    validate_overlay(config_sections, normal, "trigger profile state normal settings")
    return state


def apply_high(config_path: Path, preset_path: Path, state_path: Path) -> str:
    config = load_object(config_path, "runtime configuration")
    preset = load_object(preset_path, "high preset")
    sections = forza_sections(config)
    validate_overlay(sections, preset, "high preset")

    if state_path.exists():
        parse_state(state_path, sections)
    else:
        state = {
            "version": 1,
            "active": "high",
            "normal": {
                section: {key: sections[section][key] for key in preset[section]}
                for section in SECTIONS
            },
        }
        atomic_write_json(state_path, state)

    for section in SECTIONS:
        sections[section].update(preset[section])
    atomic_write_json(config_path, config)
    return f"high trigger profile selected: {config_path}"


def apply_normal(config_path: Path, state_path: Path) -> str:
    if not state_path.exists():
        return f"normal trigger profile already selected: {config_path}"

    config = load_object(config_path, "runtime configuration")
    sections = forza_sections(config)
    state = parse_state(state_path, sections)
    for section in SECTIONS:
        sections[section].update(state["normal"][section])
    atomic_write_json(config_path, config)
    try:
        state_path.unlink()
    except OSError as exc:
        raise ProfileError(f"configuration restored but cannot remove state {state_path}: {exc}") from exc
    return f"normal trigger profile selected: {config_path}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("high", "normal"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--preset", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "high":
            message = apply_high(args.config, args.preset, args.state)
        else:
            message = apply_normal(args.config, args.state)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Make it executable:

```bash
cd /home/deck/code/dsx4unix && chmod 0755 scripts/apply-trigger-profile.py
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
cd /home/deck/code/dsx4unix && python3 -m pytest tests/test_trigger_profiles.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Add atomic-replacement failure coverage**

Append this test, which loads the helper module directly, forces the final
rename to fail, and verifies that the destination remains intact:

```python
def _load_helper_module():
    spec = importlib.util.spec_from_file_location("trigger_profile_helper", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_atomic_replace_failure_preserves_destination_and_removes_temp(tmp_path, monkeypatch):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    state_path = tmp_path / "state.json"
    assert _run_helper("high", config_path, state_path).returncode == 0

    config_path.write_text(json.dumps(_normal_config()))
    before = config_path.read_bytes()
    helper = _load_helper_module()

    def fail_replace(source, destination):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(helper.os, "replace", fail_replace)
    with pytest.raises(helper.ProfileError, match="simulated rename failure"):
        helper.apply_high(config_path, PRESET, state_path)

    assert config_path.read_bytes() == before
    assert list(tmp_path.glob(".RacingDSX.json.*")) == []
```

Run:

```bash
cd /home/deck/code/dsx4unix && python3 -m pytest tests/test_trigger_profiles.py -q
```

Expected: all tests pass, including the simulated rename failure.

---

### Task 3: Add launcher commands with RacingDSX-only refresh

**Files:**
- Modify: `tests/test_start_dsx.py`
- Modify: `start_dsx`

**Interfaces:**
- Consumes: commands `high` and `normal` with no trailing arguments.
- Invokes: `python3 scripts/apply-trigger-profile.py MODE --config .runtime/racingdsx/RacingDSX.json --preset config/trigger-presets/high.json --state .runtime/racingdsx/trigger-profile-state.json`.
- Produces: active stack with healthy UDP `6969`/`5300`; only RacingDSX restarts when both services began active.

- [ ] **Step 1: Add a launcher fixture with safe command stubs**

Append this complete fixture to `tests/test_start_dsx.py`. It uses a checkout
path containing spaces and stubs every host-affecting command:

```python
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
```

- [ ] **Step 2: Add failing launcher tests**

Add these assertions:

```python
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
```

The helper stub must exit with `${PROFILE_HELPER_EXIT:-0}` after logging.

- [ ] **Step 3: Run launcher tests and verify RED**

Run:

```bash
cd /home/deck/code/dsx4unix && python3 -m pytest tests/test_start_dsx.py -q
```

Expected: new tests fail because `high` and `normal` are unknown commands.

- [ ] **Step 4: Add launcher paths and usage**

Add near the existing constants in `start_dsx`:

```bash
PROFILE_HELPER="$REPO_ROOT/scripts/apply-trigger-profile.py"
RUNTIME_CONFIG="$REPO_ROOT/.runtime/racingdsx/RacingDSX.json"
HIGH_PRESET="$REPO_ROOT/config/trigger-presets/high.json"
PROFILE_STATE="$REPO_ROOT/.runtime/racingdsx/trigger-profile-state.json"
```

Add usage lines:

```text
  high             Select maximum R2 + L2 feedback and start/refresh the stack
  normal           Restore pre-high R2 + L2 settings and start/refresh the stack
```

- [ ] **Step 5: Implement profile application and safe refresh**

Add these functions before command dispatch:

```bash
refresh_after_profile_change() {
  if systemctl --user --quiet is-active "$HEFESTO_SERVICE" \
      && systemctl --user --quiet is-active "$RACING_SERVICE"; then
    systemctl --user reset-failed "$RACING_SERVICE" 2>/dev/null || true
    systemctl --user restart "$RACING_SERVICE"
    wait_for_udp_port 5300 "$RACING_SERVICE"
    sleep 1
    if ! systemctl --user --quiet is-active "$RACING_SERVICE"; then
      echo "DSX profile switch failed stability check: $RACING_SERVICE is not active" >&2
      systemctl --user status "$RACING_SERVICE" --no-pager --full >&2 || true
      return 1
    fi
    wait_for_udp_port 5300 "$RACING_SERVICE"
    echo "RacingDSX refreshed; Hefesto was left running"
  else
    start_all
  fi
}

select_trigger_profile() {
  local mode="$1"
  if [[ ! -x "$PROFILE_HELPER" ]]; then
    echo "Missing trigger profile helper: $PROFILE_HELPER" >&2
    return 1
  fi
  if [[ ! -f "$HIGH_PRESET" ]]; then
    echo "Missing high trigger preset: $HIGH_PRESET" >&2
    return 1
  fi
  python3 "$PROFILE_HELPER" "$mode" \
    --config "$RUNTIME_CONFIG" \
    --preset "$HIGH_PRESET" \
    --state "$PROFILE_STATE"
  refresh_after_profile_change
}
```

Add dispatch branches:

```bash
  high|normal)
    require_setup
    if (($#)); then
      echo "$cmd does not accept additional arguments" >&2
      exit 2
    fi
    select_trigger_profile "$cmd"
    ;;
```

- [ ] **Step 6: Run launcher and existing regression tests**

Run:

```bash
cd /home/deck/code/dsx4unix && bash -n start_dsx && python3 -m pytest tests/test_start_dsx.py tests/test_stack_bootstrap.py -q
```

Expected: syntax check exits `0`; all listed tests pass.

---

### Task 4: Document the reversible maximum-feedback commands

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: final CLI behavior from Task 3.
- Produces: paste-ready commands and accurate lifecycle/safety explanation.

- [ ] **Step 1: Update launcher command documentation**

Add this command block in the launcher usage section:

```bash
start_dsx high    # maximum R2 throttle + L2 brake feedback
start_dsx normal  # restore the exact trigger settings saved before high
```

Document that `high` lowers grip-loss thresholds, strengthens baseline resistance and vibration, and reacts immediately on both triggers. State clearly that the profile is intentionally forceful.

- [ ] **Step 2: Document restoration and service behavior**

Explain that the first `high` selection snapshots only affected Forza trigger keys under `.runtime/racingdsx/`; repeated `high` does not overwrite that snapshot; `normal` restores it exactly; unrelated and DiRT settings are preserved. Explain that an already-running stack restarts RacingDSX only, leaving Hefesto and the Bluetooth controller handle intact.

- [ ] **Step 3: Validate documentation formatting**

Run:

```bash
cd /home/deck/code/dsx4unix && git diff --check -- README.md docs/plans/2026-07-17-high-trigger-profile-design.md docs/superpowers/plans/2026-07-17-high-trigger-profile.md
```

Expected: exit `0` with no output.

---

### Task 5: Run complete automated and static verification

**Files:**
- Verify all intentional source, tests, config, and docs.

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: fresh evidence that existing behavior and new behavior pass together.

- [ ] **Step 1: Run syntax and JSON checks**

```bash
cd /home/deck/code/dsx4unix && \
  bash -n start_dsx scripts/bootstrap-stack.sh && \
  python3 -m py_compile scripts/apply-trigger-profile.py && \
  python3 -m json.tool config/trigger-presets/high.json >/dev/null
```

Expected: exit `0`.

- [ ] **Step 2: Run all repository Python tests**

```bash
cd /home/deck/code/dsx4unix && python3 -m pytest tests -q
```

Expected: all tests pass with zero failures.

- [ ] **Step 3: Run helper lint/static checks available in the repository**

If Ruff is available in the bundled Hefesto environment, run:

```bash
cd /home/deck/code/dsx4unix && vendor/hefesto-dualsense4unix/.venv/bin/ruff check scripts/apply-trigger-profile.py tests/test_trigger_profiles.py tests/test_start_dsx.py
```

Expected: exit `0`. If that Ruff configuration rejects repository-external paths, run the installed `ruff` binary directly with the same file list and report the exact command/output.

- [ ] **Step 4: Inspect the scoped diff without touching unrelated files**

```bash
cd /home/deck/code/dsx4unix && \
  git diff --check && \
  git status --short && \
  git diff -- start_dsx scripts/apply-trigger-profile.py config/trigger-presets/high.json tests/test_trigger_profiles.py tests/test_start_dsx.py README.md docs/plans/2026-07-17-high-trigger-profile-design.md docs/superpowers/plans/2026-07-17-high-trigger-profile.md
```

Expected: no whitespace errors; only intentional files are attributed to this feature. Existing generated artifacts, modified submodule state, and unrelated untracked files remain unchanged and unstaged.

---

### Task 6: Perform controlled live switching without destabilizing Bluetooth

**Files:**
- Runtime only: `.runtime/racingdsx/RacingDSX.json`, `.runtime/racingdsx/trigger-profile-state.json`.

**Interfaces:**
- Consumes: verified launcher and a connected DualSense.
- Produces: real proof of high apply, exact normal restore, RacingDSX-only PID change, and controller survival.

- [ ] **Step 1: Capture the pre-switch evidence**

Record the current time, connected BlueZ devices, Hefesto/RacingDSX PIDs, UDP listeners, DualSense hidraw path, and a normalized JSON extraction of both Forza trigger sections. Do not restart any service during discovery.

- [ ] **Step 2: Select high and verify process isolation**

Run the exact command:

```bash
cd /home/deck/code/dsx4unix && ./start_dsx high
```

Verify:

- `racingdsx.service` has a new PID and is active.
- `hefesto-dualsense4unix.service` retained its original PID.
- UDP `6969` and `5300` are listening.
- Live Forza R2/L2 keys exactly match `config/trigger-presets/high.json`.
- State contains the exact pre-switch values.
- The controller remains connected and the same hidraw node is open by Hefesto.

- [ ] **Step 3: Observe beyond the old Bluetooth failure window**

Monitor for at least 30 seconds. Require no Bluetooth disconnect, HIDP socket error, CRC error, unexpected start frame, controller offline, or Hefesto daemon failure.

- [ ] **Step 4: Restore normal and verify exact round trip**

Run:

```bash
cd /home/deck/code/dsx4unix && ./start_dsx normal
```

Compare every saved trigger key against the pre-switch extraction. Require exact equality, absence of the state file, unchanged unrelated values, active UDP listeners, unchanged Hefesto PID/controller handle, and no new transport errors.

- [ ] **Step 5: Report hardware acceptance separately**

Report automated and lifecycle verification as complete. Treat subjective in-game L2/R2 force and timing as a separate hardware/gameplay acceptance result; do not claim feel was verified unless FH4 telemetry was actively exercised.

---

### Task 7: Final review and optional focused commit

**Files:**
- Review only the intentional files listed in the file map.

**Interfaces:**
- Consumes: fresh automated and live evidence.
- Produces: reviewed working tree; commit only if explicitly requested.

- [ ] **Step 1: Load and follow verification-before-completion**

Re-run any check whose evidence is stale after the last edit. Do not infer success from earlier runs.

- [ ] **Step 2: Review spec coverage**

Confirm both triggers, exact restoration, idempotence, malformed-data safety, spaces in paths, RacingDSX-only restart, full-stack fallback, unchanged existing commands, and Bluetooth preservation each have passing evidence.

- [ ] **Step 3: Inspect final status and diff**

Use `git status --short`, `git diff --check`, and scoped `git diff`. Do not reset, clean, stage, or modify pre-existing unrelated files.

- [ ] **Step 4: Commit only after explicit user direction**

If requested, stage only intentional feature files and use a focused commit message such as:

```bash
git commit -m "feat: add reversible high trigger profile"
```

Do not include generated RacingDSX binaries, `obj/`, the modified Hefesto submodule worktree, or unrelated untracked files.
