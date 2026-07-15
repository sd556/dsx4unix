"""YAML configuration loader."""

from __future__ import annotations
from pathlib import Path
from typing import Any

import yaml

from dsx4unix.config.models import Profile

# Ship built-in profiles
_BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "forza": {
        "game": "forza",
        "name": "Forza Motorsport 7/8",
        "telemetry_port": 30778,
        "throttle": {
            "trigger_mode": "vibration",
            "grip_loss_value": 0.6,
            "effect_intensity": 1.0,
            "turn_acceleration_scale": 0.25,
            "forward_acceleration_scale": 1.0,
            "acceleration_limit": 10,
            "vibration_mode_start": 5,
            "min_vibration": 5,
            "max_vibration": 55,
            "vibration_smoothing": 1.0,
            "min_stiffness": 255,
            "max_stiffness": 175,
            "min_resistance": 0,
            "max_resistance": 3,
            "resistance_smoothing": 0.9,
        },
        "brake": {
            "trigger_mode": "vibration",
            "grip_loss_value": 0.05,
            "effect_intensity": 1.0,
            "vibration_start": 0,
            "vibration_mode_start": 30,
            "min_vibration": 15,
            "max_vibration": 20,
            "vibration_smoothing": 1.0,
            "min_stiffness": 150,
            "max_stiffness": 5,
            "min_resistance": 0,
            "max_resistance": 7,
            "resistance_smoothing": 0.4,
        },
        "lightbar": {
            "rpm_redline_ratio": 0.9,
        },
    },
    "fh4": {
        "game": "forza",
        "name": "Forza Horizon 4",
        "telemetry_port": 5300,
        "throttle": {
            "trigger_mode": "vibration",
            "grip_loss_value": 0.6,
            "effect_intensity": 1.0,
            "turn_acceleration_scale": 0.25,
            "forward_acceleration_scale": 1.0,
            "acceleration_limit": 10,
            "vibration_mode_start": 5,
            "min_vibration": 5,
            "max_vibration": 55,
            "vibration_smoothing": 1.0,
            "min_stiffness": 255,
            "max_stiffness": 175,
            "min_resistance": 0,
            "max_resistance": 3,
            "resistance_smoothing": 0.9,
        },
        "brake": {
            "trigger_mode": "vibration",
            "grip_loss_value": 0.05,
            "effect_intensity": 1.0,
            "vibration_start": 0,
            "vibration_mode_start": 30,
            "min_vibration": 15,
            "max_vibration": 20,
            "vibration_smoothing": 1.0,
            "min_stiffness": 150,
            "max_stiffness": 5,
            "min_resistance": 0,
            "max_resistance": 7,
            "resistance_smoothing": 0.4,
        },
        "lightbar": {
            "rpm_redline_ratio": 0.9,
        },
    },
    "dirt": {
        "game": "dirt",
        "name": "DiRT Rally",
        "telemetry_port": 20777,
        "throttle": {
            "trigger_mode": "vibration",
            "grip_loss_value": 0.6,
            "effect_intensity": 1.0,
            "turn_acceleration_scale": 0.25,
            "forward_acceleration_scale": 1.0,
            "acceleration_limit": 10,
            "vibration_mode_start": 5,
            "min_vibration": 5,
            "max_vibration": 55,
            "vibration_smoothing": 1.0,
            "min_stiffness": 255,
            "max_stiffness": 175,
            "min_resistance": 0,
            "max_resistance": 3,
            "resistance_smoothing": 0.9,
        },
        "brake": {
            "trigger_mode": "vibration",
            "grip_loss_value": 0.05,
            "effect_intensity": 1.0,
            "vibration_start": 0,
            "vibration_mode_start": 30,
            "min_vibration": 15,
            "max_vibration": 20,
            "vibration_smoothing": 1.0,
            "min_stiffness": 150,
            "max_stiffness": 5,
            "min_resistance": 0,
            "max_resistance": 7,
            "resistance_smoothing": 0.4,
        },
        "lightbar": {
            "rpm_redline_ratio": 0.9,
        },
    },
}


def list_profiles() -> list[str]:
    return list(_BUILTIN_PROFILES.keys())


def load_profile(name: str = "forza") -> Profile:
    """Load a built-in profile by name."""
    data = _BUILTIN_PROFILES.get(name)
    if data is None:
        known = ", ".join(sorted(_BUILTIN_PROFILES.keys()))
        raise ValueError(f"Unknown profile '{name}'. Available: {known}")
    return Profile(**data)


def load_config(path: Path) -> Profile:
    """Load a profile from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return Profile(**data)
