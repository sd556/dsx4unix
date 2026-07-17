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
    assert result.stdout == f"high trigger profile selected: {config_path}\n"
    assert result.stderr == ""
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
    assert result.stdout == f"normal trigger profile selected: {config_path}\n"
    assert result.stderr == ""
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
    assert result.stdout == f"normal trigger profile already selected: {config_path}\n"
    assert result.stderr == ""
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


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: state["normal"]["throttleSettings"].pop("GripLossValue"),
        lambda state: state["normal"]["brakeSettings"].__setitem__("customBrakeKey", 99),
        lambda state: state["normal"].pop("brakeSettings"),
        lambda state: state.__setitem__("unrelated", True),
        lambda state: state.pop("active"),
    ],
    ids=("missing-key", "extra-key", "incomplete-section", "extra-root-key", "missing-root-key"),
)
def test_invalid_state_schema_is_non_mutating(tmp_path, mutate):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    state_path = tmp_path / "state.json"
    assert _run_helper("high", config_path, state_path).returncode == 0
    config = json.loads(config_path.read_text())
    config["Profiles"]["Forza"]["RPMRedlineRatio"] = 0.97
    config["Profiles"]["Forza"]["brakeSettings"]["customBrakeKey"] = 321
    config_path.write_text(json.dumps(config))
    state = json.loads(state_path.read_text())
    mutate(state)
    state_path.write_text(json.dumps(state))
    config_before, state_before = config_path.read_bytes(), state_path.read_bytes()

    result = _run_helper("normal", config_path, state_path)

    assert result.returncode != 0
    assert result.stderr.startswith("error: ")
    assert "Traceback" not in result.stderr
    assert config_path.read_bytes() == config_before
    assert state_path.read_bytes() == state_before


@pytest.mark.parametrize("version", (True, 1.0), ids=("boolean", "float"))
def test_invalid_state_version_type_is_non_mutating(tmp_path, version):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    state_path = tmp_path / "state.json"
    assert _run_helper("high", config_path, state_path).returncode == 0
    state = json.loads(state_path.read_text())
    state["version"] = version
    state_path.write_text(json.dumps(state))
    config_before, state_before = config_path.read_bytes(), state_path.read_bytes()

    result = _run_helper("normal", config_path, state_path)

    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr == "error: trigger profile state has an unsupported schema\n"
    assert config_path.read_bytes() == config_before
    assert state_path.read_bytes() == state_before


def test_repeated_high_rejects_state_keys_not_matching_preset(tmp_path):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    state_path = tmp_path / "state.json"
    assert _run_helper("high", config_path, state_path).returncode == 0
    state = json.loads(state_path.read_text())
    state["normal"]["throttleSettings"].pop("GripLossValue")
    state_path.write_text(json.dumps(state))
    config_before, state_before = config_path.read_bytes(), state_path.read_bytes()

    result = _run_helper("high", config_path, state_path)

    assert result.returncode != 0
    assert result.stderr.startswith("error: ")
    assert config_path.read_bytes() == config_before
    assert state_path.read_bytes() == state_before


@pytest.mark.parametrize("source", ("config", "preset", "state"))
def test_non_utf8_json_is_a_concise_non_mutating_error(tmp_path, source):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    preset_path = tmp_path / "high.json"
    preset_path.write_bytes(PRESET.read_bytes())
    state_path = tmp_path / "state.json"
    mode = "high"
    if source == "config":
        config_path.write_bytes(b"\xff")
    elif source == "preset":
        preset_path.write_bytes(b"\xff")
    else:
        assert _run_helper("high", config_path, state_path, preset_path).returncode == 0
        state_path.write_bytes(b"\xff")
        mode = "normal"
    config_before = config_path.read_bytes()
    state_before = state_path.read_bytes() if state_path.exists() else None

    result = _run_helper(mode, config_path, state_path, preset_path)

    assert result.returncode != 0
    assert result.stderr.startswith("error: ")
    assert "Traceback" not in result.stderr
    assert config_path.read_bytes() == config_before
    assert (state_path.read_bytes() if state_path.exists() else None) == state_before


