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