def test_first_high_state_write_failure_does_not_change_config(tmp_path, monkeypatch):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    state_path = tmp_path / "state.json"
    before = config_path.read_bytes()
    helper = _load_helper_module()

    def fail_state_write(path, payload):
        assert path == state_path
        raise helper.ProfileError("simulated state write failure")

    monkeypatch.setattr(helper, "atomic_write_json", fail_state_write)
    with pytest.raises(helper.ProfileError, match="simulated state write failure"):
        helper.apply_high(config_path, PRESET, state_path)
    assert config_path.read_bytes() == before
    assert not state_path.exists()


def test_cleanup_failure_does_not_mask_atomic_write_error(tmp_path, monkeypatch):
    destination = tmp_path / "RacingDSX.json"
    destination.write_text("original")
    helper = _load_helper_module()

    def fail_replace(source, target):
        raise OSError("primary rename failure")

    monkeypatch.setattr(helper.os, "replace", fail_replace)
    monkeypatch.setattr(helper.Path, "unlink", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("secondary cleanup failure")))
    with pytest.raises(helper.ProfileError, match="primary rename failure"):
        helper.atomic_write_json(destination, {"replacement": True})
    assert destination.read_text() == "original"


def test_mkdir_failure_is_a_concise_cli_error(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    state_path = tmp_path / "missing" / "state.json"
    helper = _load_helper_module()
    original_mkdir = helper.Path.mkdir

    def fail_mkdir(path, *args, **kwargs):
        if path == state_path.parent:
            raise OSError("simulated mkdir failure")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(helper.Path, "mkdir", fail_mkdir)
    monkeypatch.setattr(sys, "argv", [str(HELPER), "high", "--config", str(config_path), "--preset", str(PRESET), "--state", str(state_path)])
    assert helper.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "simulated mkdir failure" in captured.err
    assert "Traceback" not in captured.err


def test_stat_failure_is_a_concise_cli_error(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "RacingDSX.json"
    config_path.write_text(json.dumps(_normal_config()))
    state_path = tmp_path / "state.json"
    assert _run_helper("high", config_path, state_path).returncode == 0
    helper = _load_helper_module()
    original_stat = helper.Path.stat

    def fail_stat(path, *args, **kwargs):
        if path == config_path:
            raise OSError("simulated stat failure")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(helper.Path, "stat", fail_stat)
    monkeypatch.setattr(sys, "argv", [str(HELPER), "high", "--config", str(config_path), "--preset", str(PRESET), "--state", str(state_path)])
    assert helper.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "simulated stat failure" in captured.err


def test_state_unlink_failure_keeps_retryable_state_and_unrelated_edits(tmp_path, monkeypatch):
    config_path = tmp_path / "RacingDSX.json"
    original = _normal_config()
    config_path.write_text(json.dumps(original))
    state_path = tmp_path / "state.json"
    assert _run_helper("high", config_path, state_path).returncode == 0
    config = json.loads(config_path.read_text())
    config["Profiles"]["Forza"]["RPMRedlineRatio"] = 0.98
    config_path.write_text(json.dumps(config))
    helper = _load_helper_module()
    original_unlink = helper.Path.unlink

    def fail_unlink(path, *args, **kwargs):
        if path == state_path:
            raise OSError("simulated state unlink failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(helper.Path, "unlink", fail_unlink)
    with pytest.raises(helper.ProfileError, match="configuration restored but cannot remove state"):
        helper.apply_normal(config_path, PRESET, state_path)
    restored = json.loads(config_path.read_text())
    for section, keys in EXPECTED_HIGH.items():
        for key in keys:
            assert restored["Profiles"]["Forza"][section][key] == original["Profiles"]["Forza"][section][key]
    assert restored["Profiles"]["Forza"]["RPMRedlineRatio"] == 0.98
    assert state_path.exists()
